from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from .config import settings


def _parse_jsonish(value: Any) -> Any:
    """Gamma often returns list-like fields as JSON strings. Parse when safe."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class GammaClient:
    """Small async client for Polymarket's public Gamma API."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.gamma_base_url).rstrip("/")
        self.timeout = timeout or settings.request_timeout_seconds

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "polymarket-gamma-starter/0.1"}) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def list_events(
        self,
        limit: int = 20,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = "volume_24hr",
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        data = await self._get(
            "/events",
            {
                "active": str(active).lower(),
                "closed": str(closed).lower(),
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": str(ascending).lower(),
            },
        )
        if not isinstance(data, list):
            return []
        return [normalize_event(item) for item in data]

    async def list_markets(
        self,
        limit: int = 20,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = "volume24hr",
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        data = await self._get(
            "/markets",
            {
                "active": str(active).lower(),
                "closed": str(closed).lower(),
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": str(ascending).lower(),
            },
        )
        if not isinstance(data, list):
            return []
        return [normalize_market(item) for item in data]

    async def get_market(self, market_id: str) -> dict[str, Any] | None:
        data = await self._get(f"/markets/{market_id}")
        if isinstance(data, dict):
            return normalize_market(data)
        return None

    async def search(self, query: str, limit: int = 20) -> Any:
        return await self._get("/public-search", {"q": query, "limit": limit})


def _first_event_slug(payload: dict[str, Any]) -> str:
    for key in ("eventSlug", "event_slug", "parentEventSlug"):
        val = payload.get(key)
        if val:
            return str(val)
    events = payload.get("events")
    if isinstance(events, list) and events:
        first = events[0]
        if isinstance(first, dict) and first.get("slug"):
            return str(first.get("slug"))
    event = payload.get("event")
    if isinstance(event, dict) and event.get("slug"):
        return str(event.get("slug"))
    return ""


def build_polymarket_links(kind: str, slug: str | None, question: str, event_slug: str | None = None) -> dict[str, Any]:
    """Build safer Polymarket links without pretending market slugs are event slugs.

    Polymarket event pages use /event/<event-slug>. Individual market selections on
    an event page commonly use ?marketSlug=<market-slug>&outcomeIndex=0. Some Gamma
    /markets records only include the market slug, not the parent event slug; in that
    case a search URL is safer than a guessed dead direct URL.
    """
    slug = str(slug or "").strip()
    event_slug = str(event_slug or "").strip()
    question = str(question or "").strip()
    search_url = f"https://polymarket.com/search?query={quote(question)}" if question else "https://polymarket.com/"
    candidates: list[dict[str, str]] = []
    if kind == "event" and slug:
        direct = f"https://polymarket.com/event/{slug}"
        candidates.append({"label": "Event page", "url": direct, "confidence": "high"})
        return {"primary_url": direct, "primary_label": "Open event on Polymarket", "confidence": "high", "search_url": search_url, "candidates": candidates}
    if event_slug and slug:
        direct = f"https://polymarket.com/event/{event_slug}?marketSlug={slug}&outcomeIndex=0"
        candidates.append({"label": "Event page with market selected", "url": direct, "confidence": "high"})
        candidates.append({"label": "Parent event", "url": f"https://polymarket.com/event/{event_slug}", "confidence": "high"})
        return {"primary_url": direct, "primary_label": "Open market on Polymarket", "confidence": "high", "search_url": search_url, "candidates": candidates}
    if slug:
        candidates.append({"label": "Possible legacy market URL", "url": f"https://polymarket.com/market/{slug}", "confidence": "low"})
        candidates.append({"label": "Possible event URL", "url": f"https://polymarket.com/event/{slug}", "confidence": "low"})
    candidates.append({"label": "Polymarket search", "url": search_url, "confidence": "safe"})
    return {"primary_url": search_url, "primary_label": "Search on Polymarket", "confidence": "safe", "search_url": search_url, "candidates": candidates}


def normalize_market(market: dict[str, Any], parent_event_slug: str | None = None) -> dict[str, Any]:
    outcomes = _parse_jsonish(market.get("outcomes"))
    prices = _parse_jsonish(market.get("outcomePrices"))
    token_ids = _parse_jsonish(market.get("clobTokenIds"))

    if not isinstance(outcomes, list):
        outcomes = []
    if not isinstance(prices, list):
        prices = []
    if not isinstance(token_ids, list):
        token_ids = []

    outcome_rows = []
    for i, outcome in enumerate(outcomes):
        price = prices[i] if i < len(prices) else None
        outcome_rows.append({"name": str(outcome), "price": _to_float(price, 0.0)})

    question = market.get("question") or market.get("title") or "Untitled market"
    slug = market.get("slug")
    event_slug = parent_event_slug or _first_event_slug(market)
    links = build_polymarket_links("market", slug, question, event_slug=event_slug)

    return {
        "id": market.get("id"),
        "question": question,
        "slug": slug,
        "event_slug": event_slug,
        "category": market.get("category") or "",
        "end_date": market.get("endDateIso") or market.get("endDate") or "",
        "active": bool(market.get("active")),
        "closed": bool(market.get("closed")),
        "enable_order_book": bool(market.get("enableOrderBook")),
        "accepting_orders": bool(market.get("acceptingOrders")),
        "volume_24hr": _to_float(market.get("volume24hr") or market.get("volume24hrClob")),
        "volume": _to_float(market.get("volumeNum") or market.get("volume")),
        "liquidity": _to_float(market.get("liquidityNum") or market.get("liquidity")),
        "outcomes": outcome_rows,
        "clob_token_ids": token_ids,
        "url": links["primary_url"],
        "polymarket_url": links["primary_url"],
        "polymarket_url_label": links["primary_label"],
        "polymarket_url_confidence": links["confidence"],
        "polymarket_search_url": links["search_url"],
        "polymarket_url_candidates": links["candidates"],
    }


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    markets = event.get("markets") if isinstance(event.get("markets"), list) else []
    event_slug = str(event.get("slug") or "")
    normalized_markets = [normalize_market(m, parent_event_slug=event_slug) for m in markets[:5] if isinstance(m, dict)]
    title = event.get("title") or event.get("question") or "Untitled event"
    slug = event.get("slug")
    links = build_polymarket_links("event", slug, title)
    return {
        "id": event.get("id"),
        "title": title,
        "slug": slug,
        "category": event.get("category") or event.get("subcategory") or "",
        "end_date": event.get("endDate") or "",
        "active": bool(event.get("active")),
        "closed": bool(event.get("closed")),
        "volume_24hr": _to_float(event.get("volume24hr")),
        "volume": _to_float(event.get("volume")),
        "liquidity": _to_float(event.get("liquidity")),
        "open_interest": _to_float(event.get("openInterest")),
        "markets": normalized_markets,
        "url": links["primary_url"],
        "polymarket_url": links["primary_url"],
        "polymarket_url_label": links["primary_label"],
        "polymarket_url_confidence": links["confidence"],
        "polymarket_search_url": links["search_url"],
        "polymarket_url_candidates": links["candidates"],
    }
