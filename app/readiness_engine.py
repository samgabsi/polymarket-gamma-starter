
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


def _norm(value: Any, default: float = 0.0) -> float:
    x = _safe_float(value, default)
    if abs(x) > 1:
        x = x / 100.0
    return max(0.0, min(1.0, x))


def _edge(value: Any, default: float = 0.0) -> float:
    x = _safe_float(value, default)
    if abs(x) > 1:
        x = x / 100.0
    return max(-1.0, min(1.0, x))


@dataclass
class ReadinessResult:
    market_id: str
    title: str
    status: str
    readiness_score: float
    paper_trade_ready: bool
    suggested_next_action: str
    edge: float
    confidence: float
    evidence_score: float
    thesis_score: float
    risk_score: float
    blockers: List[str]
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_readiness_result(
    opportunity: Dict[str, Any],
    evidence_score: float | None = None,
    thesis_score: float | None = None,
    risk_score: float | None = None,
) -> Dict[str, Any]:
    market_id = str(opportunity.get("market_id") or opportunity.get("id") or opportunity.get("conditionId") or opportunity.get("slug") or "")
    title = str(opportunity.get("title") or opportunity.get("question") or opportunity.get("name") or "Untitled market")

    edge = _edge(opportunity.get("edge", opportunity.get("edge_percent", opportunity.get("edge_pct", opportunity.get("estimated_edge", 0.0)))))
    confidence = _norm(opportunity.get("confidence_score", opportunity.get("confidence", 0.0)))
    evidence_score = _norm(evidence_score if evidence_score is not None else opportunity.get("evidence_score", 0.0))
    thesis_score = _norm(thesis_score if thesis_score is not None else opportunity.get("thesis_score", 0.0))
    risk_score = _norm(risk_score if risk_score is not None else opportunity.get("risk_score", opportunity.get("risk", 0.5)), 0.5)

    readiness = (
        max(0.0, edge) * 0.30
        + confidence * 0.20
        + evidence_score * 0.20
        + thesis_score * 0.20
        + (1.0 - risk_score) * 0.10
    )

    blockers: List[str] = []
    reasons: List[str] = []

    if edge <= 0:
        blockers.append("No positive model edge detected.")
    else:
        reasons.append("Positive model edge detected.")

    if confidence < 0.50:
        blockers.append("Model confidence below 50%.")
    else:
        reasons.append("Model confidence is adequate.")

    if evidence_score < 0.45:
        blockers.append("Evidence score below 45%.")
    else:
        reasons.append("Evidence support is adequate.")

    if thesis_score < 0.40:
        blockers.append("Thesis score below 40%.")
    else:
        reasons.append("Thesis support is adequate.")

    if risk_score > 0.70:
        blockers.append("Risk score above 70%.")
    else:
        reasons.append("Risk score is within review bounds.")

    if readiness < 0.55:
        blockers.append("Composite readiness score below 55%.")
    else:
        reasons.append("Composite readiness score is above the paper-trade gate.")

    paper_ready = not blockers and readiness >= 0.55

    if paper_ready:
        status = "Paper Trade Ready"
        action = "Review order sizing and consider a simulated paper trade."
    elif evidence_score < 0.45:
        status = "Evidence Needed"
        action = "Collect supporting and contradicting evidence."
    elif thesis_score < 0.40:
        status = "Thesis Needed"
        action = "Write or improve thesis and invalidation criteria."
    elif risk_score > 0.70:
        status = "Risk Review"
        action = "Review exposure, liquidity, volatility, and event ambiguity."
    elif confidence < 0.50:
        status = "Monitor"
        action = "Monitor until confidence improves."
    else:
        status = "Review"
        action = "Manual review recommended."

    return ReadinessResult(
        market_id=market_id,
        title=title,
        status=status,
        readiness_score=round(readiness, 4),
        paper_trade_ready=paper_ready,
        suggested_next_action=action,
        edge=round(edge, 4),
        confidence=round(confidence, 4),
        evidence_score=round(evidence_score, 4),
        thesis_score=round(thesis_score, 4),
        risk_score=round(risk_score, 4),
        blockers=blockers,
        reasons=reasons,
    ).to_dict()


def build_readiness_board(
    opportunities: List[Dict[str, Any]],
    evidence_scores: Dict[str, float] | None = None,
    thesis_scores: Dict[str, float] | None = None,
    risk_scores: Dict[str, float] | None = None,
    limit: int = 50,
) -> Dict[str, Any]:
    evidence_scores = evidence_scores or {}
    thesis_scores = thesis_scores or {}
    risk_scores = risk_scores or {}

    items = []
    for opp in opportunities[:limit]:
        mid = str(opp.get("market_id") or opp.get("id") or opp.get("conditionId") or opp.get("slug") or "")
        items.append(build_readiness_result(
            opp,
            evidence_score=evidence_scores.get(mid, opp.get("evidence_score", 0.0)),
            thesis_score=thesis_scores.get(mid, opp.get("thesis_score", 0.0)),
            risk_score=risk_scores.get(mid, opp.get("risk_score", opp.get("risk", 0.5))),
        ))

    items.sort(key=lambda x: (x["paper_trade_ready"], x["readiness_score"]), reverse=True)

    return {
        "summary": {
            "total": len(items),
            "paper_trade_ready": sum(1 for i in items if i["paper_trade_ready"]),
            "needs_evidence": sum(1 for i in items if i["status"] == "Evidence Needed"),
            "needs_thesis": sum(1 for i in items if i["status"] == "Thesis Needed"),
            "risk_review": sum(1 for i in items if i["status"] == "Risk Review"),
        },
        "items": items,
    }
