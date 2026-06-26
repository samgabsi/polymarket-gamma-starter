from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_VERSION, DATA_DIR
from .platform_safety import action_is_forbidden, redact_data, redact_text, safety_flags, validate_safety_class

PLATFORM_DIR = DATA_DIR / "live_v3" / "platform"
PLUGIN_MANIFEST_DIR = PLATFORM_DIR / "plugin_manifests"
PLUGIN_TYPES = {"local-ui-extension", "local-workflow-extension", "local-export-extension", "local-diagnostic-extension", "local-research-helper", "disabled-placeholder"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manifest(plugin_id: str, title: str, plugin_type: str, capabilities: list[str], enabled: bool = False, description: str = "") -> dict[str, Any]:
    return {
        "plugin_id": plugin_id,
        "title": title,
        "description": description or f"Safe local manifest for {title}.",
        "version": "0.1.0-manifest-only",
        "app_compatibility": [APP_VERSION, "v4.x"],
        "enabled": bool(enabled),
        "plugin_type": plugin_type if plugin_type in PLUGIN_TYPES else "disabled-placeholder",
        "allowed_routes": [f"/v3/platform/plugins#{plugin_id}"],
        "allowed_api_namespaces": ["/api/v3/platform/plugins"],
        "allowed_storage_namespaces": [f"data/live_v3/platform/plugin_manifests/{plugin_id}"],
        "safety_class": "informational",
        "capabilities": capabilities,
        "forbidden_capabilities": ["place_order", "cancel_order", "approve_trade", "sign_transaction", "arm_live_trading", "disable_kill_switch", "bypass_read_only", "execute_remote_code", "load_remote_code", "read_secrets"],
        "no_live_mutation": True,
        "no_secret_access": True,
        "no_network_by_default": True,
        "operator_notes": "Metadata-only manifest. It is not executable plugin code.",
        "audit_metadata": {"created_at": _now(), "manifest_only": True, "arbitrary_code_execution": False},
        **safety_flags(),
    }


def default_plugin_manifests() -> list[dict[str, Any]]:
    return [
        _manifest("demo_local_ui_panel", "Demo Local UI Panel", "local-ui-extension", ["navigate", "display_safe_summary"], False, "Fake disabled UI extension manifest for future v4.x planning."),
        _manifest("demo_platform_diagnostic", "Demo Platform Diagnostic", "local-diagnostic-extension", ["view_diagnostics", "export_safe_report"], False, "Fake diagnostic manifest; does not execute diagnostics automatically."),
        _manifest("demo_disabled_research_helper", "Demo Disabled Research Helper", "disabled-placeholder", ["open_source_preview"], False, "Disabled placeholder showing the manifest boundary without network access."),
    ]


def normalize_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    caps = [redact_text(c) for c in raw.get("capabilities", []) if str(c or "").strip()] if isinstance(raw.get("capabilities"), list) else []
    forbidden = [redact_text(c) for c in raw.get("forbidden_capabilities", []) if str(c or "").strip()] if isinstance(raw.get("forbidden_capabilities"), list) else []
    plugin_type = str(raw.get("plugin_type") or "disabled-placeholder").strip()
    manifest = {
        "plugin_id": redact_text(raw.get("plugin_id") or raw.get("id") or "plugin_unknown"),
        "title": redact_text(raw.get("title") or "Plugin Manifest"),
        "description": redact_text(raw.get("description") or "Metadata-only plugin manifest."),
        "version": redact_text(raw.get("version") or "0.1.0-manifest-only"),
        "app_compatibility": raw.get("app_compatibility") if isinstance(raw.get("app_compatibility"), list) else [APP_VERSION],
        "enabled": bool(raw.get("enabled", False)),
        "plugin_type": plugin_type if plugin_type in PLUGIN_TYPES else "disabled-placeholder",
        "allowed_routes": raw.get("allowed_routes") if isinstance(raw.get("allowed_routes"), list) else [],
        "allowed_api_namespaces": raw.get("allowed_api_namespaces") if isinstance(raw.get("allowed_api_namespaces"), list) else [],
        "allowed_storage_namespaces": raw.get("allowed_storage_namespaces") if isinstance(raw.get("allowed_storage_namespaces"), list) else [],
        "safety_class": validate_safety_class(raw.get("safety_class")),
        "capabilities": caps,
        "forbidden_capabilities": sorted(set(forbidden + ["place_order", "cancel_order", "approve_trade", "sign_transaction", "arm_live_trading", "read_secrets", "execute_remote_code", "load_remote_code"])),
        "no_live_mutation": bool(raw.get("no_live_mutation", True)),
        "no_secret_access": bool(raw.get("no_secret_access", True)),
        "no_network_by_default": bool(raw.get("no_network_by_default", True)),
        "operator_notes": redact_text(raw.get("operator_notes") or "Metadata-only manifest."),
        "audit_metadata": raw.get("audit_metadata") if isinstance(raw.get("audit_metadata"), dict) else {"loaded_at": _now(), "manifest_only": True},
        **safety_flags(),
    }
    validation = validate_manifest(manifest)
    manifest["validation"] = validation
    return redact_data(manifest)


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    caps = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), list) else []
    forbidden_requested = [c for c in caps if action_is_forbidden(c)]
    problems = []
    required_fields = ["plugin_id", "title", "version", "plugin_type", "capabilities", "no_live_mutation", "no_secret_access", "no_network_by_default"]
    missing_required = [field for field in required_fields if field not in manifest]
    if missing_required:
        problems.append("required fields missing")
    if not manifest.get("no_live_mutation", True):
        problems.append("no_live_mutation must remain true")
    if not manifest.get("no_secret_access", True):
        problems.append("no_secret_access must remain true")
    if not manifest.get("no_network_by_default", True):
        problems.append("no_network_by_default must remain true")
    if forbidden_requested:
        problems.append("forbidden live mutation capability requested")
    if manifest.get("plugin_type") not in PLUGIN_TYPES:
        problems.append("unknown plugin type")
    api_namespaces = manifest.get("allowed_api_namespaces") if isinstance(manifest.get("allowed_api_namespaces"), list) else []
    storage_namespaces = manifest.get("allowed_storage_namespaces") if isinstance(manifest.get("allowed_storage_namespaces"), list) else []
    if any(str(ns).startswith("/api/live") or str(ns).startswith("/api/v2/live") for ns in api_namespaces):
        problems.append("live mutation api namespace declaration rejected")
    if any("secret" in str(ns).lower() or "credential" in str(ns).lower() for ns in storage_namespaces):
        problems.append("secret storage namespace declaration rejected")
    compatibility = manifest.get("app_compatibility") if isinstance(manifest.get("app_compatibility"), list) else []
    if compatibility and APP_VERSION not in compatibility and "v4.x" not in compatibility:
        problems.append("app compatibility range does not include current version")
    return safety_flags({
        "ok": len(problems) == 0,
        "status": "pass" if len(problems) == 0 else "fail",
        "problems": problems,
        "missing_required_fields": missing_required,
        "forbidden_requested": forbidden_requested,
        "manifest_only": True,
        "arbitrary_code_executed": False,
        "remote_code_loaded": False,
        "no_live_mutation_enforced": manifest.get("no_live_mutation", True) is True,
        "no_secret_access_enforced": manifest.get("no_secret_access", True) is True,
        "no_network_by_default_enforced": manifest.get("no_network_by_default", True) is True,
    })


def load_plugin_manifests(include_runtime: bool = True) -> dict[str, Any]:
    manifests = default_plugin_manifests()
    if include_runtime and PLUGIN_MANIFEST_DIR.exists():
        for path in sorted(PLUGIN_MANIFEST_DIR.glob("*.json"))[:100]:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    manifests.append(normalize_manifest(value))
            except Exception as exc:  # defensive diagnostics only
                manifests.append(normalize_manifest({"plugin_id": path.stem, "title": path.name, "enabled": False, "operator_notes": f"Invalid manifest: {exc}"}))
    normalized = [normalize_manifest(m) for m in manifests]
    invalid = [m for m in normalized if m.get("validation", {}).get("ok") is False]
    return safety_flags({"version": APP_VERSION, "count": len(normalized), "invalid_count": len(invalid), "items": normalized, "plugin_manifests_do_not_execute_code": True})


def plugin_summary() -> dict[str, Any]:
    loaded = load_plugin_manifests()
    return safety_flags({
        "version": APP_VERSION,
        "plugin_count": loaded["count"],
        "invalid_plugin_count": loaded["invalid_count"],
        "enabled_plugin_count": sum(1 for m in loaded["items"] if m.get("enabled")),
        "plugin_types": sorted({m.get("plugin_type") for m in loaded["items"]}),
        "manifest_boundary": "metadata-only; no arbitrary code execution",
    })
