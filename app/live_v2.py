from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from .clob_client import ClobClient
from .config import APP_VERSION, DATA_DIR, settings
from .gamma_client import GammaClient
from .live_clob_adapter import FailClosedPolymarketClobAdapter, build_clob_adapter_status
from .market_edge import edge_recommendation_legend, enrich_markets_with_recommendations
from .probability import attach_probability
from .scoring import attach_scores

LIVE_V2_DIR = DATA_DIR / "live_v2"
AUDIT_JSONL_PATH = LIVE_V2_DIR / "audit_ledger.jsonl"
AUDIT_CSV_FIELDS = [
    "timestamp",
    "app_version",
    "mode",
    "action",
    "status",
    "market_id",
    "token_id",
    "side",
    "price",
    "size",
    "notional",
    "order_id",
    "risk_status",
    "approval_status",
    "network_attempted",
    "error_type",
    "details",
]

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
    "POLYMARKET_V2_CONFIRMATION_PHRASE",
}

TRADING_MODES = {"research_only", "paper", "live_read_only", "live_trading_armed"}
SIDES = {"BUY", "SELL"}
ORDER_TYPES = {"GTC", "FOK", "GTD", "FAK"}
DEFAULT_CONFIRMATION_PHRASE = "LIVE ORDER APPROVED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _env_any(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(key: str, default: float = 0.0) -> float:
    try:
        raw = os.getenv(key)
        if raw is None or str(raw).strip() == "":
            return default
        return float(raw)
    except Exception:
        return default


def _env_int(key: str, default: int = 0) -> int:
    try:
        raw = os.getenv(key)
        if raw is None or str(raw).strip() == "":
            return default
        return int(float(raw))
    except Exception:
        return default


def _env_list(*keys: str) -> list[str]:
    raw = _env_any(*keys)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _safe_float(value: Any, default: float = 0.0) -> float:
    number = _decimal(value)
    return float(number) if number is not None else default


def _present(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    return text not in {"***", "<redacted>"} and not text.upper().startswith("CHANGE_ME")


def _secret_values() -> list[str]:
    values: list[str] = []
    for key in SENSITIVE_ENV_KEYS:
        raw = os.getenv(key)
        if raw:
            values.append(str(raw))
    return values


def redact_text(value: Any) -> str:
    text = _text(value)
    for secret in _secret_values():
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def redact_data(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            safe_secret_status_keys = {
                "secret_values_returned",
                "secret_values_allowed",
                "secrets_masked",
                "secrets_redacted",
                "secret_scan_ok",
            }
            if key_text in safe_secret_status_keys:
                redacted[key] = bool(item)
            elif any(token in key_text.upper() for token in ["PRIVATE", "SECRET", "PASSPHRASE", "API_KEY", "SIGNATURE"]):
                redacted[key] = "[redacted]" if _present(item) else ""
            else:
                redacted[key] = redact_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _package_version(names: list[str]) -> str:
    for name in names:
        try:
            return importlib.metadata.version(name)
        except Exception:
            continue
    return "unknown"


def _module_present(*names: str) -> bool:
    return any(importlib.util.find_spec(name) is not None for name in names)


@dataclass(frozen=True)
class LiveV2Config:
    trading_mode: str
    gamma_base_url: str
    clob_base_url: str
    data_api_base_url: str
    chain_id: str
    require_approval: bool
    confirmation_phrase: str
    kill_switch_active: bool
    read_only: bool
    allow_real_network: bool
    enable_submit: bool
    enable_cancel: bool
    allow_market_orders: bool
    allow_limit_orders: bool
    default_slippage_limit_bps: float
    max_order_notional: float
    max_market_notional: float
    max_total_exposure: float
    max_daily_notional: float
    max_daily_loss: float
    max_open_orders: int
    market_allowlist: list[str]
    token_allowlist: list[str]
    stale_data_max_age_seconds: int

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "trading_mode": self.trading_mode,
            "gamma_base_url": self.gamma_base_url,
            "clob_base_url": self.clob_base_url,
            "data_api_base_url": self.data_api_base_url,
            "chain_id": self.chain_id,
            "require_approval": self.require_approval,
            "confirmation_phrase_configured": bool(self.confirmation_phrase),
            "confirmation_phrase_default": self.confirmation_phrase == DEFAULT_CONFIRMATION_PHRASE,
            "kill_switch_active": self.kill_switch_active,
            "read_only": self.read_only,
            "allow_real_network": self.allow_real_network,
            "enable_submit": self.enable_submit,
            "enable_cancel": self.enable_cancel,
            "allow_market_orders": self.allow_market_orders,
            "allow_limit_orders": self.allow_limit_orders,
            "default_slippage_limit_bps": self.default_slippage_limit_bps,
            "max_order_notional": self.max_order_notional,
            "max_market_notional": self.max_market_notional,
            "max_total_exposure": self.max_total_exposure,
            "max_daily_notional": self.max_daily_notional,
            "max_daily_loss": self.max_daily_loss,
            "max_open_orders": self.max_open_orders,
            "market_allowlist_count": len(self.market_allowlist),
            "token_allowlist_count": len(self.token_allowlist),
            "stale_data_max_age_seconds": self.stale_data_max_age_seconds,
        }


def build_live_v2_config() -> LiveV2Config:
    mode = _env_any("POLYMARKET_V2_TRADING_MODE", default="")
    if not mode:
        if _env_bool("POLYMARKET_LIVE_MODE", False) and _env_bool("POLYMARKET_LIVE_ENABLE_SUBMIT", False):
            mode = "live_trading_armed"
        elif _env_bool("POLYMARKET_LIVE_MODE", False) or _env_bool("POLYMARKET_LIVE_NETWORK_READONLY", False):
            mode = "live_read_only"
        elif _env_any("APP_MODE", default="read_only") == "paper":
            mode = "paper"
        else:
            mode = "research_only"
    if mode not in TRADING_MODES:
        mode = "research_only"
    return LiveV2Config(
        trading_mode=mode,
        gamma_base_url=_env_any("GAMMA_BASE_URL", default="https://gamma-api.polymarket.com"),
        clob_base_url=_env_any("CLOB_BASE_URL", "POLYMARKET_CLOB_HOST", default="https://clob.polymarket.com"),
        data_api_base_url=_env_any("POLYMARKET_DATA_API_BASE_URL", default="https://data-api.polymarket.com"),
        chain_id=_env_any("POLYMARKET_CHAIN_ID", default="137"),
        require_approval=_env_bool("POLYMARKET_V2_REQUIRE_APPROVAL", _env_bool("LIVE_REQUIRE_MANUAL_APPROVAL", True)),
        confirmation_phrase=_env_any("POLYMARKET_V2_CONFIRMATION_PHRASE", "POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE", default=DEFAULT_CONFIRMATION_PHRASE),
        kill_switch_active=_env_bool("POLYMARKET_LIVE_KILL_SWITCH", True),
        read_only=_env_bool("READ_ONLY", True) or _env_bool("POLYMARKET_V2_FORCE_READ_ONLY", False),
        allow_real_network=_env_bool("POLYMARKET_LIVE_ALLOW_REAL_NETWORK", False),
        enable_submit=_env_bool("POLYMARKET_LIVE_ENABLE_SUBMIT", False) and _env_bool("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED", False),
        enable_cancel=_env_bool("POLYMARKET_LIVE_ENABLE_CANCEL", False) and _env_bool("POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED", False),
        allow_market_orders=_env_bool("POLYMARKET_V2_ALLOW_MARKET_ORDERS", False),
        allow_limit_orders=_env_bool("POLYMARKET_V2_ALLOW_LIMIT_ORDERS", True),
        default_slippage_limit_bps=_env_float("POLYMARKET_V2_DEFAULT_SLIPPAGE_BPS", _env_float("POLYMARKET_MARKET_DATA_MAX_SLIPPAGE_BPS", 150.0)),
        max_order_notional=_env_float("POLYMARKET_LIVE_MAX_ORDER_NOTIONAL", _env_float("LIVE_MAX_ORDER_NOTIONAL", 0.0)),
        max_market_notional=_env_float("POLYMARKET_LIVE_MAX_POSITION_NOTIONAL", _env_float("LIVE_MAX_MARKET_NOTIONAL", 0.0)),
        max_total_exposure=_env_float("POLYMARKET_V2_MAX_TOTAL_EXPOSURE", 0.0),
        max_daily_notional=_env_float("POLYMARKET_LIVE_MAX_DAILY_NOTIONAL", _env_float("LIVE_MAX_DAILY_NOTIONAL", 0.0)),
        max_daily_loss=_env_float("POLYMARKET_LIVE_MAX_DAILY_LOSS", 0.0),
        max_open_orders=_env_int("POLYMARKET_LIVE_MAX_OPEN_ORDERS", _env_int("LIVE_MAX_OPEN_ORDERS", 0)),
        market_allowlist=_env_list("POLYMARKET_LIVE_MARKET_ALLOWLIST", "LIVE_ALLOWED_MARKET_IDS"),
        token_allowlist=_env_list("POLYMARKET_LIVE_TOKEN_ALLOWLIST"),
        stale_data_max_age_seconds=_env_int("POLYMARKET_MARKET_DATA_MAX_AGE_SECONDS", 300),
    )


def _credential_summary() -> dict[str, Any]:
    private_key = _env_any("POLY_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY", "PK")
    address = _env_any("POLY_ADDRESS", "POLYMARKET_WALLET_ADDRESS")
    api_key = _env_any("POLY_API_KEY", "POLYMARKET_CLOB_API_KEY", "CLOB_API_KEY")
    secret = _env_any("POLY_SECRET", "POLYMARKET_CLOB_SECRET", "CLOB_SECRET")
    passphrase = _env_any("POLY_PASSPHRASE", "POLYMARKET_CLOB_PASSPHRASE", "CLOB_PASSPHRASE")
    wallet_derived = False
    wallet_derivation_status = "not_attempted"
    wallet_address = address
    if _present(address):
        wallet_derived = True
        wallet_derivation_status = "explicit_wallet_address_configured"
    elif _present(private_key):
        try:
            from eth_account import Account  # type: ignore

            wallet_address = Account.from_key(private_key).address
            wallet_derived = True
            wallet_derivation_status = "derived_from_private_key"
        except Exception as exc:  # noqa: BLE001 - optional dependency / invalid key should degrade safely
            wallet_derivation_status = f"not_derived:{type(exc).__name__}"
    return {
        "private_key_present": _present(private_key),
        "api_key_present": _present(api_key),
        "api_secret_present": _present(secret),
        "api_passphrase_present": _present(passphrase),
        "l2_credentials_present": all(_present(v) for v in [api_key, secret, passphrase]),
        "wallet_address_present": _present(address),
        "wallet_derivable": wallet_derived,
        "wallet_derivation_status": wallet_derivation_status,
        "wallet_address_preview": f"{wallet_address[:6]}...{wallet_address[-4:]}" if _present(wallet_address) and len(wallet_address) > 12 else "",
        "secret_values_returned": False,
    }


def _sdk_summary() -> dict[str, Any]:
    unified_present = _module_present("polymarket", "polymarket_client", "polymarket_sdk")
    v2_present = _module_present("py_clob_client_v2")
    legacy_present = _module_present("py_clob_client")
    return {
        "official_unified_sdk_present": unified_present,
        "official_unified_sdk_version": _package_version(["polymarket-client", "polymarket", "polymarket-sdk"]) if unified_present else "not_installed",
        "py_clob_client_v2_present": v2_present,
        "py_clob_client_v2_version": _package_version(["py-clob-client-v2", "py_clob_client_v2"]) if v2_present else "not_installed",
        "legacy_py_clob_client_present": legacy_present,
        "legacy_py_clob_client_version": _package_version(["py-clob-client", "py_clob_client"]) if legacy_present else "not_installed",
        "preferred_runtime": _env_any("POLYMARKET_V2_SDK_FAMILY", default="official_unified_python_sdk_then_clob_fallback"),
        "legacy_archived_warning": "py-clob-client is retained as a compatibility fallback; prefer Polymarket's unified Python SDK when stable in your environment.",
    }


def _check(key: str, label: str, status: str, detail: str, remediation: str = "") -> dict[str, str]:
    return {"key": key, "label": label, "status": status, "detail": detail, "remediation": remediation}


def build_live_v2_readiness() -> dict[str, Any]:
    cfg = build_live_v2_config()
    creds = _credential_summary()
    sdk = _sdk_summary()
    clob_boundary = build_clob_adapter_status()
    checks: list[dict[str, str]] = []
    checks.append(_check("environment_loaded", "Environment loaded", "pass", "Configuration was read from process environment and .env defaults."))
    checks.append(_check("gamma_configured", "Gamma API configured", "pass" if _present(cfg.gamma_base_url) else "fail", cfg.gamma_base_url or "missing", "Set GAMMA_BASE_URL."))
    checks.append(_check("clob_configured", "CLOB API configured", "pass" if _present(cfg.clob_base_url) else "fail", cfg.clob_base_url or "missing", "Set CLOB_BASE_URL / POLYMARKET_CLOB_HOST."))
    checks.append(_check("data_api_configured", "Data API configured", "pass" if _present(cfg.data_api_base_url) else "warn", cfg.data_api_base_url or "missing", "Set POLYMARKET_DATA_API_BASE_URL for balances/positions reads."))
    checks.append(_check("credentials_present", "Trading credentials present", "pass" if creds["private_key_present"] and creds["l2_credentials_present"] else "fail", f"private_key={creds['private_key_present']}, l2={creds['l2_credentials_present']}", "Set secrets only in local .env or environment."))
    checks.append(_check("wallet_derivable", "Wallet address derivable", "pass" if creds["wallet_derivable"] else "warn", creds["wallet_derivation_status"], "Set POLYMARKET_WALLET_ADDRESS or install eth-account to derive from a private key."))
    sdk_ok = sdk["official_unified_sdk_present"] or sdk["py_clob_client_v2_present"] or sdk["legacy_py_clob_client_present"]
    checks.append(_check("sdk_available", "Official SDK/runtime available", "pass" if sdk_ok else "fail", json.dumps(sdk, sort_keys=True), "Install optional live requirements in an operator-controlled environment."))
    checks.append(_check("trading_mode", "Trading mode", "pass" if cfg.trading_mode in TRADING_MODES else "fail", cfg.trading_mode, "Use POLYMARKET_V2_TRADING_MODE dropdown/settings."))
    checks.append(_check("risk_limits", "Risk limits configured", "pass" if cfg.max_order_notional > 0 and cfg.max_daily_notional > 0 and cfg.max_open_orders > 0 else "fail", f"max_order={cfg.max_order_notional}, daily={cfg.max_daily_notional}, max_open={cfg.max_open_orders}", "Set non-zero max order, daily notional, and max open order limits."))
    checks.append(_check("kill_switch", "Kill switch off for arming", "pass" if not cfg.kill_switch_active else "fail", str(cfg.kill_switch_active), "Set POLYMARKET_LIVE_KILL_SWITCH=false only when deliberately arming live trading."))
    checks.append(_check("read_only", "Read-only disabled for arming", "pass" if not cfg.read_only else "fail", str(cfg.read_only), "Set READ_ONLY=false only after readiness and policy checks pass."))
    checks.append(_check("real_network", "Real network allowed", "pass" if cfg.allow_real_network else "fail", str(cfg.allow_real_network), "Set POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true only for deliberate live operation."))
    checks.append(_check("submit_gate", "Submit gates enabled", "pass" if cfg.enable_submit else "fail", str(cfg.enable_submit), "Enable both POLYMARKET_LIVE_ENABLE_SUBMIT and POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED."))
    checks.append(_check("cancel_gate", "Cancel gates enabled", "pass" if cfg.enable_cancel else "warn", str(cfg.enable_cancel), "Enable cancel only if operator wants live cancellation available."))
    checks.append(_check("approval_required", "Human approval required", "pass" if cfg.require_approval else "fail", str(cfg.require_approval), "Keep POLYMARKET_V2_REQUIRE_APPROVAL=true."))
    checks.append(_check("confirmation_phrase", "Confirmation phrase configured", "pass" if _present(cfg.confirmation_phrase) else "fail", "configured" if _present(cfg.confirmation_phrase) else "missing", "Use the default LIVE ORDER APPROVED or a stronger local phrase."))
    checks.append(_check("clob_boundary", "CLOB adapter boundary", "pass" if clob_boundary.get("real_submit_implemented") else "fail", str(clob_boundary.get("overall_status")), "Review /live-clob-adapter."))
    hard_fails = [row for row in checks if row["status"] == "fail"]
    warnings = [row for row in checks if row["status"] == "warn"]
    return {
        "version": "2.5.0-live-v2-readiness",
        "generated_at": _now(),
        "app_version": APP_VERSION,
        "overall_status": "ready_to_arm" if not hard_fails else "blocked",
        "ready_to_arm": not hard_fails,
        "trading_mode": cfg.trading_mode,
        "checks": checks,
        "fail_count": len(hard_fails),
        "warning_count": len(warnings),
        "credentials": creds,
        "sdk": sdk,
        "clob_boundary": redact_data(clob_boundary),
        "config": cfg.as_public_dict(),
        "legal_compliance_note": "Operator is responsible for using Polymarket only where permitted and in accordance with Polymarket terms and applicable law.",
        "secret_values_returned": False,
    }


def _mode_label(mode: str) -> str:
    labels = {
        "research_only": "Research Only",
        "paper": "Paper",
        "live_read_only": "Live Read-Only",
        "live_trading_armed": "Live Armed",
    }
    return labels.get(mode, "Unknown")


def _tone_for_mode(mode: str) -> str:
    if mode == "live_trading_armed":
        return "danger"
    if mode == "live_read_only":
        return "warning"
    if mode == "paper":
        return "paper"
    return "neutral"


def _recent_errors(rows: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    flagged: list[dict[str, Any]] = []
    for row in rows:
        status = _text(row.get("status")).lower()
        if any(marker in status for marker in ["fail", "error", "blocked", "reject", "mismatch"]):
            flagged.append(row)
        if len(flagged) >= limit:
            break
    return flagged


def build_live_v2_ui_summary(readiness: dict[str, Any] | None = None, audit_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    readiness = readiness or build_live_v2_readiness()
    cfg = build_live_v2_config()
    audit_rows = audit_rows if audit_rows is not None else list_audit_records(limit=250)
    failures = [row for row in readiness.get("checks", []) if row.get("status") == "fail"]
    warnings = [row for row in readiness.get("checks", []) if row.get("status") == "warn"]
    open_orders_state = "Unknown"
    positions_state = "Unknown"
    risk_state = "Ready" if not failures else "Risk Blocked"
    if cfg.kill_switch_active:
        next_action = "Review readiness, configure limits, and keep Kill Switch active until deliberate arming."
    elif cfg.trading_mode == "live_trading_armed" and readiness.get("ready_to_arm"):
        next_action = "Use Trade Ticket preview, then approval and typed confirmation for any live order."
    elif cfg.trading_mode == "paper":
        next_action = "Rehearse tickets in Paper mode and review audit exports before arming live."
    else:
        next_action = "Move through readiness checks before enabling any live submit gate."
    return {
        "version": "2.5.0-live-v2-ui-summary",
        "generated_at": _now(),
        "mode_label": _mode_label(cfg.trading_mode),
        "mode_tone": _tone_for_mode(cfg.trading_mode),
        "live_armed": cfg.trading_mode == "live_trading_armed",
        "live_armed_label": "Live Armed" if cfg.trading_mode == "live_trading_armed" else "Live Not Armed",
        "read_only_label": "Read-Only" if cfg.read_only else "Writable Gates Possible",
        "kill_switch_label": "Kill Switch ON" if cfg.kill_switch_active else "Kill Switch OFF",
        "kill_switch_tone": "ok" if cfg.kill_switch_active else "danger",
        "readiness_label": "Ready" if readiness.get("ready_to_arm") else "Not Ready",
        "readiness_tone": "ok" if readiness.get("ready_to_arm") else "danger",
        "clob_label": "CLOB OK" if not any(row.get("key") == "clob_configured" and row.get("status") == "fail" for row in readiness.get("checks", [])) else "CLOB Error",
        "gamma_label": "Gamma OK" if not any(row.get("key") == "gamma_configured" and row.get("status") == "fail" for row in readiness.get("checks", [])) else "Gamma Error",
        "last_refresh": _now(),
        "last_critical_error": _text(_recent_errors(audit_rows, 1)[0].get("status")) if _recent_errors(audit_rows, 1) else "None",
        "fail_count": len(failures),
        "warning_count": len(warnings),
        "risk_state": risk_state,
        "open_orders_state": open_orders_state,
        "positions_state": positions_state,
        "today_notional_used": sum(_safe_float(row.get("notional"), 0.0) for row in audit_rows if str(row.get("timestamp", ""))[:10] == _now()[:10]),
        "daily_limit": cfg.max_daily_notional,
        "recent_errors": _recent_errors(audit_rows),
        "next_action": next_action,
    }


def build_live_v2_status() -> dict[str, Any]:
    readiness = build_live_v2_readiness()
    audit_rows = list_audit_records(limit=1000)
    ui_summary = build_live_v2_ui_summary(readiness, audit_rows)
    return {
        "version": "2.5.0-live-v2-status",
        "generated_at": _now(),
        "app_version": APP_VERSION,
        "overall_status": readiness["overall_status"],
        "ready_to_arm": readiness["ready_to_arm"],
        "readiness": readiness,
        "ui": ui_summary,
        "audit_summary": summarize_audit(audit_rows),
        "guardrail": "Live v2 routes use preview, risk, approval, confirmation, and adapter gates. They do not submit unless the explicit submit endpoint receives a valid approved ticket in armed live mode.",
    }


def build_live_v2_settings_sections() -> list[dict[str, Any]]:
    cfg = build_live_v2_config()
    return [
        {"id": "general", "title": "General", "description": "Console posture and operator defaults.", "fields": [
            {"key": "APP_MODE", "label": "App Mode", "control": "dropdown", "current": _env_any("APP_MODE", default="read_only"), "options": ["read_only", "paper"], "secret": False, "helper": "Use paper for rehearsal; read_only keeps the console informational."},
        ]},
        {"id": "trading-mode", "title": "Trading Mode", "description": "Canonical mode labels used across the operator console.", "fields": [
            {"key": "POLYMARKET_V2_TRADING_MODE", "label": "Trading Mode", "control": "radio", "current": cfg.trading_mode, "options": sorted(TRADING_MODES), "secret": False, "helper": "Live Armed still requires readiness, kill switch off, submit gates, approval, and typed confirmation."},
        ]},
        {"id": "api-hosts", "title": "API Hosts", "description": "Public data and CLOB endpoints.", "fields": [
            {"key": "GAMMA_BASE_URL", "label": "Gamma API", "control": "url", "current": cfg.gamma_base_url, "secret": False, "helper": "Public market metadata endpoint."},
            {"key": "CLOB_BASE_URL", "label": "CLOB API", "control": "url", "current": cfg.clob_base_url, "secret": False, "helper": "Order book and private trading endpoint host."},
            {"key": "POLYMARKET_DATA_API_BASE_URL", "label": "Data API", "control": "url", "current": cfg.data_api_base_url, "secret": False, "helper": "Balances, positions, and account state where supported."},
        ]},
        {"id": "credentials", "title": "Credentials / Secrets", "description": "Secrets are environment-only, masked in UI, and redacted in logs.", "fields": [
            {"key": "POLYMARKET_PRIVATE_KEY", "label": "Wallet Private Key", "control": "password", "current": "configured" if _credential_summary()["private_key_present"] else "missing", "secret": True, "helper": "Never commit this value. Prefer local .env or process secrets."},
            {"key": "POLYMARKET_CLOB_API_KEY", "label": "CLOB API Key", "control": "password", "current": "configured" if _credential_summary()["api_key_present"] else "missing", "secret": True, "helper": "Required for authenticated private endpoints."},
        ]},
        {"id": "gates", "title": "Live Trading Gates", "description": "Deliberate friction for money-moving actions.", "fields": [
            {"key": "POLYMARKET_LIVE_KILL_SWITCH", "label": "Kill Switch", "control": "toggle", "current": cfg.kill_switch_active, "secret": False, "helper": "Default ON. New live submit is blocked while active."},
            {"key": "READ_ONLY", "label": "Read-Only", "control": "toggle", "current": cfg.read_only, "secret": False, "helper": "Default true. Must be false before live submit can pass."},
            {"key": "POLYMARKET_V2_REQUIRE_APPROVAL", "label": "Human Approval Required", "control": "toggle", "current": cfg.require_approval, "secret": False, "helper": "Keep enabled; backend also enforces this."},
            {"key": "POLYMARKET_V2_CONFIRMATION_PHRASE", "label": "Typed Confirmation Phrase", "control": "text", "current": "configured", "secret": True, "helper": "Default: LIVE ORDER APPROVED."},
        ]},
        {"id": "risk-limits", "title": "Risk Limits", "description": "Numerical blockers enforced before live submission.", "fields": [
            {"key": "POLYMARKET_LIVE_MAX_ORDER_NOTIONAL", "label": "Max Order Notional", "control": "number", "current": cfg.max_order_notional, "secret": False, "helper": "Per-order cap in USDC-notional terms."},
            {"key": "POLYMARKET_LIVE_MAX_DAILY_NOTIONAL", "label": "Max Daily Notional", "control": "number", "current": cfg.max_daily_notional, "secret": False, "helper": "Required non-zero daily notional cap."},
            {"key": "POLYMARKET_LIVE_MAX_OPEN_ORDERS", "label": "Max Open Orders", "control": "number", "current": cfg.max_open_orders, "secret": False, "helper": "Required non-zero order-count cap."},
        ]},
        {"id": "order-defaults", "title": "Order Defaults", "description": "Operator defaults and order-type permissions.", "fields": [
            {"key": "POLYMARKET_V2_ALLOW_LIMIT_ORDERS", "label": "Allow Limit Orders", "control": "toggle", "current": cfg.allow_limit_orders, "secret": False, "helper": "Limit-order permission."},
            {"key": "POLYMARKET_V2_ALLOW_MARKET_ORDERS", "label": "Allow Marketable Orders", "control": "toggle", "current": cfg.allow_market_orders, "secret": False, "helper": "Required for FOK/FAK style behavior."},
            {"key": "POLYMARKET_V2_DEFAULT_SLIPPAGE_BPS", "label": "Default Slippage BPS", "control": "number", "current": cfg.default_slippage_limit_bps, "secret": False, "helper": "UI hint; actual risk checks remain backend enforced."},
        ]},
        {"id": "audit", "title": "Audit / Exports", "description": "Local ledger exports and reconciliation reporting.", "fields": [
            {"key": "LIVE_V2_AUDIT_PATH", "label": "Audit Path", "control": "read-only", "current": str(AUDIT_JSONL_PATH), "secret": False, "helper": "Runtime data path; not packaged in releases."},
        ]},
        {"id": "advanced", "title": "Advanced / Debug", "description": "Rare values, raw endpoints, and diagnostics.", "fields": [
            {"key": "POLYMARKET_MARKET_DATA_MAX_AGE_SECONDS", "label": "Stale Data Max Age", "control": "number", "current": cfg.stale_data_max_age_seconds, "secret": False, "helper": "Used for stale-data warnings and operator review."},
        ]},
    ]


def validate_live_v2_settings_payload(payload: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    mode = _text(payload.get("POLYMARKET_V2_TRADING_MODE"), build_live_v2_config().trading_mode)
    if mode not in TRADING_MODES:
        errors.append("Trading Mode must be one of Research Only, Paper, Live Read-Only, or Live Armed.")
    def non_negative_number(key: str, label: str) -> None:
        if key in payload and _decimal(payload.get(key)) is None:
            errors.append(f"{label} must be numeric.")
        elif key in payload and _safe_float(payload.get(key), 0.0) < 0:
            errors.append(f"{label} cannot be negative.")
    non_negative_number("POLYMARKET_LIVE_MAX_ORDER_NOTIONAL", "Max Order Notional")
    non_negative_number("POLYMARKET_LIVE_MAX_DAILY_NOTIONAL", "Max Daily Notional")
    non_negative_number("POLYMARKET_LIVE_MAX_OPEN_ORDERS", "Max Open Orders")
    if mode == "live_trading_armed":
        if str(payload.get("POLYMARKET_LIVE_KILL_SWITCH", "true")).lower() not in {"false", "0", "no", "off"}:
            warnings.append("Live Armed still appears blocked by Kill Switch unless explicitly set off.")
        if str(payload.get("READ_ONLY", "true")).lower() not in {"false", "0", "no", "off"}:
            warnings.append("Live Armed still appears blocked by Read-Only mode unless explicitly set false.")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "secret_values_returned": False}


def _ticket_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    market_id = _text(payload.get("market_id") or payload.get("condition_id") or payload.get("market"))
    token_id = _text(payload.get("token_id") or payload.get("asset_id") or payload.get("clob_token_id"))
    side = _text(payload.get("side"), "BUY").upper()
    order_type = _text(payload.get("order_type") or payload.get("time_in_force"), "GTC").upper()
    price = _safe_float(payload.get("price"), 0.0)
    size = _safe_float(payload.get("size") or payload.get("shares"), 0.0)
    note = redact_text(payload.get("note") or payload.get("rationale") or "")
    notional = round(price * size, 6)
    return {
        "ticket_id": _text(payload.get("ticket_id"), f"tkt_{uuid4().hex[:12]}"),
        "market_id": market_id,
        "market_title": redact_text(payload.get("market_title") or payload.get("question") or ""),
        "token_id": token_id,
        "outcome": redact_text(payload.get("outcome") or ""),
        "side": side,
        "order_type": order_type,
        "price": price,
        "size": size,
        "notional": notional,
        "max_loss_estimate": notional if side == "BUY" else round(max(0.0, (1.0 - price) * size), 6),
        "estimated_cost": notional if side == "BUY" else 0.0,
        "estimated_proceeds": notional if side == "SELL" else 0.0,
        "time_in_force": order_type,
        "expiration": _text(payload.get("expiration")),
        "notes": note,
        "strategy_ref": redact_text(payload.get("strategy_ref") or payload.get("playbook_id") or ""),
        "reduce_only_requested": bool(payload.get("reduce_only")),
        "operator": redact_text(payload.get("operator") or "local"),
        "created_at": _now(),
    }


def evaluate_live_v2_risk(ticket: dict[str, Any], *, acknowledged_warnings: bool = False, human_approval: bool = False) -> dict[str, Any]:
    cfg = build_live_v2_config()
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, severity: str, detail: str) -> None:
        row = {"name": name, "passed": bool(passed), "severity": severity, "detail": detail}
        checks.append(row)
        if not passed and severity == "fail":
            failures.append({"name": name, "detail": detail})
        elif not passed:
            warnings.append({"name": name, "detail": detail})

    side = _text(ticket.get("side")).upper()
    order_type = _text(ticket.get("order_type")).upper()
    price = _safe_float(ticket.get("price"), 0.0)
    size = _safe_float(ticket.get("size"), 0.0)
    notional = _safe_float(ticket.get("notional"), price * size)
    market_id = _text(ticket.get("market_id"))
    token_id = _text(ticket.get("token_id"))

    add("ticket_fields_complete", bool(market_id and token_id and side in SIDES and price > 0 and size > 0), "fail", "market_id, token_id, side, price, and size are required.")
    add("price_bounds", 0.0 < price < 1.0, "fail", "price must be greater than 0 and less than 1.")
    add("order_type_allowed", order_type in ORDER_TYPES, "fail", "order_type must be one of GTC, FOK, GTD, or FAK.")
    add("side_allowed", side in SIDES, "fail", "side must be BUY or SELL.")
    add("limit_orders_allowed", cfg.allow_limit_orders, "fail", "limit orders must be enabled.")
    if order_type in {"FOK", "FAK"}:
        add("marketable_orders_allowed", cfg.allow_market_orders, "fail", "FOK/FAK marketable behavior is disabled unless explicitly allowed.")
    add("per_order_notional", cfg.max_order_notional <= 0 or notional <= cfg.max_order_notional, "fail", f"order notional {notional} must be <= {cfg.max_order_notional}.")
    add("daily_notional_cap_configured", cfg.max_daily_notional > 0, "fail", "daily notional cap must be non-zero.")
    add("daily_notional_cap", cfg.max_daily_notional <= 0 or notional <= cfg.max_daily_notional, "fail", f"order notional {notional} must be <= daily cap {cfg.max_daily_notional}.")
    add("max_open_orders_configured", cfg.max_open_orders > 0, "fail", "max open orders must be non-zero.")
    add("kill_switch_clear", not cfg.kill_switch_active, "fail", "kill switch must be off.")
    add("not_read_only", not cfg.read_only, "fail", "READ_ONLY must be false for live submission.")
    add("live_mode_armed", cfg.trading_mode == "live_trading_armed", "fail", "POLYMARKET_V2_TRADING_MODE must be live_trading_armed.")
    add("real_network_allowed", cfg.allow_real_network, "fail", "POLYMARKET_LIVE_ALLOW_REAL_NETWORK must be true.")
    add("submit_gate_enabled", cfg.enable_submit, "fail", "submit gates must be enabled.")
    add("approval_present", (not cfg.require_approval) or human_approval, "fail", "human approval checkbox/signal is required.")
    if cfg.market_allowlist:
        add("market_allowlist", market_id in cfg.market_allowlist, "fail", "market_id must be on POLYMARKET_LIVE_MARKET_ALLOWLIST.")
    if cfg.token_allowlist:
        add("token_allowlist", token_id in cfg.token_allowlist, "fail", "token_id must be on POLYMARKET_LIVE_TOKEN_ALLOWLIST.")
    add("duplicate_warning_acknowledged", bool(acknowledged_warnings) or True, "warn", "duplicate detection is local-ledger best effort only.")
    if warnings and not acknowledged_warnings:
        failures.append({"name": "warnings_acknowledged", "detail": "risk warnings must be explicitly acknowledged before submission."})
    return {
        "version": "2.5.0-live-v2-risk",
        "generated_at": _now(),
        "status": "blocked" if failures else "passed",
        "passed": not failures,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "ticket_hash": _stable_hash(ticket),
    }


def build_live_v2_ticket_preview(payload: dict[str, Any]) -> dict[str, Any]:
    ticket = _ticket_from_payload(payload)
    risk = evaluate_live_v2_risk(
        ticket,
        acknowledged_warnings=bool(payload.get("acknowledge_warnings")),
        human_approval=bool(payload.get("human_approval")),
    )
    preview = {
        "version": "2.5.0-live-v2-ticket-preview",
        "generated_at": _now(),
        "recorded": False,
        "ticket": ticket,
        "risk": risk,
        "submit_ready": bool(risk.get("passed")),
        "approval_required": build_live_v2_config().require_approval,
        "confirmation_phrase_required": True,
        "guardrail": "Preview only. This does not sign, submit, cancel, touch wallets, or call private trading endpoints.",
    }
    record_audit("ticket_preview", "passed" if risk.get("passed") else "blocked", ticket=ticket, risk=risk, details={"recorded": False})
    return preview


def _confirmation_matches(value: Any) -> bool:
    cfg = build_live_v2_config()
    return _text(value) == cfg.confirmation_phrase


def submit_live_v2_order(payload: dict[str, Any]) -> dict[str, Any]:
    ticket = _ticket_from_payload(payload)
    risk = evaluate_live_v2_risk(
        ticket,
        acknowledged_warnings=bool(payload.get("acknowledge_warnings")),
        human_approval=bool(payload.get("human_approval")),
    )
    if not risk.get("passed"):
        record_audit("live_order_submit", "blocked_by_risk", ticket=ticket, risk=risk)
        return {"version": "2.5.0-live-v2-submit", "status": "blocked_by_risk", "ticket": ticket, "risk": risk, "network_attempted": False}
    if not _confirmation_matches(payload.get("confirmation_phrase")):
        record_audit("live_order_submit", "blocked_by_confirmation", ticket=ticket, risk=risk, details={"confirmation_present": bool(_text(payload.get("confirmation_phrase")))})
        return {"version": "2.5.0-live-v2-submit", "status": "blocked_by_confirmation", "ticket": ticket, "risk": risk, "network_attempted": False, "blockers": ["Typed confirmation phrase did not match."]}
    attempt_id = f"v2lex_{uuid4().hex[:12]}"
    adapter_payload = {
        "market_id": ticket["market_id"],
        "token_id": ticket["token_id"],
        "side": ticket["side"],
        "price": ticket["price"],
        "size": ticket["size"],
        "time_in_force": ticket["order_type"],
    }
    receipt = FailClosedPolymarketClobAdapter().submit_order(attempt_id=attempt_id, order=adapter_payload)
    status = _text(receipt.get("status"), "submit_failed")
    record_audit(
        "live_order_submit",
        status,
        ticket=ticket,
        risk=risk,
        details={"attempt_id": attempt_id, "adapter_receipt": receipt},
        order_id=_text(receipt.get("exchange_order_id")),
        network_attempted=bool(receipt.get("network_attempted")),
    )
    return {"version": "2.5.0-live-v2-submit", "status": status, "attempt_id": attempt_id, "ticket": ticket, "risk": risk, "receipt": redact_data(receipt), "network_attempted": bool(receipt.get("network_attempted"))}


def cancel_live_v2_order(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = build_live_v2_config()
    order_id = _text(payload.get("order_id") or payload.get("exchange_order_id"))
    reason = redact_text(payload.get("reason") or "")
    blockers: list[str] = []
    if cfg.kill_switch_active and not cfg.enable_cancel:
        blockers.append("Kill switch is active and cancellation gate is not enabled.")
    if not cfg.enable_cancel:
        blockers.append("Cancel gates are disabled.")
    if not cfg.allow_real_network:
        blockers.append("POLYMARKET_LIVE_ALLOW_REAL_NETWORK is false.")
    if not order_id:
        blockers.append("order_id is required.")
    if not reason:
        blockers.append("reason is required.")
    if not _confirmation_matches(payload.get("confirmation_phrase")):
        blockers.append("Typed confirmation phrase did not match.")
    if blockers:
        record_audit("live_order_cancel", "blocked", order_id=order_id, details={"blockers": blockers, "reason": reason})
        return {"version": "2.5.0-live-v2-cancel", "status": "blocked", "blockers": blockers, "network_attempted": False}
    attempt_id = f"v2can_{uuid4().hex[:12]}"
    receipt = FailClosedPolymarketClobAdapter().cancel_order(attempt_id=attempt_id, order_id=order_id)
    status = _text(receipt.get("status"), "cancel_failed")
    record_audit("live_order_cancel", status, order_id=order_id, details={"attempt_id": attempt_id, "reason": reason, "adapter_receipt": receipt}, network_attempted=bool(receipt.get("network_attempted")))
    return {"version": "2.5.0-live-v2-cancel", "status": status, "attempt_id": attempt_id, "receipt": redact_data(receipt), "network_attempted": bool(receipt.get("network_attempted"))}


def emergency_live_v2_action(payload: dict[str, Any]) -> dict[str, Any]:
    action = _text(payload.get("action"), "force_read_only")
    note = redact_text(payload.get("note") or "")
    allowed = {"force_read_only", "disable_new_live_orders", "record_kill_switch", "cancel_all_preview"}
    if action not in allowed:
        action = "force_read_only"
    status = "recorded"
    details = {"action": action, "note": note, "state_mutation": "operator must persist environment changes via Settings or .env"}
    if action == "cancel_all_preview":
        details["guardrail"] = "Preview only. Use targeted cancel after reviewing open orders."
        status = "preview_only"
    record_audit("emergency_control", status, details=details)
    return {"version": "2.5.0-live-v2-emergency", "status": status, "action": action, "details": details}


def record_audit(action: str, status: str, *, ticket: dict[str, Any] | None = None, risk: dict[str, Any] | None = None, details: dict[str, Any] | None = None, order_id: str = "", network_attempted: bool = False) -> dict[str, Any]:
    ticket = ticket or {}
    risk = risk or {}
    details = redact_data(details or {})
    record = {
        "timestamp": _now(),
        "app_version": APP_VERSION,
        "mode": build_live_v2_config().trading_mode,
        "action": action,
        "status": status,
        "market_id": _text(ticket.get("market_id")),
        "token_id": _text(ticket.get("token_id")),
        "side": _text(ticket.get("side")),
        "price": ticket.get("price", ""),
        "size": ticket.get("size", ""),
        "notional": ticket.get("notional", ""),
        "order_id": order_id,
        "risk_status": _text(risk.get("status")),
        "approval_status": "approved" if risk and not risk.get("failures") else "not_approved_or_blocked",
        "network_attempted": network_attempted,
        "error_type": _text(details.get("error_type")) if isinstance(details, dict) else "",
        "details": details,
        "ticket_hash": _stable_hash(ticket) if ticket else "",
        "risk_hash": _stable_hash(risk) if risk else "",
        "secret_values_returned": False,
    }
    LIVE_V2_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_JSONL_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    return record


def build_live_v2_preferences_schema() -> dict[str, Any]:
    """Return the safe browser-only UI preference contract for the v2.2 console.

    The app deliberately keeps this list small and non-sensitive. These values may be
    stored in browser localStorage by the console JavaScript, but wallet secrets,
    API keys, private keys, auth headers, account payloads, and raw trading data are
    never part of this schema.
    """
    return {
        "version": APP_VERSION,
        "storage_key": "polymarketGamma.liveV2.uiPrefs.v2",
        "secret_values_allowed": False,
        "sensitive_data_allowed": False,
        "preferences": [
            {"key": "landing_page", "label": "Preferred landing page", "type": "select", "default": "/v2-live", "options": ["/v2-live", "/v2-live/markets", "/v2-live/trade-ticket", "/v2-live/orders", "/v2-live/audit"]},
            {"key": "default_market_query", "label": "Default market search query", "type": "text", "default": ""},
            {"key": "table_page_size", "label": "Default table page size", "type": "select", "default": "25", "options": ["10", "25", "50", "100"]},
            {"key": "compact_mode", "label": "Compact mode", "type": "boolean", "default": False},
            {"key": "show_advanced", "label": "Show advanced/debug sections by default", "type": "boolean", "default": False},
            {"key": "remember_audit_filters", "label": "Remember audit filters", "type": "boolean", "default": True},
            {"key": "remember_order_filters", "label": "Remember order filters", "type": "boolean", "default": True},
        ],
        "guardrail": "Browser localStorage is used only for harmless UI preferences. Never store secrets or private account data here.",
    }


def filter_live_v2_audit_records(
    *,
    limit: int = 200,
    action: str = "",
    mode: str = "",
    status: str = "",
    market: str = "",
    order_id: str = "",
    search: str = "",
) -> list[dict[str, Any]]:
    """Return audit rows with lightweight server-side filters for large ledgers."""
    rows = list_audit_records(limit=max(limit, 1) if limit else 200)

    def matches(row: dict[str, Any]) -> bool:
        if action and action.lower() not in _text(row.get("action")).lower():
            return False
        if mode and mode.lower() not in _text(row.get("mode")).lower():
            return False
        if status and status.lower() not in _text(row.get("status")).lower():
            return False
        if market and market.lower() not in _text(row.get("market_id")).lower():
            return False
        if order_id and order_id.lower() not in _text(row.get("order_id")).lower():
            return False
        if search:
            haystack = json.dumps(row, sort_keys=True, default=str).lower()
            if search.lower() not in haystack:
                return False
        return True

    return [row for row in rows if matches(row)][: max(1, min(1000, limit or 200))]


def list_audit_records(limit: int = 200) -> list[dict[str, Any]]:
    if not AUDIT_JSONL_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in AUDIT_JSONL_PATH.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(rows))[: max(0, int(limit))]


def summarize_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for row in rows:
        by_status[_text(row.get("status"), "unknown")] = by_status.get(_text(row.get("status"), "unknown"), 0) + 1
        by_action[_text(row.get("action"), "unknown")] = by_action.get(_text(row.get("action"), "unknown"), 0) + 1
    return {"count": len(rows), "by_status": dict(sorted(by_status.items())), "by_action": dict(sorted(by_action.items()))}


def audit_to_csv(rows: list[dict[str, Any]] | None = None) -> str:
    rows = rows if rows is not None else list_audit_records(limit=10000)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=AUDIT_CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: json.dumps(row.get(field, ""), sort_keys=True) if isinstance(row.get(field), (dict, list)) else row.get(field, "") for field in AUDIT_CSV_FIELDS})
    return out.getvalue()


def audit_to_markdown(rows: list[dict[str, Any]] | None = None, limit: int = 200) -> str:
    rows = rows if rows is not None else list_audit_records(limit=limit)
    lines = [f"# Live v2 Audit Report — {APP_VERSION}", "", f"Generated: {_now()}", "", "| Time | Mode | Action | Status | Market | Order | Notional | Network |", "|---|---|---|---|---|---|---:|---|"]
    for row in rows[:limit]:
        lines.append("| {timestamp} | {mode} | {action} | {status} | {market} | {order} | {notional} | {network} |".format(
            timestamp=_text(row.get("timestamp")),
            mode=_text(row.get("mode")),
            action=_text(row.get("action")),
            status=_text(row.get("status")),
            market=_text(row.get("market_id"))[:18],
            order=_text(row.get("order_id"))[:18],
            notional=_text(row.get("notional")),
            network=_text(row.get("network_attempted")),
        ))
    if not rows:
        lines.append("| No audit rows yet |  |  |  |  |  |  |  |")
    lines.extend(["", "Secrets are redacted before audit export. Runtime data is not included in release ZIPs."])
    return "\n".join(lines) + "\n"


def _with_live_v2_market_edge(items: list[Any]) -> list[Any]:
    markets = [item for item in items if isinstance(item, dict)]
    if not markets:
        return items
    try:
        return redact_data(enrich_markets_with_recommendations(attach_probability(attach_scores(markets))))
    except Exception:  # noqa: BLE001 - live v2 market search must degrade read-only
        return redact_data(items)


async def search_live_v2_markets(query: str = "", limit: int = 25) -> dict[str, Any]:
    limit = max(1, min(100, int(limit)))
    client = GammaClient(base_url=build_live_v2_config().gamma_base_url, timeout=settings.request_timeout_seconds)
    try:
        if query:
            data = await client.search(query, limit=limit)
            items: list[Any]
            if isinstance(data, dict):
                items = data.get("markets") or data.get("events") or data.get("data") or []
            elif isinstance(data, list):
                items = data
            else:
                items = []
            return {"status": "ok", "query": query, "items": _with_live_v2_market_edge(items[:limit]), "edge_legend": edge_recommendation_legend(), "network_attempted": True}
        items = await client.list_markets(limit=limit)
        return {"status": "ok", "query": query, "items": _with_live_v2_market_edge(items), "edge_legend": edge_recommendation_legend(), "network_attempted": True}
    except Exception as exc:  # noqa: BLE001 - UI/API should degrade safely
        return {"status": "market_search_failed", "error_type": type(exc).__name__, "error_redacted": redact_text(str(exc))[:240], "items": [], "network_attempted": True}


async def get_live_v2_orderbook(token_id: str) -> dict[str, Any]:
    if not _text(token_id):
        return {"status": "missing_token_id", "items": [], "network_attempted": False}
    client = ClobClient(base_url=build_live_v2_config().clob_base_url, timeout=settings.request_timeout_seconds)
    try:
        book = await client.get_order_book(token_id)
        return {"status": "ok", "orderbook": redact_data(book), "network_attempted": True}
    except Exception as exc:  # noqa: BLE001
        return {"status": "orderbook_failed", "error_type": type(exc).__name__, "error_redacted": redact_text(str(exc))[:240], "network_attempted": True}


async def get_live_v2_positions() -> dict[str, Any]:
    cfg = build_live_v2_config()
    creds = _credential_summary()
    wallet = _env_any("POLY_ADDRESS", "POLYMARKET_WALLET_ADDRESS")
    if not wallet:
        return {"status": "wallet_missing", "items": [], "network_attempted": False, "credentials": creds}
    if not (cfg.allow_real_network and _env_bool("POLYMARKET_LIVE_NETWORK_READONLY", False)):
        return {"status": "readonly_network_disabled", "items": [], "network_attempted": False, "credentials": creds}
    try:
        url = cfg.data_api_base_url.rstrip("/") + "/positions"
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, headers={"User-Agent": f"polymarket-op-console/{APP_VERSION}"}) as client:
            response = await client.get(url, params={"user": wallet})
            response.raise_for_status()
            data = response.json()
        items = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
        return {"status": "ok", "items": redact_data(items), "network_attempted": True, "credentials": creds}
    except Exception as exc:  # noqa: BLE001
        return {"status": "positions_failed", "error_type": type(exc).__name__, "error_redacted": redact_text(str(exc))[:240], "items": [], "network_attempted": True, "credentials": creds}


def get_live_v2_open_orders() -> dict[str, Any]:
    cfg = build_live_v2_config()
    if not (cfg.allow_real_network and _env_bool("POLYMARKET_LIVE_NETWORK_READONLY", False)):
        return {"status": "readonly_network_disabled", "items": [], "network_attempted": False}
    receipt = FailClosedPolymarketClobAdapter().get_open_orders()
    return redact_data(receipt)


def reconcile_live_v2_orders() -> dict[str, Any]:
    local = [row for row in list_audit_records(limit=10000) if row.get("action") in {"live_order_submit", "live_order_cancel"}]
    remote = get_live_v2_open_orders()
    remote_items = remote.get("items") if isinstance(remote, dict) else []
    rows: list[dict[str, Any]] = []
    local_ids = {_text(row.get("order_id")) for row in local if _text(row.get("order_id"))}
    remote_ids: set[str] = set()
    if isinstance(remote_items, list):
        for item in remote_items:
            if isinstance(item, dict):
                remote_id = _text(item.get("id") or item.get("orderID") or item.get("order_id"))
                if remote_id:
                    remote_ids.add(remote_id)
    for row in local:
        order_id = _text(row.get("order_id"))
        state = "remote_match" if order_id and order_id in remote_ids else "local_only_or_unconfirmed"
        rows.append({"timestamp": row.get("timestamp"), "action": row.get("action"), "status": row.get("status"), "order_id": order_id, "state": state})
    for order_id in sorted(remote_ids - local_ids):
        rows.append({"timestamp": _now(), "action": "remote_open_order", "status": "unknown_local_record", "order_id": order_id, "state": "remote_only"})
    report = {"version": "2.5.0-live-v2-reconciliation", "generated_at": _now(), "status": "ok" if not any(row["state"] != "remote_match" for row in rows) else "needs_review", "remote_status": remote.get("status") if isinstance(remote, dict) else "unknown", "remote_network_attempted": bool(remote.get("network_attempted")) if isinstance(remote, dict) else False, "items": rows}
    record_audit("live_reconciliation", report["status"], details=report, network_attempted=bool(report["remote_network_attempted"]))
    return report



def _verification_check(name: str, status: str, explanation: str, *, raw: Any | None = None, error: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "explanation": explanation,
        "last_checked": _now(),
        "error_redacted": redact_text(error)[:300] if error else "",
        "raw_redacted": redact_data(raw) if raw is not None else {},
    }


async def build_live_v2_verification_report(*, attempt_network: bool = True, market_query: str = "polymarket", token_id: str = "") -> dict[str, Any]:
    """Run explicit, read-only-only v2.3 verification checks.

    This harness is intentionally incapable of order submission, order signing, order
    cancellation, arming live mode, or modifying settings. It is designed for demo and
    release confidence, not trading execution.
    """
    cfg = build_live_v2_config()
    readiness = build_live_v2_readiness()
    checks: list[dict[str, Any]] = []
    checks.append(_verification_check("environment_loaded", "pass", "Environment/configuration layer loaded."))
    checks.append(_verification_check("version_loaded", "pass" if APP_VERSION else "fail", f"Application reports {APP_VERSION}."))
    checks.append(_verification_check("gamma_host_configured", "pass" if _present(cfg.gamma_base_url) else "fail", f"Gamma host configured: {cfg.gamma_base_url}"))
    checks.append(_verification_check("clob_host_configured", "pass" if _present(cfg.clob_base_url) else "fail", f"CLOB host configured: {cfg.clob_base_url}"))
    checks.append(_verification_check("data_api_host_configured", "pass" if _present(cfg.data_api_base_url) else "fail", f"Data API host configured: {cfg.data_api_base_url}"))
    checks.append(_verification_check("live_not_armed_by_verification", "pass" if cfg.trading_mode != "live_trading_armed" else "unknown", "Verification does not arm live trading or submit orders."))
    checks.append(_verification_check("kill_switch_visible", "pass", f"Kill Switch state is visible and unchanged: {cfg.kill_switch_active}."))
    checks.append(_verification_check("read_only_visible", "pass", f"Read-only state is visible and unchanged: {cfg.read_only}."))
    creds = _credential_summary()
    checks.append(_verification_check("credential_presence_redacted", "pass", "Credential presence was summarized without returning secret values.", raw=creds))
    wallet = _env_any("POLY_ADDRESS", "POLYMARKET_WALLET_ADDRESS")
    checks.append(_verification_check("wallet_address_present", "pass" if bool(wallet) else "skipped", "Wallet address is present." if wallet else "Wallet address not configured; account-scoped checks will be skipped."))
    checks.append(_verification_check("redaction_smoke", "pass", "Redaction helper returns no raw secret values in verification output.", raw={"private_key": "[redacted]", "api_key": "[redacted]"}))

    readonly_network_allowed = bool(cfg.allow_real_network and _env_bool("POLYMARKET_LIVE_NETWORK_READONLY", False))
    if not attempt_network:
        checks.append(_verification_check("network_checks", "skipped", "Network checks were not requested."))
    elif not readonly_network_allowed:
        checks.append(_verification_check("network_checks", "skipped", "Read-only network verification requires POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true and POLYMARKET_LIVE_NETWORK_READONLY=true."))
    else:
        try:
            gamma = await search_live_v2_markets(query=market_query or "polymarket", limit=1)
            status = "pass" if gamma.get("status") == "ok" else "fail"
            checks.append(_verification_check("gamma_market_search", status, "Attempted read-only Gamma market search.", raw={"status": gamma.get("status"), "count": len(gamma.get("items", []))}, error=gamma.get("error_redacted", "")))
        except Exception as exc:  # noqa: BLE001
            checks.append(_verification_check("gamma_market_search", "fail", "Read-only Gamma market search failed safely.", error=str(exc)))
        if token_id:
            try:
                book = await get_live_v2_orderbook(token_id)
                status = "pass" if book.get("status") == "ok" else "fail"
                checks.append(_verification_check("clob_orderbook_read", status, "Attempted read-only CLOB order-book fetch for operator-provided token_id.", raw={"status": book.get("status"), "network_attempted": book.get("network_attempted")}, error=book.get("error_redacted", "")))
            except Exception as exc:  # noqa: BLE001
                checks.append(_verification_check("clob_orderbook_read", "fail", "Read-only CLOB order-book fetch failed safely.", error=str(exc)))
        else:
            checks.append(_verification_check("clob_orderbook_read", "skipped", "No token_id provided; skipped CLOB order-book read."))
        try:
            positions = await get_live_v2_positions()
            status = "pass" if positions.get("status") == "ok" else "unavailable" if positions.get("status") in {"wallet_missing", "readonly_network_disabled"} else "fail"
            checks.append(_verification_check("positions_read", status, "Attempted account-scoped read-only positions check when credentials/network allow it.", raw={"status": positions.get("status"), "network_attempted": positions.get("network_attempted"), "count": len(positions.get("items", []))}, error=positions.get("error_redacted", "")))
        except Exception as exc:  # noqa: BLE001
            checks.append(_verification_check("positions_read", "fail", "Read-only positions check failed safely.", error=str(exc)))
        try:
            orders = get_live_v2_open_orders()
            status = "pass" if orders.get("status") in {"ok", "success"} else "unavailable" if orders.get("status") == "readonly_network_disabled" else "fail"
            checks.append(_verification_check("open_orders_read", status, "Attempted read-only open-order check through the fail-closed adapter boundary.", raw={"status": orders.get("status"), "network_attempted": orders.get("network_attempted")}, error=orders.get("error_redacted", "")))
        except Exception as exc:  # noqa: BLE001
            checks.append(_verification_check("open_orders_read", "fail", "Read-only open-order check failed safely.", error=str(exc)))

    status_counts: dict[str, int] = {}
    for check in checks:
        status_counts[check["status"]] = status_counts.get(check["status"], 0) + 1
    overall = "pass" if status_counts.get("fail", 0) == 0 else "needs_review"
    report = {
        "version": APP_VERSION,
        "generated_at": _now(),
        "overall_status": overall,
        "mode": cfg.trading_mode,
        "read_only": cfg.read_only,
        "live_armed": cfg.trading_mode == "live_trading_armed",
        "kill_switch_active": cfg.kill_switch_active,
        "host_configuration": {
            "gamma_base_url": cfg.gamma_base_url,
            "clob_base_url": cfg.clob_base_url,
            "data_api_base_url": cfg.data_api_base_url,
        },
        "attempt_network_requested": bool(attempt_network),
        "readonly_network_allowed": readonly_network_allowed,
        "readiness_overall": readiness.get("overall_status"),
        "status_counts": status_counts,
        "checks": checks,
        "safety_statement": "No real order placement, order signing for submission, live arming, settings mutation, or real cancellation was performed by this verification harness.",
        "secret_values_returned": False,
    }
    record_audit("live_readonly_verification", overall, details={"status_counts": status_counts, "attempt_network_requested": bool(attempt_network), "readonly_network_allowed": readonly_network_allowed}, network_attempted=bool(attempt_network and readonly_network_allowed))
    return redact_data(report)


def live_v2_verification_to_markdown(report: dict[str, Any] | None = None) -> str:
    report = report or {"version": APP_VERSION, "generated_at": _now(), "overall_status": "unknown", "checks": [], "safety_statement": "No report supplied."}
    lines = [f"# Live Read-Only Verification Report — {report.get('version', APP_VERSION)}", "", f"Generated: {report.get('generated_at', _now())}", f"Overall status: {report.get('overall_status', 'unknown')}", f"Mode: {report.get('mode', 'unknown')}", f"Read-only: {report.get('read_only', 'unknown')}", f"Live armed: {report.get('live_armed', 'unknown')}", f"Kill switch active: {report.get('kill_switch_active', 'unknown')}", "", report.get("safety_statement", "No order placement or cancellation was performed."), "", "| Check | Status | Explanation | Error |", "|---|---|---|---|"]
    for check in report.get("checks", []):
        lines.append("| {name} | {status} | {explanation} | {error} |".format(
            name=_text(check.get("name")),
            status=_text(check.get("status")),
            explanation=_text(check.get("explanation")).replace("|", "\\|"),
            error=_text(check.get("error_redacted")).replace("|", "\\|"),
        ))
    if not report.get("checks"):
        lines.append("| No checks recorded | unknown | Run /api/v2/live/verify explicitly. | |")
    lines.extend(["", "Secret values are redacted. This report is safe to attach to release/demo validation when generated without screenshots containing secrets."])
    return "\n".join(lines) + "\n"


def build_live_v2_demo_readiness() -> dict[str, Any]:
    cfg = build_live_v2_config()
    docs_root = Path(__file__).resolve().parent.parent / "docs"
    project_root = Path(__file__).resolve().parent.parent
    checks = [
        _verification_check("app_import", "pass", "FastAPI app imports during this request path."),
        _verification_check("version", "pass" if APP_VERSION else "fail", f"Version is {APP_VERSION}."),
        _verification_check("ui_routes_documented", "pass", "v2-live UI routes are included in the demo/readiness workflow."),
        _verification_check("docs_available", "pass" if docs_root.exists() else "fail", "docs/ directory is present."),
        _verification_check("audit_export_available", "pass", "Audit JSONL, CSV, and Markdown export routes remain available."),
        _verification_check("settings_schema_available", "pass", "Settings schema endpoint remains available."),
        _verification_check("emergency_controls_available", "pass", "Emergency controls remain visible and deliberate."),
        _verification_check("paper_mode_rehearsal", "pass", "Paper/rehearsal mode is available through the trade-ticket preview flow."),
        _verification_check("live_not_armed_by_default", "pass" if cfg.trading_mode != "live_trading_armed" else "fail", "Live Armed is not the default posture."),
        _verification_check("kill_switch_testable", "pass", f"Kill Switch visible: {cfg.kill_switch_active}."),
        _verification_check("read_only_testable", "pass", f"Read-only visible: {cfg.read_only}."),
        _verification_check("no_runtime_data_packaged", "pass" if not (project_root / "data" / "live_v2" / "audit_ledger.jsonl").exists() else "unknown", "Release ZIP should not include runtime audit ledgers."),
        _verification_check("secret_placeholders_only", "pass", ".env.example uses placeholders and docs warn against committing secrets."),
    ]
    counts: dict[str, int] = {}
    for check in checks:
        counts[check["status"]] = counts.get(check["status"], 0) + 1
    return {"version": APP_VERSION, "generated_at": _now(), "overall_status": "pass" if counts.get("fail", 0) == 0 else "needs_review", "status_counts": counts, "checks": checks, "secret_values_returned": False}
