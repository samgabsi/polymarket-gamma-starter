
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

def _normalize_percent(value: Any, default: float = 0.0) -> float:
    raw = _safe_float(value, default)
    if raw > 1:
        return max(0.0, min(1.0, raw / 100.0))
    return max(0.0, min(1.0, raw))

def _text_score(text: str) -> float:
    text = (text or "").strip()
    if not text:
        return 0.0
    return max(0.0, min(1.0, len(text) / 800.0))

@dataclass
class ThesisScore:
    market_id: str
    thesis_count: int
    active_thesis_count: int
    average_confidence: float
    thesis_completeness: float
    invalidation_quality: float
    score: float
    verdict: str
    reasons: List[str]
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def score_market_theses(market_id: str, theses: List[Dict[str, Any]]) -> ThesisScore:
    relevant = [t for t in theses if str(t.get("market_id", "")) == str(market_id)]
    active = [t for t in relevant if str(t.get("status", "active")).lower() not in {"closed", "archived", "invalidated"}]
    if not relevant:
        return ThesisScore(str(market_id), 0, 0, 0.0, 0.0, 0.0, 0.0, "No thesis", ["No thesis has been recorded for this market yet."])

    population = active or relevant
    confidences = [_normalize_percent(t.get("confidence", t.get("confidence_score", 0))) for t in population]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    thesis_texts = []
    invalidation_texts = []
    for t in population:
        thesis_texts.append(" ".join(str(t.get(k, "") or "") for k in ("title", "thesis", "summary", "rationale", "evidence_summary", "notes")))
        invalidation_texts.append(" ".join(str(t.get(k, "") or "") for k in ("invalidation_criteria", "invalidation", "invalidates_if", "risk_notes")))

    completeness = sum(_text_score(t) for t in thesis_texts) / max(1, len(thesis_texts))
    invalidation = sum(_text_score(t) for t in invalidation_texts) / max(1, len(invalidation_texts))
    score = min(1.0, len(active) / 2.0) * 0.20 + avg_conf * 0.35 + completeness * 0.25 + invalidation * 0.20

    reasons = []
    reasons.append(f"{len(active)} active thesis record(s) found." if active else "Only inactive/closed thesis records found.")
    reasons.append("Thesis confidence is strong." if avg_conf >= 0.7 else "Thesis confidence is moderate." if avg_conf >= 0.4 else "Thesis confidence is weak or missing.")
    if completeness < 0.35:
        reasons.append("Thesis rationale needs more detail.")
    if invalidation < 0.25:
        reasons.append("Invalidation criteria are missing or thin.")

    verdict = "Strong thesis support" if score >= 0.75 else "Moderate thesis support" if score >= 0.50 else "Weak thesis support" if score >= 0.25 else "Insufficient thesis support"
    return ThesisScore(str(market_id), len(relevant), len(active), round(avg_conf, 4), round(completeness, 4), round(invalidation, 4), round(score, 4), verdict, reasons)

def score_all_market_theses(market_ids: List[str], theses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [score_market_theses(str(mid), theses).to_dict() for mid in market_ids]
