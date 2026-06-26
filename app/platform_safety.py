from __future__ import annotations

import json
import os
import re
from typing import Any

from .config import APP_VERSION

STANDARD_SAFETY_STATEMENT = (
    "Platform diagnostics, AI drafts, AI suggestions, ChatGPT connector blueprints, plugin manifests, route inventories, "
    "storage summaries, exports, tasks, guided reviews, cockpit views, command-palette actions, keyboard shortcuts, and workflow packets are local-first operator aids. "
    "They do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, "
    "or provide financial advice."
)
NO_FINANCIAL_ADVICE_STATEMENT = "Workflow priority, diagnostics, reports, tasks, plugins, and cockpit panels are not financial advice."
NO_LIVE_MUTATION_STATEMENT = "No AI draft, platform, plugin, diagnostic, export, route-inventory, task, guided, cockpit, shortcut, or command-palette action mutates live trading state."
TASK_NOT_APPROVAL_STATEMENT = "Task completion is an operator workflow status only and is not trade approval."
GUIDED_NOT_APPROVAL_STATEMENT = "Guided review completion is not trade approval."
COCKPIT_NOT_TRADING_STATEMENT = "Cockpit layouts, focus modes, panels, shortcuts, and command-palette actions do not place or cancel orders."
PLUGIN_NOT_TRADING_STATEMENT = "Plugin manifests are metadata only and do not execute code, place orders, cancel orders, or access secrets by default."

FORBIDDEN_LIVE_MUTATION_ACTIONS = {
    "place_order", "submit_order", "cancel_order", "cancel_orders", "approve_trade", "approve_order", "sign_transaction",
    "arm_live_trading", "enable_live_trading", "disable_kill_switch", "bypass_read_only", "mutate_live_trading_state",
    "emergency_cancel", "autonomous_trade", "auto_submit", "auto_cancel",
}
SAFE_LOCAL_ACTIONS = {
    "navigate", "open_page", "open_task", "open_review", "open_source_preview", "create_task", "add_note",
    "change_task_status", "set_due_date", "generate_safe_report", "export_safe_report", "switch_layout",
    "view_diagnostics", "view_route_inventory", "validate_plugin_manifest", "view_storage_summary",
}
SAFETY_CLASSES = {"informational", "review-only", "read-only-action", "gated-live-action-reference"}
SECRET_PATTERNS = [
    "private_key", "api_key", "api_secret", "secret", "passphrase", "auth_header", "authorization", "bearer ",
    "wallet_secret", "clob_secret", "poly_secret", "token=", "password=",
]
_SECRET_VALUE_RE = re.compile(r"(?i)(private[_-]?key|api[_-]?key|api[_-]?secret|secret|passphrase|authorization|bearer|token|password)\s*[:=]\s*[^\s,;}]+")
_SECRET_ENV_KEYS = {
    "POLYMARKET_CLOB_API_KEY",
    "POLYMARKET_CLOB_SECRET",
    "POLYMARKET_CLOB_PASSPHRASE",
    "CLOB_API_KEY",
    "CLOB_SECRET",
    "CLOB_PASSPHRASE",
    "OPENAI_API_KEY",
    "KALSHI_API_KEY_ID",
    "KALSHI_PRIVATE_KEY_PATH",
}


def _secret_values() -> list[str]:
    return [str(os.getenv(key, "")).strip() for key in _SECRET_ENV_KEYS if str(os.getenv(key, "")).strip()]


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def redact_text(value: Any) -> str:
    text = str(value or "").strip()
    for secret in _secret_values():
        text = text.replace(secret, "[redacted]")
    return _SECRET_VALUE_RE.sub(lambda m: m.group(1) + "=[REDACTED]", text)


def redact_data(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
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
            elif any(token in key_text.upper() for token in ["PRIVATE", "SECRET", "PASSPHRASE", "API_KEY", "SIGNATURE", "AUTHORIZATION"]):
                redacted[key] = "[redacted]" if _present(item) else ""
            else:
                redacted[key] = redact_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def contains_secret_keyword(value: Any) -> bool:
    raw = json.dumps(value, sort_keys=True, default=str).lower() if not isinstance(value, str) else value.lower()
    return any(pattern in raw for pattern in SECRET_PATTERNS)


def secret_scan(value: Any) -> dict[str, Any]:
    raw = json.dumps(value, sort_keys=True, default=str).lower() if not isinstance(value, str) else value.lower()
    findings = sorted({pattern for pattern in SECRET_PATTERNS if pattern in raw})
    # Field names used to say secrets are absent are acceptable when no obvious value pattern is present.
    benign = {"secret", "api_key", "private_key", "authorization", "auth_header", "passphrase", "api_secret"}
    if not _SECRET_VALUE_RE.search(raw):
        findings = [f for f in findings if f not in benign]
    return {"ok": len(findings) == 0, "finding_count": len(findings), "findings": findings, "secret_values_returned": False}


def validate_safety_class(value: Any, default: str = "informational") -> str:
    text = str(value or default).strip().lower().replace("_", "-")
    return text if text in SAFETY_CLASSES else default


def normalize_action_id(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def action_is_forbidden(action_id: Any, capabilities: list[str] | None = None) -> bool:
    aid = normalize_action_id(action_id)
    caps = {normalize_action_id(c) for c in (capabilities or [])}
    all_values = {aid, *caps}
    return any(v in FORBIDDEN_LIVE_MUTATION_ACTIONS or any(f in v for f in FORBIDDEN_LIVE_MUTATION_ACTIONS) for v in all_values if v)


def safety_flags(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    flags: dict[str, Any] = {
        "app_version": APP_VERSION,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "mutates_live_trading_state": False,
        "external_network_called": False,
        "ai_model_called": False,
        "secret_values_returned": False,
        "not_financial_advice": True,
        "task_completion_is_not_trade_approval": True,
        "guided_review_completion_is_not_trade_approval": True,
        "cockpit_actions_do_not_place_or_cancel_orders": True,
        "plugin_manifests_do_not_execute_code": True,
        "plugin_actions_do_not_place_or_cancel_orders": True,
        "platform_diagnostics_do_not_mutate_live_trading_state": True,
        "safety_statement": STANDARD_SAFETY_STATEMENT,
        "no_live_mutation_statement": NO_LIVE_MUTATION_STATEMENT,
    }
    if extra:
        flags.update(extra)
    return flags


def safety_statements() -> dict[str, Any]:
    return safety_flags({
        "standard_safety_statement": STANDARD_SAFETY_STATEMENT,
        "no_financial_advice_statement": NO_FINANCIAL_ADVICE_STATEMENT,
        "no_live_mutation_statement": NO_LIVE_MUTATION_STATEMENT,
        "task_completion_statement": TASK_NOT_APPROVAL_STATEMENT,
        "guided_review_statement": GUIDED_NOT_APPROVAL_STATEMENT,
        "cockpit_statement": COCKPIT_NOT_TRADING_STATEMENT,
        "plugin_statement": PLUGIN_NOT_TRADING_STATEMENT,
        "forbidden_live_mutation_actions": sorted(FORBIDDEN_LIVE_MUTATION_ACTIONS),
        "safe_local_actions": sorted(SAFE_LOCAL_ACTIONS),
        "safety_classes": sorted(SAFETY_CLASSES),
    })
