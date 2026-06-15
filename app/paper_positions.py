from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR
from .paper_trading import load_portfolio, save_portfolio, summarize_portfolio

POSITION_EVENTS_PATH = DATA_DIR / "paper" / "position_events.json"
VALID_POSITION_STATUSES = {"active", "watch", "reduce", "exit_planned"}


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


def _position_key(market_id: str, outcome: str) -> str:
    return f"{market_id}:{str(outcome or 'YES').strip().upper()}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except Exception:
        return default


def _optional_price(value: Any) -> float | None:
    if value is None or value == "":
        return None
    price = float(value)
    if not 0 < price < 1:
        raise ValueError("Position target/stop prices must be between 0 and 1.")
    return round(price, 4)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    days = int(value)
    if days < 0 or days > 3650:
        raise ValueError("Maximum hold days must be between 0 and 3650.")
    return days


def _normalize_status(value: Any) -> str:
    status = str(value or "active").strip().lower()
    if status not in VALID_POSITION_STATUSES:
        raise ValueError(f"Position status must be one of: {', '.join(sorted(VALID_POSITION_STATUSES))}.")
    return status


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _age_days(pos: dict[str, Any]) -> float | None:
    opened = _parse_dt(pos.get("opened_at") or pos.get("updated_at"))
    if opened is None:
        return None
    seconds = (datetime.now(timezone.utc) - opened).total_seconds()
    return max(seconds / 86400.0, 0.0)


def load_position_events() -> list[dict[str, Any]]:
    rows = _read_json(POSITION_EVENTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_position_events(rows: list[dict[str, Any]]) -> None:
    _write_json(POSITION_EVENTS_PATH, rows)


def list_position_events(limit: int = 100, market_id: str | None = None) -> list[dict[str, Any]]:
    rows = list(reversed(load_position_events()))
    if market_id:
        rows = [row for row in rows if str(row.get("market_id")) == str(market_id)]
    return rows[:limit]


def _append_position_event(row: dict[str, Any]) -> dict[str, Any]:
    event = {
        "event_id": f"pe_{uuid4().hex[:12]}",
        "timestamp": _now(),
        "mode": "paper_only_position_lifecycle",
        **row,
    }
    rows = load_position_events()
    rows.append(event)
    save_position_events(rows)
    return event


def update_position_plan(
    market_id: str,
    *,
    outcome: str = "YES",
    target_price: Any = None,
    stop_price: Any = None,
    max_hold_days: Any = None,
    status: str = "active",
    review_note: str = "",
    updated_by: str = "local",
) -> dict[str, Any]:
    key = _position_key(market_id, outcome)
    portfolio = load_portfolio()
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(key)
    if not pos:
        raise ValueError("No open paper position for that market/outcome.")

    plan = {
        "target_price": _optional_price(target_price),
        "stop_price": _optional_price(stop_price),
        "max_hold_days": _optional_int(max_hold_days),
        "status": _normalize_status(status),
        "review_note": str(review_note or "").strip(),
        "updated_at": _now(),
        "updated_by": updated_by,
    }
    pos["exit_plan"] = plan
    pos["position_status"] = plan["status"]
    pos["plan_updated_at"] = plan["updated_at"]
    if not pos.get("opened_at"):
        pos["opened_at"] = pos.get("updated_at") or plan["updated_at"]
    save_portfolio(portfolio)
    event = _append_position_event(
        {
            "type": "PLAN_UPDATE",
            "market_id": str(market_id),
            "question": pos.get("question"),
            "outcome": str(outcome or "YES").upper(),
            "plan": plan,
            "updated_by": updated_by,
        }
    )
    return {"position": pos, "plan": plan, "event": event, "portfolio": summarize_portfolio()}


def position_alerts(portfolio_summary: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    portfolio_summary = portfolio_summary or summarize_portfolio()
    alerts: list[dict[str, Any]] = []
    for pos in portfolio_summary.get("open_positions") or []:
        market_id = str(pos.get("market_id") or "")
        outcome = str(pos.get("outcome") or "YES").upper()
        question = pos.get("question") or market_id
        current_price = _safe_float(pos.get("current_price"), _safe_float(pos.get("last_price"), _safe_float(pos.get("avg_price"), 0.0)))
        plan = pos.get("exit_plan") if isinstance(pos.get("exit_plan"), dict) else {}
        status = str(plan.get("status") or pos.get("position_status") or "active")
        target = plan.get("target_price")
        stop = plan.get("stop_price")
        max_hold_days = plan.get("max_hold_days")
        age = _age_days(pos)

        base = {
            "market_id": market_id,
            "question": question,
            "outcome": outcome,
            "current_price": round(current_price, 4),
            "position_status": status,
            "market_value": pos.get("market_value"),
            "unrealized_pnl": pos.get("unrealized_pnl"),
        }
        if target is not None and current_price >= _safe_float(target):
            alerts.append(
                {
                    **base,
                    "level": "warning",
                    "kind": "paper_position_target_hit",
                    "title": "Paper target reached",
                    "detail": f"{outcome} is at {current_price:.4f}, target {float(target):.4f}.",
                    "recommended_action": "review_sell_or_raise_target",
                }
            )
        if stop is not None and current_price <= _safe_float(stop):
            alerts.append(
                {
                    **base,
                    "level": "warning",
                    "kind": "paper_position_stop_hit",
                    "title": "Paper stop reached",
                    "detail": f"{outcome} is at {current_price:.4f}, stop {float(stop):.4f}.",
                    "recommended_action": "review_reduce_or_exit",
                }
            )
        if max_hold_days is not None and age is not None and age >= _safe_float(max_hold_days):
            alerts.append(
                {
                    **base,
                    "level": "info",
                    "kind": "paper_position_review_due",
                    "title": "Paper position review due",
                    "detail": f"Held for {age:.1f} days; review limit is {int(max_hold_days)} day(s).",
                    "recommended_action": "refresh_thesis_and_evidence",
                }
            )
        if target is None and stop is None:
            alerts.append(
                {
                    **base,
                    "level": "info",
                    "kind": "paper_position_unmanaged",
                    "title": "Paper position has no target/stop",
                    "detail": "Add a local target and/or stop so the position lifecycle is explicit.",
                    "recommended_action": "set_exit_plan",
                }
            )
        if status in {"reduce", "exit_planned"}:
            alerts.append(
                {
                    **base,
                    "level": "warning" if status == "exit_planned" else "info",
                    "kind": f"paper_position_status_{status}",
                    "title": "Paper position needs operator action",
                    "detail": f"Position status is {status}.",
                    "recommended_action": "review_position_queue",
                }
            )
    severity_order = {"warning": 0, "info": 1}
    alerts.sort(key=lambda row: (severity_order.get(str(row.get("level")), 9), str(row.get("kind")), str(row.get("question"))))
    return alerts


def position_control_summary(portfolio_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    portfolio_summary = portfolio_summary or summarize_portfolio()
    positions = portfolio_summary.get("open_positions") or []
    managed = 0
    with_target = 0
    with_stop = 0
    statuses: dict[str, int] = {}
    for pos in positions:
        plan = pos.get("exit_plan") if isinstance(pos.get("exit_plan"), dict) else {}
        status = str(plan.get("status") or pos.get("position_status") or "active")
        statuses[status] = statuses.get(status, 0) + 1
        if plan.get("target_price") is not None or plan.get("stop_price") is not None:
            managed += 1
        if plan.get("target_price") is not None:
            with_target += 1
        if plan.get("stop_price") is not None:
            with_stop += 1
    alerts = position_alerts(portfolio_summary)
    return {
        "mode": "paper_only_position_lifecycle",
        "open_position_count": len(positions),
        "managed_position_count": managed,
        "unmanaged_position_count": max(len(positions) - managed, 0),
        "target_count": with_target,
        "stop_count": with_stop,
        "alert_count": len(alerts),
        "warning_count": len([row for row in alerts if row.get("level") == "warning"]),
        "statuses": statuses,
        "note": "Local paper position controls only. These alerts do not place orders or touch a wallet.",
    }
