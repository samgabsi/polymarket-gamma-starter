from __future__ import annotations

from typing import Any

from .evidence import list_evidence_packets, load_evidence_packet

_STRENGTH_POINTS = {
    "verified": 20,
    "strong": 18,
    "medium": 12,
    "weak": 6,
    "contradictory": -12,
    "unknown": 0,
    "none": 0,
}

_STATUS_POINTS = {
    "collected": 8,
    "reviewed": 8,
    "pending_manual_review": 0,
    "unavailable": -3,
    "rejected": -5,
}

_PRIORITY_POINTS = {
    "primary": 7,
    "secondary": 4,
    "weak_signal": 1,
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_evidence_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Score whether a packet is research-ready for model review.

    This does not predict the market outcome. It scores research quality and
    source coverage so the probability layer can distinguish between
    unsupported model nudges and documented evidence.
    """
    items = packet.get("evidence_items") or []
    if not isinstance(items, list):
        items = []

    primary = [i for i in items if _norm(i.get("priority")) == "primary"]
    secondary = [i for i in items if _norm(i.get("priority")) == "secondary"]
    weak = [i for i in items if _norm(i.get("priority")) == "weak_signal"]

    reviewed = 0
    verified = 0
    contradictory = 0
    pending = 0
    item_points = 0.0
    reasons: list[str] = []

    for item in items:
        strength = _norm(item.get("evidence_strength")) or "unknown"
        status = _norm(item.get("collection_status")) or "pending_manual_review"
        priority = _norm(item.get("priority")) or "secondary"
        if status in {"collected", "reviewed"} or strength in {"verified", "strong", "medium", "weak", "contradictory"}:
            reviewed += 1
        else:
            pending += 1
        if strength in {"verified", "strong"}:
            verified += 1
        if strength == "contradictory":
            contradictory += 1
        item_points += _STRENGTH_POINTS.get(strength, 0)
        item_points += _STATUS_POINTS.get(status, 0)
        item_points += _PRIORITY_POINTS.get(priority, 2) if strength in {"verified", "strong", "medium", "weak"} else 0

    coverage_points = 0.0
    if primary:
        coverage_points += min(25, len(primary) * 4)
        reasons.append(f"{len(primary)} primary source target(s)")
    if secondary:
        coverage_points += min(15, len(secondary) * 2)
    if weak:
        coverage_points += min(5, len(weak))

    review_ratio = reviewed / max(1, len(items))
    review_points = review_ratio * 25
    contradiction_penalty = min(25, contradictory * 8)
    total = _clamp(coverage_points + review_points + item_points - contradiction_penalty)

    if reviewed == 0:
        readiness = "not_started"
        reasons.append("no evidence items reviewed yet")
    elif contradictory:
        readiness = "needs_human_review"
        reasons.append("contradictory evidence present")
    elif total >= 75 and verified >= 2:
        readiness = "model_ready"
        reasons.append("verified evidence coverage is sufficient for model review")
    elif total >= 45:
        readiness = "partial"
        reasons.append("some evidence reviewed; continue collection")
    else:
        readiness = "early"
        reasons.append("evidence coverage remains thin")

    return {
        "packet_id": packet.get("packet_id") or packet.get("id") or "",
        "market_id": (packet.get("market") or {}).get("id") or packet.get("market_id") or "",
        "question": (packet.get("market") or {}).get("question") or packet.get("question") or "",
        "score": round(total, 1),
        "readiness": readiness,
        "source_targets": len(items),
        "primary_targets": len(primary),
        "secondary_targets": len(secondary),
        "weak_signal_targets": len(weak),
        "reviewed_items": reviewed,
        "pending_items": pending,
        "verified_items": verified,
        "contradictory_items": contradictory,
        "review_ratio": round(review_ratio, 3),
        "reason_codes": reasons,
        "note": "Evidence score measures research readiness, not expected profit or true probability.",
    }


def score_packet_by_id(packet_id: str) -> dict[str, Any]:
    packet = load_evidence_packet(packet_id)
    packet["packet_id"] = packet_id
    return score_evidence_packet(packet)


def score_market_evidence(market_id: str, limit: int = 200) -> dict[str, Any]:
    rows = [row for row in list_evidence_packets(limit=limit) if str(row.get("market_id")) == str(market_id)]
    scores: list[dict[str, Any]] = []
    for row in rows:
        packet_id = str(row.get("packet_id") or "")
        if not packet_id:
            continue
        try:
            scores.append(score_packet_by_id(packet_id))
        except Exception:
            continue
    best = max(scores, key=lambda s: float(s.get("score") or 0), default=None)
    readiness_counts: dict[str, int] = {}
    for score in scores:
        key = str(score.get("readiness") or "unknown")
        readiness_counts[key] = readiness_counts.get(key, 0) + 1
    return {
        "market_id": str(market_id),
        "packet_count": len(scores),
        "best_score": best.get("score") if best else 0,
        "best_readiness": best.get("readiness") if best else "no_packets",
        "readiness_counts": readiness_counts,
        "best_packet": best,
        "packets": sorted(scores, key=lambda s: float(s.get("score") or 0), reverse=True),
        "note": "Market evidence score summarizes saved evidence packets. It does not execute trades.",
    }
