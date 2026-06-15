from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR, settings
from .readiness_engine import build_readiness_result

PLAYBOOKS_PATH = DATA_DIR / "paper" / "strategy_playbooks.json"
DECISIONS_PATH = DATA_DIR / "paper" / "playbook_decisions.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


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


def _market_id(payload: dict[str, Any]) -> str:
    return str(payload.get("market_id") or payload.get("id") or payload.get("conditionId") or payload.get("slug") or "")


def _title(payload: dict[str, Any]) -> str:
    return str(payload.get("title") or payload.get("question") or payload.get("name") or _market_id(payload) or "Untitled market")


def _metric_value(metrics: dict[str, Any], key: str) -> float:
    return _safe_float(metrics.get(key), 0.0)


def default_playbooks() -> list[dict[str, Any]]:
    max_stake = float(settings.paper_max_stake_per_trade)
    return [
        {
            "playbook_id": "edge_evidence_confluence",
            "version": "0.4.0",
            "name": "Edge + Evidence Confluence",
            "status": "active",
            "intended_use": "Only consider a paper entry ticket when model edge, evidence, thesis, and risk all clear review gates.",
            "recommended_action": "create_paper_entry_ticket",
            "default_outcome": "YES",
            "gates": {
                "min_edge": 0.03,
                "min_confidence": 0.50,
                "min_evidence_score": 0.55,
                "min_thesis_score": 0.45,
                "max_risk_score": 0.70,
                "min_readiness_score": 0.55,
                "require_paper_ready": True,
                "min_liquidity": float(settings.paper_min_liquidity),
                "min_volume_24hr": float(settings.paper_min_volume_24hr),
            },
            "sizing": {"default_stake": min(100.0, max_stake), "max_stake": min(150.0, max_stake)},
            "position_plan_hints": {"target_price_delta": 0.08, "stop_price_delta": -0.05, "review_days": 3},
            "checklist": [
                "Resolution criteria are clear and not ambiguous.",
                "At least one supporting source and one contradicting/neutral source were reviewed.",
                "The invalidation condition is written before the simulated entry.",
                "Paper risk limits still approve the stake at the current price.",
            ],
            "guardrail": "Paper-entry playbook only. It never places live orders or bypasses human review.",
        },
        {
            "playbook_id": "research_watchlist_candidate",
            "version": "0.4.0",
            "name": "Research / Watchlist Candidate",
            "status": "active",
            "intended_use": "Promote interesting markets into evidence collection before a ticket exists.",
            "recommended_action": "collect_evidence_or_watchlist",
            "default_outcome": "YES",
            "gates": {
                "min_abs_edge": 0.015,
                "min_confidence": 0.35,
                "max_evidence_score": 0.60,
                "min_liquidity": 0.0,
                "min_volume_24hr": 0.0,
            },
            "sizing": {"default_stake": 0.0, "max_stake": 0.0},
            "position_plan_hints": {},
            "checklist": [
                "Collect primary source links before creating an entry ticket.",
                "Write a thesis and invalidation note if the market remains interesting.",
                "Do not simulate an entry from this playbook alone.",
            ],
            "guardrail": "Research playbook only. No paper trade is recommended from this classification alone.",
        },
        {
            "playbook_id": "negative_or_low_confidence_filter",
            "version": "0.4.0",
            "name": "Negative / Low-Confidence Filter",
            "status": "active",
            "intended_use": "Flag markets that should stay out of the paper-entry path until edge or confidence improves.",
            "recommended_action": "avoid_or_manual_review",
            "default_outcome": "YES",
            "gates": {
                "max_edge": 0.0,
                "max_confidence": 0.50,
            },
            "sizing": {"default_stake": 0.0, "max_stake": 0.0},
            "position_plan_hints": {},
            "checklist": [
                "Do not create a paper entry ticket unless a separate thesis overrides the filter.",
                "Record why the market is being skipped if it looked attractive superficially.",
            ],
            "guardrail": "Filter playbook. Its default action is no simulated entry.",
        },
        {
            "playbook_id": "managed_position_review",
            "version": "0.4.0",
            "name": "Managed Position Review",
            "status": "active",
            "intended_use": "Use after a paper position exists to keep target, stop, review date, and exit-ticket discipline visible.",
            "recommended_action": "update_position_plan_or_exit_ticket",
            "default_outcome": "YES",
            "gates": {
                "min_open_position_count": 1,
            },
            "sizing": {"default_stake": 0.0, "max_stake": 0.0},
            "position_plan_hints": {"review_days": 2},
            "checklist": [
                "Confirm a target, stop, and max-hold review date exist.",
                "Create an exit ticket instead of directly simulating a sell when discipline calls for exit.",
                "Use the review report after any close or settlement.",
            ],
            "guardrail": "Position-management playbook only. It does not auto-sell or touch live orders.",
        },
    ]


def _normalize_playbook(row: dict[str, Any]) -> dict[str, Any]:
    playbook = dict(row)
    playbook["playbook_id"] = str(playbook.get("playbook_id") or playbook.get("id") or f"custom_{uuid4().hex[:8]}")
    playbook["name"] = str(playbook.get("name") or playbook["playbook_id"].replace("_", " ").title())
    playbook["status"] = str(playbook.get("status") or "active")
    playbook["gates"] = playbook.get("gates") if isinstance(playbook.get("gates"), dict) else {}
    playbook["sizing"] = playbook.get("sizing") if isinstance(playbook.get("sizing"), dict) else {}
    playbook["position_plan_hints"] = playbook.get("position_plan_hints") if isinstance(playbook.get("position_plan_hints"), dict) else {}
    playbook["checklist"] = playbook.get("checklist") if isinstance(playbook.get("checklist"), list) else []
    playbook.setdefault("version", "0.4.0")
    playbook.setdefault("recommended_action", "manual_review")
    playbook.setdefault("guardrail", "Local paper-only strategy playbook. No live execution.")
    return playbook


def load_playbooks() -> list[dict[str, Any]]:
    saved = _read_json(PLAYBOOKS_PATH, None)
    if not isinstance(saved, list) or not saved:
        return default_playbooks()
    by_id = {row["playbook_id"]: row for row in default_playbooks()}
    for row in saved:
        if isinstance(row, dict):
            normalized = _normalize_playbook(row)
            by_id[normalized["playbook_id"]] = normalized
    return list(by_id.values())


def save_playbooks(rows: list[dict[str, Any]]) -> None:
    _write_json(PLAYBOOKS_PATH, [_normalize_playbook(row) for row in rows])


def list_playbooks(active_only: bool = False) -> list[dict[str, Any]]:
    rows = load_playbooks()
    if active_only:
        rows = [row for row in rows if str(row.get("status")) == "active"]
    return sorted(rows, key=lambda row: (str(row.get("status") != "active"), str(row.get("name") or "")))


def get_playbook(playbook_id: str) -> dict[str, Any] | None:
    for row in load_playbooks():
        if str(row.get("playbook_id")) == str(playbook_id):
            return row
    return None


def upsert_playbook(playbook: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_playbook(playbook)
    rows = load_playbooks()
    for idx, row in enumerate(rows):
        if str(row.get("playbook_id")) == normalized["playbook_id"]:
            rows[idx] = {**row, **normalized, "updated_at": _now()}
            save_playbooks(rows)
            return rows[idx]
    normalized["created_at"] = _now()
    normalized["updated_at"] = _now()
    rows.append(normalized)
    save_playbooks(rows)
    return normalized


def _extract_metrics(opportunity: dict[str, Any], readiness: dict[str, Any] | None = None, review: dict[str, Any] | None = None) -> dict[str, Any]:
    readiness = readiness or build_readiness_result(opportunity)
    review = review or {}
    edge_value = _edge(readiness.get("edge", opportunity.get("edge", opportunity.get("edge_percent", 0.0))))
    confidence = _norm(readiness.get("confidence", opportunity.get("confidence_score", opportunity.get("confidence", 0.0))))
    evidence_score = _norm(readiness.get("evidence_score", opportunity.get("evidence_score", 0.0)))
    thesis_score = _norm(readiness.get("thesis_score", opportunity.get("thesis_score", 0.0)))
    risk_score = _norm(readiness.get("risk_score", opportunity.get("risk_score", opportunity.get("risk", 0.5))), 0.5)
    market_probability = _safe_float(opportunity.get("market_probability", opportunity.get("price", opportunity.get("yes_price", 0.5))), 0.5)
    return {
        "market_id": _market_id(opportunity) or str(readiness.get("market_id") or ""),
        "title": _title(opportunity) or str(readiness.get("title") or ""),
        "edge": round(edge_value, 4),
        "abs_edge": round(abs(edge_value), 4),
        "edge_percent": round(edge_value * 100, 2),
        "confidence": round(confidence, 4),
        "evidence_score": round(evidence_score, 4),
        "thesis_score": round(thesis_score, 4),
        "risk_score": round(risk_score, 4),
        "readiness_score": round(_norm(readiness.get("readiness_score"), 0.0), 4),
        "paper_trade_ready": bool(readiness.get("paper_trade_ready")),
        "liquidity": _safe_float(opportunity.get("liquidity"), 0.0),
        "volume_24hr": _safe_float(opportunity.get("volume_24hr", opportunity.get("volume24hr")), 0.0),
        "market_probability": round(market_probability, 4),
        "open_position_count": int(_safe_float(review.get("open_position_count"), 0.0)),
        "warning_count": int(_safe_float(review.get("warning_count"), 0.0)),
        "net_pnl": round(_safe_float(review.get("net_pnl"), 0.0), 4),
        "readiness_status": readiness.get("status"),
    }


def _gate_result(name: str, actual: Any, required: str, passed: bool, weight: float = 1.0) -> dict[str, Any]:
    return {
        "name": name,
        "actual": actual,
        "required": required,
        "passed": bool(passed),
        "weight": float(weight),
        "detail": f"{actual} vs {required}",
    }


def evaluate_playbook_fit(
    playbook: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    readiness: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    playbook = _normalize_playbook(playbook)
    gates = playbook.get("gates") or {}
    metrics = _extract_metrics(opportunity, readiness=readiness, review=review)
    results: list[dict[str, Any]] = []

    def add_min(metric: str, label: str, weight: float = 1.0) -> None:
        if metric in gates:
            required = _safe_float(gates.get(metric), 0.0)
            actual = _metric_value(metrics, metric.replace("min_", ""))
            results.append(_gate_result(label, round(actual, 4), f">= {required:g}", actual >= required, weight))

    def add_max(metric: str, label: str, weight: float = 1.0) -> None:
        if metric in gates:
            required = _safe_float(gates.get(metric), 0.0)
            actual = _metric_value(metrics, metric.replace("max_", ""))
            results.append(_gate_result(label, round(actual, 4), f"<= {required:g}", actual <= required, weight))

    add_min("min_edge", "Positive edge", 1.4)
    add_min("min_abs_edge", "Absolute edge", 1.0)
    add_max("max_edge", "Edge upper bound", 1.0)
    add_min("min_confidence", "Confidence", 1.0)
    add_max("max_confidence", "Confidence upper bound", 1.0)
    add_min("min_evidence_score", "Evidence score", 1.0)
    add_max("max_evidence_score", "Evidence score upper bound", 0.8)
    add_min("min_thesis_score", "Thesis score", 1.0)
    add_max("max_risk_score", "Risk score", 1.0)
    add_min("min_readiness_score", "Readiness score", 1.2)
    add_min("min_liquidity", "Liquidity", 0.7)
    add_min("min_volume_24hr", "24h volume", 0.5)
    add_min("min_open_position_count", "Open paper position count", 1.0)

    if gates.get("require_paper_ready") is True:
        results.append(_gate_result("Paper-ready gate", metrics["paper_trade_ready"], "true", bool(metrics["paper_trade_ready"]), 1.5))

    total_weight = sum(row["weight"] for row in results) or 1.0
    passed_weight = sum(row["weight"] for row in results if row["passed"])
    gate_score = passed_weight / total_weight
    signal_score = (
        max(0.0, metrics["edge"]) * 3.0
        + metrics["confidence"] * 0.20
        + metrics["evidence_score"] * 0.20
        + metrics["thesis_score"] * 0.15
        + metrics["readiness_score"] * 0.25
        + (1.0 - metrics["risk_score"]) * 0.10
    )
    signal_score = max(0.0, min(1.0, signal_score))
    fit_score = round((gate_score * 0.72 + signal_score * 0.28), 4)
    blockers = [row["name"] for row in results if not row["passed"]]
    matched = bool(results) and not blockers
    if playbook.get("playbook_id") == "negative_or_low_confidence_filter":
        matched = any(row["passed"] for row in results)
        blockers = [] if matched else ["Negative/low-confidence filter did not trigger."]

    action = str(playbook.get("recommended_action") or "manual_review") if matched else "not_ready_for_playbook"
    return {
        "playbook_id": playbook["playbook_id"],
        "playbook_name": playbook["name"],
        "playbook_status": playbook["status"],
        "market_id": metrics["market_id"],
        "title": metrics["title"],
        "matched": matched,
        "fit_score": fit_score,
        "gate_score": round(gate_score, 4),
        "signal_score": round(signal_score, 4),
        "recommended_action": action,
        "default_outcome": playbook.get("default_outcome", "YES"),
        "sizing": playbook.get("sizing") or {},
        "position_plan_hints": playbook.get("position_plan_hints") or {},
        "checklist": playbook.get("checklist") or [],
        "metrics": metrics,
        "gates": results,
        "blockers": blockers,
        "guardrail": playbook.get("guardrail"),
    }


def evaluate_market_playbooks(
    opportunity: dict[str, Any],
    *,
    readiness: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    playbook_id: str | None = None,
) -> dict[str, Any]:
    playbooks = list_playbooks(active_only=True)
    if playbook_id:
        playbooks = [p for p in playbooks if str(p.get("playbook_id")) == str(playbook_id)]
    readiness = readiness or build_readiness_result(opportunity)
    fits = [evaluate_playbook_fit(p, opportunity, readiness=readiness, review=review) for p in playbooks]
    fits.sort(key=lambda row: (row.get("matched", False), row.get("fit_score", 0.0)), reverse=True)
    best = fits[0] if fits else None
    return {
        "market_id": _market_id(opportunity) or str(readiness.get("market_id") or ""),
        "title": _title(opportunity) or str(readiness.get("title") or ""),
        "readiness": readiness,
        "best_fit": best,
        "items": fits,
        "guardrail": "Strategy playbook matches are deterministic local paper-workflow classifications, not investment advice or live execution.",
    }


def build_playbook_board(
    opportunities: list[dict[str, Any]],
    *,
    readiness_by_market: dict[str, dict[str, Any]] | None = None,
    review_by_market: dict[str, dict[str, Any]] | None = None,
    playbook_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    readiness_by_market = readiness_by_market or {}
    review_by_market = review_by_market or {}
    rows: list[dict[str, Any]] = []
    for opportunity in opportunities[:limit]:
        mid = _market_id(opportunity)
        readiness = readiness_by_market.get(mid) or build_readiness_result(opportunity)
        review = review_by_market.get(mid) or {}
        data = evaluate_market_playbooks(opportunity, readiness=readiness, review=review, playbook_id=playbook_id)
        best = data.get("best_fit") or {}
        metrics = best.get("metrics") or {}
        rows.append(
            {
                "market_id": mid or data.get("market_id"),
                "title": data.get("title"),
                "best_playbook_id": best.get("playbook_id"),
                "best_playbook_name": best.get("playbook_name"),
                "matched": bool(best.get("matched")),
                "fit_score": best.get("fit_score", 0.0),
                "recommended_action": best.get("recommended_action"),
                "blockers": best.get("blockers") or [],
                "metrics": metrics,
                "playbook_count": len(data.get("items") or []),
                "readiness": readiness,
            }
        )
    rows.sort(key=lambda row: (row.get("matched", False), row.get("fit_score", 0.0), _safe_float((row.get("metrics") or {}).get("liquidity"))), reverse=True)
    summary = summarize_playbook_board(rows)
    return {
        "summary": summary,
        "items": rows,
        "playbooks": list_playbooks(active_only=True),
        "guardrail": "Playbooks classify local paper workflows only. Human approval is required for every simulated ticket and no live trading exists.",
    }


def summarize_playbook_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions = Counter(str(row.get("recommended_action") or "unknown") for row in rows)
    playbooks = Counter(str(row.get("best_playbook_id") or "none") for row in rows)
    matched = [row for row in rows if row.get("matched")]
    return {
        "count": len(rows),
        "matched_count": len(matched),
        "ticket_candidate_count": actions.get("create_paper_entry_ticket", 0),
        "research_candidate_count": actions.get("collect_evidence_or_watchlist", 0),
        "avoid_or_review_count": actions.get("avoid_or_manual_review", 0),
        "action_counts": dict(sorted(actions.items())),
        "playbook_counts": dict(playbooks.most_common(20)),
        "avg_fit_score": round(sum(_safe_float(row.get("fit_score")) for row in rows) / len(rows), 4) if rows else 0.0,
        "guardrail": "Local paper strategy classification only; not investment advice.",
    }


def load_playbook_decisions() -> list[dict[str, Any]]:
    rows = _read_json(DECISIONS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_playbook_decisions(rows: list[dict[str, Any]]) -> None:
    _write_json(DECISIONS_PATH, rows)


def list_playbook_decisions(limit: int = 100, market_id: str | None = None, playbook_id: str | None = None) -> list[dict[str, Any]]:
    rows = list(reversed(load_playbook_decisions()))
    if market_id:
        rows = [row for row in rows if str(row.get("market_id")) == str(market_id)]
    if playbook_id:
        rows = [row for row in rows if str(row.get("playbook_id")) == str(playbook_id)]
    return rows[: max(0, int(limit))]


def create_playbook_decision(
    market_id: str,
    playbook_id: str,
    *,
    status: str = "assigned",
    note: str = "",
    created_by: str = "local",
    fit_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    playbook = get_playbook(playbook_id)
    if not playbook:
        raise ValueError(f"Unknown playbook: {playbook_id}")
    decision = {
        "decision_id": f"pb_{uuid4().hex[:12]}",
        "version": "0.4.0-playbook-decision-v1",
        "created_at": _now(),
        "updated_at": _now(),
        "created_by": created_by,
        "market_id": str(market_id),
        "playbook_id": str(playbook_id),
        "playbook_name": playbook.get("name"),
        "status": str(status or "assigned"),
        "note": str(note or ""),
        "fit_snapshot": fit_snapshot or {},
        "guardrail": "Local strategy playbook decision only. No live trading or wallet activity.",
    }
    rows = load_playbook_decisions()
    rows.append(decision)
    save_playbook_decisions(rows)
    return decision


def summarize_playbook_decisions(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load_playbook_decisions()
    statuses = Counter(str(row.get("status") or "unknown") for row in rows)
    playbooks = Counter(str(row.get("playbook_id") or "unknown") for row in rows)
    markets = {str(row.get("market_id")) for row in rows if row.get("market_id")}
    return {
        "count": len(rows),
        "market_count": len(markets),
        "status_counts": dict(sorted(statuses.items())),
        "playbook_counts": dict(playbooks.most_common(20)),
        "last_decision_at": rows[0].get("created_at") if rows else None,
        "guardrail": "Playbook decisions are local paper-workflow notes only.",
    }


def summarize_playbooks(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else list_playbooks()
    statuses = Counter(str(row.get("status") or "unknown") for row in rows)
    actions = Counter(str(row.get("recommended_action") or "unknown") for row in rows)
    return {
        "count": len(rows),
        "active_count": statuses.get("active", 0),
        "status_counts": dict(sorted(statuses.items())),
        "action_counts": dict(actions.most_common(20)),
        "guardrail": "Playbooks are deterministic local paper workflow rules. They are not investment advice.",
    }
