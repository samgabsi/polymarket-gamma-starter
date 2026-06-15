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

from .config import APP_VERSION, DATA_DIR, settings
from .live_adapter import build_live_adapter_readiness, get_live_adapter_request
from .live_clob_adapter import build_clob_adapter_status
from .live_execution_control import (
    build_manual_cancel_preview,
    build_manual_submit_preview,
    list_live_execution_attempts,
    record_manual_cancel_attempt,
    record_manual_submit_attempt,
)

LIVE_ORDER_EVENTS_PATH = DATA_DIR / "live" / "live_order_events.json"
STRATEGY_SIGNALS_PATH = DATA_DIR / "live" / "strategy_signals.json"
AUTONOMOUS_RUNS_PATH = DATA_DIR / "live" / "autonomous_runs.json"

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

VALID_SIGNAL_SIDES = {"BUY", "SELL"}
AUTONOMOUS_MODES = {"off", "dry_run", "paper_only", "fake_adapter", "live_guarded"}


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


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


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


def _stable_hash(material: dict[str, Any]) -> str:
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _csv_join(values: list[Any]) -> str:
    return " | ".join(str(item) for item in values if str(item))


def _present(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text and not text.startswith("CHANGE_ME") and text not in {"***", "<redacted>"})


def _credential_summary() -> dict[str, Any]:
    api_key = os.getenv("POLY_API_KEY") or os.getenv("POLYMARKET_CLOB_API_KEY") or os.getenv("CLOB_API_KEY")
    secret = os.getenv("POLY_SECRET") or os.getenv("POLYMARKET_CLOB_SECRET") or os.getenv("CLOB_SECRET")
    passphrase = os.getenv("POLY_PASSPHRASE") or os.getenv("POLYMARKET_CLOB_PASSPHRASE") or os.getenv("CLOB_PASSPHRASE")
    private_key = os.getenv("POLY_PRIVATE_KEY") or os.getenv("POLYMARKET_PRIVATE_KEY")
    wallet = os.getenv("POLY_ADDRESS") or os.getenv("POLYMARKET_WALLET_ADDRESS")
    return {
        "wallet_address_present": _present(wallet),
        "private_key_present": _present(private_key),
        "api_key_present": _present(api_key),
        "secret_present": _present(secret),
        "passphrase_present": _present(passphrase),
        "l2_credentials_present": all(_present(v) for v in [wallet, api_key, secret, passphrase]),
        "l1_signing_material_present": _present(private_key),
        "secret_values_returned": False,
    }


def _dependency_summary() -> dict[str, Any]:
    return {
        "py_clob_client_present": importlib.util.find_spec("py_clob_client") is not None,
        "polymarket_sdk_present": importlib.util.find_spec("polymarket") is not None or importlib.util.find_spec("py_sdk") is not None,
        "real_submit_implemented": bool(build_clob_adapter_status().get("real_submit_implemented", False)),
        "real_cancel_implemented": bool(build_clob_adapter_status().get("real_cancel_implemented", False)),
        "note": "Real SDK calls are intentionally kept behind the adapter boundary and are not exercised by automated validation.",
    }


def _live_config() -> dict[str, Any]:
    market_allowlist = _list_env("POLYMARKET_LIVE_MARKET_ALLOWLIST") or _list_env("LIVE_ALLOWED_MARKET_IDS")
    token_allowlist = _list_env("POLYMARKET_LIVE_TOKEN_ALLOWLIST")
    strategy_allowlist = _list_env("POLYMARKET_AUTONOMOUS_STRATEGY_ALLOWLIST")
    return {
        "live_mode": _bool_env("POLYMARKET_LIVE_MODE", _bool_env("LIVE_TRADING_ENABLED", False)),
        "network_readonly": _bool_env("POLYMARKET_LIVE_NETWORK_READONLY", False),
        "allow_real_network": _bool_env("POLYMARKET_LIVE_ALLOW_REAL_NETWORK", False),
        "submit_enabled": _bool_env("POLYMARKET_LIVE_ENABLE_SUBMIT", False),
        "cancel_enabled": _bool_env("POLYMARKET_LIVE_ENABLE_CANCEL", False),
        "autonomous_enabled": _bool_env("POLYMARKET_LIVE_ENABLE_AUTONOMOUS", False),
        "manual_auth_required": _bool_env("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH", True),
        "kill_switch_active": _bool_env("POLYMARKET_LIVE_KILL_SWITCH", True),
        "fake_adapter_enabled": _bool_env("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED", False),
        "emergency_cancel_enabled": _bool_env("POLYMARKET_LIVE_EMERGENCY_CANCEL_ENABLED", False),
        "max_order_notional": _float_env("POLYMARKET_LIVE_MAX_ORDER_NOTIONAL", _float_env("LIVE_MAX_ORDER_NOTIONAL", 0.0)),
        "max_daily_notional": _float_env("POLYMARKET_LIVE_MAX_DAILY_NOTIONAL", _float_env("LIVE_MAX_DAILY_NOTIONAL", 0.0)),
        "max_open_orders": _int_env("POLYMARKET_LIVE_MAX_OPEN_ORDERS", _int_env("LIVE_MAX_OPEN_ORDERS", 0)),
        "max_position_notional": _float_env("POLYMARKET_LIVE_MAX_POSITION_NOTIONAL", 0.0),
        "max_daily_loss": _float_env("POLYMARKET_LIVE_MAX_DAILY_LOSS", 0.0),
        "market_allowlist": market_allowlist,
        "token_allowlist": token_allowlist,
        "strategy_allowlist": strategy_allowlist,
        "final_confirmation_configured": _present(os.getenv("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE")),
        "autonomous_max_orders_per_run": _int_env("POLYMARKET_AUTONOMOUS_MAX_ORDERS_PER_RUN", 0),
        "autonomous_max_orders_per_day": _int_env("POLYMARKET_AUTONOMOUS_MAX_ORDERS_PER_DAY", 0),
        "autonomous_min_signal_confidence": _float_env("POLYMARKET_AUTONOMOUS_MIN_SIGNAL_CONFIDENCE", 0.0),
        "autonomous_require_market_data": _bool_env("POLYMARKET_AUTONOMOUS_REQUIRE_MARKET_DATA", True),
        "autonomous_require_execution_quality": _bool_env("POLYMARKET_AUTONOMOUS_REQUIRE_EXECUTION_QUALITY", True),
        "autonomous_require_paper_approval": _bool_env("POLYMARKET_AUTONOMOUS_REQUIRE_PAPER_APPROVAL", True),
        "autonomous_dry_run_by_default": _bool_env("POLYMARKET_AUTONOMOUS_DRY_RUN_BY_DEFAULT", True),
        "scheduler_enabled": _bool_env("POLYMARKET_AUTONOMOUS_SCHEDULER_ENABLED", False),
        "scheduler_interval_seconds": _int_env("POLYMARKET_AUTONOMOUS_SCHEDULER_INTERVAL_SECONDS", 0),
        "scheduler_dry_run_only": _bool_env("POLYMARKET_AUTONOMOUS_SCHEDULER_DRY_RUN_ONLY", True),
    }


def build_live_trading_status() -> dict[str, Any]:
    cfg = _live_config()
    creds = _credential_summary()
    dep = _dependency_summary()
    blockers: list[str] = []
    warnings: list[str] = []
    unsafe: list[str] = []
    if not cfg["live_mode"]:
        blockers.append("POLYMARKET_LIVE_MODE is false; live trading is disabled by default.")
    if cfg["kill_switch_active"]:
        blockers.append("POLYMARKET_LIVE_KILL_SWITCH is active.")
    if cfg["submit_enabled"] and not cfg["final_confirmation_configured"]:
        unsafe.append("Submit is enabled without POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE configured.")
    if cfg["submit_enabled"] and not cfg["allow_real_network"]:
        blockers.append("Submit is enabled but POLYMARKET_LIVE_ALLOW_REAL_NETWORK is false.")
    if cfg["allow_real_network"] and not creds["l2_credentials_present"]:
        blockers.append("Real network is allowed but redacted L2 credential presence is incomplete.")
    if cfg["submit_enabled"] and cfg["max_order_notional"] <= 0:
        unsafe.append("Submit is enabled without a positive POLYMARKET_LIVE_MAX_ORDER_NOTIONAL.")
    if cfg["autonomous_enabled"]:
        if not cfg["market_allowlist"]:
            unsafe.append("Autonomous mode requires POLYMARKET_LIVE_MARKET_ALLOWLIST.")
        if not cfg["strategy_allowlist"]:
            unsafe.append("Autonomous mode requires POLYMARKET_AUTONOMOUS_STRATEGY_ALLOWLIST.")
        if cfg["autonomous_max_orders_per_run"] <= 0 or cfg["autonomous_max_orders_per_day"] <= 0:
            unsafe.append("Autonomous mode requires positive max orders per run/day.")
        if cfg["max_daily_notional"] <= 0:
            unsafe.append("Autonomous mode requires a positive daily notional budget.")
        if not cfg["autonomous_require_market_data"] or not cfg["autonomous_require_execution_quality"]:
            unsafe.append("Autonomous mode must require market data and execution quality.")
    if cfg["scheduler_enabled"]:
        warnings.append("Autonomous scheduler is configured but this bridge release does not start a background loop on import.")
    if dep["py_clob_client_present"]:
        warnings.append("Legacy py_clob_client appears installed; review SDK choice before enabling real live paths.")

    if unsafe:
        status = "unsafe_config_blocked"
    elif not cfg["live_mode"]:
        status = "live_disabled_safe_default"
    elif cfg["kill_switch_active"]:
        status = "kill_switch_active"
    elif cfg["autonomous_enabled"] and not unsafe and cfg["autonomous_dry_run_by_default"]:
        status = "autonomous_ready_dry_run"
    elif cfg["submit_enabled"] and not blockers and creds["l2_credentials_present"]:
        status = "manual_submit_ready"
    else:
        status = "manual_submit_blocked"

    return {
        "version": APP_VERSION,
        "mode": "live_trading_status_v110",
        "generated_at": _now(),
        "overall_status": status,
        "config": {k: v for k, v in cfg.items() if k not in {"market_allowlist", "token_allowlist", "strategy_allowlist"}},
        "market_allowlist_count": len(cfg["market_allowlist"]),
        "token_allowlist_count": len(cfg["token_allowlist"]),
        "strategy_allowlist_count": len(cfg["strategy_allowlist"]),
        "credentials": creds,
        "adapter_dependency": dep,
        "clob_adapter_boundary": build_clob_adapter_status(),
        "live_adapter_readiness_status": build_live_adapter_readiness().get("overall_status"),
        "real_live_submit_implemented": bool(build_clob_adapter_status().get("real_submit_implemented", False)),
        "real_live_cancel_implemented": bool(build_clob_adapter_status().get("real_cancel_implemented", False)),
        "autonomous_live_mode_implemented": False,
        "autonomous_dry_run_implemented": True,
        "blockers": blockers + unsafe,
        "warnings": warnings,
        "recommended_next_action": _recommended_status_action(status),
        "secret_values_returned": False,
        "guardrail": "v1.0.0 manual-live trading foundation: real manual submit/cancel are implemented inside the CLOB adapter boundary but remain disabled by default and require every explicit operator gate. Autonomous live trading remains blocked; no autonomous background loop is started.",
    }


def _recommended_status_action(status: str) -> str:
    return {
        "live_disabled_safe_default": "Keep live mode disabled until credentials, budgets, allowlists, and operator procedures are ready.",
        "kill_switch_active": "Kill switch blocks live actions. Leave it active until all configuration and review steps are complete.",
        "unsafe_config_blocked": "Resolve unsafe configuration before attempting any manual or autonomous live path.",
        "manual_submit_ready": "Manual submit gates appear configured. Real submit remains operator-controlled and will only run through the adapter boundary when every gate passes.",
        "autonomous_ready_dry_run": "Autonomous dry-run can evaluate deterministic strategy signals without network submission.",
    }.get(status, "Review blockers and warnings before proceeding.")


def load_live_order_events() -> list[dict[str, Any]]:
    rows = _read_json(LIVE_ORDER_EVENTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_live_order_events(rows: list[dict[str, Any]]) -> None:
    _write_json(LIVE_ORDER_EVENTS_PATH, rows)



LIFECYCLE_STATUS_MAP = {
    "not_ready": "preview_blocked",
    "blocked_by_kill_switch": "submit_blocked",
    "blocked_by_submit_disabled": "submit_blocked",
    "blocked_by_cancel_disabled": "cancel_blocked",
    "blocked_by_manual_confirmation": "preview_blocked",
    "blocked_by_missing_authorization": "preview_blocked",
    "blocked_by_stale_authorization": "preview_blocked",
    "blocked_by_missing_adapter_request": "preview_blocked",
    "blocked_by_invalid_adapter_request": "preview_blocked",
    "blocked_by_missing_dry_run": "preview_blocked",
    "blocked_by_stale_dry_run": "preview_blocked",
    "blocked_by_preflight": "preview_blocked",
    "blocked_by_risk": "preview_blocked",
    "ready_for_manual_submit": "preview_ready",
    "manual_submit_disabled_safe_default": "submit_blocked",
    "fake_adapter_validated": "preview_ready",
    "submitted_fake_adapter_only": "submit_succeeded",
    "cancelled_fake_adapter_only": "cancel_succeeded",
    "live_submit_unimplemented": "submit_blocked",
    "live_cancel_unimplemented": "cancel_blocked",
    "submit_blocked": "submit_blocked",
    "submit_ready": "preview_ready",
    "submit_attempted": "submit_attempted",
    "submit_succeeded": "submit_succeeded",
    "submit_failed": "submit_failed",
    "cancel_blocked": "cancel_blocked",
    "cancel_attempted": "cancel_attempted",
    "cancel_succeeded": "cancel_succeeded",
    "cancel_failed": "cancel_failed",
}


def _lifecycle_status(attempt: dict[str, Any], receipt: dict[str, Any]) -> str:
    status = _text(attempt.get("status"))
    exchange_status = _text(receipt.get("exchange_status") or receipt.get("status")).lower()
    if exchange_status in {"open", "matched", "live"}:
        return "open"
    if exchange_status in {"filled", "complete", "completed"}:
        return "filled"
    if exchange_status in {"partially_filled", "partial_fill"}:
        return "partially_filled"
    if exchange_status in {"cancelled", "canceled"}:
        return "cancelled"
    if exchange_status == "expired":
        return "expired"
    return LIFECYCLE_STATUS_MAP.get(status, "unknown")

def _event_from_attempt(attempt: dict[str, Any]) -> dict[str, Any] | None:
    attempt_id = _text(attempt.get("attempt_id"))
    if not attempt_id:
        return None
    action = _text(attempt.get("action"))
    order = dict(attempt.get("public_order_fields") or attempt.get("order") or {})
    receipt = dict(attempt.get("receipt") or {})
    material = {"attempt_id": attempt_id, "status": attempt.get("status"), "receipt_hash": receipt.get("receipt_hash")}
    event_type = "submit" if action == "submit" else "cancel" if action == "cancel" else "attempt"
    return {
        "order_event_id": f"loe_{attempt_id}",
        "created_at": attempt.get("created_at") or attempt.get("generated_at") or _now(),
        "event_type": event_type,
        "operator": _text(attempt.get("operator"), "local"),
        "strategy_id": _text(attempt.get("strategy_id")),
        "intent_id": _text(attempt.get("intent_id")),
        "packet_id": _text(attempt.get("packet_id")),
        "adapter_request_id": _text(attempt.get("adapter_request_id")),
        "execution_attempt_id": attempt_id,
        "market_id": _text(order.get("market_id") or attempt.get("market_id")),
        "condition_id": _text(order.get("condition_id") or attempt.get("condition_id")),
        "token_id": _text(order.get("token_id") or attempt.get("token_id")),
        "side": _text(order.get("side") or attempt.get("side")).upper(),
        "price": _safe_float(order.get("price") or attempt.get("price")),
        "size": _safe_float(order.get("size") or attempt.get("size")),
        "notional": _safe_float(order.get("notional") or attempt.get("notional")),
        "order_type": _text(order.get("order_type") or attempt.get("order_type")),
        "time_in_force": _text(order.get("time_in_force") or attempt.get("time_in_force")),
        "client_order_id": _text(receipt.get("fake_order_id") or receipt.get("client_order_id")),
        "exchange_order_id": _text(receipt.get("exchange_order_id")),
        "adapter_status": _text(attempt.get("status")),
        "lifecycle_status": _lifecycle_status(attempt, receipt),
        "exchange_status": _text(receipt.get("exchange_status") or "not_exchange_acknowledged"),
        "network_attempted": bool(attempt.get("network_attempted", False) or receipt.get("network_attempted", False)),
        "signed_payload_present": bool(attempt.get("signed_payload_present", False) or receipt.get("signed_payload_present", False)),
        "exchange_acknowledgement_present": bool(attempt.get("exchange_acknowledgement_present", False) or receipt.get("exchange_acknowledgement_present", False)),
        "raw_response_hash": _stable_hash(receipt) if receipt else "",
        "redacted_response_summary": _text(receipt.get("simulated_status") or receipt.get("status") or attempt.get("status")),
        "blockers": list(attempt.get("blockers") or []),
        "warnings": list(attempt.get("warnings") or []),
        "event_hash": _stable_hash(material),
        "source": "live_execution_attempts",
    }


def list_live_order_events(limit: int = 100, status: str | None = None, event_type: str | None = None) -> list[dict[str, Any]]:
    persisted = load_live_order_events()
    derived = [item for item in (_event_from_attempt(a) for a in list_live_execution_attempts(limit=10000)) if item]
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for row in persisted + derived:
        key = _text(row.get("order_event_id")) or _stable_hash(row)
        if key in seen:
            continue
        seen.add(key)
        if status and _text(row.get("adapter_status")) != status:
            continue
        if event_type and _text(row.get("event_type")) != event_type:
            continue
        rows.append(row)
    rows.sort(key=lambda r: _text(r.get("created_at")), reverse=True)
    return rows[:limit]


def get_live_order_event(order_event_id: str) -> dict[str, Any] | None:
    for row in list_live_order_events(limit=10000):
        if _text(row.get("order_event_id")) == _text(order_event_id):
            return row
    return None


def live_orders_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = ["order_event_id", "created_at", "event_type", "operator", "strategy_id", "intent_id", "packet_id", "adapter_request_id", "execution_attempt_id", "market_id", "condition_id", "token_id", "side", "price", "size", "notional", "order_type", "time_in_force", "client_order_id", "exchange_order_id", "adapter_status", "exchange_status", "network_attempted", "signed_payload_present", "exchange_acknowledgement_present", "raw_response_hash", "redacted_response_summary", "lifecycle_status", "blockers", "warnings", "event_hash"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        copy = dict(row)
        copy["blockers"] = _csv_join(list(row.get("blockers") or []))
        copy["warnings"] = _csv_join(list(row.get("warnings") or []))
        writer.writerow({key: copy.get(key, "") for key in fields})
    return out.getvalue()


def build_live_order_board(limit: int = 100, status: str | None = None) -> dict[str, Any]:
    rows = list_live_order_events(limit=limit, status=status)
    summary = Counter(_text(row.get("adapter_status"), "unknown") for row in rows)
    lifecycle_summary = Counter(_text(row.get("lifecycle_status"), "unknown") for row in rows)
    return {"generated_at": _now(), "items": rows, "summary": dict(summary), "lifecycle_summary": dict(lifecycle_summary), "count": len(rows), "guardrail": "Live order ledger is local/audit-oriented. Fake receipts are not exchange acknowledgements."}


def build_live_reconciliation() -> dict[str, Any]:
    rows = list_live_order_events(limit=10000)
    status = build_live_trading_status()
    items: list[dict[str, Any]] = []
    for row in rows:
        exchange_id = _text(row.get("exchange_order_id"))
        lifecycle = _text(row.get("lifecycle_status"), "unknown")
        adapter_status = _text(row.get("adapter_status"), "unknown")
        severity = "info"
        suggested_action = "Keep local record for audit."
        stale_age = ""
        if exchange_id:
            state = "reconciliation_unavailable"
            warnings = ["Remote order status/open-order lookup is not attempted by default."]
            suggested_action = "Run explicit read-only reconciliation only during an operator-approved network window."
            severity = "warning"
        elif row.get("exchange_acknowledgement_present"):
            state = "unknown"
            warnings = ["Exchange acknowledgement flag present but remote status was not fetched."]
            suggested_action = "Perform read-only status check before any cancel decision."
            severity = "warning"
        elif lifecycle in {"submit_succeeded", "cancel_succeeded"}:
            state = "local_only"
            warnings = ["Local/fake result only; not an exchange acknowledgement."]
            suggested_action = "Treat as synthetic validation unless exchange_order_id is present."
        elif lifecycle.endswith("blocked") or lifecycle == "preview_blocked":
            state = "local_blocked"
            warnings = ["Blocked attempt; no remote order expected."]
        else:
            state = "local_only"
            warnings = ["Local/fake/blocked event only; no remote order to reconcile."]
        items.append({"order_event_id": row.get("order_event_id"), "execution_attempt_id": row.get("execution_attempt_id"), "market_id": row.get("market_id"), "token_id": row.get("token_id"), "adapter_status": adapter_status, "lifecycle_status": lifecycle, "exchange_order_id": exchange_id, "state": state, "severity": severity, "stale_age": stale_age, "suggested_operator_action": suggested_action, "next_recommended_check": "Review live order ledger and adapter verification before any live window.", "warnings": warnings})
    return {"generated_at": _now(), "overall_status": "reconciliation_unavailable" if status.get("credentials", {}).get("l2_credentials_present") else "local_only", "remote_network_attempted": False, "items": items, "summary": dict(Counter(item["state"] for item in items)), "guardrail": "Read-only reconciliation; it may suggest actions but never cancels or submits."}


def live_reconciliation_to_csv(report: dict[str, Any] | None = None) -> str:
    report = report or build_live_reconciliation()
    fields = ["order_event_id", "execution_attempt_id", "market_id", "token_id", "adapter_status", "lifecycle_status", "exchange_order_id", "state", "severity", "stale_age", "suggested_operator_action", "next_recommended_check", "warnings"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in report.get("items", []):
        copy = dict(row)
        copy["warnings"] = _csv_join(list(row.get("warnings") or []))
        writer.writerow({key: copy.get(key, "") for key in fields})
    return out.getvalue()


def load_strategy_signals() -> list[dict[str, Any]]:
    rows = _read_json(STRATEGY_SIGNALS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_strategy_signals(rows: list[dict[str, Any]]) -> None:
    _write_json(STRATEGY_SIGNALS_PATH, rows)


def validate_strategy_signal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = _live_config()
    blockers: list[str] = []
    warnings: list[str] = []
    side = _text(payload.get("side"), "BUY").upper()
    price = _decimal(payload.get("limit_price") or payload.get("price"))
    size = _decimal(payload.get("size"))
    confidence = _safe_float(payload.get("confidence"), 0.0)
    market_id = _text(payload.get("market_id"))
    token_id = _text(payload.get("token_id"))
    strategy_id = _text(payload.get("strategy_id"))
    if side not in VALID_SIGNAL_SIDES:
        blockers.append("side must be BUY or SELL.")
    if not market_id:
        blockers.append("market_id is required.")
    if not token_id:
        blockers.append("token_id is required.")
    if not strategy_id:
        blockers.append("strategy_id is required.")
    if price is None or price <= 0 or price >= 1:
        blockers.append("limit_price must be between 0 and 1.")
    if size is None or size <= 0:
        blockers.append("size must be greater than zero.")
    notional = float((price or Decimal("0")) * (size or Decimal("0")))
    if cfg["max_order_notional"] > 0 and notional > cfg["max_order_notional"]:
        blockers.append("signal notional exceeds POLYMARKET_LIVE_MAX_ORDER_NOTIONAL.")
    if cfg["market_allowlist"] and market_id not in cfg["market_allowlist"]:
        blockers.append("market_id is not in POLYMARKET_LIVE_MARKET_ALLOWLIST.")
    if cfg["token_allowlist"] and token_id not in cfg["token_allowlist"]:
        blockers.append("token_id is not in POLYMARKET_LIVE_TOKEN_ALLOWLIST.")
    if cfg["strategy_allowlist"] and strategy_id not in cfg["strategy_allowlist"]:
        blockers.append("strategy_id is not in POLYMARKET_AUTONOMOUS_STRATEGY_ALLOWLIST.")
    if cfg["autonomous_min_signal_confidence"] and confidence < cfg["autonomous_min_signal_confidence"]:
        blockers.append("signal confidence is below POLYMARKET_AUTONOMOUS_MIN_SIGNAL_CONFIDENCE.")
    existing = [row for row in load_strategy_signals() if _text(row.get("strategy_id")) == strategy_id and _text(row.get("market_id")) == market_id and _text(row.get("token_id")) == token_id and _text(row.get("side")) == side and _safe_float(row.get("limit_price")) == _safe_float(price) and _safe_float(row.get("size")) == _safe_float(size)]
    if existing:
        warnings.append(f"{len(existing)} similar signal(s) already exist; duplicate prevention will block autonomous re-use after one accepted run.")
    status = "valid" if not blockers else "blocked"
    return {"generated_at": _now(), "status": status, "notional": round(notional, 6), "blockers": blockers, "warnings": warnings, "secret_values_returned": False}


def record_strategy_signal(**kwargs: Any) -> dict[str, Any]:
    payload = {k: v for k, v in kwargs.items()}
    validation = validate_strategy_signal_payload(payload)
    signal_id = f"sig_{uuid4().hex[:12]}"
    created_at = _now()
    record = {
        "signal_id": signal_id,
        "created_at": created_at,
        "strategy_id": _text(payload.get("strategy_id"), "manual"),
        "market_id": _text(payload.get("market_id")),
        "token_id": _text(payload.get("token_id")),
        "side": _text(payload.get("side"), "BUY").upper(),
        "limit_price": _safe_float(payload.get("limit_price") or payload.get("price")),
        "size": _safe_float(payload.get("size")),
        "confidence": _safe_float(payload.get("confidence")),
        "rationale": _text(payload.get("rationale")),
        "expires_at": _text(payload.get("expires_at")),
        "source": _text(payload.get("source"), "manual"),
        "paper_ticket_id": _text(payload.get("paper_ticket_id")),
        "approval_id": _text(payload.get("approval_id")),
        "snapshot_id": _text(payload.get("snapshot_id")),
        "execution_quality_id": _text(payload.get("execution_quality_id")),
        "risk_budget_id": _text(payload.get("risk_budget_id")),
        "adapter_request_id": _text(payload.get("adapter_request_id")),
        "status": validation["status"],
        "notional": validation["notional"],
        "blockers": validation["blockers"],
        "warnings": validation["warnings"],
        "signal_hash": _stable_hash({"created_at": created_at, "payload": payload, "validation": validation}),
    }
    rows = load_strategy_signals()
    rows.append(record)
    save_strategy_signals(rows)
    return record


def list_strategy_signals(limit: int = 100, status: str | None = None, strategy_id: str | None = None) -> list[dict[str, Any]]:
    rows = list(reversed(load_strategy_signals()))
    out: list[dict[str, Any]] = []
    for row in rows:
        if status and _text(row.get("status")) != status:
            continue
        if strategy_id and _text(row.get("strategy_id")) != strategy_id:
            continue
        out.append(row)
    return out[:limit]


def get_strategy_signal(signal_id: str) -> dict[str, Any] | None:
    for row in load_strategy_signals():
        if _text(row.get("signal_id")) == _text(signal_id):
            return row
    return None


def strategy_signals_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = ["signal_id", "created_at", "strategy_id", "market_id", "condition_id", "token_id", "side", "limit_price", "size", "confidence", "notional", "source", "paper_ticket_id", "approval_id", "snapshot_id", "execution_quality_id", "adapter_request_id", "status", "blockers", "warnings", "signal_hash"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        copy = dict(row)
        copy["blockers"] = _csv_join(list(row.get("blockers") or []))
        copy["warnings"] = _csv_join(list(row.get("warnings") or []))
        writer.writerow({key: copy.get(key, "") for key in fields})
    return out.getvalue()


def build_strategy_signal_board(limit: int = 100, status: str | None = None) -> dict[str, Any]:
    rows = list_strategy_signals(limit=limit, status=status)
    return {"generated_at": _now(), "items": rows, "count": len(rows), "summary": dict(Counter(_text(r.get("status"), "unknown") for r in rows)), "guardrail": "Strategy signals are deterministic local records; the engine does not invent trades from LLM text."}


def load_autonomous_runs() -> list[dict[str, Any]]:
    rows = _read_json(AUTONOMOUS_RUNS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_autonomous_runs(rows: list[dict[str, Any]]) -> None:
    _write_json(AUTONOMOUS_RUNS_PATH, rows)


def _signal_decision(signal: dict[str, Any], mode: str, cfg: dict[str, Any], used_keys: set[str]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if mode not in AUTONOMOUS_MODES:
        blockers.append("mode must be off, dry_run, paper_only, fake_adapter, or live_guarded.")
    if mode == "off":
        blockers.append("autonomous mode is off.")
    if _text(signal.get("status")) != "valid":
        blockers.append("strategy signal is not valid.")
    if cfg["kill_switch_active"] and mode in {"fake_adapter", "live_guarded"}:
        blockers.append("kill switch blocks autonomous submit-like paths.")
    if mode == "live_guarded":
        if not cfg["autonomous_enabled"]:
            blockers.append("POLYMARKET_LIVE_ENABLE_AUTONOMOUS is false.")
        if not cfg["live_mode"] or not cfg["allow_real_network"] or not cfg["submit_enabled"]:
            blockers.append("live guarded mode requires live mode, real network, and submit enabled.")
        if not cfg["market_allowlist"]:
            blockers.append("autonomous live mode requires market allowlist.")
        if not cfg["strategy_allowlist"]:
            blockers.append("autonomous live mode requires strategy allowlist.")
        if cfg["max_order_notional"] <= 0 or cfg["max_daily_notional"] <= 0:
            blockers.append("autonomous live mode requires positive order and daily budgets.")
        if not signal.get("snapshot_id") and cfg["autonomous_require_market_data"]:
            blockers.append("autonomous live mode requires market-data snapshot binding.")
        if not signal.get("execution_quality_id") and cfg["autonomous_require_execution_quality"]:
            blockers.append("autonomous live mode requires execution-quality binding.")
    if mode == "fake_adapter" and not cfg["fake_adapter_enabled"]:
        blockers.append("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED is false.")
    key = f"{signal.get('strategy_id')}|{signal.get('market_id')}|{signal.get('token_id')}|{signal.get('side')}"
    if key in used_keys:
        blockers.append("duplicate signal key already accepted in this run.")
    notional = _safe_float(signal.get("notional"))
    if cfg["max_order_notional"] > 0 and notional > cfg["max_order_notional"]:
        blockers.append("signal notional exceeds max order notional.")
    if blockers:
        decision = "blocked_by_config" if mode != "off" else "ignored_disabled"
    elif mode == "dry_run":
        decision = "queued_for_manual_review"
    elif mode == "paper_only":
        decision = "paper_recorded"
    elif mode == "fake_adapter":
        decision = "fake_submitted" if signal.get("adapter_request_id") else "queued_for_manual_review"
        if not signal.get("adapter_request_id"):
            warnings.append("No adapter_request_id on signal; queued rather than fake-submitted.")
    elif mode == "live_guarded":
        decision = "live_submit_failed"
        blockers.append("Real autonomous live submit remains blocked; use dry_run/fake_adapter to queue for manual review.")
    else:
        decision = "ignored_disabled"
    if not blockers:
        used_keys.add(key)
    return {"signal_id": signal.get("signal_id"), "strategy_id": signal.get("strategy_id"), "market_id": signal.get("market_id"), "token_id": signal.get("token_id"), "side": signal.get("side"), "notional": notional, "decision": decision, "blockers": blockers, "warnings": warnings, "adapter_request_id": signal.get("adapter_request_id", "")}


def build_autonomous_run_preview(mode: str = "off", operator: str = "local", limit: int = 50, strategy_id: str | None = None) -> dict[str, Any]:
    mode = _text(mode or "off", "off")
    cfg = _live_config()
    signals = list_strategy_signals(limit=limit, status=None, strategy_id=strategy_id)
    if cfg["autonomous_max_orders_per_run"] > 0:
        signals = signals[: cfg["autonomous_max_orders_per_run"]]
    used: set[str] = set()
    decisions = [_signal_decision(signal, mode, cfg, used) for signal in signals]
    summary = Counter(d["decision"] for d in decisions)
    blockers = []
    if mode == "off":
        blockers.append("autonomous trading is off by default.")
    if mode == "live_guarded":
        blockers.append("Real autonomous live mode remains blocked in v1.1.0; no real submit occurs.")
    return {"version": APP_VERSION, "mode": mode, "generated_at": _now(), "recorded": False, "operator": operator, "signals_considered": len(signals), "decisions": decisions, "summary": dict(summary), "notional_attempted": round(sum(_safe_float(d.get("notional")) for d in decisions if not d.get("blockers")), 6), "kill_switch_active": cfg["kill_switch_active"], "blockers": blockers, "warnings": [], "real_network_attempted": False, "real_orders_submitted": 0, "fake_orders_submitted": _safe_int(summary.get("fake_submitted")), "guardrail": "Autonomous run preview only. It consumes deterministic signals and never invents trades."}


def record_autonomous_run(mode: str = "off", operator: str = "local", limit: int = 50, strategy_id: str | None = None) -> dict[str, Any]:
    preview = build_autonomous_run_preview(mode=mode, operator=operator, limit=limit, strategy_id=strategy_id)
    created_at = _now()
    run_id = f"arun_{uuid4().hex[:12]}"
    record = dict(preview)
    record.update({"run_id": run_id, "created_at": created_at, "recorded": True, "run_hash": _stable_hash({"created_at": created_at, "preview": preview})})
    rows = load_autonomous_runs()
    rows.append(record)
    save_autonomous_runs(rows)
    return record


def list_autonomous_runs(limit: int = 100, mode: str | None = None) -> list[dict[str, Any]]:
    rows = list(reversed(load_autonomous_runs()))
    out = []
    for row in rows:
        if mode and _text(row.get("mode")) != mode:
            continue
        out.append(row)
    return out[:limit]


def get_autonomous_run(run_id: str) -> dict[str, Any] | None:
    for row in load_autonomous_runs():
        if _text(row.get("run_id")) == _text(run_id):
            return row
    return None


def autonomous_runs_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = ["run_id", "created_at", "mode", "operator", "signals_considered", "notional_attempted", "kill_switch_active", "real_network_attempted", "real_orders_submitted", "fake_orders_submitted", "blockers", "warnings", "run_hash"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        copy = dict(row)
        copy["blockers"] = _csv_join(list(row.get("blockers") or []))
        copy["warnings"] = _csv_join(list(row.get("warnings") or []))
        writer.writerow({key: copy.get(key, "") for key in fields})
    return out.getvalue()


def build_autonomous_status() -> dict[str, Any]:
    cfg = _live_config()
    rows = list_autonomous_runs(limit=100)
    return {"generated_at": _now(), "overall_status": "autonomous_disabled_safe_default" if not cfg["autonomous_enabled"] else "autonomous_configured_guarded", "enabled": cfg["autonomous_enabled"], "scheduler_enabled": cfg["scheduler_enabled"], "scheduler_starts_on_import": False, "mode_default": "off", "run_summary": dict(Counter(_text(r.get("mode"), "unknown") for r in rows)), "latest_run_id": rows[0].get("run_id") if rows else "", "guardrail": "No background autonomous loop starts automatically. Runs are explicit CLI/API actions and default to dry-run/off."}


def live_trading_alerts() -> list[dict[str, Any]]:
    status = build_live_trading_status()
    alerts = []
    level = "warning" if status.get("overall_status") in {"unsafe_config_blocked", "kill_switch_active"} else "info"
    alerts.append({"timestamp": _now(), "level": level, "kind": "live_trading_status", "title": "Live trading status", "detail": str(status.get("overall_status")), "market_id": None, "question": None, "source": "live_trading_v110", "link": "/live-trading", "data": {"blocker_count": len(status.get("blockers") or [])}})
    auto = build_autonomous_status()
    alerts.append({"timestamp": _now(), "level": "info", "kind": "autonomous_trading_status", "title": "Autonomous trading status", "detail": str(auto.get("overall_status")), "market_id": None, "question": None, "source": "live_trading_v110", "link": "/autonomous-trading", "data": {"scheduler_enabled": auto.get("scheduler_enabled")}})
    return alerts
