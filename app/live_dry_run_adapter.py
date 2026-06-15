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
from .live_config import build_live_config_readiness
from .live_execution_packets import PACKET_READY_STATUSES, get_live_execution_packet, list_live_execution_packets

DRY_RUN_RECEIPTS_PATH = DATA_DIR / "live" / "live_dry_run_adapter_receipts.json"
DRY_RUN_READY_STATUSES = {"dry_run_validated", "dry_run_validated_with_warnings"}


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


def _live_guard_snapshot() -> dict[str, Any]:
    report = build_live_config_readiness()
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    controls = report.get("controls", {}) if isinstance(report, dict) else {}
    return {
        "readiness_state": summary.get("readiness_state", "unknown"),
        "read_only": bool(summary.get("read_only")),
        "live_trading_enabled": bool(summary.get("live_trading_enabled")),
        "dry_run_only": bool(summary.get("dry_run_only")),
        "manual_approval_required": bool(summary.get("manual_approval_required")),
        "pretrade_checks_enabled": bool(summary.get("pretrade_checks_enabled")),
        "audit_required": bool(summary.get("audit_required")),
        "l2_credentials_ready": bool(summary.get("l2_credentials_ready")),
        "order_execution_available": bool(summary.get("order_execution_available")),
        "execution_adapter_present": bool(controls.get("execution_adapter_present")),
        "order_placement_enabled": bool(controls.get("order_placement_enabled")),
        "order_cancellation_enabled": bool(controls.get("order_cancellation_enabled")),
        "autonomous_trading_enabled": bool(controls.get("autonomous_trading_enabled")),
        "guard_warning_count": _safe_int(summary.get("guard_warning_count")),
        "guard_warnings": list(summary.get("guard_warnings") or [])[:8],
    }


def _adapter_request_preview(packet: dict[str, Any]) -> dict[str, Any]:
    wire = dict(packet.get("wire_order_preview") or {})
    return {
        "adapter": "polymarket_clob_dry_run_v1",
        "network_mode": "offline_no_network",
        "method": "POST",
        "path": "/orders",
        "client_order_id": f"dry_{_text(packet.get('packet_id'))}",
        "payload": {
            "market_id": _text(wire.get("market_id") or packet.get("market_id")),
            "asset_id": _text(wire.get("asset_id") or packet.get("token_id")),
            "outcome": _text(wire.get("outcome") or packet.get("outcome")),
            "side": _text(wire.get("side") or packet.get("side")),
            "order_type": _text(wire.get("order_type") or packet.get("order_type")),
            "time_in_force": _text(wire.get("time_in_force") or packet.get("time_in_force")),
            "price": _rounded(wire.get("price") or packet.get("price")),
            "size": _rounded(wire.get("size") or packet.get("size")),
        },
        "signature_included": False,
        "secret_material_included": False,
        "network_attempted": False,
    }


def _adapter_response_preview(status: str, blockers: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "dry_run_acceptance": status in DRY_RUN_READY_STATUSES,
        "dry_run_status": status,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "simulated_exchange_order_id": "",
        "exchange_acknowledgement": False,
        "network_attempted": False,
        "signature_checked": False,
        "message": "Offline dry-run adapter validation only; no network request, signature, wallet operation, or exchange submission occurred.",
    }


def _derive_status(packet: dict[str, Any] | None, guard: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not packet:
        return "invalid", ["saved live execution packet was not found."], warnings

    packet_status = _text(packet.get("status"))
    if packet_status not in PACKET_READY_STATUSES:
        blockers.append(f"packet status {packet_status or 'unknown'} is not dry-run packageable.")
    if not bool(packet.get("packet_ready_for_future_adapter")):
        blockers.append("packet_ready_for_future_adapter is false.")
    if not bool(packet.get("unsigned_only")):
        blockers.append("packet must remain unsigned_only for this dry-run adapter harness.")
    if bool(packet.get("signed_payload_present")):
        blockers.append("packet unexpectedly contains a signed payload; dry-run harness refuses signed material.")
    if bool(packet.get("exchange_acknowledgement")) or _text(packet.get("exchange_order_id")):
        blockers.append("packet unexpectedly contains exchange acknowledgement/order id data.")
    if bool(packet.get("execution_allowed")) or bool(packet.get("order_submission_enabled")):
        blockers.append("packet unexpectedly reports execution/submission enabled.")
    if not _text(packet.get("packet_hash")):
        blockers.append("packet hash is required before dry-run adapter validation.")

    wire = packet.get("wire_order_preview") or {}
    for key in ["market_id", "asset_id", "side", "order_type", "time_in_force"]:
        if not _text(wire.get(key)):
            blockers.append(f"wire_order_preview.{key} is required.")
    if _safe_float(wire.get("price")) <= 0 or _safe_float(wire.get("price")) >= 1:
        blockers.append("wire_order_preview.price must be greater than 0 and less than 1.")
    if _safe_float(wire.get("size")) <= 0:
        blockers.append("wire_order_preview.size must be greater than 0.")

    if not guard.get("read_only"):
        blockers.append("READ_ONLY must remain true for offline adapter dry-run validation.")
    if not guard.get("dry_run_only"):
        blockers.append("LIVE_DRY_RUN_ONLY must remain true for this harness.")
    if not guard.get("manual_approval_required"):
        blockers.append("LIVE_REQUIRE_MANUAL_APPROVAL must remain true before any future execution path.")
    if not guard.get("pretrade_checks_enabled"):
        blockers.append("LIVE_PRETRADE_CHECKS_ENABLED must remain true before any future execution path.")
    if not guard.get("audit_required"):
        blockers.append("LIVE_AUDIT_REQUIRED must remain true before any future execution path.")
    if guard.get("execution_adapter_present") or guard.get("order_placement_enabled") or guard.get("order_execution_available"):
        blockers.append("live config unexpectedly reports an execution adapter/order placement path; this harness must stay offline.")
    if guard.get("order_cancellation_enabled") or guard.get("autonomous_trading_enabled"):
        blockers.append("cancellation/autonomous controls are unexpectedly enabled.")

    warnings.extend(str(item) for item in list(packet.get("warnings") or [])[:8])
    if guard.get("live_trading_enabled"):
        warnings.append("LIVE_TRADING_ENABLED is true, but this build still performs offline dry-run validation only.")
    if not guard.get("l2_credentials_ready"):
        warnings.append("CLOB L2 credentials are incomplete; safe for offline validation because no network request is attempted.")
    warnings.extend(str(item) for item in list(guard.get("guard_warnings") or [])[:5])

    if blockers:
        if any("READ_ONLY" in item or "LIVE_" in item or "adapter" in item for item in blockers):
            return "blocked_by_guard", blockers, warnings
        return "blocked_by_packet", blockers, warnings
    if warnings or packet_status == "packet_ready_with_warnings":
        return "dry_run_validated_with_warnings", blockers, warnings
    return "dry_run_validated", blockers, warnings


def _receipt_hash(payload: dict[str, Any]) -> str:
    material = {
        "packet_id": payload.get("packet_id"),
        "packet_hash": payload.get("packet_hash"),
        "authorization_id": payload.get("authorization_id"),
        "authorization_hash": payload.get("authorization_hash"),
        "status": payload.get("status"),
        "market_id": payload.get("market_id"),
        "token_id": payload.get("token_id"),
        "side": payload.get("side"),
        "order_type": payload.get("order_type"),
        "time_in_force": payload.get("time_in_force"),
        "price": payload.get("price"),
        "size": payload.get("size"),
        "notional": payload.get("notional"),
        "adapter_request_preview": payload.get("adapter_request_preview"),
        "adapter_response_preview": payload.get("adapter_response_preview"),
    }
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _next_action(status: str) -> str:
    if status == "dry_run_validated":
        return "Dry-run adapter validation is clean. This remains offline evidence for a future execution adapter, not an order."
    if status == "dry_run_validated_with_warnings":
        return "Dry-run adapter validation completed with warnings; review warnings before any future execution-capable build."
    if status == "blocked_by_packet":
        return "Create or fix an unsigned ready execution packet before adapter dry-run validation."
    if status == "blocked_by_guard":
        return "Restore staged live guard settings while keeping read-only/dry-run/manual/audit controls intact."
    return "Correct packet inputs and retry dry-run validation locally."


def build_live_dry_run_receipt(
    *,
    packet_id: str,
    operator: str = "local",
    note: str = "",
    receipt_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    packet = get_live_execution_packet(packet_id)
    guard = _live_guard_snapshot()
    status, blockers, warnings = _derive_status(packet, guard)
    packet = packet or {}
    request_preview = _adapter_request_preview(packet)
    response_preview = _adapter_response_preview(status, blockers, warnings)
    receipt = {
        "receipt_id": receipt_id or f"ldr_{uuid4().hex[:12]}",
        "version": "0.5.11-live-dry-run-adapter-v1",
        "mode": "live_dry_run_adapter_v0510",
        "created_at": created_at or _now(),
        "operator": _text(operator, "local"),
        "status": status,
        "packet_id": _text(packet_id),
        "packet_hash": _text(packet.get("packet_hash")),
        "packet_status_snapshot": _text(packet.get("status") or "missing"),
        "intent_id": _text(packet.get("intent_id")),
        "authorization_id": _text(packet.get("authorization_id")),
        "authorization_hash": _text(packet.get("authorization_hash")),
        "preflight_state_snapshot": _text(packet.get("preflight_state_snapshot")),
        "market_id": _text(packet.get("market_id")),
        "token_id": _text(packet.get("token_id")),
        "outcome": _text(packet.get("outcome")),
        "side": _text(packet.get("side")),
        "order_type": _text(packet.get("order_type")),
        "time_in_force": _text(packet.get("time_in_force")),
        "price": _rounded(packet.get("price")),
        "size": _rounded(packet.get("size")),
        "notional": _rounded(packet.get("notional")),
        "source_ticket_id": _text(packet.get("source_ticket_id")),
        "source_approval_id": _text(packet.get("source_approval_id")),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "adapter_request_preview": request_preview,
        "adapter_response_preview": response_preview,
        "live_guard_snapshot": guard,
        "dry_run_validated": status in DRY_RUN_READY_STATUSES,
        "offline_only": True,
        "network_attempted": False,
        "signed_payload_present": False,
        "secret_values_returned": False,
        "exchange_order_id": "",
        "exchange_acknowledgement": False,
        "execution_allowed": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "autonomous_trading_enabled": False,
        "note": _text(note),
        "next_required_action": _next_action(status),
        "guardrail": "Offline dry-run adapter receipt only. It validates packet shape and guard posture without signing, submitting, cancelling, touching wallets, sending network requests, or automating trading.",
    }
    receipt["receipt_hash"] = _receipt_hash(receipt)
    return receipt


def load_live_dry_run_receipts() -> list[dict[str, Any]]:
    rows = _read_json(DRY_RUN_RECEIPTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_live_dry_run_receipts(rows: list[dict[str, Any]]) -> None:
    _write_json(DRY_RUN_RECEIPTS_PATH, rows)


def record_live_dry_run_receipt(*, packet_id: str, operator: str = "local", note: str = "") -> dict[str, Any]:
    record = build_live_dry_run_receipt(packet_id=packet_id, operator=operator, note=note)
    rows = load_live_dry_run_receipts()
    rows.append(record)
    save_live_dry_run_receipts(rows)
    return record


def list_live_dry_run_receipts(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    packet_id: str | None = None,
    intent_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_live_dry_run_receipts()))
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted]
    if operator:
        wanted = _text(operator)
        rows = [row for row in rows if _text(row.get("operator")) == wanted]
    if packet_id:
        wanted = _text(packet_id)
        rows = [row for row in rows if _text(row.get("packet_id")) == wanted]
    if intent_id:
        wanted = _text(intent_id)
        rows = [row for row in rows if _text(row.get("intent_id")) == wanted]
    return rows[: max(0, int(limit))]


def get_live_dry_run_receipt(receipt_id: str) -> dict[str, Any] | None:
    wanted = _text(receipt_id)
    for row in load_live_dry_run_receipts():
        if _text(row.get("receipt_id")) == wanted:
            return row
    return None


def summarize_live_dry_run_receipts(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    all_rows = load_live_dry_run_receipts()
    selected = rows if rows is not None else list(reversed(all_rows))
    statuses = Counter(_text(row.get("status") or "unknown") for row in selected)
    latest = list(reversed(all_rows))[0] if all_rows else {}
    ready = statuses.get("dry_run_validated", 0) + statuses.get("dry_run_validated_with_warnings", 0)
    blocked = statuses.get("blocked_by_packet", 0) + statuses.get("blocked_by_guard", 0) + statuses.get("invalid", 0)
    return {
        "count": len(selected),
        "saved_count": len(all_rows),
        "dry_run_validated": statuses.get("dry_run_validated", 0),
        "dry_run_validated_with_warnings": statuses.get("dry_run_validated_with_warnings", 0),
        "blocked_by_packet": statuses.get("blocked_by_packet", 0),
        "blocked_by_guard": statuses.get("blocked_by_guard", 0),
        "invalid": statuses.get("invalid", 0),
        "ready_total": ready,
        "blocked_total": blocked,
        "by_status": dict(sorted(statuses.items())),
        "total_dry_run_notional": round(sum(_safe_float(row.get("notional")) for row in selected if row.get("dry_run_validated")), 6),
        "latest_receipt_id": latest.get("receipt_id", ""),
        "latest_status": latest.get("status", ""),
        "latest_created_at": latest.get("created_at", ""),
        "execution_available": False,
        "network_available": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "autonomous_trading_enabled": False,
        "note": "Live dry-run adapter receipts are offline validation records only; they never contact Polymarket or submit orders.",
    }


def build_live_dry_run_board(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    packet_id: str | None = None,
    intent_id: str | None = None,
) -> dict[str, Any]:
    rows = list_live_dry_run_receipts(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    packet_candidates = [row for row in list_live_execution_packets(limit=100) if _text(row.get("status")) in PACKET_READY_STATUSES]
    return {
        "version": "0.5.11-live-dry-run-adapter-v1",
        "mode": "live_dry_run_adapter_board_v0510",
        "generated_at": _now(),
        "summary": summarize_live_dry_run_receipts(rows),
        "items": rows,
        "packet_candidates": packet_candidates[:25],
        "filters": {
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "packet_id": packet_id or "",
            "intent_id": intent_id or "",
        },
        "guardrail": "Offline adapter dry-run only. Receipts validate packet shape and live guard posture without network requests, signatures, wallets, submission, cancellation, or automation.",
    }


def live_dry_run_receipts_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "receipt_id",
        "created_at",
        "operator",
        "status",
        "packet_id",
        "packet_status_snapshot",
        "intent_id",
        "authorization_id",
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
        "dry_run_validated",
        "offline_only",
        "network_attempted",
        "execution_allowed",
        "signed_payload_present",
        "exchange_acknowledgement",
        "blocker_count",
        "warning_count",
        "blockers",
        "warnings",
        "packet_hash",
        "receipt_hash",
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


def live_dry_run_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_live_dry_run_board(limit=25)
    summary = board.get("summary", {}) if isinstance(board, dict) else {}
    alerts: list[dict[str, Any]] = []
    blocked = _safe_int(summary.get("blocked_total"))
    ready = _safe_int(summary.get("ready_total"))
    if blocked:
        alerts.append({
            "timestamp": _now(),
            "level": "warning",
            "kind": "live_dry_run_blocked",
            "title": "Live dry-run adapter receipts are blocked",
            "detail": f"{blocked} dry-run receipt(s) are blocked by packet or guard checks.",
            "market_id": None,
            "question": None,
            "source": "live_dry_run_adapter_v0510",
            "link": "/live-dry-run-adapter",
            "data": {"blocked": blocked},
        })
    if ready:
        alerts.append({
            "timestamp": _now(),
            "level": "info",
            "kind": "live_dry_run_validated",
            "title": "Live dry-run adapter receipts are validated",
            "detail": f"{ready} offline dry-run receipt(s) validated packet shape; no network or order action occurred.",
            "market_id": None,
            "question": None,
            "source": "live_dry_run_adapter_v0510",
            "link": "/live-dry-run-adapter",
            "data": {"ready": ready},
        })
    return alerts[:10]
