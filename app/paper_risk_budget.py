from __future__ import annotations

import csv
import io
from typing import Any

from .paper_positions import position_alerts
from .paper_trading import load_portfolio, summarize_portfolio
from .risk import RiskLimits, market_exposure, open_position_count, risk_limits_payload, total_exposure
from .trade_tickets import list_trade_tickets

ACTIVE_TICKET_STATUSES = {"draft_review", "paper_ready"}
BLOCKING_TICKET_STATUSES = {"paper_ready"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100.0, 2)


def _market_id(row: dict[str, Any]) -> str:
    return str(row.get("market_id") or row.get("id") or row.get("conditionId") or row.get("slug") or "")


def _question(row: dict[str, Any]) -> str:
    return str(row.get("question") or row.get("title") or row.get("name") or _market_id(row) or "Untitled market")


def _budget_state(utilization_percent: float, *, hard_block: bool = False) -> str:
    if hard_block or utilization_percent >= 100:
        return "blocked"
    if utilization_percent >= 85:
        return "tight"
    if utilization_percent >= 65:
        return "watch"
    return "ok"


def _pending_ticket_rows(statuses: set[str] | None = None) -> list[dict[str, Any]]:
    rows = list_trade_tickets(limit=10000)
    if statuses:
        rows = [row for row in rows if str(row.get("status") or "") in statuses]
    return rows


def _ticket_summary_by_market(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        mid = str(row.get("market_id") or "")
        if not mid:
            continue
        item = grouped.setdefault(
            mid,
            {
                "market_id": mid,
                "question": row.get("question") or mid,
                "pending_ticket_count": 0,
                "paper_ready_ticket_count": 0,
                "draft_ticket_count": 0,
                "pending_ticket_stake": 0.0,
                "paper_ready_stake": 0.0,
                "latest_ticket_id": row.get("ticket_id"),
            },
        )
        stake = _safe_float(row.get("stake"), 0.0)
        status = str(row.get("status") or "")
        item["pending_ticket_count"] += 1
        item["pending_ticket_stake"] += stake
        if status == "paper_ready":
            item["paper_ready_ticket_count"] += 1
            item["paper_ready_stake"] += stake
        elif status == "draft_review":
            item["draft_ticket_count"] += 1
        item["latest_ticket_id"] = row.get("ticket_id") or item.get("latest_ticket_id")
    for item in grouped.values():
        item["pending_ticket_stake"] = round(float(item.get("pending_ticket_stake") or 0.0), 4)
        item["paper_ready_stake"] = round(float(item.get("paper_ready_stake") or 0.0), 4)
    return grouped


def build_risk_budget(
    markets: list[dict[str, Any]] | None = None,
    *,
    limit: int = 100,
    market_id: str | None = None,
) -> dict[str, Any]:
    """Build a local paper risk-budget report.

    This does not grant live-trading permissions. It is a deterministic review
    view over local paper state, open positions, and pending entry tickets.
    """
    portfolio = load_portfolio()
    portfolio_summary = summarize_portfolio(markets or [])
    limits = RiskLimits()
    limits_payload = risk_limits_payload(limits)

    pending_tickets = _pending_ticket_rows(ACTIVE_TICKET_STATUSES)
    ticket_groups = _ticket_summary_by_market(pending_tickets)
    pending_stake = round(sum(_safe_float(row.get("stake"), 0.0) for row in pending_tickets), 4)
    paper_ready_stake = round(sum(_safe_float(row.get("stake"), 0.0) for row in pending_tickets if str(row.get("status")) in BLOCKING_TICKET_STATUSES), 4)

    exposure = total_exposure(portfolio)
    open_positions = open_position_count(portfolio)
    cash = _safe_float(portfolio_summary.get("cash"), _safe_float(portfolio.get("cash"), 0.0))
    total_budget = float(limits.max_total_exposure)
    remaining = round(max(total_budget - exposure, 0.0), 4)
    remaining_after_pending = round(max(total_budget - exposure - pending_stake, 0.0), 4)
    open_slots_remaining = max(int(limits.max_open_positions) - int(open_positions), 0)

    alerts = position_alerts(portfolio_summary)
    alert_counts_by_market: dict[str, int] = {}
    warning_counts_by_market: dict[str, int] = {}
    for alert in alerts:
        mid = str(alert.get("market_id") or "")
        if not mid:
            continue
        alert_counts_by_market[mid] = alert_counts_by_market.get(mid, 0) + 1
        if str(alert.get("level")) == "warning":
            warning_counts_by_market[mid] = warning_counts_by_market.get(mid, 0) + 1

    market_rows: dict[str, dict[str, Any]] = {}
    for pos in portfolio_summary.get("open_positions") or []:
        mid = str(pos.get("market_id") or "")
        if not mid:
            continue
        row = market_rows.setdefault(
            mid,
            {
                "market_id": mid,
                "question": pos.get("question") or mid,
                "outcomes": [],
                "open_position_count": 0,
                "open_cost_basis": 0.0,
                "open_market_value": 0.0,
                "unrealized_pnl": 0.0,
                "pending_ticket_count": 0,
                "pending_ticket_stake": 0.0,
                "paper_ready_ticket_count": 0,
                "paper_ready_stake": 0.0,
                "alert_count": 0,
                "warning_count": 0,
            },
        )
        row["open_position_count"] += 1
        row["open_cost_basis"] += _safe_float(pos.get("cost_basis"), 0.0)
        row["open_market_value"] += _safe_float(pos.get("market_value"), 0.0)
        row["unrealized_pnl"] += _safe_float(pos.get("unrealized_pnl"), 0.0)
        row["outcomes"].append(
            {
                "outcome": pos.get("outcome"),
                "shares": pos.get("shares"),
                "avg_price": pos.get("avg_price"),
                "current_price": pos.get("current_price"),
                "position_status": pos.get("position_status"),
                "exit_plan": pos.get("exit_plan") if isinstance(pos.get("exit_plan"), dict) else {},
            }
        )

    for mid, tickets in ticket_groups.items():
        row = market_rows.setdefault(
            mid,
            {
                "market_id": mid,
                "question": tickets.get("question") or mid,
                "outcomes": [],
                "open_position_count": 0,
                "open_cost_basis": 0.0,
                "open_market_value": 0.0,
                "unrealized_pnl": 0.0,
                "pending_ticket_count": 0,
                "pending_ticket_stake": 0.0,
                "paper_ready_ticket_count": 0,
                "paper_ready_stake": 0.0,
                "alert_count": 0,
                "warning_count": 0,
            },
        )
        row["pending_ticket_count"] = tickets.get("pending_ticket_count", 0)
        row["pending_ticket_stake"] = tickets.get("pending_ticket_stake", 0.0)
        row["paper_ready_ticket_count"] = tickets.get("paper_ready_ticket_count", 0)
        row["paper_ready_stake"] = tickets.get("paper_ready_stake", 0.0)
        row["latest_ticket_id"] = tickets.get("latest_ticket_id")

    for mid, row in market_rows.items():
        open_cost = round(_safe_float(row.get("open_cost_basis"), 0.0), 4)
        pending = round(_safe_float(row.get("pending_ticket_stake"), 0.0), 4)
        combined = round(open_cost + pending, 4)
        room = round(max(float(limits.max_market_exposure) - open_cost, 0.0), 4)
        room_after_pending = round(max(float(limits.max_market_exposure) - combined, 0.0), 4)
        util = _pct(open_cost, float(limits.max_market_exposure))
        combined_util = _pct(combined, float(limits.max_market_exposure))
        row.update(
            {
                "open_cost_basis": open_cost,
                "open_market_value": round(_safe_float(row.get("open_market_value"), 0.0), 4),
                "unrealized_pnl": round(_safe_float(row.get("unrealized_pnl"), 0.0), 4),
                "pending_ticket_stake": pending,
                "paper_ready_stake": round(_safe_float(row.get("paper_ready_stake"), 0.0), 4),
                "combined_open_and_pending": combined,
                "market_exposure_remaining": room,
                "market_exposure_remaining_after_pending": room_after_pending,
                "market_utilization_percent": util,
                "combined_market_utilization_percent": combined_util,
                "budget_state": _budget_state(combined_util, hard_block=room_after_pending <= 0 and combined > 0),
                "alert_count": alert_counts_by_market.get(mid, 0),
                "warning_count": warning_counts_by_market.get(mid, 0),
            }
        )

    rows = list(market_rows.values())
    if market_id:
        rows = [row for row in rows if str(row.get("market_id")) == str(market_id)]
    rows.sort(key=lambda row: (_safe_float(row.get("combined_open_and_pending"), 0.0), _safe_float(row.get("warning_count"), 0.0)), reverse=True)

    total_util = _pct(exposure, total_budget)
    pending_util = _pct(exposure + pending_stake, total_budget)
    flags: list[dict[str, Any]] = []
    if total_util >= 85:
        flags.append({"level": "warning", "kind": "total_budget_tight", "detail": f"Open paper exposure uses {total_util:.1f}% of configured total budget."})
    if pending_stake and exposure + pending_stake > total_budget:
        flags.append({"level": "warning", "kind": "pending_tickets_exceed_budget", "detail": "Open exposure plus pending entry-ticket stake exceeds total paper budget."})
    if open_slots_remaining <= 0:
        flags.append({"level": "warning", "kind": "no_position_slots", "detail": "Configured open-position slots are fully used."})
    for row in rows:
        if row.get("budget_state") in {"tight", "blocked"}:
            flags.append(
                {
                    "level": "warning" if row.get("budget_state") == "blocked" else "info",
                    "kind": f"market_budget_{row.get('budget_state')}",
                    "market_id": row.get("market_id"),
                    "question": row.get("question"),
                    "detail": f"Combined open + pending exposure is {row.get('combined_market_utilization_percent')}% of per-market paper budget.",
                }
            )

    allocatable_now = round(min(float(limits.max_stake_per_trade), cash, remaining), 4)
    if open_slots_remaining <= 0:
        allocatable_now = 0.0
    summary = {
        "mode": "paper_only_risk_budget_v042",
        "open_exposure": exposure,
        "cash": round(cash, 4),
        "paper_equity": portfolio_summary.get("equity"),
        "total_budget": round(total_budget, 4),
        "total_budget_remaining": remaining,
        "total_budget_remaining_after_pending": remaining_after_pending,
        "total_utilization_percent": total_util,
        "open_plus_pending_utilization_percent": pending_util,
        "open_position_count": open_positions,
        "open_position_limit": int(limits.max_open_positions),
        "open_position_slots_remaining": open_slots_remaining,
        "pending_ticket_count": len(pending_tickets),
        "pending_ticket_stake": pending_stake,
        "paper_ready_ticket_stake": paper_ready_stake,
        "allocatable_next_trade_now": allocatable_now,
        "market_count": len(rows),
        "flag_count": len(flags),
        "budget_state": _budget_state(pending_util, hard_block=(remaining_after_pending <= 0 and pending_stake > 0)),
    }
    return {
        "summary": summary,
        "limits": limits_payload,
        "items": rows[:limit],
        "flags": flags[: max(limit, 100)],
        "guardrail": "Paper risk-budget review only. This report does not place orders, connect a wallet, or provide investment advice.",
    }


def build_market_risk_budget(market_id: str, markets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    report = build_risk_budget(markets, limit=10000, market_id=market_id)
    item = report.get("items", [None])[0] if report.get("items") else None
    portfolio = load_portfolio()
    limits = RiskLimits()
    open_exposure = market_exposure(portfolio, market_id)
    return {
        "market_id": market_id,
        "item": item,
        "market_open_exposure": open_exposure,
        "market_exposure_remaining": round(max(float(limits.max_market_exposure) - open_exposure, 0.0), 4),
        "summary": report.get("summary", {}),
        "limits": report.get("limits", {}),
        "flags": [row for row in report.get("flags", []) if str(row.get("market_id") or "") in {"", str(market_id)}],
        "guardrail": report.get("guardrail"),
    }


def risk_budget_alerts(report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    report = report or build_risk_budget(limit=100)
    alerts: list[dict[str, Any]] = []
    summary = report.get("summary") or {}
    if summary.get("budget_state") in {"tight", "blocked"}:
        alerts.append(
            {
                "level": "warning",
                "kind": "paper_risk_budget_tight",
                "title": "Paper risk budget is tight",
                "detail": f"Open + pending paper exposure uses {summary.get('open_plus_pending_utilization_percent', 0)}% of total budget.",
                "recommended_action": "review_risk_budget_before_new_tickets",
            }
        )
    for flag in report.get("flags") or []:
        if not flag.get("market_id"):
            continue
        alerts.append(
            {
                "level": flag.get("level") or "info",
                "kind": flag.get("kind") or "paper_risk_budget_flag",
                "title": "Paper risk-budget flag",
                "market_id": flag.get("market_id"),
                "question": flag.get("question"),
                "detail": flag.get("detail"),
                "recommended_action": "open_risk_budget_review",
            }
        )
    return alerts


def risk_budget_to_csv(rows: list[dict[str, Any]]) -> str:
    fieldnames = [
        "market_id",
        "question",
        "budget_state",
        "open_position_count",
        "open_cost_basis",
        "open_market_value",
        "unrealized_pnl",
        "pending_ticket_count",
        "pending_ticket_stake",
        "paper_ready_ticket_count",
        "paper_ready_stake",
        "combined_open_and_pending",
        "market_exposure_remaining",
        "market_exposure_remaining_after_pending",
        "market_utilization_percent",
        "combined_market_utilization_percent",
        "alert_count",
        "warning_count",
        "latest_ticket_id",
    ]
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return handle.getvalue()
