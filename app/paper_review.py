from __future__ import annotations

import csv
from collections import Counter, defaultdict
from io import StringIO
from typing import Any

from .paper_audit import build_audit_events
from .paper_trading import load_portfolio


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


def _round(value: Any, places: int = 4) -> float:
    return round(_safe_float(value), places)


def _event_data(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data")
    return data if isinstance(data, dict) else {}


def _readiness_score(ticket: dict[str, Any]) -> float:
    readiness = ticket.get("readiness") if isinstance(ticket.get("readiness"), dict) else {}
    return _safe_float(readiness.get("readiness_score"), 0.0)


def _evidence_score(ticket: dict[str, Any]) -> float:
    readiness = ticket.get("readiness") if isinstance(ticket.get("readiness"), dict) else {}
    return _safe_float(readiness.get("evidence_score"), 0.0)


def _thesis_score(ticket: dict[str, Any]) -> float:
    readiness = ticket.get("readiness") if isinstance(ticket.get("readiness"), dict) else {}
    return _safe_float(readiness.get("thesis_score"), 0.0)


def _classify_market(row: dict[str, Any]) -> str:
    if row.get("open_position_count", 0) > 0:
        return "open"
    if row.get("settlement_count", 0) > 0:
        return "settled"
    if row.get("sell_count", 0) > 0:
        return "closed_by_exit"
    if row.get("buy_count", 0) > 0:
        return "entry_only_closed_unknown"
    return "review_only"


def _outcome_label(net_pnl: float) -> str:
    if net_pnl > 0.01:
        return "profitable"
    if net_pnl < -0.01:
        return "loss"
    return "breakeven"


def _discipline_flags(row: dict[str, Any]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    buy_count = _safe_int(row.get("buy_count"))
    sell_count = _safe_int(row.get("sell_count"))
    settlement_count = _safe_int(row.get("settlement_count"))
    entry_ticket_count = _safe_int(row.get("entry_ticket_count"))
    exit_ticket_count = _safe_int(row.get("exit_ticket_count"))
    position_plan_count = _safe_int(row.get("position_plan_count"))
    playbook_decision_count = _safe_int(row.get("playbook_decision_count"))
    executed_entry_count = _safe_int(row.get("executed_entry_ticket_count"))
    executed_exit_count = _safe_int(row.get("executed_exit_ticket_count"))
    net_pnl = _safe_float(row.get("net_pnl"))
    avg_readiness = _safe_float(row.get("avg_entry_readiness_score"))
    avg_evidence = _safe_float(row.get("avg_entry_evidence_score"))
    avg_thesis = _safe_float(row.get("avg_entry_thesis_score"))
    blocker_count = _safe_int(row.get("entry_blocker_count"))
    warning_count = _safe_int(row.get("entry_warning_count"))

    if buy_count and not entry_ticket_count:
        flags.append({"level": "warning", "code": "entry_without_ticket", "detail": "A simulated buy exists without a matching entry ticket."})
    elif buy_count and not executed_entry_count:
        flags.append({"level": "info", "code": "entry_ticket_not_marked_executed", "detail": "Entry tickets exist, but none are marked paper_executed."})

    if buy_count and not position_plan_count:
        flags.append({"level": "warning", "code": "missing_position_plan", "detail": "No lifecycle plan update was recorded after entry."})

    if buy_count and not playbook_decision_count:
        flags.append({"level": "info", "code": "missing_playbook_decision", "detail": "No strategy playbook decision was recorded before or during the paper trade lifecycle."})

    if sell_count and not exit_ticket_count:
        flags.append({"level": "warning", "code": "exit_without_ticket", "detail": "A simulated sell exists without an exit ticket."})
    elif sell_count and not executed_exit_count:
        flags.append({"level": "info", "code": "exit_ticket_not_marked_executed", "detail": "Exit tickets exist, but none are marked paper_executed."})

    if buy_count and avg_readiness and avg_readiness < 0.60:
        flags.append({"level": "warning", "code": "low_readiness_entry", "detail": f"Average entry readiness was {avg_readiness:.2f}."})
    if buy_count and avg_evidence and avg_evidence < 0.45:
        flags.append({"level": "warning", "code": "thin_evidence_entry", "detail": f"Average evidence score was {avg_evidence:.2f}."})
    if buy_count and avg_thesis and avg_thesis < 0.40:
        flags.append({"level": "warning", "code": "thin_thesis_entry", "detail": f"Average thesis score was {avg_thesis:.2f}."})
    if blocker_count:
        flags.append({"level": "warning", "code": "entry_blockers_present", "detail": f"Entry ticket blockers were recorded: {blocker_count}."})
    if warning_count:
        flags.append({"level": "info", "code": "risk_warnings_present", "detail": f"Entry risk/readiness warnings were recorded: {warning_count}."})
    if settlement_count and net_pnl < -0.01:
        flags.append({"level": "warning", "code": "settled_loss", "detail": "A manual settlement closed this market at a simulated loss."})
    if settlement_count and net_pnl > 0.01 and entry_ticket_count and position_plan_count:
        flags.append({"level": "positive", "code": "documented_profitable_settlement", "detail": "Profitable settled market with documented entry and lifecycle records."})
    if sell_count and net_pnl > 0.01 and entry_ticket_count and exit_ticket_count:
        flags.append({"level": "positive", "code": "documented_profitable_exit", "detail": "Profitable simulated exit with entry and exit tickets."})
    if buy_count and row.get("open_position_count", 0) > 0 and not flags:
        flags.append({"level": "positive", "code": "managed_open_position", "detail": "Open position has review records and no current discipline flags in this report."})
    return flags


def _lesson_summary(flags: list[dict[str, str]], row: dict[str, Any]) -> str:
    if not flags:
        if row.get("buy_count", 0):
            return "No obvious process gaps found in the local paper record. Continue reviewing thesis, evidence, and exit plan manually."
        return "Review-only market; no simulated trade lifecycle to learn from yet."
    priority = [flag for flag in flags if flag.get("level") == "warning"] or [flag for flag in flags if flag.get("level") == "info"] or flags
    return priority[0].get("detail") or priority[0].get("code") or "Review local paper records."


def _guardrail() -> str:
    return "Paper review reports are local simulation/accounting records only. They are not investment advice and do not represent live orders, wallet activity, or exchange settlement."


def build_review_report(
    *,
    limit: int = 100,
    market_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    events = build_audit_events(limit=100000, market_id=market_id)
    grouped: dict[str, dict[str, Any]] = {}

    for event in events:
        mid = str(event.get("market_id") or "")
        if not mid:
            continue
        row = grouped.setdefault(
            mid,
            {
                "market_id": mid,
                "question": str(event.get("question") or mid),
                "first_event_at": "",
                "last_event_at": "",
                "event_count": 0,
                "buy_count": 0,
                "sell_count": 0,
                "settlement_count": 0,
                "entry_ticket_count": 0,
                "executed_entry_ticket_count": 0,
                "exit_ticket_count": 0,
                "executed_exit_ticket_count": 0,
                "position_plan_count": 0,
                "playbook_decision_count": 0,
                "entry_blocker_count": 0,
                "entry_warning_count": 0,
                "simulated_cost": 0.0,
                "simulated_proceeds": 0.0,
                "realized_pnl": 0.0,
                "entry_readiness_scores": [],
                "entry_evidence_scores": [],
                "entry_thesis_scores": [],
                "outcomes": set(),
                "latest_status": "",
                "latest_detail": "",
                "audit_categories": Counter(),
                "audit_event_types": Counter(),
            },
        )
        if event.get("question"):
            row["question"] = str(event.get("question"))
        ts = str(event.get("timestamp") or "")
        if ts:
            if not row["first_event_at"] or ts < row["first_event_at"]:
                row["first_event_at"] = ts
            if not row["last_event_at"] or ts > row["last_event_at"]:
                row["last_event_at"] = ts
                row["latest_status"] = str(event.get("status") or "")
                row["latest_detail"] = str(event.get("detail") or "")
        row["event_count"] += 1
        row["audit_categories"].update([str(event.get("category") or "unknown")])
        row["audit_event_types"].update([str(event.get("event_type") or "unknown")])
        outcome = str(event.get("outcome") or "")
        if outcome:
            row["outcomes"].add(outcome)

        category = str(event.get("category") or "")
        event_type = str(event.get("event_type") or "")
        amount = _safe_float(event.get("amount"))
        pnl = _safe_float(event.get("pnl"))
        data = _event_data(event)

        if event_type == "TRADE_BUY":
            row["buy_count"] += 1
            row["simulated_cost"] += amount
        elif event_type == "TRADE_SELL":
            row["sell_count"] += 1
            row["simulated_proceeds"] += amount
            row["realized_pnl"] += pnl
        elif event_type == "TRADE_SETTLE":
            row["settlement_count"] += 1
            row["simulated_proceeds"] += amount
            row["realized_pnl"] += pnl
        elif event_type == "SETTLEMENT":
            # Settlement summary records are retained for context, but TRADE_SETTLE rows
            # carry the accounting amounts to avoid double-counting.
            row["settlement_count"] = max(row["settlement_count"], 1)

        if category == "entry_ticket":
            row["entry_ticket_count"] += 1
            if str(event.get("status")) == "paper_executed" or data.get("paper_trade_id"):
                row["executed_entry_ticket_count"] += 1
            row["entry_blocker_count"] += len(data.get("blockers") or []) if isinstance(data.get("blockers"), list) else 0
            row["entry_warning_count"] += len(data.get("warnings") or []) if isinstance(data.get("warnings"), list) else 0
            readiness = _readiness_score(data)
            evidence = _evidence_score(data)
            thesis = _thesis_score(data)
            if readiness:
                row["entry_readiness_scores"].append(readiness)
            if evidence:
                row["entry_evidence_scores"].append(evidence)
            if thesis:
                row["entry_thesis_scores"].append(thesis)
        elif category == "exit_ticket":
            row["exit_ticket_count"] += 1
            if str(event.get("status")) == "paper_executed" or data.get("paper_trade_id"):
                row["executed_exit_ticket_count"] += 1
        elif category == "position_lifecycle":
            row["position_plan_count"] += 1
        elif category == "playbook_decision":
            row["playbook_decision_count"] += 1

    portfolio = load_portfolio()
    for pos in (portfolio.get("positions") or {}).values():
        mid = str(pos.get("market_id") or "")
        if not mid:
            continue
        if market_id and mid != str(market_id):
            continue
        row = grouped.setdefault(
            mid,
            {
                "market_id": mid,
                "question": str(pos.get("question") or mid),
                "first_event_at": str(pos.get("opened_at") or ""),
                "last_event_at": str(pos.get("updated_at") or ""),
                "event_count": 0,
                "buy_count": 0,
                "sell_count": 0,
                "settlement_count": 0,
                "entry_ticket_count": 0,
                "executed_entry_ticket_count": 0,
                "exit_ticket_count": 0,
                "executed_exit_ticket_count": 0,
                "position_plan_count": 0,
                "playbook_decision_count": 0,
                "entry_blocker_count": 0,
                "entry_warning_count": 0,
                "simulated_cost": 0.0,
                "simulated_proceeds": 0.0,
                "realized_pnl": 0.0,
                "entry_readiness_scores": [],
                "entry_evidence_scores": [],
                "entry_thesis_scores": [],
                "outcomes": set(),
                "latest_status": str(pos.get("position_status") or "active"),
                "latest_detail": "open local paper position",
                "audit_categories": Counter(),
                "audit_event_types": Counter(),
            },
        )
        if pos.get("question"):
            row["question"] = str(pos.get("question"))
        row["open_position_count"] = _safe_int(row.get("open_position_count")) + 1
        row["open_shares"] = _safe_float(row.get("open_shares")) + _safe_float(pos.get("shares"))
        row["open_cost_basis"] = _safe_float(row.get("open_cost_basis")) + _safe_float(pos.get("cost_basis"))
        last_price = _safe_float(pos.get("last_price"), _safe_float(pos.get("avg_price")))
        row["open_market_value"] = _safe_float(row.get("open_market_value")) + (_safe_float(pos.get("shares")) * last_price)
        outcome = str(pos.get("outcome") or "")
        if outcome:
            row["outcomes"].add(outcome)
        ts = str(pos.get("updated_at") or pos.get("opened_at") or "")
        if ts and (not row.get("last_event_at") or ts > str(row.get("last_event_at") or "")):
            row["last_event_at"] = ts

    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        readiness_scores = row.pop("entry_readiness_scores", [])
        evidence_scores = row.pop("entry_evidence_scores", [])
        thesis_scores = row.pop("entry_thesis_scores", [])
        row["avg_entry_readiness_score"] = _round(sum(readiness_scores) / len(readiness_scores)) if readiness_scores else 0.0
        row["avg_entry_evidence_score"] = _round(sum(evidence_scores) / len(evidence_scores)) if evidence_scores else 0.0
        row["avg_entry_thesis_score"] = _round(sum(thesis_scores) / len(thesis_scores)) if thesis_scores else 0.0
        row["open_position_count"] = _safe_int(row.get("open_position_count"))
        row["open_shares"] = _round(row.get("open_shares"), 8)
        row["open_cost_basis"] = _round(row.get("open_cost_basis"))
        row["open_market_value"] = _round(row.get("open_market_value"))
        row["unrealized_pnl"] = _round(row["open_market_value"] - row["open_cost_basis"])
        row["simulated_cost"] = _round(row.get("simulated_cost"))
        row["simulated_proceeds"] = _round(row.get("simulated_proceeds"))
        row["realized_pnl"] = _round(row.get("realized_pnl"))
        row["net_pnl"] = _round(row["realized_pnl"] + row["unrealized_pnl"])
        row["return_on_closed_cost_percent"] = round((row["realized_pnl"] / row["simulated_cost"]) * 100, 2) if row["simulated_cost"] else 0.0
        row["outcomes"] = sorted(row.get("outcomes") or [])
        row["audit_categories"] = dict(sorted(row.get("audit_categories", Counter()).items()))
        row["audit_event_types"] = dict(sorted(row.get("audit_event_types", Counter()).items()))
        row["lifecycle_status"] = _classify_market(row)
        row["outcome_label"] = _outcome_label(row["net_pnl"])
        flags = _discipline_flags(row)
        row["discipline_flags"] = flags
        row["warning_count"] = len([flag for flag in flags if flag.get("level") == "warning"])
        row["info_count"] = len([flag for flag in flags if flag.get("level") == "info"])
        row["positive_count"] = len([flag for flag in flags if flag.get("level") == "positive"])
        row["lesson"] = _lesson_summary(flags, row)
        rows.append(row)

    if status:
        wanted = str(status).strip().lower()
        rows = [row for row in rows if str(row.get("lifecycle_status", "")).lower() == wanted]

    rows.sort(key=lambda row: (row.get("last_event_at") or "", abs(_safe_float(row.get("net_pnl"))), row.get("event_count", 0)), reverse=True)
    rows = rows[: max(0, int(limit))]
    return {"summary": summarize_review_report(rows), "items": rows, "guardrail": _guardrail()}


def summarize_review_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(str(row.get("lifecycle_status") or "unknown") for row in rows)
    outcomes = Counter(str(row.get("outcome_label") or "unknown") for row in rows)
    flag_codes = Counter(flag.get("code", "unknown") for row in rows for flag in row.get("discipline_flags", []))
    warnings = sum(_safe_int(row.get("warning_count")) for row in rows)
    positives = sum(_safe_int(row.get("positive_count")) for row in rows)
    realized = sum(_safe_float(row.get("realized_pnl")) for row in rows)
    unrealized = sum(_safe_float(row.get("unrealized_pnl")) for row in rows)
    cost = sum(_safe_float(row.get("simulated_cost")) for row in rows)
    proceeds = sum(_safe_float(row.get("simulated_proceeds")) for row in rows)
    return {
        "market_count": len(rows),
        "status_counts": dict(sorted(statuses.items())),
        "outcome_counts": dict(sorted(outcomes.items())),
        "flag_counts": dict(flag_codes.most_common(20)),
        "warning_count": warnings,
        "positive_count": positives,
        "simulated_cost": round(cost, 4),
        "simulated_proceeds": round(proceeds, 4),
        "realized_pnl": round(realized, 4),
        "unrealized_pnl": round(unrealized, 4),
        "net_pnl": round(realized + unrealized, 4),
        "win_count": outcomes.get("profitable", 0),
        "loss_count": outcomes.get("loss", 0),
        "breakeven_count": outcomes.get("breakeven", 0),
        "guardrail": _guardrail(),
    }


def build_market_review(market_id: str) -> dict[str, Any]:
    report = build_review_report(limit=1, market_id=market_id)
    items = report.get("items", [])
    item = items[0] if items else None
    audit = build_audit_events(limit=500, market_id=market_id)
    return {
        "market_id": str(market_id),
        "summary": report.get("summary", {}),
        "item": item,
        "audit_items": audit,
        "guardrail": _guardrail(),
    }


def review_report_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "market_id",
        "question",
        "lifecycle_status",
        "outcome_label",
        "event_count",
        "buy_count",
        "sell_count",
        "settlement_count",
        "entry_ticket_count",
        "exit_ticket_count",
        "position_plan_count",
        "playbook_decision_count",
        "simulated_cost",
        "simulated_proceeds",
        "realized_pnl",
        "unrealized_pnl",
        "net_pnl",
        "avg_entry_readiness_score",
        "avg_entry_evidence_score",
        "avg_entry_thesis_score",
        "warning_count",
        "positive_count",
        "lesson",
        "first_event_at",
        "last_event_at",
    ]
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        flat = dict(row)
        flat["lesson"] = str(flat.get("lesson") or "")
        writer.writerow(flat)
    return buf.getvalue()
