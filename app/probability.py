from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.01, high: float = 0.99) -> float:
    return max(low, min(high, value))


def _yes_price(market: dict[str, Any]) -> float | None:
    outcomes = market.get("outcomes") or []
    if not isinstance(outcomes, list) or not outcomes:
        return None
    for row in outcomes:
        if isinstance(row, dict) and str(row.get("name", "")).lower() in {"yes", "y"}:
            return _clamp(_num(row.get("price")))
    first = outcomes[0]
    if isinstance(first, dict):
        price = _num(first.get("price"), -1.0)
        if 0.0 <= price <= 1.0:
            return _clamp(price)
    return None


def estimate_probability(market: dict[str, Any]) -> dict[str, Any]:
    """Small deterministic probability model v1.

    This is not a forecasting oracle. It gives us a repeatable paper-trading signal
    that can later be compared against actual results and replaced with better models.
    """
    market_price = _yes_price(market)
    if market_price is None:
        return {
            "market_probability": None,
            "model_probability": None,
            "edge": None,
            "confidence": "low",
            "signal": "skip",
            "reason_codes": ["no usable outcome price"],
        }

    volume_24hr = _num(market.get("volume_24hr"))
    liquidity = _num(market.get("liquidity"))
    attention = _num(market.get("opportunity_score"))
    tradability = _num((market.get("score_components") or {}).get("tradability_score"))

    # Small nudges only. We intentionally avoid large claims until we have backtests.
    volume_nudge = 0.00
    if volume_24hr >= 100000:
        volume_nudge = 0.015
    elif volume_24hr >= 25000:
        volume_nudge = 0.010
    elif volume_24hr >= 5000:
        volume_nudge = 0.005

    liquidity_nudge = 0.00
    if liquidity >= 250000:
        liquidity_nudge = 0.010
    elif liquidity >= 50000:
        liquidity_nudge = 0.006
    elif liquidity >= 10000:
        liquidity_nudge = 0.003

    # Extreme quoted probabilities are often resolved/stale/noisy for a scanner; dampen edge.
    extreme_penalty = 0.0
    if market_price <= 0.03 or market_price >= 0.97:
        extreme_penalty = -0.020

    model_probability = _clamp(market_price + volume_nudge + liquidity_nudge + extreme_penalty)
    edge = model_probability - market_price

    confidence_score = (min(attention, 100.0) * 0.50) + (min(tradability, 100.0) * 0.50)
    if market_price <= 0.03 or market_price >= 0.97:
        confidence_score *= 0.65
    if confidence_score >= 70:
        confidence = "medium"
    elif confidence_score >= 40:
        confidence = "low-medium"
    else:
        confidence = "low"

    if edge >= 0.025 and confidence in {"medium", "low-medium"}:
        signal = "paper_buy_yes"
    elif edge <= -0.025 and confidence in {"medium", "low-medium"}:
        signal = "paper_avoid_yes"
    else:
        signal = "watch"

    reasons = []
    if volume_nudge:
        reasons.append("active volume")
    if liquidity_nudge:
        reasons.append("usable liquidity")
    if extreme_penalty:
        reasons.append("extreme price dampener")
    if not reasons:
        reasons.append("limited signal strength")

    return {
        "market_probability": round(market_price, 4),
        "model_probability": round(model_probability, 4),
        "edge": round(edge, 4),
        "edge_percent": round(edge * 100, 2),
        "confidence": confidence,
        "confidence_score": round(confidence_score, 1),
        "signal": signal,
        "reason_codes": reasons,
    }


def attach_probability(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for market in markets:
        item = dict(market)
        estimate = estimate_probability(item)
        item["probability_model"] = estimate
        item["model_probability"] = estimate.get("model_probability")
        item["market_probability"] = estimate.get("market_probability")
        item["model_edge"] = estimate.get("edge")
        item["model_signal"] = estimate.get("signal")
        item["mispricing_status"] = _label(estimate)
        out.append(item)
    return sorted(out, key=lambda m: (m.get("probability_model") or {}).get("edge") or -999, reverse=True)


def _label(estimate: dict[str, Any]) -> str:
    edge = estimate.get("edge")
    if edge is None:
        return "INSUFFICIENT DATA · model fair probability or market YES price unavailable"
    if edge >= 0.025:
        return f"DRAFT YES EDGE · model fair YES exceeds market YES by {edge * 100:+.1f} pp"
    if edge <= -0.025:
        return f"DRAFT NO EDGE · model fair YES is below market YES by {abs(edge) * 100:.1f} pp"
    return "HOLD · no clear YES/NO edge above threshold"
