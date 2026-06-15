from __future__ import annotations

import math
from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _log_score(value: Any, scale: float) -> float:
    value_f = max(_num(value), 0.0)
    if value_f <= 0:
        return 0.0
    return min(100.0, math.log10(value_f + 1.0) / math.log10(scale + 1.0) * 100.0)


def score_market(market: dict[str, Any]) -> dict[str, Any]:
    """Return a simple read-only analysis score for prioritizing research.

    This is not a trading signal. It ranks markets that are liquid/active enough to
    deserve human or model review.
    """
    volume_24hr = _num(market.get("volume_24hr"))
    volume_total = _num(market.get("volume"))
    liquidity = _num(market.get("liquidity"))
    outcomes = market.get("outcomes") or []
    prices = [_num(row.get("price")) for row in outcomes if isinstance(row, dict)]
    has_prices = bool(prices) and any(p > 0 for p in prices)
    two_sided = len([p for p in prices if 0 < p < 1]) >= 2
    accepts_orders = bool(market.get("accepting_orders"))
    order_book = bool(market.get("enable_order_book"))

    liquidity_score = _log_score(liquidity, 100_000)
    volume_score = _log_score(volume_24hr or volume_total, 250_000)
    tradability_score = 0.0
    tradability_score += 40.0 if accepts_orders else 0.0
    tradability_score += 30.0 if order_book else 0.0
    tradability_score += 20.0 if has_prices else 0.0
    tradability_score += 10.0 if two_sided else 0.0

    score = round((0.42 * volume_score) + (0.38 * liquidity_score) + (0.20 * tradability_score), 1)

    reasons: list[str] = []
    if volume_24hr > 0:
        reasons.append(f"24h volume ${volume_24hr:,.0f}")
    if liquidity > 0:
        reasons.append(f"liquidity ${liquidity:,.0f}")
    if accepts_orders and order_book:
        reasons.append("order book enabled and accepting orders")
    elif order_book:
        reasons.append("order book enabled")
    if has_prices:
        reasons.append("outcome prices available")

    return {
        "opportunity_score": score,
        "score_breakdown": {
            "volume_score": round(volume_score, 1),
            "liquidity_score": round(liquidity_score, 1),
            "tradability_score": round(tradability_score, 1),
        },
        "why_analyze": reasons or ["limited usable metrics returned by Gamma"],
        "model_view": "Needs research; this score ranks attention, not edge.",
        "mispricing_status": "Unknown until research/probability model is added.",
    }


def attach_scores(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for market in markets:
        item = dict(market)
        item.update(score_market(item))
        scored.append(item)
    return sorted(scored, key=lambda m: m.get("opportunity_score", 0), reverse=True)
