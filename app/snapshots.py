from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import settings


def _market_key(market: dict[str, Any]) -> str:
    return str(market.get("id") or market.get("slug") or market.get("question") or "")


def _num(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _price_map(market: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for outcome in market.get("outcomes") or []:
        if isinstance(outcome, dict):
            result[str(outcome.get("name") or "")] = _num(outcome.get("price"))
    return result


def load_latest() -> dict[str, Any] | None:
    if not settings.latest_path.exists():
        return None
    try:
        return json.loads(settings.latest_path.read_text())
    except json.JSONDecodeError:
        return None


def save_snapshot(markets: list[dict[str, Any]], source: str = "gamma") -> dict[str, Any]:
    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    payload = {
        "source": source,
        "created_at": now.isoformat(),
        "count": len(markets),
        "markets": markets,
    }
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = settings.snapshot_dir / f"markets_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    settings.latest_path.parent.mkdir(parents=True, exist_ok=True)
    settings.latest_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return {"path": str(path), "latest_path": str(settings.latest_path), "count": len(markets), "created_at": payload["created_at"]}


def summarize_snapshot(markets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(markets),
        "total_24h_volume": round(sum(_num(m.get("volume_24hr")) for m in markets), 2),
        "total_liquidity": round(sum(_num(m.get("liquidity")) for m in markets), 2),
        "accepting_orders": sum(1 for m in markets if m.get("accepting_orders")),
        "order_book_enabled": sum(1 for m in markets if m.get("enable_order_book")),
    }


def calculate_movers(current: list[dict[str, Any]], previous_payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if not previous_payload:
        return []
    previous = previous_payload.get("markets") or []
    prev_by_key = {_market_key(m): m for m in previous if isinstance(m, dict)}
    movers: list[dict[str, Any]] = []

    for market in current:
        key = _market_key(market)
        prev = prev_by_key.get(key)
        if not prev:
            continue

        volume_delta = _num(market.get("volume_24hr")) - _num(prev.get("volume_24hr"))
        liquidity_delta = _num(market.get("liquidity")) - _num(prev.get("liquidity"))
        current_prices = _price_map(market)
        previous_prices = _price_map(prev)
        price_changes = []
        max_abs_price_delta = 0.0
        for name, price in current_prices.items():
            if name in previous_prices:
                delta = price - previous_prices[name]
                max_abs_price_delta = max(max_abs_price_delta, abs(delta))
                if abs(delta) >= 0.01:
                    price_changes.append({"outcome": name, "delta": round(delta, 4), "from": previous_prices[name], "to": price})

        movement_score = abs(volume_delta) / 1000.0 + abs(liquidity_delta) / 1000.0 + max_abs_price_delta * 100.0
        if movement_score <= 0:
            continue
        movers.append({
            "id": market.get("id"),
            "slug": market.get("slug"),
            "question": market.get("question"),
            "url": market.get("url"),
            "volume_24hr_delta": round(volume_delta, 2),
            "liquidity_delta": round(liquidity_delta, 2),
            "price_changes": price_changes,
            "movement_score": round(movement_score, 2),
        })
    return sorted(movers, key=lambda m: m["movement_score"], reverse=True)


def detect_new_markets(current: list[dict[str, Any]], previous_payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if not previous_payload:
        return []
    previous = previous_payload.get("markets") or []
    prev_keys = {_market_key(m) for m in previous if isinstance(m, dict)}
    new_rows = [m for m in current if _market_key(m) not in prev_keys]
    return sorted(new_rows, key=lambda m: _num(m.get("volume_24hr")), reverse=True)
