
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default

def _get_market_id(item: Dict[str, Any]) -> str:
    return str(item.get("market_id") or item.get("id") or item.get("conditionId") or item.get("slug") or "")

@dataclass
class ReviewItem:
    market_id: str
    title: str
    priority: float
    stage: str
    action: str
    reason: str
    edge: float
    confidence: float
    risk_score: float
    evidence_score: float
    thesis_score: float
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def _norm(x: float) -> float:
    return x / 100.0 if abs(x) > 1 else x

def build_review_queue(opportunities: List[Dict[str, Any]], thesis_scores: Dict[str, Dict[str, Any]] | None = None, limit: int = 25) -> List[Dict[str, Any]]:
    thesis_scores = thesis_scores or {}
    queue: List[ReviewItem] = []
    for opp in opportunities:
        market_id = _get_market_id(opp)
        title = str(opp.get("title") or opp.get("question") or opp.get("name") or "Untitled market")
        edge = _norm(_safe_float(opp.get("edge", opp.get("edge_percent", opp.get("edge_pct", opp.get("estimated_edge", 0.0))))))
        confidence = _norm(_safe_float(opp.get("confidence_score", opp.get("confidence", 0.0))))
        risk_score = _norm(_safe_float(opp.get("risk_score", opp.get("risk", 0.5))))
        evidence_score = _norm(_safe_float(opp.get("evidence_score", opp.get("evidence", 0.0))))
        thesis_score = _norm(_safe_float((thesis_scores.get(market_id) or {}).get("score", 0.0)))

        readiness = max(0.0, edge) * 0.35 + confidence * 0.25 + evidence_score * 0.20 + thesis_score * 0.20
        risk_penalty = max(0.0, risk_score - 0.55) * 0.35
        priority = max(0.0, readiness - risk_penalty)

        if evidence_score < 0.35:
            stage, action, reason = "Evidence Needed", "Collect evidence", "Opportunity exists, but evidence is too thin for a paper trade."
        elif thesis_score < 0.35:
            stage, action, reason = "Thesis Needed", "Write thesis", "Evidence exists, but the trade thesis/invalidation criteria are weak."
        elif risk_score > 0.75:
            stage, action, reason = "Risk Review", "Review risk", "Potential edge is offset by high risk."
        elif edge > 0 and confidence >= 0.50:
            stage, action, reason = "Paper Candidate", "Consider paper trade", "Positive edge with adequate confidence and supporting material."
        else:
            stage, action, reason = "Monitor", "Monitor", "Not enough edge or confidence to act."

        queue.append(ReviewItem(market_id, title, round(priority, 4), stage, action, reason, round(edge, 4), round(confidence, 4), round(risk_score, 4), round(evidence_score, 4), round(thesis_score, 4)))
    queue.sort(key=lambda x: x.priority, reverse=True)
    return [q.to_dict() for q in queue[:limit]]
