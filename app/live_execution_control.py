from __future__ import annotations

import csv
import hashlib
import hmac
import importlib.util
import io
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR, settings
from .live_adapter import ADAPTER_REQUEST_READY_STATUSES, build_live_adapter_readiness, get_live_adapter_request, list_live_adapter_requests
from .live_dry_run_adapter import DRY_RUN_READY_STATUSES, get_live_dry_run_receipt
from .live_execution_packets import PACKET_READY_STATUSES, get_live_execution_packet
from .live_order_authorizations import get_live_order_authorization
from .live_clob_adapter import FailClosedPolymarketClobAdapter, build_clob_adapter_status

LIVE_EXECUTION_ATTEMPTS_PATH = DATA_DIR / "live" / "live_execution_attempts.json"

SUBMIT_ATTEMPT_STATUSES = {
    "not_ready",
    "blocked_by_kill_switch",
    "blocked_by_submit_disabled",
    "blocked_by_missing_authorization",
    "blocked_by_stale_authorization",
    "blocked_by_missing_adapter_request",
    "blocked_by_invalid_adapter_request",
    "blocked_by_missing_dry_run",
    "blocked_by_stale_dry_run",
    "blocked_by_preflight",
    "blocked_by_risk",
    "blocked_by_manual_confirmation",
    "ready_for_manual_submit",
    "manual_submit_disabled_safe_default",
    "fake_adapter_validated",
    "submitted_fake_adapter_only",
    "live_submit_unimplemented",
    "submit_blocked",
    "submit_ready",
    "submit_attempted",
    "submit_succeeded",
    "submit_failed",
}

CANCEL_ATTEMPT_STATUSES = {
    "not_ready",
    "blocked_by_kill_switch",
    "blocked_by_cancel_disabled",
    "blocked_by_manual_confirmation",
    "fake_adapter_validated",
    "cancelled_fake_adapter_only",
    "live_cancel_unimplemented",
    "cancel_blocked",
    "cancel_attempted",
    "cancel_succeeded",
    "cancel_failed",
}

VALID_ADAPTER_MODES = {"blocked", "fake_local", "real_live"}
SENSITIVE_ENV_KEYS = {
    "POLY_PRIVATE_KEY",
    "POLYMARKET_PRIVATE_KEY",
    "POLY_API_KEY",
    "POLYMARKET_CLOB_API_KEY",
    "CLOB_API_KEY",
    "POLY_SECRET",
    "POLYMARKET_CLOB_SECRET",
    "CLOB_SECRET",
    "POLY_PASSPHRASE",
    "POLYMARKET_CLOB_PASSPHRASE",
    "CLOB_PASSPHRASE",
}


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


def _bool_env(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(key: str, default: int) -> int:
    try:
        return int(float(os.getenv(key, str(default)) or default))
    except (TypeError, ValueError):
        return default


def _float_env(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _list_env(key: str) -> list[str]:
    return [item.strip() for item in os.getenv(key, "").split(",") if item.strip()]


def _csv_join(values: list[Any]) -> str:
    return " | ".join(str(item) for item in values if str(item))


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _rounded(value: Any) -> float:
    return round(_safe_float(value), 6)


def _stable_hash(material: dict[str, Any]) -> str:
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hash_secret(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _secret_values() -> list[str]:
    values: list[str] = []
    for key in SENSITIVE_ENV_KEYS:
        raw = os.getenv(key)
        if raw:
            values.append(str(raw))
    return values


def _redact_text(value: Any) -> str:
    text = _text(value)
    for secret in _secret_values():
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def _parse_dt(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_minutes(value: Any, *, now: datetime | None = None) -> float | None:
    parsed = _parse_dt(value)
    if not parsed:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - parsed).total_seconds() / 60)


def _is_stale(value: Any, max_age_minutes: int, *, now: datetime | None = None) -> bool:
    if max_age_minutes <= 0:
        return False
    age = _age_minutes(value, now=now)
    return age is None or age > max_age_minutes


def _dependency_report() -> dict[str, Any]:
    status = build_clob_adapter_status()
    dependency = dict(status.get("dependency") or {})
    return {
        "status": dependency.get("status", "dependency_missing"),
        "preferred_future_sdk": dependency.get("preferred_future_sdk", "official SDK after local review"),
        "preferred_family": dependency.get("preferred_family", ""),
        "preferred_dependency_present": bool(dependency.get("preferred_dependency_present")),
        "legacy_py_clob_client_present": bool(dependency.get("legacy_dependency_present")),
        "sdk_mapping_completed": bool(status.get("sdk_mapping_completed", False)),
        "submit_available": bool(status.get("real_submit_implemented", False)),
        "cancel_available": bool(status.get("real_cancel_implemented", False)),
        "real_live_smoke_test_guard": status.get("real_live_smoke_test_guard", {}),
        "note": "Real manual submit/cancel are implemented inside app.live_clob_adapter but remain fail-closed unless every explicit live gate passes.",
    }


def _control_config() -> dict[str, Any]:
    phrase = _text(os.getenv("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE", ""))
    allowed = _list_env("POLYMARKET_LIVE_MARKET_ALLOWLIST") or _list_env("LIVE_ALLOWED_MARKET_IDS") or list(settings.live_allowed_market_ids or [])
    dependency = _dependency_report()
    return {
        "kill_switch_active": _bool_env("POLYMARKET_LIVE_KILL_SWITCH", True),
        "submit_enabled": _bool_env("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED", False),
        "cancel_enabled": _bool_env("POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED", False),
        "adapter_submit_requested": _bool_env("POLYMARKET_LIVE_ENABLE_SUBMIT", False),
        "adapter_cancel_requested": _bool_env("POLYMARKET_LIVE_ENABLE_CANCEL", False),
        "fake_adapter_enabled": _bool_env("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED", False),
        "manual_auth_required": _bool_env("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH", _bool_env("LIVE_REQUIRE_MANUAL_APPROVAL", True)),
        "network_mode": _text(os.getenv("POLYMARKET_LIVE_NETWORK_MODE", "offline_default"), "offline_default"),
        "live_mode": _bool_env("POLYMARKET_LIVE_MODE", _bool_env("LIVE_TRADING_ENABLED", False)),
        "allow_real_network": _bool_env("POLYMARKET_LIVE_ALLOW_REAL_NETWORK", False),
        "authorization_max_age_minutes": _int_env("POLYMARKET_LIVE_AUTHORIZATION_MAX_AGE_MINUTES", 60),
        "dry_run_max_age_minutes": _int_env("POLYMARKET_LIVE_DRY_RUN_MAX_AGE_MINUTES", 60),
        "adapter_request_max_age_minutes": _int_env("POLYMARKET_LIVE_ADAPTER_REQUEST_MAX_AGE_MINUTES", 60),
        "final_confirmation_phrase_configured": bool(phrase),
        "final_confirmation_phrase_hash": _hash_secret(phrase),
        "max_order_notional": _float_env("POLYMARKET_LIVE_MAX_ORDER_NOTIONAL", _float_env("LIVE_MAX_ORDER_NOTIONAL", settings.live_max_order_notional)),
        "allowed_market_ids": allowed,
        "allowed_market_count": len(allowed),
        "real_submit_enabled": bool(dependency.get("submit_available")),
        "real_cancel_enabled": bool(dependency.get("cancel_available")),
        "adapter_dependency": dependency,
    }


def _public_order_fields(adapter_request: dict[str, Any] | None) -> dict[str, Any]:
    adapter_request = adapter_request or {}
    preview = adapter_request.get("adapter_request_preview") if isinstance(adapter_request.get("adapter_request_preview"), dict) else {}
    payload = preview.get("payload") if isinstance(preview.get("payload"), dict) else {}
    price = _rounded(payload.get("price") if payload.get("price") not in (None, "") else adapter_request.get("price"))
    size = _rounded(payload.get("size") if payload.get("size") not in (None, "") else adapter_request.get("size"))
    notional = _rounded(adapter_request.get("notional") or (price * size))
    return {
        "market_id": _text(payload.get("market_id") or adapter_request.get("market_id")),
        "token_id": _text(payload.get("asset_id") or adapter_request.get("token_id")),
        "asset_id": _text(payload.get("asset_id") or adapter_request.get("token_id")),
        "outcome": _text(payload.get("outcome") or adapter_request.get("outcome")),
        "side": _text(payload.get("side") or adapter_request.get("side")).upper(),
        "order_type": _text(payload.get("order_type") or adapter_request.get("order_type")).lower(),
        "time_in_force": _text(payload.get("time_in_force") or adapter_request.get("time_in_force")).upper(),
        "price": price,
        "size": size,
        "notional": notional,
    }


def _confirmation_state(final_confirmation: str) -> dict[str, Any]:
    expected = _text(os.getenv("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE", ""))
    provided = _text(final_confirmation)
    return {
        "required": True,
        "configured": bool(expected),
        "present": bool(provided),
        "matches": bool(expected and provided and hmac.compare_digest(provided, expected)),
        "phrase_hash": _hash_secret(provided) if provided else "",
        "guidance": "Enter the exact locally configured POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE for this one manual attempt.",
    }


def _check(step: str, required: bool, passed: bool, detail: str) -> dict[str, Any]:
    return {"step": step, "required": required, "passed": bool(passed), "detail": detail}


def _source_bundle(adapter_request_id: str) -> dict[str, Any]:
    adapter_request = get_live_adapter_request(adapter_request_id)
    packet = get_live_execution_packet(_text(adapter_request.get("packet_id"))) if adapter_request else None
    authorization = get_live_order_authorization(_text(adapter_request.get("authorization_id"))) if adapter_request else None
    dry_run = get_live_dry_run_receipt(_text(adapter_request.get("dry_run_receipt_id"))) if adapter_request else None
    return {
        "adapter_request": adapter_request,
        "packet": packet,
        "authorization": authorization,
        "dry_run": dry_run,
        "readiness": build_live_adapter_readiness(),
    }


def _risk_blockers(order: dict[str, Any], config: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    market_id = _text(order.get("market_id"))
    notional = _decimal(order.get("notional")) or Decimal("0")
    max_order = Decimal(str(config.get("max_order_notional") or 0))
    if max_order <= Decimal("0"):
        blockers.append("LIVE_MAX_ORDER_NOTIONAL is 0/unset; set a deliberate local maximum before manual execution attempts.")
    elif notional > max_order:
        blockers.append(f"order notional {float(notional):.4f} exceeds LIVE_MAX_ORDER_NOTIONAL {float(max_order):.4f}.")
    allowed = list(config.get("allowed_market_ids") or [])
    if not allowed:
        blockers.append("LIVE_ALLOWED_MARKET_IDS is empty; no market is allowlisted for manual execution attempts.")
    elif market_id not in allowed:
        blockers.append("market_id is not present in LIVE_ALLOWED_MARKET_IDS.")
    return blockers


def _submission_status(
    *,
    adapter_mode: str,
    config: dict[str, Any],
    adapter_request: dict[str, Any] | None,
    packet: dict[str, Any] | None,
    authorization: dict[str, Any] | None,
    dry_run: dict[str, Any] | None,
    confirmation: dict[str, Any],
    order: dict[str, Any],
    warnings: list[str],
) -> tuple[str, list[str], list[dict[str, Any]]]:
    blockers: list[str] = []
    checks: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    if adapter_mode not in VALID_ADAPTER_MODES:
        adapter_mode = "blocked"
        blockers.append("adapter_mode must be blocked, fake_local, or real_live.")

    checks.append(_check("manual_only_mode", True, bool(config.get("manual_auth_required")), "POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH must remain true."))
    if not config.get("manual_auth_required"):
        blockers.append("manual-only authorization is disabled; this control plane refuses execution attempts.")

    checks.append(_check("kill_switch_clear", True, not bool(config.get("kill_switch_active")), "POLYMARKET_LIVE_KILL_SWITCH must be false."))
    if config.get("kill_switch_active"):
        blockers.append("POLYMARKET_LIVE_KILL_SWITCH is active.")
        return "blocked_by_kill_switch", blockers, checks

    if adapter_mode == "blocked":
        checks.append(_check("operator_selected_non_submit_mode", True, True, "adapter_mode=blocked records the safe default without submission."))
        return "manual_submit_disabled_safe_default", ["operator selected blocked adapter mode; no submit adapter was invoked."], checks

    checks.append(_check("manual_submit_enabled", True, bool(config.get("submit_enabled")), "POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED must be true."))
    checks.append(_check("adapter_submit_requested", True, bool(config.get("adapter_submit_requested")), "POLYMARKET_LIVE_ENABLE_SUBMIT must be true for adapter request readiness."))
    if not config.get("submit_enabled") or not config.get("adapter_submit_requested"):
        blockers.append("manual submit is disabled by default; set both manual-submit and adapter-submit flags deliberately before retrying.")
        return "blocked_by_submit_disabled", blockers, checks

    checks.append(_check("adapter_request_present", True, bool(adapter_request), "A saved adapter request validation record is required."))
    if not adapter_request:
        blockers.append("saved live adapter request was not found.")
        return "blocked_by_missing_adapter_request", blockers, checks

    request_status = _text(adapter_request.get("status"))
    checks.append(_check("adapter_request_ready", True, request_status in ADAPTER_REQUEST_READY_STATUSES, f"Adapter request status is {request_status or 'missing'}."))
    checks.append(_check("adapter_request_unsigned", True, not bool(adapter_request.get("signed_payload_present")), "Adapter request must not contain signed payload material."))
    checks.append(_check("adapter_request_no_network", True, not bool(adapter_request.get("network_submission_attempted") or adapter_request.get("network_attempted")), "Adapter request validation must not have attempted network submission."))
    if request_status not in ADAPTER_REQUEST_READY_STATUSES:
        blockers.append(f"adapter request status {request_status or 'missing'} is not ready for manual submit.")
    if adapter_request.get("signed_payload_present") or adapter_request.get("network_submission_attempted") or adapter_request.get("network_attempted"):
        blockers.append("adapter request includes forbidden signed/network state.")
    quality_state = _text(adapter_request.get("execution_quality_state"))
    quality_ok = quality_state in {"quality_pass", "quality_pass_with_warnings"}
    checks.append(_check("execution_quality_ready", True, quality_ok or not settings.market_data_require_for_live, f"Execution-quality state is {quality_state or 'missing'}."))
    if settings.market_data_require_for_live and not quality_ok:
        blockers.append("execution-quality simulation is missing or not passing for this adapter request.")

    request_age = _age_minutes(adapter_request.get("created_at"), now=now)
    checks.append(_check("adapter_request_fresh", True, not _is_stale(adapter_request.get("created_at"), _safe_int(config.get("adapter_request_max_age_minutes")), now=now), f"Adapter request age is {round(request_age or 0, 2)} minutes."))
    if _is_stale(adapter_request.get("created_at"), _safe_int(config.get("adapter_request_max_age_minutes")), now=now):
        blockers.append("adapter request is stale.")

    checks.append(_check("execution_packet_present", True, bool(packet), "The source unsigned execution packet must still exist."))
    if not packet:
        blockers.append("source execution packet was not found.")
    else:
        packet_hash_current = _text(packet.get("packet_hash"))
        packet_hash_bound = _text(adapter_request.get("packet_hash"))
        packet_status = _text(packet.get("status"))
        checks.append(_check("execution_packet_ready", True, packet_status in PACKET_READY_STATUSES, f"Packet status is {packet_status or 'missing'}."))
        checks.append(_check("execution_packet_hash_unchanged", True, packet_hash_current == packet_hash_bound, "Adapter request must bind the current execution packet hash."))
        checks.append(_check("preflight_snapshot_ready", True, _text(packet.get("preflight_state_snapshot")) in {"ready_for_operator_authorization", "ready_with_warnings"}, "Packet preflight snapshot must be ready."))
        preflight_age = _age_minutes(packet.get("preflight_generated_at_snapshot"), now=now)
        checks.append(_check("preflight_snapshot_fresh", True, not _is_stale(packet.get("preflight_generated_at_snapshot"), _safe_int(config.get("adapter_request_max_age_minutes")), now=now), f"Preflight snapshot age is {round(preflight_age or 0, 2)} minutes."))
        if packet_status not in PACKET_READY_STATUSES or packet_hash_current != packet_hash_bound:
            blockers.append("source execution packet is stale or no longer ready.")
        if _text(packet.get("preflight_state_snapshot")) not in {"ready_for_operator_authorization", "ready_with_warnings"}:
            blockers.append("source preflight snapshot is not ready.")
        if _is_stale(packet.get("preflight_generated_at_snapshot"), _safe_int(config.get("adapter_request_max_age_minutes")), now=now):
            blockers.append("source preflight snapshot is stale.")

    checks.append(_check("authorization_present", True, bool(authorization), "Latest bound operator authorization is required."))
    if not authorization:
        blockers.append("operator authorization snapshot was not found.")
        if blockers:
            return "blocked_by_missing_authorization", blockers, checks
    else:
        auth_status = _text(authorization.get("status"))
        auth_age = _age_minutes(authorization.get("created_at"), now=now)
        checks.append(_check("authorization_authorized", True, auth_status in {"authorized_dry_run", "authorized_with_warnings"}, f"Authorization status is {auth_status or 'missing'}."))
        checks.append(_check("authorization_acknowledged", True, bool(authorization.get("acknowledgement")), "Authorization acknowledgement is required."))
        checks.append(_check("authorization_hash_bound", True, _text(authorization.get("authorization_hash")) == _text(adapter_request.get("authorization_hash")), "Authorization hash must match adapter request binding."))
        checks.append(_check("authorization_fresh", True, not _is_stale(authorization.get("created_at"), _safe_int(config.get("authorization_max_age_minutes")), now=now), f"Authorization age is {round(auth_age or 0, 2)} minutes."))
        if auth_status not in {"authorized_dry_run", "authorized_with_warnings"} or not authorization.get("acknowledgement"):
            blockers.append("operator authorization is missing acknowledgement or not authorized.")
        if _text(authorization.get("authorization_hash")) != _text(adapter_request.get("authorization_hash")):
            blockers.append("operator authorization hash no longer matches adapter request binding.")
        if _is_stale(authorization.get("created_at"), _safe_int(config.get("authorization_max_age_minutes")), now=now):
            blockers.append("operator authorization is stale.")
            return "blocked_by_stale_authorization", blockers, checks

    checks.append(_check("dry_run_present", True, bool(dry_run), "Latest bound offline dry-run receipt is required."))
    if not dry_run:
        blockers.append("offline dry-run receipt was not found.")
        return "blocked_by_missing_dry_run", blockers, checks
    dry_status = _text(dry_run.get("status"))
    dry_age = _age_minutes(dry_run.get("created_at"), now=now)
    checks.append(_check("dry_run_validated", True, dry_status in DRY_RUN_READY_STATUSES, f"Dry-run receipt status is {dry_status or 'missing'}."))
    checks.append(_check("dry_run_hash_bound", True, _text(dry_run.get("packet_hash")) == _text(adapter_request.get("packet_hash")), "Dry-run packet hash must match adapter request binding."))
    checks.append(_check("dry_run_no_network", True, not bool(dry_run.get("network_attempted")), "Dry-run receipt must be offline/no-network."))
    checks.append(_check("dry_run_fresh", True, not _is_stale(dry_run.get("created_at"), _safe_int(config.get("dry_run_max_age_minutes")), now=now), f"Dry-run receipt age is {round(dry_age or 0, 2)} minutes."))
    if dry_status not in DRY_RUN_READY_STATUSES or _text(dry_run.get("packet_hash")) != _text(adapter_request.get("packet_hash")) or dry_run.get("network_attempted"):
        blockers.append("offline dry-run receipt is not valid for this adapter request.")
    if _is_stale(dry_run.get("created_at"), _safe_int(config.get("dry_run_max_age_minutes")), now=now):
        blockers.append("offline dry-run receipt is stale.")
        return "blocked_by_stale_dry_run", blockers, checks

    risk_blockers = _risk_blockers(order, config)
    checks.append(_check("risk_limits_pass", True, not risk_blockers, "Order notional and market allowlist must pass current local risk limits."))
    if risk_blockers:
        blockers.extend(risk_blockers)
        return "blocked_by_risk", blockers, checks

    checks.append(_check("final_confirmation_configured", True, bool(confirmation.get("configured")), "POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE must be configured locally."))
    checks.append(_check("final_confirmation_matches", True, bool(confirmation.get("matches")), "Operator final confirmation phrase must match exactly for this attempt."))
    if not confirmation.get("configured") or not confirmation.get("matches"):
        blockers.append("final operator confirmation phrase is missing or does not match the configured local phrase.")
        return "blocked_by_manual_confirmation", blockers, checks

    if blockers:
        if any("preflight" in item.lower() for item in blockers):
            return "blocked_by_preflight", blockers, checks
        if any("adapter request" in item.lower() for item in blockers):
            return "blocked_by_invalid_adapter_request", blockers, checks
        return "not_ready", blockers, checks

    if adapter_mode == "fake_local":
        checks.append(_check("fake_adapter_enabled", True, bool(config.get("fake_adapter_enabled")), "POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED must be true for fake-local submit simulation."))
        if not config.get("fake_adapter_enabled"):
            return "blocked_by_submit_disabled", ["fake-local adapter is disabled."], checks
        return "fake_adapter_validated", blockers, checks

    dependency = dict(config.get("adapter_dependency") or {})
    checks.append(_check("live_mode_enabled", True, bool(config.get("live_mode")), "POLYMARKET_LIVE_MODE must be true."))
    checks.append(_check("real_network_allowed", True, bool(config.get("allow_real_network")), "POLYMARKET_LIVE_ALLOW_REAL_NETWORK must be true."))
    checks.append(_check("real_submit_adapter_available", True, bool(config.get("real_submit_enabled")), "Real submit implementation and SDK dependency must be available."))
    if not config.get("live_mode"):
        blockers.append("POLYMARKET_LIVE_MODE is false.")
    if not config.get("allow_real_network"):
        blockers.append("POLYMARKET_LIVE_ALLOW_REAL_NETWORK is false.")
    if not config.get("real_submit_enabled"):
        blockers.append(f"real submit adapter is not available: {dependency.get('status') or 'unknown dependency status'}.")
    if blockers:
        return "submit_blocked", blockers, checks
    return "ready_for_manual_submit", blockers, checks


class FakeLocalExecutionAdapter:
    adapter_mode = "fake_local"

    def validate_client_readonly(self) -> dict[str, Any]:
        return {
            "adapter_mode": self.adapter_mode,
            "dependency_required": False,
            "network_attempted": False,
            "signed_payload_present": False,
            "status": "fake_adapter_validated",
        }

    def prepare_order(self, order: dict[str, Any]) -> dict[str, Any]:
        return {
            "adapter_mode": self.adapter_mode,
            "prepared_order_id": f"fake_prepared_{_stable_hash(order)[:16]}",
            "public_order_fields": order,
            "network_attempted": False,
            "signed_payload_present": False,
        }

    def submit_order(self, *, attempt_id: str, order: dict[str, Any]) -> dict[str, Any]:
        receipt_material = {"attempt_id": attempt_id, "order": order, "adapter_mode": self.adapter_mode, "action": "submit"}
        digest = _stable_hash(receipt_material)
        return {
            "fake_submit_receipt_id": f"fsr_{digest[:16]}",
            "fake_order_id": f"fake_order_{digest[16:32]}",
            "adapter_mode": self.adapter_mode,
            "network_attempted": False,
            "signed_payload_present": False,
            "exchange_acknowledgement_present": False,
            "simulated_status": "accepted_fake_local",
            "simulated_reason": "Fake-local manual submit simulation. No exchange order was placed.",
        }

    def cancel_order(self, *, attempt_id: str, original_attempt: dict[str, Any] | None, fake_order_id: str = "") -> dict[str, Any]:
        receipt_material = {
            "attempt_id": attempt_id,
            "original_attempt_id": (original_attempt or {}).get("attempt_id"),
            "fake_order_id": fake_order_id or (original_attempt or {}).get("fake_order_id"),
            "adapter_mode": self.adapter_mode,
            "action": "cancel",
        }
        digest = _stable_hash(receipt_material)
        return {
            "fake_cancel_receipt_id": f"fcr_{digest[:16]}",
            "fake_order_id": fake_order_id or _text((original_attempt or {}).get("fake_order_id")),
            "adapter_mode": self.adapter_mode,
            "network_attempted": False,
            "signed_payload_present": False,
            "exchange_acknowledgement_present": False,
            "simulated_status": "cancelled_fake_local",
            "simulated_reason": "Fake-local manual cancel simulation. No exchange order was cancelled.",
        }

    def get_order_status(self, fake_order_id: str) -> dict[str, Any]:
        return {
            "fake_order_id": fake_order_id,
            "adapter_mode": self.adapter_mode,
            "network_attempted": False,
            "exchange_acknowledgement_present": False,
            "simulated_status": "fake_local_unknown_or_open",
        }


class RealLiveExecutionAdapter(FailClosedPolymarketClobAdapter):
    """Fail-closed real adapter facade used by the manual control plane.

    v1.0.0 centralizes dependency/credential/gate inspection and an explicit SDK method contract in app.live_clob_adapter.
    It deliberately remains fail-closed until exact current Polymarket SDK submit/cancel mapping is implemented and locally reviewed.
    """


def _attempt_base(
    *,
    action: str,
    attempt_id: str,
    created_at: str,
    operator: str,
    adapter_mode: str,
    final_confirmation: str,
    note: str,
    status: str,
    blockers: list[str],
    warnings: list[str],
    recommended_next_action: str,
    config: dict[str, Any],
    adapter_request: dict[str, Any] | None = None,
    packet: dict[str, Any] | None = None,
    authorization: dict[str, Any] | None = None,
    dry_run: dict[str, Any] | None = None,
    checklist: list[dict[str, Any]] | None = None,
    receipt: dict[str, Any] | None = None,
    cancel_reason: str = "",
    original_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    order = _public_order_fields(adapter_request)
    confirmation = _confirmation_state(final_confirmation)
    receipt = receipt or {}
    original_attempt = original_attempt or {}
    if not order.get("market_id") and isinstance(original_attempt.get("public_order_fields"), dict):
        order = dict(original_attempt.get("public_order_fields") or {})
    attempt = {
        "attempt_id": attempt_id,
        "version": "0.7.0-live-execution-control-v1",
        "mode": "live_execution_control_v070",
        "created_at": created_at,
        "action": action,
        "operator": _text(operator, "local"),
        "intent_id": _text((adapter_request or {}).get("intent_id") or (packet or {}).get("intent_id") or original_attempt.get("intent_id")),
        "packet_id": _text((adapter_request or {}).get("packet_id") or (packet or {}).get("packet_id") or original_attempt.get("packet_id")),
        "adapter_request_id": _text((adapter_request or {}).get("request_id") or original_attempt.get("adapter_request_id")),
        "authorization_id": _text((adapter_request or {}).get("authorization_id") or (authorization or {}).get("authorization_id") or original_attempt.get("authorization_id")),
        "dry_run_receipt_id": _text((adapter_request or {}).get("dry_run_receipt_id") or (dry_run or {}).get("receipt_id") or original_attempt.get("dry_run_receipt_id")),
        "market_id": _text(order.get("market_id") or original_attempt.get("market_id")),
        "token_id": _text(order.get("token_id") or original_attempt.get("token_id")),
        "side": _text(order.get("side") or original_attempt.get("side")),
        "price": _rounded(order.get("price") if order.get("price") not in (None, "") else original_attempt.get("price")),
        "size": _rounded(order.get("size") if order.get("size") not in (None, "") else original_attempt.get("size")),
        "notional": _rounded(order.get("notional") if order.get("notional") not in (None, "") else original_attempt.get("notional")),
        "order_type": _text(order.get("order_type") or original_attempt.get("order_type")),
        "time_in_force": _text(order.get("time_in_force") or original_attempt.get("time_in_force")),
        "final_confirmation_present": bool(confirmation.get("present")),
        "final_confirmation_phrase_hash": confirmation.get("phrase_hash", ""),
        "kill_switch_active": bool(config.get("kill_switch_active")),
        "submit_enabled": bool(config.get("submit_enabled")),
        "cancel_enabled": bool(config.get("cancel_enabled")),
        "manual_auth_required": bool(config.get("manual_auth_required")),
        "network_mode": _text(config.get("network_mode")),
        "adapter_mode": adapter_mode,
        "adapter_dependency": config.get("adapter_dependency", {}),
        "fake_adapter_used": bool(adapter_mode == "fake_local" and status in {"fake_adapter_validated", "submitted_fake_adapter_only", "cancelled_fake_adapter_only"}),
        "real_network_attempted": bool(receipt.get("network_attempted", False)),
        "network_attempted": bool(receipt.get("network_attempted", False)),
        "signed_payload_present": bool(receipt.get("signed_payload_present", False)),
        "exchange_acknowledgement_present": bool(receipt.get("exchange_acknowledgement_present", False)),
        "submission_status": status if action == "submit" else "",
        "cancel_status": status if action == "cancel" else "",
        "status": status,
        "fake_submit_receipt_id": _text(receipt.get("fake_submit_receipt_id")),
        "fake_cancel_receipt_id": _text(receipt.get("fake_cancel_receipt_id")),
        "fake_order_id": _text(receipt.get("fake_order_id") or original_attempt.get("fake_order_id")),
        "exchange_order_id": _text(receipt.get("exchange_order_id") or original_attempt.get("exchange_order_id")),
        "adapter_status": _text(receipt.get("adapter_status") or receipt.get("status") or status),
        "exchange_status": _text(receipt.get("exchange_status")),
        "raw_response_hash": _text(receipt.get("raw_response_hash")),
        "original_attempt_id": _text(original_attempt.get("attempt_id")),
        "cancel_reason": _redact_text(cancel_reason),
        "public_order_fields": order if order.get("market_id") else dict(original_attempt.get("public_order_fields") or {}),
        "checklist": checklist or [],
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "recommended_next_action": recommended_next_action,
        "receipt": receipt,
        "note": _redact_text(note),
        "secret_values_returned": False,
        "guardrail": "Manual live execution control-plane record. Real submit/cancel route through the fail-closed CLOB adapter boundary; fake-local receipts are not exchange orders.",
    }
    attempt["attempt_hash"] = _stable_hash(
        {
            "attempt_id": attempt.get("attempt_id"),
            "created_at": attempt.get("created_at"),
            "action": attempt.get("action"),
            "operator": attempt.get("operator"),
            "adapter_request_id": attempt.get("adapter_request_id"),
            "authorization_id": attempt.get("authorization_id"),
            "dry_run_receipt_id": attempt.get("dry_run_receipt_id"),
            "status": attempt.get("status"),
            "adapter_mode": attempt.get("adapter_mode"),
            "public_order_fields": attempt.get("public_order_fields"),
            "final_confirmation_phrase_hash": attempt.get("final_confirmation_phrase_hash"),
            "blockers": attempt.get("blockers"),
            "warnings": attempt.get("warnings"),
            "fake_submit_receipt_id": attempt.get("fake_submit_receipt_id"),
            "fake_cancel_receipt_id": attempt.get("fake_cancel_receipt_id"),
        }
    )
    return attempt


def _submit_next_action(status: str) -> str:
    if status == "submitted_fake_adapter_only":
        return "Fake-local submit receipt recorded. This is not an exchange order; continue with reconciliation review or fake cancel testing only."
    if status == "fake_adapter_validated":
        return "All manual gates pass for fake-local simulation. Recording an attempt will create a fake receipt only."
    if status == "ready_for_manual_submit":
        return "Manual gates pass. If adapter_mode=real_live is recorded under this configuration, the SDK adapter will be invoked."
    if status == "submit_succeeded":
        return "Real manual submit returned an exchange acknowledgement. Review ledger and reconciliation before any further action."
    if status == "submit_failed":
        return "Real manual submit attempted the SDK and failed. Review redacted error and do not assume exchange execution."
    if status == "submit_blocked":
        return "Real manual submit was blocked before the SDK call."
    if status == "manual_submit_disabled_safe_default":
        return "No submit adapter was invoked. This is the default safe outcome."
    if status == "live_submit_unimplemented":
        return "Legacy status: real live submit did not run; keep the attempt as audit evidence and do not assume exchange execution."
    if status == "blocked_by_kill_switch":
        return "Keep submission blocked while the kill switch is active."
    if status == "blocked_by_submit_disabled":
        return "Leave submit disabled unless deliberately running a fake-local manual boundary test."
    if status == "blocked_by_manual_confirmation":
        return "Re-enter the exact local confirmation phrase after reviewing all source records."
    if "stale" in status:
        return "Regenerate the stale source record before retrying."
    return "Resolve blockers and retry only through the manual control plane."


def build_manual_submit_preview(
    *,
    adapter_request_id: str,
    operator: str = "local",
    final_confirmation: str = "",
    adapter_mode: str = "blocked",
    note: str = "",
) -> dict[str, Any]:
    config = _control_config()
    adapter_mode = _text(adapter_mode or "blocked", "blocked")
    bundle = _source_bundle(adapter_request_id)
    adapter_request = bundle.get("adapter_request")
    packet = bundle.get("packet")
    authorization = bundle.get("authorization")
    dry_run = bundle.get("dry_run")
    readiness = bundle.get("readiness")
    order = _public_order_fields(adapter_request)
    warnings: list[str] = []
    if adapter_request:
        warnings.extend(str(item) for item in list(adapter_request.get("warnings") or [])[:6])
    repeated = [row for row in load_live_execution_attempts() if _text(row.get("adapter_request_id")) == _text((adapter_request or {}).get("request_id")) and _text(row.get("action")) == "submit"]
    if repeated:
        warnings.append(f"{len(repeated)} previous submit attempt(s) exist for this adapter request.")
    confirmation = _confirmation_state(final_confirmation)
    status, blockers, checklist = _submission_status(
        adapter_mode=adapter_mode,
        config=config,
        adapter_request=adapter_request,
        packet=packet,
        authorization=authorization,
        dry_run=dry_run,
        confirmation=confirmation,
        order=order,
        warnings=warnings,
    )
    return {
        "version": "0.7.0-live-manual-submit-preview-v1",
        "mode": "live_manual_submit_preview_v070",
        "generated_at": _now(),
        "recorded": False,
        "operator": _text(operator, "local"),
        "status": status,
        "adapter_mode": adapter_mode,
        "adapter_request_id": _text((adapter_request or {}).get("request_id") or adapter_request_id),
        "packet_id": _text((adapter_request or {}).get("packet_id")),
        "intent_id": _text((adapter_request or {}).get("intent_id")),
        "authorization_id": _text((adapter_request or {}).get("authorization_id")),
        "dry_run_receipt_id": _text((adapter_request or {}).get("dry_run_receipt_id")),
        "public_order_fields": order,
        "final_confirmation": {
            "required": True,
            "configured": confirmation.get("configured"),
            "present": confirmation.get("present"),
            "matches": confirmation.get("matches"),
            "raw_phrase_returned": False,
            "guidance": confirmation.get("guidance"),
        },
        "fake_adapter_available": bool(config.get("fake_adapter_enabled")),
        "real_adapter_available": False,
        "live_submit_disabled": not bool(config.get("submit_enabled")),
        "kill_switch_active": bool(config.get("kill_switch_active")),
        "checklist": checklist,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "source_bindings": {
            "adapter_request_hash": _text((adapter_request or {}).get("request_hash")),
            "packet_hash": _text((adapter_request or {}).get("packet_hash")),
            "authorization_hash": _text((adapter_request or {}).get("authorization_hash")),
            "dry_run_receipt_status": _text((dry_run or {}).get("status")),
            "live_adapter_readiness_status": _text((readiness or {}).get("overall_status")),
        },
        "attempt_history": {
            "previous_submit_attempts": len(repeated),
            "latest_attempt_id": _text(repeated[-1].get("attempt_id")) if repeated else "",
            "replay_warning": bool(repeated),
        },
        "recommended_next_action": _submit_next_action(status),
        "note": _redact_text(note),
        "secret_values_returned": False,
        "guardrail": "Preview only. It does not write state, sign payloads, submit orders, cancel orders, touch wallets, or call the network.",
    }


def record_manual_submit_attempt(
    *,
    adapter_request_id: str,
    operator: str = "local",
    final_confirmation: str = "",
    adapter_mode: str = "blocked",
    note: str = "",
) -> dict[str, Any]:
    config = _control_config()
    adapter_mode = _text(adapter_mode or "blocked", "blocked")
    preview = build_manual_submit_preview(
        adapter_request_id=adapter_request_id,
        operator=operator,
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        note=note,
    )
    bundle = _source_bundle(adapter_request_id)
    attempt_id = f"lex_{uuid4().hex[:12]}"
    status = _text(preview.get("status"))
    receipt: dict[str, Any] = {}
    if status == "fake_adapter_validated" and adapter_mode == "fake_local":
        receipt = FakeLocalExecutionAdapter().submit_order(attempt_id=attempt_id, order=dict(preview.get("public_order_fields") or {}))
        status = "submitted_fake_adapter_only"
    elif adapter_mode == "real_live" and status not in {
        "blocked_by_kill_switch",
        "blocked_by_submit_disabled",
        "blocked_by_missing_authorization",
        "blocked_by_stale_authorization",
        "blocked_by_missing_adapter_request",
        "blocked_by_invalid_adapter_request",
        "blocked_by_missing_dry_run",
        "blocked_by_stale_dry_run",
        "blocked_by_preflight",
        "blocked_by_risk",
        "blocked_by_manual_confirmation",
    }:
        receipt = RealLiveExecutionAdapter().submit_order(attempt_id=attempt_id, order=dict(preview.get("public_order_fields") or {}))
        status = _text(receipt.get("status"), "submit_failed")

    blockers = list(preview.get("blockers") or [])
    warnings = list(preview.get("warnings") or [])
    if receipt.get("simulated_reason"):
        warnings.append(str(receipt.get("simulated_reason")))
    if receipt.get("warnings"):
        warnings.extend(str(item) for item in list(receipt.get("warnings") or []))
    record = _attempt_base(
        action="submit",
        attempt_id=attempt_id,
        created_at=_now(),
        operator=operator,
        adapter_mode=adapter_mode,
        final_confirmation=final_confirmation,
        note=note,
        status=status,
        blockers=blockers,
        warnings=warnings,
        recommended_next_action=_submit_next_action(status),
        config=config,
        adapter_request=bundle.get("adapter_request"),
        packet=bundle.get("packet"),
        authorization=bundle.get("authorization"),
        dry_run=bundle.get("dry_run"),
        checklist=list(preview.get("checklist") or []),
        receipt=receipt,
    )
    rows = load_live_execution_attempts()
    rows.append(record)
    save_live_execution_attempts(rows)
    return record


def _cancel_next_action(status: str) -> str:
    if status == "cancelled_fake_adapter_only":
        return "Fake-local cancel receipt recorded. This did not cancel an exchange order."
    if status == "fake_adapter_validated":
        return "All manual gates pass for fake-local cancel simulation. Recording will create a fake cancel receipt only."
    if status == "live_cancel_unimplemented":
        return "Legacy status: real live cancel did not run; use the record for audit only."
    if status == "cancel_succeeded":
        return "Real manual cancel returned an exchange acknowledgement. Review ledger and reconciliation."
    if status == "cancel_failed":
        return "Real manual cancel attempted the SDK and failed. Review redacted error and do not assume exchange cancellation."
    if status == "cancel_blocked":
        return "Real manual cancel was blocked before the SDK call."
    if status == "blocked_by_cancel_disabled":
        return "Cancel remains disabled by default."
    if status == "blocked_by_manual_confirmation":
        return "Re-enter the exact local confirmation phrase after reviewing the target attempt."
    if status == "blocked_by_kill_switch":
        return "Keep cancellation blocked while the kill switch is active."
    return "Resolve blockers before retrying a manual cancel attempt."


def _find_attempt_for_cancel(original_attempt_id: str = "", fake_order_id: str = "") -> dict[str, Any] | None:
    wanted_attempt = _text(original_attempt_id)
    wanted_order = _text(fake_order_id)
    for row in load_live_execution_attempts():
        if wanted_attempt and _text(row.get("attempt_id")) == wanted_attempt:
            return row
    if wanted_order:
        for row in reversed(load_live_execution_attempts()):
            receipt = row.get("receipt") if isinstance(row.get("receipt"), dict) else {}
            if _text(row.get("fake_order_id")) == wanted_order or _text(row.get("exchange_order_id")) == wanted_order or _text(receipt.get("exchange_order_id")) == wanted_order:
                return row
        return {"attempt_id": "", "adapter_mode": "real_live", "exchange_order_id": wanted_order, "public_order_fields": {}, "status": "operator_supplied_order_id"}
    return None


def _cancel_status(
    *,
    adapter_mode: str,
    config: dict[str, Any],
    original_attempt: dict[str, Any] | None,
    confirmation: dict[str, Any],
    reason: str,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    blockers: list[str] = []
    checks: list[dict[str, Any]] = []
    if adapter_mode not in VALID_ADAPTER_MODES:
        adapter_mode = "blocked"
        blockers.append("adapter_mode must be blocked, fake_local, or real_live.")
    checks.append(_check("kill_switch_clear", True, not bool(config.get("kill_switch_active")), "POLYMARKET_LIVE_KILL_SWITCH must be false."))
    if config.get("kill_switch_active"):
        return "blocked_by_kill_switch", ["POLYMARKET_LIVE_KILL_SWITCH is active."], checks
    checks.append(_check("manual_cancel_enabled", True, bool(config.get("cancel_enabled")), "POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED must be true."))
    checks.append(_check("adapter_cancel_requested", True, bool(config.get("adapter_cancel_requested")), "POLYMARKET_LIVE_ENABLE_CANCEL must be true for cancel scaffolding."))
    if adapter_mode == "blocked" or not config.get("cancel_enabled") or not config.get("adapter_cancel_requested"):
        return "blocked_by_cancel_disabled", ["manual cancel is disabled by default; no cancel adapter was invoked."], checks
    checks.append(_check("target_order_present", True, bool(original_attempt), "An original attempt ID, fake order ID, or exchange order ID is required."))
    if not original_attempt:
        blockers.append("original execution attempt or exchange order id was not found/provided.")
    else:
        checks.append(_check("original_attempt_fake_local", adapter_mode == "fake_local", _text(original_attempt.get("adapter_mode")) == "fake_local", "Fake-local cancel requires a fake-local submit attempt."))
        if adapter_mode == "fake_local" and _text(original_attempt.get("adapter_mode")) != "fake_local":
            blockers.append("fake-local cancel can only target a fake-local submit attempt.")
    checks.append(_check("cancel_reason_present", True, bool(_text(reason)), "A human-readable cancel reason is required."))
    if not _text(reason):
        blockers.append("cancel reason is required.")
    checks.append(_check("final_confirmation_configured", True, bool(confirmation.get("configured")), "POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE must be configured locally."))
    checks.append(_check("final_confirmation_matches", True, bool(confirmation.get("matches")), "Operator final confirmation phrase must match exactly for this cancel attempt."))
    if not confirmation.get("configured") or not confirmation.get("matches"):
        blockers.append("final operator confirmation phrase is missing or does not match the configured local phrase.")
        return "blocked_by_manual_confirmation", blockers, checks
    if blockers:
        return "not_ready", blockers, checks
    if adapter_mode == "fake_local":
        checks.append(_check("fake_adapter_enabled", True, bool(config.get("fake_adapter_enabled")), "POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED must be true for fake-local cancel simulation."))
        if not config.get("fake_adapter_enabled"):
            return "blocked_by_cancel_disabled", ["fake-local adapter is disabled."], checks
        return "fake_adapter_validated", blockers, checks
    dependency = dict(config.get("adapter_dependency") or {})
    checks.append(_check("live_mode_enabled", True, bool(config.get("live_mode")), "POLYMARKET_LIVE_MODE must be true."))
    checks.append(_check("real_network_allowed", True, bool(config.get("allow_real_network")), "POLYMARKET_LIVE_ALLOW_REAL_NETWORK must be true."))
    checks.append(_check("real_cancel_adapter_available", True, bool(config.get("real_cancel_enabled")), "Real cancel implementation and SDK dependency must be available."))
    if not config.get("live_mode"):
        blockers.append("POLYMARKET_LIVE_MODE is false.")
    if not config.get("allow_real_network"):
        blockers.append("POLYMARKET_LIVE_ALLOW_REAL_NETWORK is false.")
    if not config.get("real_cancel_enabled"):
        blockers.append(f"real cancel adapter is not available: {dependency.get('status') or 'unknown dependency status'}.")
    if blockers:
        return "cancel_blocked", blockers, checks
    return "cancel_attempted", blockers, checks


def build_manual_cancel_preview(
    *,
    original_attempt_id: str = "",
    fake_order_id: str = "",
    operator: str = "local",
    final_confirmation: str = "",
    adapter_mode: str = "blocked",
    reason: str = "",
    note: str = "",
) -> dict[str, Any]:
    config = _control_config()
    original_attempt = _find_attempt_for_cancel(original_attempt_id=original_attempt_id, fake_order_id=fake_order_id)
    confirmation = _confirmation_state(final_confirmation)
    status, blockers, checklist = _cancel_status(
        adapter_mode=_text(adapter_mode or "blocked", "blocked"),
        config=config,
        original_attempt=original_attempt,
        confirmation=confirmation,
        reason=reason,
    )
    repeated = [
        row
        for row in load_live_execution_attempts()
        if _text(row.get("action")) == "cancel" and _text(row.get("original_attempt_id")) == _text((original_attempt or {}).get("attempt_id"))
    ]
    warnings: list[str] = []
    if repeated:
        warnings.append(f"{len(repeated)} previous cancel attempt(s) exist for this original attempt.")
    return {
        "version": "0.7.0-live-manual-cancel-preview-v1",
        "mode": "live_manual_cancel_preview_v070",
        "generated_at": _now(),
        "recorded": False,
        "operator": _text(operator, "local"),
        "status": status,
        "adapter_mode": _text(adapter_mode or "blocked", "blocked"),
        "original_attempt_id": _text((original_attempt or {}).get("attempt_id") or original_attempt_id),
        "fake_order_id": _text(fake_order_id or (original_attempt or {}).get("fake_order_id")),
        "cancel_reason_present": bool(_text(reason)),
        "final_confirmation": {
            "required": True,
            "configured": confirmation.get("configured"),
            "present": confirmation.get("present"),
            "matches": confirmation.get("matches"),
            "raw_phrase_returned": False,
            "guidance": confirmation.get("guidance"),
        },
        "checklist": checklist,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "original_attempt": original_attempt or {},
        "recommended_next_action": _cancel_next_action(status),
        "note": _redact_text(note),
        "secret_values_returned": False,
        "guardrail": "Cancel preview only. It does not write state, sign payloads, cancel orders, touch wallets, or call the network.",
    }


def record_manual_cancel_attempt(
    *,
    original_attempt_id: str = "",
    fake_order_id: str = "",
    operator: str = "local",
    final_confirmation: str = "",
    adapter_mode: str = "blocked",
    reason: str = "",
    note: str = "",
) -> dict[str, Any]:
    config = _control_config()
    preview = build_manual_cancel_preview(
        original_attempt_id=original_attempt_id,
        fake_order_id=fake_order_id,
        operator=operator,
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        reason=reason,
        note=note,
    )
    original_attempt = preview.get("original_attempt") if isinstance(preview.get("original_attempt"), dict) else {}
    attempt_id = f"lex_{uuid4().hex[:12]}"
    status = _text(preview.get("status"))
    receipt: dict[str, Any] = {}
    if status == "fake_adapter_validated" and _text(adapter_mode) == "fake_local":
        receipt = FakeLocalExecutionAdapter().cancel_order(attempt_id=attempt_id, original_attempt=original_attempt, fake_order_id=fake_order_id)
        status = "cancelled_fake_adapter_only"
    elif _text(adapter_mode) == "real_live" and status not in {"blocked_by_kill_switch", "blocked_by_cancel_disabled", "blocked_by_manual_confirmation", "not_ready", "cancel_blocked"}:
        receipt = RealLiveExecutionAdapter().cancel_order(attempt_id=attempt_id, original_attempt=original_attempt, fake_order_id=fake_order_id)
        status = _text(receipt.get("status"), "cancel_failed")
    warnings = list(preview.get("warnings") or [])
    if receipt.get("simulated_reason"):
        warnings.append(str(receipt.get("simulated_reason")))
    if receipt.get("warnings"):
        warnings.extend(str(item) for item in list(receipt.get("warnings") or []))
    record = _attempt_base(
        action="cancel",
        attempt_id=attempt_id,
        created_at=_now(),
        operator=operator,
        adapter_mode=_text(adapter_mode or "blocked", "blocked"),
        final_confirmation=final_confirmation,
        note=note,
        status=status,
        blockers=list(preview.get("blockers") or []),
        warnings=warnings,
        recommended_next_action=_cancel_next_action(status),
        config=config,
        checklist=list(preview.get("checklist") or []),
        receipt=receipt,
        cancel_reason=reason,
        original_attempt=original_attempt,
    )
    rows = load_live_execution_attempts()
    rows.append(record)
    save_live_execution_attempts(rows)
    return record


def load_live_execution_attempts() -> list[dict[str, Any]]:
    rows = _read_json(LIVE_EXECUTION_ATTEMPTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_live_execution_attempts(rows: list[dict[str, Any]]) -> None:
    _write_json(LIVE_EXECUTION_ATTEMPTS_PATH, rows)


def list_live_execution_attempts(
    *,
    limit: int = 100,
    status: str | None = None,
    adapter_mode: str | None = None,
    action: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    adapter_request_id: str | None = None,
    packet_id: str | None = None,
    intent_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_live_execution_attempts()))
    filters = {
        "status": status,
        "adapter_mode": adapter_mode,
        "action": action,
        "market_id": market_id,
        "operator": operator,
        "adapter_request_id": adapter_request_id,
        "packet_id": packet_id,
        "intent_id": intent_id,
    }
    for key, value in filters.items():
        if value:
            wanted = _text(value)
            rows = [row for row in rows if _text(row.get(key)) == wanted]
    return rows[: max(0, int(limit))]


def get_live_execution_attempt(attempt_id: str) -> dict[str, Any] | None:
    wanted = _text(attempt_id)
    for row in load_live_execution_attempts():
        if _text(row.get("attempt_id")) == wanted:
            return row
    return None


def summarize_live_execution_attempts(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    all_rows = load_live_execution_attempts()
    selected = rows if rows is not None else list(reversed(all_rows))
    statuses = Counter(_text(row.get("status") or "unknown") for row in selected)
    modes = Counter(_text(row.get("adapter_mode") or "unknown") for row in selected)
    actions = Counter(_text(row.get("action") or "unknown") for row in selected)
    latest = list(reversed(all_rows))[0] if all_rows else {}
    return {
        "count": len(selected),
        "saved_count": len(all_rows),
        "submitted_fake_adapter_only": statuses.get("submitted_fake_adapter_only", 0),
        "cancelled_fake_adapter_only": statuses.get("cancelled_fake_adapter_only", 0),
        "blocked_by_kill_switch": statuses.get("blocked_by_kill_switch", 0),
        "blocked_by_submit_disabled": statuses.get("blocked_by_submit_disabled", 0),
        "blocked_by_cancel_disabled": statuses.get("blocked_by_cancel_disabled", 0),
        "blocked_by_manual_confirmation": statuses.get("blocked_by_manual_confirmation", 0),
        "live_submit_unimplemented": statuses.get("live_submit_unimplemented", 0),
        "live_cancel_unimplemented": statuses.get("live_cancel_unimplemented", 0),
        "fake_adapter_attempts": modes.get("fake_local", 0),
        "real_live_attempts": modes.get("real_live", 0),
        "submit_attempts": actions.get("submit", 0),
        "cancel_attempts": actions.get("cancel", 0),
        "by_status": dict(sorted(statuses.items())),
        "by_adapter_mode": dict(sorted(modes.items())),
        "by_action": dict(sorted(actions.items())),
        "latest_attempt_id": latest.get("attempt_id", ""),
        "latest_status": latest.get("status", ""),
        "latest_created_at": latest.get("created_at", ""),
        "real_network_attempted": any(bool(row.get("real_network_attempted")) for row in selected),
        "signed_payload_present": any(bool(row.get("signed_payload_present")) for row in selected),
        "exchange_acknowledgement_present": any(bool(row.get("exchange_acknowledgement_present")) for row in selected),
        "note": "Execution attempts include blocked and fake-local records. Fake receipts are not exchange orders.",
    }


def build_live_execution_attempt_board(
    *,
    limit: int = 100,
    status: str | None = None,
    adapter_mode: str | None = None,
    action: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    adapter_request_id: str | None = None,
    packet_id: str | None = None,
    intent_id: str | None = None,
) -> dict[str, Any]:
    rows = list_live_execution_attempts(
        limit=limit,
        status=status,
        adapter_mode=adapter_mode,
        action=action,
        market_id=market_id,
        operator=operator,
        adapter_request_id=adapter_request_id,
        packet_id=packet_id,
        intent_id=intent_id,
    )
    candidates = [
        row
        for row in list(reversed(list_live_adapter_requests(limit=1000)))
        if _text(row.get("status")) in ADAPTER_REQUEST_READY_STATUSES or _text(row.get("status")) == "blocked_by_submit_disabled"
    ][:25]
    return {
        "version": "0.7.0-live-execution-control-v1",
        "mode": "live_execution_attempt_board_v070",
        "generated_at": _now(),
        "summary": summarize_live_execution_attempts(rows),
        "items": rows,
        "adapter_request_candidates": candidates,
        "filters": {
            "status": status or "",
            "adapter_mode": adapter_mode or "",
            "action": action or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "adapter_request_id": adapter_request_id or "",
            "packet_id": packet_id or "",
            "intent_id": intent_id or "",
        },
        "guardrail": "Manual execution attempts are local audit records. Fake-local receipts are simulations; real live submit/cancel are gated and autonomous live trading remains blocked.",
    }


def build_live_execution_control_readiness() -> dict[str, Any]:
    config = _control_config()
    adapter_readiness = build_live_adapter_readiness()
    request_rows = list_live_adapter_requests(limit=1000)
    ready_requests = [row for row in request_rows if _text(row.get("status")) in ADAPTER_REQUEST_READY_STATUSES]
    attempts = load_live_execution_attempts()
    blockers: list[str] = []
    warnings: list[str] = []
    if config.get("kill_switch_active"):
        blockers.append("POLYMARKET_LIVE_KILL_SWITCH is active.")
    if not config.get("submit_enabled"):
        warnings.append("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED is false; manual submit is safely disabled.")
    if not config.get("cancel_enabled"):
        warnings.append("POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED is false; manual cancel is safely disabled.")
    if not config.get("fake_adapter_enabled"):
        warnings.append("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED is false; fake-local end-to-end simulation is disabled.")
    if not config.get("final_confirmation_phrase_configured") and (config.get("submit_enabled") or config.get("cancel_enabled") or config.get("fake_adapter_enabled")):
        blockers.append("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE is not configured.")
    elif not config.get("final_confirmation_phrase_configured"):
        warnings.append("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE is not configured; this is safe while submit/cancel/fake paths are disabled.")
    if not config.get("manual_auth_required"):
        blockers.append("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH must remain true.")
    if not ready_requests:
        warnings.append("No adapter_request_ready records are currently available for manual submit preview.")
    quality_blocked_ready = [row for row in ready_requests if _text(row.get("execution_quality_state")) not in {"quality_pass", "quality_pass_with_warnings"}]
    if settings.market_data_require_for_live and quality_blocked_ready:
        blockers.append("At least one ready adapter request is missing a passing execution-quality simulation.")
    if config.get("adapter_dependency", {}).get("status") == "legacy_py_clob_client_present_review_before_use":
        warnings.append("Legacy py_clob_client is present; review current official SDK guidance before any future real adapter work.")

    if config.get("kill_switch_active"):
        status = "blocked_by_kill_switch"
    elif blockers:
        status = "not_ready"
    elif config.get("submit_enabled") and config.get("fake_adapter_enabled") and ready_requests:
        status = "fake_adapter_validated"
    elif config.get("submit_enabled") and ready_requests:
        status = "ready_for_manual_submit"
    else:
        status = "manual_submit_disabled_safe_default"

    return {
        "source": "local_environment_and_ledgers",
        "version": "0.7.0-live-execution-control-v1",
        "mode": "live_execution_control_readiness_v070",
        "generated_at": _now(),
        "overall_status": status,
        "kill_switch_active": bool(config.get("kill_switch_active")),
        "submit_enabled": bool(config.get("submit_enabled")),
        "cancel_enabled": bool(config.get("cancel_enabled")),
        "fake_adapter_enabled": bool(config.get("fake_adapter_enabled")),
        "manual_auth_required": bool(config.get("manual_auth_required")),
        "network_mode": config.get("network_mode"),
        "real_submit_implemented": False,
        "real_cancel_implemented": False,
        "autonomous_execution_enabled": False,
        "final_confirmation_phrase_configured": bool(config.get("final_confirmation_phrase_configured")),
        "final_confirmation_phrase_hash": config.get("final_confirmation_phrase_hash"),
        "authorization_max_age_minutes": config.get("authorization_max_age_minutes"),
        "dry_run_max_age_minutes": config.get("dry_run_max_age_minutes"),
        "adapter_request_max_age_minutes": config.get("adapter_request_max_age_minutes"),
        "max_order_notional": config.get("max_order_notional"),
        "allowed_market_count": config.get("allowed_market_count"),
        "adapter_dependency": config.get("adapter_dependency"),
        "live_adapter_readiness_status": adapter_readiness.get("overall_status"),
        "ready_adapter_request_count": len(ready_requests),
        "ready_adapter_requests_missing_quality": len(quality_blocked_ready),
        "market_data_required_for_live": bool(settings.market_data_require_for_live),
        "attempt_summary": summarize_live_execution_attempts(list(reversed(attempts))[:100]),
        "blockers": blockers,
        "warnings": warnings,
        "recommended_next_action": _submit_next_action(status),
        "secret_values_returned": False,
        "guardrail": "Manual live execution control plane. Real live submit/cancel are gated through the CLOB adapter; fake-local simulation is explicit, audited, and default-off.",
    }


def live_execution_control_readiness_to_csv(report: dict[str, Any] | None = None) -> str:
    report = report or build_live_execution_control_readiness()
    fields = [
        "generated_at",
        "overall_status",
        "kill_switch_active",
        "submit_enabled",
        "cancel_enabled",
        "fake_adapter_enabled",
        "manual_auth_required",
        "network_mode",
        "real_submit_implemented",
        "real_cancel_implemented",
        "final_confirmation_phrase_configured",
        "authorization_max_age_minutes",
        "dry_run_max_age_minutes",
        "adapter_request_max_age_minutes",
        "max_order_notional",
        "allowed_market_count",
        "ready_adapter_request_count",
        "ready_adapter_requests_missing_quality",
        "market_data_required_for_live",
        "blockers",
        "warnings",
        "recommended_next_action",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    row = dict(report)
    row["blockers"] = _csv_join(list(report.get("blockers") or []))
    row["warnings"] = _csv_join(list(report.get("warnings") or []))
    writer.writerow({key: row.get(key, "") for key in fields})
    return output.getvalue()


def live_execution_attempts_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "attempt_id",
        "created_at",
        "action",
        "operator",
        "status",
        "adapter_mode",
        "intent_id",
        "packet_id",
        "adapter_request_id",
        "authorization_id",
        "dry_run_receipt_id",
        "market_id",
        "token_id",
        "side",
        "price",
        "size",
        "notional",
        "order_type",
        "time_in_force",
        "final_confirmation_present",
        "kill_switch_active",
        "submit_enabled",
        "cancel_enabled",
        "manual_auth_required",
        "network_mode",
        "fake_adapter_used",
        "real_network_attempted",
        "signed_payload_present",
        "exchange_acknowledgement_present",
        "fake_submit_receipt_id",
        "fake_cancel_receipt_id",
        "fake_order_id",
        "original_attempt_id",
        "submission_status",
        "cancel_status",
        "blocker_count",
        "warning_count",
        "blockers",
        "warnings",
        "recommended_next_action",
        "attempt_hash",
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


def live_execution_control_alerts(
    readiness: dict[str, Any] | None = None,
    attempt_board: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    readiness = readiness or build_live_execution_control_readiness()
    attempt_board = attempt_board or build_live_execution_attempt_board(limit=25)
    summary = attempt_board.get("summary", {}) if isinstance(attempt_board, dict) else {}
    alerts: list[dict[str, Any]] = []
    if readiness.get("kill_switch_active"):
        alerts.append(_alert("warning", "live_execution_kill_switch", "Live execution kill switch active", "Manual submit and cancel attempts are blocked.", {"status": readiness.get("overall_status")}, "/live-manual-execution"))
    if readiness.get("overall_status") in {"fake_adapter_validated", "ready_for_manual_submit"}:
        alerts.append(_alert("info", "live_manual_submit_ready", "Manual submit boundary has ready inputs", "At least one adapter request can be previewed through the final control plane; fake-local remains the only implemented path.", {"ready_adapter_request_count": readiness.get("ready_adapter_request_count")}, "/live-manual-execution"))
    if not readiness.get("submit_enabled"):
        alerts.append(_alert("info", "live_manual_submit_disabled", "Manual submit disabled", "POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED is false, which is the safe default.", {}, "/live-manual-execution"))
    if not readiness.get("cancel_enabled"):
        alerts.append(_alert("info", "live_manual_cancel_disabled", "Manual cancel disabled", "POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED is false, which is the safe default.", {}, "/live-manual-cancel"))
    if _safe_int(summary.get("submitted_fake_adapter_only")):
        alerts.append(_alert("info", "live_fake_adapter_receipt", "Fake adapter receipt recorded", "A fake-local submit receipt exists. It is not an exchange order.", {"count": summary.get("submitted_fake_adapter_only")}, "/live-execution-attempts"))
    if _safe_int(summary.get("real_live_attempts")):
        alerts.append(_alert("warning", "live_real_attempt_blocked", "Real live attempt was blocked", "Real live submit/cancel is gated; blocked attempts should remain audited as blocked.", {"count": summary.get("real_live_attempts")}, "/live-execution-attempts"))
    latest_status = _text(summary.get("latest_status"))
    if latest_status:
        alerts.append(_alert("info", "live_execution_attempt_created", "Latest execution attempt recorded", f"Latest attempt status: {latest_status}.", {"attempt_id": summary.get("latest_attempt_id")}, "/live-execution-attempts"))
    return alerts[:10]


def _alert(level: str, kind: str, title: str, detail: str, data: dict[str, Any], link: str) -> dict[str, Any]:
    return {
        "timestamp": _now(),
        "level": level,
        "kind": kind,
        "title": title,
        "detail": detail,
        "market_id": None,
        "question": None,
        "source": "live_execution_control_v070",
        "link": link,
        "data": data,
    }
