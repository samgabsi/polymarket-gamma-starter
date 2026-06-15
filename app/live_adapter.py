from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import os
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from .config import DATA_DIR, settings
from .live_dry_run_adapter import DRY_RUN_READY_STATUSES, load_live_dry_run_receipts
from .live_execution_packets import PACKET_READY_STATUSES, get_live_execution_packet, list_live_execution_packets
from .live_order_authorizations import get_live_order_authorization
from .market_data import build_execution_quality_simulation, latest_market_snapshot

LIVE_ADAPTER_VALIDATIONS_PATH = DATA_DIR / "live" / "live_adapter_readonly_validations.json"
LIVE_ADAPTER_REQUESTS_PATH = DATA_DIR / "live" / "live_adapter_requests.json"
MANUAL_EXECUTION_REVIEWS_PATH = DATA_DIR / "live" / "manual_execution_reviews.json"

ADAPTER_REQUEST_READY_STATUSES = {"adapter_request_ready", "adapter_request_ready_with_warnings"}
MANUAL_REVIEW_READY_STATUSES = {"manual_execution_review_ready", "manual_execution_review_ready_with_warnings", "operator_final_confirmation_required"}
VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"limit", "marketable_limit"}
VALID_TIME_IN_FORCE = {"GTC", "FOK", "FAK"}

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


def _present(value: Any) -> bool:
    if value is None:
        return False
    stripped = str(value).strip()
    return bool(stripped and not stripped.startswith("CHANGE_ME") and stripped not in {"<redacted>", "***"})


def _env_first(*keys: str, default: str = "") -> tuple[str, str]:
    for key in keys:
        value = os.getenv(key)
        if _present(value):
            return str(value).strip(), key
    return default, ""


def _bool_env(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _bool_env_any(keys: list[str], default: bool = False) -> bool:
    for key in keys:
        raw = os.getenv(key)
        if raw is not None:
            return raw.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _float_env(key: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(key, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _int_env(key: str, default: int = 0) -> int:
    try:
        return int(float(os.getenv(key, str(default)) or default))
    except (TypeError, ValueError):
        return default


def _list_env(key: str) -> list[str]:
    return [item.strip() for item in os.getenv(key, "").split(",") if item.strip()]


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


def _csv_join(values: list[Any]) -> str:
    return " | ".join(str(item) for item in values if str(item))


def _mask(value: str | None) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if len(stripped) <= 8:
        return "***"
    return f"{stripped[:4]}...{stripped[-4:]}"


def _secret_values() -> list[str]:
    values: list[str] = []
    for key in SENSITIVE_ENV_KEYS:
        raw = os.getenv(key)
        if _present(raw):
            values.append(str(raw))
    return values


def _redact_text(value: Any) -> str:
    text = _text(value)
    for secret in _secret_values():
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def _stable_hash(material: dict[str, Any]) -> str:
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dependency_present() -> bool:
    return importlib.util.find_spec("py_clob_client") is not None


def _host() -> str:
    value, _ = _env_first("POLYMARKET_CLOB_HOST", "CLOB_BASE_URL", default=settings.clob_base_url)
    return value.rstrip("/")


def _credential_summary() -> dict[str, Any]:
    wallet, wallet_key = _env_first("POLY_ADDRESS", "POLYMARKET_WALLET_ADDRESS")
    funder, funder_key = _env_first("POLYMARKET_FUNDER_ADDRESS")
    api_key, api_key_source = _env_first("POLY_API_KEY", "POLYMARKET_CLOB_API_KEY", "CLOB_API_KEY")
    secret, secret_source = _env_first("POLY_SECRET", "POLYMARKET_CLOB_SECRET", "CLOB_SECRET")
    passphrase, passphrase_source = _env_first("POLY_PASSPHRASE", "POLYMARKET_CLOB_PASSPHRASE", "CLOB_PASSPHRASE")
    private_key, private_key_source = _env_first("POLY_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY")
    l2_ready = all(_present(value) for value in [wallet, api_key, secret, passphrase])
    return {
        "wallet_address_present": _present(wallet),
        "wallet_address_source": wallet_key,
        "wallet_address_redacted": _mask(wallet),
        "funder_address_present": _present(funder),
        "funder_address_source": funder_key,
        "funder_address_redacted": _mask(funder),
        "api_key_present": _present(api_key),
        "api_key_source": api_key_source,
        "secret_present": _present(secret),
        "secret_source": secret_source,
        "passphrase_present": _present(passphrase),
        "passphrase_source": passphrase_source,
        "private_key_present": _present(private_key),
        "private_key_source": private_key_source,
        "l2_credentials_present": l2_ready,
        "signing_key_present": _present(private_key),
        "secret_values_returned": False,
    }


def _adapter_config() -> dict[str, Any]:
    credential_summary = _credential_summary()
    signature_type, signature_type_source = _env_first("POLYMARKET_SIGNATURE_TYPE", default="")
    host_value, host_source = _env_first("POLYMARKET_CLOB_HOST", "CLOB_BASE_URL", default=settings.clob_base_url)
    return {
        "host": host_value.rstrip("/"),
        "host_source": host_source or "default",
        "chain_id": os.getenv("POLYMARKET_CHAIN_ID", settings.polymarket_chain_id),
        "signature_type": signature_type,
        "signature_type_source": signature_type_source,
        "live_mode_enabled": _bool_env_any(["POLYMARKET_LIVE_MODE", "LIVE_TRADING_ENABLED"], False),
        "readonly_network_enabled": _bool_env("POLYMARKET_LIVE_NETWORK_READONLY", False),
        "submit_requested": _bool_env("POLYMARKET_LIVE_ENABLE_SUBMIT", False),
        "cancel_requested": _bool_env("POLYMARKET_LIVE_ENABLE_CANCEL", False),
        "manual_auth_required": _bool_env("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH", _bool_env("LIVE_REQUIRE_MANUAL_APPROVAL", True)),
        "legacy_manual_approval_required": _bool_env("LIVE_REQUIRE_MANUAL_APPROVAL", True),
        "kill_switch_active": _bool_env("POLYMARKET_LIVE_KILL_SWITCH", False),
        "dry_run_receipt_required": _bool_env("POLYMARKET_LIVE_REQUIRE_DRY_RUN_RECEIPT", True),
        "readonly_timeout_seconds": _float_env("POLYMARKET_LIVE_READONLY_TIMEOUT_SECONDS", 4.0),
        "max_order_notional": _float_env("LIVE_MAX_ORDER_NOTIONAL", settings.live_max_order_notional),
        "allowed_market_ids": _list_env("LIVE_ALLOWED_MARKET_IDS") or list(settings.live_allowed_market_ids or []),
        "dependency_present": _dependency_present(),
        "credentials": credential_summary,
    }


def _allowed_operations(config: dict[str, Any]) -> list[str]:
    operations = [
        "adapter_readiness_report",
        "readonly_validation_preview",
        "adapter_request_preview",
        "adapter_request_validation",
        "manual_execution_review",
        "csv_export",
    ]
    if config.get("readonly_network_enabled") and config.get("dependency_present"):
        operations.append("explicit_readonly_network_validation")
    return operations


def _blocked_operations(config: dict[str, Any]) -> list[str]:
    blocked = [
        "order_submission",
        "order_cancellation",
        "autonomous_execution",
        "payload_signing",
        "wallet_mutation",
    ]
    if not config.get("readonly_network_enabled"):
        blocked.append("readonly_network_validation")
    if config.get("kill_switch_active"):
        blocked.extend(["manual_execution_review_ready_state", "future_live_submission"])
    return sorted(set(blocked))


def _readiness_status(config: dict[str, Any], latest_validation: dict[str, Any] | None) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    credentials = config.get("credentials", {})

    if config.get("kill_switch_active"):
        blockers.append("POLYMARKET_LIVE_KILL_SWITCH is active; adapter request and manual execution review must remain blocked.")
    if config.get("submit_requested") and not config.get("manual_auth_required"):
        blockers.append("POLYMARKET_LIVE_ENABLE_SUBMIT is true while POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH is false.")
    if config.get("cancel_requested"):
        warnings.append("POLYMARKET_LIVE_ENABLE_CANCEL is true, but this release has no cancellation implementation.")
    if config.get("submit_requested"):
        warnings.append("POLYMARKET_LIVE_ENABLE_SUBMIT is true, but this release still does not submit orders.")
    if config.get("readonly_network_enabled") and not config.get("dependency_present"):
        blockers.append("py_clob_client dependency is missing; authenticated read-only validation cannot run.")
    if config.get("readonly_network_enabled") and not credentials.get("l2_credentials_present"):
        blockers.append("Read-only network validation was enabled, but CLOB L2 credential presence is incomplete.")
    if config.get("live_mode_enabled") and not credentials.get("l2_credentials_present"):
        blockers.append("Live mode is configured, but CLOB L2 credential presence is incomplete.")
    if credentials.get("l2_credentials_present") and not latest_validation:
        warnings.append("CLOB credential presence is detected, but no local read-only validation receipt has been recorded.")
    if latest_validation and latest_validation.get("status") == "readonly_validation_failed":
        blockers.append("The latest read-only validation receipt failed; review the recorded error before proceeding.")
    if latest_validation and latest_validation.get("status") == "readonly_ready":
        warnings.append("Latest read-only validation receipt is ready; order submission remains disabled in this release.")

    if blockers and config.get("kill_switch_active"):
        return "blocked_by_kill_switch", blockers, warnings
    if blockers and any("dependency" in item.lower() for item in blockers):
        return "dependency_missing", blockers, warnings
    if blockers and any("read-only network validation" in item.lower() or "credential" in item.lower() for item in blockers):
        return "config_incomplete", blockers, warnings
    if blockers:
        return "unsafe_submit_config", blockers, warnings
    if latest_validation and latest_validation.get("status") == "readonly_ready":
        return "readonly_ready", blockers, warnings
    if config.get("submit_requested") and config.get("manual_auth_required"):
        return "manual_execution_configured_but_disabled", blockers, warnings
    if credentials.get("l2_credentials_present") or config.get("live_mode_enabled"):
        return "ready_for_manual_execution_review", blockers, warnings
    return "offline_safe_default", blockers, warnings


def latest_live_adapter_readonly_validation() -> dict[str, Any] | None:
    rows = load_live_adapter_readonly_validations()
    return rows[-1] if rows else None


def build_live_adapter_readiness() -> dict[str, Any]:
    config = _adapter_config()
    latest_validation = latest_live_adapter_readonly_validation()
    status, blockers, warnings = _readiness_status(config, latest_validation)
    return {
        "source": "local_environment",
        "version": "0.6.0-live-adapter-readiness-v1",
        "mode": "live_adapter_readiness_v060",
        "generated_at": _now(),
        "overall_status": status,
        "configured_host": config.get("host"),
        "configured_chain_id": config.get("chain_id"),
        "signature_type_configured": bool(config.get("signature_type")),
        "credential_presence": config.get("credentials", {}),
        "read_only_network_validation_enabled": bool(config.get("readonly_network_enabled")),
        "read_only_validation_attempted": False,
        "network_attempted": False,
        "dependency_present": bool(config.get("dependency_present")),
        "live_mode_enabled": bool(config.get("live_mode_enabled")),
        "order_submission_requested": bool(config.get("submit_requested")),
        "order_submission_enabled": False,
        "order_submission_available": False,
        "order_cancellation_requested": bool(config.get("cancel_requested")),
        "order_cancellation_enabled": False,
        "order_cancellation_available": False,
        "autonomous_execution_enabled": False,
        "manual_auth_required": bool(config.get("manual_auth_required")),
        "kill_switch_active": bool(config.get("kill_switch_active")),
        "dry_run_receipt_required": bool(config.get("dry_run_receipt_required")),
        "max_order_notional": config.get("max_order_notional"),
        "allowed_market_count": len(config.get("allowed_market_ids") or []),
        "allowed_operations": _allowed_operations(config),
        "blocked_operations": _blocked_operations(config),
        "blockers": blockers,
        "warnings": warnings,
        "latest_readonly_validation": _compact_validation(latest_validation),
        "recommended_next_action": _readiness_next_action(status),
        "secret_values_returned": False,
        "guardrail": "Live adapter readiness is a redacted local capability report. This release never signs, submits, cancels, touches wallets, or automates trading.",
    }


def _readiness_next_action(status: str) -> str:
    if status == "offline_safe_default":
        return "Continue staged setup locally; enable read-only validation only when credentials and dependency are deliberately configured."
    if status == "config_incomplete":
        return "Complete redacted local configuration or disable read-only network validation until credentials are ready."
    if status == "dependency_missing":
        return "Install and review the Polymarket CLOB client dependency before attempting authenticated read-only validation."
    if status == "readonly_ready":
        return "Review adapter requests and manual execution boundary records; live submission remains disabled."
    if status == "blocked_by_kill_switch":
        return "Keep all adapter requests blocked until the operator deliberately clears the live kill switch."
    if status == "unsafe_submit_config":
        return "Restore manual authorization and default-off submit/cancel settings before proceeding."
    if status == "manual_execution_configured_but_disabled":
        return "Submission was requested in config, but this release still provides only manual review scaffolding."
    if status == "ready_for_manual_execution_review":
        return "Record read-only validation and adapter request previews before any future manual submission implementation."
    return "Review blockers and keep execution disabled."


def _compact_validation(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "validation_id": row.get("validation_id"),
        "created_at": row.get("created_at"),
        "status": row.get("status"),
        "network_attempted": bool(row.get("network_attempted")),
        "dependency_present": bool(row.get("dependency_present")),
        "validation_hash": row.get("validation_hash"),
    }


def _build_readonly_validation(*, operator: str = "local", note: str = "", validation_id: str | None = None, created_at: str | None = None) -> dict[str, Any]:
    config = _adapter_config()
    warnings: list[str] = []
    blockers: list[str] = []
    network_attempted = False
    client_constructed = False
    dependency_present = bool(config.get("dependency_present"))
    validation_error = ""
    status = "readonly_validation_disabled"

    credentials = config.get("credentials", {})
    if config.get("kill_switch_active"):
        blockers.append("POLYMARKET_LIVE_KILL_SWITCH is active; no read-only network validation was attempted.")
        status = "blocked_by_kill_switch"
    elif not config.get("readonly_network_enabled"):
        warnings.append("POLYMARKET_LIVE_NETWORK_READONLY is false; no network validation was attempted.")
    elif not dependency_present:
        blockers.append("py_clob_client dependency is missing; no network validation was attempted.")
        status = "dependency_missing"
    elif not credentials.get("l2_credentials_present"):
        blockers.append("CLOB L2 credential presence is incomplete; no authenticated read-only validation was attempted.")
        status = "config_incomplete"
    else:
        try:
            import py_clob_client.client as py_clob_client  # type: ignore[import-not-found]

            client_cls = getattr(py_clob_client, "ClobClient", None)
            if client_cls is not None:
                client_cls(host=config.get("host"), chain_id=int(str(config.get("chain_id") or "137")))
                client_constructed = True
            else:
                warnings.append("py_clob_client imported, but ClobClient was not found for construction validation.")
        except Exception as exc:  # noqa: BLE001 - redacted diagnostic only
            validation_error = _redact_text(exc)
            blockers.append("CLOB client construction failed; no order or cancellation action was attempted.")
            status = "readonly_validation_failed"

        if status != "readonly_validation_failed":
            try:
                network_attempted = True
                timeout = max(1.0, min(_safe_float(config.get("readonly_timeout_seconds"), 4.0), 15.0))
                response = httpx.get(f"{config.get('host')}/", timeout=timeout, headers={"User-Agent": "polymarket-gamma-starter/0.6.0-readonly-validation"})
                if response.status_code < 500:
                    status = "readonly_ready"
                    warnings.append(f"Read-only host reachability returned HTTP {response.status_code}; no order endpoint was called.")
                else:
                    status = "readonly_validation_failed"
                    blockers.append(f"Read-only host reachability returned HTTP {response.status_code}.")
            except Exception as exc:  # noqa: BLE001 - redacted diagnostic only
                validation_error = _redact_text(exc)
                status = "readonly_validation_failed"
                blockers.append("Read-only host reachability failed within the configured timeout.")

    payload = {
        "validation_id": validation_id or f"lav_{uuid4().hex[:12]}",
        "version": "0.6.0-live-adapter-readonly-validation-v1",
        "mode": "live_adapter_readonly_validation_v060",
        "created_at": created_at or _now(),
        "operator": _text(operator, "local"),
        "status": status,
        "configured_host": config.get("host"),
        "configured_chain_id": config.get("chain_id"),
        "dependency_present": dependency_present,
        "client_construction_attempted": bool(config.get("readonly_network_enabled") and dependency_present and credentials.get("l2_credentials_present")),
        "client_constructed": client_constructed,
        "read_only_network_validation_enabled": bool(config.get("readonly_network_enabled")),
        "read_only_validation_attempted": bool(config.get("readonly_network_enabled")),
        "network_attempted": network_attempted,
        "order_submission_attempted": False,
        "order_cancellation_attempted": False,
        "payload_signing_attempted": False,
        "wallet_operation_attempted": False,
        "credential_presence": credentials,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "validation_error": validation_error,
        "note": _text(note),
        "secret_values_returned": False,
        "next_required_action": _readonly_validation_next_action(status),
        "guardrail": "Optional read-only validation receipt only. It never submits orders, cancels orders, signs payloads, touches wallets, or returns secret values.",
    }
    payload["validation_hash"] = _stable_hash(
        {
            "validation_id": payload.get("validation_id"),
            "status": payload.get("status"),
            "configured_host": payload.get("configured_host"),
            "configured_chain_id": payload.get("configured_chain_id"),
            "dependency_present": payload.get("dependency_present"),
            "network_attempted": payload.get("network_attempted"),
            "blockers": payload.get("blockers"),
            "warnings": payload.get("warnings"),
        }
    )
    return payload


def _readonly_validation_next_action(status: str) -> str:
    if status == "readonly_ready":
        return "Read-only adapter validation is recorded. Continue with adapter request review; submission remains disabled."
    if status == "readonly_validation_disabled":
        return "Set POLYMARKET_LIVE_NETWORK_READONLY=true only when you deliberately want a read-only validation attempt."
    if status == "dependency_missing":
        return "Install py_clob_client only after reviewing dependency and credential handling."
    if status == "config_incomplete":
        return "Complete local CLOB L2 credential fields or keep validation disabled."
    if status == "blocked_by_kill_switch":
        return "Leave validation blocked until the kill switch is deliberately cleared."
    return "Review redacted validation blockers; no execution was attempted."


def preview_live_adapter_readonly_validation(*, operator: str = "local", note: str = "") -> dict[str, Any]:
    return _build_readonly_validation(operator=operator, note=note)


def load_live_adapter_readonly_validations() -> list[dict[str, Any]]:
    rows = _read_json(LIVE_ADAPTER_VALIDATIONS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_live_adapter_readonly_validations(rows: list[dict[str, Any]]) -> None:
    _write_json(LIVE_ADAPTER_VALIDATIONS_PATH, rows)


def record_live_adapter_readonly_validation(*, operator: str = "local", note: str = "") -> dict[str, Any]:
    record = _build_readonly_validation(operator=operator, note=note)
    rows = load_live_adapter_readonly_validations()
    rows.append(record)
    save_live_adapter_readonly_validations(rows)
    return record


def list_live_adapter_readonly_validations(*, limit: int = 100, status: str | None = None, operator: str | None = None) -> list[dict[str, Any]]:
    rows = list(reversed(load_live_adapter_readonly_validations()))
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if operator:
        wanted = _text(operator)
        rows = [row for row in rows if _text(row.get("operator")) == wanted]
    return rows[: max(0, int(limit))]


def get_live_adapter_readonly_validation(validation_id: str) -> dict[str, Any] | None:
    wanted = _text(validation_id)
    for row in load_live_adapter_readonly_validations():
        if _text(row.get("validation_id")) == wanted:
            return row
    return None


def _execution_packet_hash(payload: dict[str, Any]) -> str:
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
    return _stable_hash(material)


def _latest_dry_run_receipt(packet_id: str) -> dict[str, Any] | None:
    wanted = _text(packet_id)
    for receipt in reversed(load_live_dry_run_receipts()):
        if _text(receipt.get("packet_id")) == wanted:
            return receipt
    return None


def _adapter_request_preview(packet: dict[str, Any]) -> dict[str, Any]:
    wire = dict(packet.get("wire_order_preview") or {})
    return {
        "adapter": "polymarket_clob_manual_boundary_v1",
        "request_schema_version": "0.6.0-adapter-request-v1",
        "network_mode": "manual_review_no_submission",
        "method": "POST",
        "path": "/orders",
        "client_order_id": f"manual_{_text(packet.get('packet_id'))}",
        "payload": {
            "market_id": _text(wire.get("market_id") or packet.get("market_id")),
            "asset_id": _text(wire.get("asset_id") or packet.get("token_id")),
            "outcome": _text(wire.get("outcome") or packet.get("outcome")),
            "side": _text(wire.get("side") or packet.get("side")).upper(),
            "order_type": _text(wire.get("order_type") or packet.get("order_type")).lower(),
            "time_in_force": _text(wire.get("time_in_force") or packet.get("time_in_force")).upper(),
            "price": _rounded(wire.get("price") or packet.get("price")),
            "size": _rounded(wire.get("size") or packet.get("size")),
        },
        "signature_included": False,
        "signed_payload_present": False,
        "secret_material_included": False,
        "network_submission_attempted": False,
        "exchange_acknowledgement": False,
    }


def _validate_request_shape(request_preview: dict[str, Any]) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    payload = request_preview.get("payload") if isinstance(request_preview.get("payload"), dict) else {}
    for key in ["market_id", "asset_id", "side", "order_type", "time_in_force", "price", "size"]:
        if payload.get(key) in (None, ""):
            blockers.append(f"adapter_request.payload.{key} is required.")
    side = _text(payload.get("side")).upper()
    if side and side not in VALID_SIDES:
        blockers.append("adapter_request.payload.side must be BUY or SELL.")
    order_type = _text(payload.get("order_type")).lower()
    if order_type and order_type not in VALID_ORDER_TYPES:
        blockers.append("adapter_request.payload.order_type must be limit or marketable_limit.")
    tif = _text(payload.get("time_in_force")).upper()
    if tif and tif not in VALID_TIME_IN_FORCE:
        blockers.append("adapter_request.payload.time_in_force must be GTC, FOK, or FAK.")
    price = _decimal(payload.get("price"))
    size = _decimal(payload.get("size"))
    if price is None:
        blockers.append("adapter_request.payload.price must be a valid decimal.")
    elif price <= Decimal("0") or price >= Decimal("1"):
        blockers.append("adapter_request.payload.price must be greater than 0 and less than 1.")
    if size is None:
        blockers.append("adapter_request.payload.size must be a valid decimal.")
    elif size <= Decimal("0"):
        blockers.append("adapter_request.payload.size must be greater than zero.")
    if request_preview.get("signature_included") or request_preview.get("signed_payload_present"):
        blockers.append("adapter request preview must not include a signed payload.")
    if request_preview.get("secret_material_included"):
        blockers.append("adapter request preview must not include secret material.")
    if request_preview.get("network_submission_attempted"):
        blockers.append("adapter request preview must not report network submission.")
    if not blockers and order_type == "marketable_limit":
        warnings.append("marketable_limit is structurally valid but requires heightened manual review before any future live implementation.")
    return blockers, warnings


def _derive_adapter_request_status(
    *,
    packet: dict[str, Any] | None,
    authorization: dict[str, Any] | None,
    dry_run: dict[str, Any] | None,
    config: dict[str, Any],
    request_shape_blockers: list[str],
    request_shape_warnings: list[str],
) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    kinds: set[str] = set()

    def block(kind: str, message: str) -> None:
        kinds.add(kind)
        blockers.append(message)

    if not packet:
        return "blocked_by_missing_packet", ["saved live execution packet was not found."], warnings

    packet_status = _text(packet.get("status"))
    if packet_status not in PACKET_READY_STATUSES:
        block("packet", f"packet status {packet_status or 'unknown'} is not adapter-request ready.")
    if not bool(packet.get("packet_ready_for_future_adapter")):
        block("packet", "packet_ready_for_future_adapter is false.")
    if not bool(packet.get("unsigned_only")):
        block("packet", "packet must remain unsigned_only for adapter request validation.")
    if bool(packet.get("signed_payload_present")):
        block("order_fields", "packet unexpectedly contains signed payload material.")
    if bool(packet.get("exchange_acknowledgement")) or _text(packet.get("exchange_order_id")):
        block("order_fields", "packet unexpectedly contains exchange acknowledgement/order id data.")
    if bool(packet.get("execution_allowed")) or bool(packet.get("order_submission_enabled")):
        block("order_fields", "packet unexpectedly reports execution/submission enabled.")
    expected_hash = _execution_packet_hash(packet)
    if _text(packet.get("packet_hash")) != expected_hash:
        block("packet", "packet_hash does not match current packet fields.")

    auth_id = _text(packet.get("authorization_id"))
    if not auth_id or not authorization:
        block("authorization", "operator authorization snapshot is required before adapter request validation.")
    else:
        if _text(authorization.get("authorization_hash")) != _text(packet.get("authorization_hash")):
            block("authorization", "authorization hash does not match the packet snapshot.")
        if _text(authorization.get("decision")).lower() != "authorize":
            block("authorization", "authorization decision is not authorize.")
        if _text(authorization.get("status")) not in {"authorized_dry_run", "authorized_with_warnings"}:
            block("authorization", f"authorization status {_text(authorization.get('status') or 'unknown')} is not adapter-request ready.")
        if not bool(authorization.get("acknowledgement")):
            block("authorization", "authorization acknowledgement is missing.")
        if bool(authorization.get("execution_allowed")):
            block("authorization", "authorization unexpectedly reports execution_allowed=true.")

    preflight_state = _text(packet.get("preflight_state_snapshot"))
    if preflight_state not in {"ready_for_operator_authorization", "ready_with_warnings"}:
        block("preflight", f"packet preflight snapshot {preflight_state or 'missing'} is not ready.")
    if preflight_state == "ready_with_warnings":
        warnings.append("packet preflight snapshot was ready_with_warnings; review warnings before any future execution.")

    if config.get("dry_run_receipt_required"):
        if not dry_run:
            block("dry_run", "offline dry-run adapter receipt is required before adapter request validation.")
        else:
            dry_status = _text(dry_run.get("status"))
            if dry_status not in DRY_RUN_READY_STATUSES:
                block("dry_run", f"latest dry-run receipt status {dry_status or 'unknown'} is not validated.")
            if _text(dry_run.get("packet_hash")) != _text(packet.get("packet_hash")):
                block("dry_run", "latest dry-run receipt packet_hash does not match the packet.")
            if bool(dry_run.get("network_attempted")):
                block("dry_run", "latest dry-run receipt unexpectedly reports network_attempted=true.")
            if bool(dry_run.get("execution_allowed")) or bool(dry_run.get("order_submission_enabled")):
                block("dry_run", "latest dry-run receipt unexpectedly reports execution/submission enabled.")
            if bool(dry_run.get("signed_payload_present")):
                block("dry_run", "latest dry-run receipt unexpectedly reports signed payload material.")
            warnings.extend(str(item) for item in list(dry_run.get("warnings") or [])[:5])

    token_id = _text(packet.get("token_id"))
    market_id = _text(packet.get("market_id"))
    side = _text(packet.get("side")).upper()
    price = _decimal(packet.get("price"))
    size = _decimal(packet.get("size"))
    notional = Decimal("0")
    if price is not None and size is not None:
        notional = price * size

    if not token_id:
        block("order_fields", "token_id is required.")
    if not market_id:
        block("order_fields", "market_id is required.")
    if side not in VALID_SIDES:
        block("order_fields", "side must be BUY or SELL.")
    if price is None or price <= Decimal("0") or price >= Decimal("1"):
        block("order_fields", "price must be a valid decimal greater than 0 and less than 1.")
    if size is None or size <= Decimal("0"):
        block("order_fields", "size must be a valid decimal greater than zero.")
    if notional <= Decimal("0"):
        block("order_fields", "computed notional must be greater than zero.")

    max_order = Decimal(str(config.get("max_order_notional") or 0))
    if max_order <= Decimal("0"):
        block("risk", "LIVE_MAX_ORDER_NOTIONAL is 0/unset; set a deliberate local maximum before adapter requests can be ready.")
    elif notional > max_order:
        block("risk", f"packet notional {float(notional):.4f} exceeds LIVE_MAX_ORDER_NOTIONAL {float(max_order):.4f}.")
    allowed = list(config.get("allowed_market_ids") or [])
    if not allowed:
        block("risk", "LIVE_ALLOWED_MARKET_IDS is empty; no market is allowlisted for live adapter request review.")
    elif market_id not in allowed:
        block("risk", "market_id is not present in LIVE_ALLOWED_MARKET_IDS.")

    quality = _execution_quality_for_packet(packet)
    if not quality:
        if settings.market_data_require_for_live:
            block("market_data", "market-data snapshot/execution-quality simulation is required for live adapter request review.")
        else:
            warnings.append("market-data snapshot/execution-quality simulation is missing.")
    else:
        quality_state = _text(quality.get("state"))
        if quality_state not in {"quality_pass", "quality_pass_with_warnings"}:
            block("market_data", f"execution-quality state is {quality_state or 'unknown'}.")
        warnings.extend(str(item) for item in list(quality.get("warnings") or [])[:5])

    if config.get("kill_switch_active"):
        block("kill_switch", "POLYMARKET_LIVE_KILL_SWITCH is active.")
    if config.get("manual_auth_required") and not bool(packet.get("authorization_acknowledged_snapshot")):
        block("manual_auth", "manual authorization acknowledgement snapshot is required.")
    if not config.get("manual_auth_required"):
        block("manual_auth", "POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH must remain true before adapter requests can be ready.")
    if config.get("cancel_requested"):
        warnings.append("Cancellation was requested in config, but cancellation remains unavailable in this release.")

    for message in request_shape_blockers:
        block("order_fields", message)
    warnings.extend(request_shape_warnings)
    warnings.extend(str(item) for item in list(packet.get("warnings") or [])[:5])

    if blockers:
        priority = [
            ("packet", "blocked_by_missing_packet"),
            ("authorization", "blocked_by_missing_authorization"),
            ("preflight", "blocked_by_preflight"),
            ("dry_run", "blocked_by_dry_run"),
            ("market_data", "blocked_by_preflight"),
            ("kill_switch", "blocked_by_kill_switch"),
            ("risk", "blocked_by_risk_limit"),
            ("order_fields", "blocked_by_invalid_order_fields"),
            ("manual_auth", "invalid"),
        ]
        for kind, status in priority:
            if kind in kinds:
                return status, blockers, warnings
        return "invalid", blockers, warnings
    if not config.get("submit_requested"):
        return "blocked_by_submit_disabled", ["POLYMARKET_LIVE_ENABLE_SUBMIT is false; adapter request is only a local preview."], warnings
    if warnings:
        return "adapter_request_ready_with_warnings", blockers, warnings
    return "adapter_request_ready", blockers, warnings


def _execution_quality_for_packet(packet: dict[str, Any] | None) -> dict[str, Any] | None:
    if not packet:
        return None
    snapshot = latest_market_snapshot(market_id=_text(packet.get("market_id")), token_id=_text(packet.get("token_id")))
    if not snapshot:
        return None
    return build_execution_quality_simulation(
        side=_text(packet.get("side") or "BUY", "BUY"),
        market_id=_text(packet.get("market_id")),
        token_id=_text(packet.get("token_id")),
        price=_safe_float(packet.get("price")),
        size=_safe_float(packet.get("size")),
        order_type=_text(packet.get("order_type") or "limit", "limit"),
        time_in_force=_text(packet.get("time_in_force") or "GTC", "GTC"),
        snapshot_id=_text(snapshot.get("snapshot_id")),
        source_intent_id=_text(packet.get("intent_id")),
    )


def build_live_adapter_request(
    *,
    packet_id: str,
    operator: str = "local",
    note: str = "",
    request_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    packet = get_live_execution_packet(packet_id)
    config = _adapter_config()
    authorization = get_live_order_authorization(_text(packet.get("authorization_id"))) if packet else None
    dry_run = _latest_dry_run_receipt(packet_id)
    request_preview = _adapter_request_preview(packet or {"packet_id": packet_id})
    shape_blockers, shape_warnings = _validate_request_shape(request_preview)
    status, blockers, warnings = _derive_adapter_request_status(
        packet=packet,
        authorization=authorization,
        dry_run=dry_run,
        config=config,
        request_shape_blockers=shape_blockers,
        request_shape_warnings=shape_warnings,
    )
    packet = packet or {}
    authorization = authorization or {}
    dry_run = dry_run or {}
    execution_quality = _execution_quality_for_packet(packet)
    record = {
        "request_id": request_id or f"lar_{uuid4().hex[:12]}",
        "version": "0.6.0-live-adapter-request-v1",
        "mode": "live_adapter_request_validation_v060",
        "created_at": created_at or _now(),
        "operator": _text(operator, "local"),
        "status": status,
        "packet_id": _text(packet_id),
        "packet_hash": _text(packet.get("packet_hash")),
        "packet_status_snapshot": _text(packet.get("status") or "missing"),
        "intent_id": _text(packet.get("intent_id")),
        "authorization_id": _text(packet.get("authorization_id")),
        "authorization_hash": _text(packet.get("authorization_hash")),
        "authorization_status_snapshot": _text(authorization.get("status") or packet.get("authorization_status_snapshot")),
        "preflight_state_snapshot": _text(packet.get("preflight_state_snapshot")),
        "dry_run_receipt_id": _text(dry_run.get("receipt_id")),
        "dry_run_receipt_status": _text(dry_run.get("status")),
        "market_id": _text(packet.get("market_id")),
        "token_id": _text(packet.get("token_id")),
        "outcome": _text(packet.get("outcome")),
        "side": _text(packet.get("side")),
        "order_type": _text(packet.get("order_type")),
        "time_in_force": _text(packet.get("time_in_force")),
        "price": _rounded(packet.get("price")),
        "size": _rounded(packet.get("size")),
        "notional": _rounded(packet.get("notional")),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "execution_quality_state": (execution_quality or {}).get("state", "missing"),
        "execution_quality_snapshot_id": (execution_quality or {}).get("snapshot_id", ""),
        "execution_quality_simulation": execution_quality,
        "adapter_request_preview": request_preview,
        "adapter_config_snapshot": {
            "host": config.get("host"),
            "chain_id": config.get("chain_id"),
            "live_mode_enabled": bool(config.get("live_mode_enabled")),
            "readonly_network_enabled": bool(config.get("readonly_network_enabled")),
            "submit_requested": bool(config.get("submit_requested")),
            "cancel_requested": bool(config.get("cancel_requested")),
            "manual_auth_required": bool(config.get("manual_auth_required")),
            "kill_switch_active": bool(config.get("kill_switch_active")),
            "dry_run_receipt_required": bool(config.get("dry_run_receipt_required")),
            "max_order_notional": config.get("max_order_notional"),
            "allowed_market_count": len(config.get("allowed_market_ids") or []),
        },
        "adapter_request_ready": status in ADAPTER_REQUEST_READY_STATUSES,
        "manual_execution_review_candidate": status in ADAPTER_REQUEST_READY_STATUSES or status == "blocked_by_submit_disabled",
        "order_submission_requested": bool(config.get("submit_requested")),
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "network_submission_attempted": False,
        "network_attempted": False,
        "signed_payload_present": False,
        "exchange_order_id": "",
        "exchange_acknowledgement": False,
        "secret_values_returned": False,
        "note": _text(note),
        "next_required_action": _adapter_request_next_action(status),
        "guardrail": "Adapter request validation only. This record validates request shape and gates for manual review without signing, submitting, cancelling, sending network requests, touching wallets, or automating trading.",
    }
    record["request_hash"] = _stable_hash(
        {
            "packet_id": record.get("packet_id"),
            "packet_hash": record.get("packet_hash"),
            "authorization_hash": record.get("authorization_hash"),
            "status": record.get("status"),
            "market_id": record.get("market_id"),
            "token_id": record.get("token_id"),
            "side": record.get("side"),
            "order_type": record.get("order_type"),
            "time_in_force": record.get("time_in_force"),
            "price": record.get("price"),
            "size": record.get("size"),
            "notional": record.get("notional"),
            "adapter_request_preview": record.get("adapter_request_preview"),
            "blockers": record.get("blockers"),
        }
    )
    return record


def _adapter_request_next_action(status: str) -> str:
    if status == "adapter_request_ready":
        return "Adapter request shape is ready for manual execution review; this release still cannot submit it."
    if status == "adapter_request_ready_with_warnings":
        return "Adapter request shape is ready with warnings; inspect warnings before any future manual execution implementation."
    if status == "blocked_by_submit_disabled":
        return "Adapter request preview is local-only because submit configuration is disabled. Leave it disabled unless a future manual submission build is explicitly implemented."
    if status == "blocked_by_missing_packet":
        return "Create or select a saved unsigned execution packet."
    if status == "blocked_by_missing_authorization":
        return "Record an acknowledged operator authorization snapshot first."
    if status == "blocked_by_preflight":
        return "Resolve live-intent preflight blockers and regenerate the packet."
    if status == "blocked_by_dry_run":
        return "Record a current offline dry-run adapter receipt for this packet."
    if status == "blocked_by_kill_switch":
        return "Keep request blocked while the kill switch is active."
    if status == "blocked_by_risk_limit":
        return "Set deliberate local risk limits and allowlist before adapter request review."
    if status == "blocked_by_invalid_order_fields":
        return "Correct market/token/side/price/size fields before adapter request review."
    return "Review blockers before proceeding."


def load_live_adapter_requests() -> list[dict[str, Any]]:
    rows = _read_json(LIVE_ADAPTER_REQUESTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_live_adapter_requests(rows: list[dict[str, Any]]) -> None:
    _write_json(LIVE_ADAPTER_REQUESTS_PATH, rows)


def record_live_adapter_request(*, packet_id: str, operator: str = "local", note: str = "") -> dict[str, Any]:
    record = build_live_adapter_request(packet_id=packet_id, operator=operator, note=note)
    rows = load_live_adapter_requests()
    rows.append(record)
    save_live_adapter_requests(rows)
    return record


def list_live_adapter_requests(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    packet_id: str | None = None,
    intent_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_live_adapter_requests()))
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


def get_live_adapter_request(identifier: str) -> dict[str, Any] | None:
    wanted = _text(identifier)
    for row in load_live_adapter_requests():
        if _text(row.get("request_id")) == wanted:
            return row
    for row in reversed(load_live_adapter_requests()):
        if _text(row.get("packet_id")) == wanted:
            return row
    return None


def summarize_live_adapter_requests(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    all_rows = load_live_adapter_requests()
    selected = rows if rows is not None else list(reversed(all_rows))
    statuses = Counter(_text(row.get("status") or "unknown") for row in selected)
    latest = list(reversed(all_rows))[0] if all_rows else {}
    ready = statuses.get("adapter_request_ready", 0) + statuses.get("adapter_request_ready_with_warnings", 0)
    blocked = len(selected) - ready
    return {
        "count": len(selected),
        "saved_count": len(all_rows),
        "adapter_request_ready": statuses.get("adapter_request_ready", 0),
        "adapter_request_ready_with_warnings": statuses.get("adapter_request_ready_with_warnings", 0),
        "blocked_by_submit_disabled": statuses.get("blocked_by_submit_disabled", 0),
        "blocked_by_dry_run": statuses.get("blocked_by_dry_run", 0),
        "blocked_by_kill_switch": statuses.get("blocked_by_kill_switch", 0),
        "blocked_by_risk_limit": statuses.get("blocked_by_risk_limit", 0),
        "blocked_by_invalid_order_fields": statuses.get("blocked_by_invalid_order_fields", 0),
        "invalid": statuses.get("invalid", 0),
        "ready_total": ready,
        "blocked_total": blocked,
        "by_status": dict(sorted(statuses.items())),
        "total_ready_notional": round(sum(_safe_float(row.get("notional")) for row in selected if row.get("adapter_request_ready")), 6),
        "latest_request_id": latest.get("request_id", ""),
        "latest_status": latest.get("status", ""),
        "latest_created_at": latest.get("created_at", ""),
        "network_attempted": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "execution_available": False,
        "note": "Live adapter requests are local validation records only; they never submit orders.",
    }


def build_live_adapter_request_board(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    packet_id: str | None = None,
    intent_id: str | None = None,
) -> dict[str, Any]:
    rows = list_live_adapter_requests(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    packets = [row for row in list_live_execution_packets(limit=100) if _text(row.get("status")) in PACKET_READY_STATUSES]
    return {
        "version": "0.6.0-live-adapter-request-v1",
        "mode": "live_adapter_request_board_v060",
        "generated_at": _now(),
        "summary": summarize_live_adapter_requests(rows),
        "items": rows,
        "packet_candidates": packets[:25],
        "filters": {
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "packet_id": packet_id or "",
            "intent_id": intent_id or "",
        },
        "guardrail": "Live adapter requests are request-shape and safety-gate validation records. They never sign, submit, cancel, send network requests, touch wallets, or automate trading.",
    }


def live_adapter_readiness_to_csv(report: dict[str, Any] | None = None) -> str:
    report = report or build_live_adapter_readiness()
    fields = [
        "generated_at",
        "overall_status",
        "configured_host",
        "configured_chain_id",
        "dependency_present",
        "live_mode_enabled",
        "read_only_network_validation_enabled",
        "order_submission_requested",
        "order_submission_enabled",
        "order_cancellation_requested",
        "order_cancellation_enabled",
        "manual_auth_required",
        "kill_switch_active",
        "dry_run_receipt_required",
        "max_order_notional",
        "allowed_market_count",
        "wallet_address_present",
        "funder_address_present",
        "api_key_present",
        "secret_present",
        "passphrase_present",
        "private_key_present",
        "blockers",
        "warnings",
        "recommended_next_action",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    creds = report.get("credential_presence", {})
    row = dict(report)
    for key in ["wallet_address_present", "funder_address_present", "api_key_present", "secret_present", "passphrase_present", "private_key_present"]:
        row[key] = creds.get(key, "")
    row["blockers"] = _csv_join(list(report.get("blockers") or []))
    row["warnings"] = _csv_join(list(report.get("warnings") or []))
    writer.writerow({key: row.get(key, "") for key in fields})
    return output.getvalue()


def live_adapter_validations_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "validation_id",
        "created_at",
        "operator",
        "status",
        "configured_host",
        "configured_chain_id",
        "dependency_present",
        "client_construction_attempted",
        "client_constructed",
        "read_only_network_validation_enabled",
        "network_attempted",
        "order_submission_attempted",
        "order_cancellation_attempted",
        "blocker_count",
        "warning_count",
        "blockers",
        "warnings",
        "validation_hash",
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


def live_adapter_requests_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "request_id",
        "created_at",
        "operator",
        "status",
        "packet_id",
        "packet_status_snapshot",
        "intent_id",
        "authorization_id",
        "preflight_state_snapshot",
        "dry_run_receipt_id",
        "dry_run_receipt_status",
        "market_id",
        "token_id",
        "outcome",
        "side",
        "order_type",
        "time_in_force",
        "price",
        "size",
        "notional",
        "adapter_request_ready",
        "manual_execution_review_candidate",
        "order_submission_requested",
        "order_submission_enabled",
        "network_submission_attempted",
        "signed_payload_present",
        "exchange_acknowledgement",
        "blocker_count",
        "warning_count",
        "blockers",
        "warnings",
        "packet_hash",
        "request_hash",
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


def _latest_adapter_request(packet_id: str) -> dict[str, Any] | None:
    wanted = _text(packet_id)
    for row in reversed(load_live_adapter_requests()):
        if _text(row.get("packet_id")) == wanted:
            return row
    return None


def build_manual_execution_review(
    *,
    packet_id: str,
    operator: str = "local",
    note: str = "",
    acknowledged: bool = False,
    review_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    config = _adapter_config()
    adapter_request = _latest_adapter_request(packet_id) or build_live_adapter_request(packet_id=packet_id, operator=operator, note=note)
    request_status = _text(adapter_request.get("status"))
    checklist = [
        {
            "step": "adapter_request_ready",
            "required": True,
            "passed": request_status in ADAPTER_REQUEST_READY_STATUSES,
            "detail": f"Adapter request status is {request_status or 'missing'}.",
        },
        {
            "step": "manual_authorization_required",
            "required": True,
            "passed": bool(config.get("manual_auth_required")),
            "detail": "POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH must remain true.",
        },
        {
            "step": "kill_switch_clear",
            "required": True,
            "passed": not bool(config.get("kill_switch_active")),
            "detail": "POLYMARKET_LIVE_KILL_SWITCH must be false for manual review readiness.",
        },
        {
            "step": "final_operator_acknowledgement",
            "required": True,
            "passed": bool(acknowledged),
            "detail": "A one-time final acknowledgement is required for this local review record.",
        },
        {
            "step": "signed_payload_absent",
            "required": True,
            "passed": not bool(adapter_request.get("signed_payload_present")),
            "detail": "No signed payload may be present in this scaffolded boundary.",
        },
        {
            "step": "network_not_attempted",
            "required": True,
            "passed": not bool(adapter_request.get("network_submission_attempted") or adapter_request.get("network_attempted")),
            "detail": "Manual execution review must not submit to the network.",
        },
        {
            "step": "submission_implementation_absent",
            "required": False,
            "passed": not bool(adapter_request.get("order_submission_enabled")),
            "detail": "This release intentionally has no live order submission implementation.",
        },
    ]
    blockers = [item["detail"] for item in checklist if item.get("required") and not item.get("passed")]
    warnings = [str(item) for item in list(adapter_request.get("warnings") or [])[:5]]
    if request_status == "blocked_by_submit_disabled":
        status = "execution_submission_disabled"
        blockers = ["POLYMARKET_LIVE_ENABLE_SUBMIT is false; manual execution remains a non-submitting local review."] + blockers
    elif config.get("kill_switch_active"):
        status = "blocked_by_kill_switch"
    elif request_status not in ADAPTER_REQUEST_READY_STATUSES:
        status = "blocked_by_adapter_request"
    elif not acknowledged:
        status = "operator_final_confirmation_required"
    elif warnings:
        status = "manual_execution_review_ready_with_warnings"
    else:
        status = "manual_execution_review_ready"

    record = {
        "review_id": review_id or f"mer_{uuid4().hex[:12]}",
        "version": "0.6.0-manual-execution-boundary-v1",
        "mode": "manual_execution_review_v060",
        "created_at": created_at or _now(),
        "operator": _text(operator, "local"),
        "status": status,
        "packet_id": _text(packet_id),
        "adapter_request_id": _text(adapter_request.get("request_id")),
        "adapter_request_status_snapshot": request_status,
        "adapter_request_hash": _text(adapter_request.get("request_hash")),
        "market_id": _text(adapter_request.get("market_id")),
        "token_id": _text(adapter_request.get("token_id")),
        "side": _text(adapter_request.get("side")),
        "outcome": _text(adapter_request.get("outcome")),
        "price": _rounded(adapter_request.get("price")),
        "size": _rounded(adapter_request.get("size")),
        "notional": _rounded(adapter_request.get("notional")),
        "checklist": checklist,
        "final_confirmation_acknowledged": bool(acknowledged),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "manual_execution_ready": status in MANUAL_REVIEW_READY_STATUSES,
        "execution_submission_disabled": True,
        "operator_final_confirmation_required": not bool(acknowledged),
        "not_submitted": True,
        "network_not_attempted": True,
        "network_submission_attempted": False,
        "signed_payload_present": False,
        "exchange_order_id": "",
        "exchange_acknowledgement": False,
        "order_submission_enabled": False,
        "order_cancellation_enabled": False,
        "secret_values_returned": False,
        "note": _text(note),
        "next_required_action": _manual_review_next_action(status),
        "guardrail": "Manual execution review scaffold only. It records local checklist state and final acknowledgement status, but never signs, submits, cancels, sends network requests, touches wallets, or creates exchange acknowledgements.",
    }
    record["review_hash"] = _stable_hash(
        {
            "packet_id": record.get("packet_id"),
            "adapter_request_hash": record.get("adapter_request_hash"),
            "status": record.get("status"),
            "final_confirmation_acknowledged": record.get("final_confirmation_acknowledged"),
            "checklist": record.get("checklist"),
            "blockers": record.get("blockers"),
        }
    )
    return record


def _manual_review_next_action(status: str) -> str:
    if status == "manual_execution_review_ready":
        return "Manual review scaffold is complete. This release still does not submit; preserve the record for future implementation review."
    if status == "manual_execution_review_ready_with_warnings":
        return "Manual review scaffold is complete with warnings; inspect them before any future submission implementation."
    if status == "operator_final_confirmation_required":
        return "Record final local acknowledgement only after reviewing the adapter request and all blockers/warnings."
    if status == "execution_submission_disabled":
        return "Submission is disabled. This is the default safe boundary and no order was submitted."
    if status == "blocked_by_kill_switch":
        return "Manual execution review remains blocked while the kill switch is active."
    return "Resolve adapter request blockers before manual execution review."


def load_manual_execution_reviews() -> list[dict[str, Any]]:
    rows = _read_json(MANUAL_EXECUTION_REVIEWS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_manual_execution_reviews(rows: list[dict[str, Any]]) -> None:
    _write_json(MANUAL_EXECUTION_REVIEWS_PATH, rows)


def record_manual_execution_review(*, packet_id: str, operator: str = "local", note: str = "", acknowledged: bool = False) -> dict[str, Any]:
    record = build_manual_execution_review(packet_id=packet_id, operator=operator, note=note, acknowledged=acknowledged)
    rows = load_manual_execution_reviews()
    rows.append(record)
    save_manual_execution_reviews(rows)
    return record


def list_manual_execution_reviews(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    packet_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_manual_execution_reviews()))
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
    return rows[: max(0, int(limit))]


def get_manual_execution_review(review_id: str) -> dict[str, Any] | None:
    wanted = _text(review_id)
    for row in load_manual_execution_reviews():
        if _text(row.get("review_id")) == wanted:
            return row
    return None


def summarize_manual_execution_reviews(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    all_rows = load_manual_execution_reviews()
    selected = rows if rows is not None else list(reversed(all_rows))
    statuses = Counter(_text(row.get("status") or "unknown") for row in selected)
    latest = list(reversed(all_rows))[0] if all_rows else {}
    ready = statuses.get("manual_execution_review_ready", 0) + statuses.get("manual_execution_review_ready_with_warnings", 0)
    blocked = len(selected) - ready
    return {
        "count": len(selected),
        "saved_count": len(all_rows),
        "manual_execution_review_ready": statuses.get("manual_execution_review_ready", 0),
        "manual_execution_review_ready_with_warnings": statuses.get("manual_execution_review_ready_with_warnings", 0),
        "operator_final_confirmation_required": statuses.get("operator_final_confirmation_required", 0),
        "execution_submission_disabled": statuses.get("execution_submission_disabled", 0),
        "blocked_by_kill_switch": statuses.get("blocked_by_kill_switch", 0),
        "blocked_by_adapter_request": statuses.get("blocked_by_adapter_request", 0),
        "ready_total": ready,
        "blocked_total": blocked,
        "by_status": dict(sorted(statuses.items())),
        "latest_review_id": latest.get("review_id", ""),
        "latest_status": latest.get("status", ""),
        "latest_created_at": latest.get("created_at", ""),
        "network_attempted": False,
        "order_submission_enabled": False,
        "execution_available": False,
        "note": "Manual execution reviews are local checklist records only; this release never submits live orders.",
    }


def build_manual_execution_review_board(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    operator: str | None = None,
    packet_id: str | None = None,
) -> dict[str, Any]:
    rows = list_manual_execution_reviews(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id)
    candidates = [
        row
        for row in list(reversed(load_live_adapter_requests()))
        if _text(row.get("status")) in ADAPTER_REQUEST_READY_STATUSES or _text(row.get("status")) == "blocked_by_submit_disabled"
    ][:25]
    return {
        "version": "0.6.0-manual-execution-boundary-v1",
        "mode": "manual_execution_review_board_v060",
        "generated_at": _now(),
        "summary": summarize_manual_execution_reviews(rows),
        "items": rows,
        "adapter_request_candidates": candidates,
        "filters": {
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "packet_id": packet_id or "",
        },
        "guardrail": "Manual execution reviews are local checklist records only. They do not sign, submit, cancel, send network requests, touch wallets, or acknowledge exchange orders.",
    }


def manual_execution_reviews_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "review_id",
        "created_at",
        "operator",
        "status",
        "packet_id",
        "adapter_request_id",
        "adapter_request_status_snapshot",
        "market_id",
        "token_id",
        "side",
        "outcome",
        "price",
        "size",
        "notional",
        "final_confirmation_acknowledged",
        "manual_execution_ready",
        "execution_submission_disabled",
        "not_submitted",
        "network_submission_attempted",
        "signed_payload_present",
        "exchange_acknowledgement",
        "blocker_count",
        "warning_count",
        "blockers",
        "warnings",
        "review_hash",
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


def live_adapter_alerts(
    readiness: dict[str, Any] | None = None,
    request_board: dict[str, Any] | None = None,
    manual_board: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    readiness = readiness or build_live_adapter_readiness()
    request_board = request_board or build_live_adapter_request_board(limit=25)
    manual_board = manual_board or build_manual_execution_review_board(limit=25)
    alerts: list[dict[str, Any]] = []
    status = _text(readiness.get("overall_status"))
    if readiness.get("kill_switch_active"):
        alerts.append(_adapter_alert("warning", "live_adapter_kill_switch", "Live adapter kill switch is active", "Adapter request and manual execution review stay blocked.", {"overall_status": status}, "/live-adapter"))
    if status == "unsafe_submit_config":
        alerts.append(_adapter_alert("warning", "live_adapter_unsafe_config", "Live adapter config needs review", _csv_join(list(readiness.get("blockers") or [])[:2]), {"overall_status": status}, "/live-adapter"))
    if readiness.get("credential_presence", {}).get("l2_credentials_present") and not readiness.get("latest_readonly_validation"):
        alerts.append(_adapter_alert("info", "live_adapter_validation_missing", "Credentials detected without read-only validation", "Record an optional read-only validation receipt before future manual execution work.", {"overall_status": status}, "/live-adapter"))

    request_summary = request_board.get("summary", {}) if isinstance(request_board, dict) else {}
    ready_requests = _safe_int(request_summary.get("ready_total"))
    blocked_requests = _safe_int(request_summary.get("blocked_total"))
    if ready_requests:
        alerts.append(_adapter_alert("info", "live_adapter_request_ready", "Adapter requests ready for manual review", f"{ready_requests} adapter request validation record(s) are shape-ready; submission remains disabled.", {"ready": ready_requests}, "/live-adapter-requests"))
    if blocked_requests:
        alerts.append(_adapter_alert("warning", "live_adapter_request_blocked", "Adapter request validations are blocked", f"{blocked_requests} adapter request validation record(s) are blocked by safety gates.", {"blocked": blocked_requests}, "/live-adapter-requests"))

    manual_summary = manual_board.get("summary", {}) if isinstance(manual_board, dict) else {}
    if _safe_int(manual_summary.get("operator_final_confirmation_required")):
        alerts.append(_adapter_alert("warning", "manual_execution_confirmation_required", "Manual execution review needs final confirmation", "One or more local manual execution review records are waiting for final operator acknowledgement.", {"count": manual_summary.get("operator_final_confirmation_required")}, "/manual-execution-boundary"))
    return alerts[:10]


def _adapter_alert(level: str, kind: str, title: str, detail: str, data: dict[str, Any], link: str) -> dict[str, Any]:
    return {
        "timestamp": _now(),
        "level": level,
        "kind": kind,
        "title": title,
        "detail": detail,
        "market_id": None,
        "question": None,
        "source": "live_adapter_v060",
        "link": link,
        "data": data,
    }
