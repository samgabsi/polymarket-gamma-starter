from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from typing import Any

from .config import APP_VERSION, settings


@dataclass(frozen=True)
class LiveConfigField:
    group: str
    key: str
    aliases: list[str]
    label: str
    required_for: str
    sensitive: bool
    default: str | None
    status: str
    redacted_value: str
    note: str


SENSITIVE_KEYS = {
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
    "OPENAI_API_KEY",
    "NEWS_API_KEY",
    "POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE",
}


FIELD_SPECS: list[dict[str, Any]] = [
    {
        "group": "Runtime gates",
        "key": "APP_MODE",
        "label": "Application mode",
        "required_for": "All modes",
        "default": "read_only",
        "note": "Keep this read_only until an execution adapter exists and is tested.",
    },
    {
        "group": "Runtime gates",
        "key": "READ_ONLY",
        "label": "Read-only master switch",
        "required_for": "All modes",
        "default": "true",
        "note": "Must remain true for this stage; it prevents the app from representing itself as live-execution capable.",
    },
    {
        "group": "Runtime gates",
        "key": "LIVE_TRADING_ENABLED",
        "label": "Live trading feature flag",
        "required_for": "Future gated execution",
        "default": "false",
        "note": "This version exposes readiness fields only. Turning this on does not create order execution support.",
    },
    {
        "group": "Runtime gates",
        "key": "LIVE_DRY_RUN_ONLY",
        "label": "Dry-run-only execution guard",
        "required_for": "Future staged execution tests",
        "default": "true",
        "note": "Keeps future authenticated calls in dry-run/shadow mode until explicitly changed in a later build.",
    },
    {
        "group": "Runtime gates",
        "key": "LIVE_REQUIRE_MANUAL_APPROVAL",
        "label": "Manual approval required",
        "required_for": "Future staged execution tests",
        "default": "true",
        "note": "Preserves human-in-the-loop operator approval before any future live action.",
    },
    {
        "group": "Runtime gates",
        "key": "LIVE_PRETRADE_CHECKS_ENABLED",
        "label": "Pre-trade checks enabled",
        "required_for": "Future staged execution tests",
        "default": "true",
        "note": "Future live adapters should refuse orders when deterministic preflight/risk checks are disabled.",
    },
    {
        "group": "Runtime gates",
        "key": "LIVE_AUDIT_REQUIRED",
        "label": "Audit record required",
        "required_for": "Future staged execution tests",
        "default": "true",
        "note": "Future live adapters should require durable local audit records for approvals and order intents.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_LIVE_MODE",
        "label": "Polymarket live adapter mode",
        "required_for": "Future manual live adapter review",
        "default": "false",
        "note": "Enables live-adapter readiness posture only. It does not create order submission support.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_LIVE_NETWORK_READONLY",
        "label": "Read-only network validation",
        "required_for": "Optional authenticated read-only validation",
        "default": "false",
        "note": "Default off. When true, validation endpoints may attempt a read-only client/host check; they still never submit or cancel orders.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_LIVE_ENABLE_SUBMIT",
        "label": "Submit requested",
        "required_for": "Future manual execution implementation",
        "default": "false",
        "note": "Default off. This release records request readiness only and still has no live submission implementation.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_LIVE_ENABLE_CANCEL",
        "label": "Cancel requested",
        "required_for": "Future manual cancellation implementation",
        "default": "false",
        "note": "Default off. This release has no live cancellation implementation.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH",
        "label": "Manual adapter authorization required",
        "required_for": "Future manual execution implementation",
        "default": "true",
        "note": "Must remain true for any future manual execution-capable stage.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_LIVE_KILL_SWITCH",
        "label": "Execution kill switch",
        "required_for": "Emergency/live adapter block",
        "default": "false",
        "note": "When true, adapter request and manual execution review records are blocked.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_LIVE_REQUIRE_DRY_RUN_RECEIPT",
        "label": "Dry-run receipt required",
        "required_for": "Adapter request validation",
        "default": "true",
        "note": "Requires a current offline dry-run adapter receipt before adapter request records can become ready.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_LIVE_READONLY_TIMEOUT_SECONDS",
        "label": "Read-only validation timeout",
        "required_for": "Optional authenticated read-only validation",
        "default": "4",
        "note": "Timeout used only by explicitly enabled read-only validation.",
    },
    {
        "group": "Manual execution control",
        "key": "POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED",
        "label": "Manual submit enabled",
        "required_for": "Fake-local manual submit simulation",
        "default": "false",
        "note": "Default off. Must be deliberately true before the v0.7 control plane records any fake-local submit receipt.",
    },
    {
        "group": "Manual execution control",
        "key": "POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED",
        "label": "Manual cancel enabled",
        "required_for": "Fake-local manual cancel simulation",
        "default": "false",
        "note": "Default off. Real live cancellation requires every manual live gate.",
    },
    {
        "group": "Manual execution control",
        "key": "POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED",
        "label": "Fake-local adapter enabled",
        "required_for": "Safe execution-boundary simulation",
        "default": "false",
        "note": "Enables deterministic local fake receipts only. Fake receipts are not exchange orders.",
    },
    {
        "group": "Manual execution control",
        "key": "POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE",
        "label": "Final confirmation phrase",
        "required_for": "Every manual submit/cancel attempt",
        "default": "",
        "sensitive": True,
        "note": "Local phrase required for final attempts. It is never returned raw and should not be committed.",
    },
    {
        "group": "Manual execution control",
        "key": "POLYMARKET_LIVE_AUTHORIZATION_MAX_AGE_MINUTES",
        "label": "Authorization max age",
        "required_for": "Manual submit staleness control",
        "default": "60",
        "note": "Blocks manual submit when the bound operator authorization is too old.",
    },
    {
        "group": "Manual execution control",
        "key": "POLYMARKET_LIVE_DRY_RUN_MAX_AGE_MINUTES",
        "label": "Dry-run max age",
        "required_for": "Manual submit staleness control",
        "default": "60",
        "note": "Blocks manual submit when the bound offline dry-run receipt is too old.",
    },
    {
        "group": "Manual execution control",
        "key": "POLYMARKET_LIVE_ADAPTER_REQUEST_MAX_AGE_MINUTES",
        "label": "Adapter request max age",
        "required_for": "Manual submit staleness control",
        "default": "60",
        "note": "Blocks manual submit when the adapter request or packet preflight snapshot is stale.",
    },
    {
        "group": "Live adapter boundary",
        "key": "POLYMARKET_CLOB_HOST",
        "aliases": ["CLOB_BASE_URL"],
        "label": "Polymarket CLOB host",
        "required_for": "Readiness and optional read-only validation",
        "default": "https://clob.polymarket.com",
        "note": "Host metadata only unless read-only validation is explicitly enabled.",
    },
    {
        "group": "Polymarket identity",
        "key": "POLY_ADDRESS",
        "aliases": ["POLYMARKET_WALLET_ADDRESS"],
        "label": "Wallet address",
        "required_for": "Authenticated CLOB account context",
        "default": "",
        "note": "Public address only. Used for readiness checks, not for signing or order placement in this build.",
    },
    {
        "group": "Polymarket identity",
        "key": "POLYMARKET_FUNDER_ADDRESS",
        "label": "Funder/proxy address",
        "required_for": "Future CLOB account/funder mapping",
        "default": "",
        "note": "Optional until an execution adapter validates the required account model.",
    },
    {
        "group": "Polymarket identity",
        "key": "POLYMARKET_CHAIN_ID",
        "label": "Target chain ID",
        "required_for": "Future signer validation",
        "default": "137",
        "note": "Readiness metadata only. This version does not sign messages or submit orders.",
    },
    {
        "group": "Polymarket identity",
        "key": "POLYMARKET_SIGNATURE_TYPE",
        "label": "Signature type",
        "required_for": "Future CLOB client construction",
        "default": "",
        "note": "Readiness metadata only. This version does not sign messages or submit orders.",
    },
    {
        "group": "Polymarket credentials",
        "key": "POLY_PRIVATE_KEY",
        "aliases": ["POLYMARKET_PRIVATE_KEY"],
        "label": "L1/private signing key",
        "required_for": "Future credential derivation and signing phase",
        "default": "",
        "note": "Secret. Not needed by this build and never returned through the UI/API.",
    },
    {
        "group": "Polymarket credentials",
        "key": "POLY_API_KEY",
        "aliases": ["POLYMARKET_CLOB_API_KEY", "CLOB_API_KEY"],
        "label": "CLOB API key",
        "required_for": "Future authenticated order-management endpoints",
        "default": "",
        "note": "Secret. Presence is checked only as configured/missing.",
    },
    {
        "group": "Polymarket credentials",
        "key": "POLY_SECRET",
        "aliases": ["POLYMARKET_CLOB_SECRET", "CLOB_SECRET"],
        "label": "CLOB API secret",
        "required_for": "Future authenticated order-management endpoints",
        "default": "",
        "note": "Secret. Presence is checked only as configured/missing.",
    },
    {
        "group": "Polymarket credentials",
        "key": "POLY_PASSPHRASE",
        "aliases": ["POLYMARKET_CLOB_PASSPHRASE", "CLOB_PASSPHRASE"],
        "label": "CLOB passphrase",
        "required_for": "Future authenticated order-management endpoints",
        "default": "",
        "note": "Secret. Presence is checked only as configured/missing.",
    },
    {
        "group": "Live risk limits",
        "key": "LIVE_MAX_ORDER_NOTIONAL",
        "label": "Max live order notional",
        "required_for": "Future staged execution tests",
        "default": "0",
        "note": "Zero is safest and blocks future live order sizing until you set a deliberate limit.",
    },
    {
        "group": "Live risk limits",
        "key": "LIVE_MAX_MARKET_NOTIONAL",
        "label": "Max live market notional",
        "required_for": "Future staged execution tests",
        "default": "0",
        "note": "Zero is safest and blocks future market exposure until you set a deliberate limit.",
    },
    {
        "group": "Live risk limits",
        "key": "LIVE_MAX_DAILY_NOTIONAL",
        "label": "Max live daily notional",
        "required_for": "Future staged execution tests",
        "default": "0",
        "note": "Zero is safest and blocks future daily notional until you set a deliberate limit.",
    },
    {
        "group": "Live risk limits",
        "key": "LIVE_MAX_OPEN_ORDERS",
        "label": "Max open live orders",
        "required_for": "Future staged execution tests",
        "default": "0",
        "note": "Zero is safest and blocks future open-order fanout until you set a deliberate limit.",
    },
    {
        "group": "Live risk limits",
        "key": "LIVE_ALLOWED_MARKET_IDS",
        "label": "Allowed market IDs",
        "required_for": "Future allowlisted live execution",
        "default": "",
        "note": "Comma-separated allowlist for future execution tests. Empty should mean no markets allowed.",
    },
]


def _present(value: str | None) -> bool:
    if value is None:
        return False
    stripped = value.strip()
    return bool(stripped and not stripped.startswith("CHANGE_ME") and stripped not in {"<redacted>", "***"})


def _env_value(key: str, aliases: list[str] | None = None) -> tuple[str | None, str | None]:
    for candidate in [key, *(aliases or [])]:
        value = os.getenv(candidate)
        if _present(value):
            return value, candidate
    return None, None


def _mask(value: str | None) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if len(stripped) <= 8:
        return "***"
    return f"{stripped[:4]}...{stripped[-4:]}"


def _field_from_spec(spec: dict[str, Any]) -> LiveConfigField:
    key = str(spec["key"])
    aliases = list(spec.get("aliases") or [])
    value, source_key = _env_value(key, aliases)
    default = spec.get("default")
    sensitive = key in SENSITIVE_KEYS or any(alias in SENSITIVE_KEYS for alias in aliases)
    if value is not None:
        status = "configured"
        display = "configured" if sensitive else value
        if sensitive:
            display = _mask(value)
        if source_key and source_key != key:
            note = f"{spec.get('note', '')} Using alias {source_key}.".strip()
        else:
            note = str(spec.get("note", ""))
    elif default not in (None, ""):
        status = "default"
        display = str(default)
        note = str(spec.get("note", ""))
    else:
        status = "missing"
        display = ""
        note = str(spec.get("note", ""))
    return LiveConfigField(
        group=str(spec.get("group") or "General"),
        key=key,
        aliases=aliases,
        label=str(spec.get("label") or key),
        required_for=str(spec.get("required_for") or "Future stage"),
        sensitive=sensitive,
        default=str(default) if default is not None else None,
        status=status,
        redacted_value=display,
        note=note,
    )


def _bool_env(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _int_env(key: str, default: int) -> int:
    try:
        return int(float(os.getenv(key, str(default)) or default))
    except (TypeError, ValueError):
        return default


def summarize_live_config(fields: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = fields or [asdict(_field_from_spec(spec)) for spec in FIELD_SPECS]
    configured = sum(1 for row in rows if row.get("status") == "configured")
    missing = sum(1 for row in rows if row.get("status") == "missing")
    defaults = sum(1 for row in rows if row.get("status") == "default")
    credential_keys = {"POLY_ADDRESS", "POLY_API_KEY", "POLY_SECRET", "POLY_PASSPHRASE"}
    configured_credentials = {str(row.get("key")) for row in rows if row.get("key") in credential_keys and row.get("status") == "configured"}
    l2_ready = credential_keys.issubset(configured_credentials)
    guard_warnings: list[str] = []
    if not settings.read_only:
        guard_warnings.append("READ_ONLY is false, but this build has no live execution adapter.")
    if settings.live_trading_enabled:
        guard_warnings.append("LIVE_TRADING_ENABLED is true, but this build exposes readiness only and cannot place orders.")
    if not _bool_env("LIVE_DRY_RUN_ONLY", True):
        guard_warnings.append("LIVE_DRY_RUN_ONLY is false before a live adapter exists.")
    if not _bool_env("LIVE_REQUIRE_MANUAL_APPROVAL", True):
        guard_warnings.append("LIVE_REQUIRE_MANUAL_APPROVAL is false; human approval should remain required.")
    if not _bool_env("LIVE_PRETRADE_CHECKS_ENABLED", True):
        guard_warnings.append("LIVE_PRETRADE_CHECKS_ENABLED is false; deterministic preflight should remain required.")
    if not _bool_env("LIVE_AUDIT_REQUIRED", True):
        guard_warnings.append("LIVE_AUDIT_REQUIRED is false; audit records should remain required.")
    if _float_env("LIVE_MAX_ORDER_NOTIONAL", 0.0) > 0 and not l2_ready:
        guard_warnings.append("A live order notional limit is set before CLOB L2 credentials are complete.")
    if _int_env("LIVE_MAX_OPEN_ORDERS", 0) > 0 and not l2_ready:
        guard_warnings.append("A live open-order limit is set before CLOB L2 credentials are complete.")

    if _bool_env("POLYMARKET_LIVE_KILL_SWITCH", False):
        guard_warnings.append("POLYMARKET_LIVE_KILL_SWITCH is active; adapter request and manual execution review records will be blocked.")
    if _bool_env("POLYMARKET_LIVE_ENABLE_SUBMIT", False):
        guard_warnings.append("POLYMARKET_LIVE_ENABLE_SUBMIT is true, but this build still has no order submission implementation.")
    if _bool_env("POLYMARKET_LIVE_ENABLE_CANCEL", False):
        guard_warnings.append("POLYMARKET_LIVE_ENABLE_CANCEL is true, but this build still has no cancellation implementation.")
    if not _bool_env("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH", _bool_env("LIVE_REQUIRE_MANUAL_APPROVAL", True)):
        guard_warnings.append("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH is false; manual authorization should remain required.")
    if _bool_env("POLYMARKET_LIVE_NETWORK_READONLY", False) and not l2_ready:
        guard_warnings.append("POLYMARKET_LIVE_NETWORK_READONLY is true before CLOB L2 credentials are complete.")
    if _bool_env("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED", False) and not os.getenv("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE", "").strip():
        guard_warnings.append("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED is true without a final confirmation phrase.")
    if _bool_env("POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED", False) and not os.getenv("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE", "").strip():
        guard_warnings.append("POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED is true without a final confirmation phrase.")
    if _bool_env("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED", False) and not _bool_env("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH", True):
        guard_warnings.append("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED is true while manual adapter authorization is disabled.")

    if guard_warnings:
        readiness_state = "guard_attention"
    elif l2_ready:
        readiness_state = "credentials_present_gated"
    else:
        readiness_state = "config_fields_available"

    return {
        "field_count": len(rows),
        "configured": configured,
        "missing": missing,
        "defaults": defaults,
        "l2_credentials_ready": l2_ready,
        "guard_warning_count": len(guard_warnings),
        "guard_warnings": guard_warnings,
        "readiness_state": readiness_state,
        "order_execution_available": False,
        "live_trading_enabled": settings.live_trading_enabled,
        "polymarket_live_mode": _bool_env("POLYMARKET_LIVE_MODE", settings.live_trading_enabled),
        "readonly_network_enabled": _bool_env("POLYMARKET_LIVE_NETWORK_READONLY", False),
        "submit_requested": _bool_env("POLYMARKET_LIVE_ENABLE_SUBMIT", False),
        "cancel_requested": _bool_env("POLYMARKET_LIVE_ENABLE_CANCEL", False),
        "kill_switch_active": _bool_env("POLYMARKET_LIVE_KILL_SWITCH", False),
        "dry_run_receipt_required": _bool_env("POLYMARKET_LIVE_REQUIRE_DRY_RUN_RECEIPT", True),
        "manual_submit_enabled": _bool_env("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED", False),
        "manual_cancel_enabled": _bool_env("POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED", False),
        "fake_adapter_enabled": _bool_env("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED", False),
        "read_only": settings.read_only,
        "dry_run_only": _bool_env("LIVE_DRY_RUN_ONLY", True),
        "manual_approval_required": _bool_env("LIVE_REQUIRE_MANUAL_APPROVAL", True),
        "manual_adapter_auth_required": _bool_env("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH", _bool_env("LIVE_REQUIRE_MANUAL_APPROVAL", True)),
        "pretrade_checks_enabled": _bool_env("LIVE_PRETRADE_CHECKS_ENABLED", True),
        "audit_required": _bool_env("LIVE_AUDIT_REQUIRED", True),
    }


def build_live_config_readiness() -> dict[str, Any]:
    fields = [asdict(_field_from_spec(spec)) for spec in FIELD_SPECS]
    summary = summarize_live_config(fields)
    return {
        "source": "local_environment",
        "version": "0.7.0-live-config-readiness-v1",
        "mode": settings.app_mode,
        "read_only": settings.read_only,
        "safe_to_run_without_keys": True,
        "secret_values_returned": False,
        "note": "Configuration-readiness only. This build adds a manual live execution control plane, but real submit/cancel are implemented behind hard gates and autonomous trading is absent.",
        "summary": summary,
        "fields": fields,
        "controls": {
            "live_adapter_boundary_present": True,
            "execution_adapter_present": False,
            "order_placement_enabled": False,
            "order_cancellation_enabled": False,
            "autonomous_trading_enabled": False,
            "manual_approval_required": summary["manual_approval_required"],
            "manual_adapter_auth_required": summary["manual_adapter_auth_required"],
            "readonly_network_enabled": summary["readonly_network_enabled"],
            "submit_requested": summary["submit_requested"],
            "cancel_requested": summary["cancel_requested"],
            "kill_switch_active": summary["kill_switch_active"],
            "dry_run_receipt_required": summary["dry_run_receipt_required"],
            "manual_submit_enabled": summary["manual_submit_enabled"],
            "manual_cancel_enabled": summary["manual_cancel_enabled"],
            "fake_adapter_enabled": summary["fake_adapter_enabled"],
            "pretrade_checks_enabled": summary["pretrade_checks_enabled"],
            "audit_required": summary["audit_required"],
            "dry_run_only": summary["dry_run_only"],
        },
    }


def live_config_readiness_to_csv(report: dict[str, Any] | None = None) -> str:
    report = report or build_live_config_readiness()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["group", "key", "aliases", "label", "required_for", "status", "sensitive", "redacted_value", "default", "note"])
    writer.writeheader()
    for row in report.get("fields", []):
        item = dict(row)
        item["aliases"] = ",".join(item.get("aliases") or [])
        writer.writerow({key: item.get(key, "") for key in writer.fieldnames or []})
    return output.getvalue()


def live_config_template() -> str:
    lines = [
        f"# Polymarket Gamma Starter {APP_VERSION} live configuration template",
        "# Copy the fields you need into .env. Do not commit or share populated secrets.",
        "# This version only reads/redacts these values for readiness; it does not trade.",
        "",
    ]
    current_group = ""
    for spec in FIELD_SPECS:
        group = str(spec.get("group") or "General")
        if group != current_group:
            if current_group:
                lines.append("")
            lines.append(f"# {group}")
            current_group = group
        key = str(spec["key"])
        default = spec.get("default")
        value = "" if key in SENSITIVE_KEYS else (str(default) if default not in (None, "") else "")
        lines.append(f"# {spec.get('label', key)} - {spec.get('required_for', 'Future stage')}")
        lines.append(f"{key}={value}")
    lines.append("")
    return "\n".join(lines)


def live_config_alerts(report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    report = report or build_live_config_readiness()
    summary = report.get("summary", {})
    alerts: list[dict[str, Any]] = []
    if summary.get("guard_warning_count"):
        alerts.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "warning",
            "kind": "live_config_guard",
            "title": "Live-readiness guard needs review",
            "detail": "; ".join(str(w) for w in summary.get("guard_warnings", [])[:3]),
            "market_id": None,
            "question": None,
            "data": {"readiness_state": summary.get("readiness_state"), "guard_warnings": summary.get("guard_warnings", [])},
        })
    elif summary.get("readiness_state") == "credentials_present_gated":
        alerts.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "info",
            "kind": "live_config_ready_gated",
            "title": "Live credentials appear configured but gated",
            "detail": "CLOB L2 credential presence is detected, but execution remains unavailable in this build.",
            "market_id": None,
            "question": None,
            "data": {"readiness_state": summary.get("readiness_state")},
        })
    return alerts
