from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .config import APP_VERSION, PROJECT_ROOT, settings
from .market_edge import build_market_recommendation_row, calculate_yes_no_edges, extract_market_prices, normalize_probability
from .platform_safety import redact_data, redact_text, safety_flags, secret_scan

AI_NEWS_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "ai_news_odds"
AI_NEWS_AUDIT_DIR = PROJECT_ROOT / "runtime" / "ai_news_odds_audit"
AI_NEWS_SOURCES_DIR = PROJECT_ROOT / "runtime" / "ai_news_sources"
AI_NEWS_ADJUSTMENTS_DIR = PROJECT_ROOT / "runtime" / "ai_news_adjustments"
ADJUSTMENTS_PATH = AI_NEWS_ADJUSTMENTS_DIR / "adjustments.jsonl"
SOURCES_PATH = AI_NEWS_SOURCES_DIR / "sources.jsonl"
AUDIT_PATH = AI_NEWS_AUDIT_DIR / "audit.jsonl"

REVIEW_ONLY_NOTE = (
    "AI News Odds adjustments are draft fair-probability updates for human review only. "
    "They do not change Polymarket prices, approve trades, place orders, cancel orders, arm live trading, "
    "disable read-only mode, or bypass backend gates."
)

SOURCE_TYPE_WEIGHTS = {
    "primary": 1.00,
    "primary_official": 1.00,
    "government": 0.95,
    "regulator": 0.95,
    "league_or_organization": 0.95,
    "direct_announcement": 0.90,
    "wire": 0.85,
    "major_news": 0.80,
    "specialist": 0.70,
    "local": 0.55,
    "blog": 0.40,
    "social": 0.30,
    "forum": 0.20,
    "rumor": 0.20,
    "unknown": 0.25,
}

PRIMARY_DOMAINS = {"fifa.com", "sec.gov", "fec.gov", "whitehouse.gov", "congress.gov", "who.int", "cdc.gov", "fda.gov", "uefa.com", "olympics.com", "nba.com", "nfl.com", "mlb.com", "nhl.com", "premierleague.com"}
WIRE_DOMAINS = {"reuters.com", "apnews.com", "ap.org", "bloomberg.com", "afp.com"}
MAJOR_NEWS_DOMAINS = {"nytimes.com", "wsj.com", "washingtonpost.com", "bbc.com", "bbc.co.uk", "cnn.com", "nbcnews.com", "cbsnews.com", "abcnews.go.com", "theguardian.com", "ft.com", "axios.com", "politico.com"}
SPECIALIST_DOMAINS = {"espn.com", "theathletic.com", "sports.yahoo.com", "fivethirtyeight.com", "sabato", "realclearpolitics.com", "coindesk.com", "cointelegraph.com", "theverge.com", "techcrunch.com"}
SOCIAL_DOMAINS = {"x.com", "twitter.com", "truthsocial.com", "facebook.com", "instagram.com", "tiktok.com", "youtube.com", "threads.net", "bsky.app"}
FORUM_DOMAINS = {"reddit.com", "4chan.org", "discord.com", "telegram.org", "bitcointalk.org"}
LOW_SIGNAL_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid"}

POSITIVE_TERMS = {"wins", "win", "confirmed", "cleared", "approved", "leading", "surges", "qualified", "endorsed", "returns", "healthy", "favorite", "poll lead", "positive", "beats", "support", "upgraded"}
NEGATIVE_TERMS = {"injury", "injured", "out", "withdraw", "withdraws", "banned", "charged", "indicted", "suspended", "loses", "loss", "negative", "denied", "rejected", "ill", "doubt", "doubtful", "under investigation", "downgraded"}
CONTRADICTION_TERMS = {"denies", "not true", "false", "contradicts", "refutes", "disputes", "unconfirmed", "rumor", "hoax"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_id(prefix: str = "news_odds") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _ensure_runtime_dirs() -> None:
    AI_NEWS_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    AI_NEWS_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    AI_NEWS_SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    AI_NEWS_ADJUSTMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_runtime_dirs()
    safe = redact_data(row)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe, sort_keys=True, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(redact_data(parsed))
        except json.JSONDecodeError:
            rows.append({"adjustment_id": _record_id("invalid_news_odds"), "status": "invalid_json", "secret_values_returned": False})
    return rows


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    for candidate in [text, text.replace("Z", "+00:00")]:
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"]:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def normalize_source_url(url: Any) -> str:
    """Return a stable, redacted URL without common tracking parameters."""
    raw = redact_text(str(url or "")).strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in LOW_SIGNAL_TRACKING_PARAMS])
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", query, ""))


def canonicalize_source_domain(url: Any) -> str:
    normalized = normalize_source_url(url)
    if not normalized:
        return ""
    netloc = urlparse(normalized).netloc.lower()
    for prefix in ["www.", "m.", "amp."]:
        if netloc.startswith(prefix):
            netloc = netloc[len(prefix):]
    return netloc


def _source_text(source: dict[str, Any]) -> str:
    return " ".join(str(source.get(key) or "") for key in ["title", "snippet", "summary", "claim", "notes", "source_type", "publisher"])


def classify_source_type(source: dict[str, Any]) -> str:
    explicit = str(source.get("source_type") or source.get("type") or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "official": "primary",
        "primary_official_source": "primary",
        "government_official": "government",
        "regulator_government": "regulator",
        "wire_service": "wire",
        "major_outlet": "major_news",
        "social_media": "social",
        "forum_rumor": "forum",
    }
    if explicit in aliases:
        return aliases[explicit]
    if explicit in SOURCE_TYPE_WEIGHTS:
        return explicit
    domain = canonicalize_source_domain(source.get("url") or source.get("source_url") or "")
    text = _source_text(source).lower()
    if domain.endswith(".gov") or domain in PRIMARY_DOMAINS:
        return "government" if domain.endswith(".gov") else "primary"
    if domain in WIRE_DOMAINS:
        return "wire"
    if domain in MAJOR_NEWS_DOMAINS:
        return "major_news"
    if domain in SPECIALIST_DOMAINS or any(token in domain for token in ["espn", "theathletic", "politico", "coindesk"]):
        return "specialist"
    if domain in SOCIAL_DOMAINS or any(token in domain for token in ["twitter", "x.com", "instagram", "tiktok"]):
        return "social"
    if domain in FORUM_DOMAINS or "reddit" in domain or "forum" in text:
        return "forum"
    if "official" in text or "press release" in text:
        return "primary"
    if "blog" in text or "newsletter" in text:
        return "blog"
    return "unknown"


def source_weight_table() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "title": "AI News Odds Source Weights",
        "weights": {
            "primary": float(getattr(settings, "ai_news_source_weight_primary", SOURCE_TYPE_WEIGHTS["primary"])),
            "government": float(getattr(settings, "ai_news_source_weight_government", SOURCE_TYPE_WEIGHTS["government"])),
            "regulator": float(getattr(settings, "ai_news_source_weight_regulator", SOURCE_TYPE_WEIGHTS["regulator"])),
            "wire": float(getattr(settings, "ai_news_source_weight_wire", SOURCE_TYPE_WEIGHTS["wire"])),
            "major_news": float(getattr(settings, "ai_news_source_weight_major_news", SOURCE_TYPE_WEIGHTS["major_news"])),
            "specialist": float(getattr(settings, "ai_news_source_weight_specialist", SOURCE_TYPE_WEIGHTS["specialist"])),
            "local": float(getattr(settings, "ai_news_source_weight_local", SOURCE_TYPE_WEIGHTS["local"])),
            "blog": float(getattr(settings, "ai_news_source_weight_blog", SOURCE_TYPE_WEIGHTS["blog"])),
            "social": float(getattr(settings, "ai_news_source_weight_social", SOURCE_TYPE_WEIGHTS["social"])),
            "forum": float(getattr(settings, "ai_news_source_weight_forum", SOURCE_TYPE_WEIGHTS["forum"])),
            "unknown": float(getattr(settings, "ai_news_source_weight_unknown", SOURCE_TYPE_WEIGHTS["unknown"])),
        },
        "principles": [
            "More copied sources do not automatically create more confidence.",
            "Multiple independent high-quality sources receive more weight than many low-quality repeats.",
            "Contradictions and rumors reduce confidence and adjustment caps.",
            "Source weighting supports review; it does not prove truth or imply trade approval.",
        ],
        "review_only": True,
        "source_weighting_does_not_imply_truth": True,
        "corroboration_does_not_imply_certainty": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
    })


def _weight_for_source_type(source_type: str) -> float:
    table = source_weight_table()["weights"]
    return float(table.get(source_type, table.get("unknown", 0.25)))


def score_source_credibility(source: dict[str, Any]) -> dict[str, Any]:
    source_type = classify_source_type(source)
    base = _weight_for_source_type(source_type)
    text = _source_text(source).lower()
    if any(token in text for token in ["rumor", "unverified", "anonymous source", "allegedly"]):
        base *= 0.65
    if any(token in text for token in ["official", "statement", "press release", "court filing", "regulator"]):
        base = min(1.0, base + 0.08)
    return {
        "source_type": source_type,
        "credibility_score": round(max(0.0, min(base, 1.0)), 3),
        "domain": canonicalize_source_domain(source.get("url") or source.get("source_url") or ""),
        "rationale": f"Classified as {source_type}; transparent default weight applied.",
    }


def score_source_recency(published_at: Any, market_close_time: Any | None = None) -> dict[str, Any]:
    parsed = _parse_datetime(published_at)
    if parsed is None:
        return {"recency_score": 0.35, "age_days": None, "warning": "Published date unavailable; recency discounted."}
    now = datetime.now(timezone.utc)
    age_days = max(0.0, (now - parsed).total_seconds() / 86400.0)
    if market_close_time:
        close = _parse_datetime(market_close_time)
        if close and parsed > close:
            return {"recency_score": 0.25, "age_days": round(age_days, 2), "warning": "Source appears after market close/resolution; verify applicability."}
    if age_days <= 2:
        score = 1.0
    elif age_days <= 7:
        score = 0.85
    elif age_days <= 30:
        score = 0.70
    elif age_days <= 90:
        score = 0.50
    else:
        score = 0.25
    return {"recency_score": round(score, 3), "age_days": round(age_days, 2), "warning": "" if score >= 0.5 else "Source is stale for a news adjustment."}


def _tokens(text: Any) -> set[str]:
    stop = {"will", "the", "and", "for", "with", "that", "this", "from", "into", "about", "does", "have", "win", "yes", "no", "market", "polymarket"}
    return {token for token in re.findall(r"[a-z0-9]{3,}", str(text or "").lower()) if token not in stop}


def score_source_relevance(source: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    market_text = " ".join(str(market.get(key) or "") for key in ["question", "title", "market_title", "slug", "family_title"])
    source_text = _source_text(source)
    market_tokens = _tokens(market_text)
    source_tokens = _tokens(source_text)
    if not market_tokens or not source_tokens:
        return {"relevance_score": 0.25, "matched_terms": [], "warning": "Market/source terms unavailable; relevance discounted."}
    matches = sorted(market_tokens & source_tokens)
    base = min(1.0, len(matches) / max(4, len(market_tokens) * 0.5))
    if any(term in source_text.lower() for term in ["official", "resolution", "confirmed", "injury", "poll", "court", "filing", "press conference"]):
        base = min(1.0, base + 0.15)
    return {"relevance_score": round(max(base, 0.05), 3), "matched_terms": matches[:20], "warning": "" if base >= 0.35 else "Low term overlap; verify relevance to resolution criteria."}


def _source_signature(source: dict[str, Any]) -> str:
    text = str(source.get("claim") or source.get("title") or source.get("snippet") or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [word for word in text.split() if len(word) > 2][:16]
    return " ".join(words)


def detect_duplicate_or_syndicated_sources(sources: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    unique_sources: list[dict[str, Any]] = []
    duplicate_count = 0
    for index, raw in enumerate(sources):
        source = dict(raw)
        signature = _source_signature(source) or canonicalize_source_domain(source.get("url") or "") or f"source_{index}"
        group_id = "dup_" + hashlib.sha1(signature.encode("utf-8")).hexdigest()[:10]
        source["duplicate_group_id"] = group_id
        source["normalized_url"] = normalize_source_url(source.get("url") or source.get("source_url") or "")
        source["canonical_domain"] = canonicalize_source_domain(source.get("url") or source.get("source_url") or "")
        if group_id in groups:
            source["is_duplicate_or_syndicated"] = True
            duplicate_count += 1
        else:
            source["is_duplicate_or_syndicated"] = False
            unique_sources.append(source)
        groups.setdefault(group_id, []).append(source)
    duplicate_groups = [
        {"duplicate_group_id": group_id, "count": len(items), "domains": sorted({item.get("canonical_domain", "") for item in items if item.get("canonical_domain")}), "representative_title": items[0].get("title") or items[0].get("claim") or ""}
        for group_id, items in groups.items()
        if len(items) > 1
    ]
    return {
        "source_count": len(sources),
        "unique_source_count": len(unique_sources),
        "independent_source_count": len(unique_sources),
        "duplicate_source_count": duplicate_count,
        "unique_sources": unique_sources,
        "duplicate_groups": duplicate_groups,
        "annotated_sources": [item for group in groups.values() for item in group],
        "duplicate_penalty_applied": duplicate_count > 0,
    }


def _claim_key(source: dict[str, Any]) -> str:
    text = str(source.get("claim") or source.get("title") or source.get("snippet") or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [word for word in text.split() if word not in {"the", "and", "for", "with", "from", "that", "this", "after", "before"}]
    return " ".join(words[:10]) or _source_signature(source)


def cluster_evidence_claims(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated = detect_duplicate_or_syndicated_sources(sources).get("annotated_sources", [])
    clusters: dict[str, list[dict[str, Any]]] = {}
    for source in annotated:
        key = _claim_key(source) or f"claim_{len(clusters)}"
        clusters.setdefault(key, []).append(source)
    out: list[dict[str, Any]] = []
    for idx, (key, items) in enumerate(clusters.items(), start=1):
        contradiction = any(any(term in _source_text(item).lower() for term in CONTRADICTION_TERMS) or str(item.get("claim_stance") or "").lower() in {"against", "contradicts", "opposes"} for item in items)
        corroboration = score_independent_corroboration({"sources": items, "claim_key": key, "contradiction": contradiction})
        out.append({
            "claim_cluster_id": f"claim_{idx}_{hashlib.sha1(key.encode('utf-8')).hexdigest()[:8]}",
            "claim_key": key,
            "claim_summary": redact_text(items[0].get("claim") or items[0].get("title") or items[0].get("snippet") or "Evidence claim")[:300],
            "source_count": len(items),
            "independent_source_count": corroboration.get("independent_source_count"),
            "duplicate_source_count": len([item for item in items if item.get("is_duplicate_or_syndicated")]),
            "domains": sorted({canonicalize_source_domain(item.get("url") or "") for item in items if canonicalize_source_domain(item.get("url") or "")}),
            "contradiction_detected": contradiction,
            "corroboration_score": corroboration.get("corroboration_score"),
            "sources": items,
        })
    return sorted(out, key=lambda row: row.get("corroboration_score", 0), reverse=True)


def score_independent_corroboration(claim_cluster: dict[str, Any]) -> dict[str, Any]:
    sources = list(claim_cluster.get("sources") or [])
    if not sources:
        return {"corroboration_score": 0.0, "independent_source_count": 0, "duplicate_source_count": 0, "source_diversity_count": 0, "contradiction_penalty": 0.0}
    dedup = detect_duplicate_or_syndicated_sources(sources)
    unique = dedup["unique_sources"]
    scores = [score_source_credibility(source)["credibility_score"] for source in unique]
    avg_cred = sum(scores) / len(scores) if scores else 0.0
    diversity = len({canonicalize_source_domain(source.get("url") or "") for source in unique if canonicalize_source_domain(source.get("url") or "")})
    independent_count = len(unique)
    base = min(1.0, (independent_count / 4.0) * 0.45 + avg_cred * 0.45 + min(diversity / 4.0, 1.0) * 0.10)
    contradiction = bool(claim_cluster.get("contradiction") or any(any(term in _source_text(source).lower() for term in CONTRADICTION_TERMS) for source in unique))
    contradiction_penalty = 0.35 if contradiction else 0.0
    duplicate_penalty = min(0.20, dedup.get("duplicate_source_count", 0) * 0.03)
    score = max(0.0, min(1.0, base - contradiction_penalty - duplicate_penalty))
    return {
        "corroboration_score": round(score, 3),
        "independent_source_count": independent_count,
        "duplicate_source_count": dedup.get("duplicate_source_count", 0),
        "source_diversity_count": diversity,
        "average_credibility_score": round(avg_cred, 3),
        "contradiction_penalty": contradiction_penalty,
        "duplicate_penalty": round(duplicate_penalty, 3),
    }


def build_market_search_plan(market: dict[str, Any], operator_notes: str | None = None, prior_context: dict[str, Any] | None = None) -> dict[str, Any]:
    title = redact_text(market.get("question") or market.get("title") or market.get("market_title") or "Polymarket market")[:240]
    slug = redact_text(market.get("slug") or market.get("market_slug") or "")[:160]
    family = redact_text(market.get("market_family_id") or market.get("family_id") or market.get("family_title") or "")[:160]
    outcomes = []
    raw_outcomes = market.get("outcomes") or []
    if isinstance(raw_outcomes, list):
        for outcome in raw_outcomes[:6]:
            if isinstance(outcome, dict):
                outcomes.append(str(outcome.get("name") or outcome.get("title") or "")[:80])
            else:
                outcomes.append(str(outcome)[:80])
    context_terms = " ".join([title, slug.replace("-", " "), family.replace("_", " "), " ".join(outcomes), redact_text(operator_notes or "")[:160]])
    base = re.sub(r"\s+", " ", context_terms).strip()
    queries = [
        f"{title} official update",
        f"{title} latest news",
        f"{title} contradiction denied false rumor",
        f"{title} primary source statement",
        f"{title} resolution criteria news",
        f"{base} market relevant evidence",
    ]
    if family:
        queries.append(f"{family} latest official news market outcomes")
    if outcomes:
        queries.append(f"{title} {' '.join(outcomes[:3])} comparison news")
    clean: list[dict[str, str]] = []
    seen: set[str] = set()
    labels = ["primary-source", "latest-news", "contradiction", "official-update", "market-resolution", "domain-specific", "family", "outcome-comparison"]
    for idx, query in enumerate(queries):
        q = redact_text(query)[:220]
        if q.lower() not in seen:
            clean.append({"query_type": labels[idx] if idx < len(labels) else "supplemental", "query": q})
            seen.add(q.lower())
    return safety_flags({
        "version": APP_VERSION,
        "market_id_or_slug": redact_text(market.get("id") or market.get("market_id") or slug or title),
        "market_title": title,
        "queries": clean[: max(1, min(int(getattr(settings, "openai_web_search_max_queries", 5)), 12))],
        "source": "deterministic_query_planner",
        "secrets_included": False,
        "operator_notes_redacted": bool(operator_notes),
        "prior_context_used": bool(prior_context),
        "review_only": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
    })


def estimate_event_direction(event: dict[str, Any], market: dict[str, Any]) -> str:
    text = (_source_text(event) + " " + str(event.get("claim_summary") or "") + " " + str(event.get("event_summary") or "")).lower()
    stance = str(event.get("claim_stance") or event.get("stance") or "").lower()
    if stance in {"against", "negative", "opposes", "yes_down"}:
        return "YES_DOWN"
    if stance in {"supports", "positive", "yes_up"}:
        return "YES_UP"
    if any(term in text for term in NEGATIVE_TERMS):
        return "YES_DOWN"
    if any(term in text for term in POSITIVE_TERMS):
        return "YES_UP"
    return "NEUTRAL_OR_UNCLEAR"


def estimate_event_magnitude(event: dict[str, Any], market: dict[str, Any]) -> float:
    corroboration = _safe_float(event.get("corroboration_score"), 0.25) or 0.25
    relevance = _safe_float(event.get("relevance_score"), None)
    if relevance is None:
        source = (event.get("sources") or [{}])[0] if isinstance(event.get("sources"), list) else event
        relevance = score_source_relevance(source if isinstance(source, dict) else {}, market)["relevance_score"]
    high_terms = any(term in (_source_text(event).lower() + str(event.get("claim_summary") or "").lower()) for term in ["official", "confirmed", "injury", "withdraw", "court filing", "regulator", "wins", "loss"])
    raw = 0.8 + 2.2 * corroboration + 1.8 * float(relevance or 0.25) + (0.8 if high_terms else 0.0)
    return round(max(0.0, min(raw, float(getattr(settings, "ai_news_odds_max_cluster_adjustment_pp", 3.0)))), 3)


def extract_market_relevant_events(evidence_packet: dict[str, Any]) -> list[dict[str, Any]]:
    market = evidence_packet.get("market") if isinstance(evidence_packet.get("market"), dict) else evidence_packet
    sources = evidence_packet.get("sources") or evidence_packet.get("source_records") or evidence_packet.get("evidence_sources") or []
    if not isinstance(sources, list):
        sources = []
    clusters = cluster_evidence_claims([source for source in sources if isinstance(source, dict)])
    events: list[dict[str, Any]] = []
    for cluster in clusters:
        source = cluster.get("sources", [{}])[0] if cluster.get("sources") else {}
        relevance = score_source_relevance(source if isinstance(source, dict) else {}, market if isinstance(market, dict) else {})
        direction = estimate_event_direction(cluster, market if isinstance(market, dict) else {})
        magnitude = estimate_event_magnitude({**cluster, "relevance_score": relevance["relevance_score"]}, market if isinstance(market, dict) else {})
        events.append({
            "event_id": "event_" + cluster["claim_cluster_id"].split("_", 1)[-1],
            "event_summary": cluster.get("claim_summary"),
            "claim_cluster_id": cluster.get("claim_cluster_id"),
            "direction": direction,
            "magnitude_pp": magnitude,
            "relevance_score": relevance.get("relevance_score"),
            "matched_terms": relevance.get("matched_terms", []),
            "corroboration_score": cluster.get("corroboration_score"),
            "independent_source_count": cluster.get("independent_source_count"),
            "contradiction_detected": cluster.get("contradiction_detected"),
            "source_count": cluster.get("source_count"),
        })
    return events


def _adjustment_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    incoming = config or {}
    mode = str(incoming.get("ai_odds_adjustment_mode", getattr(settings, "ai_odds_adjustment_mode", "conservative")) or "conservative").strip().lower()
    if mode not in {"off", "conservative", "balanced", "aggressive", "custom"}:
        mode = "conservative"
    default_cap = float(incoming.get("default_max_adjustment_pct", getattr(settings, "ai_default_max_adjustment_pct", 2.5)))
    balanced_cap = float(incoming.get("balanced_max_adjustment_pct", getattr(settings, "ai_balanced_max_adjustment_pct", 7.5)))
    aggressive_cap = float(incoming.get("aggressive_max_adjustment_pct", getattr(settings, "ai_aggressive_max_adjustment_pct", 15.0)))
    legacy_custom_cap = float(incoming.get("max_adjustment_pp", getattr(settings, "ai_news_odds_max_adjustment_pp", default_cap)))
    mode_cap = {
        "off": 0.0,
        "conservative": default_cap,
        "balanced": balanced_cap,
        "aggressive": aggressive_cap,
        "custom": legacy_custom_cap,
    }[mode]
    return {
        "ai_odds_adjustment_enabled": _safe_bool(incoming.get("ai_odds_adjustment_enabled"), bool(getattr(settings, "ai_odds_adjustment_enabled", True))),
        "ai_odds_adjustment_mode": mode,
        "max_adjustment_pp": mode_cap,
        "default_max_adjustment_pct": default_cap,
        "balanced_max_adjustment_pct": balanced_cap,
        "aggressive_max_adjustment_pct": aggressive_cap,
        "absolute_hard_cap_pct": float(incoming.get("absolute_hard_cap_pct", getattr(settings, "ai_absolute_hard_cap_pct", 25.0))),
        "require_extra_evidence_above_pct": float(incoming.get("require_extra_evidence_above_pct", getattr(settings, "ai_require_extra_evidence_above_pct", 5.0))),
        "require_operator_confirm_above_pct": float(incoming.get("require_operator_confirm_above_pct", getattr(settings, "ai_require_operator_confirm_above_pct", 10.0))),
        "allow_cap_exceed_with_evidence": _safe_bool(incoming.get("allow_cap_exceed_with_evidence"), bool(getattr(settings, "ai_allow_cap_exceed_with_evidence", False))),
        "max_cluster_adjustment_pp": float(incoming.get("max_cluster_adjustment_pp", getattr(settings, "ai_news_odds_max_cluster_adjustment_pp", 3.0))),
        "max_low_confidence_adjustment_pp": float(incoming.get("max_low_confidence_adjustment_pp", getattr(settings, "ai_news_odds_max_low_confidence_adjustment_pp", 1.0))),
        "max_no_primary_source_adjustment_pp": float(incoming.get("max_no_primary_source_adjustment_pp", getattr(settings, "ai_news_odds_max_no_primary_source_adjustment_pp", 4.0))),
        "min_probability": float(incoming.get("min_probability", 0.01)),
        "max_probability": float(incoming.get("max_probability", 0.99)),
        "duplicate_penalty": _safe_bool(incoming.get("duplicate_penalty"), bool(getattr(settings, "ai_news_odds_duplicate_penalty", True))),
        "contradiction_penalty": _safe_bool(incoming.get("contradiction_penalty"), bool(getattr(settings, "ai_news_odds_contradiction_penalty", True))),
    }


def _evidence_quality_summary(events: list[dict[str, Any]], source_scores: dict[str, Any] | list[dict[str, Any]] | None) -> dict[str, Any]:
    independent_count = 0
    high_cred_count = 0
    contradiction_count = 0
    source_count = 0
    relevance_scores: list[float] = []
    recency_scores: list[float] = []
    credibility_scores: list[float] = []
    source_types: set[str] = set()
    has_primary = False
    if isinstance(source_scores, list):
        source_count = len(source_scores)
        domains = set()
        for score in source_scores:
            st = str(score.get("source_type") or "")
            source_types.add(st)
            domains.add(str(score.get("canonical_domain") or score.get("domain") or score.get("url") or ""))
            cred = _safe_float(score.get("credibility_score"), 0.0) or 0.0
            rel = _safe_float(score.get("relevance_score"), None)
            recency = _safe_float(score.get("recency_score"), None)
            credibility_scores.append(cred)
            if rel is not None:
                relevance_scores.append(rel)
            if recency is not None:
                recency_scores.append(recency)
            high_cred_count += 1 if cred >= 0.80 else 0
            has_primary = has_primary or st in {"primary", "primary_official", "government", "regulator", "league_or_organization"}
        independent_count = len({item for item in domains if item})
    elif isinstance(source_scores, dict):
        source_count = int(source_scores.get("source_count") or 0)
        independent_count = int(source_scores.get("independent_source_count") or 0)
        high_cred_count = int(source_scores.get("high_credibility_source_count") or 0)
        contradiction_count = int(source_scores.get("contradiction_count") or 0)
        has_primary = bool(source_scores.get("has_primary_source"))
    for event in events:
        contradiction_count += 1 if event.get("contradiction_detected") else 0
        rel = _safe_float(event.get("relevance_score"), None)
        if rel is not None:
            relevance_scores.append(rel)
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.25
    avg_recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0.35
    avg_credibility = sum(credibility_scores) / len(credibility_scores) if credibility_scores else (0.85 if high_cred_count else 0.35)
    agreement_score = max(0.0, min(1.0, (independent_count / 4.0) * 0.55 + (high_cred_count / 3.0) * 0.30 + (0.15 if has_primary else 0.0)))
    contradiction_penalty = min(0.65, contradiction_count * 0.22)
    evidence_score = max(0.0, min(1.0, avg_relevance * 0.25 + avg_recency * 0.15 + avg_credibility * 0.25 + agreement_score * 0.35 - contradiction_penalty))
    weak_reasons: list[str] = []
    if independent_count <= 1:
        weak_reasons.append("single_or_no_independent_source")
    if not has_primary:
        weak_reasons.append("no_primary_or_high_authority_source")
    if avg_recency < 0.5:
        weak_reasons.append("stale_or_missing_recency")
    if avg_relevance < 0.35:
        weak_reasons.append("low_market_relevance")
    if contradiction_count:
        weak_reasons.append("contradictory_evidence")
    return {
        "source_count": source_count,
        "independent_source_count": independent_count,
        "high_credibility_source_count": high_cred_count,
        "has_primary_source": has_primary,
        "contradiction_count": contradiction_count,
        "source_trust_tiers": sorted(source_types),
        "average_relevance_score": round(avg_relevance, 3),
        "average_recency_score": round(avg_recency, 3),
        "average_credibility_score": round(avg_credibility, 3),
        "agreement_score": round(agreement_score, 3),
        "contradiction_penalty": round(contradiction_penalty, 3),
        "evidence_score": round(evidence_score, 3),
        "weak_evidence_reasons": weak_reasons,
    }


def _market_adjustment_risk(market_context: dict[str, Any] | None) -> dict[str, Any]:
    market = market_context or {}
    warnings: list[str] = []
    confidence_multiplier = 1.0
    liquidity = _safe_float(market.get("liquidity") or market.get("liquidity_num"), None)
    min_liquidity = _safe_float(getattr(settings, "paper_min_liquidity", 1000), 1000.0) or 1000.0
    if liquidity is not None and liquidity < min_liquidity:
        confidence_multiplier *= 0.80
        warnings.append("Liquidity is thin relative to configured paper-trading minimum; confidence degraded.")
    prices = extract_market_prices(market) if market else {}
    if prices.get("sum_yes_no") is not None and abs(float(prices["sum_yes_no"]) - 1.0) > 0.03:
        confidence_multiplier *= 0.85
        warnings.append("YES/NO sum suggests wide spread or imperfect price inputs; confidence degraded.")
    resolution_text = " ".join(str(market.get(key) or "") for key in ["resolution_source", "resolutionSource", "rules", "description", "resolution_rules"])
    if market and not resolution_text.strip():
        confidence_multiplier *= 0.90
        warnings.append("Resolution criteria/source not available in market row; confidence degraded.")
    if any(term in resolution_text.lower() for term in ["ambiguous", "subject to", "conditional", "if needed", "runoff"]):
        confidence_multiplier *= 0.85
        warnings.append("Resolution criteria appears conditional or ambiguous; confidence degraded.")
    return {"confidence_multiplier": round(confidence_multiplier, 3), "warnings": warnings}


def _cap_reason(raw_pct: float, weighted_pct: float, final_pct: float, cfg: dict[str, Any], evidence: dict[str, Any]) -> str:
    if not cfg["ai_odds_adjustment_enabled"] or cfg["ai_odds_adjustment_mode"] == "off":
        return "AI odds adjustment disabled by configuration."
    if abs(final_pct) < abs(weighted_pct):
        return "Risk controls reduced the evidence-weighted adjustment."
    if abs(final_pct) > 2.5:
        return "Adjustment exceeds the legacy 2.5 pp guard because configured mode and evidence quality allow a larger reviewed move."
    if abs(raw_pct) > 2.5 and abs(final_pct) <= 2.5:
        return "Raw evidence exceeded 2.5 pp, but conservative caps kept the final adjustment near the legacy limit."
    if evidence.get("weak_evidence_reasons"):
        return "Weak evidence guardrails limited the adjustment."
    return "Adjustment stayed within configured conservative bounds."


def risk_control_adjustment(
    raw_adjustment_pct: float,
    evidence_weighted_adjustment_pct: float,
    evidence_summary: dict[str, Any],
    cfg: dict[str, Any],
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    clamps: list[str] = []
    if not cfg["ai_odds_adjustment_enabled"] or cfg["ai_odds_adjustment_mode"] == "off":
        final = 0.0
        clamps.append("ai_adjustment_disabled")
    else:
        final = evidence_weighted_adjustment_pct
    market_risk = _market_adjustment_risk(market_context)
    if market_risk["warnings"]:
        warnings.extend(market_risk["warnings"])
        final *= float(market_risk["confidence_multiplier"])
    configured_cap = max(0.0, float(cfg["max_adjustment_pp"]))
    hard_cap = max(0.0, float(cfg["absolute_hard_cap_pct"]))
    effective_cap = min(configured_cap, hard_cap)
    weak_reasons = list(evidence_summary.get("weak_evidence_reasons") or [])
    if "single_or_no_independent_source" in weak_reasons:
        effective_cap = min(effective_cap, float(cfg["max_low_confidence_adjustment_pp"]))
        clamps.append("single_source_low_confidence_cap")
    if "no_primary_or_high_authority_source" in weak_reasons:
        effective_cap = min(effective_cap, float(cfg["max_no_primary_source_adjustment_pp"]))
        clamps.append("no_primary_source_cap")
    if "contradictory_evidence" in weak_reasons:
        effective_cap = min(effective_cap, float(cfg["max_low_confidence_adjustment_pp"]))
        clamps.append("contradiction_cap")
    extra_threshold = float(cfg["require_extra_evidence_above_pct"])
    if abs(final) > extra_threshold:
        extra_ok = evidence_summary.get("independent_source_count", 0) >= 3 and evidence_summary.get("high_credibility_source_count", 0) >= 1 and not evidence_summary.get("contradiction_count", 0)
        if not extra_ok:
            effective_cap = min(effective_cap, extra_threshold)
            clamps.append("extra_evidence_required_cap")
            warnings.append(f"Adjustment above {extra_threshold:.1f} pp requires stronger independent evidence.")
        elif cfg["allow_cap_exceed_with_evidence"] and cfg["ai_odds_adjustment_mode"] == "conservative":
            effective_cap = min(max(effective_cap, float(cfg["balanced_max_adjustment_pct"])), hard_cap)
            warnings.append("Configured evidence override allowed conservative cap expansion up to the balanced cap.")
    if abs(final) > effective_cap:
        final = math.copysign(effective_cap, final)
        clamps.append("configured_cap_applied")
    if abs(final) > hard_cap:
        final = math.copysign(hard_cap, final)
        clamps.append("absolute_hard_cap_applied")
    operator_threshold = float(cfg["require_operator_confirm_above_pct"])
    operator_confirmation_required = abs(final) >= operator_threshold and operator_threshold > 0
    if operator_confirmation_required:
        warnings.append(f"Operator confirmation required because final adjustment is at least {operator_threshold:.1f} pp.")
    old_cap_warning = abs(final) > 2.5
    if old_cap_warning:
        warnings.append("Final adjustment exceeds the legacy 2.5 pp cap; review evidence rationale and cap decision before use.")
    return {
        "raw_ai_adjustment_pct": round(raw_adjustment_pct, 3),
        "evidence_weighted_adjustment_pct": round(evidence_weighted_adjustment_pct, 3),
        "final_adjustment_pct": round(final, 3),
        "configured_cap_pct": round(configured_cap, 3),
        "effective_cap_pct": round(effective_cap, 3),
        "absolute_hard_cap_pct": round(hard_cap, 3),
        "ai_odds_adjustment_mode": cfg["ai_odds_adjustment_mode"],
        "operator_confirmation_required": operator_confirmation_required,
        "old_2_5_cap_exceeded": old_cap_warning,
        "cap_clamps": sorted(set(clamps)),
        "cap_warnings": warnings,
        "cap_decision": _cap_reason(raw_adjustment_pct, evidence_weighted_adjustment_pct, final, cfg, evidence_summary),
        "evidence_summary": evidence_summary,
        "market_risk": market_risk,
    }


def calculate_news_adjustment(
    base_fair_yes: Any,
    events: list[dict[str, Any]],
    source_scores: dict[str, Any] | list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = normalize_probability(base_fair_yes)
    cfg = _adjustment_config(config)
    if base is None:
        return safety_flags({
            "ok": False,
            "reason": "base_fair_yes_unavailable",
            "adjustment_pp": 0.0,
            "raw_ai_adjustment_pct": 0.0,
            "evidence_weighted_adjustment_pct": 0.0,
            "final_adjustment_pct": 0.0,
            "confidence": "INSUFFICIENT_DATA",
            "uncertainty": "HIGH",
            "warnings": ["Base fair YES probability is unavailable; no anchored fair-probability adjustment was produced."],
            "review_only": True,
            "order_submitted": False,
            "order_cancelled": False,
            "live_trading_armed": False,
        })
    raw_total = 0.0
    weighted_total = 0.0
    warnings: list[str] = []
    has_primary = False
    contradiction_count = 0
    independent_count = 0
    high_cred_count = 0
    for event in events:
        direction = str(event.get("direction") or "NEUTRAL_OR_UNCLEAR")
        if direction == "NEUTRAL_OR_UNCLEAR":
            continue
        sign = 1.0 if direction == "YES_UP" else -1.0
        raw_mag = min(abs(_safe_float(event.get("magnitude_pp"), 0.0) or 0.0), max(cfg["absolute_hard_cap_pct"] * 2.0, cfg["max_cluster_adjustment_pp"]))
        mag = min(raw_mag, cfg["max_cluster_adjustment_pp"])
        corr = max(0.0, min(_safe_float(event.get("corroboration_score"), 0.25) or 0.25, 1.0))
        rel = max(0.0, min(_safe_float(event.get("relevance_score"), 0.25) or 0.25, 1.0))
        raw_total += sign * raw_mag
        if event.get("contradiction_detected") and cfg["contradiction_penalty"]:
            mag *= 0.45
            contradiction_count += 1
        weighted_total += sign * mag * (0.4 + 0.35 * corr + 0.25 * rel)
        independent_count += int(event.get("independent_source_count") or 0)
    if isinstance(source_scores, list):
        for score in source_scores:
            st = str(score.get("source_type") or "")
            cred = _safe_float(score.get("credibility_score"), 0.0) or 0.0
            has_primary = has_primary or st in {"primary", "primary_official", "government", "regulator", "league_or_organization"}
            high_cred_count += 1 if cred >= 0.80 else 0
    elif isinstance(source_scores, dict):
        has_primary = bool(source_scores.get("has_primary_source"))
        high_cred_count = int(source_scores.get("high_credibility_source_count") or 0)
        independent_count = int(source_scores.get("independent_source_count") or independent_count)
        contradiction_count = int(source_scores.get("contradiction_count") or contradiction_count)
    evidence_summary = _evidence_quality_summary(events, source_scores)
    evidence_summary.update({
        "has_primary_source": has_primary or bool(evidence_summary.get("has_primary_source")),
        "high_credibility_source_count": max(high_cred_count, int(evidence_summary.get("high_credibility_source_count") or 0)),
        "independent_source_count": max(independent_count, int(evidence_summary.get("independent_source_count") or 0)),
        "contradiction_count": max(contradiction_count, int(evidence_summary.get("contradiction_count") or 0)),
    })
    control = risk_control_adjustment(raw_total, weighted_total, evidence_summary, cfg, market_context=market_context)
    total = control["final_adjustment_pct"]
    warnings.extend(control.get("cap_warnings") or [])
    confidence = "LOW"
    uncertainty = "HIGH"
    if independent_count >= int(getattr(settings, "ai_news_odds_min_independent_sources_for_medium", 2)) and high_cred_count >= 1 and not contradiction_count:
        confidence = "HIGH" if high_cred_count >= int(getattr(settings, "ai_news_odds_min_high_cred_sources_for_high", 1)) and independent_count >= 3 else "MEDIUM"
        uncertainty = "MEDIUM" if confidence == "MEDIUM" else "LOW_MEDIUM"
    elif independent_count >= 2 and not contradiction_count:
        confidence = "MEDIUM"
        uncertainty = "MEDIUM_HIGH"
    adjusted = apply_probability_adjustment(base, total, {"min_probability": cfg["min_probability"], "max_probability": cfg["max_probability"]})
    return safety_flags({
        "ok": True,
        "base_fair_yes": base,
        "base_fair_no": round(1.0 - base, 6),
        "adjustment_pp": round(total, 3),
        "raw_ai_adjustment_pct": control["raw_ai_adjustment_pct"],
        "evidence_weighted_adjustment_pct": control["evidence_weighted_adjustment_pct"],
        "final_adjustment_pct": control["final_adjustment_pct"],
        "cap_decision": control["cap_decision"],
        "cap_mode": control["ai_odds_adjustment_mode"],
        "configured_cap_pct": control["configured_cap_pct"],
        "effective_cap_pct": control["effective_cap_pct"],
        "absolute_hard_cap_pct": control["absolute_hard_cap_pct"],
        "old_2_5_cap_exceeded": control["old_2_5_cap_exceeded"],
        "operator_confirmation_required": control["operator_confirmation_required"],
        "cap_clamps": control["cap_clamps"],
        "evidence_quality": control["evidence_summary"],
        "market_risk": control["market_risk"],
        "direction": "YES_UP" if total > 0 else "YES_DOWN" if total < 0 else "NEUTRAL_OR_UNCLEAR",
        "adjusted_fair_yes": adjusted["adjusted_probability"],
        "adjusted_fair_no": round(1.0 - adjusted["adjusted_probability"], 6),
        "confidence": confidence,
        "uncertainty": uncertainty,
        "warnings": warnings,
        "independent_source_count": independent_count,
        "high_credibility_source_count": high_cred_count,
        "contradiction_count": contradiction_count,
        "review_only": True,
        "not_financial_advice": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
    })


def apply_probability_adjustment(base_fair_yes: Any, adjustment_pp: Any, bounds: dict[str, Any] | None = None) -> dict[str, Any]:
    base = normalize_probability(base_fair_yes)
    if base is None:
        return {"ok": False, "reason": "base_probability_unavailable", "adjusted_probability": None}
    pp = _safe_float(adjustment_pp, 0.0) or 0.0
    bounds = bounds or {}
    min_p = float(bounds.get("min_probability", 0.01))
    max_p = float(bounds.get("max_probability", 0.99))
    base = min(max(base, min_p), max_p)
    log_odds = math.log(base / (1.0 - base))
    # Interpret percentage-point evidence as a small log-odds shift. This keeps changes bounded and auditable.
    shifted = log_odds + (pp / 100.0) * 4.0
    adjusted = 1.0 / (1.0 + math.exp(-shifted))
    adjusted = min(max(adjusted, min_p), max_p)
    return {"ok": True, "base_probability": round(base, 6), "adjustment_pp": round(pp, 3), "adjusted_probability": round(adjusted, 6), "method": "bounded_log_odds_shift"}


def _base_fair_from_market(market: dict[str, Any], base_recommendation: dict[str, Any] | None = None) -> float | None:
    if base_recommendation and base_recommendation.get("model_fair_yes") is not None:
        return normalize_probability(base_recommendation.get("model_fair_yes"))
    edge = market.get("market_edge_recommendation") if isinstance(market.get("market_edge_recommendation"), dict) else {}
    if edge and edge.get("model_fair_yes") is not None:
        return normalize_probability(edge.get("model_fair_yes"))
    for key in ["model_fair_yes", "model_probability", "probability"]:
        value = normalize_probability(market.get(key))
        if value is not None:
            return value
    pm = market.get("probability_model") if isinstance(market.get("probability_model"), dict) else {}
    return normalize_probability(pm.get("model_probability") or pm.get("probability") or pm.get("fair_probability"))


def build_news_odds_adjustment_packet(market: dict[str, Any], evidence: list[dict[str, Any]] | dict[str, Any], base_recommendation: dict[str, Any] | None = None) -> dict[str, Any]:
    sources = evidence.get("sources", []) if isinstance(evidence, dict) else evidence
    if not isinstance(sources, list):
        sources = []
    sources = [redact_data(source) for source in sources if isinstance(source, dict)]
    secret_check = secret_scan({"market": market, "sources": sources})
    if secret_check.get("ok") is not True:
        return safety_flags({"ok": False, "error": "secret_like_content_rejected", "secret_scan": secret_check, "review_only": True})
    base_recommendation = base_recommendation or build_market_recommendation_row(market)
    base_fair = _base_fair_from_market(market, base_recommendation)
    dedup = detect_duplicate_or_syndicated_sources(sources)
    annotated_sources = dedup.get("annotated_sources", [])
    source_scores = []
    for source in annotated_sources:
        cred = score_source_credibility(source)
        recency = score_source_recency(source.get("published_at") or source.get("date"), market.get("end_date") or market.get("close_time"))
        relevance = score_source_relevance(source, market)
        source_scores.append({**source, **cred, **recency, **relevance, "source_id": source.get("source_id") or _record_id("source")})
    clusters = cluster_evidence_claims(source_scores)
    events = extract_market_relevant_events({"market": market, "sources": source_scores})
    score_summary = {
        "source_count": len(source_scores),
        "independent_source_count": dedup.get("independent_source_count", 0),
        "duplicate_source_count": dedup.get("duplicate_source_count", 0),
        "high_credibility_source_count": len([score for score in source_scores if _safe_float(score.get("credibility_score"), 0.0) and float(score.get("credibility_score")) >= 0.80]),
        "has_primary_source": any(score.get("source_type") in {"primary", "government", "regulator", "league_or_organization"} for score in source_scores),
        "contradiction_count": len([cluster for cluster in clusters if cluster.get("contradiction_detected")]),
    }
    adjustment = calculate_news_adjustment(base_fair, events, score_summary, market_context=market)
    price = extract_market_prices(market)
    adjusted_edge = calculate_yes_no_edges(price.get("market_yes_price"), price.get("market_no_price"), adjustment.get("adjusted_fair_yes")) if adjustment.get("adjusted_fair_yes") is not None else {}
    base_edge = calculate_yes_no_edges(price.get("market_yes_price"), price.get("market_no_price"), base_fair) if base_fair is not None else {}
    adjustment_id = _record_id("news_adjustment")
    packet = safety_flags({
        "version": APP_VERSION,
        "adjustment_id": adjustment_id,
        "market_id": redact_text(market.get("id") or market.get("market_id") or market.get("slug") or market.get("question") or ""),
        "market_title": redact_text(market.get("question") or market.get("title") or market.get("market_title") or "Untitled market"),
        "created_at": _now(),
        "updated_at": _now(),
        "provider": "manual_or_openai_web_search_when_enabled",
        "query_plan": build_market_search_plan(market),
        "source_records": source_scores,
        "source_weights": source_weight_table().get("weights"),
        "source_count": len(source_scores),
        "independent_source_count": dedup.get("independent_source_count", 0),
        "high_credibility_source_count": score_summary["high_credibility_source_count"],
        "duplicate_source_count": dedup.get("duplicate_source_count", 0),
        "duplicate_groups": dedup.get("duplicate_groups", []),
        "claim_clusters": clusters,
        "contradictions": [cluster for cluster in clusters if cluster.get("contradiction_detected")],
        "events": events,
        "base_fair_yes": base_fair,
        "base_fair_no": None if base_fair is None else round(1.0 - base_fair, 6),
        "adjusted_fair_yes": adjustment.get("adjusted_fair_yes"),
        "adjusted_fair_no": adjustment.get("adjusted_fair_no"),
        "adjustment_pp": adjustment.get("adjustment_pp", 0.0),
        "raw_ai_adjustment_pct": adjustment.get("raw_ai_adjustment_pct", 0.0),
        "evidence_weighted_adjustment_pct": adjustment.get("evidence_weighted_adjustment_pct", 0.0),
        "final_adjustment_pct": adjustment.get("final_adjustment_pct", adjustment.get("adjustment_pp", 0.0)),
        "cap_decision": adjustment.get("cap_decision", ""),
        "cap_mode": adjustment.get("cap_mode", "conservative"),
        "configured_cap_pct": adjustment.get("configured_cap_pct"),
        "effective_cap_pct": adjustment.get("effective_cap_pct"),
        "absolute_hard_cap_pct": adjustment.get("absolute_hard_cap_pct"),
        "old_2_5_cap_exceeded": adjustment.get("old_2_5_cap_exceeded", False),
        "operator_confirmation_required": adjustment.get("operator_confirmation_required", False),
        "cap_clamps": adjustment.get("cap_clamps", []),
        "evidence_quality": adjustment.get("evidence_quality", {}),
        "market_risk": adjustment.get("market_risk", {}),
        "direction": adjustment.get("direction", "NEUTRAL_OR_UNCLEAR"),
        "confidence": adjustment.get("confidence", "LOW"),
        "uncertainty": adjustment.get("uncertainty", "HIGH"),
        "warnings": list(adjustment.get("warnings") or []) + (["Web search unavailable; add manual evidence or enable a provider."] if not getattr(settings, "ai_news_odds_web_search_enabled", False) else []),
        "top_evidence": source_scores[:5],
        "base_edge": base_edge,
        "adjusted_edge": adjusted_edge,
        "base_recommendation": base_recommendation,
        "operator_action": "draft_generated",
        "accepted_to_review_context": False,
        "rejected": False,
        "archived": False,
        "audit_hash": _hash({"market": market.get("id") or market.get("question"), "sources": source_scores, "adjustment": adjustment, "cap_decision": adjustment.get("cap_decision")}),
        "review_only": True,
        "not_financial_advice": True,
        "does_not_place_orders": True,
        "does_not_cancel_orders": True,
        "does_not_arm_live": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
        "source_weighting_does_not_imply_truth": True,
        "corroboration_does_not_imply_certainty": True,
    })
    return packet


def explain_news_odds_adjustment(packet: dict[str, Any]) -> str:
    base = packet.get("base_fair_yes")
    adjusted = packet.get("adjusted_fair_yes")
    adjustment_pp = packet.get("adjustment_pp")
    raw = packet.get("raw_ai_adjustment_pct", adjustment_pp)
    weighted = packet.get("evidence_weighted_adjustment_pct", adjustment_pp)
    confidence = packet.get("confidence") or "LOW"
    sources = packet.get("source_count", 0)
    independent = packet.get("independent_source_count", 0)
    duplicate = packet.get("duplicate_source_count", 0)
    if base is None or adjusted is None:
        return "Base fair probability or evidence is insufficient, so no anchored news-adjusted fair odds were produced. Review-only; not financial advice."
    return (
        f"Draft news adjustment moves fair YES from {float(base) * 100:.1f}% to {float(adjusted) * 100:.1f}% "
        f"(raw AI {float(raw or 0):+.1f} pp, evidence-weighted {float(weighted or 0):+.1f} pp, final risk-controlled {float(adjustment_pp or 0):+.1f} pp). "
        f"Confidence {confidence}; {independent} independent source(s), {sources} total source(s), {duplicate} duplicate/syndicated source(s). "
        f"Cap decision: {packet.get('cap_decision') or 'not recorded'} "
        f"Operator confirmation required: {bool(packet.get('operator_confirmation_required'))}. "
        "This is review-only, not financial advice, not a trade approval, and it does not place or cancel orders."
    )


def validate_news_adjustment_safety(packet: dict[str, Any]) -> dict[str, Any]:
    failed = []
    for key in ["review_only", "not_financial_advice", "does_not_place_orders", "does_not_cancel_orders", "does_not_arm_live", "no_live_mutation"]:
        if packet.get(key) is not True:
            failed.append(key)
    for key in ["order_submitted", "order_cancelled", "trade_approved", "live_trading_armed"]:
        if packet.get(key) is not False:
            failed.append(key)
    return safety_flags({"ok": not failed, "failed_flags": failed, "review_only": True, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False})


def persist_adjustment(packet: dict[str, Any], *, write_sources: bool = True) -> dict[str, Any]:
    safe = redact_data(packet)
    _write_jsonl(ADJUSTMENTS_PATH, safe)
    if write_sources:
        for source in safe.get("source_records", [])[:500]:
            if isinstance(source, dict):
                _write_jsonl(SOURCES_PATH, {**source, "adjustment_id": safe.get("adjustment_id"), "review_only": True})
    _write_jsonl(AUDIT_PATH, {"audit_id": _record_id("news_odds_audit"), "action": "adjustment_persisted", "adjustment_id": safe.get("adjustment_id"), "created_at": _now(), "audit_hash": safe.get("audit_hash"), "review_only": True, "order_submitted": False, "order_cancelled": False})
    return safety_flags({"ok": True, "adjustment": safe, "runtime_records_excluded_from_release_zip": True, "review_only": True, "order_submitted": False, "order_cancelled": False})


def list_adjustments(limit: int = 250, include_archived: bool = False) -> dict[str, Any]:
    rows = list(reversed(_read_jsonl(ADJUSTMENTS_PATH)))
    if not include_archived:
        rows = [row for row in rows if row.get("archived") is not True]
    capped = rows[: max(1, min(int(limit or 250), 5000))]
    return safety_flags({"version": APP_VERSION, "count": len(capped), "total_count": len(rows), "items": capped, "review_only": True, "order_submitted": False, "order_cancelled": False, "runtime_records_excluded_from_release_zip": True})


def get_adjustment(adjustment_id: str) -> dict[str, Any]:
    safe_id = redact_text(adjustment_id)
    for row in reversed(_read_jsonl(ADJUSTMENTS_PATH)):
        if row.get("adjustment_id") == safe_id:
            return safety_flags({"ok": True, "adjustment": row, "review_only": True, "order_submitted": False, "order_cancelled": False})
    return safety_flags({"ok": False, "error": "adjustment_not_found", "adjustment_id": safe_id, "review_only": True, "order_submitted": False, "order_cancelled": False})


def _mutate_adjustment(adjustment_id: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    found = get_adjustment(adjustment_id)
    if not found.get("ok"):
        # Create a safe tombstone response rather than mutating live state.
        return found
    packet = dict(found["adjustment"])
    now = _now()
    packet["updated_at"] = now
    packet["operator_action"] = action
    packet["accepted_to_review_context"] = action == "accepted_to_review_context"
    packet["rejected"] = action == "rejected"
    packet["archived"] = action == "archived"
    packet["operator_note"] = redact_text((payload or {}).get("operator_note") or (payload or {}).get("note") or "")[:1000]
    packet.update({"review_only": True, "not_financial_advice": True, "does_not_place_orders": True, "does_not_cancel_orders": True, "does_not_arm_live": True, "order_submitted": False, "order_cancelled": False, "trade_approved": False, "live_trading_armed": False, "no_live_mutation": True})
    persist_adjustment(packet, write_sources=False)
    return safety_flags({"ok": True, "adjustment": packet, "review_only": True, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False})


def accept_adjustment_to_review_context(adjustment_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _mutate_adjustment(adjustment_id, "accepted_to_review_context", payload)


def reject_adjustment(adjustment_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _mutate_adjustment(adjustment_id, "rejected", payload)


def archive_adjustment(adjustment_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _mutate_adjustment(adjustment_id, "archived", payload)


def news_odds_settings_summary() -> dict[str, Any]:
    cfg = _adjustment_config()
    return safety_flags({
        "version": APP_VERSION,
        "ai_news_odds_enabled": bool(getattr(settings, "ai_news_odds_enabled", True)),
        "ai_news_odds_web_search_enabled": bool(getattr(settings, "ai_news_odds_web_search_enabled", False)),
        "ai_news_odds_manual_evidence_enabled": bool(getattr(settings, "ai_news_odds_manual_evidence_enabled", True)),
        "ai_news_odds_local_llm_enabled": bool(getattr(settings, "ai_news_odds_local_llm_enabled", False)),
        "ai_news_odds_review_only": bool(getattr(settings, "ai_news_odds_review_only", True)),
        "ai_news_odds_require_human_accept": bool(getattr(settings, "ai_news_odds_require_human_accept", True)),
        "ai_news_odds_can_place_orders": bool(getattr(settings, "ai_news_odds_can_place_orders", False)),
        "ai_news_odds_can_cancel_orders": bool(getattr(settings, "ai_news_odds_can_cancel_orders", False)),
        "ai_news_odds_can_arm_live": bool(getattr(settings, "ai_news_odds_can_arm_live", False)),
        "ai_odds_adjustment_enabled": bool(getattr(settings, "ai_odds_adjustment_enabled", True)),
        "ai_odds_adjustment_mode": getattr(settings, "ai_odds_adjustment_mode", "conservative"),
        "ai_default_max_adjustment_pct": float(getattr(settings, "ai_default_max_adjustment_pct", 2.5)),
        "ai_balanced_max_adjustment_pct": float(getattr(settings, "ai_balanced_max_adjustment_pct", 7.5)),
        "ai_aggressive_max_adjustment_pct": float(getattr(settings, "ai_aggressive_max_adjustment_pct", 15.0)),
        "ai_absolute_hard_cap_pct": float(getattr(settings, "ai_absolute_hard_cap_pct", 25.0)),
        "ai_require_extra_evidence_above_pct": float(getattr(settings, "ai_require_extra_evidence_above_pct", 5.0)),
        "ai_require_operator_confirm_above_pct": float(getattr(settings, "ai_require_operator_confirm_above_pct", 10.0)),
        "ai_allow_cap_exceed_with_evidence": bool(getattr(settings, "ai_allow_cap_exceed_with_evidence", False)),
        "max_adjustment_pp": float(cfg["max_adjustment_pp"]),
        "legacy_custom_max_adjustment_pp": float(getattr(settings, "ai_news_odds_max_adjustment_pp", 8.0)),
        "max_cluster_adjustment_pp": float(getattr(settings, "ai_news_odds_max_cluster_adjustment_pp", 3.0)),
        "max_low_confidence_adjustment_pp": float(getattr(settings, "ai_news_odds_max_low_confidence_adjustment_pp", 1.0)),
        "max_no_primary_source_adjustment_pp": float(getattr(settings, "ai_news_odds_max_no_primary_source_adjustment_pp", 4.0)),
        "openai_web_search_enabled": bool(getattr(settings, "openai_enable_web_search", False)),
        "openai_api_enabled": bool(getattr(settings, "openai_enable_api", False)),
        "openai_api_key_configured": bool(getattr(settings, "openai_api_key", None)),
        "openai_api_key_value_returned": False,
        "local_llm_enable": bool(getattr(settings, "local_llm_enable", False)),
        "local_llm_edge_can_search_web": bool(getattr(settings, "local_llm_edge_can_search_web", False)),
        "source_weights": source_weight_table().get("weights"),
        "runtime_storage_paths": ["runtime/ai_news_odds", "runtime/ai_news_odds_audit", "runtime/ai_news_sources", "runtime/ai_news_adjustments"],
        "safe_default_posture": bool(getattr(settings, "ai_news_odds_review_only", True)) and not bool(getattr(settings, "ai_news_odds_web_search_enabled", False)) and not bool(getattr(settings, "ai_news_odds_can_place_orders", False)) and not bool(getattr(settings, "ai_news_odds_can_cancel_orders", False)) and not bool(getattr(settings, "ai_news_odds_can_arm_live", False)),
        "review_only_note": REVIEW_ONLY_NOTE,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
    })


def summarize_news_odds() -> dict[str, Any]:
    adjustments = list_adjustments(limit=500, include_archived=True)
    return safety_flags({
        "version": APP_VERSION,
        "title": "AI News Odds Adjustment Engine",
        "settings": news_odds_settings_summary(),
        "adjustment_count": adjustments.get("total_count", 0),
        "active_adjustment_count": len([item for item in adjustments.get("items", []) if item.get("archived") is not True]),
        "api_routes": [
            "/api/v3/ai/news-odds/config",
            "/api/v3/ai/news-odds/market/{market_id_or_slug}/plan",
            "/api/v3/ai/news-odds/market/{market_id_or_slug}/search",
            "/api/v3/ai/news-odds/market/{market_id_or_slug}/manual-evidence",
            "/api/v3/ai/news-odds/market/{market_id_or_slug}/adjust",
            "/api/v3/ai/news-odds/adjustments",
            "/api/v3/ai/news-odds/adjustment/{adjustment_id}",
        ],
        "ui_routes": ["/v3/ai/news-odds", "/v3/ai/news-odds/run", "/v3/ai/news-odds/adjustments", "/v3/ai/news-odds/source-weights", "/v3/markets/{market_id_or_slug}/news-odds"],
        "manual_evidence_mode_available": bool(getattr(settings, "ai_news_odds_manual_evidence_enabled", True)),
        "web_search_unavailable_message": "Web search unavailable; add manual evidence or enable a provider." if not bool(getattr(settings, "ai_news_odds_web_search_enabled", False)) else "Web search can be requested when all OpenAI/provider gates pass.",
        "review_only_note": REVIEW_ONLY_NOTE,
        "source_weighting_does_not_imply_truth": True,
        "corroboration_does_not_imply_certainty": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
    })
