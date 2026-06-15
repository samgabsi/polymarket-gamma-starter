from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR, settings
from .paper_trading import load_portfolio
from .risk import check_paper_buy

TICKETS_PATH = DATA_DIR / "paper" / "trade_tickets.json"
VALID_STATUSES = {
    "draft_review",
    "paper_ready",
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


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _norm(value: Any, default: float = 0.0) -> float:
    raw = _num(value, default)
    if abs(raw) > 1:
        raw = raw / 100.0
    return max(0.0, min(1.0, raw))


def _edge(value: Any, default: float = 0.0) -> float:
    raw = _num(value, default)
    if abs(raw) > 1:
        raw = raw / 100.0
    return max(-1.0, min(1.0, raw))


def _market_id(payload: dict[str, Any]) -> str:
    return str(payload.get("market_id") or payload.get("id") or payload.get("conditionId") or payload.get("slug") or "")


def _title(payload: dict[str, Any]) -> str:
    return str(payload.get("question") or payload.get("title") or payload.get("name") or _market_id(payload) or "Untitled market")


def _price_from_opportunity(opportunity: dict[str, Any]) -> float:
    price = _num(
        opportunity.get("market_probability", opportunity.get("price", opportunity.get("yes_price"))),
        0.5,
    )
    return max(0.0001, min(0.9999, price))


def _suggested_stake(readiness: dict[str, Any], edge_value: float, risk_approved: bool) -> float:
    max_stake = max(1.0, float(settings.paper_max_stake_per_trade))
    score = _norm(readiness.get("readiness_score"), 0.0)
    if not readiness.get("paper_trade_ready") or not risk_approved:
        return round(min(max_stake, max(10.0, max_stake * 0.10)), 2)
    if score >= 0.80 and edge_value >= 0.06:
        return round(min(max_stake, 150.0), 2)
    if score >= 0.70 and edge_value >= 0.04:
        return round(min(max_stake, 100.0), 2)
    return round(min(max_stake, 50.0), 2)


def _market_snapshot(opportunity: dict[str, Any]) -> dict[str, Any]:
    mid = _market_id(opportunity)
    title = _title(opportunity)
    return {
        "id": mid,
        "market_id": mid,
        "question": title,
        "title": title,
        "category": opportunity.get("category") or "",
        "liquidity": _num(opportunity.get("liquidity"), 0.0),
        "volume_24hr": _num(opportunity.get("volume_24hr", opportunity.get("volume24hr")), 0.0),
        "polymarket_url": opportunity.get("url") or opportunity.get("polymarket_url") or opportunity.get("polymarket_search_url"),
        "polymarket_search_url": opportunity.get("polymarket_search_url"),
    }


def load_trade_tickets() -> list[dict[str, Any]]:
    rows = _read_json(TICKETS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_trade_tickets(rows: list[dict[str, Any]]) -> None:
    _write_json(TICKETS_PATH, rows)


def list_trade_tickets(limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    rows = list(reversed(load_trade_tickets()))
    if status:
        rows = [r for r in rows if str(r.get("status")) == status]
    return rows[:limit]


def get_trade_ticket(ticket_id: str) -> dict[str, Any] | None:
    for row in load_trade_tickets():
        if str(row.get("ticket_id")) == str(ticket_id):
            return row
    return None


def summarize_trade_tickets(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load_trade_tickets()
    by_status: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "count": len(rows),
        "by_status": by_status,
        "paper_ready": by_status.get("paper_ready", 0),
        "blocked": by_status.get("blocked", 0),
        "paper_executed": by_status.get("paper_executed", 0),
        "note": "Tickets are local paper-trading preparation records only. They do not place live trades.",
    }


def build_trade_ticket(
    opportunity: dict[str, Any],
    readiness: dict[str, Any],
    *,
    stake: float | None = None,
    outcome: str = "YES",
    created_by: str = "local",
    operator_note: str = "",
) -> dict[str, Any]:
    mid = _market_id(opportunity)
    title = _title(opportunity)
    price = _price_from_opportunity(opportunity)
    edge_value = _edge(opportunity.get("edge", opportunity.get("edge_percent", readiness.get("edge", 0.0))))
    snapshot = _market_snapshot(opportunity)

    first_pass_stake = float(stake) if stake is not None else min(float(settings.paper_max_stake_per_trade), 50.0)
    first_risk = check_paper_buy(snapshot, load_portfolio(), stake=first_pass_stake, price=price, outcome=outcome)
    final_stake = round(float(stake), 2) if stake is not None else _suggested_stake(readiness, edge_value, bool(first_risk.get("approved")))
    risk = check_paper_buy(snapshot, load_portfolio(), stake=final_stake, price=price, outcome=outcome)

    blockers = list(readiness.get("blockers") or [])
    blockers.extend(item.get("detail", item.get("name", "risk failure")) for item in risk.get("blocking_failures", []))

    checklist = [
        {"name": "Positive model edge", "passed": edge_value > 0, "detail": f"edge={edge_value * 100:+.2f}%"},
        {"name": "Readiness gate passed", "passed": bool(readiness.get("paper_trade_ready")), "detail": readiness.get("status", "unknown")},
        {"name": "Evidence score >= 45%", "passed": _norm(readiness.get("evidence_score"), 0.0) >= 0.45, "detail": f"{_norm(readiness.get('evidence_score'), 0.0) * 100:.1f}%"},
        {"name": "Thesis score >= 40%", "passed": _norm(readiness.get("thesis_score"), 0.0) >= 0.40, "detail": f"{_norm(readiness.get('thesis_score'), 0.0) * 100:.1f}%"},
        {"name": "Paper risk approved", "passed": bool(risk.get("approved")), "detail": "approved" if risk.get("approved") else "blocked"},
        {"name": "Human review required", "passed": False, "detail": "Operator must review thesis, invalidation, price, and stake before executing a paper trade."},
    ]

    execution_allowed = bool(readiness.get("paper_trade_ready")) and bool(risk.get("approved"))
    status = "paper_ready" if execution_allowed else "blocked" if blockers else "draft_review"

    return {
        "ticket_id": f"pt_{uuid4().hex[:12]}",
        "version": "0.3.4-paper-ticket-v1",
        "created_at": _now(),
        "updated_at": _now(),
        "created_by": created_by,
        "status": status,
        "market_id": mid,
        "title": title,
        "outcome": str(outcome).upper(),
        "price": round(price, 4),
        "stake": final_stake,
        "estimated_shares": round(final_stake / price, 8) if price > 0 else 0.0,
        "readiness": readiness,
        "risk": risk,
        "checklist": checklist,
        "blockers": blockers,
        "warnings": risk.get("warnings", []),
        "execution_allowed": execution_allowed,
        "operator_note": operator_note,
        "operator_decision": "pending",
        "market_snapshot": snapshot,
        "paper_trade_id": None,
        "guardrails": [
            "Paper ticket only; no wallet or live trading integration is present.",
            "Do not execute even a paper trade until the human-review checklist is satisfied.",
            "Re-check market price and resolution rules before using this ticket.",
        ],
    }


def create_trade_ticket(
    opportunity: dict[str, Any],
    readiness: dict[str, Any],
    *,
    stake: float | None = None,
    outcome: str = "YES",
    created_by: str = "local",
    operator_note: str = "",
) -> dict[str, Any]:
    ticket = build_trade_ticket(
        opportunity,
        readiness,
        stake=stake,
        outcome=outcome,
        created_by=created_by,
        operator_note=operator_note,
    )
    rows = load_trade_tickets()
    rows.append(ticket)
    save_trade_tickets(rows)
    return ticket


def update_trade_ticket(ticket_id: str, **updates: Any) -> dict[str, Any]:
    rows = load_trade_tickets()
    for idx, row in enumerate(rows):
        if str(row.get("ticket_id")) == str(ticket_id):
            if "status" in updates and updates["status"] is not None:
                status = str(updates["status"])
                if status not in VALID_STATUSES:
                    raise ValueError(f"Invalid ticket status: {status}")
                row["status"] = status
            if "operator_note" in updates and updates["operator_note"] is not None:
                row["operator_note"] = str(updates["operator_note"])
            if "operator_decision" in updates and updates["operator_decision"] is not None:
                row["operator_decision"] = str(updates["operator_decision"])
            if "paper_trade_id" in updates and updates["paper_trade_id"] is not None:
                row["paper_trade_id"] = str(updates["paper_trade_id"])
            row["updated_at"] = _now()
            rows[idx] = row
            save_trade_tickets(rows)
            return row
    raise ValueError("Trade ticket not found")


def delete_trade_ticket(ticket_id: str) -> bool:
    rows = load_trade_tickets()
    kept = [row for row in rows if str(row.get("ticket_id")) != str(ticket_id)]
    if len(kept) == len(rows):
        return False
    save_trade_tickets(kept)
    return True
