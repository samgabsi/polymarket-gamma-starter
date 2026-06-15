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
from .paper_preflight import build_ticket_preflight
from .trade_tickets import get_trade_ticket, list_trade_tickets, update_trade_ticket

APPROVALS_PATH = DATA_DIR / "paper" / "execution_approvals.json"
APPROVAL_STATUSES = {"approved", "blocked", "rejected", "executed"}


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


def _approval_record(
    *,
    ticket: dict[str, Any],
    preflight: dict[str, Any] | None,
    status: str,
    operator: str = "local",
    note: str = "",
    source: str = "manual",
    paper_trade_id: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    status = status if status in APPROVAL_STATUSES else "blocked"
    preflight = preflight or {}
    blockers = preflight.get("blockers") or []
    warnings = preflight.get("warnings") or []
    return {
        "approval_id": f"pa_{uuid4().hex[:12]}",
        "version": "0.4.4-paper-approval-v1",
        "mode": "paper_execution_approval_v044",
        "created_at": _now(),
        "operator": _text(operator, "local"),
        "source": _text(source, "manual"),
        "status": status,
        "ticket_id": ticket.get("ticket_id"),
        "market_id": ticket.get("market_id"),
        "title": ticket.get("title") or ticket.get("question") or ticket.get("market_id"),
        "outcome": _text(ticket.get("outcome") or "YES").upper(),
        "stake": round(_safe_float(ticket.get("stake")), 4),
        "price": round(_safe_float(ticket.get("price"), 0.5), 4),
        "approved": status in {"approved", "executed"},
        "paper_trade_id": paper_trade_id,
        "preflight_status": preflight.get("status"),
        "preflight_approved": bool(preflight.get("approved")),
        "blocker_count": int(preflight.get("blocker_count") or len(blockers) or 0),
        "warning_count": int(preflight.get("warning_count") or len(warnings) or 0),
        "blocker_summary": " | ".join(_text(item.get("detail") or item.get("name") or item) for item in blockers[:5]),
        "warning_summary": " | ".join(_text(item.get("detail") or item.get("name") or item) for item in warnings[:5]),
        "note": _text(note),
        "reason": _text(reason),
        "preflight_snapshot": preflight,
        "ticket_snapshot": ticket,
        "guardrail": "Local paper-execution approval record only. It does not place live orders, connect a wallet, sign messages, or provide investment advice.",
    }


def load_execution_approvals() -> list[dict[str, Any]]:
    rows = _read_json(APPROVALS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_execution_approvals(rows: list[dict[str, Any]]) -> None:
    _write_json(APPROVALS_PATH, rows)


def list_execution_approvals(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    ticket_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_execution_approvals()))
    if status:
        rows = [row for row in rows if _text(row.get("status")) == _text(status)]
    if market_id:
        rows = [row for row in rows if _text(row.get("market_id")) == _text(market_id)]
    if ticket_id:
        rows = [row for row in rows if _text(row.get("ticket_id")) == _text(ticket_id)]
    return rows[: max(0, int(limit))]


def get_execution_approval(approval_id: str) -> dict[str, Any] | None:
    for row in load_execution_approvals():
        if _text(row.get("approval_id")) == _text(approval_id):
            return row
    return None


def latest_approval_for_ticket(ticket_id: str) -> dict[str, Any] | None:
    rows = list_execution_approvals(limit=1, ticket_id=ticket_id)
    return rows[0] if rows else None


def record_execution_decision(
    ticket: dict[str, Any] | str,
    *,
    preflight: dict[str, Any] | None = None,
    status: str,
    operator: str = "local",
    note: str = "",
    source: str = "manual",
    paper_trade_id: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    if isinstance(ticket, str):
        found = get_trade_ticket(ticket)
        if not found:
            raise ValueError("Trade ticket not found")
        ticket = found
    record = _approval_record(
        ticket=ticket,
        preflight=preflight,
        status=status,
        operator=operator,
        note=note,
        source=source,
        paper_trade_id=paper_trade_id,
        reason=reason,
    )
    rows = load_execution_approvals()
    rows.append(record)
    save_execution_approvals(rows)
    return record


def approve_trade_ticket(
    ticket_id: str,
    *,
    operator: str = "local",
    note: str = "",
    strict_playbook: bool = False,
    opportunity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ticket = get_trade_ticket(ticket_id)
    if not ticket:
        raise ValueError("Trade ticket not found")
    preflight = build_ticket_preflight(ticket, opportunity=opportunity, strict_playbook=strict_playbook)
    if preflight.get("approved"):
        record = record_execution_decision(ticket, preflight=preflight, status="approved", operator=operator, note=note, source="manual_approval")
        updated_note = note or _text(ticket.get("operator_note"))
        update_trade_ticket(ticket_id, status="paper_ready", operator_note=updated_note, operator_decision=f"approved:{record.get('approval_id')}")
        record["ticket_after_update"] = get_trade_ticket(ticket_id)
        return record
    record = record_execution_decision(
        ticket,
        preflight=preflight,
        status="blocked",
        operator=operator,
        note=note,
        source="manual_approval",
        reason="Preflight did not approve the paper ticket.",
    )
    update_trade_ticket(ticket_id, status="blocked", operator_note=note or _text(ticket.get("operator_note")), operator_decision=f"blocked:{record.get('approval_id')}")
    record["ticket_after_update"] = get_trade_ticket(ticket_id)
    return record


def reject_trade_ticket(ticket_id: str, *, operator: str = "local", note: str = "") -> dict[str, Any]:
    ticket = get_trade_ticket(ticket_id)
    if not ticket:
        raise ValueError("Trade ticket not found")
    preflight = build_ticket_preflight(ticket)
    record = record_execution_decision(ticket, preflight=preflight, status="rejected", operator=operator, note=note, source="manual_rejection")
    update_trade_ticket(ticket_id, status="rejected", operator_note=note or _text(ticket.get("operator_note")), operator_decision=f"rejected:{record.get('approval_id')}")
    record["ticket_after_update"] = get_trade_ticket(ticket_id)
    return record


def summarize_execution_approvals(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load_execution_approvals()
    statuses = Counter(_text(row.get("status") or "unknown") for row in rows)
    markets = {_text(row.get("market_id")) for row in rows if row.get("market_id")}
    tickets = {_text(row.get("ticket_id")) for row in rows if row.get("ticket_id")}
    warnings = sum(int(row.get("warning_count") or 0) for row in rows)
    blockers = sum(int(row.get("blocker_count") or 0) for row in rows)
    return {
        "count": len(rows),
        "market_count": len(markets),
        "ticket_count": len(tickets),
        "by_status": dict(sorted(statuses.items())),
        "approved": statuses.get("approved", 0),
        "blocked": statuses.get("blocked", 0),
        "rejected": statuses.get("rejected", 0),
        "executed": statuses.get("executed", 0),
        "total_blockers_snapshot": blockers,
        "total_warnings_snapshot": warnings,
        "last_approval_at": rows[0].get("created_at") if rows else None,
        "guardrail": "Approvals are local paper-only governance records. They do not place live orders or provide investment advice.",
    }


def build_execution_approval_board(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    rows = list_execution_approvals(limit=limit, status=status, market_id=market_id, ticket_id=ticket_id)
    return {
        "summary": summarize_execution_approvals(rows),
        "items": rows,
        "guardrail": "Paper approval board only. It never connects a wallet, signs messages, places orders, or automates execution.",
    }


def approval_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_execution_approval_board(limit=100)
    alerts: list[dict[str, Any]] = []
    for row in board.get("items") or []:
        status = _text(row.get("status"))
        if status == "blocked":
            alerts.append(
                {
                    "level": "warning",
                    "kind": "paper_approval_blocked",
                    "title": "Paper execution approval blocked",
                    "market_id": row.get("market_id"),
                    "question": row.get("title"),
                    "detail": row.get("blocker_summary") or "A paper-ticket approval was blocked by preflight.",
                    "recommended_action": "review_approval_and_preflight",
                }
            )
        elif status == "approved" and int(row.get("warning_count") or 0) > 0:
            alerts.append(
                {
                    "level": "info",
                    "kind": "paper_approval_warning",
                    "title": "Paper execution approved with warnings",
                    "market_id": row.get("market_id"),
                    "question": row.get("title"),
                    "detail": row.get("warning_summary") or "A paper-ticket approval has preflight warnings.",
                    "recommended_action": "review_warnings_before_execution",
                }
            )
    return alerts


def approvals_to_csv(rows: list[dict[str, Any]]) -> str:
    fieldnames = [
        "created_at",
        "approval_id",
        "status",
        "operator",
        "source",
        "ticket_id",
        "market_id",
        "title",
        "outcome",
        "stake",
        "price",
        "paper_trade_id",
        "preflight_status",
        "preflight_approved",
        "blocker_count",
        "warning_count",
        "blocker_summary",
        "warning_summary",
        "note",
        "reason",
    ]
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return handle.getvalue()
