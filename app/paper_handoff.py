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
from .paper_briefing import build_paper_ops_briefing

HANDOFFS_PATH = DATA_DIR / "paper" / "paper_operator_handoffs.json"
HANDOFF_STATUSES = {"open", "handed_off", "accepted", "needs_followup", "archived"}
UNRESOLVED_ITEM_STATUSES = {"ready", "action_required", "blocked", "review", "watch"}


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


def _compact_item(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    links = row.get("links") if isinstance(row.get("links"), dict) else {}
    return {
        "briefing_item_id": _text(row.get("briefing_item_id")),
        "section": _text(row.get("section")),
        "status": _text(row.get("status")),
        "priority": _safe_int(row.get("priority")),
        "title": _text(row.get("title")),
        "recommended_action": _text(row.get("recommended_action")),
        "detail": _text(row.get("detail")),
        "market_id": _text(row.get("market_id")),
        "ticket_id": _text(row.get("ticket_id")),
        "question": _text(row.get("question") or row.get("title")),
        "metrics": metrics,
        "links": links,
    }


def _next_focus(summary: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    focus: list[str] = []
    if _safe_int(summary.get("blocked")):
        focus.append("Clear blocked paper-workflow items before any new simulated execution.")
    if _safe_int(summary.get("action_required")):
        focus.append("Review action-required handoff items and record acknowledgement/checkpoint notes.")
    if _safe_int(summary.get("ready")):
        focus.append("Confirm ready entry/exit items against preflight, approval, and risk-budget state.")
    if _safe_int(summary.get("watch")):
        focus.append("Check watched portfolio or process-health items during the next operator pass.")
    if not focus and items:
        focus.append("Review open paper workflow context and preserve any operator notes.")
    if not focus:
        focus.append("No unresolved paper handoff items were found in the current briefing filters.")
    return focus[:4]


def load_operator_handoffs() -> list[dict[str, Any]]:
    rows = _read_json(HANDOFFS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_operator_handoffs(rows: list[dict[str, Any]]) -> None:
    _write_json(HANDOFFS_PATH, rows)


def list_operator_handoffs(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_operator_handoffs()))
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [
            row
            for row in rows
            if any(_text(item.get("market_id")) == wanted for item in row.get("handoff_items") or [])
            or _text(row.get("market_filter")) == wanted
        ]
    return rows[: max(0, int(limit))]


def get_operator_handoff(handoff_id: str) -> dict[str, Any] | None:
    wanted = _text(handoff_id)
    for row in load_operator_handoffs():
        if _text(row.get("handoff_id")) == wanted:
            return row
    return None


def build_operator_handoff_packet(
    *,
    limit: int = 25,
    section: str | None = None,
    item_status: str | None = None,
    market_id: str | None = None,
    handoff_status: str = "open",
    outgoing_operator: str = "local",
    incoming_operator: str = "",
    note: str = "",
    handoff_id: str | None = None,
    created_at: str | None = None,
    briefing_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    limit = max(1, int(limit))
    briefing = briefing_snapshot or build_paper_ops_briefing(
        limit=max(limit, 100),
        section=section,
        status=item_status,
        market_id=market_id,
    )
    summary = briefing.get("summary", {}) if isinstance(briefing, dict) else {}
    all_items = [_compact_item(row) for row in (briefing.get("items") or [])]
    unresolved_items = [row for row in all_items if row.get("status") in UNRESOLVED_ITEM_STATUSES]
    status_counts = Counter(_text(row.get("status") or "unknown") for row in all_items)
    section_counts = Counter(_text(row.get("section") or "unknown") for row in all_items)
    top_items = unresolved_items[:limit]
    record_status = handoff_status if handoff_status in HANDOFF_STATUSES else "open"
    return {
        "handoff_id": handoff_id or f"poh_{uuid4().hex[:12]}",
        "version": "0.4.8-paper-operator-handoff-v1",
        "mode": "paper_operator_handoff_v048",
        "created_at": created_at or _now(),
        "outgoing_operator": _text(outgoing_operator, "local"),
        "incoming_operator": _text(incoming_operator),
        "status": record_status,
        "note": _text(note),
        "section_filter": _text(section or "all"),
        "item_status_filter": _text(item_status or "all"),
        "market_filter": _text(market_id),
        "item_count_snapshot": _safe_int(summary.get("count"), len(all_items)),
        "unresolved_count_snapshot": len(unresolved_items),
        "blocked_snapshot": _safe_int(summary.get("blocked"), status_counts.get("blocked", 0)),
        "action_required_snapshot": _safe_int(summary.get("action_required"), status_counts.get("action_required", 0)),
        "ready_snapshot": _safe_int(summary.get("ready"), status_counts.get("ready", 0)),
        "review_snapshot": _safe_int(summary.get("review"), status_counts.get("review", 0)),
        "watch_snapshot": _safe_int(summary.get("watch"), status_counts.get("watch", 0)),
        "top_priority_snapshot": _safe_int(summary.get("top_priority")),
        "ready_entry_stake_snapshot": round(_safe_float(summary.get("ready_entry_stake")), 4),
        "market_count_snapshot": _safe_int(summary.get("market_count")),
        "by_status_snapshot": dict(sorted(status_counts.items())),
        "by_section_snapshot": dict(sorted(section_counts.items())),
        "briefing_summary_snapshot": summary,
        "next_operator_focus": _next_focus(summary, unresolved_items),
        "handoff_items": top_items,
        "recent_checkpoints": (briefing.get("recent_checkpoints") or [])[:5],
        "guardrail": "Local paper-operator handoff packet only. It preserves workflow context and never places live orders, connects a wallet, signs messages, or provides investment advice.",
    }


def record_operator_handoff(
    *,
    status: str = "open",
    outgoing_operator: str = "local",
    incoming_operator: str = "",
    note: str = "",
    limit: int = 25,
    section: str | None = None,
    item_status: str | None = None,
    market_id: str | None = None,
    briefing_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = build_operator_handoff_packet(
        limit=limit,
        section=section,
        item_status=item_status,
        market_id=market_id,
        handoff_status=status,
        outgoing_operator=outgoing_operator,
        incoming_operator=incoming_operator,
        note=note,
        briefing_snapshot=briefing_snapshot,
    )
    rows = load_operator_handoffs()
    rows.append(record)
    save_operator_handoffs(rows)
    return record


def summarize_operator_handoffs(records: list[dict[str, Any]], current: dict[str, Any]) -> dict[str, Any]:
    statuses = Counter(_text(row.get("status") or "unknown") for row in records)
    return {
        "saved_count": len(records),
        "open": statuses.get("open", 0),
        "handed_off": statuses.get("handed_off", 0),
        "accepted": statuses.get("accepted", 0),
        "needs_followup": statuses.get("needs_followup", 0),
        "archived": statuses.get("archived", 0),
        "latest_handoff_at": records[0].get("created_at") if records else "",
        "current_item_count": current.get("item_count_snapshot", 0),
        "current_unresolved": current.get("unresolved_count_snapshot", 0),
        "current_ready": current.get("ready_snapshot", 0),
        "current_action_required": current.get("action_required_snapshot", 0),
        "current_blocked": current.get("blocked_snapshot", 0),
        "current_review": current.get("review_snapshot", 0),
        "current_watch": current.get("watch_snapshot", 0),
        "current_top_priority": current.get("top_priority_snapshot", 0),
        "current_ready_entry_stake": current.get("ready_entry_stake_snapshot", 0),
        "guardrail": "Paper handoff summaries are local simulated workflow records only, not trading recommendations or execution status.",
    }


def build_operator_handoff_board(
    *,
    limit: int = 25,
    section: str | None = None,
    item_status: str | None = None,
    market_id: str | None = None,
    handoff_status: str | None = None,
) -> dict[str, Any]:
    current = build_operator_handoff_packet(
        limit=limit,
        section=section,
        item_status=item_status,
        market_id=market_id,
        handoff_status="open",
        outgoing_operator="preview",
        incoming_operator="",
        note="Current unsaved handoff preview",
    )
    records = list_operator_handoffs(limit=limit, status=handoff_status, market_id=market_id)
    return {
        "version": "0.4.8-paper-operator-handoff-v1",
        "mode": "paper_operator_handoffs_v048",
        "generated_at": _now(),
        "summary": summarize_operator_handoffs(records, current),
        "current": current,
        "items": records,
        "guardrail": "Paper operator handoffs are local workflow context records only. They do not place live orders, connect a wallet, sign messages, or provide investment advice.",
    }


def _reconciliation_action(status: str, *, handoff_status: str) -> str:
    if status in {"still_open", "changed_open"}:
        return "review_current_briefing_before_closing_handoff"
    if status == "no_longer_unresolved":
        return "verify_cleared_item_before_archiving_handoff"
    if status == "not_visible":
        return "confirm_item_resolution_or_filter_change"
    if handoff_status == "needs_followup":
        return "review_saved_followup_note"
    return "no_action_required_from_reconciliation"


def _reconcile_item(saved: dict[str, Any], current_by_id: dict[str, dict[str, Any]], *, handoff_status: str) -> dict[str, Any]:
    item_id = _text(saved.get("briefing_item_id"))
    current = current_by_id.get(item_id)
    saved_status = _text(saved.get("status"))
    if not current:
        reconciliation_status = "not_visible"
        current_status = ""
        detail = "Saved handoff item is not visible in the current briefing. Confirm whether it was resolved, completed, or filtered out before archiving."
    else:
        current_status = _text(current.get("status"))
        if current_status in UNRESOLVED_ITEM_STATUSES and current_status == saved_status:
            reconciliation_status = "still_open"
            detail = "Saved handoff item is still present with the same unresolved status."
        elif current_status in UNRESOLVED_ITEM_STATUSES:
            reconciliation_status = "changed_open"
            detail = f"Saved handoff item is still present but changed from {saved_status or 'unknown'} to {current_status}."
        else:
            reconciliation_status = "no_longer_unresolved"
            detail = f"Saved handoff item is currently visible as {current_status or 'unknown'}, not as an unresolved handoff item."
    return {
        "briefing_item_id": item_id,
        "section": _text(saved.get("section")),
        "market_id": _text(saved.get("market_id")),
        "ticket_id": _text(saved.get("ticket_id")),
        "question": _text(saved.get("question") or saved.get("title")),
        "title": _text(saved.get("title") or item_id),
        "saved_status": saved_status,
        "current_status": current_status,
        "saved_priority": _safe_int(saved.get("priority")),
        "current_priority": _safe_int(current.get("priority")) if current else 0,
        "reconciliation_status": reconciliation_status,
        "recommended_action": _reconciliation_action(reconciliation_status, handoff_status=handoff_status),
        "detail": detail,
        "saved_item": saved,
        "current_item": current or {},
    }


def summarize_handoff_reconciliation(items: list[dict[str, Any]], handoff: dict[str, Any]) -> dict[str, Any]:
    statuses = Counter(_text(row.get("reconciliation_status") or "unknown") for row in items)
    followup_required = statuses.get("still_open", 0) + statuses.get("changed_open", 0)
    saved_count = len(items)
    if not saved_count:
        reconciliation_state = "no_saved_items"
        action = "no_handoff_items_to_reconcile"
    elif followup_required:
        reconciliation_state = "followup_required"
        action = "review_persistent_handoff_items"
    elif statuses.get("not_visible", 0):
        reconciliation_state = "verify_clearance"
        action = "verify_items_cleared_or_filtered_before_archiving"
    else:
        reconciliation_state = "cleared_review"
        action = "confirm_cleared_items_then_archive_or_accept_handoff"
    return {
        "handoff_id": handoff.get("handoff_id"),
        "handoff_status": handoff.get("status"),
        "created_at": handoff.get("created_at"),
        "saved_item_count": saved_count,
        "followup_required": followup_required,
        "still_open": statuses.get("still_open", 0),
        "changed_open": statuses.get("changed_open", 0),
        "not_visible": statuses.get("not_visible", 0),
        "no_longer_unresolved": statuses.get("no_longer_unresolved", 0),
        "reconciliation_state": reconciliation_state,
        "recommended_action": action,
        "guardrail": "Handoff reconciliation is a local comparison report only. It does not mutate handoffs, tickets, approvals, positions, or execution state.",
    }


def reconcile_operator_handoff(
    handoff: dict[str, Any] | str,
    *,
    current_briefing: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    record = get_operator_handoff(handoff) if isinstance(handoff, str) else handoff
    if not record:
        return None
    market_filter = _text(record.get("market_filter"))
    current_briefing = current_briefing or build_paper_ops_briefing(limit=1000, market_id=market_filter or None)
    current_items = [_compact_item(row) for row in (current_briefing.get("items") or [])]
    current_by_id = {_text(row.get("briefing_item_id")): row for row in current_items if row.get("briefing_item_id")}
    saved_items = [_compact_item(row) for row in (record.get("handoff_items") or [])]
    items = [_reconcile_item(row, current_by_id, handoff_status=_text(record.get("status"))) for row in saved_items]
    return {
        "version": "0.4.9-paper-handoff-reconciliation-v1",
        "mode": "paper_handoff_reconciliation_v049",
        "generated_at": _now(),
        "handoff": record,
        "summary": summarize_handoff_reconciliation(items, record),
        "items": items,
        "current_briefing_summary": current_briefing.get("summary", {}),
        "guardrail": "Paper handoff reconciliation is a local read-only comparison report. It never places live orders, connects a wallet, signs messages, changes approvals, or marks work complete.",
    }


def build_operator_handoff_reconciliation_board(
    *,
    limit: int = 25,
    status: str | None = None,
    market_id: str | None = None,
) -> dict[str, Any]:
    records = list_operator_handoffs(limit=limit, status=status, market_id=market_id)
    current_briefing = build_paper_ops_briefing(limit=1000, market_id=market_id)
    reconciliations = [reconcile_operator_handoff(record, current_briefing=current_briefing) for record in records]
    details = [row for row in reconciliations if row]
    summary_rows = [row.get("summary", {}) for row in details]
    return {
        "version": "0.4.9-paper-handoff-reconciliation-v1",
        "mode": "paper_handoff_reconciliation_board_v049",
        "generated_at": _now(),
        "summary": summarize_handoff_reconciliation_board(summary_rows),
        "items": summary_rows,
        "details": details,
        "guardrail": "Paper handoff reconciliation is a local read-only comparison report. It does not mutate saved handoffs or any paper workflow records.",
    }


def summarize_handoff_reconciliation_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    states = Counter(_text(row.get("reconciliation_state") or "unknown") for row in rows)
    return {
        "count": len(rows),
        "followup_required_count": states.get("followup_required", 0),
        "verify_clearance_count": states.get("verify_clearance", 0),
        "cleared_review_count": states.get("cleared_review", 0),
        "no_saved_items_count": states.get("no_saved_items", 0),
        "saved_item_count": sum(_safe_int(row.get("saved_item_count")) for row in rows),
        "still_open": sum(_safe_int(row.get("still_open")) for row in rows),
        "changed_open": sum(_safe_int(row.get("changed_open")) for row in rows),
        "not_visible": sum(_safe_int(row.get("not_visible")) for row in rows),
        "no_longer_unresolved": sum(_safe_int(row.get("no_longer_unresolved")) for row in rows),
        "guardrail": "Reconciliation counts are local handoff comparison results only, not execution instructions.",
    }


def handoff_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_operator_handoff_board(limit=25)
    summary = board.get("summary", {}) if isinstance(board, dict) else {}
    alerts: list[dict[str, Any]] = []
    unresolved = _safe_int(summary.get("current_unresolved"))
    blocked = _safe_int(summary.get("current_blocked"))
    action_required = _safe_int(summary.get("current_action_required"))
    if unresolved:
        level = "warning" if blocked or action_required else "info"
        alerts.append(
            {
                "level": level,
                "kind": "paper_operator_handoff_open_items",
                "title": "Paper operator handoff has unresolved items",
                "detail": f"{unresolved} unresolved item(s): blocked={blocked}, action_required={action_required}, ready={summary.get('current_ready', 0)}.",
                "market_id": "",
                "question": "Paper operator handoff",
                "source": "paper_operator_handoff_v048",
                "link": "/paper-handoffs",
            }
        )
    if _safe_int(summary.get("needs_followup")):
        alerts.append(
            {
                "level": "warning",
                "kind": "paper_operator_handoff_followup",
                "title": "Saved handoff needs follow-up",
                "detail": f"{summary.get('needs_followup')} saved handoff record(s) are marked needs_followup.",
                "market_id": "",
                "question": "Paper operator handoff",
                "source": "paper_operator_handoff_v048",
                "link": "/paper-handoffs?record_status=needs_followup",
            }
        )
    return alerts[:10]


def handoff_reconciliation_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "handoff_id",
        "created_at",
        "handoff_status",
        "reconciliation_state",
        "recommended_action",
        "saved_item_count",
        "followup_required",
        "still_open",
        "changed_open",
        "not_visible",
        "no_longer_unresolved",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def handoffs_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "handoff_id",
        "created_at",
        "status",
        "outgoing_operator",
        "incoming_operator",
        "section_filter",
        "item_status_filter",
        "market_filter",
        "item_count_snapshot",
        "unresolved_count_snapshot",
        "blocked_snapshot",
        "action_required_snapshot",
        "ready_snapshot",
        "review_snapshot",
        "watch_snapshot",
        "top_priority_snapshot",
        "ready_entry_stake_snapshot",
        "market_count_snapshot",
        "note",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()
