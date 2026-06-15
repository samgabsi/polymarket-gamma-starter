from __future__ import annotations

from typing import Any

import httpx

from .config import APP_VERSION, settings


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class ClobClient:
    """Small async client for Polymarket CLOB public read-only endpoints."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.clob_base_url).rstrip("/")
        self.timeout = timeout or settings.request_timeout_seconds

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": f"polymarket-gamma-starter/{APP_VERSION}"}) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def get_order_book(self, token_id: str) -> dict[str, Any]:
        data = await self._get("/book", {"token_id": token_id})
        return normalize_order_book(data, token_id)

    async def get_books_for_tokens(self, token_ids: list[str], max_tokens: int = 4) -> list[dict[str, Any]]:
        books: list[dict[str, Any]] = []
        for token_id in token_ids[:max_tokens]:
            try:
                books.append(await self.get_order_book(token_id))
            except httpx.HTTPStatusError as exc:
                books.append({"token_id": token_id, "error": f"HTTP {exc.response.status_code}"})
            except Exception as exc:  # noqa: BLE001 - dashboard should degrade gracefully
                books.append({"token_id": token_id, "error": str(exc)})
        return books


def normalize_order_book(book: dict[str, Any], token_id: str) -> dict[str, Any]:
    bids = [_normalize_level(row) for row in book.get("bids", []) if isinstance(row, dict)]
    asks = [_normalize_level(row) for row in book.get("asks", []) if isinstance(row, dict)]

    bids = sorted(bids, key=lambda row: row["price"], reverse=True)
    asks = sorted(asks, key=lambda row: row["price"])

    best_bid = bids[0]["price"] if bids else None
    best_ask = asks[0]["price"] if asks else None
    spread = round(best_ask - best_bid, 4) if best_bid is not None and best_ask is not None else None
    midpoint = round((best_bid + best_ask) / 2, 4) if best_bid is not None and best_ask is not None else None

    bid_depth = round(sum(row["size"] for row in bids[:10]), 4)
    ask_depth = round(sum(row["size"] for row in asks[:10]), 4)

    return {
        "token_id": token_id,
        "market": book.get("market"),
        "asset_id": book.get("asset_id") or token_id,
        "timestamp": book.get("timestamp"),
        "hash": book.get("hash"),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "midpoint": midpoint,
        "bid_depth_top10": bid_depth,
        "ask_depth_top10": ask_depth,
        "last_trade_price": _to_float(book.get("last_trade_price"), 0.0),
        "min_order_size": _to_float(book.get("min_order_size"), 0.0),
        "tick_size": _to_float(book.get("tick_size"), 0.0),
        "neg_risk": bool(book.get("neg_risk")),
        "bids": bids[:25],
        "asks": asks[:25],
    }


def _normalize_level(row: dict[str, Any]) -> dict[str, float]:
    return {"price": _to_float(row.get("price")), "size": _to_float(row.get("size"))}
