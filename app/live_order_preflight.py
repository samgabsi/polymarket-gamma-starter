from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .config import settings
from .live_config import build_live_config_readiness
from .live_order_intents import get_live_order_intent, list_live_order_intents
from .market_data import build_execution_quality_simulation, latest_market_snapshot
from .paper_approvals import get_execution_approval, latest_approval_for_ticket
from .paper_preflight import build_ticket_preflight
from .trade_tickets import get_trade_ticket

PREFLIGHT_STATES = {
    "ready_for_operator_authorization",
    "ready_with_warnings",
    "needs_paper_binding",
    "blocked_by_live_guard",
    "blocked",
    "invalid",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _live_guard_snapshot() -> dict[str, Any]:
    report = build_live_config_readiness()
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    controls = report.get("controls", {}) if isinstance(report, dict) else {}
    return {
        "readiness_state": summary.get("readiness_state"),
        "l2_credentials_ready": bool(summary.get("l2_credentials_ready")),
        "read_only": bool(summary.get("read_only")),
        "dry_run_only": bool(summary.get("dry_run_only")),
        "manual_approval_required": bool(summary.get("manual_approval_required")),
        "pretrade_checks_enabled": bool(summary.get("pretrade_checks_enabled")),
        "audit_required": bool(summary.get("audit_required")),
        "order_execution_available": bool(summary.get("order_execution_available")),
        "execution_adapter_present": bool(controls.get("execution_adapter_present")),
        "order_placement_enabled": bool(controls.get("order_placement_enabled")),
        "order_cancellation_enabled": bool(controls.get("order_cancellation_enabled")),
        "autonomous_trading_enabled": bool(controls.get("autonomous_trading_enabled")),
    }


def _latest_approval_note(ticket_id: str) -> str:
    latest = latest_approval_for_ticket(ticket_id) if ticket_id else None
    if not latest:
        return ""
    return f"Latest paper approval for ticket is {latest.get('approval_id')} with status {latest.get('status')}."


def _evaluate_preflight(intent: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str, *, severity: str = "blocker", kind: str = "governance") -> None:
        checks.append({
            "name": name,
            "passed": bool(passed),
            "severity": severity,
            "kind": kind,
            "blocking": bool(severity == "blocker" and not passed),
            "detail": detail,
        })
        if severity == "blocker" and not passed:
            blockers.append(detail)
        elif severity == "warning" and not passed:
            warnings.append(detail)
        elif severity == "warning" and passed and detail:
            warnings.append(detail)

    intent_id = _text(intent.get("intent_id"))
    market_id = _text(intent.get("market_id"))
    token_id = _text(intent.get("token_id"))
    intent_status = _text(intent.get("status") or "unknown")
    source_ticket_id = _text(intent.get("source_ticket_id"))
    source_approval_id = _text(intent.get("source_approval_id"))
    intent_notional = round(_safe_float(intent.get("notional")), 6)
    intent_price = _safe_float(intent.get("price"))
    intent_size = _safe_float(intent.get("size"))
    intent_outcome = _text(intent.get("outcome") or "YES").upper()
    guard = _live_guard_snapshot()
    market_data_quality: dict[str, Any] | None = None

    check("Intent exists", bool(intent_id), "Live order intent record is missing an intent_id.", kind="intent")
    check("Intent preview status", intent_status == "ready_for_manual_review", f"Intent preview status is {intent_status}; resolve preview blockers first.", kind="intent")
    check("Intent execution flag remains disabled", not bool(intent.get("execution_allowed")), "Intent unexpectedly reports execution_allowed=true; live preflight must never enable execution.", kind="intent")
    check("Token id present", bool(token_id), "token_id is required before a future CLOB adapter can bind this intent to an outcome token.", kind="intent")
    check("Notional positive", intent_notional > 0, f"Intent notional must be positive; current notional={intent_notional:g}.", kind="intent")

    for blocker in list(intent.get("blockers") or [])[:8]:
        check("Intent blocker snapshot", False, str(blocker), kind="intent")
    for warning in list(intent.get("warnings") or [])[:5]:
        check("Intent warning snapshot", True, str(warning), severity="warning", kind="intent")

    check("Read-only runtime guard", guard.get("read_only"), "READ_ONLY must remain true for this staged preflight build.", kind="live_guard")
    check("Dry-run runtime guard", guard.get("dry_run_only"), "LIVE_DRY_RUN_ONLY must remain true for this staged preflight build.", kind="live_guard")
    check("Manual approval guard", guard.get("manual_approval_required"), "LIVE_REQUIRE_MANUAL_APPROVAL must remain true before any future live action path.", kind="live_guard")
    check("Pre-trade checks guard", guard.get("pretrade_checks_enabled"), "LIVE_PRETRADE_CHECKS_ENABLED must remain true before any future live action path.", kind="live_guard")
    check("Audit guard", guard.get("audit_required"), "LIVE_AUDIT_REQUIRED must remain true before any future live action path.", kind="live_guard")
    check("No execution adapter", not guard.get("execution_adapter_present") and not guard.get("order_placement_enabled"), "Execution adapter/order placement is unexpectedly enabled; this build must stay non-executing.", kind="live_guard")
    if guard.get("order_cancellation_enabled") or guard.get("autonomous_trading_enabled"):
        check("No cancel/autonomous controls", False, "Cancellation/autonomous controls are unexpectedly enabled; this build must stay non-executing.", kind="live_guard")

    snapshot_row = latest_market_snapshot(market_id=market_id, token_id=token_id)
    if not snapshot_row:
        check(
            "Market-data snapshot present",
            not settings.market_data_require_for_live,
            "No local market-data snapshot found for this live intent. Record a snapshot before manual execution review.",
            severity="blocker" if settings.market_data_require_for_live else "warning",
            kind="market_data",
        )
    else:
        market_data_quality = build_execution_quality_simulation(
            side=_text(intent.get("side") or "BUY", "BUY"),
            market_id=market_id,
            token_id=token_id,
            price=intent_price,
            size=intent_size,
            order_type=_text(intent.get("order_type") or "limit", "limit"),
            time_in_force=_text(intent.get("time_in_force") or "GTC", "GTC"),
            snapshot_id=_text(snapshot_row.get("snapshot_id")),
            source_intent_id=intent_id,
        )
        state = _text(market_data_quality.get("state") or "unknown")
        quality_passed = state in {"quality_pass", "quality_pass_with_warnings"}
        check("Execution-quality simulation", quality_passed, f"execution_quality={state}; snapshot={market_data_quality.get('snapshot_id')}", kind="market_data")
        for blocker in list(market_data_quality.get("blockers") or [])[:5]:
            check("Execution-quality blocker", False, str(blocker), kind="market_data")
        for warning in list(market_data_quality.get("warnings") or [])[:5]:
            check("Execution-quality warning", True, str(warning), severity="warning", kind="market_data")

    ticket: dict[str, Any] | None = None
    paper_preflight: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None

    check("Source ticket id present", bool(source_ticket_id), "source_ticket_id is required to bind a live intent back to a paper trade ticket.", kind="paper_binding")
    if source_ticket_id:
        ticket = get_trade_ticket(source_ticket_id)
        check("Source ticket found", ticket is not None, f"Source ticket {source_ticket_id} was not found in local paper tickets.", kind="paper_binding")
        if ticket:
            ticket_market = _text(ticket.get("market_id"))
            ticket_outcome = _text(ticket.get("outcome") or "YES").upper()
            ticket_stake = _safe_float(ticket.get("stake"))
            ticket_price = _safe_float(ticket.get("price"))
            check("Ticket market matches intent", ticket_market == market_id, f"Ticket market {ticket_market or 'unknown'} does not match intent market {market_id or 'unknown'}.", kind="paper_binding")
            check("Ticket outcome matches intent", ticket_outcome == intent_outcome, f"Ticket outcome {ticket_outcome or 'unknown'} does not match intent outcome {intent_outcome or 'unknown'}.", kind="paper_binding")
            check("Ticket is paper_ready", _text(ticket.get("status")) == "paper_ready", f"Source ticket status is {_text(ticket.get('status') or 'unknown')}; expected paper_ready.", kind="paper_binding")
            check("Intent notional within ticket stake", intent_notional <= ticket_stake + 0.000001, f"Intent notional ${intent_notional:.4f} exceeds source ticket stake ${ticket_stake:.4f}.", kind="risk")
            if abs(ticket_price - intent_price) > 0.02:
                check("Ticket price drift", False, f"Intent price {intent_price:.4f} differs from source ticket price {ticket_price:.4f} by more than 0.02; re-check market before any future execution.", severity="warning", kind="paper_binding")
            try:
                paper_preflight = build_ticket_preflight(ticket)
                check("Current paper preflight approved", bool(paper_preflight.get("approved")), f"Current paper preflight status is {paper_preflight.get('status') or 'unknown'}.", kind="paper_preflight")
                for blocker in list(paper_preflight.get("blockers") or [])[:5]:
                    detail = str(blocker.get("detail") or blocker.get("name") or blocker)
                    check("Paper preflight blocker", False, detail, kind="paper_preflight")
                for warning in list(paper_preflight.get("warnings") or [])[:5]:
                    detail = str(warning.get("detail") or warning.get("name") or warning)
                    check("Paper preflight warning", True, detail, severity="warning", kind="paper_preflight")
            except Exception as exc:  # noqa: BLE001 - local report must degrade safely
                check("Current paper preflight available", False, f"Could not rebuild current paper preflight for {source_ticket_id}: {exc}", kind="paper_preflight")

    check("Source approval id present", bool(source_approval_id), "source_approval_id is required; latest approval is not used implicitly for live readiness.", kind="paper_binding")
    if not source_approval_id and source_ticket_id:
        latest_note = _latest_approval_note(source_ticket_id)
        if latest_note:
            check("Latest approval hint", True, latest_note, severity="warning", kind="paper_binding")
    if source_approval_id:
        approval = get_execution_approval(source_approval_id)
        check("Source approval found", approval is not None, f"Source approval {source_approval_id} was not found in local paper approvals.", kind="paper_binding")
        if approval:
            check("Approval status is approved", _text(approval.get("status")) == "approved", f"Source approval status is {_text(approval.get('status') or 'unknown')}; expected approved.", kind="paper_binding")
            check("Approval ticket matches intent ticket", _text(approval.get("ticket_id")) == source_ticket_id, f"Approval ticket {_text(approval.get('ticket_id') or 'unknown')} does not match intent ticket {source_ticket_id or 'unknown'}.", kind="paper_binding")
            check("Approval market matches intent", _text(approval.get("market_id")) == market_id, f"Approval market {_text(approval.get('market_id') or 'unknown')} does not match intent market {market_id or 'unknown'}.", kind="paper_binding")
            check("Intent notional within approved stake", intent_notional <= _safe_float(approval.get("stake")) + 0.000001, f"Intent notional ${intent_notional:.4f} exceeds approved paper stake ${_safe_float(approval.get('stake')):.4f}.", kind="risk")
            if _safe_int(approval.get("warning_count")):
                check("Approval warning snapshot", True, approval.get("warning_summary") or f"Approval has {approval.get('warning_count')} warning(s).", severity="warning", kind="paper_binding")

    if intent_status == "invalid":
        state = "invalid"
    elif intent_status == "blocked_by_guard" or any(row.get("kind") == "live_guard" and row.get("blocking") for row in checks):
        state = "blocked_by_live_guard"
    elif any(row.get("kind") == "paper_binding" and row.get("blocking") for row in checks):
        state = "needs_paper_binding"
    elif blockers:
        state = "blocked"
    elif warnings:
        state = "ready_with_warnings"
    else:
        state = "ready_for_operator_authorization"

    return {
        "review_id": f"lop_{intent_id}" if intent_id else "lop_unknown",
        "version": "0.5.11-live-order-preflight-v1",
        "mode": "live_order_intent_preflight_v057",
        "generated_at": _now(),
        "state": state,
        "intent_id": intent_id,
        "intent_status": intent_status,
        "created_at": intent.get("created_at"),
        "operator": intent.get("operator"),
        "market_id": market_id,
        "token_id": token_id,
        "outcome": intent_outcome,
        "side": intent.get("side"),
        "order_type": intent.get("order_type"),
        "time_in_force": intent.get("time_in_force"),
        "price": intent_price,
        "size": _safe_float(intent.get("size")),
        "notional": intent_notional,
        "source_ticket_id": source_ticket_id,
        "source_approval_id": source_approval_id,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "ticket_status": ticket.get("status") if ticket else "missing" if source_ticket_id else "not_provided",
        "approval_status": approval.get("status") if approval else "missing" if source_approval_id else "not_provided",
        "paper_preflight_status": paper_preflight.get("status") if paper_preflight else "not_available",
        "paper_preflight_approved": bool(paper_preflight.get("approved")) if paper_preflight else False,
        "market_data_status": (market_data_quality or {}).get("state", "missing"),
        "market_data_snapshot_id": (market_data_quality or {}).get("snapshot_id", ""),
        "market_data_quality": market_data_quality,
        "live_guard_snapshot": guard,
        "ready_for_operator_authorization": state in {"ready_for_operator_authorization", "ready_with_warnings"},
        "execution_allowed": False,
        "secret_values_returned": False,
        "next_required_action": _next_action(state),
        "guardrail": "Read-only live-intent preflight review. It validates local paper/governance bindings for future staged live testing, but never signs, submits, cancels, or automates orders.",
    }


def _next_action(state: str) -> str:
    if state == "ready_for_operator_authorization":
        return "Human may perform a final authorization review in a future execution-capable build; this build still cannot execute."
    if state == "ready_with_warnings":
        return "Review warnings before any future operator authorization. Execution remains unavailable."
    if state == "needs_paper_binding":
        return "Bind the intent to an explicit paper ticket and explicit approved paper approval record."
    if state == "blocked_by_live_guard":
        return "Resolve live readiness/config guard blockers while keeping dry-run/manual approval/audit gates intact."
    if state == "invalid":
        return "Correct invalid intent fields and record a new local intent preview."
    return "Resolve blockers before considering any future live authorization workflow."


def review_live_order_intent(intent_id: str) -> dict[str, Any] | None:
    intent = get_live_order_intent(intent_id)
    if not intent:
        return None
    return _evaluate_preflight(intent)


def list_live_order_preflights(
    *,
    limit: int = 100,
    state: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
) -> list[dict[str, Any]]:
    rows = [_evaluate_preflight(row) for row in list_live_order_intents(limit=10000, market_id=market_id, operator=operator)]
    if state:
        wanted = _text(state)
        rows = [row for row in rows if _text(row.get("state")) == wanted]
    return rows[: max(0, int(limit))]


def summarize_live_order_preflights(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else list_live_order_preflights(limit=10000)
    states = Counter(_text(row.get("state") or "unknown") for row in rows)
    blockers = sum(_safe_int(row.get("blocker_count")) for row in rows)
    warnings = sum(_safe_int(row.get("warning_count")) for row in rows)
    notional = sum(_safe_float(row.get("notional")) for row in rows)
    market_data_missing = sum(1 for row in rows if _text(row.get("market_data_status")) == "missing")
    market_data_blocked = sum(1 for row in rows if _text(row.get("market_data_status")) not in {"", "missing", "quality_pass", "quality_pass_with_warnings"})
    return {
        "count": len(rows),
        "by_state": dict(sorted(states.items())),
        "ready_for_operator_authorization": states.get("ready_for_operator_authorization", 0),
        "ready_with_warnings": states.get("ready_with_warnings", 0),
        "needs_paper_binding": states.get("needs_paper_binding", 0),
        "blocked_by_live_guard": states.get("blocked_by_live_guard", 0),
        "blocked": states.get("blocked", 0),
        "invalid": states.get("invalid", 0),
        "total_blockers": blockers,
        "total_warnings": warnings,
        "total_review_notional": round(notional, 6),
        "market_data_missing": market_data_missing,
        "market_data_blocked": market_data_blocked,
        "execution_available": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "note": "Live-intent preflight is local review only. Ready states still do not permit live execution in this build.",
    }


def build_live_order_preflight_board(
    *,
    limit: int = 100,
    state: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
) -> dict[str, Any]:
    rows = list_live_order_preflights(limit=limit, state=state, market_id=market_id, operator=operator)
    return {
        "version": "0.5.11-live-order-preflight-v1",
        "mode": "live_order_intent_preflight_board_v057",
        "generated_at": _now(),
        "summary": summarize_live_order_preflights(rows),
        "items": rows,
        "filters": {"state": state or "", "market_id": market_id or "", "operator": operator or ""},
        "guardrail": "Live intent preflight only verifies local bindings and guard state. It never signs, submits, cancels, or automates orders.",
    }


def live_order_preflights_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "generated_at",
        "review_id",
        "state",
        "intent_id",
        "intent_status",
        "created_at",
        "operator",
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
        "ticket_status",
        "source_approval_id",
        "approval_status",
        "paper_preflight_status",
        "paper_preflight_approved",
        "market_data_status",
        "market_data_snapshot_id",
        "blocker_count",
        "warning_count",
        "execution_allowed",
        "blockers",
        "warnings",
        "next_required_action",
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


def live_order_preflight_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_live_order_preflight_board(limit=25)
    summary = board.get("summary", {}) if isinstance(board, dict) else {}
    alerts: list[dict[str, Any]] = []
    blocked_count = _safe_int(summary.get("blocked_by_live_guard")) + _safe_int(summary.get("blocked")) + _safe_int(summary.get("invalid"))
    binding_count = _safe_int(summary.get("needs_paper_binding"))
    ready_count = _safe_int(summary.get("ready_for_operator_authorization")) + _safe_int(summary.get("ready_with_warnings"))
    if blocked_count:
        alerts.append({
            "timestamp": _now(),
            "level": "warning",
            "kind": "live_order_preflight_blocked",
            "title": "Live intent preflight blockers exist",
            "detail": f"{blocked_count} live-intent preflight review(s) have live guard, invalid-field, or governance blockers.",
            "market_id": None,
            "question": None,
            "source": "live_order_preflight_v057",
            "link": "/live-order-intent-preflight",
            "data": {"blocked": blocked_count},
        })
    if binding_count:
        alerts.append({
            "timestamp": _now(),
            "level": "info",
            "kind": "live_order_preflight_binding",
            "title": "Live intents need explicit paper binding",
            "detail": f"{binding_count} intent preview(s) need an explicit paper ticket and approval ID before future authorization review.",
            "market_id": None,
            "question": None,
            "source": "live_order_preflight_v057",
            "link": "/live-order-intent-preflight",
            "data": {"needs_paper_binding": binding_count},
        })
    if ready_count:
        alerts.append({
            "timestamp": _now(),
            "level": "info",
            "kind": "live_order_preflight_ready_review",
            "title": "Live intent preflight is ready for operator review",
            "detail": f"{ready_count} intent preflight review(s) pass local binding checks, but execution remains disabled.",
            "market_id": None,
            "question": None,
            "source": "live_order_preflight_v057",
            "link": "/live-order-intent-preflight",
            "data": {"ready": ready_count},
        })
    return alerts[:10]
