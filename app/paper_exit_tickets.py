from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR
from .paper_trading import load_portfolio, summarize_portfolio

EXIT_TICKETS_PATH = DATA_DIR / "paper" / "exit_tickets.json"
VALID_EXIT_STATUSES = {
    "draft_review",
    "exit_ready",
    "blocked",
    "rejected",
    "paper_executed",
    "archived",
}


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


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _position_key(market_id: str, outcome: str) -> str:
    return f"{market_id}:{str(outcome or 'YES').strip().upper()}"


def _market_price(market: dict[str, Any] | None, outcome: str, fallback: float) -> float:
    if market:
        for row in market.get("outcomes") or []:
            if isinstance(row, dict) and str(row.get("name", "")).upper() == str(outcome or "YES").upper():
                return _safe_float(row.get("price"), fallback)
        outcomes = market.get("outcomes") or []
        if outcomes and isinstance(outcomes[0], dict):
            return _safe_float(outcomes[0].get("price"), fallback)
    return fallback


def _market_snapshot(market: dict[str, Any] | None, position: dict[str, Any], outcome: str, price: float) -> dict[str, Any]:
    market_id = str(position.get("market_id") or (market or {}).get("id") or "")
    question = str(position.get("question") or (market or {}).get("question") or market_id)
    if market:
        snapshot = dict(market)
        snapshot["id"] = str(snapshot.get("id") or market_id)
        snapshot["market_id"] = str(snapshot.get("market_id") or snapshot.get("id") or market_id)
        snapshot["question"] = snapshot.get("question") or question
        return snapshot
    return {
        "id": market_id,
        "market_id": market_id,
        "question": question,
        "outcomes": [{"name": str(outcome or "YES").upper(), "price": round(price, 4)}],
    }


def load_exit_tickets() -> list[dict[str, Any]]:
    rows = _read_json(EXIT_TICKETS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_exit_tickets(rows: list[dict[str, Any]]) -> None:
    _write_json(EXIT_TICKETS_PATH, rows)


def list_exit_tickets(limit: int = 100, status: str | None = None, market_id: str | None = None) -> list[dict[str, Any]]:
    rows = list(reversed(load_exit_tickets()))
    if status:
        rows = [row for row in rows if str(row.get("status")) == str(status)]
    if market_id:
        rows = [row for row in rows if str(row.get("market_id")) == str(market_id)]
    return rows[:limit]


def get_exit_ticket(ticket_id: str) -> dict[str, Any] | None:
    for row in load_exit_tickets():
        if str(row.get("ticket_id")) == str(ticket_id):
            return row
    return None


def summarize_exit_tickets(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load_exit_tickets()
    by_status: dict[str, int] = {}
    potential_proceeds = 0.0
    potential_realized = 0.0
    for row in rows:
        status = str(row.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        if status in {"exit_ready", "draft_review"}:
            potential_proceeds += _safe_float(row.get("estimated_proceeds"), 0.0)
            potential_realized += _safe_float(row.get("estimated_realized_pnl"), 0.0)
    return {
        "count": len(rows),
        "by_status": by_status,
        "exit_ready": by_status.get("exit_ready", 0),
        "blocked": by_status.get("blocked", 0),
        "paper_executed": by_status.get("paper_executed", 0),
        "potential_proceeds": round(potential_proceeds, 4),
        "potential_realized_pnl": round(potential_realized, 4),
        "note": "Exit tickets are local paper-trading review records only. They do not place live trades.",
    }


def build_exit_ticket(
    market_id: str,
    *,
    outcome: str = "YES",
    market: dict[str, Any] | None = None,
    shares: Any = None,
    price: Any = None,
    reason: str = "manual paper exit review",
    created_by: str = "local",
    operator_note: str = "",
) -> dict[str, Any]:
    outcome = str(outcome or "YES").strip().upper()
    portfolio = load_portfolio()
    position = (portfolio.get("positions") or {}).get(_position_key(str(market_id), outcome))
    blockers: list[str] = []
    if not position:
        position = {
            "market_id": str(market_id),
            "question": str((market or {}).get("question") or market_id),
            "outcome": outcome,
            "shares": 0.0,
            "cost_basis": 0.0,
            "avg_price": 0.0,
            "last_price": 0.5,
            "exit_plan": {},
            "position_status": "unknown",
        }
        blockers.append("No open paper position exists for that market/outcome.")

    open_shares = _safe_float(position.get("shares"), 0.0)
    exit_shares = _safe_float(shares, open_shares) if shares not in (None, "") else open_shares
    if exit_shares <= 0:
        blockers.append("Exit shares must be greater than zero.")
    if open_shares > 0 and exit_shares > open_shares:
        blockers.append("Exit shares cannot exceed open paper shares.")

    fallback_price = _safe_float(position.get("current_price"), _safe_float(position.get("last_price"), _safe_float(position.get("avg_price"), 0.5)))
    exit_price = _optional_float(price)
    if exit_price is None:
        exit_price = _market_price(market, outcome, fallback=fallback_price)
    if not 0 < float(exit_price) < 1:
        blockers.append("Exit price must be between 0 and 1.")
        exit_price = max(0.0001, min(0.9999, float(exit_price or fallback_price or 0.5)))

    cost_basis = _safe_float(position.get("cost_basis"), 0.0)
    cost_portion = cost_basis * (exit_shares / open_shares) if open_shares > 0 else 0.0
    proceeds = exit_shares * float(exit_price)
    realized = proceeds - cost_portion
    plan = position.get("exit_plan") if isinstance(position.get("exit_plan"), dict) else {}
    status_hint = str(plan.get("status") or position.get("position_status") or "active")
    checklist = [
        {"name": "Open paper position exists", "passed": open_shares > 0, "detail": f"open_shares={open_shares:.8f}"},
        {"name": "Exit size valid", "passed": 0 < exit_shares <= open_shares if open_shares > 0 else False, "detail": f"exit_shares={exit_shares:.8f}"},
        {"name": "Exit price valid", "passed": 0 < float(exit_price) < 1, "detail": f"price={float(exit_price):.4f}"},
        {"name": "Lifecycle status reviewed", "passed": status_hint in {"reduce", "exit_planned", "watch"}, "detail": status_hint},
        {"name": "Human review required", "passed": False, "detail": "Operator must confirm price, thesis invalidation, and exit size before simulated execution."},
    ]
    execution_allowed = not blockers and open_shares > 0 and 0 < exit_shares <= open_shares and 0 < float(exit_price) < 1
    status = "exit_ready" if execution_allowed else "blocked"
    snapshot = _market_snapshot(market, position, outcome, float(exit_price))
    return {
        "ticket_id": f"px_{uuid4().hex[:12]}",
        "version": "0.3.7-paper-exit-ticket-v1",
        "created_at": _now(),
        "updated_at": _now(),
        "created_by": created_by,
        "status": status,
        "market_id": str(market_id),
        "title": str(position.get("question") or snapshot.get("question") or market_id),
        "outcome": outcome,
        "price": round(float(exit_price), 4),
        "shares": round(exit_shares, 8),
        "open_shares_at_creation": round(open_shares, 8),
        "estimated_proceeds": round(proceeds, 4),
        "estimated_cost_reduction": round(cost_portion, 4),
        "estimated_realized_pnl": round(realized, 4),
        "exit_reason": str(reason or "manual paper exit review"),
        "position_status": status_hint,
        "exit_plan": plan,
        "position_snapshot": position,
        "market_snapshot": snapshot,
        "checklist": checklist,
        "blockers": blockers,
        "execution_allowed": execution_allowed,
        "operator_note": operator_note,
        "operator_decision": "pending",
        "paper_trade_id": None,
        "guardrails": [
            "Paper exit ticket only; no wallet or live trading integration is present.",
            "The ticket can only execute a simulated paper sell after an admin/operator action.",
            "Re-check the live market, resolution state, and thesis before closing the simulated position.",
        ],
    }


def create_exit_ticket(
    market_id: str,
    *,
    outcome: str = "YES",
    market: dict[str, Any] | None = None,
    shares: Any = None,
    price: Any = None,
    reason: str = "manual paper exit review",
    created_by: str = "local",
    operator_note: str = "",
) -> dict[str, Any]:
    ticket = build_exit_ticket(
        market_id,
        outcome=outcome,
        market=market,
        shares=shares,
        price=price,
        reason=reason,
        created_by=created_by,
        operator_note=operator_note,
    )
    rows = load_exit_tickets()
    rows.append(ticket)
    save_exit_tickets(rows)
    return ticket


def update_exit_ticket(ticket_id: str, **updates: Any) -> dict[str, Any]:
    rows = load_exit_tickets()
    for idx, row in enumerate(rows):
        if str(row.get("ticket_id")) == str(ticket_id):
            if "status" in updates and updates["status"] is not None:
                status = str(updates["status"])
                if status not in VALID_EXIT_STATUSES:
                    raise ValueError(f"Invalid exit ticket status: {status}")
                row["status"] = status
            if "operator_note" in updates and updates["operator_note"] is not None:
                row["operator_note"] = str(updates["operator_note"])
            if "operator_decision" in updates and updates["operator_decision"] is not None:
                row["operator_decision"] = str(updates["operator_decision"])
            if "paper_trade_id" in updates and updates["paper_trade_id"] is not None:
                row["paper_trade_id"] = str(updates["paper_trade_id"])
            if "execution_result" in updates and updates["execution_result"] is not None:
                row["execution_result"] = updates["execution_result"]
            row["updated_at"] = _now()
            rows[idx] = row
            save_exit_tickets(rows)
            return row
    raise ValueError("Exit ticket not found")


def delete_exit_ticket(ticket_id: str) -> bool:
    rows = load_exit_tickets()
    kept = [row for row in rows if str(row.get("ticket_id")) != str(ticket_id)]
    if len(kept) == len(rows):
        return False
    save_exit_tickets(kept)
    return True


def executable_exit_snapshot(ticket: dict[str, Any]) -> dict[str, Any]:
    snapshot = ticket.get("market_snapshot") if isinstance(ticket.get("market_snapshot"), dict) else {}
    if snapshot:
        snapshot = dict(snapshot)
    else:
        snapshot = {}
    market_id = str(ticket.get("market_id") or snapshot.get("id") or "")
    outcome = str(ticket.get("outcome") or "YES").upper()
    price = _safe_float(ticket.get("price"), 0.5)
    snapshot["id"] = str(snapshot.get("id") or market_id)
    snapshot["market_id"] = str(snapshot.get("market_id") or market_id)
    snapshot["question"] = snapshot.get("question") or ticket.get("title") or market_id
    outcomes = snapshot.get("outcomes")
    if not outcomes:
        snapshot["outcomes"] = [{"name": outcome, "price": round(price, 4)}]
    return snapshot
