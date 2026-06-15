from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any

from .paper_approvals import latest_approval_for_ticket
from .paper_preflight import build_ticket_preflight
from .trade_tickets import get_trade_ticket, list_trade_tickets

EXECUTION_QUEUE_STATUSES = {
    "approved_ready",
    "needs_approval",
    "blocked",
    "rejected",
    "executed",
    "stale_approval",
}

TERMINAL_TICKET_STATUSES = {"paper_executed", "archived"}


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


def _approval_matches_ticket(ticket: dict[str, Any], approval: dict[str, Any] | None) -> bool:
    if not approval:
        return False
    if _text(approval.get("ticket_id")) != _text(ticket.get("ticket_id")):
        return False
    if _text(approval.get("market_id")) != _text(ticket.get("market_id")):
        return False
    if _text(approval.get("outcome"), "YES").upper() != _text(ticket.get("outcome"), "YES").upper():
        return False
    return abs(_safe_float(approval.get("stake")) - _safe_float(ticket.get("stake"))) < 0.0001


def _queue_status(ticket: dict[str, Any], preflight: dict[str, Any], approval: dict[str, Any] | None, *, require_approval: bool = True) -> tuple[str, str, bool, list[str]]:
    ticket_status = _text(ticket.get("status"))
    approval_status = _text((approval or {}).get("status"))
    reasons: list[str] = []

    if ticket_status in TERMINAL_TICKET_STATUSES or ticket.get("paper_trade_id"):
        return "executed", "review_executed_ticket", False, ["Ticket already has a paper execution record."]

    if ticket_status == "rejected" or approval_status == "rejected":
        return "rejected", "restore_or_archive_ticket", False, ["Ticket or latest approval is rejected."]

    if not preflight.get("approved"):
        for item in preflight.get("blockers") or []:
            detail = item.get("detail") if isinstance(item, dict) else item
            if detail:
                reasons.append(str(detail))
        return "blocked", "resolve_preflight_blockers", False, reasons or ["Preflight did not approve this paper ticket."]

    if require_approval:
        if not approval:
            return "needs_approval", "approve_or_reject_ticket", False, ["No local approval record exists for this preflight-approved ticket."]
        if approval_status != "approved":
            return "needs_approval", "approve_or_reject_ticket", False, [f"Latest approval status is {approval_status or 'missing'}, not approved."]
        if not _approval_matches_ticket(ticket, approval):
            return "stale_approval", "rerun_approval", False, ["Latest approval does not match the current ticket market/outcome/stake snapshot."]

    if preflight.get("warning_count"):
        reasons.append(f"Preflight approved with {preflight.get('warning_count')} warning(s).")
    return "approved_ready", "execute_paper_buy_or_hold", True, reasons


def build_ticket_execution_queue_item(
    ticket: dict[str, Any] | str,
    *,
    opportunity: dict[str, Any] | None = None,
    strict_playbook: bool = False,
    require_approval: bool = True,
) -> dict[str, Any]:
    if isinstance(ticket, str):
        found = get_trade_ticket(ticket)
        if not found:
            raise ValueError("Trade ticket not found")
        ticket = found
    preflight = build_ticket_preflight(ticket, opportunity=opportunity, strict_playbook=strict_playbook)
    approval = latest_approval_for_ticket(_text(ticket.get("ticket_id"))) if ticket.get("ticket_id") else None
    status, action, executable, reasons = _queue_status(ticket, preflight, approval, require_approval=require_approval)
    priority_map = {
        "blocked": 95,
        "stale_approval": 90,
        "needs_approval": 85,
        "approved_ready": 75,
        "rejected": 30,
        "executed": 10,
    }
    return {
        "version": "0.4.5-paper-execution-queue-v1",
        "mode": "paper_execution_queue_v045",
        "ticket_id": ticket.get("ticket_id"),
        "market_id": ticket.get("market_id"),
        "title": ticket.get("title") or ticket.get("question") or ticket.get("market_id"),
        "outcome": _text(ticket.get("outcome") or "YES").upper(),
        "stake": round(_safe_float(ticket.get("stake")), 4),
        "price": round(_safe_float(ticket.get("price"), 0.5), 4),
        "ticket_status": _text(ticket.get("status")),
        "queue_status": status,
        "recommended_action": action,
        "paper_buy_executable": bool(executable),
        "priority": priority_map.get(status, 50) + int(preflight.get("blocker_count") or 0) * 3 + int(preflight.get("warning_count") or 0),
        "reason_summary": " | ".join(reasons[:5]),
        "preflight_status": preflight.get("status"),
        "preflight_approved": bool(preflight.get("approved")),
        "blocker_count": int(preflight.get("blocker_count") or 0),
        "warning_count": int(preflight.get("warning_count") or 0),
        "latest_approval_id": (approval or {}).get("approval_id"),
        "latest_approval_status": (approval or {}).get("status"),
        "latest_approval_at": (approval or {}).get("created_at"),
        "paper_trade_id": ticket.get("paper_trade_id"),
        "preflight_snapshot": preflight,
        "latest_approval": approval,
        "ticket_snapshot": ticket,
        "guardrail": "Local paper execution queue only. It does not place live orders, connect a wallet, sign messages, or provide investment advice.",
    }


def build_execution_queue(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    ticket_id: str | None = None,
    strict_playbook: bool = False,
    require_approval: bool = True,
    opportunities_by_market: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tickets = list_trade_tickets(limit=10000)
    rows: list[dict[str, Any]] = []
    opportunities_by_market = opportunities_by_market or {}
    for ticket in tickets:
        if market_id and _text(ticket.get("market_id")) != _text(market_id):
            continue
        if ticket_id and _text(ticket.get("ticket_id")) != _text(ticket_id):
            continue
        opportunity = opportunities_by_market.get(_text(ticket.get("market_id")))
        try:
            item = build_ticket_execution_queue_item(ticket, opportunity=opportunity, strict_playbook=strict_playbook, require_approval=require_approval)
        except Exception as exc:
            item = {
                "version": "0.4.5-paper-execution-queue-v1",
                "mode": "paper_execution_queue_v045",
                "ticket_id": ticket.get("ticket_id"),
                "market_id": ticket.get("market_id"),
                "title": ticket.get("title") or ticket.get("market_id"),
                "queue_status": "blocked",
                "recommended_action": "repair_ticket_or_preflight",
                "paper_buy_executable": False,
                "priority": 100,
                "reason_summary": f"Execution queue build failed: {exc}",
                "ticket_snapshot": ticket,
                "guardrail": "Local paper execution queue only.",
            }
        if status and _text(item.get("queue_status")) != _text(status):
            continue
        rows.append(item)
    rows.sort(key=lambda row: (int(row.get("priority") or 0), str(row.get("latest_approval_at") or ""), str(row.get("ticket_id") or "")), reverse=True)
    rows = rows[: max(0, int(limit))]
    return {
        "summary": summarize_execution_queue(rows, require_approval=require_approval),
        "items": rows,
        "guardrail": "Paper execution queue only. Entry-ticket paper buys require a local approval gate and still never reach a wallet or exchange.",
    }


def summarize_execution_queue(rows: list[dict[str, Any]], *, require_approval: bool = True) -> dict[str, Any]:
    counts = Counter(_text(row.get("queue_status") or "unknown") for row in rows)
    executable = sum(1 for row in rows if row.get("paper_buy_executable"))
    total_stake = sum(_safe_float(row.get("stake")) for row in rows)
    executable_stake = sum(_safe_float(row.get("stake")) for row in rows if row.get("paper_buy_executable"))
    markets = {_text(row.get("market_id")) for row in rows if row.get("market_id")}
    return {
        "count": len(rows),
        "market_count": len(markets),
        "by_status": dict(sorted(counts.items())),
        "approved_ready": counts.get("approved_ready", 0),
        "needs_approval": counts.get("needs_approval", 0),
        "blocked": counts.get("blocked", 0),
        "stale_approval": counts.get("stale_approval", 0),
        "rejected": counts.get("rejected", 0),
        "executed": counts.get("executed", 0),
        "paper_buy_executable": executable,
        "total_stake": round(total_stake, 4),
        "executable_stake": round(executable_stake, 4),
        "approval_required": bool(require_approval),
        "guardrail": "Queue statuses are local paper-workflow controls only and are not live trading advice.",
    }


def ticket_execution_gate(
    ticket: dict[str, Any] | str,
    *,
    preflight: dict[str, Any] | None = None,
    strict_playbook: bool = False,
    require_approval: bool = True,
) -> dict[str, Any]:
    if isinstance(ticket, str):
        found = get_trade_ticket(ticket)
        if not found:
            raise ValueError("Trade ticket not found")
        ticket = found
    if preflight is None:
        preflight = build_ticket_preflight(ticket, strict_playbook=strict_playbook)
    approval = latest_approval_for_ticket(_text(ticket.get("ticket_id"))) if ticket.get("ticket_id") else None
    status, action, executable, reasons = _queue_status(ticket, preflight, approval, require_approval=require_approval)
    return {
        "version": "0.4.5-paper-execution-queue-v1",
        "mode": "paper_execution_gate_v045",
        "ticket_id": ticket.get("ticket_id"),
        "market_id": ticket.get("market_id"),
        "queue_status": status,
        "recommended_action": action,
        "paper_buy_executable": bool(executable),
        "reason_summary": " | ".join(reasons[:5]),
        "latest_approval_id": (approval or {}).get("approval_id"),
        "latest_approval_status": (approval or {}).get("status"),
        "latest_approval_at": (approval or {}).get("created_at"),
        "preflight_status": preflight.get("status"),
        "preflight_approved": bool(preflight.get("approved")),
        "latest_approval": approval,
        "guardrail": "Paper execution gate only; no live order is possible from this check.",
    }


def execution_queue_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_execution_queue(limit=100)
    alerts: list[dict[str, Any]] = []
    for row in board.get("items") or []:
        status = _text(row.get("queue_status"))
        if status == "approved_ready":
            alerts.append(
                {
                    "level": "info",
                    "kind": "paper_execution_ready",
                    "title": "Paper ticket approved for simulated execution",
                    "market_id": row.get("market_id"),
                    "question": row.get("title"),
                    "detail": f"Ticket {row.get('ticket_id')} has approval {row.get('latest_approval_id')} and is ready for operator-controlled paper buy.",
                    "recommended_action": "open_execution_queue",
                }
            )
        elif status in {"needs_approval", "stale_approval"}:
            alerts.append(
                {
                    "level": "warning",
                    "kind": "paper_execution_needs_approval",
                    "title": "Paper ticket needs execution approval",
                    "market_id": row.get("market_id"),
                    "question": row.get("title"),
                    "detail": row.get("reason_summary") or f"Ticket {row.get('ticket_id')} needs approval review.",
                    "recommended_action": "approve_or_reject_ticket",
                }
            )
    return alerts


def execution_queue_to_csv(rows: list[dict[str, Any]]) -> str:
    fieldnames = [
        "ticket_id",
        "market_id",
        "title",
        "outcome",
        "stake",
        "price",
        "ticket_status",
        "queue_status",
        "recommended_action",
        "paper_buy_executable",
        "preflight_status",
        "preflight_approved",
        "blocker_count",
        "warning_count",
        "latest_approval_id",
        "latest_approval_status",
        "latest_approval_at",
        "paper_trade_id",
        "reason_summary",
    ]
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return handle.getvalue()
