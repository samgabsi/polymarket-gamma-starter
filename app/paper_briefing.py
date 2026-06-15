from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .analytics import trade_analytics
from .config import DATA_DIR
from .paper_execution_queue import build_execution_queue
from .paper_risk_budget import build_risk_budget
from .paper_runbook import build_runbook
from .paper_trading import load_trades, summarize_portfolio
from .paper_review import build_review_report
from .playbook_performance import build_playbook_performance

BRIEFING_CHECKPOINTS_PATH = DATA_DIR / "paper" / "paper_ops_briefing_checkpoints.json"
BRIEFING_SECTIONS = {
    "runbook",
    "entry_execution",
    "risk_budget",
    "post_trade_review",
    "playbook_performance",
    "portfolio_health",
}
BRIEFING_STATUSES = {"ready", "action_required", "blocked", "review", "watch", "ok", "checkpoint"}
CHECKPOINT_STATUSES = {"reviewed", "needs_followup", "skipped"}


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


def _item(
    *,
    section: str,
    status: str,
    priority: int,
    title: str,
    recommended_action: str,
    detail: str = "",
    market_id: str = "",
    ticket_id: str = "",
    source_id: str = "",
    question: str = "",
    links: dict[str, str] | None = None,
    metrics: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    section = section if section in BRIEFING_SECTIONS else "runbook"
    status = status if status in BRIEFING_STATUSES else "review"
    return {
        "briefing_item_id": f"{section}:{source_id or market_id or ticket_id or uuid4().hex[:8]}",
        "version": "0.4.7-paper-ops-briefing-v1",
        "mode": "paper_ops_briefing_v047",
        "section": section,
        "status": status,
        "priority": int(priority),
        "title": title,
        "recommended_action": recommended_action,
        "detail": detail,
        "market_id": market_id,
        "ticket_id": ticket_id,
        "source_id": source_id,
        "question": question or title,
        "links": links or {},
        "metrics": metrics or {},
        "data": data or {},
        "guardrail": "Local paper-ops briefing item only. It does not place live orders, connect a wallet, sign messages, or provide investment advice.",
    }


def load_briefing_checkpoints() -> list[dict[str, Any]]:
    rows = _read_json(BRIEFING_CHECKPOINTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_briefing_checkpoints(rows: list[dict[str, Any]]) -> None:
    _write_json(BRIEFING_CHECKPOINTS_PATH, rows)


def list_briefing_checkpoints(
    *,
    limit: int = 100,
    status: str | None = None,
    operator: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_briefing_checkpoints()))
    if status:
        rows = [row for row in rows if _text(row.get("status")) == _text(status)]
    if operator:
        rows = [row for row in rows if _text(row.get("operator")) == _text(operator)]
    return rows[: max(0, int(limit))]


def record_briefing_checkpoint(
    *,
    status: str = "reviewed",
    operator: str = "local",
    note: str = "",
    section: str | None = None,
    briefing_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = status if status in CHECKPOINT_STATUSES else "reviewed"
    briefing_snapshot = briefing_snapshot or build_paper_ops_briefing(limit=100, section=section)
    summary = briefing_snapshot.get("summary", {}) if isinstance(briefing_snapshot, dict) else {}
    record = {
        "checkpoint_id": f"pob_{uuid4().hex[:12]}",
        "version": "0.4.7-paper-ops-briefing-checkpoint-v1",
        "mode": "paper_ops_briefing_checkpoint_v047",
        "created_at": _now(),
        "operator": _text(operator, "local"),
        "status": status,
        "section": _text(section or "all"),
        "note": _text(note),
        "summary_snapshot": summary,
        "item_count_snapshot": _safe_int(summary.get("count")),
        "blocked_snapshot": _safe_int(summary.get("blocked")),
        "action_required_snapshot": _safe_int(summary.get("action_required")),
        "ready_snapshot": _safe_int(summary.get("ready")),
        "briefing_snapshot": briefing_snapshot,
        "guardrail": "Local paper-ops briefing checkpoint only. It is not live trading activity or investment advice.",
    }
    rows = load_briefing_checkpoints()
    rows.append(record)
    save_briefing_checkpoints(rows)
    return record


def _portfolio_health_items(portfolio: dict[str, Any], analytics: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    open_positions = _safe_int(portfolio.get("open_position_count"))
    open_cost = _safe_float(portfolio.get("open_cost_basis"))
    total_pnl = _safe_float(portfolio.get("total_pnl"))
    return_pct = _safe_float(portfolio.get("total_return_percent"))
    realized = _safe_float(analytics.get("realized_pnl"))
    trade_count = _safe_int(analytics.get("trade_count"))

    status = "ok"
    priority = 20
    detail = "Portfolio has no open simulated exposure."
    action = "continue_research_or_review_closed_lessons"
    if open_positions:
        status = "watch"
        priority = 45
        detail = f"{open_positions} open paper position(s), open cost basis ${open_cost:,.2f}, paper total P&L {total_pnl:+,.2f} ({return_pct:+.2f}%)."
        action = "review_open_positions_and_lifecycle_plans"
    if realized < 0:
        status = "review" if status != "watch" else "action_required"
        priority = max(priority, 60)
        detail += f" Realized simulated P&L is {realized:+,.2f}; review post-trade lessons before increasing paper exposure."
        action = "review_realized_losses_and_process_flags"

    items.append(
        _item(
            section="portfolio_health",
            status=status,
            priority=priority,
            title="Paper portfolio health snapshot",
            recommended_action=action,
            detail=detail,
            source_id="portfolio",
            links={"positions": "/positions", "review_report": "/review-report", "audit": "/audit"},
            metrics={
                "open_positions": open_positions,
                "open_cost_basis": round(open_cost, 4),
                "total_pnl": round(total_pnl, 4),
                "total_return_percent": round(return_pct, 4),
                "realized_pnl": round(realized, 4),
                "trade_count": trade_count,
            },
            data={"portfolio": portfolio, "analytics": analytics},
        )
    )
    return items


def _runbook_items(runbook: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in runbook.get("items") or []:
        status = _text(row.get("effective_status") or row.get("status") or "review")
        priority = _safe_int(row.get("priority"), 50) + 10
        source_id = _text(row.get("item_id"))
        rows.append(
            _item(
                section="runbook",
                status=status,
                priority=priority,
                title=_text(row.get("title") or source_id),
                recommended_action=_text(row.get("recommended_action") or "review_runbook_item"),
                detail=_text(row.get("detail") or "Runbook item needs operator review."),
                market_id=_text(row.get("market_id")),
                ticket_id=_text(row.get("ticket_id")),
                source_id=source_id,
                question=_text(row.get("question") or row.get("title")),
                links={"runbook": f"/runbook?item_id={source_id}", **(row.get("links") or {})},
                metrics={"checklist_required": row.get("checklist_required"), "checklist_total": row.get("checklist_total")},
                data=row,
            )
        )
    return rows


def _execution_queue_items(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    status_map = {
        "approved_ready": "ready",
        "needs_approval": "action_required",
        "stale_approval": "action_required",
        "blocked": "blocked",
        "rejected": "ok",
        "executed": "ok",
    }
    priority_map = {
        "approved_ready": 95,
        "needs_approval": 85,
        "stale_approval": 80,
        "blocked": 90,
        "rejected": 20,
        "executed": 15,
    }
    for row in queue.get("items") or []:
        raw_status = _text(row.get("queue_status"))
        if raw_status in {"rejected", "executed"}:
            continue
        ticket_id = _text(row.get("ticket_id"))
        market_id = _text(row.get("market_id"))
        rows.append(
            _item(
                section="entry_execution",
                status=status_map.get(raw_status, "review"),
                priority=priority_map.get(raw_status, 60),
                title=f"Entry execution queue: {ticket_id}",
                recommended_action=_text(row.get("recommended_action") or "review_entry_execution_queue"),
                detail=_text(row.get("reason_summary") or f"Queue status: {raw_status}"),
                market_id=market_id,
                ticket_id=ticket_id,
                source_id=ticket_id,
                question=_text(row.get("title") or market_id),
                links={
                    "execution_queue": f"/execution-queue?ticket_id={ticket_id}",
                    "approvals": f"/approvals?ticket_id={ticket_id}",
                    "preflight": f"/preflight?ticket_id={ticket_id}",
                    "audit": f"/audit?market_id={market_id}",
                },
                metrics={
                    "stake": row.get("stake"),
                    "preflight_status": row.get("preflight_status"),
                    "latest_approval_status": row.get("latest_approval_status"),
                    "warning_count": row.get("warning_count"),
                    "blocker_count": row.get("blocker_count"),
                },
                data=row,
            )
        )
    return rows


def _risk_budget_items(risk_budget: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for flag in risk_budget.get("flags") or []:
        market_id = _text(flag.get("market_id"))
        kind = _text(flag.get("kind") or "risk_budget_flag")
        level = _text(flag.get("level"))
        status = "blocked" if level == "warning" or "blocked" in kind or "exceed" in kind else "review"
        rows.append(
            _item(
                section="risk_budget",
                status=status,
                priority=88 if status == "blocked" else 62,
                title=f"Risk budget: {kind}",
                recommended_action="resolve_risk_budget_before_new_entries",
                detail=_text(flag.get("detail") or kind),
                market_id=market_id,
                source_id=market_id or kind,
                question=_text(flag.get("question") or market_id or kind),
                links={"risk_budget": f"/risk-budget?market_id={market_id}" if market_id else "/risk-budget", "audit": f"/audit?market_id={market_id}" if market_id else "/audit"},
                metrics={"level": level, "kind": kind},
                data=flag,
            )
        )
    return rows


def _review_items(review_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in review_report.get("items") or []:
        warnings = _safe_int(row.get("warning_count"))
        infos = _safe_int(row.get("info_count"))
        if not warnings and not infos:
            continue
        market_id = _text(row.get("market_id"))
        rows.append(
            _item(
                section="post_trade_review",
                status="action_required" if warnings else "review",
                priority=68 + warnings * 8 + infos * 2,
                title=f"Post-trade review: {_text(row.get('question') or market_id)}",
                recommended_action="review_discipline_flags_and_update_process",
                detail=_text(row.get("lesson") or "Review local paper discipline flags."),
                market_id=market_id,
                source_id=market_id,
                question=_text(row.get("question") or market_id),
                links={"review_report": f"/review-report?market_id={market_id}", "audit": f"/audit?market_id={market_id}"},
                metrics={
                    "warning_count": warnings,
                    "info_count": infos,
                    "lifecycle_status": row.get("lifecycle_status"),
                    "net_pnl": row.get("net_pnl"),
                },
                data=row,
            )
        )
    return rows


def _playbook_performance_items(performance: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in performance.get("items") or []:
        decision_count = _safe_int(row.get("decision_count"))
        warning_count = _safe_int(row.get("warning_count"))
        lifecycle_count = _safe_int(row.get("paper_lifecycle_market_count"))
        net_pnl = _safe_float(row.get("net_pnl"))
        if not decision_count:
            continue
        status = "ok"
        priority = 30
        detail = "Playbook has decisions but no urgent paper-performance flags."
        action = "keep_tracking_playbook_discipline"
        if decision_count and not lifecycle_count:
            status = "review"
            priority = 54
            detail = "Playbook has decisions but no local paper lifecycle follow-through yet."
            action = "confirm_decisions_are_becoming_auditable_workflow"
        if warning_count:
            status = "action_required"
            priority = max(priority, 72 + warning_count)
            detail = f"Playbook has {warning_count} review warning(s) across local paper records."
            action = "review_playbook_process_warnings"
        if net_pnl < 0 and lifecycle_count:
            status = "review" if status == "ok" else status
            priority = max(priority, 64)
            detail += f" Net simulated P&L is {net_pnl:+,.2f}."
            action = "review_playbook_loss_or_noise"
        if status == "ok":
            continue
        playbook_id = _text(row.get("playbook_id"))
        rows.append(
            _item(
                section="playbook_performance",
                status=status,
                priority=priority,
                title=f"Playbook performance: {_text(row.get('playbook_name') or playbook_id)}",
                recommended_action=action,
                detail=detail,
                source_id=playbook_id,
                question=_text(row.get("playbook_name") or playbook_id),
                links={"playbook_performance": f"/playbook-performance?playbook_id={playbook_id}", "playbooks": "/playbooks", "review_report": "/review-report"},
                metrics={
                    "decision_count": decision_count,
                    "paper_lifecycle_market_count": lifecycle_count,
                    "warning_count": warning_count,
                    "net_pnl": round(net_pnl, 4),
                    "win_rate_percent": row.get("win_rate_percent"),
                },
                data=row,
            )
        )
    return rows


def summarize_briefing(items: list[dict[str, Any]], *, portfolio: dict[str, Any], analytics: dict[str, Any], risk_budget: dict[str, Any], runbook: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    sections = Counter(_text(row.get("section") or "unknown") for row in items)
    statuses = Counter(_text(row.get("status") or "unknown") for row in items)
    markets = {_text(row.get("market_id")) for row in items if row.get("market_id")}
    ready_entry_stake = sum(_safe_float((row.get("metrics") or {}).get("stake")) for row in items if row.get("section") == "entry_execution" and row.get("status") == "ready")
    return {
        "count": len(items),
        "market_count": len(markets),
        "by_section": dict(sorted(sections.items())),
        "by_status": dict(sorted(statuses.items())),
        "ready": statuses.get("ready", 0),
        "action_required": statuses.get("action_required", 0),
        "blocked": statuses.get("blocked", 0),
        "review": statuses.get("review", 0),
        "watch": statuses.get("watch", 0),
        "ok": statuses.get("ok", 0),
        "ready_entry_stake": round(ready_entry_stake, 4),
        "top_priority": max([_safe_int(row.get("priority")) for row in items], default=0),
        "portfolio": {
            "cash": portfolio.get("cash"),
            "equity": portfolio.get("equity"),
            "open_position_count": portfolio.get("open_position_count"),
            "total_pnl": portfolio.get("total_pnl"),
            "total_return_percent": portfolio.get("total_return_percent"),
        },
        "analytics": {
            "trade_count": analytics.get("trade_count"),
            "realized_pnl": analytics.get("realized_pnl"),
            "win_rate_percent": analytics.get("win_rate_percent"),
            "last_trade_at": analytics.get("last_trade_at"),
        },
        "risk_budget": risk_budget.get("summary", {}),
        "runbook": runbook.get("summary", {}),
        "execution_queue": queue.get("summary", {}),
        "guardrail": "Paper ops briefing summarizes local simulated workflow state only. It is not investment advice, live trading status, or exchange settlement.",
    }


def build_paper_ops_briefing(
    *,
    limit: int = 100,
    section: str | None = None,
    status: str | None = None,
    market_id: str | None = None,
) -> dict[str, Any]:
    portfolio = summarize_portfolio([])
    analytics = trade_analytics(load_trades(), portfolio)
    risk_budget = build_risk_budget(limit=1000, market_id=market_id)
    runbook = build_runbook(limit=1000, market_id=market_id)
    queue = build_execution_queue(limit=1000, market_id=market_id)
    review_report = build_review_report(limit=1000, market_id=market_id)
    performance = build_playbook_performance(limit=1000)

    items: list[dict[str, Any]] = []
    items.extend(_portfolio_health_items(portfolio, analytics))
    items.extend(_runbook_items(runbook))
    items.extend(_execution_queue_items(queue))
    items.extend(_risk_budget_items(risk_budget))
    items.extend(_review_items(review_report))
    items.extend(_playbook_performance_items(performance))

    if section:
        wanted = _text(section)
        items = [row for row in items if _text(row.get("section")) == wanted]
    if status:
        wanted = _text(status)
        items = [row for row in items if _text(row.get("status")) == wanted]
    if market_id:
        wanted = _text(market_id)
        items = [row for row in items if _text(row.get("market_id")) == wanted or not row.get("market_id")]

    items.sort(key=lambda row: (_safe_int(row.get("priority")), _text(row.get("briefing_item_id"))), reverse=True)
    items = items[: max(0, int(limit))]
    summary = summarize_briefing(items, portfolio=portfolio, analytics=analytics, risk_budget=risk_budget, runbook=runbook, queue=queue)
    return {
        "version": "0.4.7-paper-ops-briefing-v1",
        "mode": "paper_ops_briefing_v047",
        "generated_at": _now(),
        "summary": summary,
        "items": items,
        "recent_checkpoints": list_briefing_checkpoints(limit=10),
        "guardrail": "Daily paper ops briefing is a local simulated workflow report only. It never connects a wallet, signs messages, places live orders, or provides investment advice.",
    }


def briefing_alerts(report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    report = report or build_paper_ops_briefing(limit=100)
    alerts: list[dict[str, Any]] = []
    for row in report.get("items") or []:
        status = _text(row.get("status"))
        if status not in {"ready", "action_required", "blocked"}:
            continue
        level = "warning" if status in {"blocked", "action_required"} else "info"
        alerts.append(
            {
                "level": level,
                "kind": f"paper_ops_briefing_{status}",
                "title": _text(row.get("title") or "Paper ops briefing item"),
                "detail": _text(row.get("detail") or row.get("recommended_action")),
                "market_id": row.get("market_id"),
                "question": row.get("question"),
                "source": "paper_ops_briefing_v047",
                "link": "/paper-ops-briefing",
            }
        )
    return alerts[:25]


def briefing_to_csv(items: list[dict[str, Any]]) -> str:
    fields = [
        "briefing_item_id",
        "section",
        "status",
        "priority",
        "title",
        "recommended_action",
        "detail",
        "market_id",
        "ticket_id",
        "source_id",
        "question",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(item)
    return buf.getvalue()
