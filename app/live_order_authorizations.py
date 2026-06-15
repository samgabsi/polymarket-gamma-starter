from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR
from .live_order_preflight import review_live_order_intent

AUTHORIZATIONS_PATH = DATA_DIR / "live" / "live_order_authorizations.json"
AUTHORIZATION_DECISIONS = {"authorize", "reject", "defer"}
AUTHORIZATION_STATUSES = {
    "authorized_dry_run",
    "authorized_with_warnings",
    "rejected",
    "deferred",
    "blocked_by_preflight",
    "invalid",
}
AUTHORIZABLE_PREFLIGHT_STATES = {"ready_for_operator_authorization", "ready_with_warnings"}


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


def _snapshot_hash(payload: dict[str, Any]) -> str:
    material = {
        "intent_id": payload.get("intent_id"),
        "decision": payload.get("decision"),
        "status": payload.get("status"),
        "preflight_state_snapshot": payload.get("preflight_state_snapshot"),
        "market_id": payload.get("market_id"),
        "token_id": payload.get("token_id"),
        "outcome": payload.get("outcome"),
        "side": payload.get("side"),
        "order_type": payload.get("order_type"),
        "time_in_force": payload.get("time_in_force"),
        "price": payload.get("price"),
        "size": payload.get("size"),
        "notional": payload.get("notional"),
        "source_ticket_id": payload.get("source_ticket_id"),
        "source_approval_id": payload.get("source_approval_id"),
        "blockers_snapshot": payload.get("blockers_snapshot"),
        "warnings_snapshot": payload.get("warnings_snapshot"),
        "acknowledgement": payload.get("acknowledgement"),
    }
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _derive_status(decision: str, preflight: dict[str, Any] | None, acknowledged: bool) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    normalized = _text(decision or "authorize", "authorize").lower()
    if normalized not in AUTHORIZATION_DECISIONS:
        return "invalid", [f"decision must be one of {', '.join(sorted(AUTHORIZATION_DECISIONS))}."], warnings
    if not preflight:
        return "invalid", ["intent preflight review was not found."], warnings

    state = _text(preflight.get("state"))
    blockers.extend(str(item) for item in list(preflight.get("blockers") or [])[:8])
    warnings.extend(str(item) for item in list(preflight.get("warnings") or [])[:8])

    if normalized == "reject":
        return "rejected", [], warnings
    if normalized == "defer":
        return "deferred", [], warnings

    if not acknowledged:
        blockers.append("operator acknowledgement is required before recording an authorization snapshot.")
    if state not in AUTHORIZABLE_PREFLIGHT_STATES:
        blockers.append(f"preflight state {state or 'unknown'} is not authorizable; resolve blockers or record a rejection/defer decision.")
    if bool(preflight.get("execution_allowed")):
        blockers.append("preflight unexpectedly reports execution_allowed=true; authorization ledger must remain non-executing.")

    if blockers:
        return "blocked_by_preflight", blockers, warnings
    if state == "ready_with_warnings" or warnings:
        return "authorized_with_warnings", blockers, warnings
    return "authorized_dry_run", blockers, warnings


def _compact_preflight(preflight: dict[str, Any] | None) -> dict[str, Any]:
    if not preflight:
        return {}
    return {
        "review_id": _text(preflight.get("review_id")),
        "state": _text(preflight.get("state")),
        "generated_at": _text(preflight.get("generated_at")),
        "intent_status": _text(preflight.get("intent_status")),
        "paper_preflight_status": _text(preflight.get("paper_preflight_status")),
        "paper_preflight_approved": bool(preflight.get("paper_preflight_approved")),
        "ticket_status": _text(preflight.get("ticket_status")),
        "approval_status": _text(preflight.get("approval_status")),
        "blocker_count": _safe_int(preflight.get("blocker_count")),
        "warning_count": _safe_int(preflight.get("warning_count")),
        "checks": list(preflight.get("checks") or [])[:25],
    }


def load_live_order_authorizations() -> list[dict[str, Any]]:
    rows = _read_json(AUTHORIZATIONS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_live_order_authorizations(rows: list[dict[str, Any]]) -> None:
    _write_json(AUTHORIZATIONS_PATH, rows)


def build_live_order_authorization_packet(
    *,
    intent_id: str,
    decision: str = "authorize",
    operator: str = "local",
    note: str = "",
    acknowledged: bool = False,
    authorization_id: str | None = None,
    created_at: str | None = None,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preflight = preflight if preflight is not None else review_live_order_intent(intent_id)
    normalized_decision = _text(decision or "authorize", "authorize").lower()
    status, blockers, warnings = _derive_status(normalized_decision, preflight, acknowledged)
    preflight = preflight or {}
    packet = {
        "authorization_id": authorization_id or f"loa_{uuid4().hex[:12]}",
        "version": "0.5.11-live-order-authorization-v1",
        "mode": "live_order_operator_authorization_v058",
        "created_at": created_at or _now(),
        "operator": _text(operator, "local"),
        "decision": normalized_decision,
        "status": status,
        "intent_id": _text(intent_id),
        "preflight_review_id": _text(preflight.get("review_id")),
        "preflight_state_snapshot": _text(preflight.get("state") or "missing"),
        "preflight_generated_at_snapshot": _text(preflight.get("generated_at")),
        "intent_status_snapshot": _text(preflight.get("intent_status")),
        "market_id": _text(preflight.get("market_id")),
        "token_id": _text(preflight.get("token_id")),
        "outcome": _text(preflight.get("outcome")),
        "side": _text(preflight.get("side")),
        "order_type": _text(preflight.get("order_type")),
        "time_in_force": _text(preflight.get("time_in_force")),
        "price": _safe_float(preflight.get("price")),
        "size": _safe_float(preflight.get("size")),
        "notional": round(_safe_float(preflight.get("notional")), 6),
        "source_ticket_id": _text(preflight.get("source_ticket_id")),
        "source_approval_id": _text(preflight.get("source_approval_id")),
        "paper_preflight_status_snapshot": _text(preflight.get("paper_preflight_status")),
        "paper_preflight_approved_snapshot": bool(preflight.get("paper_preflight_approved")),
        "ticket_status_snapshot": _text(preflight.get("ticket_status")),
        "approval_status_snapshot": _text(preflight.get("approval_status")),
        "blocker_count_snapshot": len(blockers),
        "warning_count_snapshot": len(warnings),
        "blockers_snapshot": blockers,
        "warnings_snapshot": warnings,
        "preflight_snapshot": _compact_preflight(preflight),
        "acknowledgement": bool(acknowledged),
        "note": _text(note),
        "authorization_effective": status in {"authorized_dry_run", "authorized_with_warnings"},
        "execution_allowed": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "secret_values_returned": False,
        "next_required_action": _next_required_action(status),
        "guardrail": "Local operator authorization snapshot only. It does not sign, submit, cancel, automate, touch wallets, derive credentials, or bypass preflight/risk/audit controls.",
    }
    packet["authorization_hash"] = _snapshot_hash(packet)
    return packet


def _next_required_action(status: str) -> str:
    if status == "authorized_dry_run":
        return "Authorization snapshot recorded for future staged execution review; execution remains unavailable in this build."
    if status == "authorized_with_warnings":
        return "Authorization snapshot recorded with warnings; review warnings before any future execution-capable build."
    if status == "rejected":
        return "Operator rejected this intent; do not carry it forward without recording a new intent/preflight."
    if status == "deferred":
        return "Operator deferred this intent; revisit after updated research, paper workflow, or guard review."
    if status == "blocked_by_preflight":
        return "Resolve preflight blockers or record a reject/defer decision."
    return "Correct the authorization request and retry only after review."


def record_live_order_authorization(
    *,
    intent_id: str,
    decision: str = "authorize",
    operator: str = "local",
    note: str = "",
    acknowledged: bool = False,
) -> dict[str, Any]:
    record = build_live_order_authorization_packet(
        intent_id=intent_id,
        decision=decision,
        operator=operator,
        note=note,
        acknowledged=acknowledged,
    )
    rows = load_live_order_authorizations()
    rows.append(record)
    save_live_order_authorizations(rows)
    return record


def list_live_order_authorizations(
    *,
    limit: int = 100,
    status: str | None = None,
    decision: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    intent_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_live_order_authorizations()))
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if decision:
        wanted = _text(decision).lower()
        rows = [row for row in rows if _text(row.get("decision")).lower() == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted]
    if operator:
        wanted = _text(operator)
        rows = [row for row in rows if _text(row.get("operator")) == wanted]
    if intent_id:
        wanted = _text(intent_id)
        rows = [row for row in rows if _text(row.get("intent_id")) == wanted]
    return rows[: max(0, int(limit))]


def get_live_order_authorization(authorization_id: str) -> dict[str, Any] | None:
    wanted = _text(authorization_id)
    for row in load_live_order_authorizations():
        if _text(row.get("authorization_id")) == wanted:
            return row
    return None


def latest_live_order_authorization_for_intent(intent_id: str) -> dict[str, Any] | None:
    rows = list_live_order_authorizations(limit=1, intent_id=intent_id)
    return rows[0] if rows else None


def summarize_live_order_authorizations(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    all_rows = load_live_order_authorizations()
    selected = rows if rows is not None else list(reversed(all_rows))
    statuses = Counter(_text(row.get("status") or "unknown") for row in selected)
    decisions = Counter(_text(row.get("decision") or "unknown") for row in selected)
    latest = list(reversed(all_rows))[0] if all_rows else {}
    return {
        "count": len(selected),
        "saved_count": len(all_rows),
        "authorized_dry_run": statuses.get("authorized_dry_run", 0),
        "authorized_with_warnings": statuses.get("authorized_with_warnings", 0),
        "rejected": statuses.get("rejected", 0),
        "deferred": statuses.get("deferred", 0),
        "blocked_by_preflight": statuses.get("blocked_by_preflight", 0),
        "invalid": statuses.get("invalid", 0),
        "authorized_total": statuses.get("authorized_dry_run", 0) + statuses.get("authorized_with_warnings", 0),
        "by_status": dict(sorted(statuses.items())),
        "by_decision": dict(sorted(decisions.items())),
        "total_authorized_notional": round(sum(_safe_float(row.get("notional")) for row in selected if row.get("authorization_effective")), 6),
        "latest_authorization_id": latest.get("authorization_id", ""),
        "latest_status": latest.get("status", ""),
        "latest_created_at": latest.get("created_at", ""),
        "execution_available": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "note": "Live operator authorizations are local documentation snapshots only; they do not execute orders.",
    }


def build_live_order_authorization_board(
    *,
    limit: int = 100,
    status: str | None = None,
    decision: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    intent_id: str | None = None,
) -> dict[str, Any]:
    rows = list_live_order_authorizations(limit=limit, status=status, decision=decision, market_id=market_id, operator=operator, intent_id=intent_id)
    return {
        "version": "0.5.11-live-order-authorization-v1",
        "mode": "live_order_operator_authorization_board_v058",
        "generated_at": _now(),
        "summary": summarize_live_order_authorizations(rows),
        "items": rows,
        "filters": {
            "status": status or "",
            "decision": decision or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "intent_id": intent_id or "",
        },
        "guardrail": "Live operator authorizations are local human review records only. They never sign, submit, cancel, automate, touch wallets, or override preflight/risk/audit controls.",
    }


def live_order_authorizations_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "authorization_id",
        "created_at",
        "operator",
        "decision",
        "status",
        "intent_id",
        "preflight_review_id",
        "preflight_state_snapshot",
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
        "acknowledgement",
        "authorization_effective",
        "execution_allowed",
        "blocker_count_snapshot",
        "warning_count_snapshot",
        "blockers_snapshot",
        "warnings_snapshot",
        "authorization_hash",
        "note",
        "next_required_action",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        item = dict(row)
        item["blockers_snapshot"] = _csv_join(list(item.get("blockers_snapshot") or []))
        item["warnings_snapshot"] = _csv_join(list(item.get("warnings_snapshot") or []))
        writer.writerow({key: item.get(key, "") for key in fields})
    return output.getvalue()


def live_order_authorization_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_live_order_authorization_board(limit=25)
    summary = board.get("summary", {}) if isinstance(board, dict) else {}
    alerts: list[dict[str, Any]] = []
    blocked = _safe_int(summary.get("blocked_by_preflight")) + _safe_int(summary.get("invalid"))
    authorized = _safe_int(summary.get("authorized_total"))
    deferred = _safe_int(summary.get("deferred"))
    if blocked:
        alerts.append({
            "timestamp": _now(),
            "level": "warning",
            "kind": "live_order_authorization_blocked",
            "title": "Live authorization records are blocked",
            "detail": f"{blocked} live operator authorization record(s) were blocked by preflight or invalid request fields.",
            "market_id": None,
            "question": None,
            "source": "live_order_authorization_v058",
            "link": "/live-order-authorizations",
            "data": {"blocked": blocked},
        })
    if authorized:
        alerts.append({
            "timestamp": _now(),
            "level": "info",
            "kind": "live_order_authorization_recorded",
            "title": "Live operator authorization snapshots exist",
            "detail": f"{authorized} non-executing authorization snapshot(s) are recorded for future staged review; execution remains disabled.",
            "market_id": None,
            "question": None,
            "source": "live_order_authorization_v058",
            "link": "/live-order-authorizations",
            "data": {"authorized": authorized},
        })
    if deferred:
        alerts.append({
            "timestamp": _now(),
            "level": "info",
            "kind": "live_order_authorization_deferred",
            "title": "Live intents deferred by operator",
            "detail": f"{deferred} authorization decision(s) were deferred for later review.",
            "market_id": None,
            "question": None,
            "source": "live_order_authorization_v058",
            "link": "/live-order-authorizations",
            "data": {"deferred": deferred},
        })
    return alerts[:10]
