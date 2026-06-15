from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .live_dry_run_adapter import DRY_RUN_READY_STATUSES, load_live_dry_run_receipts
from .live_execution_packets import PACKET_READY_STATUSES, get_live_execution_packet, list_live_execution_packets

DRY_RUN_REVIEW_STATES = {
    "validated_ready",
    "validated_with_warnings",
    "needs_dry_run_receipt",
    "stale_dry_run_receipt",
    "dry_run_blocked",
    "packet_blocked",
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


def _latest_receipts_by_packet() -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    receipts = load_live_dry_run_receipts()
    latest: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for receipt in receipts:
        packet_id = _text(receipt.get("packet_id"))
        if packet_id:
            counts[packet_id] += 1
    for receipt in reversed(receipts):
        packet_id = _text(receipt.get("packet_id"))
        if packet_id and packet_id not in latest:
            latest[packet_id] = receipt
    return latest, counts


def _next_action(state: str) -> str:
    if state == "validated_ready":
        return "Latest dry-run receipt is current and clean. Preserve it as offline review evidence only; execution remains unavailable."
    if state == "validated_with_warnings":
        return "Latest dry-run receipt is current with warnings. Review warning text before any future execution-capable build."
    if state == "needs_dry_run_receipt":
        return "Record an offline dry-run adapter receipt for this unsigned packet before any future adapter review."
    if state == "stale_dry_run_receipt":
        return "Record a fresh offline dry-run receipt because the latest receipt no longer matches the current packet snapshot."
    if state == "dry_run_blocked":
        return "Resolve dry-run receipt blockers, keep live guards enabled, and rerun offline validation."
    if state == "packet_blocked":
        return "Resolve packet packaging blockers before recording another dry-run receipt."
    return "Correct saved packet metadata before continuing the dry-run review workflow."


def _review_packet(packet: dict[str, Any], latest_receipt: dict[str, Any] | None, receipt_count: int) -> dict[str, Any]:
    packet_id = _text(packet.get("packet_id"))
    packet_status = _text(packet.get("status") or "unknown")
    blockers: list[str] = []
    warnings: list[str] = []

    if not packet_id:
        blockers.append("saved execution packet is missing packet_id.")
    if packet_status not in PACKET_READY_STATUSES:
        blockers.append(f"packet status {packet_status} is not dry-run reviewable.")
    if not bool(packet.get("packet_ready_for_future_adapter")):
        blockers.append("packet_ready_for_future_adapter is false.")
    if not bool(packet.get("unsigned_only")):
        blockers.append("packet is not marked unsigned_only.")
    if bool(packet.get("signed_payload_present")):
        blockers.append("packet unexpectedly includes signed payload material.")
    if bool(packet.get("exchange_acknowledgement")) or _text(packet.get("exchange_order_id")):
        blockers.append("packet unexpectedly includes exchange acknowledgement/order id data.")
    if bool(packet.get("execution_allowed")) or bool(packet.get("order_submission_enabled")):
        blockers.append("packet unexpectedly reports execution/submission enabled.")
    if not _text(packet.get("packet_hash")):
        blockers.append("packet_hash is required for dry-run review.")

    if blockers:
        state = "packet_blocked" if packet_id else "invalid"
        return _row(packet, latest_receipt, receipt_count, state, blockers, warnings)

    if not latest_receipt:
        return _row(
            packet,
            None,
            receipt_count,
            "needs_dry_run_receipt",
            ["no dry-run adapter receipt has been recorded for this packet."],
            warnings,
        )

    receipt_status = _text(latest_receipt.get("status") or "unknown")
    receipt_blockers = [str(item) for item in list(latest_receipt.get("blockers") or [])]
    receipt_warnings = [str(item) for item in list(latest_receipt.get("warnings") or [])]
    warnings.extend(str(item) for item in list(packet.get("warnings") or [])[:8])
    warnings.extend(receipt_warnings[:8])

    if receipt_status not in DRY_RUN_READY_STATUSES:
        blockers.extend(receipt_blockers or [f"latest receipt status {receipt_status} is not validated."])
        return _row(packet, latest_receipt, receipt_count, "dry_run_blocked", blockers, warnings)
    if bool(latest_receipt.get("network_attempted")):
        blockers.append("latest receipt unexpectedly reports network_attempted=true.")
    if bool(latest_receipt.get("execution_allowed")) or bool(latest_receipt.get("order_submission_enabled")):
        blockers.append("latest receipt unexpectedly reports execution/submission enabled.")
    if bool(latest_receipt.get("order_cancellation_enabled")) or bool(latest_receipt.get("autonomous_trading_enabled")):
        blockers.append("latest receipt unexpectedly reports cancellation/autonomous trading enabled.")
    if bool(latest_receipt.get("signed_payload_present")):
        blockers.append("latest receipt unexpectedly reports signed payload material.")
    if bool(latest_receipt.get("exchange_acknowledgement")) or _text(latest_receipt.get("exchange_order_id")):
        blockers.append("latest receipt unexpectedly reports exchange acknowledgement/order id data.")
    if blockers:
        return _row(packet, latest_receipt, receipt_count, "dry_run_blocked", blockers, warnings)

    stale: list[str] = []
    if _text(latest_receipt.get("packet_hash")) != _text(packet.get("packet_hash")):
        stale.append("latest receipt packet_hash does not match the current packet hash.")
    if _text(latest_receipt.get("authorization_hash")) != _text(packet.get("authorization_hash")):
        stale.append("latest receipt authorization_hash does not match the current packet authorization hash.")
    if _text(latest_receipt.get("packet_status_snapshot")) != packet_status:
        stale.append("latest receipt packet status snapshot does not match the current packet status.")
    if _text(latest_receipt.get("intent_id")) != _text(packet.get("intent_id")):
        stale.append("latest receipt intent_id does not match the current packet.")
    if stale:
        return _row(packet, latest_receipt, receipt_count, "stale_dry_run_receipt", stale, warnings)

    if receipt_status == "dry_run_validated_with_warnings" or warnings or _safe_int(latest_receipt.get("warning_count")):
        return _row(packet, latest_receipt, receipt_count, "validated_with_warnings", blockers, warnings)
    return _row(packet, latest_receipt, receipt_count, "validated_ready", blockers, warnings)


def _row(
    packet: dict[str, Any],
    latest_receipt: dict[str, Any] | None,
    receipt_count: int,
    state: str,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    latest_receipt = latest_receipt or {}
    return {
        "review_id": f"ldr_review_{_text(packet.get('packet_id')) or 'unknown'}",
        "version": "0.5.11-live-dry-run-review-v1",
        "mode": "live_dry_run_review_v0511",
        "generated_at": _now(),
        "state": state,
        "packet_id": _text(packet.get("packet_id")),
        "packet_created_at": _text(packet.get("created_at")),
        "packet_operator": _text(packet.get("operator")),
        "packet_status": _text(packet.get("status") or "unknown"),
        "packet_hash": _text(packet.get("packet_hash")),
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
        "price": round(_safe_float(packet.get("price")), 6),
        "size": round(_safe_float(packet.get("size")), 6),
        "notional": round(_safe_float(packet.get("notional")), 6),
        "latest_receipt_id": _text(latest_receipt.get("receipt_id")),
        "latest_receipt_created_at": _text(latest_receipt.get("created_at")),
        "latest_receipt_operator": _text(latest_receipt.get("operator")),
        "latest_receipt_status": _text(latest_receipt.get("status")),
        "latest_receipt_hash": _text(latest_receipt.get("receipt_hash")),
        "receipt_count": receipt_count,
        "receipt_packet_hash_snapshot": _text(latest_receipt.get("packet_hash")),
        "receipt_authorization_hash_snapshot": _text(latest_receipt.get("authorization_hash")),
        "receipt_packet_status_snapshot": _text(latest_receipt.get("packet_status_snapshot")),
        "dry_run_validated": state in {"validated_ready", "validated_with_warnings"},
        "receipt_current": state in {"validated_ready", "validated_with_warnings"},
        "offline_only": bool(latest_receipt.get("offline_only", True)),
        "network_attempted": bool(latest_receipt.get("network_attempted", False)),
        "execution_allowed": bool(latest_receipt.get("execution_allowed", False)),
        "order_submission_enabled": bool(latest_receipt.get("order_submission_enabled", False)),
        "order_cancellation_enabled": bool(latest_receipt.get("order_cancellation_enabled", False)),
        "autonomous_trading_enabled": bool(latest_receipt.get("autonomous_trading_enabled", False)),
        "signed_payload_present": bool(latest_receipt.get("signed_payload_present", False)),
        "exchange_acknowledgement": bool(latest_receipt.get("exchange_acknowledgement", False)),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "next_required_action": _next_action(state),
        "guardrail": "Read-only live dry-run review. It reconciles saved unsigned packets with offline receipts without signing, submitting, cancelling, touching wallets, sending network requests, or automating trading.",
    }


def review_live_dry_run_packet(packet_id: str) -> dict[str, Any] | None:
    packet = get_live_execution_packet(packet_id)
    if not packet:
        return None
    latest, counts = _latest_receipts_by_packet()
    wanted = _text(packet_id)
    return _review_packet(packet, latest.get(wanted), counts.get(wanted, 0))


def list_live_dry_run_reviews(
    *,
    limit: int = 100,
    state: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    packet_id: str | None = None,
    intent_id: str | None = None,
) -> list[dict[str, Any]]:
    latest, counts = _latest_receipts_by_packet()
    rows = [_review_packet(packet, latest.get(_text(packet.get("packet_id"))), counts.get(_text(packet.get("packet_id")), 0)) for packet in list_live_execution_packets(limit=10000)]
    if state:
        wanted = _text(state)
        rows = [row for row in rows if _text(row.get("state")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted]
    if operator:
        wanted = _text(operator)
        rows = [row for row in rows if _text(row.get("packet_operator")) == wanted or _text(row.get("latest_receipt_operator")) == wanted]
    if packet_id:
        wanted = _text(packet_id)
        rows = [row for row in rows if _text(row.get("packet_id")) == wanted]
    if intent_id:
        wanted = _text(intent_id)
        rows = [row for row in rows if _text(row.get("intent_id")) == wanted]
    return rows[: max(0, int(limit))]


def summarize_live_dry_run_reviews(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    selected = rows if rows is not None else list_live_dry_run_reviews(limit=10000)
    states = Counter(_text(row.get("state") or "unknown") for row in selected)
    action_required = (
        states.get("needs_dry_run_receipt", 0)
        + states.get("stale_dry_run_receipt", 0)
        + states.get("dry_run_blocked", 0)
        + states.get("packet_blocked", 0)
        + states.get("invalid", 0)
    )
    reviewed = states.get("validated_ready", 0) + states.get("validated_with_warnings", 0)
    return {
        "count": len(selected),
        "saved_packet_count": len(list_live_execution_packets(limit=10000)),
        "validated_ready": states.get("validated_ready", 0),
        "validated_with_warnings": states.get("validated_with_warnings", 0),
        "needs_dry_run_receipt": states.get("needs_dry_run_receipt", 0),
        "stale_dry_run_receipt": states.get("stale_dry_run_receipt", 0),
        "dry_run_blocked": states.get("dry_run_blocked", 0),
        "packet_blocked": states.get("packet_blocked", 0),
        "invalid": states.get("invalid", 0),
        "reviewed_total": reviewed,
        "action_required_total": action_required,
        "by_state": dict(sorted(states.items())),
        "total_reviewed_notional": round(sum(_safe_float(row.get("notional")) for row in selected if row.get("dry_run_validated")), 6),
        "execution_available": False,
        "network_available": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "autonomous_trading_enabled": False,
        "note": "Live dry-run review is a derived local reconciliation board only; it never contacts Polymarket or submits orders.",
    }


def build_live_dry_run_review_board(
    *,
    limit: int = 100,
    state: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    packet_id: str | None = None,
    intent_id: str | None = None,
) -> dict[str, Any]:
    rows = list_live_dry_run_reviews(limit=limit, state=state, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    return {
        "version": "0.5.11-live-dry-run-review-v1",
        "mode": "live_dry_run_review_board_v0511",
        "generated_at": _now(),
        "summary": summarize_live_dry_run_reviews(rows),
        "items": rows,
        "filters": {
            "state": state or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "packet_id": packet_id or "",
            "intent_id": intent_id or "",
        },
        "guardrail": "Read-only live dry-run review. It reconciles unsigned execution packets and offline dry-run receipts without signing, submitting, cancelling, touching wallets, sending network requests, or automating trading.",
    }


def live_dry_run_reviews_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "review_id",
        "generated_at",
        "state",
        "packet_id",
        "packet_status",
        "packet_created_at",
        "packet_operator",
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
        "latest_receipt_id",
        "latest_receipt_status",
        "latest_receipt_created_at",
        "latest_receipt_operator",
        "receipt_count",
        "dry_run_validated",
        "receipt_current",
        "offline_only",
        "network_attempted",
        "execution_allowed",
        "order_submission_enabled",
        "order_cancellation_enabled",
        "autonomous_trading_enabled",
        "signed_payload_present",
        "exchange_acknowledgement",
        "blocker_count",
        "warning_count",
        "blockers",
        "warnings",
        "packet_hash",
        "receipt_packet_hash_snapshot",
        "latest_receipt_hash",
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


def live_dry_run_review_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_live_dry_run_review_board(limit=25)
    summary = board.get("summary", {}) if isinstance(board, dict) else {}
    action_required = _safe_int(summary.get("action_required_total"))
    reviewed = _safe_int(summary.get("reviewed_total"))
    alerts: list[dict[str, Any]] = []
    if action_required:
        alerts.append({
            "timestamp": _now(),
            "level": "warning",
            "kind": "live_dry_run_review_action_required",
            "title": "Live dry-run review needs operator attention",
            "detail": f"{action_required} execution packet(s) need a dry-run receipt refresh, blocker resolution, or packet repair.",
            "market_id": None,
            "question": None,
            "source": "live_dry_run_review_v0511",
            "link": "/live-dry-run-review",
            "data": {"action_required": action_required},
        })
    if reviewed:
        alerts.append({
            "timestamp": _now(),
            "level": "info",
            "kind": "live_dry_run_review_validated",
            "title": "Live dry-run review has current validated receipts",
            "detail": f"{reviewed} execution packet(s) have current offline dry-run receipt review; execution remains disabled.",
            "market_id": None,
            "question": None,
            "source": "live_dry_run_review_v0511",
            "link": "/live-dry-run-review",
            "data": {"reviewed": reviewed},
        })
    return alerts[:10]
