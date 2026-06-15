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
from .paper_execution_queue import build_execution_queue, build_ticket_execution_queue_item
from .paper_exit_tickets import get_exit_ticket, list_exit_tickets
from .paper_risk_budget import build_risk_budget
from .paper_settlement import settlement_candidates
from .trade_tickets import get_trade_ticket

RUNBOOK_ACKS_PATH = DATA_DIR / "paper" / "operator_runbook_acknowledgements.json"
RUNBOOK_SCOPES = {"entry_execution", "exit_execution", "settlement", "post_trade_review", "risk_budget"}
RUNBOOK_STATUSES = {"ready", "action_required", "blocked", "review", "completed", "acknowledged", "skipped"}
ACK_STATUSES = {"done", "skipped", "needs_followup"}


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


def _task(
    *,
    item_id: str,
    scope: str,
    status: str,
    priority: int,
    title: str,
    recommended_action: str,
    market_id: str = "",
    ticket_id: str = "",
    question: str = "",
    detail: str = "",
    checklist: list[dict[str, Any]] | None = None,
    links: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "version": "0.4.6-paper-operator-runbook-v1",
        "mode": "paper_operator_runbook_v046",
        "scope": scope,
        "status": status if status in RUNBOOK_STATUSES else "review",
        "priority": int(priority),
        "title": title,
        "recommended_action": recommended_action,
        "market_id": market_id,
        "ticket_id": ticket_id,
        "question": question or title,
        "detail": detail,
        "checklist": checklist or [],
        "checklist_total": len(checklist or []),
        "checklist_required": sum(1 for row in (checklist or []) if row.get("required", True)),
        "links": links or {},
        "data": data or {},
        "guardrail": "Local paper-operator runbook item only. It does not place live orders, connect a wallet, sign messages, or provide investment advice.",
    }


def load_runbook_acknowledgements() -> list[dict[str, Any]]:
    rows = _read_json(RUNBOOK_ACKS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_runbook_acknowledgements(rows: list[dict[str, Any]]) -> None:
    _write_json(RUNBOOK_ACKS_PATH, rows)


def list_runbook_acknowledgements(
    *,
    limit: int = 100,
    item_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_runbook_acknowledgements()))
    if item_id:
        rows = [row for row in rows if _text(row.get("item_id")) == _text(item_id)]
    if status:
        rows = [row for row in rows if _text(row.get("status")) == _text(status)]
    return rows[: max(0, int(limit))]


def latest_acknowledgement_by_item() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in load_runbook_acknowledgements():
        item_id = _text(row.get("item_id"))
        if item_id:
            latest[item_id] = row
    return latest


def _entry_execution_tasks(limit: int) -> list[dict[str, Any]]:
    board = build_execution_queue(limit=max(limit, 1000))
    tasks: list[dict[str, Any]] = []
    status_map = {
        "approved_ready": "ready",
        "needs_approval": "action_required",
        "stale_approval": "action_required",
        "blocked": "blocked",
        "rejected": "completed",
        "executed": "completed",
    }
    for row in board.get("items") or []:
        queue_status = _text(row.get("queue_status"))
        item_status = status_map.get(queue_status, "review")
        ticket_id = _text(row.get("ticket_id"))
        market_id = _text(row.get("market_id"))
        tasks.append(
            _task(
                item_id=f"entry:{ticket_id}",
                scope="entry_execution",
                status=item_status,
                priority=100 + int(row.get("priority") or 0),
                title=f"Entry ticket {ticket_id}: {_text(row.get('title') or market_id)}",
                recommended_action=_text(row.get("recommended_action") or "review_entry_ticket"),
                market_id=market_id,
                ticket_id=ticket_id,
                question=_text(row.get("title") or market_id),
                detail=_text(row.get("reason_summary") or f"Execution queue status: {queue_status}"),
                checklist=[
                    {"step": "Confirm preflight is still passing", "required": True, "state": _text(row.get("preflight_status") or "unknown")},
                    {"step": "Confirm latest approval matches market/outcome/stake", "required": True, "state": _text(row.get("latest_approval_status") or "missing")},
                    {"step": "Re-check risk budget and position concentration", "required": True, "state": "manual_review"},
                    {"step": "Execute only via paper-buy button/CLI after operator review", "required": True, "state": "human_controlled"},
                ],
                links={
                    "queue": f"/execution-queue?ticket_id={ticket_id}",
                    "preflight": f"/preflight?ticket_id={ticket_id}",
                    "approvals": f"/approvals?ticket_id={ticket_id}",
                    "audit": f"/audit?market_id={market_id}",
                },
                data=row,
            )
        )
    return tasks


def _exit_execution_tasks(limit: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    status_map = {
        "exit_ready": "ready",
        "draft_review": "action_required",
        "blocked": "blocked",
        "rejected": "completed",
        "paper_executed": "completed",
        "archived": "completed",
    }
    for row in list_exit_tickets(limit=max(limit, 1000)):
        ticket_id = _text(row.get("ticket_id"))
        market_id = _text(row.get("market_id"))
        raw_status = _text(row.get("status"))
        tasks.append(
            _task(
                item_id=f"exit:{ticket_id}",
                scope="exit_execution",
                status=status_map.get(raw_status, "review"),
                priority=85 if raw_status == "exit_ready" else 70 if raw_status == "draft_review" else 45,
                title=f"Exit ticket {ticket_id}: {_text(row.get('title') or market_id)}",
                recommended_action="execute_simulated_sell_or_hold" if raw_status == "exit_ready" else "review_exit_ticket",
                market_id=market_id,
                ticket_id=ticket_id,
                question=_text(row.get("title") or market_id),
                detail=_text(row.get("exit_reason") or row.get("operator_note") or f"Exit ticket status: {raw_status}"),
                checklist=[
                    {"step": "Verify open paper shares and exit size", "required": True, "state": f"shares={row.get('shares', 0)}"},
                    {"step": "Confirm exit price and thesis invalidation/target rationale", "required": True, "state": f"price={row.get('price', 'n/a')}"},
                    {"step": "Review estimated realized P&L before simulated sell", "required": True, "state": f"pnl={row.get('estimated_realized_pnl', 0)}"},
                    {"step": "Execute only as a local paper sell", "required": True, "state": "human_controlled"},
                ],
                links={
                    "exit_ticket": f"/exit-tickets?ticket_id={ticket_id}",
                    "positions": f"/positions?market_id={market_id}",
                    "audit": f"/audit?market_id={market_id}",
                },
                data=row,
            )
        )
    return tasks


def _settlement_tasks(limit: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for row in settlement_candidates(limit=max(limit, 1000)):
        market_id = _text(row.get("market_id"))
        outcomes = ",".join(_text(x) for x in (row.get("outcomes") or []))
        tasks.append(
            _task(
                item_id=f"settlement:{market_id}",
                scope="settlement",
                status="action_required",
                priority=65,
                title=f"Settlement review: {_text(row.get('question') or market_id)}",
                recommended_action="verify_resolution_then_manual_settle_or_hold",
                market_id=market_id,
                question=_text(row.get("question") or market_id),
                detail=f"Open paper settlement candidate with {row.get('position_count', 0)} position(s), outcomes={outcomes or 'n/a'}, cost_basis={row.get('cost_basis', 0)}.",
                checklist=[
                    {"step": "Verify official market resolution from source material", "required": True, "state": "manual_verification_required"},
                    {"step": "Choose winning outcome explicitly", "required": True, "state": outcomes or "unknown"},
                    {"step": "Preview settlement P&L before recording", "required": True, "state": "preview_required"},
                    {"step": "Record manual paper settlement only after confirmation", "required": True, "state": "human_controlled"},
                ],
                links={
                    "settlements": f"/settlements?market_id={market_id}",
                    "preview": f"/api/paper/settlement-preview/{market_id}",
                    "audit": f"/audit?market_id={market_id}",
                },
                data=row,
            )
        )
    return tasks


def _post_trade_review_tasks(limit: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    from .paper_review import build_review_report
    report = build_review_report(limit=max(limit, 1000))
    for row in report.get("items") or []:
        flags = row.get("discipline_flags") or []
        warnings = [flag for flag in flags if _text(flag.get("level")) == "warning"]
        infos = [flag for flag in flags if _text(flag.get("level")) == "info"]
        if not warnings and not infos:
            continue
        market_id = _text(row.get("market_id"))
        first_flag = (warnings or infos)[0]
        tasks.append(
            _task(
                item_id=f"review:{market_id}",
                scope="post_trade_review",
                status="review",
                priority=55 + len(warnings) * 10 + len(infos) * 3,
                title=f"Review lesson: {_text(row.get('question') or market_id)}",
                recommended_action="write_or_close_post_trade_lesson",
                market_id=market_id,
                question=_text(row.get("question") or market_id),
                detail=_text(first_flag.get("detail") or row.get("lesson") or "Review paper-trade discipline flags."),
                checklist=[
                    {"step": "Read the market-level review report", "required": True, "state": row.get("lifecycle_status") or row.get("status") or "review"},
                    {"step": "Decide whether the process gap needs a playbook/risk-rule adjustment", "required": False, "state": first_flag.get("code") or "flagged"},
                    {"step": "Record lesson in notes or mark the runbook item done", "required": True, "state": "manual_review"},
                ],
                links={
                    "review_report": f"/review-report?market_id={market_id}",
                    "audit": f"/audit?market_id={market_id}",
                },
                data=row,
            )
        )
    return tasks


def _risk_budget_tasks(limit: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    report = build_risk_budget(limit=max(limit, 1000))
    for flag in report.get("flags") or []:
        kind = _text(flag.get("kind") or "risk_budget_flag")
        market_id = _text(flag.get("market_id"))
        item_id = f"risk:{market_id or kind}"
        tasks.append(
            _task(
                item_id=item_id,
                scope="risk_budget",
                status="blocked" if "blocked" in kind or "exceed" in kind or _text(flag.get("level")) == "warning" else "review",
                priority=80 if _text(flag.get("level")) == "warning" else 50,
                title=f"Risk budget check: {kind}",
                recommended_action="resolve_risk_budget_before_new_entries",
                market_id=market_id,
                question=_text(flag.get("question") or market_id or kind),
                detail=_text(flag.get("detail") or kind),
                checklist=[
                    {"step": "Open risk-budget report", "required": True, "state": "required"},
                    {"step": "Reduce pending tickets, position size, or wait for exposure to clear", "required": False, "state": "operator_choice"},
                    {"step": "Do not force simulated entries through blocked budget state", "required": True, "state": "paper_guardrail"},
                ],
                links={
                    "risk_budget": f"/risk-budget?market_id={market_id}" if market_id else "/risk-budget",
                    "audit": f"/audit?market_id={market_id}" if market_id else "/audit",
                },
                data=flag,
            )
        )
    return tasks


def _apply_acknowledgements(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = latest_acknowledgement_by_item()
    for task in tasks:
        ack = latest.get(_text(task.get("item_id")))
        task["latest_acknowledgement"] = ack
        task["acknowledged"] = bool(ack and ack.get("status") in {"done", "skipped"})
        task["acknowledgement_status"] = ack.get("status") if ack else None
        task["acknowledgement_note"] = ack.get("note") if ack else ""
        task["effective_status"] = task.get("status")
        if ack and ack.get("status") == "done" and task.get("status") != "blocked":
            task["effective_status"] = "acknowledged"
        elif ack and ack.get("status") == "skipped":
            task["effective_status"] = "skipped"
        elif ack and ack.get("status") == "needs_followup":
            task["effective_status"] = "action_required"
            task["priority"] = max(int(task.get("priority") or 0), 90)
    return tasks


def build_runbook(
    *,
    limit: int = 100,
    scope: str | None = None,
    status: str | None = None,
    market_id: str | None = None,
    item_id: str | None = None,
    include_completed: bool = False,
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    tasks.extend(_entry_execution_tasks(limit))
    tasks.extend(_exit_execution_tasks(limit))
    tasks.extend(_settlement_tasks(limit))
    tasks.extend(_risk_budget_tasks(limit))
    tasks.extend(_post_trade_review_tasks(limit))
    tasks = _apply_acknowledgements(tasks)

    if not include_completed:
        tasks = [row for row in tasks if _text(row.get("effective_status") or row.get("status")) not in {"completed", "acknowledged", "skipped"}]
    if scope:
        tasks = [row for row in tasks if _text(row.get("scope")) == _text(scope)]
    if status:
        tasks = [row for row in tasks if _text(row.get("effective_status") or row.get("status")) == _text(status)]
    if market_id:
        tasks = [row for row in tasks if _text(row.get("market_id")) == _text(market_id)]
    if item_id:
        tasks = [row for row in tasks if _text(row.get("item_id")) == _text(item_id)]
    tasks.sort(key=lambda row: (int(row.get("priority") or 0), _text(row.get("item_id"))), reverse=True)
    tasks = tasks[: max(0, int(limit))]
    return {
        "summary": summarize_runbook(tasks),
        "items": tasks,
        "acknowledgement_count": len(load_runbook_acknowledgements()),
        "guardrail": "Paper operator runbook only. These checklist items coordinate local simulated workflows and never connect a wallet, sign messages, place live orders, or provide investment advice.",
    }


def get_runbook_item(item_id: str, *, include_completed: bool = True) -> dict[str, Any] | None:
    report = build_runbook(limit=10000, item_id=item_id, include_completed=include_completed)
    items = report.get("items") or []
    return items[0] if items else None


def record_runbook_acknowledgement(
    item_id: str,
    *,
    status: str = "done",
    operator: str = "local",
    note: str = "",
    item_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = status if status in ACK_STATUSES else "done"
    item_snapshot = item_snapshot or get_runbook_item(item_id, include_completed=True) or {"item_id": item_id}
    record = {
        "ack_id": f"prb_{uuid4().hex[:12]}",
        "version": "0.4.6-paper-operator-runbook-ack-v1",
        "mode": "paper_operator_runbook_acknowledgement_v046",
        "created_at": _now(),
        "operator": _text(operator, "local"),
        "item_id": _text(item_id),
        "scope": _text(item_snapshot.get("scope")),
        "market_id": _text(item_snapshot.get("market_id")),
        "ticket_id": _text(item_snapshot.get("ticket_id")),
        "status": status,
        "note": _text(note),
        "item_status_at_ack": _text(item_snapshot.get("effective_status") or item_snapshot.get("status")),
        "recommended_action_at_ack": _text(item_snapshot.get("recommended_action")),
        "item_snapshot": item_snapshot,
        "guardrail": "Local paper-runbook acknowledgement only. It is not live trading activity.",
    }
    rows = load_runbook_acknowledgements()
    rows.append(record)
    save_runbook_acknowledgements(rows)
    return record


def summarize_runbook(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    scopes = Counter(_text(row.get("scope") or "unknown") for row in tasks)
    statuses = Counter(_text(row.get("effective_status") or row.get("status") or "unknown") for row in tasks)
    markets = {_text(row.get("market_id")) for row in tasks if row.get("market_id")}
    ready_stake = sum(_safe_float((row.get("data") or {}).get("stake")) for row in tasks if _text(row.get("scope")) == "entry_execution" and _text(row.get("effective_status") or row.get("status")) == "ready")
    return {
        "count": len(tasks),
        "market_count": len(markets),
        "by_scope": dict(sorted(scopes.items())),
        "by_status": dict(sorted(statuses.items())),
        "ready": statuses.get("ready", 0),
        "action_required": statuses.get("action_required", 0),
        "blocked": statuses.get("blocked", 0),
        "review": statuses.get("review", 0),
        "acknowledged": statuses.get("acknowledged", 0),
        "ready_entry_stake": round(ready_stake, 4),
        "top_priority": max([int(row.get("priority") or 0) for row in tasks], default=0),
        "guardrail": "Runbook counts are local paper-workflow operations only, not trading recommendations.",
    }


def runbook_alerts(report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    report = report or build_runbook(limit=100)
    alerts: list[dict[str, Any]] = []
    for row in report.get("items") or []:
        status = _text(row.get("effective_status") or row.get("status"))
        if status == "ready":
            alerts.append(
                {
                    "level": "info",
                    "kind": "paper_runbook_ready",
                    "title": "Paper runbook item ready",
                    "market_id": row.get("market_id"),
                    "question": row.get("question"),
                    "detail": row.get("detail") or row.get("recommended_action"),
                    "recommended_action": "open_operator_runbook",
                }
            )
        elif status in {"action_required", "blocked"}:
            alerts.append(
                {
                    "level": "warning" if status == "blocked" else "info",
                    "kind": "paper_runbook_action_required",
                    "title": "Paper runbook item needs operator action",
                    "market_id": row.get("market_id"),
                    "question": row.get("question"),
                    "detail": row.get("detail") or row.get("recommended_action"),
                    "recommended_action": "open_operator_runbook",
                }
            )
    return alerts[:25]


def runbook_to_csv(rows: list[dict[str, Any]]) -> str:
    fieldnames = [
        "item_id",
        "scope",
        "effective_status",
        "status",
        "priority",
        "market_id",
        "ticket_id",
        "title",
        "recommended_action",
        "detail",
        "checklist_total",
        "checklist_required",
        "acknowledgement_status",
        "acknowledgement_note",
    ]
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return handle.getvalue()
