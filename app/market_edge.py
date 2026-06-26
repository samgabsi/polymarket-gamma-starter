from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .config import APP_VERSION, settings

RECOMMENDATION_SAFETY_NOTE = (
    "Review only. Not financial advice. Not trade approval. Edge rows do not place orders, "
    "cancel orders, approve trades, arm live trading, disable read-only mode, or bypass safety gates."
)

FAVORITE_VS_EDGE_EXPLAINER = (
    "Favorite means the highest probability/price within a detected mutually exclusive group. "
    "Edge means the model fair probability differs from the current market-implied price. "
    "A favorite can have no edge if the market price is too high; an underdog can have edge if the market price is too low."
)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            if text.endswith("%"):
                return float(text[:-1]) / 100.0
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_probability(value: Any) -> float | None:
    """Normalize decimal, percentage, or numeric-string probabilities to 0..1.

    Values above 1 and at most 100 are treated as percentages. Values outside the
    usable probability range return None instead of being silently invented.
    """
    parsed = _safe_float(value)
    if parsed is None:
        return None
    if parsed > 1.0 and parsed <= 100.0:
        parsed = parsed / 100.0
    if parsed < 0.0 or parsed > 1.0:
        return None
    return round(parsed, 6)


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return text or "market_family"


def _market_key(market: dict[str, Any]) -> str:
    return str(
        market.get("id")
        or market.get("market_id")
        or market.get("conditionId")
        or market.get("condition_id")
        or market.get("slug")
        or market.get("question")
        or market.get("title")
        or ""
    )


def _market_slug(market: dict[str, Any]) -> str:
    return str(market.get("slug") or market.get("market_slug") or market.get("event_slug") or "")


def _market_title(market: dict[str, Any]) -> str:
    return str(market.get("question") or market.get("title") or market.get("market_title") or "Untitled market")


def _outcome_rows(market: dict[str, Any]) -> list[dict[str, Any]]:
    outcomes = _parse_jsonish(market.get("outcomes") or market.get("outcome") or [])
    prices = _parse_jsonish(market.get("outcomePrices") or market.get("outcome_prices") or market.get("prices") or [])
    if not isinstance(outcomes, list):
        outcomes = []
    if not isinstance(prices, list):
        prices = []

    rows: list[dict[str, Any]] = []
    for index, outcome in enumerate(outcomes):
        if isinstance(outcome, dict):
            name = str(outcome.get("name") or outcome.get("outcome") or outcome.get("label") or outcome.get("title") or index)
            price = outcome.get("price", outcome.get("probability", outcome.get("lastPrice", outcome.get("last_price"))))
        else:
            name = str(outcome)
            price = prices[index] if index < len(prices) else None
        rows.append({"name": name, "price": normalize_probability(price)})
    return rows


def extract_market_prices(market: dict[str, Any]) -> dict[str, Any]:
    rows = _outcome_rows(market)
    yes_price = None
    no_price = None
    source = "unavailable"
    warnings: list[str] = []

    direct_yes = (
        market.get("market_yes_price")
        or market.get("yes_price")
        or market.get("yesPrice")
        or market.get("market_probability")
        or market.get("market_implied_probability")
        or market.get("probability")
    )
    direct_no = market.get("market_no_price") or market.get("no_price") or market.get("noPrice")
    yes_price = normalize_probability(direct_yes)
    no_price = normalize_probability(direct_no)
    if yes_price is not None:
        source = "market probability fields"

    for row in rows:
        label = str(row.get("name") or "").strip().lower()
        price = normalize_probability(row.get("price"))
        if price is None:
            continue
        if label in {"yes", "y"} or label.endswith(" yes"):
            yes_price = price
            source = "YES/NO outcome prices"
        elif label in {"no", "n"} or label.endswith(" no"):
            no_price = price
            source = "YES/NO outcome prices"

    if yes_price is None and rows:
        first_price = normalize_probability(rows[0].get("price"))
        if first_price is not None:
            yes_price = first_price
            source = "first outcome price as YES approximation"
            warnings.append("YES price uses the first listed outcome because no explicit YES label was available.")

    if no_price is None and len(rows) >= 2:
        second_label = str(rows[1].get("name") or "").strip().lower()
        second_price = normalize_probability(rows[1].get("price"))
        if second_price is not None and second_label not in {"yes", "y"}:
            no_price = second_price
            source = source if source != "unavailable" else "second outcome price as NO approximation"

    approximate_no_from_complement = False
    if no_price is None and yes_price is not None:
        no_price = round(1.0 - yes_price, 6)
        approximate_no_from_complement = True
        warnings.append("NO price is approximated as 1 - YES because no explicit NO price was available.")

    sum_price = None
    spread_note = ""
    if yes_price is not None and no_price is not None:
        sum_price = round(yes_price + no_price, 6)
        if abs(sum_price - 1.0) > 0.03:
            spread_note = f"YES + NO sums to {sum_price:.3f}; spread/fees/order-book side may matter."
            warnings.append(spread_note)

    return {
        "market_yes_price": yes_price,
        "market_no_price": no_price,
        "market_implied_source": source,
        "outcome_prices": rows,
        "approximate_no_from_complement": approximate_no_from_complement,
        "sum_yes_no": sum_price,
        "spread_note": spread_note,
        "price_warnings": warnings,
    }


def _extract_model_probability(market: dict[str, Any], model_context: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = model_context or {}
    sources: list[tuple[str, Any, Any]] = [
        ("operator/model context", ctx.get("model_fair_yes") or ctx.get("fair_probability") or ctx.get("model_probability") or ctx.get("draft_probability"), ctx.get("model_fair_no")),
        ("AI Edge draft", (market.get("ai_edge") or {}).get("fair_probability") if isinstance(market.get("ai_edge"), dict) else None, None),
        ("evidence-adjusted model", (market.get("evidence_probability") or {}).get("evidence_adjusted_probability") if isinstance(market.get("evidence_probability"), dict) else None, None),
        ("deterministic baseline model", (market.get("probability_model") or {}).get("model_probability") if isinstance(market.get("probability_model"), dict) else None, None),
        ("market field", market.get("model_fair_yes") or market.get("fair_probability") or market.get("model_probability"), market.get("model_fair_no")),
    ]
    for source, yes, no in sources:
        yes_norm = normalize_probability(yes)
        if yes_norm is not None:
            no_norm = normalize_probability(no)
            if no_norm is None:
                no_norm = round(1.0 - yes_norm, 6)
            return {"model_fair_yes": yes_norm, "model_fair_no": no_norm, "model_fair_source": source}
    return {"model_fair_yes": None, "model_fair_no": None, "model_fair_source": "unavailable"}


def default_edge_thresholds() -> dict[str, Any]:
    return {
        "yes_pp": float(getattr(settings, "edge_min_yes_pp", 2.0)),
        "no_pp": float(getattr(settings, "edge_min_no_pp", 2.0)),
        "min_liquidity": getattr(settings, "edge_min_liquidity", None),
        "min_volume_24h": getattr(settings, "edge_min_volume_24h", None),
        "require_fresh_data": bool(getattr(settings, "edge_require_fresh_data", True)),
        "max_data_age_minutes": getattr(settings, "edge_max_data_age_minutes", None),
        "show_favorite_rank": bool(getattr(settings, "edge_show_favorite_rank", True)),
        "show_family_groups": bool(getattr(settings, "edge_show_family_groups", True)),
        "show_ai_edge_actions": bool(getattr(settings, "edge_show_ai_edge_actions", True)),
        "recommendation_mode": getattr(settings, "edge_default_recommendation_mode", "review_only"),
    }


def calculate_yes_no_edges(
    market_yes_price: Any,
    market_no_price: Any,
    model_fair_yes: Any,
    model_fair_no: Any | None = None,
) -> dict[str, Any]:
    yes = normalize_probability(market_yes_price)
    no = normalize_probability(market_no_price)
    fair_yes = normalize_probability(model_fair_yes)
    fair_no = normalize_probability(model_fair_no)
    if fair_no is None and fair_yes is not None:
        fair_no = round(1.0 - fair_yes, 6)

    missing = []
    if yes is None:
        missing.append("market_yes_price")
    if no is None:
        missing.append("market_no_price")
    if fair_yes is None:
        missing.append("model_fair_yes")
    if fair_no is None:
        missing.append("model_fair_no")

    yes_edge_pp = None if missing else round((fair_yes - yes) * 100.0, 3)  # type: ignore[operator]
    no_edge_pp = None if missing else round((fair_no - no) * 100.0, 3)  # type: ignore[operator]
    sum_yes_no = None if yes is None or no is None else round(yes + no, 6)
    overround_note = ""
    if sum_yes_no is not None and abs(sum_yes_no - 1.0) > 0.03:
        overround_note = f"YES + NO price sum is {sum_yes_no:.3f}; calculation is approximate and does not hide spread/fees."

    return {
        "market_yes_price": yes,
        "market_no_price": no,
        "model_fair_yes": fair_yes,
        "model_fair_no": fair_no,
        "yes_edge_pp": yes_edge_pp,
        "no_edge_pp": no_edge_pp,
        "missing_fields": missing,
        "sum_yes_no": sum_yes_no,
        "overround_note": overround_note,
        "calculation_note": "yes_edge_pp = (model_fair_yes - market_yes_price) * 100; no_edge_pp = (model_fair_no - market_no_price) * 100.",
    }


def _confidence_label(market: dict[str, Any], model_context: dict[str, Any] | None = None) -> str:
    ctx = model_context or {}
    evidence_probability = market.get("evidence_probability") if isinstance(market.get("evidence_probability"), dict) else {}
    value = (
        ctx.get("confidence")
        or ctx.get("confidence_label")
        or evidence_probability.get("evidence_adjusted_confidence")
    )
    if not value and isinstance(market.get("probability_model"), dict):
        value = market["probability_model"].get("confidence")
    return str(value or "low").replace("_", " ")


def _data_quality(market: dict[str, Any], confidence: str, thresholds: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []
    liquidity = _safe_float(market.get("liquidity"), 0.0) or 0.0
    volume_24h = _safe_float(market.get("volume_24hr") or market.get("volume24hr"), 0.0) or 0.0
    min_liq = thresholds.get("min_liquidity")
    min_vol = thresholds.get("min_volume_24h")
    if min_liq not in {None, ""} and liquidity < float(min_liq):
        blockers.append(f"Liquidity ${liquidity:,.0f} is below configured minimum ${float(min_liq):,.0f}.")
    elif liquidity <= 0:
        warnings.append("Liquidity is unavailable or zero.")
    if min_vol not in {None, ""} and volume_24h < float(min_vol):
        blockers.append(f"24h volume ${volume_24h:,.0f} is below configured minimum ${float(min_vol):,.0f}.")
    elif volume_24h <= 0:
        warnings.append("24h volume is unavailable or zero.")

    age_minutes = _safe_float(market.get("data_age_minutes") or market.get("market_data_age_minutes"), None)
    max_age = thresholds.get("max_data_age_minutes")
    if max_age not in {None, ""} and age_minutes is not None and age_minutes > float(max_age):
        blockers.append(f"Market data is stale: {age_minutes:.0f} minutes old, above {float(max_age):.0f} minute maximum.")
    elif thresholds.get("require_fresh_data") and age_minutes is None:
        warnings.append("Freshness age is unavailable; verify prices before any review decision.")

    if confidence.lower() in {"blocked", "unavailable", "insufficient data", "insufficient_data"}:
        blockers.append("Model confidence is blocked or unavailable.")
    elif confidence.lower() in {"low", "low-medium", "low medium"}:
        warnings.append(f"Confidence is {confidence}; treat recommendation as weak draft research.")

    evidence_warning = ""
    ep = market.get("evidence_probability") if isinstance(market.get("evidence_probability"), dict) else {}
    if ep and not ep.get("evidence_inputs"):
        evidence_warning = "No saved evidence packet is linked to this market."
        warnings.append(evidence_warning)

    return {
        "liquidity": liquidity,
        "volume_24h": volume_24h,
        "confidence": confidence,
        "warnings": warnings,
        "blockers": blockers,
        "liquidity_warning": next((w for w in warnings + blockers if "Liquidity" in w or "liquidity" in w), ""),
        "freshness_warning": next((w for w in warnings + blockers if "Freshness" in w or "fresh" in w or "stale" in w), ""),
        "evidence_quality_warning": evidence_warning,
        "passes": not blockers,
    }


def recommend_wager_side(edge_result: dict[str, Any], thresholds: dict[str, Any] | None = None, data_quality: dict[str, Any] | None = None) -> dict[str, Any]:
    thresholds = thresholds or default_edge_thresholds()
    data_quality = data_quality or {"passes": True, "blockers": []}
    missing = edge_result.get("missing_fields") or []
    if missing:
        return {"recommended_side": "INSUFFICIENT DATA", "side_badge": "INSUFFICIENT DATA", "status": "insufficient_data", "decision_reason": "Missing: " + ", ".join(missing)}
    if not data_quality.get("passes", True):
        return {"recommended_side": "NEEDS REVIEW", "side_badge": "NEEDS REVIEW", "status": "needs_review", "decision_reason": "; ".join(data_quality.get("blockers") or ["Data quality failed configured gates."])}
    yes_edge = float(edge_result.get("yes_edge_pp") or 0.0)
    no_edge = float(edge_result.get("no_edge_pp") or 0.0)
    yes_threshold = float(thresholds.get("yes_pp", 2.0))
    no_threshold = float(thresholds.get("no_pp", 2.0))
    if yes_edge >= yes_threshold and yes_edge > no_edge:
        return {"recommended_side": "YES", "side_badge": "DRAFT YES EDGE", "status": "draft_yes_edge", "decision_reason": f"YES edge {yes_edge:+.1f} pp exceeds {yes_threshold:.1f} pp threshold."}
    if no_edge >= no_threshold and no_edge > yes_edge:
        return {"recommended_side": "NO", "side_badge": "DRAFT NO EDGE", "status": "draft_no_edge", "decision_reason": f"NO edge {no_edge:+.1f} pp exceeds {no_threshold:.1f} pp threshold."}
    if yes_edge >= yes_threshold and no_edge >= no_threshold and abs(yes_edge - no_edge) < 0.001:
        return {"recommended_side": "NEEDS REVIEW", "side_badge": "NEEDS REVIEW", "status": "needs_review", "decision_reason": "YES and NO edges are tied after normalization."}
    return {"recommended_side": "HOLD", "side_badge": "NO CLEAR EDGE", "status": "hold", "decision_reason": "Neither YES nor NO edge exceeds the configured threshold."}


def _fmt_pct(value: Any) -> str:
    prob = normalize_probability(value)
    if prob is None:
        return "unavailable"
    return f"{prob * 100:.1f}%"


def _fmt_pp(value: Any) -> str:
    if value is None:
        return "unavailable"
    return f"{float(value):+.1f} pp"


def explain_edge_recommendation(edge_result: dict[str, Any], decision: dict[str, Any], family_context: dict[str, Any] | None = None) -> str:
    side = decision.get("recommended_side")
    if side == "YES":
        sentence = (
            f"Model fair YES {_fmt_pct(edge_result.get('model_fair_yes'))} vs market YES {_fmt_pct(edge_result.get('market_yes_price'))} "
            f"= {_fmt_pp(edge_result.get('yes_edge_pp'))} draft YES edge."
        )
    elif side == "NO":
        sentence = (
            f"Model fair YES {_fmt_pct(edge_result.get('model_fair_yes'))} vs market YES {_fmt_pct(edge_result.get('market_yes_price'))}; "
            f"model fair NO {_fmt_pct(edge_result.get('model_fair_no'))} vs market NO {_fmt_pct(edge_result.get('market_no_price'))} "
            f"= {_fmt_pp(edge_result.get('no_edge_pp'))} draft NO edge."
        )
    elif side == "INSUFFICIENT DATA":
        sentence = "Model fair probability or market-implied price is unavailable, so no YES/NO edge is labeled."
    elif side == "NEEDS REVIEW":
        sentence = f"Data consistency or quality needs review before a side can be labeled: {decision.get('decision_reason', 'review required')}."
    else:
        sentence = "Model fair probability is too close to market price, or data quality is not strong enough, so the draft recommendation is HOLD / no wager."
    if edge_result.get("overround_note"):
        sentence += " " + str(edge_result["overround_note"])
    if family_context and family_context.get("group_rank_label"):
        sentence += " " + str(family_context["group_rank_label"])
    return sentence


def detect_market_family_from_title(title: str) -> dict[str, Any] | None:
    text = re.sub(r"\s+", " ", str(title or "").strip().rstrip("?"))
    if not text:
        return None
    patterns = [
        re.compile(r"^will (?P<outcome>.+?) win (?:the )?(?P<event>\d{4} fifa world cup)$", re.I),
        re.compile(r"^will (?P<outcome>.+?) win (?:the )?(?P<event>.+?(?:world cup|super bowl|nba finals|stanley cup|champions league|premier league|tournament|championship|election|presidential election|senate|governor|mayor|oscar|academy award|grammy|emmy|award))$", re.I),
        re.compile(r"^will (?P<outcome>.+?) be (?:the )?(?P<event>next .+?(?:president|prime minister|governor|mayor|senator|speaker))$", re.I),
    ]
    for pattern in patterns:
        match = pattern.match(text)
        if not match:
            continue
        outcome = match.group("outcome").strip()
        event = match.group("event").strip()
        family_title = f"{event} winner" if "next " not in event.lower() else event
        return {
            "family_id": _slugify(family_title),
            "family_title": family_title[0:1].upper() + family_title[1:],
            "outcome_label": outcome,
            "detection_confidence": "medium",
            "detection_source": "title pattern",
        }
    return None


def detect_market_family_from_slug(slug: str) -> dict[str, Any] | None:
    text = str(slug or "").replace("_", "-").lower().strip("-")
    if not text:
        return None
    match = re.match(r"(?P<outcome>.+?)-win-(?P<event>\d{4}-fifa-world-cup)", text)
    if match:
        event = match.group("event").replace("-", " ")
        return {
            "family_id": _slugify(f"{event} winner"),
            "family_title": f"{event.title()} winner",
            "outcome_label": match.group("outcome").replace("-", " ").title(),
            "detection_confidence": "low",
            "detection_source": "slug pattern",
        }
    return None


def detect_market_family(market: dict[str, Any]) -> dict[str, Any] | None:
    return detect_market_family_from_title(_market_title(market)) or detect_market_family_from_slug(_market_slug(market))


def group_related_markets(markets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    detected: dict[str, dict[str, Any]] = {}
    for market in markets:
        family = detect_market_family(market)
        if not family:
            continue
        family_id = family["family_id"]
        enriched = {"market": market, "family": family, "market_key": _market_key(market)}
        buckets.setdefault(family_id, []).append(enriched)
    for family_id, rows in buckets.items():
        if len(rows) < 2:
            continue
        market_rank = sorted(rows, key=lambda row: (extract_market_prices(row["market"]).get("market_yes_price") or -1), reverse=True)
        model_rank = sorted(rows, key=lambda row: (_extract_model_probability(row["market"]).get("model_fair_yes") or -1), reverse=True)
        market_positions = {row["market_key"]: index + 1 for index, row in enumerate(market_rank)}
        model_positions = {row["market_key"]: index + 1 for index, row in enumerate(model_rank)}
        market_favorite_key = market_rank[0]["market_key"]
        model_favorite_key = model_rank[0]["market_key"]
        title = rows[0]["family"].get("family_title") or family_id
        for row in rows:
            key = row["market_key"]
            rank_market = market_positions[key]
            rank_model = model_positions[key]
            is_market_fav = key == market_favorite_key
            is_model_fav = key == model_favorite_key
            label = (
                f"Group favorite: rank #1 by market YES price among detected {title} markets."
                if is_market_fav
                else f"Group rank #{rank_market} by market YES price among detected {title} markets."
            )
            if is_model_fav and not is_market_fav:
                label += " Rank #1 by model fair probability."
            detected[key] = {
                "family_id": family_id,
                "family_title": title,
                "outcome_label": row["family"].get("outcome_label"),
                "family_size": len(rows),
                "rank_by_market_yes_price": rank_market,
                "rank_by_model_fair_yes": rank_model,
                "is_market_favorite": is_market_fav,
                "is_model_favorite": is_model_fav,
                "group_rank_label": label,
                "favorite_vs_edge_note": FAVORITE_VS_EDGE_EXPLAINER,
            }
    return detected


def rank_market_family(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    family_context = group_related_markets(markets)
    rows = []
    for market in markets:
        key = _market_key(market)
        if key in family_context:
            rows.append({"market_id": key, "question": _market_title(market), **family_context[key]})
    return sorted(rows, key=lambda row: (row.get("family_id", ""), row.get("rank_by_market_yes_price") or 999))


def build_market_recommendation_row(
    market: dict[str, Any],
    model_context: dict[str, Any] | None = None,
    family_context: dict[str, Any] | None = None,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or default_edge_thresholds()
    price = extract_market_prices(market)
    model = _extract_model_probability(market, model_context)
    edge = calculate_yes_no_edges(price.get("market_yes_price"), price.get("market_no_price"), model.get("model_fair_yes"), model.get("model_fair_no"))
    confidence = _confidence_label(market, model_context)
    quality = _data_quality(market, confidence, thresholds)
    decision = recommend_wager_side(edge, thresholds, quality)
    explanation = explain_edge_recommendation(edge, decision, family_context)
    market_id = _market_key(market)
    market_slug = _market_slug(market)
    family_id = (family_context or {}).get("family_id") or ""
    packet_href = f"/v3/ai/edge/market/{market_id}" if market_id else "/v3/ai/edge"
    row = {
        "app_version": APP_VERSION,
        "market_id": market_id,
        "market_slug": market_slug,
        "question": _market_title(market),
        "market_yes_price": edge.get("market_yes_price"),
        "market_no_price": edge.get("market_no_price"),
        "market_implied_probability": edge.get("market_yes_price"),
        "market_implied_source": price.get("market_implied_source"),
        "model_fair_yes": edge.get("model_fair_yes"),
        "model_fair_no": edge.get("model_fair_no"),
        "model_fair_source": model.get("model_fair_source"),
        "yes_edge_pp": edge.get("yes_edge_pp"),
        "no_edge_pp": edge.get("no_edge_pp"),
        "minimum_yes_edge_pp": thresholds.get("yes_pp"),
        "minimum_no_edge_pp": thresholds.get("no_pp"),
        "recommended_side": decision.get("recommended_side"),
        "side_badge": decision.get("side_badge"),
        "recommendation_status": decision.get("status"),
        "decision_reason": decision.get("decision_reason"),
        "confidence_label": confidence,
        "explanation": explanation,
        "why": explanation,
        "edge_calculation_note": edge.get("calculation_note"),
        "favorite_vs_edge_note": (family_context or {}).get("favorite_vs_edge_note", FAVORITE_VS_EDGE_EXPLAINER),
        "family_id": family_id,
        "family_title": (family_context or {}).get("family_title") or "No family detected",
        "family_size": (family_context or {}).get("family_size"),
        "outcome_label": (family_context or {}).get("outcome_label"),
        "group_rank_label": (family_context or {}).get("group_rank_label", "No family detected"),
        "rank_by_market_yes_price": (family_context or {}).get("rank_by_market_yes_price"),
        "rank_by_model_fair_yes": (family_context or {}).get("rank_by_model_fair_yes"),
        "is_market_favorite": (family_context or {}).get("is_market_favorite", False),
        "is_model_favorite": (family_context or {}).get("is_model_favorite", False),
        "data_quality_warnings": list(price.get("price_warnings") or []) + list(quality.get("warnings") or []),
        "data_quality_blockers": quality.get("blockers") or [],
        "liquidity_warning": quality.get("liquidity_warning", ""),
        "freshness_warning": quality.get("freshness_warning", ""),
        "evidence_quality_warning": quality.get("evidence_quality_warning", ""),
        "spread_note": price.get("spread_note") or edge.get("overround_note") or "",
        "sum_yes_no": edge.get("sum_yes_no"),
        "approximate_no_from_complement": price.get("approximate_no_from_complement"),
        "ai_edge_analyze_href": packet_href,
        "ai_edge_market_href": packet_href,
        "ai_edge_summary_href": f"/api/v3/ai/edge/market/{market_id}/summary" if market_id else "/api/v3/ai/edge/summary",
        "ai_edge_packet_href": f"/api/v3/ai/edge/market/{market_id}/packet" if market_id else "/api/v3/ai/edge/packets",
        "ai_edge_family_href": f"/api/v3/ai/edge/family/{family_id}/summary" if family_id else "",
        "evidence_href": f"/api/v3/ai/edge/evidence?market_id={market_id}" if market_id else "/v3/ai/edge/evidence",
        "calibration_href": "/v3/ai/edge/calibration",
        "safety_note": RECOMMENDATION_SAFETY_NOTE,
        "research_only": True,
        "not_financial_advice": True,
        "no_trade_approval": True,
        "no_live_mutation": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
    }
    return row


def enrich_markets_with_recommendations(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    family_contexts = group_related_markets(markets) if getattr(settings, "edge_show_family_groups", True) else {}
    out: list[dict[str, Any]] = []
    for market in markets:
        item = dict(market)
        key = _market_key(item)
        recommendation = build_market_recommendation_row(item, family_context=family_contexts.get(key))
        item["market_edge_recommendation"] = recommendation
        item["recommended_side"] = recommendation["recommended_side"]
        item["recommendation_status"] = recommendation["recommendation_status"]
        item["model_fair_yes"] = recommendation["model_fair_yes"]
        item["model_fair_no"] = recommendation["model_fair_no"]
        item["yes_edge_pp"] = recommendation["yes_edge_pp"]
        item["no_edge_pp"] = recommendation["no_edge_pp"]
        item["market_family_id"] = recommendation["family_id"]
        item["market_family_rank_label"] = recommendation["group_rank_label"]
        out.append(item)
    return out


def edge_recommendation_legend() -> dict[str, Any]:
    thresholds = default_edge_thresholds()
    return {
        "version": APP_VERSION,
        "recommended_sides": ["YES", "NO", "HOLD", "NO CLEAR EDGE", "NEEDS REVIEW", "INSUFFICIENT DATA"],
        "edge_definition": "Positive expected-value draft edge is approximated as model fair probability minus market-implied price, in percentage points.",
        "yes_edge_formula": "(model_fair_yes - market_yes_price) * 100",
        "no_edge_formula": "(model_fair_no - market_no_price) * 100",
        "minimum_yes_edge_pp": thresholds.get("yes_pp"),
        "minimum_no_edge_pp": thresholds.get("no_pp"),
        "favorite_vs_edge": FAVORITE_VS_EDGE_EXPLAINER,
        "safety_note": RECOMMENDATION_SAFETY_NOTE,
        "research_only": True,
        "no_trade_approval": True,
        "no_live_mutation": True,
        "order_submitted": False,
        "order_cancelled": False,
    }
