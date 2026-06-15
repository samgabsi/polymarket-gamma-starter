from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR, settings
from .live_config import build_live_config_readiness

INTENTS_PATH = DATA_DIR / "live" / "live_order_intents.json"
VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"limit", "marketable_limit"}
VALID_TIME_IN_FORCE = {"GTC", "FOK", "FAK"}
INTENT_STATUSES = {"ready_for_manual_review", "blocked_by_guard", "invalid", "archived"}


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
    return str(value).strip()


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


def _csv_join(values: list[Any]) -> str:
    return " | ".join(str(item) for item in values if str(item))


def _allowed_markets() -> list[str]:
    return list(settings.live_allowed_market_ids or [])


def _guard_snapshot() -> dict[str, Any]:
    config_report = build_live_config_readiness()
    summary = config_report.get("summary", {})
    controls = config_report.get("controls", {})
    return {
        "readiness_state": summary.get("readiness_state"),
        "l2_credentials_ready": bool(summary.get("l2_credentials_ready")),
        "guard_warning_count": _safe_int(summary.get("guard_warning_count")),
        "guard_warnings": list(summary.get("guard_warnings") or []),
        "read_only": bool(summary.get("read_only")),
        "live_trading_enabled": bool(summary.get("live_trading_enabled")),
        "dry_run_only": bool(summary.get("dry_run_only")),
        "manual_approval_required": bool(summary.get("manual_approval_required")),
        "pretrade_checks_enabled": bool(summary.get("pretrade_checks_enabled")),
        "audit_required": bool(summary.get("audit_required")),
        "order_execution_available": bool(summary.get("order_execution_available")),
        "execution_adapter_present": bool(controls.get("execution_adapter_present")),
        "order_placement_enabled": bool(controls.get("order_placement_enabled")),
        "order_cancellation_enabled": bool(controls.get("order_cancellation_enabled")),
        "autonomous_trading_enabled": bool(controls.get("autonomous_trading_enabled")),
        "max_order_notional": _safe_float(settings.live_max_order_notional),
        "max_market_notional": _safe_float(settings.live_max_market_notional),
        "max_daily_notional": _safe_float(settings.live_max_daily_notional),
        "max_open_orders": _safe_int(settings.live_max_open_orders),
        "allowed_market_ids": _allowed_markets(),
    }


def _evaluate_intent(*, market_id: str, token_id: str, side: str, price: float, size: float, order_type: str, time_in_force: str, guard: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    normalized_side = side.upper()
    normalized_order_type = order_type.lower()
    normalized_tif = time_in_force.upper()
    notional = round(price * size, 6)

    if not market_id:
        blockers.append("market_id is required for a live order intent preview.")
    if normalized_side not in VALID_SIDES:
        blockers.append("side must be BUY or SELL.")
    if normalized_order_type not in VALID_ORDER_TYPES:
        blockers.append("order_type must be limit or marketable_limit.")
    if normalized_tif not in VALID_TIME_IN_FORCE:
        blockers.append("time_in_force must be GTC, FOK, or FAK.")
    if price <= 0 or price >= 1:
        blockers.append("price must be greater than 0 and less than 1 for a binary outcome token.")
    if size <= 0:
        blockers.append("size must be greater than 0.")
    if notional <= 0:
        blockers.append("computed notional must be greater than 0.")

    if not guard.get("read_only"):
        blockers.append("READ_ONLY must remain true while this build has no execution adapter.")
    if guard.get("live_trading_enabled"):
        warnings.append("LIVE_TRADING_ENABLED is true, but this build still only records non-executing intents.")
    if not guard.get("dry_run_only"):
        blockers.append("LIVE_DRY_RUN_ONLY must remain true for live order intent preview.")
    if not guard.get("manual_approval_required"):
        blockers.append("LIVE_REQUIRE_MANUAL_APPROVAL must remain true before any future live action path.")
    if not guard.get("pretrade_checks_enabled"):
        blockers.append("LIVE_PRETRADE_CHECKS_ENABLED must remain true before any future live action path.")
    if not guard.get("audit_required"):
        blockers.append("LIVE_AUDIT_REQUIRED must remain true before any future live action path.")
    if guard.get("execution_adapter_present") or guard.get("order_placement_enabled"):
        blockers.append("Execution controls unexpectedly report an adapter/order placement path; this preview layer must remain non-executing.")

    max_order = _safe_float(guard.get("max_order_notional"))
    if max_order <= 0:
        blockers.append("LIVE_MAX_ORDER_NOTIONAL is 0/unset; set a deliberate local limit before future staged live tests.")
    elif notional > max_order:
        blockers.append(f"intent notional {notional:.4f} exceeds LIVE_MAX_ORDER_NOTIONAL {max_order:.4f}.")

    allowed = list(guard.get("allowed_market_ids") or [])
    if not allowed:
        blockers.append("LIVE_ALLOWED_MARKET_IDS is empty; no market is allowlisted for future live testing.")
    elif market_id not in allowed:
        blockers.append("market_id is not present in LIVE_ALLOWED_MARKET_IDS.")

    if not token_id:
        warnings.append("token_id is empty; a future CLOB adapter will require a concrete token/asset id.")
    if not guard.get("l2_credentials_ready"):
        warnings.append("CLOB L2 credential presence is incomplete; this is still safe because no network order action is available.")
    if guard.get("guard_warning_count"):
        warnings.extend(str(item) for item in list(guard.get("guard_warnings") or [])[:3])

    status = "invalid" if any("must be" in item or "required" in item for item in blockers[:3]) and not market_id else "blocked_by_guard" if blockers else "ready_for_manual_review"
    return status, blockers, warnings


def build_live_order_intent(
    *,
    market_id: str,
    outcome: str = "YES",
    side: str = "BUY",
    price: float = 0.5,
    size: float = 1.0,
    token_id: str = "",
    order_type: str = "limit",
    time_in_force: str = "GTC",
    operator: str = "local",
    note: str = "",
    source_ticket_id: str = "",
    source_approval_id: str = "",
    intent_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_market = _text(market_id)
    normalized_token = _text(token_id)
    normalized_outcome = _text(outcome or "YES", "YES").upper()
    normalized_side = _text(side or "BUY", "BUY").upper()
    normalized_order_type = _text(order_type or "limit", "limit").lower()
    normalized_tif = _text(time_in_force or "GTC", "GTC").upper()
    px = round(_safe_float(price), 6)
    qty = round(_safe_float(size), 6)
    notional = round(px * qty, 6)
    guard = _guard_snapshot()
    status, blockers, warnings = _evaluate_intent(
        market_id=normalized_market,
        token_id=normalized_token,
        side=normalized_side,
        price=px,
        size=qty,
        order_type=normalized_order_type,
        time_in_force=normalized_tif,
        guard=guard,
    )
    return {
        "intent_id": intent_id or f"loi_{uuid4().hex[:12]}",
        "version": "0.5.11-live-order-intent-v1",
        "mode": "live_order_intent_preview_v056",
        "created_at": created_at or _now(),
        "operator": _text(operator, "local"),
        "status": status,
        "market_id": normalized_market,
        "token_id": normalized_token,
        "outcome": normalized_outcome,
        "side": normalized_side,
        "order_type": normalized_order_type,
        "time_in_force": normalized_tif,
        "price": px,
        "size": qty,
        "notional": notional,
        "source_ticket_id": _text(source_ticket_id),
        "source_approval_id": _text(source_approval_id),
        "note": _text(note),
        "blockers": blockers,
        "warnings": warnings,
        "ready_for_manual_review": status == "ready_for_manual_review",
        "execution_allowed": False,
        "dry_run_only": True,
        "secret_values_returned": False,
        "guard_snapshot": guard,
        "next_required_action": "Resolve blockers and keep manual approval/audit gates before any future live adapter is added." if blockers else "Human may review the intent preview; this build still cannot submit or cancel orders.",
        "guardrail": "Local live-order intent preview only. This record never derives credentials, signs messages, posts orders, cancels orders, touches wallets, bypasses approvals, or automates trading.",
    }


def load_live_order_intents() -> list[dict[str, Any]]:
    rows = _read_json(INTENTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_live_order_intents(rows: list[dict[str, Any]]) -> None:
    _write_json(INTENTS_PATH, rows)


def record_live_order_intent(**kwargs: Any) -> dict[str, Any]:
    record = build_live_order_intent(**kwargs)
    rows = load_live_order_intents()
    rows.append(record)
    save_live_order_intents(rows)
    return record


def list_live_order_intents(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_live_order_intents()))
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted]
    if operator:
        wanted = _text(operator)
        rows = [row for row in rows if _text(row.get("operator")) == wanted]
    return rows[: max(0, int(limit))]


def get_live_order_intent(intent_id: str) -> dict[str, Any] | None:
    wanted = _text(intent_id)
    for row in load_live_order_intents():
        if _text(row.get("intent_id")) == wanted:
            return row
    return None


def summarize_live_order_intents(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    all_rows = load_live_order_intents()
    selected = rows if rows is not None else all_rows
    statuses = Counter(_text(row.get("status") or "unknown") for row in selected)
    total_notional = sum(_safe_float(row.get("notional")) for row in selected)
    latest = list(reversed(all_rows))[0] if all_rows else {}
    guard = _guard_snapshot()
    return {
        "count": len(selected),
        "saved_count": len(all_rows),
        "ready_for_manual_review": statuses.get("ready_for_manual_review", 0),
        "blocked_by_guard": statuses.get("blocked_by_guard", 0),
        "invalid": statuses.get("invalid", 0),
        "archived": statuses.get("archived", 0),
        "by_status": dict(sorted(statuses.items())),
        "total_preview_notional": round(total_notional, 6),
        "latest_intent_id": latest.get("intent_id", ""),
        "latest_status": latest.get("status", ""),
        "latest_created_at": latest.get("created_at", ""),
        "execution_available": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "readiness_state": guard.get("readiness_state"),
        "allowed_market_count": len(guard.get("allowed_market_ids") or []),
        "max_order_notional": guard.get("max_order_notional"),
        "guard_warning_count": guard.get("guard_warning_count"),
        "note": "Live order intents are local dry-run preview records only; they are not orders and cannot execute in this build.",
    }


def build_live_order_intent_board(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
) -> dict[str, Any]:
    rows = list_live_order_intents(limit=limit, status=status, market_id=market_id, operator=operator)
    sample_preview = build_live_order_intent(market_id=market_id or "", price=0.5, size=1.0, operator=operator or "local")
    return {
        "version": "0.5.11-live-order-intent-v1",
        "mode": "live_order_intent_board_v056",
        "generated_at": _now(),
        "summary": summarize_live_order_intents(rows),
        "items": rows,
        "sample_preview": sample_preview,
        "filters": {"status": status or "", "market_id": market_id or "", "operator": operator or ""},
        "guardrail": "Live order intents are staged local dry-run previews. They never submit orders, cancel orders, sign messages, connect wallets, or bypass manual approval/audit controls.",
    }


def live_order_intents_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "intent_id",
        "created_at",
        "operator",
        "status",
        "market_id",
        "token_id",
        "outcome",
        "side",
        "order_type",
        "time_in_force",
        "price",
        "size",
        "notional",
        "source_ticket_id",
        "source_approval_id",
        "ready_for_manual_review",
        "execution_allowed",
        "blockers",
        "warnings",
        "note",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        item = dict(row)
        item["blockers"] = _csv_join(list(item.get("blockers") or []))
        item["warnings"] = _csv_join(list(item.get("warnings") or []))
        writer.writerow({key: item.get(key, "") for key in fields})
    return output.getvalue()


def live_order_intent_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_live_order_intent_board(limit=25)
    summary = board.get("summary", {}) if isinstance(board, dict) else {}
    alerts: list[dict[str, Any]] = []
    if _safe_int(summary.get("blocked_by_guard")):
        alerts.append({
            "timestamp": _now(),
            "level": "warning",
            "kind": "live_order_intent_blocked",
            "title": "Live order intents are blocked by guardrails",
            "detail": f"{summary.get('blocked_by_guard')} saved live-order intent preview(s) are blocked by local guardrails.",
            "market_id": None,
            "question": None,
            "source": "live_order_intent_v056",
            "link": "/live-order-intents",
            "data": {"blocked_by_guard": summary.get("blocked_by_guard")},
        })
    if _safe_int(summary.get("ready_for_manual_review")):
        alerts.append({
            "timestamp": _now(),
            "level": "info",
            "kind": "live_order_intent_review",
            "title": "Live order intent preview awaits manual review",
            "detail": f"{summary.get('ready_for_manual_review')} saved intent preview(s) pass current preview checks, but execution remains disabled.",
            "market_id": None,
            "question": None,
            "source": "live_order_intent_v056",
            "link": "/live-order-intents",
            "data": {"ready_for_manual_review": summary.get("ready_for_manual_review")},
        })
    return alerts[:10]
