from __future__ import annotations

from typing import Any


def recommend_paper_trades(
    markets: list[dict[str, Any]],
    min_edge: float = 0.02,
    min_confidence_score: float = 35.0,
    max_price: float = 0.95,
    max_recommendations: int = 20,
    default_stake: float = 100.0,
) -> list[dict[str, Any]]:
    """Return deterministic paper-trade candidates from already-scored markets.

    This is intentionally conservative and transparent. It never places trades.
    """
    rows: list[dict[str, Any]] = []
    for market in markets:
        pm = market.get("probability_model") or {}
        edge = pm.get("edge")
        market_probability = pm.get("market_probability")
        confidence_score = float(pm.get("confidence_score") or 0.0)
        if edge is None or market_probability is None:
            continue
        if edge < min_edge:
            continue
        if confidence_score < min_confidence_score:
            continue
        if float(market_probability) <= 0.0 or float(market_probability) >= max_price:
            continue
        expected_value = float(edge) * default_stake
        rows.append(
            {
                "market_id": str(market.get("id")),
                "question": market.get("question"),
                "outcome": "YES",
                "recommended_action": "paper_buy_yes",
                "suggested_stake": round(default_stake, 2),
                "market_probability": round(float(market_probability), 4),
                "model_probability": pm.get("model_probability"),
                "edge": round(float(edge), 4),
                "edge_percent": pm.get("edge_percent"),
                "confidence": pm.get("confidence"),
                "confidence_score": round(confidence_score, 1),
                "expected_value_per_100": round(float(edge) * 100.0, 2),
                "expected_value_at_stake": round(expected_value, 2),
                "reason_codes": pm.get("reason_codes") or [],
                "opportunity_score": market.get("opportunity_score", 0),
                "volume_24hr": market.get("volume_24hr", 0),
                "liquidity": market.get("liquidity", 0),
                "url": market.get("url"),
            }
        )
    return sorted(rows, key=lambda r: (r["expected_value_at_stake"], r["confidence_score"], r["opportunity_score"]), reverse=True)[:max_recommendations]


def explain_strategy() -> dict[str, Any]:
    return {
        "name": "Probability Model v1 Paper Strategy",
        "status": "simulation_only",
        "rules": [
            "Only considers YES-side simulated buys.",
            "Requires positive model edge above the configured threshold.",
            "Requires minimum confidence score.",
            "Skips extreme prices above the configured maximum price.",
            "Never sends orders, signs messages, or touches a wallet.",
        ],
        "default_parameters": {
            "min_edge": 0.02,
            "min_confidence_score": 35.0,
            "max_price": 0.95,
            "default_stake": 100.0,
        },
    }
