from __future__ import annotations

from typing import Any

from .evidence import list_evidence_packets, load_evidence_packet
from .evidence_scoring import score_market_evidence, score_packet_by_id
from .probability import estimate_probability


def _clamp(value: float, low: float = 0.01, high: float = 0.99) -> float:
    return max(low, min(high, value))


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _packet_adjustment(packet: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    """Convert evidence readiness into a conservative probability adjustment.

    This is intentionally conservative. Evidence is not yet being semantically
    interpreted for outcome direction; it changes confidence and applies only a
    small directionless quality adjustment unless humans mark evidence items as
    contradictory. This keeps the roadmap honest: data collection -> evidence ->
    probability inputs, without pretending the app has solved forecasting.
    """
    readiness = _norm(score.get("readiness"))
    readiness_score = float(score.get("score") or 0.0)
    contradictory = int(score.get("contradictory_items") or 0)
    verified = int(score.get("verified_items") or 0)
    reviewed = int(score.get("reviewed_items") or 0)

    confidence_delta = 0.0
    probability_delta = 0.0
    direction = "neutral"
    reasons: list[str] = []

    if readiness == "model_ready":
        confidence_delta += 15.0
        probability_delta += 0.010
        reasons.append("model-ready evidence packet")
    elif readiness == "partial":
        confidence_delta += 8.0
        probability_delta += 0.004
        reasons.append("partial evidence packet")
    elif readiness in {"early", "not_started"}:
        confidence_delta += 2.0 if reviewed else 0.0
        reasons.append("evidence packet is not fully reviewed")
    elif readiness == "needs_human_review":
        confidence_delta -= 8.0
        probability_delta -= 0.006
        direction = "caution"
        reasons.append("contradictory evidence requires human review")

    if verified >= 3:
        confidence_delta += 5.0
        reasons.append("multiple verified or strong evidence items")
    if contradictory:
        confidence_delta -= min(15.0, contradictory * 5.0)
        probability_delta -= min(0.015, contradictory * 0.004)
        direction = "caution"
        reasons.append("contradictory item penalty")

    # The evidence score itself provides a small confidence-only lift.
    if readiness_score >= 70:
        confidence_delta += 4.0
    elif readiness_score >= 45:
        confidence_delta += 2.0

    return {
        "packet_id": score.get("packet_id") or packet.get("packet_id") or "",
        "readiness": score.get("readiness"),
        "evidence_score": readiness_score,
        "probability_delta": round(probability_delta, 4),
        "confidence_delta": round(confidence_delta, 1),
        "direction": direction,
        "reason_codes": reasons or ["no evidence adjustment"],
    }


def evidence_adjusted_probability(market: dict[str, Any]) -> dict[str, Any]:
    base = estimate_probability(market)
    market_id = str(market.get("id") or market.get("market_id") or "")
    if base.get("market_probability") is None or base.get("model_probability") is None:
        return {
            "market_id": market_id,
            "question": market.get("question") or market.get("title") or "",
            "base_model": base,
            "evidence_adjusted_probability": None,
            "evidence_adjusted_edge": None,
            "evidence_adjusted_confidence_score": None,
            "evidence_adjusted_confidence": "low",
            "evidence_inputs": [],
            "reason_codes": ["no usable base market probability"],
        }

    market_score = score_market_evidence(market_id)
    packet_ids = [str(row.get("packet_id") or "") for row in list_evidence_packets(limit=200) if str(row.get("market_id")) == market_id]
    adjustments = []
    for packet_id in packet_ids[:5]:
        if not packet_id:
            continue
        try:
            packet = load_evidence_packet(packet_id)
            score = score_packet_by_id(packet_id)
            adjustments.append(_packet_adjustment(packet, score))
        except Exception:
            continue

    total_probability_delta = sum(float(a.get("probability_delta") or 0) for a in adjustments)
    total_confidence_delta = sum(float(a.get("confidence_delta") or 0) for a in adjustments)
    # Keep early evidence from moving model odds too far.
    total_probability_delta = max(-0.03, min(0.03, total_probability_delta))
    adjusted_probability = _clamp(float(base["model_probability"]) + total_probability_delta)
    adjusted_edge = adjusted_probability - float(base["market_probability"])
    adjusted_confidence_score = max(0.0, min(100.0, float(base.get("confidence_score") or 0.0) + total_confidence_delta))

    if adjusted_confidence_score >= 75:
        confidence = "high"
    elif adjusted_confidence_score >= 60:
        confidence = "medium"
    elif adjusted_confidence_score >= 40:
        confidence = "low-medium"
    else:
        confidence = "low"

    reasons = ["base model plus evidence-readiness adjustment"]
    if not adjustments:
        reasons.append("no saved evidence packets for this market")
    if market_score.get("best_packet"):
        reasons.append(f"best evidence readiness: {market_score.get('best_packet', {}).get('readiness')}")

    signal = "watch"
    if adjusted_edge >= 0.03 and confidence in {"high", "medium", "low-medium"}:
        signal = "paper_buy_yes_candidate"
    elif adjusted_edge <= -0.03 and confidence in {"high", "medium", "low-medium"}:
        signal = "avoid_or_review_yes_candidate"

    return {
        "market_id": market_id,
        "question": market.get("question") or market.get("title") or "",
        "market_probability": base.get("market_probability"),
        "base_model_probability": base.get("model_probability"),
        "base_edge": base.get("edge"),
        "evidence_probability_delta": round(total_probability_delta, 4),
        "evidence_confidence_delta": round(total_confidence_delta, 1),
        "evidence_adjusted_probability": round(adjusted_probability, 4),
        "evidence_adjusted_edge": round(adjusted_edge, 4),
        "evidence_adjusted_edge_percent": round(adjusted_edge * 100, 2),
        "evidence_adjusted_confidence_score": round(adjusted_confidence_score, 1),
        "evidence_adjusted_confidence": confidence,
        "evidence_adjusted_signal": signal,
        "market_evidence_score": market_score,
        "evidence_inputs": adjustments,
        "reason_codes": reasons,
        "note": "Evidence-adjusted probability is a conservative research-quality input, not live-trading advice.",
    }


def attach_evidence_probability(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for market in markets:
        item = dict(market)
        ep = evidence_adjusted_probability(item)
        item["evidence_probability"] = ep
        item["evidence_adjusted_probability"] = ep.get("evidence_adjusted_probability")
        item["evidence_adjusted_edge"] = ep.get("evidence_adjusted_edge")
        item["evidence_adjusted_signal"] = ep.get("evidence_adjusted_signal")
        out.append(item)
    return sorted(out, key=lambda m: (m.get("evidence_probability") or {}).get("evidence_adjusted_edge") or -999, reverse=True)
