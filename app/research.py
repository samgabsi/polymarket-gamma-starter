from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote_plus
from typing import Any

STOPWORDS = {
    "will", "the", "this", "that", "there", "with", "from", "before", "after", "have", "has",
    "into", "than", "over", "under", "above", "below", "yes", "no", "and", "or", "for", "to",
    "of", "in", "on", "by", "a", "an", "is", "are", "be", "as", "at", "if", "its", "it",
    "market", "polymarket", "resolve", "resolved", "end", "date", "2026", "2027", "2028",
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_keywords(question: str, max_terms: int = 8) -> list[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9$%.-]{2,}", question)
    result: list[str] = []
    seen: set[str] = set()
    for word in words:
        key = word.lower().strip(".-")
        if key in STOPWORDS or len(key) < 3:
            continue
        if key not in seen:
            seen.add(key)
            result.append(word.strip(".-"))
        if len(result) >= max_terms:
            break
    return result


def build_search_links(question: str) -> list[dict[str, str]]:
    q = quote_plus(question)
    news_q = quote_plus(f"{question} latest news")
    return [
        {"label": "Google News", "url": f"https://news.google.com/search?q={news_q}"},
        {"label": "Google Search", "url": f"https://www.google.com/search?q={q}"},
        {"label": "Reuters Search", "url": f"https://www.reuters.com/site-search/?query={q}"},
        {"label": "AP News Search", "url": f"https://apnews.com/search?q={q}"},
        {"label": "X Search", "url": f"https://x.com/search?q={q}&src=typed_query&f=live"},
    ]


def build_research_checklist(market: dict[str, Any]) -> list[str]:
    question = _clean_text(market.get("question"))
    lower = question.lower()
    items = [
        "Read the market resolution rules and confirm the exact settlement criteria.",
        "Find at least two independent primary or high-quality sources relevant to the outcome.",
        "Compare current market-implied probability to the source-backed estimate before making any trade decision.",
    ]
    if any(term in lower for term in ["bitcoin", "btc", "ethereum", "eth", "crypto"]):
        items.append("Compare against spot price, options/futures positioning, funding rates, and major crypto news catalysts.")
    if any(term in lower for term in ["fed", "rate", "cpi", "inflation", "unemployment", "recession"]):
        items.append("Check official economic calendars, recent data releases, and market-implied macro probabilities.")
    if any(term in lower for term in ["election", "president", "senate", "congress", "governor", "mayor"]):
        items.append("Check polling averages, official election calendars/rules, candidate status, and related markets.")
    if any(term in lower for term in ["nba", "nfl", "mlb", "nhl", "soccer", "ufc", "cup", "championship"]):
        items.append("Compare to major sportsbook odds and current injury/roster/schedule information.")
    if any(term in lower for term in ["openai", "anthropic", "google", "apple", "spacex", "tesla", "ai"]):
        items.append("Check official company channels, product release history, credible reporting, and timing ambiguity.")
    return items


def make_research_packet(market: dict[str, Any]) -> dict[str, Any]:
    question = _clean_text(market.get("question"))
    outcomes = market.get("outcomes") or []
    prices = []
    for row in outcomes:
        if isinstance(row, dict):
            prices.append({"name": row.get("name", ""), "price": row.get("price", 0)})
    implied = [f"{p['name']}: {float(p.get('price') or 0):.1%}" for p in prices if p.get("price") is not None]
    return {
        "market_id": market.get("id"),
        "question": question,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "category": market.get("category", ""),
        "end_date": market.get("end_date", ""),
        "url": market.get("url", ""),
        "keywords": extract_keywords(question),
        "search_links": build_search_links(question),
        "checklist": build_research_checklist(market),
        "implied_probabilities": implied,
        "attention_score": market.get("opportunity_score"),
        "why_analyze": market.get("why_analyze", []),
        "manual_notes": "Add human notes here after reviewing sources.",
        "model_probability": None,
        "edge_status": "Not evaluated. This packet prepares research; it is not a trading signal.",
    }
