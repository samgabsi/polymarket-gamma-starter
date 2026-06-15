from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse
from typing import Any

import httpx

from .config import APP_VERSION

SOURCE_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "google_news",
        "name": "Google News Search",
        "category": "news",
        "requires_key": False,
        "role": "breaking-news discovery and broad source triangulation",
        "url_template": "https://news.google.com/search?q={query}",
        "notes": "Use this to find current reporting before forming any probability update.",
    },
    {
        "id": "reuters_search",
        "name": "Reuters Search",
        "category": "news",
        "requires_key": False,
        "role": "primary/low-noise news checks where available",
        "url_template": "https://www.reuters.com/site-search/?query={query}",
        "notes": "Good for major macro, geopolitical, business, legal, and market-moving events.",
    },
    {
        "id": "ap_search",
        "name": "Associated Press Search",
        "category": "news",
        "requires_key": False,
        "role": "wire-service validation",
        "url_template": "https://apnews.com/search?q={query}",
        "notes": "Useful independent confirmation for high-impact public events.",
    },
    {
        "id": "sec_edgar",
        "name": "SEC EDGAR Search",
        "category": "government_data",
        "requires_key": False,
        "role": "public-company filings and official disclosures",
        "url_template": "https://www.sec.gov/edgar/search/#/q={query}",
        "notes": "Use for IPO, merger, earnings, executive, filing, and company-event markets.",
    },
    {
        "id": "federal_register",
        "name": "Federal Register Search",
        "category": "government_data",
        "requires_key": False,
        "role": "US regulatory/public-rulemaking checks",
        "url_template": "https://www.federalregister.gov/documents/search?conditions%5Bterm%5D={query}",
        "notes": "Useful for policy/regulatory markets where official publication matters.",
    },
    {
        "id": "congress",
        "name": "Congress.gov Search",
        "category": "government_data",
        "requires_key": False,
        "role": "US legislation status checks",
        "url_template": "https://www.congress.gov/search?q={query}",
        "notes": "Use for lawmaking, bill passage, government, and committee-related markets.",
    },
    {
        "id": "reddit_search",
        "name": "Reddit Search",
        "category": "social",
        "requires_key": False,
        "role": "retail sentiment and rumor discovery",
        "url_template": "https://www.reddit.com/search/?q={query}",
        "notes": "Treat as weak evidence; useful for finding narratives, not validating facts.",
    },
    {
        "id": "x_search",
        "name": "X / Twitter Search",
        "category": "social",
        "requires_key": False,
        "role": "fast rumor/news discovery",
        "url_template": "https://x.com/search?q={query}&src=typed_query&f=live",
        "notes": "Treat as unverified until matched against primary or reputable sources.",
    },
    {
        "id": "polymarket_search",
        "name": "Polymarket Search",
        "category": "market",
        "requires_key": False,
        "role": "canonical market/event lookup fallback",
        "url_template": "https://polymarket.com/search?q={query}",
        "notes": "Use when direct event URLs are missing or low confidence.",
    },
]


MARKET_TOPIC_RULES: list[dict[str, Any]] = [
    {"topic": "crypto", "keywords": ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "etf", "token"], "preferred_categories": ["news", "government_data", "market"]},
    {"topic": "macro", "keywords": ["fed", "rate", "inflation", "cpi", "unemployment", "recession", "gdp", "treasury"], "preferred_categories": ["news", "government_data", "market"]},
    {"topic": "politics", "keywords": ["election", "senate", "congress", "president", "minister", "speaker", "bill", "law"], "preferred_categories": ["news", "government_data", "social", "market"]},
    {"topic": "geopolitics", "keywords": ["war", "ukraine", "russia", "china", "iran", "nato", "troops", "military", "ceasefire"], "preferred_categories": ["news", "social", "market"]},
    {"topic": "company_filings", "keywords": ["ipo", "earnings", "sec", "merger", "acquisition", "lawsuit", "ceo", "stock"], "preferred_categories": ["government_data", "news", "market"]},
    {"topic": "sports", "keywords": ["world cup", "nba", "nfl", "nhl", "mlb", "championship", "win the", "final", "match"], "preferred_categories": ["news", "social", "market"]},
    {"topic": "ai_technology", "keywords": ["openai", "anthropic", "google", "model", "ai", "launch", "hardware", "benchmark"], "preferred_categories": ["news", "social", "market"]},
]


def _source_public(source: dict[str, Any]) -> dict[str, Any]:
    item = dict(source)
    item.pop("url_template", None)
    return item


def infer_market_topics(market: dict[str, Any] | str) -> list[dict[str, Any]]:
    if isinstance(market, str):
        text = market
    else:
        text = " ".join([
            str(market.get("question") or ""),
            str(market.get("title") or ""),
            str(market.get("slug") or "").replace("-", " "),
            str(market.get("category") or ""),
        ])
    low = text.lower()
    matches: list[dict[str, Any]] = []
    for rule in MARKET_TOPIC_RULES:
        matched = [kw for kw in rule["keywords"] if kw in low]
        if matched:
            matches.append({
                "topic": rule["topic"],
                "matched_keywords": matched,
                "preferred_categories": rule["preferred_categories"],
            })
    if not matches:
        matches.append({"topic": "general", "matched_keywords": [], "preferred_categories": ["news", "market", "social"]})
    return matches


def recommended_source_ids_for_market(market: dict[str, Any]) -> list[str]:
    topics = infer_market_topics(market)
    preferred_categories: list[str] = []
    for topic in topics:
        for category in topic.get("preferred_categories", []):
            if category not in preferred_categories:
                preferred_categories.append(category)
    ordered: list[str] = []
    for category in preferred_categories:
        for source in SOURCE_REGISTRY:
            if source.get("category") == category and source["id"] not in ordered:
                ordered.append(source["id"])
    for source in SOURCE_REGISTRY:
        if source["id"] not in ordered and source.get("category") == "market":
            ordered.append(source["id"])
    return ordered


def build_market_collection_targets(market: dict[str, Any]) -> dict[str, Any]:
    query = extract_market_query(market)
    topic_matches = infer_market_topics(market)
    recommended_ids = set(recommended_source_ids_for_market(market))
    links = build_source_links(query)
    primary = []
    secondary = []
    weak = []
    for link in links:
        if link["id"] in recommended_ids and link["category"] in {"news", "government_data", "market"}:
            primary.append(link)
        elif link["category"] == "social":
            weak.append(link)
        else:
            secondary.append(link)
    return {
        "market_id": str(market.get("id") or ""),
        "question": market.get("question") or market.get("title") or "",
        "query": query,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topics": topic_matches,
        "primary_targets": primary,
        "secondary_targets": secondary,
        "weak_signal_targets": weak,
        "collection_steps": [
            "Check primary/official sources first and record dated facts in notes.",
            "Use social sources only to discover leads or rumors, not to validate facts.",
            "Compare verified facts to current market odds and model edge.",
            "Paper trade only when the rationale is documented and risk checks pass.",
        ],
        "note": "Collection targets only. No AI summarization, no external keys, and no live trading.",
    }


async def check_source_status(source: dict[str, Any], timeout: float = 4.0) -> dict[str, Any]:
    template = source.get("url_template", "")
    parsed = urlparse(template)
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else template
    started_at = datetime.now(timezone.utc)
    item = _source_public(source)
    item.update({"base_url": base_url, "checked_at": started_at.isoformat(), "ok": False, "status_code": None, "latency_ms": None, "error": ""})
    if not base_url:
        item["error"] = "missing base URL"
        return item
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": f"polymarket-gamma-starter/{APP_VERSION}"}) as client:
            response = await client.get(base_url)
        elapsed = datetime.now(timezone.utc) - started_at
        item["status_code"] = response.status_code
        item["latency_ms"] = round(elapsed.total_seconds() * 1000, 1)
        item["ok"] = 200 <= response.status_code < 400
        if not item["ok"]:
            item["error"] = f"HTTP {response.status_code}"
    except Exception as exc:  # network diagnostics only
        elapsed = datetime.now(timezone.utc) - started_at
        item["latency_ms"] = round(elapsed.total_seconds() * 1000, 1)
        item["error"] = str(exc)[:240]
    return item


async def check_sources_status(category: str | None = None, timeout: float = 4.0) -> dict[str, Any]:
    sources = list_sources(category=category)
    results = [await check_source_status(source, timeout=timeout) for source in sources]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "ok_count": sum(1 for row in results if row.get("ok")),
        "fail_count": sum(1 for row in results if not row.get("ok")),
        "items": results,
        "note": "Live source availability check only. It does not fetch article content or require keys.",
    }


def list_sources(category: str | None = None) -> list[dict[str, Any]]:
    rows = SOURCE_REGISTRY
    if category:
        rows = [row for row in rows if row.get("category") == category]
    return [dict(row) for row in rows]


def source_summary() -> dict[str, Any]:
    categories: dict[str, int] = {}
    for row in SOURCE_REGISTRY:
        categories[row["category"]] = categories.get(row["category"], 0) + 1
    return {
        "count": len(SOURCE_REGISTRY),
        "categories": categories,
        "requires_keys_now": any(row.get("requires_key") for row in SOURCE_REGISTRY),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def extract_market_query(market: dict[str, Any]) -> str:
    question = str(market.get("question") or market.get("title") or "").strip()
    if not question:
        question = str(market.get("slug") or "polymarket market").replace("-", " ")
    return question[:180]


def build_source_links(query: str, category: str | None = None) -> list[dict[str, Any]]:
    encoded = quote_plus(query)
    links = []
    for source in list_sources(category=category):
        item = dict(source)
        item["query"] = query
        item["url"] = source["url_template"].format(query=encoded)
        item.pop("url_template", None)
        links.append(item)
    return links


def build_market_source_pack(market: dict[str, Any]) -> dict[str, Any]:
    query = extract_market_query(market)
    links = build_source_links(query)
    categories: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        categories.setdefault(link["category"], []).append(link)
    return {
        "market_id": str(market.get("id") or ""),
        "question": market.get("question") or market.get("title") or "",
        "query": query,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(links),
        "categories": categories,
        "links": links,
        "collection_targets": build_market_collection_targets(market),
        "workflow": [
            "Open high-quality news and official-source links first.",
            "Record claims and timestamps in local notes.",
            "Compare evidence against current market probability.",
            "Only use the paper-trading engine after documenting rationale.",
        ],
        "note": "Source pack only. This is a data-collection/research aid, not a trading signal.",
    }
