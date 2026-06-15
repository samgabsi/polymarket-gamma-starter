from __future__ import annotations

import csv
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .config import APP_VERSION, settings

SENSITIVE_ENV_KEYS = {
    "POLY_PRIVATE_KEY",
    "POLYMARKET_PRIVATE_KEY",
    "PK",
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

REAL_LIVE_CONFIRMATION = "I_UNDERSTAND_THIS_MAY_TRADE_REAL_MONEY"

# v1.0.0 keeps all SDK calls isolated in this module. Normal import, status,
# UI, CLI, and automated validation are still no-network. Real submit/cancel only
# occur when the caller already passed the manual control-plane gates and the
# operator explicitly configured live mode, real-network, submit/cancel flags,
# risk budgets, allowlists, credentials, and final confirmation.
SDK_CANDIDATES = {
    "official_unified_python_sdk": ["polymarket", "py_sdk", "polymarket_sdk"],
    "py_clob_client_v2": ["py_clob_client_v2"],
    "current_py_clob_client": ["py_clob_client"],
}

SDK_METHOD_CANDIDATES = {
    "official_unified_python_sdk": {
        "client": ["AsyncSecureClient", "SecureClient", "Client", "ClobClient"],
        "readonly": ["get_server_time", "get_ok", "get_markets", "get_order_book"],
        "submit": ["create_order", "post_order", "create_and_post_order", "submit_order"],
        "cancel": ["cancel", "cancel_order", "cancel_orders", "cancel_all"],
        "status": ["get_order", "get_order_status", "get_orders", "get_open_orders"],
    },
    "py_clob_client_v2": {
        "module": "py_clob_client_v2",
        "client": ["ClobClient"],
        "readonly": ["get_ok", "get_server_time", "get_markets", "get_order_book", "get_order_books", "get_midpoint"],
        "submit": ["create_and_post_order", "create_order", "post_order", "create_and_post_market_order"],
        "cancel": ["cancel_orders", "cancel_order", "cancel_market_orders", "cancel_all"],
        "status": ["get_order", "get_orders", "get_open_orders", "get_order_status"],
    },
    "current_py_clob_client": {
        "package": "py-clob-client",
        "client_module": "py_clob_client.client",
        "types_module": "py_clob_client.clob_types",
        "constants_module": "py_clob_client.order_builder.constants",
        "client": ["ClobClient"],
        "auth": ["ApiCreds"],
        "order": ["OrderArgs", "OrderType", "OpenOrderParams"],
        "readonly": ["get_ok", "get_server_time", "get_order_book", "get_orders"],
        "submit": ["create_order", "post_order"],
        "cancel": ["cancel", "cancel_all"],
        "status": ["get_order", "get_orders"],
        "documented_submit_path": "signed = ClobClient.create_order(OrderArgs(...)); ClobClient.post_order(signed, OrderType.GTC)",
        "documented_cancel_path": "ClobClient.cancel(order_id)",
    },
}

CURRENT_SDK_MAPPING_PLAN = {
    "preferred_family": "current_py_clob_client",
    "package": "py-clob-client",
    "import_modules": ["py_clob_client.client", "py_clob_client.clob_types", "py_clob_client.order_builder.constants"],
    "required_imports": ["ClobClient", "ApiCreds", "OrderArgs", "OrderType", "OpenOrderParams", "BUY", "SELL"],
    "client_constructor": "ClobClient(host, chain_id=137, key=POLY_PRIVATE_KEY, creds=ApiCreds(...), signature_type=..., funder=...)",
    "submit_method": "create_order + post_order",
    "submit_shape": "OrderArgs(token_id, price, size, side) then post_order(signed_order, OrderType.GTC)",
    "cancel_method": "cancel",
    "cancel_shape": "cancel(order_id)",
    "read_methods": ["get_ok", "get_server_time", "get_order", "get_orders"],
    "normal_validation_calls_sdk": False,
    "normal_validation_network": False,
    "real_submit_calls_sdk_when_gated": True,
    "real_cancel_calls_sdk_when_gated": True,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _bool_env(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(key: str, default: float = 0.0) -> float:
    try:
        raw = os.getenv(key)
        if raw is None or str(raw).strip() == "":
            return default
        return float(raw)
    except Exception:
        return default


def _int_env(key: str, default: int = 0) -> int:
    try:
        raw = os.getenv(key)
        if raw is None or str(raw).strip() == "":
            return default
        return int(float(raw))
    except Exception:
        return default


def _list_env(key: str) -> list[str]:
    return [item.strip() for item in os.getenv(key, "").split(",") if item.strip()]


def _present(value: Any) -> bool:
    text = _text(value)
    return bool(text and text not in {"***", "<redacted>"} and not text.upper().startswith("CHANGE_ME"))


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _stable_hash(material: Any) -> str:
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _package_version(name: str) -> str:
    candidates = [name, name.replace("_", "-"), "py-clob-client" if name == "py_clob_client" else name, "py-clob-client-v2" if name == "py_clob_client_v2" else name]
    for candidate in candidates:
        try:
            return importlib.metadata.version(candidate)
        except Exception:
            continue
    return "unknown"


def _module_presence(names: list[str]) -> tuple[bool, list[dict[str, str]]]:
    found: list[dict[str, str]] = []
    for name in names:
        if importlib.util.find_spec(name) is not None:
            found.append({"module": name, "version": _package_version(name)})
    return bool(found), found


def _safe_dir(obj: Any) -> set[str]:
    try:
        return set(dir(obj))
    except Exception:
        return set()


def _probe_current_py_clob_client() -> dict[str, Any]:
    root_spec = importlib.util.find_spec("py_clob_client")
    if root_spec is None:
        return {
            "module": "py_clob_client",
            "present": False,
            "status": "py_clob_client_dependency_missing",
            "required_symbols_present": False,
            "required_symbols": {name: False for name in CURRENT_SDK_MAPPING_PLAN["required_imports"]},
            "client_methods": {},
            "network_attempted": False,
        }
    try:
        client_mod = importlib.import_module("py_clob_client.client")
        types_mod = importlib.import_module("py_clob_client.clob_types")
        constants_mod = importlib.import_module("py_clob_client.order_builder.constants")
    except Exception as exc:
        return {
            "module": "py_clob_client",
            "present": True,
            "version": _package_version("py_clob_client"),
            "status": "py_clob_client_import_failed",
            "import_error_type": type(exc).__name__,
            "import_error_redacted": _redact_text(str(exc))[:240],
            "required_symbols_present": False,
            "network_attempted": False,
        }
    clob_client = getattr(client_mod, "ClobClient", None)
    client_dir = _safe_dir(clob_client)
    required_symbols = {
        "ClobClient": clob_client is not None,
        "ApiCreds": hasattr(types_mod, "ApiCreds"),
        "OrderArgs": hasattr(types_mod, "OrderArgs"),
        "OrderType": hasattr(types_mod, "OrderType"),
        "OpenOrderParams": hasattr(types_mod, "OpenOrderParams"),
        "BUY": hasattr(constants_mod, "BUY"),
        "SELL": hasattr(constants_mod, "SELL"),
    }
    client_methods = {
        "readonly": {name: name in client_dir for name in SDK_METHOD_CANDIDATES["current_py_clob_client"]["readonly"]},
        "submit": {name: name in client_dir for name in SDK_METHOD_CANDIDATES["current_py_clob_client"]["submit"]},
        "cancel": {name: name in client_dir for name in SDK_METHOD_CANDIDATES["current_py_clob_client"]["cancel"]},
        "status": {name: name in client_dir for name in SDK_METHOD_CANDIDATES["current_py_clob_client"]["status"]},
    }
    submit_ready = bool(client_methods["submit"].get("create_order") and client_methods["submit"].get("post_order"))
    cancel_ready = bool(client_methods["cancel"].get("cancel"))
    status = "py_clob_client_mapping_probe_passed" if all(required_symbols.values()) and submit_ready and cancel_ready else "py_clob_client_mapping_probe_incomplete"
    return {
        "module": "py_clob_client",
        "present": True,
        "version": _package_version("py_clob_client"),
        "status": status,
        "required_symbols_present": all(required_symbols.values()),
        "required_symbols": required_symbols,
        "client_methods": client_methods,
        "documented_submit_method_present": submit_ready,
        "documented_cancel_method_present": cancel_ready,
        "probe_imported_module": True,
        "constructed_client": False,
        "network_attempted": False,
        "signed_payload_present": False,
        "secret_values_returned": False,
    }


def _probe_py_clob_client_v2() -> dict[str, Any]:
    spec = importlib.util.find_spec("py_clob_client_v2")
    if spec is None:
        return {"module": "py_clob_client_v2", "present": False, "status": "py_clob_client_v2_dependency_missing", "network_attempted": False}
    try:
        module = importlib.import_module("py_clob_client_v2")
    except Exception as exc:
        return {"module": "py_clob_client_v2", "present": True, "status": "py_clob_client_v2_import_failed", "import_error_type": type(exc).__name__, "import_error_redacted": _redact_text(str(exc))[:240], "network_attempted": False}
    client = getattr(module, "ClobClient", None)
    client_dir = _safe_dir(client)
    return {
        "module": "py_clob_client_v2",
        "present": True,
        "version": _package_version("py_clob_client_v2"),
        "status": "py_clob_client_v2_present",
        "client_methods": {
            "submit": {name: name in client_dir for name in SDK_METHOD_CANDIDATES["py_clob_client_v2"]["submit"]},
            "cancel": {name: name in client_dir for name in SDK_METHOD_CANDIDATES["py_clob_client_v2"]["cancel"]},
            "status": {name: name in client_dir for name in SDK_METHOD_CANDIDATES["py_clob_client_v2"]["status"]},
        },
        "network_attempted": False,
    }


def probe_sdk_method_contract() -> dict[str, Any]:
    classic = _probe_current_py_clob_client()
    py_v2 = _probe_py_clob_client_v2()
    readiness = bool(classic.get("status") == "py_clob_client_mapping_probe_passed")
    status = "current_py_clob_client_mapping_probe_passed" if readiness else classic.get("status", "dependency_missing")
    return {
        "status": status,
        "mapping_plan": CURRENT_SDK_MAPPING_PLAN,
        "current_py_clob_client_probe": classic,
        "py_clob_client_v2_probe": py_v2,
        "submit_method_mapped": readiness,
        "cancel_method_mapped": readiness,
        "readiness_for_real_calls": readiness,
        "normal_validation_network": False,
        "normal_validation_submit_cancel": False,
    }


def detect_clob_dependencies() -> dict[str, Any]:
    packages: dict[str, dict[str, Any]] = {}
    present_any = False
    preferred_available = False
    preferred_family = ""
    for family, names in SDK_CANDIDATES.items():
        present, modules = _module_presence(names)
        packages[family] = {"present": present, "modules": modules, "method_candidates": SDK_METHOD_CANDIDATES.get(family, {})}
        present_any = present_any or present
        if family == "current_py_clob_client" and present:
            preferred_available = True
            preferred_family = family
        elif family in {"py_clob_client_v2", "official_unified_python_sdk"} and present and not preferred_family:
            preferred_available = True
            preferred_family = family
    method_probe = probe_sdk_method_contract()
    if method_probe.get("readiness_for_real_calls"):
        status = "preferred_dependency_present"
        preferred_available = True
        preferred_family = "current_py_clob_client"
    elif preferred_available:
        status = "dependency_present_mapping_incomplete"
    else:
        status = "dependency_missing"
    return {
        "status": status,
        "packages": packages,
        "any_dependency_present": present_any,
        "preferred_dependency_present": preferred_available,
        "preferred_family": preferred_family,
        "legacy_dependency_present": bool(packages.get("current_py_clob_client", {}).get("present") and not method_probe.get("readiness_for_real_calls")),
        "sdk_mapping_completed": bool(method_probe.get("readiness_for_real_calls")),
        "sdk_mapping_status": method_probe.get("status"),
        "sdk_method_probe": method_probe,
        "preferred_future_sdk": "py-clob-client runtime mapping implemented behind fail-closed gates; review current Polymarket docs before enabling.",
        "exact_remaining_integration_points": [] if method_probe.get("readiness_for_real_calls") else ["Install py-clob-client in the operator runtime and rerun no-network status probe."],
    }


def _env_any(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def clob_credential_readiness() -> dict[str, Any]:
    api_key = _env_any("POLY_API_KEY", "POLYMARKET_CLOB_API_KEY", "CLOB_API_KEY")
    secret = _env_any("POLY_SECRET", "POLYMARKET_CLOB_SECRET", "CLOB_SECRET")
    passphrase = _env_any("POLY_PASSPHRASE", "POLYMARKET_CLOB_PASSPHRASE", "CLOB_PASSPHRASE")
    private_key = _env_any("POLY_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY", "PK")
    wallet = _env_any("POLYMARKET_FUNDER_ADDRESS", "POLY_ADDRESS", "POLYMARKET_WALLET_ADDRESS")
    return {
        "wallet_address_present": _present(wallet),
        "private_key_present": _present(private_key),
        "api_key_present": _present(api_key),
        "secret_present": _present(secret),
        "passphrase_present": _present(passphrase),
        "l2_credentials_present": all(_present(v) for v in [api_key, secret, passphrase]),
        "l1_signing_material_present": _present(private_key),
        "funder_or_wallet_present": _present(wallet),
        "values_returned": False,
        "secret_values_returned": False,
    }


def _adapter_config() -> dict[str, Any]:
    return {
        "clob_host": _text(os.getenv("POLYMARKET_CLOB_HOST"), settings.clob_base_url),
        "chain_id": _int_env("POLYMARKET_CHAIN_ID", 137),
        "signature_type_configured": _present(os.getenv("POLYMARKET_SIGNATURE_TYPE")),
        "signature_type": _int_env("POLYMARKET_SIGNATURE_TYPE", 0),
        "live_mode": _bool_env("POLYMARKET_LIVE_MODE", _bool_env("LIVE_TRADING_ENABLED", False)),
        "network_readonly": _bool_env("POLYMARKET_LIVE_NETWORK_READONLY", False),
        "allow_real_network": _bool_env("POLYMARKET_LIVE_ALLOW_REAL_NETWORK", False),
        "enable_submit": _bool_env("POLYMARKET_LIVE_ENABLE_SUBMIT", False),
        "enable_cancel": _bool_env("POLYMARKET_LIVE_ENABLE_CANCEL", False),
        "enable_autonomous": _bool_env("POLYMARKET_LIVE_ENABLE_AUTONOMOUS", False),
        "kill_switch_active": _bool_env("POLYMARKET_LIVE_KILL_SWITCH", True),
        "manual_auth_required": _bool_env("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH", True),
        "fake_adapter_enabled": _bool_env("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED", False),
        "manual_submit_enabled": _bool_env("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED", False),
        "manual_cancel_enabled": _bool_env("POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED", False),
        "emergency_cancel_enabled": _bool_env("POLYMARKET_LIVE_EMERGENCY_CANCEL_ENABLED", False),
        "run_real_live_tests": _bool_env("POLYMARKET_RUN_REAL_LIVE_TESTS", False),
        "real_live_test_confirmation_present": _text(os.getenv("POLYMARKET_REAL_LIVE_TEST_CONFIRMATION")) == REAL_LIVE_CONFIRMATION,
        "max_order_notional": _float_env("POLYMARKET_LIVE_MAX_ORDER_NOTIONAL", _float_env("LIVE_MAX_ORDER_NOTIONAL", 0.0)),
        "max_daily_notional": _float_env("POLYMARKET_LIVE_MAX_DAILY_NOTIONAL", _float_env("LIVE_MAX_DAILY_NOTIONAL", 0.0)),
        "max_open_orders": _int_env("POLYMARKET_LIVE_MAX_OPEN_ORDERS", _int_env("LIVE_MAX_OPEN_ORDERS", 0)),
        "market_allowlist_count": len(_list_env("POLYMARKET_LIVE_MARKET_ALLOWLIST") or _list_env("LIVE_ALLOWED_MARKET_IDS")),
        "token_allowlist_count": len(_list_env("POLYMARKET_LIVE_TOKEN_ALLOWLIST")),
        "strategy_allowlist_count": len(_list_env("POLYMARKET_AUTONOMOUS_STRATEGY_ALLOWLIST")),
        "final_confirmation_configured": _present(os.getenv("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE")),
        "timeout_seconds": _float_env("POLYMARKET_LIVE_READONLY_TIMEOUT_SECONDS", 4.0),
        "real_adapter_sdk_family": _text(os.getenv("POLYMARKET_LIVE_SDK_FAMILY"), "current_py_clob_client"),
        "real_adapter_submit_method": "create_order+post_order",
        "real_adapter_cancel_method": "cancel",
    }


def _real_live_smoke_guard(cfg: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(cfg.get("run_real_live_tests") and cfg.get("real_live_test_confirmation_present") and cfg.get("live_mode") and cfg.get("allow_real_network"))
    return {
        "enabled": enabled,
        "run_real_live_tests": bool(cfg.get("run_real_live_tests")),
        "confirmation_matches_required_phrase": bool(cfg.get("real_live_test_confirmation_present")),
        "required_confirmation_phrase": REAL_LIVE_CONFIRMATION,
        "normal_validation_runs_real_tests": False,
    }


def build_clob_adapter_status() -> dict[str, Any]:
    cfg = _adapter_config()
    deps = detect_clob_dependencies()
    creds = clob_credential_readiness()
    probe = deps.get("sdk_method_probe", {})
    blockers: list[str] = []
    warnings: list[str] = []
    unsafe: list[str] = []

    if cfg["kill_switch_active"]:
        blockers.append("POLYMARKET_LIVE_KILL_SWITCH is active; live submit/cancel must stay blocked.")
    if not cfg["live_mode"]:
        blockers.append("POLYMARKET_LIVE_MODE is false; real CLOB adapter actions are disabled.")
    if cfg["allow_real_network"] and not cfg["live_mode"]:
        unsafe.append("Real network is allowed while live mode is false.")
    if cfg["enable_submit"] and not cfg["manual_submit_enabled"]:
        blockers.append("POLYMARKET_LIVE_ENABLE_SUBMIT is true but POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED is false.")
    if cfg["enable_cancel"] and not cfg["manual_cancel_enabled"] and not cfg["emergency_cancel_enabled"]:
        blockers.append("POLYMARKET_LIVE_ENABLE_CANCEL is true but manual/emergency cancel controls are disabled.")
    if cfg["allow_real_network"] and not creds["l2_credentials_present"]:
        blockers.append("Real network is allowed but redacted L2 credential presence is incomplete.")
    if cfg["allow_real_network"] and not creds["l1_signing_material_present"]:
        blockers.append("Real network is allowed but redacted private-key signing material is missing.")
    if cfg["enable_submit"] and not cfg["final_confirmation_configured"]:
        unsafe.append("Submit is enabled without POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE configured.")
    if cfg["enable_submit"] and cfg["max_order_notional"] <= 0:
        unsafe.append("Submit is enabled with no positive POLYMARKET_LIVE_MAX_ORDER_NOTIONAL.")
    if cfg["enable_submit"] and cfg["market_allowlist_count"] <= 0:
        unsafe.append("Submit is enabled without a market allowlist.")
    if not deps["sdk_mapping_completed"]:
        blockers.append("Current Python CLOB SDK dependency/method probe is not complete. Install py-clob-client in the operator runtime.")
    if deps.get("packages", {}).get("py_clob_client_v2", {}).get("present"):
        warnings.append("py_clob_client_v2 is present; this app uses the audited py-clob-client mapping unless POLYMARKET_LIVE_SDK_FAMILY is changed in a future adapter pass.")
    if cfg["enable_autonomous"]:
        warnings.append("Autonomous live mode remains blocked until manual live trading has been operator validated.")

    real_submit_outer_gates = bool(
        cfg["live_mode"]
        and cfg["allow_real_network"]
        and cfg["enable_submit"]
        and cfg["manual_submit_enabled"]
        and not cfg["kill_switch_active"]
        and creds["l2_credentials_present"]
        and creds["l1_signing_material_present"]
        and cfg["final_confirmation_configured"]
        and cfg["max_order_notional"] > 0
        and cfg["market_allowlist_count"] > 0
        and deps["sdk_mapping_completed"]
        and not unsafe
    )
    real_cancel_outer_gates = bool(
        cfg["live_mode"]
        and cfg["allow_real_network"]
        and cfg["enable_cancel"]
        and (cfg["manual_cancel_enabled"] or cfg["emergency_cancel_enabled"])
        and not cfg["kill_switch_active"]
        and creds["l2_credentials_present"]
        and creds["l1_signing_material_present"]
        and deps["sdk_mapping_completed"]
        and not unsafe
    )

    if unsafe:
        status = "unsafe_config_blocked"
    elif cfg["kill_switch_active"]:
        status = "kill_switch_active"
    elif not cfg["live_mode"]:
        status = "live_disabled_safe_default"
    elif not deps["sdk_mapping_completed"]:
        status = "dependency_missing"
    elif real_submit_outer_gates and real_cancel_outer_gates:
        status = "manual_submit_cancel_ready"
    elif real_submit_outer_gates:
        status = "manual_submit_ready"
    elif real_cancel_outer_gates:
        status = "manual_cancel_ready"
    elif cfg["network_readonly"] and cfg["allow_real_network"] and creds["l2_credentials_present"]:
        status = "readonly_ready"
    elif cfg["enable_submit"] or cfg["enable_cancel"]:
        status = "manual_live_blocked"
    else:
        status = "readonly_ready_no_submit"

    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "overall_status": status,
        "config": cfg,
        "credentials": creds,
        "dependency": deps,
        "method_contract": SDK_METHOD_CANDIDATES,
        "current_sdk_mapping_plan": CURRENT_SDK_MAPPING_PLAN,
        "sdk_method_probe": probe,
        "real_live_smoke_test_guard": _real_live_smoke_guard(cfg),
        "adapter_method_signatures_defined": True,
        "sdk_mapping_completed": bool(deps["sdk_mapping_completed"]),
        "sdk_mapping_plan_available": True,
        "sdk_mapping_status": probe.get("status"),
        "real_submit_outer_gates_configured": real_submit_outer_gates,
        "real_cancel_outer_gates_configured": real_cancel_outer_gates,
        "real_submit_implemented": True,
        "real_cancel_implemented": True,
        "real_submit_required_method": CURRENT_SDK_MAPPING_PLAN["submit_method"],
        "real_cancel_required_method": CURRENT_SDK_MAPPING_PLAN["cancel_method"],
        "network_attempted": False,
        "signed_payload_present": False,
        "exchange_acknowledgement_present": False,
        "blockers": blockers + unsafe,
        "warnings": warnings,
        "recommended_next_action": _adapter_next_action(status),
        "secret_values_returned": False,
        "guardrail": "v1.0.0 manual-live adapter mapping is implemented behind fail-closed gates. Status/validation remain no-network; real submit/cancel only run from manual control-plane record calls when every explicit operator gate passes.",
    }


def _adapter_next_action(status: str) -> str:
    return {
        "live_disabled_safe_default": "Keep live mode disabled until credentials, budgets, allowlists, final confirmation, and operator procedures are ready.",
        "kill_switch_active": "Kill switch blocks adapter calls. Leave it active until a deliberate live operation window.",
        "dependency_missing": "Install py-clob-client in the operator runtime and rerun the no-network adapter status probe.",
        "unsafe_config_blocked": "Resolve unsafe live/autonomous configuration before retrying.",
        "readonly_ready": "Read-only validation may be attempted after local review. Submit/cancel still require the manual control plane.",
        "manual_submit_ready": "Manual submit gates can pass. Recording a real_live submit will call the SDK; automated tests must not do this.",
        "manual_cancel_ready": "Manual cancel gates can pass. Recording a real_live cancel will call the SDK; automated tests must not do this.",
        "manual_submit_cancel_ready": "Manual submit/cancel gates can pass. Proceed only during an operator-controlled live window.",
    }.get(status, "Review adapter blockers before proceeding.")


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


def _redact_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _redact_data(v) for k, v in value.items() if str(k).lower() not in {"key", "secret", "passphrase", "private_key", "api_secret"}}
    if isinstance(value, list):
        return [_redact_data(v) for v in value]
    if isinstance(value, tuple):
        return [_redact_data(v) for v in value]
    return _redact_text(value)


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, default=str)
        return value
    except Exception:
        return _redact_text(str(value))


def _normalize_response(value: Any) -> dict[str, Any]:
    if value is None:
        raw: Any = {}
    elif isinstance(value, dict):
        raw = dict(value)
    elif hasattr(value, "model_dump"):
        raw = value.model_dump()
    elif hasattr(value, "dict"):
        raw = value.dict()
    else:
        raw = str(value)
    redacted = _redact_data(_json_safe(raw))
    return {
        "raw_response_hash": _stable_hash(redacted),
        "redacted_response_summary": redacted if isinstance(redacted, dict) else {"text": str(redacted)[:500]},
    }


def _extract_exchange_order_id(response: dict[str, Any]) -> str:
    candidates = []
    if isinstance(response, dict):
        candidates.extend([response.get("orderID"), response.get("order_id"), response.get("id"), response.get("hash")])
        data = response.get("data")
        if isinstance(data, dict):
            candidates.extend([data.get("orderID"), data.get("order_id"), data.get("id"), data.get("hash")])
    for candidate in candidates:
        text = _text(candidate)
        if text:
            return text
    return ""


def _public_order_copy(order: dict[str, Any]) -> dict[str, Any]:
    allowed = {"market_id", "condition_id", "token_id", "asset_id", "side", "price", "size", "notional", "order_type", "time_in_force", "outcome"}
    copy = {key: order.get(key) for key in allowed if key in order}
    for key in ["price", "size", "notional"]:
        if key in copy:
            number = _decimal(copy[key])
            copy[key] = str(number) if number is not None else copy[key]
    return copy


def _load_py_clob_client_runtime() -> dict[str, Any]:
    try:
        client_mod = importlib.import_module("py_clob_client.client")
        types_mod = importlib.import_module("py_clob_client.clob_types")
        constants_mod = importlib.import_module("py_clob_client.order_builder.constants")
        return {
            "ok": True,
            "ClobClient": getattr(client_mod, "ClobClient"),
            "ApiCreds": getattr(types_mod, "ApiCreds"),
            "OrderArgs": getattr(types_mod, "OrderArgs"),
            "OrderType": getattr(types_mod, "OrderType"),
            "OpenOrderParams": getattr(types_mod, "OpenOrderParams"),
            "BUY": getattr(constants_mod, "BUY"),
            "SELL": getattr(constants_mod, "SELL"),
        }
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "error": _redact_text(str(exc))[:240]}


def _build_client() -> tuple[Any | None, dict[str, Any]]:
    runtime = _load_py_clob_client_runtime()
    if not runtime.get("ok"):
        return None, {"status": "dependency_missing", "error_type": runtime.get("error_type"), "error_redacted": runtime.get("error"), "network_attempted": False}
    cfg = _adapter_config()
    api_key = _env_any("POLY_API_KEY", "POLYMARKET_CLOB_API_KEY", "CLOB_API_KEY")
    secret = _env_any("POLY_SECRET", "POLYMARKET_CLOB_SECRET", "CLOB_SECRET")
    passphrase = _env_any("POLY_PASSPHRASE", "POLYMARKET_CLOB_PASSPHRASE", "CLOB_PASSPHRASE")
    private_key = _env_any("POLY_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY", "PK")
    funder = _env_any("POLYMARKET_FUNDER_ADDRESS", "POLY_ADDRESS", "POLYMARKET_WALLET_ADDRESS")
    if not all(_present(v) for v in [api_key, secret, passphrase, private_key]):
        return None, {"status": "credentials_missing", "network_attempted": False}
    try:
        creds = runtime["ApiCreds"](api_key=api_key, api_secret=secret, api_passphrase=passphrase)
        kwargs: dict[str, Any] = {
            "host": cfg["clob_host"],
            "chain_id": int(cfg["chain_id"]),
            "key": private_key,
            "creds": creds,
        }
        if cfg.get("signature_type_configured"):
            kwargs["signature_type"] = int(cfg["signature_type"])
        if _present(funder):
            kwargs["funder"] = funder
        client = runtime["ClobClient"](**kwargs)
    except Exception as exc:
        return None, {"status": "adapter_unavailable", "error_type": type(exc).__name__, "error_redacted": _redact_text(str(exc))[:240], "network_attempted": False}
    return client, {"status": "client_initialized", "network_attempted": False, "secret_values_returned": False}


class FailClosedPolymarketClobAdapter:
    adapter_mode = "real_live"

    def validate_client_readonly(self) -> dict[str, Any]:
        status = build_clob_adapter_status()
        if status["overall_status"] in {"readonly_ready", "manual_submit_ready", "manual_cancel_ready", "manual_submit_cancel_ready"} and status.get("config", {}).get("network_readonly"):
            client, init = _build_client()
            if client is None:
                return {"adapter_mode": self.adapter_mode, "status": init.get("status", "adapter_unavailable"), "network_attempted": False, "blockers": [init.get("error_redacted") or init.get("status")], "secret_values_returned": False}
            try:
                ok = client.get_ok()
                server_time = client.get_server_time()
                normalized = _normalize_response({"ok": ok, "server_time": server_time})
                return {"adapter_mode": self.adapter_mode, "status": "readonly_validated", "network_attempted": True, "signed_payload_present": False, "exchange_acknowledgement_present": False, **normalized, "secret_values_returned": False}
            except Exception as exc:
                return {"adapter_mode": self.adapter_mode, "status": "readonly_failed", "network_attempted": True, "error_type": type(exc).__name__, "error_redacted": _redact_text(str(exc))[:240], "secret_values_returned": False}
        return {
            "adapter_mode": self.adapter_mode,
            "status": status["overall_status"],
            "network_attempted": False,
            "signed_payload_present": False,
            "exchange_acknowledgement_present": False,
            "dependency": status["dependency"],
            "sdk_method_probe": status.get("sdk_method_probe"),
            "blockers": status["blockers"],
            "warnings": status["warnings"],
            "secret_values_returned": False,
        }

    def prepare_order(self, order: dict[str, Any]) -> dict[str, Any]:
        public = _public_order_copy(order)
        return {"adapter_mode": self.adapter_mode, "status": "real_prepare_boundary_only", "public_order_fields": public, "order_shape_hash": _stable_hash(public), "network_attempted": False, "signed_payload_present": False, "exchange_acknowledgement_present": False, "secret_values_returned": False}

    def _status_blockers(self) -> tuple[dict[str, Any], list[str]]:
        status = build_clob_adapter_status()
        blockers = list(status.get("blockers") or [])
        return status, blockers

    def submit_order(self, *, attempt_id: str, order: dict[str, Any]) -> dict[str, Any]:
        status, blockers = self._status_blockers()
        public_order = _public_order_copy(order)
        if not status.get("real_submit_outer_gates_configured"):
            return {"adapter_mode": self.adapter_mode, "status": "submit_blocked", "attempt_id": attempt_id, "order_shape_hash": _stable_hash(public_order), "network_attempted": False, "signed_payload_present": False, "exchange_acknowledgement_present": False, "adapter_status": status["overall_status"], "blockers": blockers or ["real submit outer gates are not configured"], "warnings": status.get("warnings", []), "secret_values_returned": False}
        client, init = _build_client()
        if client is None:
            return {"adapter_mode": self.adapter_mode, "status": init.get("status", "adapter_unavailable"), "attempt_id": attempt_id, "network_attempted": False, "signed_payload_present": False, "exchange_acknowledgement_present": False, "blockers": [init.get("error_redacted") or init.get("status")], "secret_values_returned": False}
        runtime = _load_py_clob_client_runtime()
        try:
            side_raw = _text(order.get("side")).upper()
            side = runtime["BUY"] if side_raw == "BUY" else runtime["SELL"] if side_raw == "SELL" else side_raw
            token_id = _text(order.get("token_id") or order.get("asset_id"))
            price = float(_decimal(order.get("price")) or Decimal("0"))
            size = float(_decimal(order.get("size")) or Decimal("0"))
            if not token_id or price <= 0 or size <= 0 or side_raw not in {"BUY", "SELL"}:
                return {"adapter_mode": self.adapter_mode, "status": "submit_blocked", "attempt_id": attempt_id, "network_attempted": False, "signed_payload_present": False, "exchange_acknowledgement_present": False, "blockers": ["public order fields are incomplete: token_id, side, price, and size are required"], "secret_values_returned": False}
            order_args = runtime["OrderArgs"](token_id=token_id, price=price, size=size, side=side)
            order_type_name = _text(order.get("time_in_force") or order.get("order_type") or "GTC").upper()
            order_type = getattr(runtime["OrderType"], order_type_name, getattr(runtime["OrderType"], "GTC"))
            signed = client.create_order(order_args)
            response = client.post_order(signed, order_type)
            normalized = _normalize_response(response)
            summary = normalized.get("redacted_response_summary", {})
            exchange_order_id = _extract_exchange_order_id(summary if isinstance(summary, dict) else {})
            return {
                "adapter_mode": self.adapter_mode,
                "status": "submit_succeeded",
                "adapter_status": "submit_succeeded",
                "exchange_status": "acknowledged",
                "attempt_id": attempt_id,
                "network_attempted": True,
                "signed_payload_present": True,
                "exchange_acknowledgement_present": True,
                "exchange_order_id": exchange_order_id,
                **normalized,
                "secret_values_returned": False,
            }
        except Exception as exc:
            return {"adapter_mode": self.adapter_mode, "status": "submit_failed", "adapter_status": "submit_failed", "attempt_id": attempt_id, "network_attempted": True, "signed_payload_present": True, "exchange_acknowledgement_present": False, "error_type": type(exc).__name__, "error_redacted": _redact_text(str(exc))[:500], "secret_values_returned": False}

    def cancel_order(self, *, attempt_id: str, order_id: str = "", original_attempt: dict[str, Any] | None = None, fake_order_id: str = "") -> dict[str, Any]:
        status, blockers = self._status_blockers()
        target = _text(order_id) or _text(fake_order_id) or _text((original_attempt or {}).get("exchange_order_id")) or _text((original_attempt or {}).get("fake_order_id"))
        if not status.get("real_cancel_outer_gates_configured"):
            return {"adapter_mode": self.adapter_mode, "status": "cancel_blocked", "attempt_id": attempt_id, "target_order_id_present": bool(target), "target_order_id_hash": hashlib.sha256(target.encode("utf-8")).hexdigest() if target else "", "network_attempted": False, "signed_payload_present": False, "exchange_acknowledgement_present": False, "adapter_status": status["overall_status"], "blockers": blockers or ["real cancel outer gates are not configured"], "warnings": status.get("warnings", []), "secret_values_returned": False}
        if not target:
            return {"adapter_mode": self.adapter_mode, "status": "cancel_blocked", "attempt_id": attempt_id, "network_attempted": False, "target_order_id_present": False, "blockers": ["order_id is required for real cancel"], "secret_values_returned": False}
        client, init = _build_client()
        if client is None:
            return {"adapter_mode": self.adapter_mode, "status": init.get("status", "adapter_unavailable"), "attempt_id": attempt_id, "network_attempted": False, "signed_payload_present": False, "exchange_acknowledgement_present": False, "blockers": [init.get("error_redacted") or init.get("status")], "secret_values_returned": False}
        try:
            response = client.cancel(target)
            normalized = _normalize_response(response)
            return {"adapter_mode": self.adapter_mode, "status": "cancel_succeeded", "adapter_status": "cancel_succeeded", "exchange_status": "cancel_acknowledged", "attempt_id": attempt_id, "exchange_order_id": target, "network_attempted": True, "signed_payload_present": False, "exchange_acknowledgement_present": True, **normalized, "secret_values_returned": False}
        except Exception as exc:
            return {"adapter_mode": self.adapter_mode, "status": "cancel_failed", "adapter_status": "cancel_failed", "attempt_id": attempt_id, "exchange_order_id": target, "network_attempted": True, "signed_payload_present": False, "exchange_acknowledgement_present": False, "error_type": type(exc).__name__, "error_redacted": _redact_text(str(exc))[:500], "secret_values_returned": False}

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        client, init = _build_client()
        if client is None:
            return {"adapter_mode": self.adapter_mode, "status": "order_status_unavailable", "order_id_hash": hashlib.sha256(_text(order_id).encode("utf-8")).hexdigest() if _text(order_id) else "", "dependency_status": init.get("status"), "network_attempted": False, "secret_values_returned": False}
        try:
            response = client.get_order(order_id)
            return {"adapter_mode": self.adapter_mode, "status": "order_status_available", "order_id_hash": hashlib.sha256(_text(order_id).encode("utf-8")).hexdigest(), "network_attempted": True, **_normalize_response(response), "secret_values_returned": False}
        except Exception as exc:
            return {"adapter_mode": self.adapter_mode, "status": "order_status_unavailable", "order_id_hash": hashlib.sha256(_text(order_id).encode("utf-8")).hexdigest() if _text(order_id) else "", "error_type": type(exc).__name__, "error_redacted": _redact_text(str(exc))[:240], "network_attempted": True, "secret_values_returned": False}

    def get_open_orders(self) -> dict[str, Any]:
        client, init = _build_client()
        if client is None:
            return {"adapter_mode": self.adapter_mode, "status": "open_orders_unavailable", "dependency_status": init.get("status"), "network_attempted": False, "items": [], "secret_values_returned": False}
        runtime = _load_py_clob_client_runtime()
        try:
            response = client.get_orders(runtime["OpenOrderParams"]())
            normalized = _normalize_response(response)
            items = response if isinstance(response, list) else response.get("data", []) if isinstance(response, dict) else []
            return {"adapter_mode": self.adapter_mode, "status": "open_orders_available", "network_attempted": True, "items": _redact_data(items), **normalized, "secret_values_returned": False}
        except Exception as exc:
            return {"adapter_mode": self.adapter_mode, "status": "open_orders_unavailable", "error_type": type(exc).__name__, "error_redacted": _redact_text(str(exc))[:240], "network_attempted": True, "items": [], "secret_values_returned": False}

    def get_positions(self) -> dict[str, Any]:
        return {"adapter_mode": self.adapter_mode, "status": "positions_unavailable", "network_attempted": False, "items": [], "secret_values_returned": False}


def clob_adapter_status_to_csv(report: dict[str, Any] | None = None) -> str:
    report = report or build_clob_adapter_status()
    out = io.StringIO()
    fields = [
        "generated_at",
        "overall_status",
        "live_mode",
        "allow_real_network",
        "enable_submit",
        "enable_cancel",
        "kill_switch_active",
        "l2_credentials_present",
        "dependency_status",
        "preferred_family",
        "sdk_mapping_status",
        "sdk_probe_status",
        "real_submit_required_method",
        "real_cancel_required_method",
        "sdk_mapping_completed",
        "real_submit_implemented",
        "real_cancel_implemented",
        "real_live_smoke_guard_enabled",
        "network_attempted",
        "blockers",
        "warnings",
    ]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    dep = report.get("dependency", {})
    probe = report.get("sdk_method_probe", {})
    writer.writerow({
        "generated_at": report.get("generated_at", ""),
        "overall_status": report.get("overall_status", ""),
        "live_mode": report.get("config", {}).get("live_mode"),
        "allow_real_network": report.get("config", {}).get("allow_real_network"),
        "enable_submit": report.get("config", {}).get("enable_submit"),
        "enable_cancel": report.get("config", {}).get("enable_cancel"),
        "kill_switch_active": report.get("config", {}).get("kill_switch_active"),
        "l2_credentials_present": report.get("credentials", {}).get("l2_credentials_present"),
        "dependency_status": dep.get("status"),
        "preferred_family": dep.get("preferred_family"),
        "sdk_mapping_status": report.get("sdk_mapping_status"),
        "sdk_probe_status": probe.get("status"),
        "real_submit_required_method": report.get("real_submit_required_method"),
        "real_cancel_required_method": report.get("real_cancel_required_method"),
        "sdk_mapping_completed": report.get("sdk_mapping_completed"),
        "real_submit_implemented": report.get("real_submit_implemented"),
        "real_cancel_implemented": report.get("real_cancel_implemented"),
        "real_live_smoke_guard_enabled": report.get("real_live_smoke_test_guard", {}).get("enabled"),
        "network_attempted": report.get("network_attempted"),
        "blockers": " | ".join(str(x) for x in report.get("blockers", [])),
        "warnings": " | ".join(str(x) for x in report.get("warnings", [])),
    })
    return out.getvalue()
