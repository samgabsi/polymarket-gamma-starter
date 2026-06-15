from __future__ import annotations

import csv
import io
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .config import APP_VERSION
from .live_clob_adapter import REAL_LIVE_CONFIRMATION, build_clob_adapter_status, clob_credential_readiness, detect_clob_dependencies
from .live_execution_control import build_manual_cancel_preview, build_manual_submit_preview
from .live_trading import build_autonomous_status, build_live_order_board, build_live_reconciliation, build_live_trading_status, list_live_order_events


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


def _csv_join(values: list[Any]) -> str:
    return " | ".join(str(item) for item in values if str(item))


def _row(level: str, name: str, status: str, detail: str, *, blocker: str = "", remediation: str = "", network_attempted: bool = False) -> dict[str, Any]:
    return {
        "level": level,
        "name": name,
        "status": status,
        "detail": detail,
        "blocker": blocker,
        "remediation": remediation,
        "network_attempted": bool(network_attempted),
    }


def build_live_adapter_verification(*, run: bool = False, operator: str = "local", request_readonly_network: bool = False, request_real_smoke: bool = False) -> dict[str, Any]:
    """Build a no-network-by-default adapter verification report.

    This deliberately does not call real submit/cancel. It also does not perform a
    read-only network call unless explicitly requested and all safety flags permit
    it; even then this implementation reports readiness rather than touching the
    network so CI and normal local validation remain safe.
    """
    clob = build_clob_adapter_status()
    deps = detect_clob_dependencies()
    creds = clob_credential_readiness()
    cfg = dict(clob.get("config") or {})
    smoke_guard = dict(clob.get("real_live_smoke_test_guard") or {})
    rows: list[dict[str, Any]] = []

    rows.append(_row("offline_config_check", "offline configuration snapshot", "passed", "Configuration parsed without returning secrets.", remediation="Review live status before enabling any real network path."))
    rows.append(_row("dependency_check", "CLOB SDK dependency", "passed" if deps.get("sdk_mapping_completed") else "blocked", str(deps.get("status") or "unknown"), blocker="Optional live SDK missing or method probe incomplete." if not deps.get("sdk_mapping_completed") else "", remediation="Install optional live SDK in the operator runtime and rerun this report." if not deps.get("sdk_mapping_completed") else "Keep SDK pinned/reviewed before live windows."))
    rows.append(_row("credential_presence_check", "redacted credential presence", "passed" if creds.get("l2_credentials_present") and creds.get("l1_signing_material_present") else "blocked", f"l2={bool(creds.get('l2_credentials_present'))}; signing={bool(creds.get('l1_signing_material_present'))}", blocker="Credentials are incomplete." if not (creds.get("l2_credentials_present") and creds.get("l1_signing_material_present")) else "", remediation="Set credentials locally in .env or environment; never commit them."))
    rows.append(_row("client_init_check", "client initialization readiness", "passed" if deps.get("sdk_mapping_completed") and creds.get("l1_signing_material_present") else "blocked", "Client construction remains gated behind dependency and credential readiness.", blocker="Cannot initialize live client safely yet." if not (deps.get("sdk_mapping_completed") and creds.get("l1_signing_material_present")) else "", remediation="Resolve dependency/credential blockers before live verification."))

    readonly_allowed = bool(request_readonly_network and cfg.get("network_readonly") and cfg.get("allow_real_network") and not cfg.get("kill_switch_active"))
    rows.append(_row("readonly_network_check", "read-only network check", "ready_but_not_executed" if readonly_allowed else "skipped", "Read-only network calls are skipped by default and not attempted by this report.", blocker="Readonly network check was not explicitly requested or live network gates are closed." if not readonly_allowed else "", remediation="Run only during a deliberate live verification window."))

    submit_preview = build_manual_submit_preview(adapter_request_id="", operator=operator, final_confirmation="", adapter_mode="blocked", note="verification gate check")
    cancel_preview = build_manual_cancel_preview(original_attempt_id="", fake_order_id="", operator=operator, final_confirmation="", adapter_mode="blocked", reason="verification gate check", note="verification gate check")
    rows.append(_row("submit_gate_check", "manual submit gate check", "blocked_safe" if submit_preview.get("blockers") else "ready", _csv_join(list(submit_preview.get("blockers") or [])) or str(submit_preview.get("status") or "ready"), remediation="Use real submit only with adapter request, limits, allowlists, kill switch off, and final confirmation."))
    rows.append(_row("cancel_gate_check", "manual cancel gate check", "blocked_safe" if cancel_preview.get("blockers") else "ready", _csv_join(list(cancel_preview.get("blockers") or [])) or str(cancel_preview.get("status") or "ready"), remediation="Use real cancel only with explicit order ID and operator confirmation."))
    rows.append(_row("fake_submit_check", "fake submit validation", "available" if cfg.get("fake_adapter_enabled") else "skipped", "Fake submit can validate local control-plane behavior when explicitly enabled.", remediation="Enable POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED only for local validation."))
    rows.append(_row("fake_cancel_check", "fake cancel validation", "available" if cfg.get("fake_adapter_enabled") else "skipped", "Fake cancel can validate local control-plane behavior when explicitly enabled.", remediation="Use fake/local mode for regression tests."))

    smoke_ready = bool(smoke_guard.get("enabled") and request_real_smoke and run)
    rows.append(_row("real_smoke_test_available_but_skipped", "real submit/cancel smoke harness", "ready_but_skipped" if smoke_guard.get("enabled") else "skipped", "Real smoke tests are never executed by normal validation.", blocker="Real smoke guard is not fully enabled." if not smoke_guard.get("enabled") else "", remediation=f"Requires {REAL_LIVE_CONFIRMATION}, live mode, real network, operation-specific confirmation, allowlists, limits, and kill switch off."))
    rows.append(_row("real_smoke_test_explicitly_requested", "explicit real smoke request", "blocked_safe" if request_real_smoke and not smoke_ready else "skipped", "Even when requested, this implementation does not submit/cancel during automated verification.", blocker="Real smoke tests must be run by a human operator outside normal validation." if request_real_smoke else "", remediation="Follow docs/REAL_LIVE_SMOKE_TESTS.md and start with read-only checks."))

    summary = Counter(row["status"] for row in rows)
    blockers = [row["blocker"] for row in rows if row.get("blocker")]
    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "operator": operator,
        "run_requested": bool(run),
        "request_readonly_network": bool(request_readonly_network),
        "request_real_smoke": bool(request_real_smoke),
        "overall_status": "blocked_safe" if blockers else "verification_safe_default",
        "levels": rows,
        "summary": dict(summary),
        "blockers": blockers,
        "warnings": ["No real network, submit, cancel, signing, or wallet action is attempted by default."],
        "network_attempted": False,
        "real_submit_attempted": False,
        "real_cancel_attempted": False,
        "signed_payload_present": False,
        "exchange_acknowledgement_present": False,
        "audit_event": "live_clob_adapter_verification",
        "guardrail": "Adapter verification is offline/default-safe; real smoke tests require separate human-operated opt-in procedures.",
    }


def live_adapter_verification_to_csv(report: dict[str, Any] | None = None) -> str:
    report = report or build_live_adapter_verification()
    fields = ["level", "name", "status", "detail", "blocker", "remediation", "network_attempted"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in report.get("levels", []):
        writer.writerow({key: row.get(key, "") for key in fields})
    return out.getvalue()


def _check_item(area: str, requirement: str, current: Any, expected: Any, ok: bool, remediation: str, *, safety_impact: str = "prevents accidental live trading") -> dict[str, Any]:
    return {
        "area": area,
        "requirement": requirement,
        "current_value": current,
        "expected_value": expected,
        "status": "pass" if ok else "blocker",
        "blocker_or_warning": "" if ok else f"{requirement} is not ready.",
        "remediation_hint": remediation,
        "safety_impact": safety_impact,
    }


def build_live_readiness_checklist() -> dict[str, Any]:
    live = build_live_trading_status()
    clob = build_clob_adapter_status()
    cfg = dict(live.get("config") or {})
    creds = dict(live.get("credentials") or {})
    clob_cfg = dict(clob.get("config") or {})
    rows = [
        _check_item("manual_live", "live mode enabled", cfg.get("live_mode"), True, bool(cfg.get("live_mode")), "Set POLYMARKET_LIVE_MODE=true only during a live operation window."),
        _check_item("manual_live", "real network allowed", cfg.get("allow_real_network"), True, bool(cfg.get("allow_real_network")), "Set POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true only after dry-run validation."),
        _check_item("manual_live", "kill switch off", cfg.get("kill_switch_active"), False, not bool(cfg.get("kill_switch_active")), "Keep kill switch active until final operator review."),
        _check_item("manual_live", "submit enabled", cfg.get("submit_enabled"), True, bool(cfg.get("submit_enabled")), "Set POLYMARKET_LIVE_ENABLE_SUBMIT=true only when ready to submit manually."),
        _check_item("manual_live", "cancel enabled", cfg.get("cancel_enabled"), True, bool(cfg.get("cancel_enabled")), "Set POLYMARKET_LIVE_ENABLE_CANCEL=true only when ready to cancel manually."),
        _check_item("manual_live", "L2 credentials present", creds.get("l2_credentials_present"), True, bool(creds.get("l2_credentials_present")), "Configure API key/secret/passphrase locally; never package secrets."),
        _check_item("manual_live", "signing material present", creds.get("l1_signing_material_present"), True, bool(creds.get("l1_signing_material_present")), "Configure private key locally; never commit it."),
        _check_item("manual_live", "market allowlist configured", live.get("market_allowlist_count"), ">0", int(live.get("market_allowlist_count") or 0) > 0, "Set POLYMARKET_LIVE_MARKET_ALLOWLIST to the exact market IDs allowed."),
        _check_item("manual_live", "token allowlist configured", live.get("token_allowlist_count"), ">0", int(live.get("token_allowlist_count") or 0) > 0, "Set POLYMARKET_LIVE_TOKEN_ALLOWLIST to exact token IDs allowed."),
        _check_item("manual_live", "max order notional positive", cfg.get("max_order_notional"), ">0", float(cfg.get("max_order_notional") or 0) > 0, "Set a tiny POLYMARKET_LIVE_MAX_ORDER_NOTIONAL for first live tests."),
        _check_item("manual_live", "final confirmation phrase configured", cfg.get("final_confirmation_configured"), True, bool(cfg.get("final_confirmation_configured")), "Set POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE locally."),
        _check_item("adapter", "SDK dependency/method probe ready", clob.get("sdk_mapping_completed"), True, bool(clob.get("sdk_mapping_completed")), "Install optional live SDK and rerun adapter verification."),
        _check_item("adapter", "fake adapter available", cfg.get("fake_adapter_enabled"), True, bool(cfg.get("fake_adapter_enabled")), "Use fake adapter for local validation before live operation.", safety_impact="validates control plane without money"),
        _check_item("reconciliation", "read-only reconciliation available", True, True, True, "Open /live-reconciliation before and after live windows.", safety_impact="detects local/remote mismatches"),
        _check_item("autonomous", "autonomous disabled by default", cfg.get("autonomous_enabled"), False, not bool(cfg.get("autonomous_enabled")), "Leave POLYMARKET_LIVE_ENABLE_AUTONOMOUS=false until manual live ops are proven.", safety_impact="prevents uncontrolled automation"),
        _check_item("autonomous", "strategy allowlist configured", live.get("strategy_allowlist_count"), ">0", int(live.get("strategy_allowlist_count") or 0) > 0, "Set strategy allowlist only for reviewed strategies.", safety_impact="autonomous readiness only"),
        _check_item("autonomous", "scheduler disabled", cfg.get("scheduler_enabled"), False, not bool(cfg.get("scheduler_enabled")), "Keep POLYMARKET_AUTONOMOUS_SCHEDULER_ENABLED=false.", safety_impact="prevents background loops"),
        _check_item("smoke_tests", "real smoke tests skipped", clob.get("real_live_smoke_test_guard", {}).get("enabled"), False, not bool(clob.get("real_live_smoke_test_guard", {}).get("enabled")), "Real smoke tests require separate human operator confirmation.", safety_impact="prevents accidental real-money tests"),
        _check_item("config", "manual submit control enabled", clob_cfg.get("manual_submit_enabled"), True, bool(clob_cfg.get("manual_submit_enabled")), "Enable POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED only when all live gates are ready."),
        _check_item("config", "manual cancel control enabled", clob_cfg.get("manual_cancel_enabled"), True, bool(clob_cfg.get("manual_cancel_enabled") or clob_cfg.get("emergency_cancel_enabled")), "Enable cancel or emergency cancel only for controlled windows."),
    ]
    summary = Counter(row["status"] for row in rows)
    ready_for_manual_live = all(row["status"] == "pass" for row in rows if row["area"] in {"manual_live", "adapter"} and row["requirement"] != "fake adapter available")
    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "overall_status": "manual_live_ready" if ready_for_manual_live else "blocked_safe_default",
        "rows": rows,
        "summary": dict(summary),
        "ready_for_manual_live": ready_for_manual_live,
        "ready_for_autonomous_live": False,
        "guardrail": "Checklist is diagnostic only; it never enables live trading.",
    }


def live_readiness_checklist_to_csv(report: dict[str, Any] | None = None) -> str:
    report = report or build_live_readiness_checklist()
    fields = ["area", "requirement", "current_value", "expected_value", "status", "blocker_or_warning", "remediation_hint", "safety_impact"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in report.get("rows", []):
        writer.writerow({key: row.get(key, "") for key in fields})
    return out.getvalue()


def build_operator_runbook() -> dict[str, Any]:
    checklist = build_live_readiness_checklist()
    verification = build_live_adapter_verification()
    reconciliation = build_live_reconciliation()
    orders = build_live_order_board(limit=25)
    autonomous = build_autonomous_status()
    steps = [
        ("Start app", "Run the app on the intended host and confirm it is reachable only from trusted LAN/VPN clients."),
        ("Confirm version", f"Verify /health returns {APP_VERSION} and the release ZIP SHA matches your artifact notes."),
        ("Confirm auth/session", "Confirm you are logged in as an admin/operator and no default password remains in use."),
        ("Review live readiness", "Open /live-trading and inspect every checklist blocker before touching live mode."),
        ("Review kill switch", "Keep the kill switch active until the final deliberate live operation window."),
        ("Verify adapter", "Run the offline adapter verification report first; do not begin with network checks."),
        ("Review allowlists", "Confirm market and token allowlists contain only the exact intended market/token IDs."),
        ("Review risk limits", "Use tiny max-order and daily-notional limits for early live operations."),
        ("Review paper approvals", "Confirm the paper ticket, approval, preflight, authorization, and packet chain is current."),
        ("Run fake submit/cancel", "Use fake_local mode to prove the control plane and ledgers before any real network action."),
        ("Run reconciliation", "Inspect local order ledger and reconciliation before and after live windows."),
        ("Optional read-only live check", "Only run read-only network verification with explicit readonly/network flags and credentials."),
        ("Manual live submit/cancel", "Use real_live only with all gates passing, operator confirmation phrase, and kill switch deliberately off."),
        ("Autonomous queue", "Keep autonomous live blocked. Use dry_run/fake_adapter to queue validated signals for manual review."),
        ("Closeout", "Record results, restore kill switch, disable live flags, export audit/ledger records, and remove local secrets from shared artifacts."),
    ]
    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "overall_status": "operator_runbook_ready",
        "steps": [{"step": i + 1, "title": title, "instruction": instruction} for i, (title, instruction) in enumerate(steps)],
        "live_readiness_summary": checklist.get("summary", {}),
        "adapter_verification_status": verification.get("overall_status"),
        "reconciliation_status": reconciliation.get("overall_status"),
        "recent_live_order_count": orders.get("count", 0),
        "autonomous_status": autonomous.get("overall_status"),
        "guardrail": "The runbook is instructional only. It never flips env flags, starts a scheduler, submits, cancels, or touches wallets.",
    }
