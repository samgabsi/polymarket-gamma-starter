from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .config import APP_VERSION, PROJECT_ROOT
from .opportunity_review import REVIEW_ONLY_NOTE as OPPORTUNITY_REVIEW_ONLY_NOTE, normalize_data_state
from .platform_safety import redact_data, redact_text, safety_flags, secret_scan

REVIEW_QUEUE_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "review_queue"
REVIEW_QUEUE_DECISIONS_PATH = REVIEW_QUEUE_RUNTIME_DIR / "decisions.jsonl"
REVIEW_QUEUE_ACTIONS_PATH = REVIEW_QUEUE_RUNTIME_DIR / "actions.jsonl"
REVIEW_QUEUE_AUDIT_PATH = REVIEW_QUEUE_RUNTIME_DIR / "audit.jsonl"

DATA_STATE_VALUES = ["live", "cached", "sample", "stale", "unavailable"]
REVIEW_QUEUE_STATES = [
    "UNREVIEWED",
    "WATCHING",
    "NEEDS_MORE_EVIDENCE",
    "NEEDS_THESIS",
    "RISK_REVIEWED",
    "PAPER_REVIEW",
    "REVIEWED",
    "REJECTED",
    "ARCHIVED",
]

REVIEW_QUEUE_ACTIONS: list[dict[str, str]] = [
    {"label": "Add to Watchlist", "action": "add_to_watchlist", "target_status": "WATCHING", "reason": "Operator moved review queue item to watchlist."},
    {"label": "Send to Paper Review", "action": "send_to_paper_review", "target_status": "PAPER_REVIEW", "reason": "Operator moved review queue item to paper review."},
    {"label": "Needs More Evidence", "action": "needs_more_evidence", "target_status": "NEEDS_MORE_EVIDENCE", "reason": "Operator marked review queue item as needing more evidence."},
    {"label": "Mark Reviewed", "action": "mark_reviewed", "target_status": "REVIEWED", "reason": "Operator marked review queue item reviewed."},
    {"label": "Reject", "action": "reject", "target_status": "REJECTED", "reason": "Operator rejected review queue item."},
    {"label": "Archive", "action": "archive", "target_status": "ARCHIVED", "reason": "Operator archived review queue item."},
]

_ACTION_TO_STATUS = {row["action"]: row["target_status"] for row in REVIEW_QUEUE_ACTIONS}
_ACTION_REASON = {row["action"]: row["reason"] for row in REVIEW_QUEUE_ACTIONS}

REVIEW_QUEUE_REVIEW_ONLY_NOTE = (
    "Review queue decisions are local operator workflow records only. They do not approve trades, place orders, "
    "cancel orders, arm live trading, disable read-only mode, or bypass backend safety gates."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _ensure_runtime_dir() -> None:
    REVIEW_QUEUE_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_runtime_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = redact_data(row)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe, sort_keys=True, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(redact_data(parsed))
        except json.JSONDecodeError:
            rows.append({"decision_id": _record_id("invalid_review_queue"), "status": "invalid_json", "secret_values_returned": False})
    return rows


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _get_market_id(item: Dict[str, Any]) -> str:
    return str(item.get("market_id") or item.get("id") or item.get("conditionId") or item.get("condition_id") or item.get("slug") or "")


def _norm(x: float) -> float:
    return x / 100.0 if abs(x) > 1 else x


def _first_number(*values: Any, default: float = 0.0) -> float:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except Exception:
            continue
    return default


def _normalize_queue_status(value: Any, default: str = "UNREVIEWED") -> str:
    text = str(value or default or "UNREVIEWED").strip().upper().replace("-", "_").replace(" ", "_")
    if text == "NEEDS_EVIDENCE":
        text = "NEEDS_MORE_EVIDENCE"
    return text if text in REVIEW_QUEUE_STATES else default


def _normalize_action(value: Any) -> str:
    text = str(value or "mark_reviewed").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "watchlist": "add_to_watchlist",
        "watching": "add_to_watchlist",
        "paper_review": "send_to_paper_review",
        "needs_evidence": "needs_more_evidence",
        "need_evidence": "needs_more_evidence",
        "reviewed": "mark_reviewed",
        "dismiss": "archive",
    }
    text = aliases.get(text, text)
    return text if text in _ACTION_TO_STATUS else "mark_reviewed"


def _latest_by_market(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        market_id = str(row.get("market_id") or row.get("target_id") or "")
        if market_id:
            latest[market_id] = row
    return latest


def _safe_data_state(value: Any, default: str = "cached") -> str:
    try:
        return normalize_data_state(value, default=default)
    except Exception:
        text = str(value or default or "cached").strip().lower().replace("-", "_").replace(" ", "_")
        if text in DATA_STATE_VALUES:
            return text
        if text in {"demo", "fixture", "fixtures", "demo_fixture"}:
            return "sample"
        return default if default in DATA_STATE_VALUES else "cached"


def _is_demo_fixture(item: dict[str, Any]) -> bool:
    text = " ".join(str(item.get(key) or "") for key in ["id", "market_id", "slug", "category", "source", "data_state"]).lower()
    return bool(item.get("demo_fixture")) or "demo_fixture" in text or text.startswith("demo_") or "sample" in text


def _row_data_state(item: dict[str, Any], default: str = "cached") -> str:
    if _is_demo_fixture(item):
        return "sample"
    explicit = item.get("data_state") or item.get("data_freshness_state")
    if explicit:
        return _safe_data_state(explicit, default=default)
    age = item.get("data_age_minutes")
    try:
        if age is not None and float(age) > 240:
            return "stale"
    except (TypeError, ValueError):
        pass
    if item.get("active") is False and not item.get("closed"):
        return "unavailable"
    return _safe_data_state(default, default="cached")


def _row_freshness(item: dict[str, Any], data_state: str) -> str:
    if data_state == "sample":
        return "sample_fixture"
    age = item.get("data_age_minutes")
    try:
        return f"{float(age):.0f}_minutes_old"
    except (TypeError, ValueError):
        return str(item.get("data_freshness") or data_state)


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
    review_status: str = "UNREVIEWED"
    previous_review_status: str = ""
    operator_notes: str = ""
    last_action: str = ""
    last_action_reason: str = ""
    audit_event_count: int = 0
    last_audit_event: dict[str, Any] | None = None
    data_state: str = "cached"
    data_freshness: str = "cached"
    source_state: str = "configured_or_cached_source"
    source_route: str = "/api/review-queue"
    source_component: str = "review_queue.workflow"
    detail_href: str = ""
    action_disabled_reason: str = ""
    review_only: bool = True
    safe_review_only: bool = True
    live_disabled: bool = True
    order_submitted: bool = False
    order_cancelled: bool = False
    trade_approved: bool = False
    live_trading_armed: bool = False
    no_live_mutation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["last_audit_event"] = data["last_audit_event"] or {}
        data["actions"] = REVIEW_QUEUE_ACTIONS if self.market_id else []
        data["operator_implication"] = "Review queue decisions persist local metadata only; they do not approve or execute trades."
        data["next_action"] = "Use a review-only action, inspect the market detail, or collect evidence/thesis context."
        return data


def build_review_queue(opportunities: List[Dict[str, Any]], thesis_scores: Dict[str, Dict[str, Any]] | None = None, limit: int = 25) -> List[Dict[str, Any]]:
    thesis_scores = thesis_scores or {}
    latest_decisions = _latest_by_market(_read_jsonl(REVIEW_QUEUE_DECISIONS_PATH))
    queue: List[ReviewItem] = []
    for opp in opportunities:
        market_id = _get_market_id(opp)
        title = str(opp.get("title") or opp.get("question") or opp.get("name") or "Untitled market")
        edge_row = opp.get("market_edge_recommendation") if isinstance(opp.get("market_edge_recommendation"), dict) else {}
        probability_model = opp.get("probability_model") if isinstance(opp.get("probability_model"), dict) else {}
        edge = _norm(
            _first_number(
                opp.get("edge"),
                opp.get("edge_percent"),
                opp.get("edge_pct"),
                opp.get("estimated_edge"),
                opp.get("model_edge"),
                edge_row.get("yes_edge_pp"),
                probability_model.get("edge"),
                probability_model.get("edge_percent"),
                default=0.0,
            )
        )
        confidence = _norm(
            _first_number(
                opp.get("confidence_score"),
                opp.get("confidence"),
                edge_row.get("confidence_score"),
                probability_model.get("confidence_score"),
                default=0.0,
            )
        )
        risk_score = _norm(_first_number(opp.get("risk_score"), opp.get("risk"), default=0.5))
        evidence_score = _norm(_first_number(opp.get("evidence_score"), opp.get("evidence"), default=0.0))
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

        latest = latest_decisions.get(market_id) or {}
        data_state = _row_data_state(opp, default=str(opp.get("data_state") or "cached"))
        queue.append(
            ReviewItem(
                market_id,
                title,
                round(priority, 4),
                stage,
                action,
                reason,
                round(edge, 4),
                round(confidence, 4),
                round(risk_score, 4),
                round(evidence_score, 4),
                round(thesis_score, 4),
                review_status=_normalize_queue_status(latest.get("new_state") or latest.get("review_status") or "UNREVIEWED"),
                previous_review_status=str(latest.get("previous_state") or ""),
                operator_notes=str(latest.get("operator_note") or ""),
                last_action=str(latest.get("action") or latest.get("decision_action") or ""),
                last_action_reason=str(latest.get("reason") or ""),
                audit_event_count=int(latest.get("audit_event_count") or len(latest.get("audit_history") or [])),
                last_audit_event=(latest.get("audit_history") or [{}])[-1] if latest.get("audit_history") else {},
                data_state=_safe_data_state(latest.get("data_state") or data_state, default=data_state),
                data_freshness=str(latest.get("data_freshness") or _row_freshness(opp, data_state)),
                source_state="demo_fixture" if data_state == "sample" else str(latest.get("source_state") or "configured_or_cached_source"),
                detail_href=f"/v3/markets/{market_id}" if market_id else "",
                action_disabled_reason="Missing market identifier; review queue actions are unavailable for this row." if not market_id else "",
            )
        )
    queue.sort(key=lambda x: x.priority, reverse=True)
    return [q.to_dict() for q in queue[:limit]]


def _status_counts(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _queue_data_state(items: list[dict[str, Any]], source_state: str, requested_demo: bool) -> str:
    if requested_demo:
        return "sample"
    explicit_states = [str(item.get("data_state") or "") for item in items if item.get("data_state")]
    if explicit_states:
        normalized = [_safe_data_state(value, default="cached") for value in explicit_states]
        if "live" in normalized:
            return "live"
        if "stale" in normalized:
            return "stale"
        if "sample" in normalized and len(set(normalized)) == 1:
            return "sample"
        if "cached" in normalized:
            return "cached"
    if source_state in {"demo_fixture", "sample_fallback"}:
        return "sample"
    if source_state in {"empty", "no_source_rows", "source_unavailable", "unavailable"}:
        return "unavailable"
    return "cached"


def build_review_queue_payload(
    opportunities: list[dict[str, Any]],
    thesis_scores: dict[str, dict[str, Any]] | None = None,
    *,
    limit: int = 25,
    requested_demo: bool = False,
    source_state: str = "configured_or_cached_source",
    source_reason: str = "Review queue rows came from configured/local opportunity ranking helpers.",
    source_route: str = "/api/review-queue",
) -> dict[str, Any]:
    items = build_review_queue(opportunities, thesis_scores or {}, limit=limit)
    data_state = _queue_data_state(items, source_state, requested_demo)
    if not items and not requested_demo:
        source_reason = "No review queue candidates were available from the selected configured source."
    if requested_demo:
        source_reason = "Demo fixtures were explicitly requested; rows are deterministic sample data for review queue workflow validation."
    for item in items:
        item["source_state"] = "demo_fixture" if requested_demo else source_state
        item["source_route"] = source_route
        item["source_component"] = "review_queue.workflow"
    return safety_flags(
        {
            "version": APP_VERSION,
            "mode": "review_queue_operator_workflow_v415",
            "limit": max(1, min(int(limit or 25), 500)),
            "count": len(items),
            "items": items,
            "review_status_counts": _status_counts(items, "review_status"),
            "stage_counts": _status_counts(items, "stage"),
            "available_actions": REVIEW_QUEUE_ACTIONS,
            "requested_demo": bool(requested_demo),
            "requested_data_mode": "demo_fixtures" if requested_demo else "configured_source",
            "resolved_data_mode": "demo_fixtures" if requested_demo else ("unavailable" if not items else "configured_source"),
            "data_state": data_state,
            "data_state_reason": source_reason,
            "source_state": "demo_fixture" if requested_demo else source_state,
            "operator_implication": "Review queue actions persist local operator decisions only; they never approve trades, place orders, cancel orders, or arm live trading.",
            "next_action": "Use the data-mode selector, inspect item stage and signal scores, then save notes or submit a review-only status action.",
            "empty_state_reason": "No review queue candidates were available from the selected source." if not items else "",
            "empty_state_next_action": "Switch to Demo fixtures to validate the workflow, or configure market data/evidence inputs before using the configured source." if not items else "",
            "review_only_note": REVIEW_QUEUE_REVIEW_ONLY_NOTE,
            "opportunity_review_note": OPPORTUNITY_REVIEW_ONLY_NOTE,
            "actions_storage_path": "runtime/review_queue/actions.jsonl",
            "decisions_storage_path": "runtime/review_queue/decisions.jsonl",
            "audit_storage_path": "runtime/review_queue/audit.jsonl",
            "runtime_records_excluded_from_release_zip": True,
            "review_only": True,
            "safe_review_only": True,
            "live_disabled": True,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "live_trading_armed": False,
            "no_live_mutation": True,
        }
    )


def build_review_queue_context(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return build_review_queue_payload(*args, **kwargs)


def build_review_queue_workflow(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return build_review_queue_payload(*args, **kwargs)


def list_review_queue_audit(limit: int = 500) -> list[dict[str, Any]]:
    rows = _read_jsonl(REVIEW_QUEUE_AUDIT_PATH)
    rows.sort(key=lambda row: str(row.get("at") or row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    return rows[: max(1, min(int(limit or 500), 5000))]


def list_review_queue_actions(market_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    rows = _read_jsonl(REVIEW_QUEUE_ACTIONS_PATH)
    rows.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    if market_id:
        rows = [row for row in rows if str(row.get("market_id") or row.get("target_id") or "") == str(market_id)]
    return rows[: max(1, min(int(limit or 100), 500))]


def record_review_queue_action(market_id: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    safe_id = redact_text(str(market_id or payload.get("market_id") or "")).strip()
    if not safe_id:
        return safety_flags({"ok": False, "error": "market_id_required", "review_only": True, "safe_review_only": True, "live_disabled": True})
    normalized_action = _normalize_action(action or payload.get("action"))
    current = _latest_by_market(_read_jsonl(REVIEW_QUEUE_DECISIONS_PATH)).get(safe_id, {})
    previous_state = _normalize_queue_status(payload.get("previous_state") or current.get("new_state") or current.get("review_status") or "UNREVIEWED")
    new_state = _normalize_queue_status(_ACTION_TO_STATUS[normalized_action])
    now = _now()
    market_title = redact_text(str(payload.get("market_title") or current.get("market_title") or ""))[:300]
    reason = redact_text(str(payload.get("reason") or _ACTION_REASON[normalized_action]))[:600]
    operator_note = redact_text(str(payload.get("operator_note") or payload.get("notes") or current.get("operator_note") or ""))[:2000]
    source_route = redact_text(str(payload.get("source_route") or payload.get("return_to") or current.get("source_route") or "/review-queue"))[:240]
    source_component = redact_text(str(payload.get("source_component") or current.get("source_component") or "review_queue.action_form"))[:160]
    data_state = _safe_data_state(payload.get("data_state") or current.get("data_state") or "cached")
    data_freshness = redact_text(str(payload.get("data_freshness") or current.get("data_freshness") or data_state))[:120]
    source_state = redact_text(str(payload.get("source_state") or current.get("source_state") or "configured_or_cached_source"))[:120]
    operator = redact_text(str(payload.get("requested_by") or payload.get("operator") or current.get("operator") or ""))[:120]
    queue_stage = redact_text(str(payload.get("queue_stage") or payload.get("stage") or current.get("queue_stage") or ""))[:120]
    queue_action = redact_text(str(payload.get("queue_action") or current.get("queue_action") or ""))[:120]
    secret_check = secret_scan({"market_title": market_title, "reason": reason, "operator_note": operator_note, "operator": operator})
    if secret_check.get("ok") is not True:
        return safety_flags({"ok": False, "error": "secret_like_content_rejected", "secret_scan": secret_check, "review_only": True, "safe_review_only": True, "live_disabled": True})
    audit_event = {
        "event_id": _record_id("rq_audit"),
        "at": now,
        "feature_area": "review_queue",
        "action_type": "operator_decision",
        "action": normalized_action,
        "target_id": safe_id,
        "target_name": market_title,
        "previous_state": previous_state,
        "new_state": new_state,
        "state_changed": previous_state != new_state,
        "reason": reason,
        "operator_note": operator_note,
        "source_route": source_route,
        "source_component": source_component,
        "data_state": data_state,
        "data_freshness": data_freshness,
        "source_state": source_state,
        "operator": operator,
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
    }
    decision = {
        "decision_id": current.get("decision_id") or _record_id("rq_decision"),
        "market_id": safe_id,
        "target_id": safe_id,
        "market_title": market_title,
        "queue_stage": queue_stage,
        "queue_action": queue_action,
        "action": normalized_action,
        "decision_action": normalized_action,
        "previous_state": previous_state,
        "new_state": new_state,
        "review_status": new_state,
        "reason": reason,
        "operator_note": operator_note,
        "source_route": source_route,
        "source_component": source_component,
        "source_state": source_state,
        "data_state": data_state,
        "data_freshness": data_freshness,
        "operator": operator,
        "created_at": current.get("created_at") or now,
        "updated_at": now,
        "audit_event_count": int(current.get("audit_event_count") or len(current.get("audit_history") or [])) + 1,
        "audit_history": list(current.get("audit_history") or [])[-20:] + [audit_event],
        "operator_implication": "Local review queue state changed only; no trade was approved or submitted.",
        "next_action": "Return to the queue, inspect market detail, or continue evidence/thesis review.",
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
        "not_financial_advice": True,
        "secret_values_returned": False,
    }
    action_record = {
        "action_record_id": _record_id("rq_action"),
        "decision_id": decision["decision_id"],
        "market_id": safe_id,
        "target_id": safe_id,
        "market_title": market_title,
        "action": normalized_action,
        "previous_state": previous_state,
        "new_state": new_state,
        "reason": reason,
        "operator_note": operator_note,
        "source_route": source_route,
        "source_component": source_component,
        "source_state": source_state,
        "data_state": data_state,
        "data_freshness": data_freshness,
        "operator": operator,
        "created_at": now,
        "updated_at": now,
        "audit_event_count": 1,
        "audit_history": [audit_event],
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
        "secret_values_returned": False,
    }
    _write_jsonl(REVIEW_QUEUE_DECISIONS_PATH, decision)
    _write_jsonl(REVIEW_QUEUE_ACTIONS_PATH, action_record)
    _write_jsonl(REVIEW_QUEUE_AUDIT_PATH, audit_event)
    return safety_flags({"ok": True, "item": decision, "action_record": action_record, "audit_event": audit_event, "review_only": True, "safe_review_only": True, "live_disabled": True})
