from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from .paper_playbooks import evaluate_market_playbooks, list_playbook_decisions
from .paper_risk_budget import build_market_risk_budget, build_risk_budget
from .paper_trading import load_portfolio
from .readiness_engine import build_readiness_result
from .risk import check_paper_buy
from .trade_tickets import get_trade_ticket, list_trade_tickets
from .market_data import build_execution_quality_simulation, latest_market_snapshot

ACTIVE_PREFLIGHT_STATUSES = {"draft_review", "paper_ready", "blocked"}
POSITIVE_PLAYBOOK_STATUSES = {"assigned", "approved", "completed", "paper_ready"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any) -> bool:
    return bool(value)


def _market_id(row: dict[str, Any]) -> str:
    return str(row.get("market_id") or row.get("id") or row.get("conditionId") or row.get("slug") or "")


def _title(row: dict[str, Any]) -> str:
    return str(row.get("question") or row.get("title") or row.get("name") or _market_id(row) or "Untitled market")


def _price_from_row(row: dict[str, Any], default: float = 0.5) -> float:
    price = _safe_float(row.get("market_probability", row.get("price", row.get("yes_price", default))), default)
    return max(0.0001, min(0.9999, price))


def _snapshot_from_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    snapshot = ticket.get("market_snapshot") if isinstance(ticket.get("market_snapshot"), dict) else {}
    mid = str(ticket.get("market_id") or _market_id(snapshot) or "")
    title = str(ticket.get("title") or _title(snapshot) or mid or "Untitled market")
    return {
        **snapshot,
        "id": mid,
        "market_id": mid,
        "question": title,
        "title": title,
        "liquidity": _safe_float(snapshot.get("liquidity"), 0.0),
        "volume_24hr": _safe_float(snapshot.get("volume_24hr", snapshot.get("volume24hr")), 0.0),
    }


def _snapshot_from_opportunity(opportunity: dict[str, Any], ticket: dict[str, Any]) -> dict[str, Any]:
    if not opportunity:
        return _snapshot_from_ticket(ticket)
    mid = _market_id(opportunity) or str(ticket.get("market_id") or "")
    title = _title(opportunity) or str(ticket.get("title") or mid or "Untitled market")
    return {
        **opportunity,
        "id": mid,
        "market_id": mid,
        "question": title,
        "title": title,
        "liquidity": _safe_float(opportunity.get("liquidity"), 0.0),
        "volume_24hr": _safe_float(opportunity.get("volume_24hr", opportunity.get("volume24hr")), 0.0),
    }


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _age_hours(value: Any) -> float | None:
    dt = _parse_dt(value)
    if not dt:
        return None
    delta = datetime.now(timezone.utc) - dt
    return round(max(delta.total_seconds(), 0.0) / 3600.0, 2)


def _check(name: str, passed: bool, detail: str, *, severity: str = "blocker", kind: str = "process") -> dict[str, Any]:
    blocking = severity == "blocker" and not passed
    return {
        "name": name,
        "passed": bool(passed),
        "severity": severity,
        "kind": kind,
        "blocking": blocking,
        "detail": detail,
    }


def _latest_positive_playbook_decision(market_id: str) -> dict[str, Any] | None:
    for row in list_playbook_decisions(limit=100, market_id=market_id):
        if str(row.get("status") or "") in POSITIVE_PLAYBOOK_STATUSES:
            return row
    return None


def build_ticket_preflight(
    ticket: dict[str, Any] | str,
    *,
    opportunity: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
    strict_playbook: bool = False,
    include_budget: bool = True,
) -> dict[str, Any]:
    """Build a deterministic paper-only execution preflight for one entry ticket.

    The preflight is intentionally local. It re-checks the ticket, readiness, paper
    risk, paper budget, and playbook discipline without connecting a wallet or
    placing any real order.
    """
    if isinstance(ticket, str):
        found = get_trade_ticket(ticket)
        if not found:
            raise ValueError("Trade ticket not found")
        ticket = found

    mid = str(ticket.get("market_id") or "")
    snapshot = _snapshot_from_opportunity(opportunity or {}, ticket)
    price = _price_from_row(snapshot, _safe_float(ticket.get("price"), 0.5))
    stake = round(_safe_float(ticket.get("stake"), 0.0), 4)
    outcome = str(ticket.get("outcome") or "YES").upper()
    readiness = readiness or (build_readiness_result(snapshot) if opportunity else ticket.get("readiness") or {})
    risk = check_paper_buy(snapshot, load_portfolio(), stake=stake, price=price, outcome=outcome)

    budget_detail = build_market_risk_budget(mid, [snapshot]) if include_budget and mid else {}
    budget_item = budget_detail.get("item") or {}
    budget_state = str(budget_item.get("budget_state") or budget_detail.get("summary", {}).get("budget_state") or "ok")
    budget_room_after = _safe_float(budget_item.get("market_exposure_remaining_after_pending", budget_detail.get("market_exposure_remaining")), 0.0)

    decision = _latest_positive_playbook_decision(mid) if mid else None
    playbook_fit = None
    if opportunity:
        try:
            playbook_fit = evaluate_market_playbooks(snapshot, readiness=readiness).get("best_fit")
        except Exception:
            playbook_fit = None

    status = str(ticket.get("status") or "")
    execution_allowed = _safe_bool(ticket.get("execution_allowed"))
    age = _age_hours(ticket.get("updated_at") or ticket.get("created_at"))

    checks: list[dict[str, Any]] = [
        _check("Entry ticket status", status == "paper_ready", f"status={status or 'unknown'}", kind="ticket"),
        _check("Ticket execution flag", execution_allowed, "execution_allowed=true" if execution_allowed else "execution_allowed=false", kind="ticket"),
        _check("Stake present", stake > 0, f"stake={stake:g}", kind="ticket"),
        _check("Readiness gate", bool(readiness.get("paper_trade_ready")), str(readiness.get("status") or "unknown"), kind="readiness"),
        _check("Paper risk check", bool(risk.get("approved")), "approved" if risk.get("approved") else "blocked", kind="risk"),
        _check("Risk budget not blocked", budget_state != "blocked", f"budget_state={budget_state}; market room after tickets=${budget_room_after:,.2f}", kind="risk_budget"),
    ]

    if budget_state in {"tight", "watch"}:
        checks.append(_check("Risk budget comfort", True, f"budget_state={budget_state}; review concentration before execution", severity="warning", kind="risk_budget"))

    if decision:
        checks.append(_check("Playbook decision present", True, f"{decision.get('playbook_name') or decision.get('playbook_id')} · {decision.get('status')}", severity="info", kind="playbook"))
    else:
        checks.append(_check("Playbook decision present", not strict_playbook, "No assigned/approved/completed playbook decision found for this market.", severity="blocker" if strict_playbook else "warning", kind="playbook"))

    if playbook_fit:
        checks.append(_check("Current playbook fit", bool(playbook_fit.get("matched")), f"{playbook_fit.get('playbook_name')} · fit={_safe_float(playbook_fit.get('fit_score')) * 100:.1f}%", severity="warning", kind="playbook"))

    if age is not None:
        checks.append(_check("Ticket recency", age <= 72.0, f"updated {age:.1f}h ago", severity="blocker" if age > 72.0 else "info", kind="staleness"))
        if 24.0 < age <= 72.0:
            checks.append(_check("Fresh price review", True, f"ticket is {age:.1f}h old; re-check price/resolution before paper execution", severity="warning", kind="staleness"))

    for failure in risk.get("blocking_failures") or []:
        checks.append(_check("Risk blocker detail", False, str(failure.get("detail") or failure.get("name") or failure), kind="risk"))
    for warning in risk.get("warnings") or []:
        checks.append(_check("Risk warning detail", True, str(warning.get("detail") or warning.get("name") or warning), severity="warning", kind="risk"))

    market_data_quality: dict[str, Any] | None = None
    snapshot_row = latest_market_snapshot(market_id=mid)
    estimated_size = stake / price if price > 0 else 0.0
    if not snapshot_row:
        checks.append(_check("Market-data snapshot present", True, "No local market-data snapshot found; record a fixture/manual snapshot for execution-quality estimates.", severity="warning", kind="market_data"))
    else:
        market_data_quality = build_execution_quality_simulation(
            side="BUY",
            market_id=mid,
            token_id=str(snapshot_row.get("token_id") or ""),
            price=price,
            size=estimated_size,
            order_type="limit",
            time_in_force="GTC",
            snapshot_id=str(snapshot_row.get("snapshot_id") or ""),
            source_ticket_id=str(ticket.get("ticket_id") or ""),
        )
        state = str(market_data_quality.get("state") or "unknown")
        blocking_state = state in {"blocked_by_closed_market", "blocked_by_not_accepting_orders", "invalid_snapshot"}
        checks.append(_check("Market-data quality", not blocking_state, f"execution_quality={state}; snapshot={market_data_quality.get('snapshot_id') or 'missing'}", severity="blocker" if blocking_state else "warning" if state != "quality_pass" else "info", kind="market_data"))
        for blocker in list(market_data_quality.get("blockers") or [])[:3]:
            severity = "blocker" if "closed" in str(blocker).lower() or "not accepting" in str(blocker).lower() or "invalid" in str(blocker).lower() else "warning"
            checks.append(_check("Market-data quality detail", severity != "blocker", str(blocker), severity=severity, kind="market_data"))
        for warning in list(market_data_quality.get("warnings") or [])[:3]:
            checks.append(_check("Market-data quality warning", True, str(warning), severity="warning", kind="market_data"))

    blockers = [row for row in checks if row.get("blocking")]
    warnings = [row for row in checks if row.get("severity") == "warning"]
    infos = [row for row in checks if row.get("severity") == "info"]
    approved = not blockers
    preflight_status = "approved" if approved and not warnings else "approved_with_warnings" if approved else "blocked"

    return {
        "version": "0.4.3-paper-preflight-v1",
        "mode": "paper_preflight_gate_v043",
        "ticket_id": ticket.get("ticket_id"),
        "market_id": mid,
        "title": ticket.get("title") or _title(snapshot),
        "outcome": outcome,
        "stake": stake,
        "price": round(price, 4),
        "status": preflight_status,
        "approved": approved,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "info_count": len(infos),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "readiness": readiness,
        "risk": risk,
        "risk_budget": {"detail": budget_detail, "state": budget_state},
        "playbook_decision": decision,
        "playbook_fit": playbook_fit,
        "market_data_quality": market_data_quality,
        "ticket_snapshot": ticket,
        "guardrail": "Paper preflight gate only. It does not place live orders, connect a wallet, sign messages, or provide investment advice.",
    }


def build_preflight_board(
    tickets: list[dict[str, Any]] | None = None,
    *,
    limit: int = 100,
    status: str | None = None,
    strict_playbook: bool = False,
    opportunities_by_market: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if tickets is None:
        tickets = list_trade_tickets(limit=10000)
    if status:
        tickets = [row for row in tickets if str(row.get("status") or "") == status]
    else:
        tickets = [row for row in tickets if str(row.get("status") or "") in ACTIVE_PREFLIGHT_STATUSES]

    opportunities_by_market = opportunities_by_market or {}
    rows: list[dict[str, Any]] = []
    for ticket in tickets[: max(limit, 1)]:
        mid = str(ticket.get("market_id") or "")
        opportunity = opportunities_by_market.get(mid)
        try:
            preflight = build_ticket_preflight(ticket, opportunity=opportunity, strict_playbook=strict_playbook)
        except Exception as exc:
            preflight = {
                "version": "0.4.3-paper-preflight-v1",
                "ticket_id": ticket.get("ticket_id"),
                "market_id": mid,
                "title": ticket.get("title") or mid,
                "status": "blocked",
                "approved": False,
                "blocker_count": 1,
                "warning_count": 0,
                "checks": [],
                "blockers": [_check("Preflight build", False, str(exc))],
                "warnings": [],
                "ticket_snapshot": ticket,
                "guardrail": "Paper preflight gate only.",
            }
        rows.append(preflight)

    rows.sort(key=lambda row: (row.get("approved", False), -int(row.get("blocker_count") or 0), -int(row.get("warning_count") or 0)), reverse=True)
    return {
        "summary": summarize_preflight(rows),
        "items": rows[:limit],
        "guardrail": "Paper preflight review only. This report does not place orders, connect a wallet, or provide investment advice.",
    }


def summarize_preflight(rows: list[dict[str, Any]]) -> dict[str, Any]:
    approved = [row for row in rows if row.get("approved")]
    blocked = [row for row in rows if not row.get("approved")]
    with_warnings = [row for row in approved if int(row.get("warning_count") or 0) > 0]
    total_blockers = sum(int(row.get("blocker_count") or 0) for row in rows)
    total_warnings = sum(int(row.get("warning_count") or 0) for row in rows)
    return {
        "count": len(rows),
        "approved": len(approved),
        "approved_with_warnings": len(with_warnings),
        "blocked": len(blocked),
        "total_blockers": total_blockers,
        "total_warnings": total_warnings,
        "strict_playbook_available": True,
        "guardrail": "Preflight approvals are local paper-simulation checks only and still require human action.",
    }


def preflight_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_preflight_board(limit=100)
    alerts: list[dict[str, Any]] = []
    for row in board.get("items") or []:
        if row.get("approved"):
            if int(row.get("warning_count") or 0) > 0:
                alerts.append(
                    {
                        "level": "info",
                        "kind": "paper_preflight_warning",
                        "title": "Paper preflight has warnings",
                        "market_id": row.get("market_id"),
                        "question": row.get("title"),
                        "detail": f"Ticket {row.get('ticket_id')} is approved with {row.get('warning_count')} warnings.",
                        "recommended_action": "review_preflight_before_paper_execution",
                    }
                )
            continue
        alerts.append(
            {
                "level": "warning",
                "kind": "paper_preflight_blocked",
                "title": "Paper entry ticket blocked by preflight",
                "market_id": row.get("market_id"),
                "question": row.get("title"),
                "detail": f"Ticket {row.get('ticket_id')} has {row.get('blocker_count')} blockers.",
                "recommended_action": "open_preflight_review",
            }
        )
    return alerts


def preflight_to_csv(rows: list[dict[str, Any]]) -> str:
    fieldnames = [
        "ticket_id",
        "market_id",
        "title",
        "outcome",
        "stake",
        "price",
        "status",
        "approved",
        "blocker_count",
        "warning_count",
        "market_data_state",
        "blockers",
        "warnings",
    ]
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                **row,
                "market_data_state": (row.get("market_data_quality") or {}).get("state", "missing"),
                "blockers": " | ".join(str(item.get("detail") or item.get("name") or item) for item in row.get("blockers") or []),
                "warnings": " | ".join(str(item.get("detail") or item.get("name") or item) for item in row.get("warnings") or []),
            }
        )
    return handle.getvalue()
