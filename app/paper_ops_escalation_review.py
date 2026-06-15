from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .paper_ops_aging import build_paper_ops_aging
from .paper_ops_escalations import OPEN_STATUSES, get_ops_escalation, list_ops_escalations

ACTIONABLE_AGING_SEVERITIES = {"critical", "stale", "followup", "repeat"}
CLOSED_ESCALATION_STATUSES = {"resolved", "dismissed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _current_aging_index(*, market_id: str | None = None) -> dict[str, dict[str, Any]]:
    report = build_paper_ops_aging(limit=10000, market_id=market_id)
    index: dict[str, dict[str, Any]] = {}
    for item in report.get("items") or []:
        item_id = _text(item.get("aging_item_id"))
        if item_id:
            index[item_id] = item
    return index


def _review_state(escalation: dict[str, Any], current: dict[str, Any] | None) -> str:
    status = _text(escalation.get("status"))
    current_severity = _text((current or {}).get("severity"))
    current_is_actionable = bool(current) and current_severity in ACTIONABLE_AGING_SEVERITIES

    if status in OPEN_STATUSES:
        if current_is_actionable:
            return "active_followup"
        if current:
            return "deescalation_candidate"
        return "verify_resolution"

    if status in CLOSED_ESCALATION_STATUSES and current_is_actionable:
        return "closed_but_reappeared"
    if status in CLOSED_ESCALATION_STATUSES:
        return "closed_record"
    if current_is_actionable:
        return "active_followup"
    if current:
        return "deescalation_candidate"
    return "verify_resolution"


def _recommended_action(state: str, escalation: dict[str, Any], current: dict[str, Any] | None) -> str:
    if state == "active_followup":
        return _text((current or {}).get("recommended_action") or escalation.get("recommended_action_at_escalation") or "continue_operator_followup")
    if state == "deescalation_candidate":
        return "verify_softened_aging_item_then_lower_severity_or_resolve"
    if state == "verify_resolution":
        return "verify_item_cleared_or_filtered_before_marking_resolved"
    if state == "closed_but_reappeared":
        return "review_closed_escalation_against_reappeared_aging_item"
    if state == "closed_record":
        return "no_action_required_unless_operator_reopens"
    return "review_escalation_state"


def review_ops_escalation(
    escalation: dict[str, Any] | str,
    *,
    current_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    record = get_ops_escalation(escalation) if isinstance(escalation, str) else escalation
    if not record:
        return None
    if current_index is None:
        current_index = _current_aging_index(market_id=_text(record.get("market_id")) or None)
    aging_item_id = _text(record.get("aging_item_id"))
    current = current_index.get(aging_item_id)
    state = _review_state(record, current)
    current_status = _text((current or {}).get("status"))
    current_severity = _text((current or {}).get("severity"))
    saved_status = _text(record.get("status"))
    saved_severity = _text(record.get("severity"))
    source_severity = _text(record.get("source_severity"))
    source_status = _text(record.get("source_status"))
    severity_changed = bool(current) and current_severity != source_severity
    status_changed = bool(current) and current_status != source_status
    return {
        "version": "0.5.2-paper-ops-escalation-review-v1",
        "mode": "paper_ops_escalation_review_v052",
        "generated_at": _now(),
        "escalation_id": _text(record.get("escalation_id")),
        "aging_item_id": aging_item_id,
        "created_at": _text(record.get("created_at")),
        "updated_at": _text(record.get("updated_at")),
        "owner": _text(record.get("owner") or "unassigned"),
        "market_id": _text(record.get("market_id")),
        "ticket_id": _text(record.get("ticket_id")),
        "section": _text(record.get("section")),
        "title": _text(record.get("title") or record.get("question") or aging_item_id),
        "question": _text(record.get("question") or record.get("title")),
        "escalation_status": saved_status,
        "escalation_severity": saved_severity,
        "source_status_at_escalation": source_status,
        "source_severity_at_escalation": source_severity,
        "current_status": current_status,
        "current_severity": current_severity,
        "current_age_hours": current.get("age_hours") if current else None,
        "current_handoff_count": _safe_int((current or {}).get("handoff_count")),
        "review_state": state,
        "current_item_visible": bool(current),
        "severity_changed": severity_changed,
        "status_changed": status_changed,
        "recommended_action": _recommended_action(state, record, current),
        "note": _text(record.get("note")),
        "escalation": record,
        "current_aging_item": current or {},
        "guardrail": "Escalation review is a read-only local comparison. It does not change escalation records, approvals, tickets, paper trades, settlements, or live trading state.",
    }


def summarize_escalation_review(rows: list[dict[str, Any]]) -> dict[str, Any]:
    states = Counter(_text(row.get("review_state") or "unknown") for row in rows)
    owners = Counter(_text(row.get("owner") or "unassigned") for row in rows)
    severities = Counter(_text(row.get("escalation_severity") or "unknown") for row in rows)
    markets = {_text(row.get("market_id")) for row in rows if row.get("market_id")}
    open_like = sum(1 for row in rows if _text(row.get("escalation_status")) in OPEN_STATUSES)
    review_required = states.get("active_followup", 0) + states.get("verify_resolution", 0) + states.get("closed_but_reappeared", 0)
    return {
        "count": len(rows),
        "open_like": open_like,
        "review_required": review_required,
        "active_followup": states.get("active_followup", 0),
        "verify_resolution": states.get("verify_resolution", 0),
        "deescalation_candidate": states.get("deescalation_candidate", 0),
        "closed_but_reappeared": states.get("closed_but_reappeared", 0),
        "closed_record": states.get("closed_record", 0),
        "market_count": len(markets),
        "by_state": dict(sorted(states.items())),
        "by_owner": dict(sorted(owners.items())),
        "by_escalation_severity": dict(sorted(severities.items())),
        "guardrail": "Escalation review counts are local workflow hygiene diagnostics only, not execution instructions or trading advice.",
    }


def build_ops_escalation_review(
    *,
    limit: int = 100,
    status: str | None = None,
    severity: str | None = None,
    market_id: str | None = None,
    owner: str | None = None,
    review_state: str | None = None,
) -> dict[str, Any]:
    records = list_ops_escalations(limit=limit, status=status, severity=severity, market_id=market_id, owner=owner)
    current_index = _current_aging_index(market_id=market_id)
    items = [row for row in (review_ops_escalation(record, current_index=current_index) for record in records) if row]
    if review_state:
        wanted = _text(review_state)
        items = [row for row in items if _text(row.get("review_state")) == wanted]
    items.sort(
        key=lambda row: (
            {"closed_but_reappeared": 5, "active_followup": 4, "verify_resolution": 3, "deescalation_candidate": 2, "closed_record": 1}.get(_text(row.get("review_state")), 0),
            _safe_float(row.get("current_age_hours")),
            _text(row.get("updated_at")),
        ),
        reverse=True,
    )
    return {
        "version": "0.5.2-paper-ops-escalation-review-v1",
        "mode": "paper_ops_escalation_review_board_v052",
        "generated_at": _now(),
        "summary": summarize_escalation_review(items),
        "items": items[: max(0, int(limit))],
        "filters": {"status": status or "", "severity": severity or "", "market_id": market_id or "", "owner": owner or "", "review_state": review_state or ""},
        "current_aging_count": len(current_index),
        "guardrail": "Paper ops escalation review is read-only. It reconciles saved escalation records against current aging diagnostics and never changes paper or live trading state.",
    }


def ops_escalation_review_alerts(report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    report = report or build_ops_escalation_review(limit=25)
    alerts: list[dict[str, Any]] = []
    for row in report.get("items") or []:
        state = _text(row.get("review_state"))
        if state not in {"closed_but_reappeared", "active_followup", "verify_resolution"}:
            continue
        level = "warning" if state in {"closed_but_reappeared", "active_followup"} else "info"
        alerts.append(
            {
                "level": level,
                "kind": f"paper_ops_escalation_review_{state}",
                "title": _text(row.get("title") or "Paper ops escalation review"),
                "detail": f"{state}: {row.get('recommended_action')}",
                "market_id": row.get("market_id"),
                "question": row.get("question"),
                "source": "paper_ops_escalation_review_v052",
                "link": "/paper-ops-escalation-review",
            }
        )
    return alerts[:25]


def ops_escalation_review_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "escalation_id",
        "aging_item_id",
        "review_state",
        "recommended_action",
        "escalation_status",
        "escalation_severity",
        "owner",
        "section",
        "market_id",
        "ticket_id",
        "title",
        "source_status_at_escalation",
        "source_severity_at_escalation",
        "current_status",
        "current_severity",
        "current_age_hours",
        "current_handoff_count",
        "current_item_visible",
        "status_changed",
        "severity_changed",
        "created_at",
        "updated_at",
        "note",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()
