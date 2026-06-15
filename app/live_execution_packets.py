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
from .live_order_authorizations import get_live_order_authorization, latest_live_order_authorization_for_intent
from .live_order_intents import get_live_order_intent
from .live_order_preflight import review_live_order_intent

EXECUTION_PACKETS_PATH = DATA_DIR / "live" / "live_execution_packets.json"
PACKET_READY_STATUSES = {"packet_ready_dry_run", "packet_ready_with_warnings"}
AUTHORIZED_STATUSES = {"authorized_dry_run", "authorized_with_warnings"}
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


def _rounded(value: Any) -> float:
    return round(_safe_float(value), 6)


def _packet_hash(payload: dict[str, Any]) -> str:
    material = {
        "intent_id": payload.get("intent_id"),
        "authorization_id": payload.get("authorization_id"),
        "authorization_hash": payload.get("authorization_hash"),
        "status": payload.get("status"),
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
        "preflight_state_snapshot": payload.get("preflight_state_snapshot"),
        "authorization_status_snapshot": payload.get("authorization_status_snapshot"),
        "wire_order_preview": payload.get("wire_order_preview"),
    }
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _latest_or_requested_authorization(intent_id: str, authorization_id: str | None = None) -> dict[str, Any] | None:
    if authorization_id:
        return get_live_order_authorization(authorization_id)
    return latest_live_order_authorization_for_intent(intent_id)


def _matches(a: Any, b: Any) -> bool:
    return _text(a) == _text(b)


def _float_matches(a: Any, b: Any, tolerance: float = 0.000001) -> bool:
    return abs(_safe_float(a) - _safe_float(b)) <= tolerance


def _derive_packet_status(
    *,
    intent: dict[str, Any] | None,
    preflight: dict[str, Any] | None,
    authorization: dict[str, Any] | None,
) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []

    if not intent:
        return "invalid", ["saved live order intent was not found."], warnings
    if not preflight:
        return "invalid", ["current live order intent preflight was not found."], warnings
    if not authorization:
        return "blocked_by_authorization", ["a live operator authorization snapshot is required before packaging."], warnings

    auth_intent_id = _text(authorization.get("intent_id"))
    intent_id = _text(intent.get("intent_id"))
    if auth_intent_id != intent_id:
        blockers.append(f"authorization intent {auth_intent_id or 'unknown'} does not match requested intent {intent_id or 'unknown'}.")

    auth_status = _text(authorization.get("status"))
    if auth_status not in AUTHORIZED_STATUSES:
        blockers.append(f"authorization status {auth_status or 'unknown'} is not packageable; expected authorized_dry_run or authorized_with_warnings.")
    if _text(authorization.get("decision")).lower() != "authorize":
        blockers.append("authorization decision is not authorize.")
    if not bool(authorization.get("acknowledgement")):
        blockers.append("authorization acknowledgement is missing.")
    if not bool(authorization.get("authorization_effective")):
        blockers.append("authorization snapshot is not effective.")
    if bool(authorization.get("execution_allowed")):
        blockers.append("authorization unexpectedly reports execution_allowed=true; packet generation must remain non-executing.")

    state = _text(preflight.get("state"))
    if state not in AUTHORIZABLE_PREFLIGHT_STATES:
        blockers.append(f"current preflight state {state or 'unknown'} is not packageable.")
    if bool(preflight.get("execution_allowed")):
        blockers.append("preflight unexpectedly reports execution_allowed=true; packet generation must remain non-executing.")

    for key in ["market_id", "token_id", "outcome", "side", "order_type", "time_in_force", "source_ticket_id", "source_approval_id"]:
        if not _matches(authorization.get(key), preflight.get(key)):
            blockers.append(f"authorization {key} does not match current preflight {key}.")
    for key in ["price", "size", "notional"]:
        if not _float_matches(authorization.get(key), preflight.get(key)):
            blockers.append(f"authorization {key} does not match current preflight {key}.")

    token_id = _text(preflight.get("token_id"))
    if not token_id:
        blockers.append("token_id is required before an execution packet can be considered ready for future adapter testing.")

    warnings.extend(str(item) for item in list(preflight.get("warnings") or [])[:8])
    warnings.extend(str(item) for item in list(authorization.get("warnings_snapshot") or [])[:8])
    if _text(authorization.get("preflight_state_snapshot")) != state:
        warnings.append("authorization was recorded against a different preflight state than the current review; inspect drift before future execution testing.")
    if _text(authorization.get("preflight_review_id")) != _text(preflight.get("review_id")):
        warnings.append("authorization preflight review id differs from the current generated review id; this may be normal for regenerated read-only reviews.")

    if blockers:
        if any("preflight" in item.lower() for item in blockers):
            return "blocked_by_preflight", blockers, warnings
        return "blocked_by_authorization", blockers, warnings
    if auth_status == "authorized_with_warnings" or state == "ready_with_warnings" or warnings:
        return "packet_ready_with_warnings", blockers, warnings
    return "packet_ready_dry_run", blockers, warnings


def _wire_order_preview(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "market_id": _text(preflight.get("market_id")),
        "asset_id": _text(preflight.get("token_id")),
        "outcome": _text(preflight.get("outcome")),
        "side": _text(preflight.get("side")),
        "order_type": _text(preflight.get("order_type")),
        "time_in_force": _text(preflight.get("time_in_force")),
        "price": _rounded(preflight.get("price")),
        "size": _rounded(preflight.get("size")),
        "notional": _rounded(preflight.get("notional")),
        "source_ticket_id": _text(preflight.get("source_ticket_id")),
        "source_approval_id": _text(preflight.get("source_approval_id")),
    }


def _next_action(status: str) -> str:
    if status == "packet_ready_dry_run":
        return "Packet is ready for offline review or export. This build still cannot submit, sign, cancel, or automate orders."
    if status == "packet_ready_with_warnings":
        return "Packet is exportable with warnings; review all warnings before any future execution-capable build."
    if status == "blocked_by_authorization":
        return "Record a valid acknowledged operator authorization snapshot before packaging this intent."
    if status == "blocked_by_preflight":
        return "Resolve current live-intent preflight blockers before packaging this intent."
    return "Correct the source intent/authorization inputs and retry only after review."


def build_live_execution_packet(
    *,
    intent_id: str,
    authorization_id: str | None = None,
    operator: str = "local",
    note: str = "",
    packet_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    intent = get_live_order_intent(intent_id)
    preflight = review_live_order_intent(intent_id) if intent else None
    authorization = _latest_or_requested_authorization(intent_id, authorization_id)
    status, blockers, warnings = _derive_packet_status(intent=intent, preflight=preflight, authorization=authorization)
    intent = intent or {}
    preflight = preflight or {}
    authorization = authorization or {}
    wire_preview = _wire_order_preview(preflight)
    packet = {
        "packet_id": packet_id or f"lep_{uuid4().hex[:12]}",
        "version": "0.5.11-live-execution-packet-v1",
        "mode": "live_execution_packet_v059",
        "created_at": created_at or _now(),
        "operator": _text(operator, "local"),
        "status": status,
        "intent_id": _text(intent_id),
        "authorization_id": _text(authorization.get("authorization_id")),
        "authorization_hash": _text(authorization.get("authorization_hash")),
        "authorization_status_snapshot": _text(authorization.get("status") or "missing"),
        "authorization_decision_snapshot": _text(authorization.get("decision")),
        "authorization_created_at_snapshot": _text(authorization.get("created_at")),
        "authorization_acknowledged_snapshot": bool(authorization.get("acknowledgement")),
        "preflight_review_id": _text(preflight.get("review_id")),
        "preflight_state_snapshot": _text(preflight.get("state") or "missing"),
        "preflight_generated_at_snapshot": _text(preflight.get("generated_at")),
        "intent_status_snapshot": _text(intent.get("status") or preflight.get("intent_status")),
        "market_id": _text(preflight.get("market_id") or intent.get("market_id")),
        "token_id": _text(preflight.get("token_id") or intent.get("token_id")),
        "outcome": _text(preflight.get("outcome") or intent.get("outcome")),
        "side": _text(preflight.get("side") or intent.get("side")),
        "order_type": _text(preflight.get("order_type") or intent.get("order_type")),
        "time_in_force": _text(preflight.get("time_in_force") or intent.get("time_in_force")),
        "price": _rounded(preflight.get("price") or intent.get("price")),
        "size": _rounded(preflight.get("size") or intent.get("size")),
        "notional": _rounded(preflight.get("notional") or intent.get("notional")),
        "source_ticket_id": _text(preflight.get("source_ticket_id") or intent.get("source_ticket_id")),
        "source_approval_id": _text(preflight.get("source_approval_id") or intent.get("source_approval_id")),
        "paper_preflight_status_snapshot": _text(preflight.get("paper_preflight_status")),
        "paper_preflight_approved_snapshot": bool(preflight.get("paper_preflight_approved")),
        "ticket_status_snapshot": _text(preflight.get("ticket_status")),
        "approval_status_snapshot": _text(preflight.get("approval_status")),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "wire_order_preview": wire_preview,
        "authorization_snapshot": {
            "authorization_id": _text(authorization.get("authorization_id")),
            "status": _text(authorization.get("status")),
            "decision": _text(authorization.get("decision")),
            "authorization_hash": _text(authorization.get("authorization_hash")),
            "acknowledgement": bool(authorization.get("acknowledgement")),
        },
        "preflight_snapshot": {
            "review_id": _text(preflight.get("review_id")),
            "state": _text(preflight.get("state")),
            "blocker_count": _safe_int(preflight.get("blocker_count")),
            "warning_count": _safe_int(preflight.get("warning_count")),
            "checks": list(preflight.get("checks") or [])[:25],
        },
        "packet_ready_for_future_adapter": status in PACKET_READY_STATUSES,
        "unsigned_only": True,
        "signed_payload_present": False,
        "exchange_order_id": "",
        "exchange_acknowledgement": False,
        "execution_allowed": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "autonomous_trading_enabled": False,
        "secret_values_returned": False,
        "note": _text(note),
        "next_required_action": _next_action(status),
        "guardrail": "Unsigned local execution packet only. It packages reviewed intent fields for future adapter design, but never signs, submits, cancels, automates, touches wallets, derives credentials, or bypasses preflight/risk/audit controls.",
    }
    packet["packet_hash"] = _packet_hash(packet)
    return packet


def load_live_execution_packets() -> list[dict[str, Any]]:
    rows = _read_json(EXECUTION_PACKETS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_live_execution_packets(rows: list[dict[str, Any]]) -> None:
    _write_json(EXECUTION_PACKETS_PATH, rows)


def record_live_execution_packet(
    *,
    intent_id: str,
    authorization_id: str | None = None,
    operator: str = "local",
    note: str = "",
) -> dict[str, Any]:
    record = build_live_execution_packet(
        intent_id=intent_id,
        authorization_id=authorization_id,
        operator=operator,
        note=note,
    )
    rows = load_live_execution_packets()
    rows.append(record)
    save_live_execution_packets(rows)
    return record


def list_live_execution_packets(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    intent_id: str | None = None,
    authorization_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_live_execution_packets()))
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted]
    if operator:
        wanted = _text(operator)
        rows = [row for row in rows if _text(row.get("operator")) == wanted]
    if intent_id:
        wanted = _text(intent_id)
        rows = [row for row in rows if _text(row.get("intent_id")) == wanted]
    if authorization_id:
        wanted = _text(authorization_id)
        rows = [row for row in rows if _text(row.get("authorization_id")) == wanted]
    return rows[: max(0, int(limit))]


def get_live_execution_packet(packet_id: str) -> dict[str, Any] | None:
    wanted = _text(packet_id)
    for row in load_live_execution_packets():
        if _text(row.get("packet_id")) == wanted:
            return row
    return None


def summarize_live_execution_packets(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    all_rows = load_live_execution_packets()
    selected = rows if rows is not None else list(reversed(all_rows))
    statuses = Counter(_text(row.get("status") or "unknown") for row in selected)
    latest = list(reversed(all_rows))[0] if all_rows else {}
    ready = statuses.get("packet_ready_dry_run", 0) + statuses.get("packet_ready_with_warnings", 0)
    blocked = statuses.get("blocked_by_authorization", 0) + statuses.get("blocked_by_preflight", 0) + statuses.get("invalid", 0)
    return {
        "count": len(selected),
        "saved_count": len(all_rows),
        "packet_ready_dry_run": statuses.get("packet_ready_dry_run", 0),
        "packet_ready_with_warnings": statuses.get("packet_ready_with_warnings", 0),
        "blocked_by_authorization": statuses.get("blocked_by_authorization", 0),
        "blocked_by_preflight": statuses.get("blocked_by_preflight", 0),
        "invalid": statuses.get("invalid", 0),
        "ready_total": ready,
        "blocked_total": blocked,
        "by_status": dict(sorted(statuses.items())),
        "total_ready_notional": round(sum(_safe_float(row.get("notional")) for row in selected if row.get("packet_ready_for_future_adapter")), 6),
        "latest_packet_id": latest.get("packet_id", ""),
        "latest_status": latest.get("status", ""),
        "latest_created_at": latest.get("created_at", ""),
        "execution_available": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "autonomous_trading_enabled": False,
        "note": "Live execution packets are unsigned local review/export records only; they do not execute orders.",
    }


def build_live_execution_packet_board(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    intent_id: str | None = None,
    authorization_id: str | None = None,
) -> dict[str, Any]:
    rows = list_live_execution_packets(
        limit=limit,
        status=status,
        market_id=market_id,
        operator=operator,
        intent_id=intent_id,
        authorization_id=authorization_id,
    )
    return {
        "version": "0.5.11-live-execution-packet-v1",
        "mode": "live_execution_packet_board_v059",
        "generated_at": _now(),
        "summary": summarize_live_execution_packets(rows),
        "items": rows,
        "filters": {
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "intent_id": intent_id or "",
            "authorization_id": authorization_id or "",
        },
        "guardrail": "Live execution packets are unsigned local packaging records only. They never sign, submit, cancel, automate, touch wallets, or override preflight/risk/audit controls.",
    }


def live_execution_packets_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "packet_id",
        "created_at",
        "operator",
        "status",
        "intent_id",
        "authorization_id",
        "authorization_status_snapshot",
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
        "packet_ready_for_future_adapter",
        "execution_allowed",
        "signed_payload_present",
        "exchange_acknowledgement",
        "blocker_count",
        "warning_count",
        "blockers",
        "warnings",
        "authorization_hash",
        "packet_hash",
        "note",
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


def live_execution_packet_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_live_execution_packet_board(limit=25)
    summary = board.get("summary", {}) if isinstance(board, dict) else {}
    alerts: list[dict[str, Any]] = []
    blocked = _safe_int(summary.get("blocked_total"))
    ready = _safe_int(summary.get("ready_total"))
    if blocked:
        alerts.append({
            "timestamp": _now(),
            "level": "warning",
            "kind": "live_execution_packet_blocked",
            "title": "Live execution packets are blocked",
            "detail": f"{blocked} unsigned live execution packet(s) are blocked by authorization, preflight, or invalid inputs.",
            "market_id": None,
            "question": None,
            "source": "live_execution_packet_v059",
            "link": "/live-execution-packets",
            "data": {"blocked": blocked},
        })
    if ready:
        alerts.append({
            "timestamp": _now(),
            "level": "info",
            "kind": "live_execution_packet_ready",
            "title": "Unsigned live execution packets are ready for review",
            "detail": f"{ready} unsigned packet(s) are ready for offline/future-adapter review; execution remains disabled.",
            "market_id": None,
            "question": None,
            "source": "live_execution_packet_v059",
            "link": "/live-execution-packets",
            "data": {"ready": ready},
        })
    return alerts[:10]
