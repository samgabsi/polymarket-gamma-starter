from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR
from .paper_ops_closeout import build_paper_ops_closeout

SIGNOFFS_PATH = DATA_DIR / "paper" / "paper_ops_closeout_signoffs.json"
SIGNOFF_STATUSES = {"completed", "handed_off", "needs_followup", "blocked", "skipped"}
FOLLOWUP_SIGNOFF_STATUSES = {"handed_off", "needs_followup", "blocked"}


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


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _compact_closeout_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": _text(row.get("source")),
        "source_id": _text(row.get("source_id")),
        "title": _text(row.get("title") or row.get("source_id")),
        "status": _text(row.get("status")),
        "severity": _text(row.get("severity")),
        "priority": _safe_int(row.get("priority")),
        "recommended_action": _text(row.get("recommended_action")),
        "detail": _text(row.get("detail")),
        "market_id": _text(row.get("market_id")),
        "ticket_id": _text(row.get("ticket_id")),
        "owner": _text(row.get("owner")),
        "handoff_required": bool(row.get("handoff_required")),
        "closure_gate": _text(row.get("closure_gate")),
        "link": _text(row.get("link")),
    }


def _recommended_signoff_status(summary: dict[str, Any]) -> str:
    closeout_status = _text(summary.get("closeout_status"))
    if closeout_status == "clear":
        return "completed"
    if closeout_status == "blocked":
        return "blocked"
    if _safe_int(summary.get("handoff_required")):
        return "handed_off"
    return "needs_followup"


def _closure_gate(status: str, summary: dict[str, Any]) -> str:
    closeout_status = _text(summary.get("closeout_status"))
    handoff_count = _safe_int(summary.get("handoff_required"))
    if status == "skipped":
        return "operator_skipped_closeout"
    if status == "blocked" or closeout_status == "blocked":
        return "blocked_not_closeable_without_explicit_followup"
    if status == "handed_off" or handoff_count:
        return "handoff_record_expected_for_unresolved_items"
    if status == "needs_followup":
        return "needs_followup_before_next_operator_pass"
    return "clear_to_closeout"


def load_ops_closeout_signoffs() -> list[dict[str, Any]]:
    rows = _read_json(SIGNOFFS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_ops_closeout_signoffs(rows: list[dict[str, Any]]) -> None:
    _write_json(SIGNOFFS_PATH, rows)


def list_ops_closeout_signoffs(
    *,
    limit: int = 100,
    status: str | None = None,
    operator: str | None = None,
    market_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_ops_closeout_signoffs()))
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if operator:
        wanted = _text(operator)
        rows = [row for row in rows if _text(row.get("operator")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_filter")) == wanted or any(_text(item.get("market_id")) == wanted for item in row.get("top_closeout_items") or [])]
    return rows[: max(0, int(limit))]


def get_ops_closeout_signoff(signoff_id: str) -> dict[str, Any] | None:
    wanted = _text(signoff_id)
    for row in load_ops_closeout_signoffs():
        if _text(row.get("signoff_id")) == wanted:
            return row
    return None


def build_ops_closeout_signoff_packet(
    *,
    status: str = "",
    operator: str = "local",
    note: str = "",
    limit: int = 25,
    source: str | None = None,
    item_status: str | None = None,
    market_id: str | None = None,
    handoff_required: bool | None = None,
    closeout_report: dict[str, Any] | None = None,
    signoff_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    limit = max(1, int(limit))
    report = closeout_report or build_paper_ops_closeout(
        limit=max(limit, 100),
        source=source,
        status=item_status,
        market_id=market_id,
        handoff_required=handoff_required,
    )
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    items = [_compact_closeout_item(row) for row in (report.get("items") or [])]
    handoff_items = [row for row in items if row.get("handoff_required")]
    normalized_status = status if status in SIGNOFF_STATUSES else _recommended_signoff_status(summary)
    return {
        "signoff_id": signoff_id or f"pocs_{uuid4().hex[:12]}",
        "version": "0.5.11-paper-ops-closeout-signoff-v1",
        "mode": "paper_ops_closeout_signoff_v054",
        "created_at": created_at or _now(),
        "operator": _text(operator, "local"),
        "status": normalized_status,
        "note": _text(note),
        "source_filter": _text(source or "all"),
        "item_status_filter": _text(item_status or "all"),
        "market_filter": _text(market_id),
        "handoff_required_filter": "all" if handoff_required is None else bool(handoff_required),
        "closeout_status_snapshot": _text(summary.get("closeout_status")),
        "closeout_message_snapshot": _text(summary.get("closeout_message")),
        "closure_gate": _closure_gate(normalized_status, summary),
        "item_count_snapshot": _safe_int(summary.get("count"), len(items)),
        "handoff_required_count_snapshot": _safe_int(summary.get("handoff_required"), len(handoff_items)),
        "briefing_blocked_snapshot": _safe_int(summary.get("briefing_blocked")),
        "briefing_action_required_snapshot": _safe_int(summary.get("briefing_action_required")),
        "aging_critical_snapshot": _safe_int(summary.get("aging_critical")),
        "aging_stale_snapshot": _safe_int(summary.get("aging_stale")),
        "handoff_reconciliation_followup_snapshot": _safe_int(summary.get("handoff_reconciliation_followup")),
        "open_escalations_snapshot": _safe_int(summary.get("open_escalations")),
        "escalation_candidates_snapshot": _safe_int(summary.get("escalation_candidates")),
        "escalation_review_required_snapshot": _safe_int(summary.get("escalation_review_required")),
        "closed_but_reappeared_snapshot": _safe_int(summary.get("closed_but_reappeared")),
        "by_source_snapshot": dict(summary.get("by_source") or {}),
        "by_status_snapshot": dict(summary.get("by_status") or {}),
        "by_severity_snapshot": dict(summary.get("by_severity") or {}),
        "component_summaries_snapshot": dict(report.get("component_summaries") or {}),
        "top_closeout_items": items[:limit],
        "top_handoff_required_items": handoff_items[:limit],
        "guardrail": "Local paper-ops closeout signoff only. It records an operator-reviewed snapshot and never closes escalations, creates handoffs, approves tickets, executes paper trades, connects wallets, signs messages, or provides investment advice.",
    }


def record_ops_closeout_signoff(
    *,
    status: str = "",
    operator: str = "local",
    note: str = "",
    limit: int = 25,
    source: str | None = None,
    item_status: str | None = None,
    market_id: str | None = None,
    handoff_required: bool | None = None,
    closeout_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = build_ops_closeout_signoff_packet(
        status=status,
        operator=operator,
        note=note,
        limit=limit,
        source=source,
        item_status=item_status,
        market_id=market_id,
        handoff_required=handoff_required,
        closeout_report=closeout_report,
    )
    rows = load_ops_closeout_signoffs()
    rows.append(record)
    save_ops_closeout_signoffs(rows)
    return record


def summarize_ops_closeout_signoffs(records: list[dict[str, Any]], current_closeout: dict[str, Any]) -> dict[str, Any]:
    statuses = Counter(_text(row.get("status") or "unknown") for row in records)
    operators = Counter(_text(row.get("operator") or "unknown") for row in records)
    latest = records[0] if records else {}
    current_summary = current_closeout.get("summary", {}) if isinstance(current_closeout, dict) else {}
    return {
        "saved_count": len(records),
        "completed": statuses.get("completed", 0),
        "handed_off": statuses.get("handed_off", 0),
        "needs_followup": statuses.get("needs_followup", 0),
        "blocked": statuses.get("blocked", 0),
        "skipped": statuses.get("skipped", 0),
        "followup_signoffs": sum(statuses.get(status, 0) for status in FOLLOWUP_SIGNOFF_STATUSES),
        "by_status": dict(sorted(statuses.items())),
        "by_operator": dict(sorted(operators.items())),
        "latest_signoff_id": latest.get("signoff_id", ""),
        "latest_signoff_at": latest.get("created_at", ""),
        "latest_status": latest.get("status", ""),
        "latest_operator": latest.get("operator", ""),
        "latest_closeout_status": latest.get("closeout_status_snapshot", ""),
        "current_closeout_status": current_summary.get("closeout_status", ""),
        "current_handoff_required": _safe_int(current_summary.get("handoff_required")),
        "current_rows": _safe_int(current_summary.get("count")),
        "guardrail": "Closeout signoff summaries describe local operator records only. They do not represent live orders, exchange state, or investment advice.",
    }


def build_ops_closeout_signoff_board(
    *,
    limit: int = 100,
    status: str | None = None,
    operator: str | None = None,
    market_id: str | None = None,
    closeout_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = closeout_report or build_paper_ops_closeout(limit=max(25, min(1000, int(limit))), market_id=market_id)
    records = list_ops_closeout_signoffs(limit=limit, status=status, operator=operator, market_id=market_id)
    preview = build_ops_closeout_signoff_packet(limit=25, market_id=market_id, closeout_report=current)
    return {
        "version": "0.5.11-paper-ops-closeout-signoff-v1",
        "mode": "paper_ops_closeout_signoff_board_v054",
        "generated_at": _now(),
        "summary": summarize_ops_closeout_signoffs(records, current),
        "items": records,
        "current_closeout_summary": current.get("summary", {}),
        "current_signoff_preview": preview,
        "filters": {"status": status or "", "operator": operator or "", "market_id": market_id or ""},
        "guardrail": "Paper ops closeout signoffs are explicit local operator records. Listing or previewing them never mutates workflow state or execution controls.",
    }


def ops_closeout_signoff_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_ops_closeout_signoff_board(limit=25)
    summary = board.get("summary", {}) if isinstance(board, dict) else {}
    latest_status = _text(summary.get("latest_status"))
    alerts: list[dict[str, Any]] = []
    if latest_status in FOLLOWUP_SIGNOFF_STATUSES:
        alerts.append(
            {
                "level": "warning" if latest_status == "blocked" else "info",
                "kind": f"paper_ops_closeout_signoff_{latest_status}",
                "title": "Latest closeout signoff still needs follow-up",
                "detail": f"Latest signoff {summary.get('latest_signoff_id') or ''} is {latest_status}; verify handoff/follow-up before the next operator pass.",
                "market_id": None,
                "question": None,
                "source": "paper_ops_closeout_signoff_v054",
                "link": "/paper-ops-closeout-signoffs",
            }
        )
    current_status = _text(summary.get("current_closeout_status"))
    if current_status in {"blocked", "attention"} and not summary.get("latest_signoff_id"):
        alerts.append(
            {
                "level": "warning" if current_status == "blocked" else "info",
                "kind": f"paper_ops_closeout_signoff_missing_{current_status}",
                "title": "Closeout signoff has not been recorded",
                "detail": "Current closeout has unresolved work and no saved closeout signoff yet.",
                "market_id": None,
                "question": None,
                "source": "paper_ops_closeout_signoff_v054",
                "link": "/paper-ops-closeout-signoffs",
            }
        )
    return alerts[:10]


def ops_closeout_signoffs_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "signoff_id",
        "created_at",
        "operator",
        "status",
        "closeout_status_snapshot",
        "closure_gate",
        "item_count_snapshot",
        "handoff_required_count_snapshot",
        "briefing_blocked_snapshot",
        "briefing_action_required_snapshot",
        "aging_critical_snapshot",
        "aging_stale_snapshot",
        "handoff_reconciliation_followup_snapshot",
        "open_escalations_snapshot",
        "escalation_review_required_snapshot",
        "closed_but_reappeared_snapshot",
        "market_filter",
        "source_filter",
        "item_status_filter",
        "note",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()
