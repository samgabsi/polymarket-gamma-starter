from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .live_v2 import record_audit, redact_data, redact_text

COCKPIT_DIR = DATA_DIR / "live_v3" / "cockpit"
COCKPIT_EVENTS_PATH = COCKPIT_DIR / "cockpit_events.jsonl"
LAYOUTS_PATH = COCKPIT_DIR / "cockpit_layouts.jsonl"
PANELS_PATH = COCKPIT_DIR / "cockpit_panels.jsonl"
SETTINGS_PATH = COCKPIT_DIR / "settings.json"
SESSION_SNAPSHOTS_PATH = COCKPIT_DIR / "session_snapshots.jsonl"
EXPORT_MANIFESTS_PATH = COCKPIT_DIR / "export_manifests.jsonl"

LAYOUT_TYPES = [
    "daily-ops", "weekly-review", "task-triage", "blocked-task-review", "source-review",
    "dataset-review", "freshness-review", "simulation-review", "analytics-review", "governance-review",
    "research-review", "monitoring-review", "portfolio-review", "custom",
]
PANEL_TYPES = [
    "task-list", "task-detail", "source-preview", "guided-review-step", "dependency", "blocker",
    "review-packet", "notifications", "freshness-findings", "dataset-readiness", "simulation-follow-up",
    "analytics-warnings", "governance-checklist", "monitoring-alerts", "research-queue",
    "portfolio-warnings", "safe-next-actions", "saved-views", "command-palette", "keyboard-shortcuts",
]
REFRESH_MODES = ["manual", "page-load-safe-summary", "disabled"]
SAFETY_CLASSES = ["informational", "review-only", "read-only-action", "gated-live-action-reference"]
FORBIDDEN_COMMAND_KEYWORDS = {"place_order", "cancel_order", "approve_trade", "sign_transaction", "arm_live_trading", "disable_kill_switch", "bypass_read_only", "mutate_live_trading_state"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    COCKPIT_DIR.mkdir(parents=True, exist_ok=True)


def _record_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _safe_text(value: Any, default: str = "") -> str:
    text = redact_text(str(value or "").strip())
    return text or default


def _safe_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [redact_text(str(v).strip()) for v in value if str(v or "").strip()]


def _safe_dict(value: Any) -> dict[str, Any]:
    return redact_data(value) if isinstance(value, dict) else {}


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_dir()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact_data(row), sort_keys=True, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(redact_data(value))
        except json.JSONDecodeError:
            rows.append({"id": _record_id("invalid"), "status": "invalid_json", "created_at": _now(), "secret_values_returned": False})
    return rows


def _latest_by_id(rows: list[dict[str, Any]], id_key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get(id_key) or row.get("id") or _record_id("row"))
        latest[rid] = row
    return sorted(latest.values(), key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)


def _safety(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "cockpit_views_are_not_orders": True,
        "cockpit_layouts_are_not_orders": True,
        "command_palette_actions_do_not_place_or_cancel_orders": True,
        "keyboard_shortcuts_do_not_place_or_cancel_orders": True,
        "guided_review_completion_is_not_trade_approval": True,
        "task_completion_is_not_trade_approval": True,
        "dependency_chains_are_workflow_only": True,
        "not_financial_advice": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "mutates_live_trading_state": False,
        "external_network_called": False,
        "ai_model_called": False,
        "secret_values_returned": False,
        "safety_statement": "Cockpit views, saved layouts, keyboard shortcuts, command-palette actions, dependency views, source context, guided reviews, and exports are local-first human-in-the-loop workflow aids. They do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, or provide financial advice.",
    }
    if extra:
        base.update(extra)
    return base


def _audit(action: str, status: str = "ok", details: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "event_id": _record_id("cockpit_evt"),
        "timestamp": _now(),
        "app_version": APP_VERSION,
        "action": action,
        "status": status,
        "details": redact_data(details or {}),
        **_safety(),
    }
    _write_jsonl(COCKPIT_EVENTS_PATH, event)
    record_audit(
        f"v3_cockpit_{action}",
        status,
        details={**redact_data(details or {}), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False},
        network_attempted=False,
    )
    return redact_data(event)


def _layout_type(value: Any) -> str:
    text = _safe_text(value, "custom").lower().replace("_", "-")
    return text if text in LAYOUT_TYPES else "custom"


def _panel_type(value: Any) -> str:
    text = _safe_text(value, "safe-next-actions").lower().replace("_", "-")
    return text if text in PANEL_TYPES else "safe-next-actions"


def _refresh_mode(value: Any) -> str:
    text = _safe_text(value, "manual").lower().replace("_", "-")
    return text if text in REFRESH_MODES else "manual"


def _safety_class(value: Any, subsystem: str = "") -> str:
    text = _safe_text(value).lower().replace("_", "-")
    if text in SAFETY_CLASSES:
        return text
    sub = subsystem.lower()
    if "live" in sub or "order" in sub or "trade" in sub:
        return "gated-live-action-reference"
    if sub in {"datasets", "freshness", "simulation", "data"}:
        return "read-only-action"
    if sub:
        return "review-only"
    return "informational"


def _default_panel(panel_id: str, panel_type: str, title: str, subsystem: str = "tasks", **extra: Any) -> dict[str, Any]:
    now = _now()
    return {
        "panel_id": panel_id,
        "created_at": now,
        "updated_at": now,
        "app_version": APP_VERSION,
        "panel_type": _panel_type(panel_type),
        "title": _safe_text(title, "Cockpit Panel"),
        "source_subsystem": _safe_text(subsystem, "tasks"),
        "source_object_type": _safe_text(extra.get("source_object_type"), "summary"),
        "source_object_id": _safe_text(extra.get("source_object_id"), ""),
        "linked_task_ids": _safe_list(extra.get("linked_task_ids")),
        "linked_review_session_ids": _safe_list(extra.get("linked_review_session_ids")),
        "linked_packet_ids": _safe_list(extra.get("linked_packet_ids")),
        "linked_dependency_ids": _safe_list(extra.get("linked_dependency_ids")),
        "visible_fields": _safe_list(extra.get("visible_fields")) or ["status", "priority", "title", "source", "safety"],
        "refresh_mode": _refresh_mode(extra.get("refresh_mode", "page-load-safe-summary")),
        "unknown_unavailable_data": _safe_list(extra.get("unknown_unavailable_data")) or ["Runtime records may be absent until the operator creates local tasks, reviews, or previews."],
        "safety_class": _safety_class(extra.get("safety_class"), subsystem),
        "audit_metadata": {"created_by": "system-default", "safe_local_only": True},
        **_safety(),
    }


def default_panels() -> list[dict[str, Any]]:
    return [
        _default_panel("panel_task_list", "task-list", "Task List", "tasks"),
        _default_panel("panel_task_detail", "task-detail", "Task Detail", "tasks"),
        _default_panel("panel_source_preview", "source-preview", "Source Preview", "workspace"),
        _default_panel("panel_guided_step", "guided-review-step", "Guided Review Step", "workspace"),
        _default_panel("panel_dependency", "dependency", "Dependency Chain", "workspace"),
        _default_panel("panel_blocker", "blocker", "Blocked Work", "workspace"),
        _default_panel("panel_review_packet", "review-packet", "Review Packets", "workspace"),
        _default_panel("panel_notifications", "notifications", "Notifications", "freshness"),
        _default_panel("panel_freshness", "freshness-findings", "Freshness Findings", "freshness"),
        _default_panel("panel_dataset", "dataset-readiness", "Dataset Readiness", "datasets"),
        _default_panel("panel_simulation", "simulation-follow-up", "Simulation Follow-ups", "simulation"),
        _default_panel("panel_analytics", "analytics-warnings", "Analytics Warnings", "analytics"),
        _default_panel("panel_governance", "governance-checklist", "Governance Checklist", "governance"),
        _default_panel("panel_monitoring", "monitoring-alerts", "Monitoring Alerts", "monitoring"),
        _default_panel("panel_research", "research-queue", "Research Queue", "research"),
        _default_panel("panel_portfolio", "portfolio-warnings", "Portfolio Warnings", "portfolio"),
        _default_panel("panel_safe_next", "safe-next-actions", "Safe Next Actions", "tasks"),
        _default_panel("panel_saved_views", "saved-views", "Saved Views", "workspace"),
        _default_panel("panel_command_palette", "command-palette", "Safe Command Palette", "cockpit"),
        _default_panel("panel_shortcuts", "keyboard-shortcuts", "Keyboard Shortcuts", "cockpit"),
    ]


def _layout(layout_id: str, title: str, layout_type: str, panel_ids: list[str], default_focus_panel: str, description: str = "") -> dict[str, Any]:
    now = _now()
    panel_lookup = {p["panel_id"]: p for p in default_panels()}
    panels = [panel_lookup[pid] for pid in panel_ids if pid in panel_lookup]
    return {
        "layout_id": layout_id,
        "created_at": now,
        "updated_at": now,
        "app_version": APP_VERSION,
        "title": title,
        "description": description or f"Local-first cockpit layout for {title.lower()}.",
        "layout_type": _layout_type(layout_type),
        "panel_definitions": panels,
        "panel_ids": [p["panel_id"] for p in panels],
        "default_focus_panel": default_focus_panel,
        "enabled": True,
        "operator_notes": "Default layout. Operator may create local overrides.",
        "safety_statement": _safety()["safety_statement"],
        "audit_metadata": {"created_by": "system-default", "safe_local_only": True},
        **_safety(),
    }


def default_layouts() -> list[dict[str, Any]]:
    return [
        _layout("layout_daily_ops", "Daily Ops Cockpit", "daily-ops", ["panel_task_list", "panel_notifications", "panel_freshness", "panel_safe_next"], "panel_task_list"),
        _layout("layout_weekly_review", "Weekly Review Cockpit", "weekly-review", ["panel_task_list", "panel_review_packet", "panel_dependency", "panel_safe_next"], "panel_review_packet"),
        _layout("layout_task_triage", "Task Triage Cockpit", "task-triage", ["panel_task_list", "panel_task_detail", "panel_source_preview", "panel_saved_views"], "panel_task_list"),
        _layout("layout_blocked_tasks", "Blocked Task Cockpit", "blocked-task-review", ["panel_blocker", "panel_dependency", "panel_task_detail", "panel_safe_next"], "panel_blocker"),
        _layout("layout_source_review", "Source Review Cockpit", "source-review", ["panel_source_preview", "panel_task_detail", "panel_guided_step", "panel_safe_next"], "panel_source_preview"),
        _layout("layout_dataset", "Dataset Review Cockpit", "dataset-review", ["panel_dataset", "panel_task_list", "panel_review_packet", "panel_safe_next"], "panel_dataset"),
        _layout("layout_freshness", "Freshness Review Cockpit", "freshness-review", ["panel_freshness", "panel_notifications", "panel_task_list", "panel_safe_next"], "panel_freshness"),
        _layout("layout_simulation", "Simulation Review Cockpit", "simulation-review", ["panel_simulation", "panel_task_list", "panel_review_packet", "panel_safe_next"], "panel_simulation"),
        _layout("layout_analytics", "Analytics Review Cockpit", "analytics-review", ["panel_analytics", "panel_task_list", "panel_review_packet", "panel_safe_next"], "panel_analytics"),
        _layout("layout_governance", "Governance Review Cockpit", "governance-review", ["panel_governance", "panel_task_list", "panel_review_packet", "panel_safe_next"], "panel_governance"),
        _layout("layout_research", "Research Review Cockpit", "research-review", ["panel_research", "panel_source_preview", "panel_task_list", "panel_safe_next"], "panel_research"),
        _layout("layout_monitoring", "Monitoring Review Cockpit", "monitoring-review", ["panel_monitoring", "panel_notifications", "panel_task_list", "panel_safe_next"], "panel_monitoring"),
        _layout("layout_portfolio", "Portfolio Review Cockpit", "portfolio-review", ["panel_portfolio", "panel_task_list", "panel_dependency", "panel_safe_next"], "panel_portfolio"),
    ]


def _read_settings() -> dict[str, Any]:
    defaults = {
        "selected_layout_id": "layout_daily_ops",
        "active_focus_mode_id": "focus_daily_review",
        "keyboard_shortcuts_enabled": True,
        "command_palette_enabled": True,
        "cockpit_scans_on_startup": False,
        "safe_summary_refresh_mode": "manual",
        "layout_mutates_live_state": False,
        "command_palette_mutates_live_state": False,
        "keyboard_shortcuts_mutate_live_state": False,
        **_safety(),
    }
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(redact_data(data))
        except json.JSONDecodeError:
            defaults["settings_warning"] = "Settings file was invalid JSON; defaults were used."
    return redact_data(defaults)


def build_settings() -> dict[str, Any]:
    return _read_settings()


def update_settings(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    settings = _read_settings()
    allowed = {"selected_layout_id", "active_focus_mode_id", "keyboard_shortcuts_enabled", "command_palette_enabled", "safe_summary_refresh_mode"}
    for key in allowed:
        if key in payload:
            settings[key] = redact_data(payload[key])
    settings.update({"updated_at": _now(), **_safety()})
    _ensure_dir()
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _audit("cockpit_settings_changed", "ok", {"keys": sorted(k for k in payload if k in allowed)})
    return redact_data(settings)


def list_layouts(limit: int = 250) -> dict[str, Any]:
    rows = _latest_by_id(_read_jsonl(LAYOUTS_PATH), "layout_id")
    if not rows:
        rows = default_layouts()
    settings = _read_settings()
    selected = settings.get("selected_layout_id", "layout_daily_ops")
    for row in rows:
        row["selected"] = row.get("layout_id") == selected
    return {"items": redact_data(rows[: max(1, min(int(limit or 250), 5000))]), "count": len(rows), "selected_layout_id": selected, **_safety()}


def get_layout(layout_id: str) -> dict[str, Any] | None:
    for row in list_layouts(limit=5000)["items"]:
        if row.get("layout_id") == layout_id:
            return redact_data(row)
    return None


def create_layout(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    now = _now()
    panel_ids = _safe_list(payload.get("panel_ids")) or ["panel_task_list", "panel_task_detail", "panel_safe_next"]
    panel_lookup = {p["panel_id"]: p for p in default_panels()}
    panels = [panel_lookup.get(pid) or _default_panel(pid, "safe-next-actions", pid, "cockpit") for pid in panel_ids]
    layout = {
        "layout_id": _safe_text(payload.get("layout_id"), _record_id("layout")),
        "created_at": now,
        "updated_at": now,
        "app_version": APP_VERSION,
        "title": _safe_text(payload.get("title"), "Custom Cockpit Layout")[:180],
        "description": _safe_text(payload.get("description"), "Operator-created cockpit layout.")[:1000],
        "layout_type": _layout_type(payload.get("layout_type")),
        "panel_definitions": redact_data(panels),
        "panel_ids": [p["panel_id"] for p in panels],
        "default_focus_panel": _safe_text(payload.get("default_focus_panel"), panels[0]["panel_id"] if panels else "panel_safe_next"),
        "enabled": bool(payload.get("enabled", True)),
        "operator_notes": _safe_text(payload.get("operator_notes"), "")[:1000],
        "safety_statement": _safety()["safety_statement"],
        "audit_metadata": {"created_by": "operator", "safe_local_only": True},
        **_safety(),
    }
    _write_jsonl(LAYOUTS_PATH, layout)
    _audit("cockpit_layout_created", "ok", {"layout_id": layout["layout_id"]})
    return redact_data(layout)


def update_layout(layout_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    current = get_layout(layout_id)
    if not current:
        return {"ok": False, "error": "layout_not_found", **_safety()}
    update = {**current, "updated_at": _now()}
    for key in ["title", "description", "operator_notes", "default_focus_panel"]:
        if key in payload:
            update[key] = _safe_text(payload.get(key), str(update.get(key, "")))
    if "layout_type" in payload:
        update["layout_type"] = _layout_type(payload.get("layout_type"))
    if "panel_ids" in payload:
        panel_lookup = {p["panel_id"]: p for p in default_panels()}
        ids = _safe_list(payload.get("panel_ids")) or update.get("panel_ids", [])
        update["panel_ids"] = ids
        update["panel_definitions"] = [panel_lookup.get(pid) or _default_panel(pid, "safe-next-actions", pid, "cockpit") for pid in ids]
    if "enabled" in payload:
        update["enabled"] = bool(payload.get("enabled"))
    update.update(_safety())
    _write_jsonl(LAYOUTS_PATH, update)
    _audit("cockpit_layout_updated", "ok", {"layout_id": layout_id})
    return redact_data(update)


def save_current_layout_copy(title: str = "") -> dict[str, Any]:
    settings = _read_settings()
    selected = get_layout(settings.get("selected_layout_id", "layout_daily_ops")) or default_layouts()[0]
    safe_title = _safe_text(title, f"Saved copy of {selected.get('title', 'Cockpit Layout')}")[:180]
    payload = {
        "title": safe_title,
        "description": f"Operator-saved copy of {selected.get('title', 'the current cockpit layout')}.",
        "layout_type": selected.get("layout_type", "custom"),
        "panel_ids": selected.get("panel_ids", []),
        "default_focus_panel": selected.get("default_focus_panel", "panel_safe_next"),
        "operator_notes": "Saved from the v4.15.0 cockpit layout selector. Local-only workflow layout; not a trading action.",
        "enabled": True,
    }
    layout = create_layout(payload)
    select_layout(layout["layout_id"])
    _audit("cockpit_layout_saved_copy", "ok", {"layout_id": layout["layout_id"], "source_layout_id": selected.get("layout_id")})
    return {"ok": True, "layout": layout, "selected_layout_id": layout["layout_id"], **_safety()}


def select_layout(layout_id: str) -> dict[str, Any]:
    layout = get_layout(layout_id)
    if not layout:
        return {"ok": False, "error": "layout_not_found", **_safety()}
    settings = update_settings({"selected_layout_id": layout_id})
    _audit("cockpit_layout_selected", "ok", {"layout_id": layout_id})
    return {"ok": True, "selected_layout_id": layout_id, "layout": layout, "settings": settings, **_safety()}


def reset_default_layouts() -> dict[str, Any]:
    _ensure_dir()
    if LAYOUTS_PATH.exists():
        LAYOUTS_PATH.unlink()
    for layout in default_layouts():
        _write_jsonl(LAYOUTS_PATH, layout)
    _audit("cockpit_default_layouts_reset", "ok", {"layout_count": len(default_layouts())})
    return {"ok": True, "layouts": list_layouts(limit=5000), **_safety()}


def list_panels(limit: int = 250) -> dict[str, Any]:
    rows = _latest_by_id(_read_jsonl(PANELS_PATH), "panel_id")
    if not rows:
        rows = default_panels()
    return {"items": redact_data(rows[: max(1, min(int(limit or 250), 5000))]), "count": len(rows), **_safety()}


def create_panel(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    extra = dict(payload)
    for key in ["panel_id", "panel_type", "title", "source_subsystem"]:
        extra.pop(key, None)
    panel = _default_panel(
        _safe_text(payload.get("panel_id"), _record_id("panel")),
        _safe_text(payload.get("panel_type"), "safe-next-actions"),
        _safe_text(payload.get("title"), "Custom Cockpit Panel"),
        _safe_text(payload.get("source_subsystem"), "cockpit"),
        **extra,
    )
    panel["audit_metadata"] = {"created_by": "operator", "safe_local_only": True}
    _write_jsonl(PANELS_PATH, panel)
    _audit("cockpit_panel_created", "ok", {"panel_id": panel["panel_id"]})
    return redact_data(panel)


def keyboard_shortcuts() -> dict[str, Any]:
    shortcuts = [
        ("cmd+k", "open_command_palette", "Open command palette"),
        ("g c", "jump_cockpit", "Jump to cockpit"),
        ("g t", "jump_tasks", "Jump to tasks"),
        ("g w", "jump_workspace", "Jump to guided workspace"),
        ("g d", "jump_daily_review", "Jump to daily review"),
        ("g y", "jump_weekly_review", "Jump to weekly review"),
        ("g b", "jump_blocked_tasks", "Jump to blocked tasks"),
        ("g x", "jump_dependencies", "Jump to dependencies"),
        ("g s", "jump_source_preview", "Jump to source preview"),
        ("g p", "jump_review_packets", "Jump to review packets"),
        ("j", "focus_next_panel", "Focus next panel"),
        ("k", "focus_previous_panel", "Focus previous panel"),
        ("enter", "open_selected_detail", "Open selected item detail"),
        ("esc", "close_detail_panel", "Close detail panel"),
        ("r", "refresh_safe_summaries", "Refresh safe summaries manually"),
    ]
    items = [
        {
            "shortcut_id": f"shortcut_{action}",
            "keys": keys,
            "action": action,
            "description": description,
            "enabled": True,
            "safety_class": "informational",
            "mutates_live_trading_state": False,
            "places_orders": False,
            "cancels_orders": False,
            **_safety(),
        }
        for keys, action, description in shortcuts
    ]
    return {"items": redact_data(items), "count": len(items), "viewed_at": _now(), **_safety()}


def command_palette_actions() -> dict[str, Any]:
    specs = [
        ("navigate_cockpit", "Navigate to Cockpit", "navigate", "/v3/cockpit"),
        ("navigate_tasks", "Navigate to Tasks", "navigate", "/v3/tasks"),
        ("navigate_workspace", "Navigate to Guided Workspace", "navigate", "/v3/workspace"),
        ("open_daily_review", "Open Daily Review", "navigate", "/v3/workspace/daily-review"),
        ("open_weekly_review", "Open Weekly Review", "navigate", "/v3/workspace/weekly-review"),
        ("open_dependency_review", "Open Dependency Review", "navigate", "/v3/cockpit/dependencies"),
        ("open_source_preview", "Open Source Preview", "navigate", "/v3/cockpit/source"),
        ("open_saved_views", "Open Saved Views", "navigate", "/v3/workspace/saved-views"),
        ("open_review_packets", "Open Review Packets", "navigate", "/v3/cockpit/packets"),
        ("create_task", "Create Task", "local-task", "/api/v3/tasks"),
        ("create_task_from_template", "Create Task From Template", "local-task", "/api/v3/tasks/templates"),
        ("add_task_note", "Add Task Note", "local-task", "/api/v3/tasks/{task_id}"),
        ("change_task_status", "Change Task Status", "local-task", "/api/v3/tasks/{task_id}/status"),
        ("change_task_priority", "Change Task Priority", "local-task", "/api/v3/tasks/{task_id}"),
        ("set_task_due_date", "Set Task Due Date", "local-task", "/api/v3/tasks/{task_id}"),
        ("generate_review_packet", "Generate Review Packet", "local-report", "/api/v3/workspace/review-packets"),
        ("export_safe_report", "Export Safe Report", "local-report", "/api/v3/cockpit/export.md"),
        ("switch_cockpit_layout", "Switch Cockpit Layout", "layout", "/api/v3/cockpit/layouts/{id}/select"),
        ("show_keyboard_shortcuts", "Show Keyboard Shortcuts", "navigate", "/v3/cockpit/shortcuts"),
        ("open_cockpit_settings", "Open Cockpit Settings", "navigate", "/v3/cockpit/settings"),
    ]
    items = []
    for action_id, title, action_type, target in specs:
        items.append({
            "action_id": action_id,
            "title": title,
            "action_type": action_type,
            "target": target,
            "enabled": True,
            "safety_class": "review-only" if action_type != "navigate" else "informational",
            "does_not_mutate_live_trading_state": True,
            "places_orders": False,
            "cancels_orders": False,
            "requires_backend_gate_for_any_live_action": True,
            **_safety(),
        })
    return {"items": redact_data(items), "count": len(items), **_safety()}


def run_command_palette_action(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    action_id = _safe_text(payload.get("action_id"), "")
    normalized = action_id.lower().replace("-", "_")
    if normalized in FORBIDDEN_COMMAND_KEYWORDS or any(word in normalized for word in ["place_order", "cancel_order", "approve_trade", "sign_transaction", "arm_live", "disable_kill", "bypass_read_only"]):
        _audit("safe_command_palette_action_rejected", "blocked", {"action_id": action_id, "reason": "forbidden_live_mutation"})
        return {"ok": False, "status": "rejected", "reason": "forbidden_live_mutation", "action_id": action_id, **_safety()}
    actions = {a["action_id"]: a for a in command_palette_actions()["items"]}
    action = actions.get(action_id)
    if not action:
        return {"ok": False, "status": "not_found", "action_id": action_id, **_safety()}
    result = {"ok": True, "status": "ready", "action": action, "message": "Safe local command resolved. Operator must still use normal pages/APIs for any follow-through.", **_safety()}
    _audit("safe_command_palette_action_run", "ok", {"action_id": action_id})
    return redact_data(result)


def focus_modes() -> dict[str, Any]:
    specs = [
        ("focus_daily_review", "Daily Review Focus", "layout_daily_ops", "/v3/cockpit/focus", "Review daily safety, notifications, freshness, tasks, and safe next actions."),
        ("focus_weekly_review", "Weekly Review Focus", "layout_weekly_review", "/v3/cockpit/review", "Review weekly rollups, packets, blockers, and next-week focus."),
        ("focus_task_triage", "Task Triage Focus", "layout_task_triage", "/v3/cockpit/tasks", "Review source previews and task details side-by-side."),
        ("focus_blocked_tasks", "Blocked Task Focus", "layout_blocked_tasks", "/v3/cockpit/dependencies", "Inspect blockers and dependency chains."),
        ("focus_source_preview", "Source Preview Focus", "layout_source_review", "/v3/cockpit/source", "Preview source context before creating tasks."),
        ("focus_dependency_review", "Dependency Review Focus", "layout_blocked_tasks", "/v3/cockpit/dependencies", "Review workflow-only task dependencies."),
        ("focus_dataset_review", "Dataset Review Focus", "layout_dataset", "/v3/cockpit/review", "Review dataset readiness and follow-up tasks."),
        ("focus_freshness_review", "Freshness Review Focus", "layout_freshness", "/v3/cockpit/review", "Review stale findings and notifications."),
        ("focus_simulation_review", "Simulation Review Focus", "layout_simulation", "/v3/cockpit/review", "Review simulation follow-ups and packets."),
        ("focus_analytics_review", "Analytics Review Focus", "layout_analytics", "/v3/cockpit/review", "Review analytics warnings and learning reports."),
        ("focus_governance_review", "Governance Review Focus", "layout_governance", "/v3/cockpit/review", "Review governance checklist items."),
        ("focus_monitoring_review", "Monitoring Review Focus", "layout_monitoring", "/v3/cockpit/review", "Review monitoring alerts."),
        ("focus_research_review", "Research Review Focus", "layout_research", "/v3/cockpit/review", "Review research backlog and stale evidence."),
        ("focus_portfolio_review", "Portfolio Review Focus", "layout_portfolio", "/v3/cockpit/review", "Review portfolio and concentration warnings."),
    ]
    items = []
    for focus_id, title, layout_id, route, next_action in specs:
        layout = get_layout(layout_id) or next((x for x in default_layouts() if x["layout_id"] == layout_id), None)
        items.append({
            "focus_mode_id": focus_id,
            "created_at": _now(),
            "updated_at": _now(),
            "app_version": APP_VERSION,
            "title": title,
            "layout_id": layout_id,
            "layout": layout,
            "entry_route": route,
            "relevant_panels": layout.get("panel_ids", []) if layout else [],
            "suggested_next_safe_action": next_action,
            "unknown_unavailable_data": ["Runtime source/task/review records may be unavailable until the operator creates local records."],
            "safety_statement": _safety()["safety_statement"],
            **_safety(),
        })
    return {"items": redact_data(items), "count": len(items), **_safety()}


def get_focus_mode(focus_id: str) -> dict[str, Any] | None:
    for item in focus_modes()["items"]:
        if item.get("focus_mode_id") == focus_id:
            return item
    return None


def start_focus_mode(focus_id: str) -> dict[str, Any]:
    focus = get_focus_mode(focus_id)
    if not focus:
        return {"ok": False, "error": "focus_mode_not_found", **_safety()}
    update_settings({"active_focus_mode_id": focus_id, "selected_layout_id": focus.get("layout_id")})
    snapshot = {
        "snapshot_id": _record_id("cockpit_snapshot"),
        "created_at": _now(),
        "updated_at": _now(),
        "app_version": APP_VERSION,
        "focus_mode_id": focus_id,
        "layout_id": focus.get("layout_id"),
        "title": focus.get("title"),
        "status": "active",
        "safe_local_only": True,
        **_safety(),
    }
    _write_jsonl(SESSION_SNAPSHOTS_PATH, snapshot)
    _audit("cockpit_focus_mode_started", "ok", {"focus_mode_id": focus_id, "layout_id": focus.get("layout_id")})
    return {"ok": True, "focus_mode": focus, "snapshot": snapshot, **_safety()}


def _workspace_summary() -> dict[str, Any]:
    try:
        from . import live_v3_workspace as workspace
        return workspace.workspace_summary()
    except Exception as exc:
        return {"warning": redact_text(str(exc)), "secret_values_returned": False}


def _task_summary() -> dict[str, Any]:
    try:
        from .live_v3_tasks import task_summary
        return task_summary()
    except Exception as exc:
        return {"warning": redact_text(str(exc)), "secret_values_returned": False}


def dependency_view(task_id: str = "") -> dict[str, Any]:
    deps: list[dict[str, Any]] = []
    try:
        from . import live_v3_workspace as workspace
        deps = workspace.list_dependencies(limit=5000).get("items", [])
    except Exception:
        deps = []
    selected = _safe_text(task_id, "")
    depends_on = [d for d in deps if not selected or d.get("task_id") == selected]
    blocked_by = [d for d in deps if selected and d.get("depends_on_task_id") == selected]
    unresolved = [d for d in deps if d.get("status") not in {"done", "resolved", "archived"}]
    return {
        "selected_task_id": selected,
        "dependencies": redact_data(deps),
        "depends_on": redact_data(depends_on),
        "tasks_blocked_by_selected": redact_data(blocked_by),
        "unresolved_blockers": redact_data(unresolved),
        "completed_dependencies": [d for d in deps if d.get("status") in {"done", "resolved"}],
        "dependency_warnings": len(unresolved),
        "related_source_previews": source_context().get("items", [])[:10],
        "related_review_packets": review_packets_context().get("items", [])[:10],
        "count": len(deps),
        **_safety(),
    }


def source_context() -> dict[str, Any]:
    try:
        from . import live_v3_workspace as workspace
        previews = workspace.list_source_previews(limit=250).get("items", [])
    except Exception:
        previews = []
    return {"items": redact_data(previews), "count": len(previews), "unknown_unavailable_data": [] if previews else ["No source previews have been generated yet."], **_safety()}


def review_packets_context() -> dict[str, Any]:
    try:
        from . import live_v3_workspace as workspace
        packets = workspace.list_review_packets(limit=250).get("items", [])
    except Exception:
        packets = []
    return {"items": redact_data(packets), "count": len(packets), "unknown_unavailable_data": [] if packets else ["No guided review packets have been generated yet."], **_safety()}


def cockpit_summary() -> dict[str, Any]:
    settings = _read_settings()
    layouts = list_layouts(limit=5000)
    selected_layout_id = settings.get("selected_layout_id", "layout_daily_ops")
    focus_id = settings.get("active_focus_mode_id", "focus_daily_review")
    deps = dependency_view()
    source = source_context()
    packets = review_packets_context()
    shortcuts = keyboard_shortcuts()
    commands = command_palette_actions()
    workspace = _workspace_summary()
    tasks = _task_summary()
    return {
        "app_version": APP_VERSION,
        "generated_at": _now(),
        "active_cockpit_layout": selected_layout_id,
        "active_focus_mode": focus_id,
        "cockpit_saved_layouts_count": layouts.get("count", 0),
        "available_shortcuts_count": shortcuts.get("count", 0),
        "command_palette_safe_actions_count": commands.get("count", 0),
        "active_guided_review_session": workspace.get("active_guided_review_session"),
        "blocked_task_count": tasks.get("blocked_tasks", workspace.get("blocked_task_count", 0)),
        "dependency_warning_count": deps.get("dependency_warnings", 0),
        "overdue_task_count": tasks.get("overdue_tasks", 0),
        "source_previews_awaiting_review": source.get("count", 0),
        "latest_review_packet": packets.get("items", [{}])[0] if packets.get("items") else None,
        "selected_layout": get_layout(selected_layout_id),
        "selected_focus_mode": get_focus_mode(focus_id),
        "warnings": [],
        **_safety(),
    }


def build_cockpit_context() -> dict[str, Any]:
    settings = _read_settings()
    selected = get_layout(settings.get("selected_layout_id", "layout_daily_ops")) or default_layouts()[0]
    return {
        "summary": cockpit_summary(),
        "settings": settings,
        "layouts": list_layouts(limit=500),
        "selected_layout": selected,
        "panels": list_panels(limit=500),
        "focus_modes": focus_modes(),
        "shortcuts": keyboard_shortcuts(),
        "command_palette": command_palette_actions(),
        "dependency_view": dependency_view(),
        "source_context": source_context(),
        "review_packets": review_packets_context(),
        "task_summary": _task_summary(),
        "workspace_summary": _workspace_summary(),
        **_safety(),
    }


def export_json() -> dict[str, Any]:
    export = {
        "export_id": _record_id("cockpit_export"),
        "created_at": _now(),
        "app_version": APP_VERSION,
        "kind": "cockpit_full_export",
        "summary": cockpit_summary(),
        "layouts": list_layouts(limit=5000).get("items", []),
        "focus_modes": focus_modes().get("items", []),
        "panels": list_panels(limit=5000).get("items", []),
        "shortcuts": keyboard_shortcuts().get("items", []),
        "command_palette": command_palette_actions().get("items", []),
        "dependencies": dependency_view(),
        "source_context": source_context(),
        "review_packets": review_packets_context(),
        "included_layout_ids": [x.get("layout_id") for x in list_layouts(limit=5000).get("items", [])],
        "included_panel_ids": [x.get("panel_id") for x in list_panels(limit=5000).get("items", [])],
        "related_task_ids": [],
        "related_object_ids": [],
        "status_summary": "Cockpit export generated locally. It is a workflow/navigation aid only.",
        "blockers": dependency_view().get("unresolved_blockers", []),
        "warnings": ["Cockpit exports do not contain runtime secrets and do not perform live actions."],
        "limitations": ["Side-by-side context is based on available local summaries only."],
        "unknown_unavailable_data": ["Missing runtime records are represented explicitly rather than invented."],
        **_safety(),
    }
    _write_jsonl(EXPORT_MANIFESTS_PATH, {"export_id": export["export_id"], "created_at": export["created_at"], "kind": export["kind"], **_safety()})
    _audit("cockpit_export_generated", "ok", {"kind": "json"})
    return redact_data(export)


def export_markdown() -> str:
    summary = cockpit_summary()
    lines = [
        "# Cockpit Layout Report",
        "",
        f"Version: {APP_VERSION}",
        f"Generated: {_now()}",
        "",
        "Cockpit views, layouts, command-palette actions, and keyboard shortcuts do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, or provide financial advice.",
        "",
        "## Summary",
        f"- Active layout: {summary.get('active_cockpit_layout')}",
        f"- Active focus mode: {summary.get('active_focus_mode')}",
        f"- Saved layouts: {summary.get('cockpit_saved_layouts_count')}",
        f"- Safe command actions: {summary.get('command_palette_safe_actions_count')}",
        f"- Shortcuts: {summary.get('available_shortcuts_count')}",
        f"- Dependency warnings: {summary.get('dependency_warning_count')}",
        "",
        "## Layouts",
    ]
    for layout in list_layouts(limit=5000).get("items", []):
        lines.append(f"- **{layout.get('title')}** (`{layout.get('layout_id')}`): {len(layout.get('panel_ids', []))} panels; selected={layout.get('selected', False)}")
    lines.extend(["", "## Safety", "No cockpit, shortcut, layout, command-palette, dependency, guided review, task, cadence, saved view, or packet button places or cancels orders.", ""])
    _audit("cockpit_export_generated", "ok", {"kind": "markdown"})
    return "\n".join(lines)


def export_focus_mode_json() -> dict[str, Any]:
    return {"export_id": _record_id("focus_export"), "created_at": _now(), "app_version": APP_VERSION, "focus_modes": focus_modes().get("items", []), **_safety()}


def export_focus_mode_markdown() -> str:
    lines = ["# Cockpit Focus Mode Report", "", f"Version: {APP_VERSION}", "", "Focus modes are navigation/layout aids only.", ""]
    for focus in focus_modes().get("items", []):
        lines.append(f"- **{focus.get('title')}** (`{focus.get('focus_mode_id')}`) → {focus.get('layout_id')}: {focus.get('suggested_next_safe_action')}")
    return "\n".join(lines) + "\n"


def export_command_palette_json() -> dict[str, Any]:
    return {"export_id": _record_id("command_export"), "created_at": _now(), "app_version": APP_VERSION, "command_palette": command_palette_actions().get("items", []), **_safety()}


def export_command_palette_markdown() -> str:
    lines = ["# Command Palette Safety Report", "", f"Version: {APP_VERSION}", "", "Command-palette actions are restricted to safe local navigation, task/workflow records, layout switching, and exports. They do not place or cancel orders.", ""]
    for action in command_palette_actions().get("items", []):
        lines.append(f"- `{action.get('action_id')}` — {action.get('title')} ({action.get('action_type')})")
    return "\n".join(lines) + "\n"


def export_shortcuts_json() -> dict[str, Any]:
    return {"export_id": _record_id("shortcut_export"), "created_at": _now(), "app_version": APP_VERSION, "shortcuts": keyboard_shortcuts().get("items", []), **_safety()}


def export_shortcuts_markdown() -> str:
    lines = ["# Keyboard Shortcut Report", "", f"Version: {APP_VERSION}", "", "Keyboard shortcuts are safe navigation/local workflow shortcuts only. They do not place or cancel orders.", ""]
    for shortcut in keyboard_shortcuts().get("items", []):
        lines.append(f"- `{shortcut.get('keys')}` — {shortcut.get('description')}")
    return "\n".join(lines) + "\n"


def export_csv(kind: str = "layouts") -> str:
    kind = _safe_text(kind, "layouts")
    if kind == "command_palette":
        rows = command_palette_actions().get("items", [])
        fields = ["action_id", "title", "action_type", "target", "safety_class", "does_not_mutate_live_trading_state"]
    elif kind == "shortcuts":
        rows = keyboard_shortcuts().get("items", [])
        fields = ["shortcut_id", "keys", "action", "description", "enabled", "safety_class"]
    elif kind == "panels":
        rows = list_panels(limit=5000).get("items", [])
        fields = ["panel_id", "panel_type", "title", "source_subsystem", "refresh_mode", "safety_class"]
    else:
        rows = list_layouts(limit=5000).get("items", [])
        fields = ["layout_id", "title", "description", "layout_type", "panel_ids", "default_focus_panel", "enabled"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in redact_data(row).items()})
    _audit("cockpit_export_generated", "ok", {"kind": f"csv:{kind}"})
    return output.getvalue()


def cockpit_search_items(limit: int = 250) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layout in list_layouts(limit=limit).get("items", []):
        rows.append({"result_id": f"cockpit_layout:{layout.get('layout_id')}", "result_type": "cockpit_layout", "title": layout.get("title"), "summary": layout.get("description"), "status": "enabled" if layout.get("enabled") else "disabled", "timestamp": layout.get("updated_at"), "url": "/v3/cockpit/layouts", "quick_link": "/v3/cockpit/layouts", "tags": [layout.get("layout_type", "")], "search_text": f"cockpit layout {layout.get('title','')} {layout.get('layout_type','')} {layout.get('description','')}", "secret_values_returned": False})
    for panel in list_panels(limit=limit).get("items", []):
        rows.append({"result_id": f"cockpit_panel:{panel.get('panel_id')}", "result_type": "cockpit_panel", "title": panel.get("title"), "summary": panel.get("panel_type"), "status": panel.get("refresh_mode"), "timestamp": panel.get("updated_at"), "url": "/v3/cockpit", "quick_link": "/v3/cockpit", "tags": [panel.get("source_subsystem", "")], "search_text": f"cockpit panel {panel.get('title','')} {panel.get('panel_type','')} {panel.get('source_subsystem','')}", "secret_values_returned": False})
    for focus in focus_modes().get("items", [])[:limit]:
        rows.append({"result_id": f"cockpit_focus_mode:{focus.get('focus_mode_id')}", "result_type": "cockpit_focus_mode", "title": focus.get("title"), "summary": focus.get("suggested_next_safe_action"), "status": "available", "timestamp": focus.get("updated_at"), "url": focus.get("entry_route"), "quick_link": focus.get("entry_route"), "tags": [focus.get("layout_id", "")], "search_text": f"cockpit focus mode {focus.get('title','')} {focus.get('layout_id','')}", "secret_values_returned": False})
    for shortcut in keyboard_shortcuts().get("items", [])[:limit]:
        rows.append({"result_id": f"keyboard_shortcut:{shortcut.get('shortcut_id')}", "result_type": "keyboard_shortcut", "title": shortcut.get("description"), "summary": shortcut.get("keys"), "status": "enabled" if shortcut.get("enabled") else "disabled", "timestamp": _now(), "url": "/v3/cockpit/shortcuts", "quick_link": "/v3/cockpit/shortcuts", "tags": ["shortcut"], "search_text": f"keyboard shortcut {shortcut.get('keys','')} {shortcut.get('description','')}", "secret_values_returned": False})
    for action in command_palette_actions().get("items", [])[:limit]:
        rows.append({"result_id": f"command_palette_action:{action.get('action_id')}", "result_type": "command_palette_action", "title": action.get("title"), "summary": action.get("action_type"), "status": "enabled" if action.get("enabled") else "disabled", "timestamp": _now(), "url": "/v3/cockpit/command-palette", "quick_link": "/v3/cockpit/command-palette", "tags": ["command_palette"], "search_text": f"command palette action {action.get('action_id','')} {action.get('title','')} {action.get('action_type','')}", "secret_values_returned": False})
    rows.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    return redact_data(rows[: max(1, min(int(limit or 250), 5000))])


def cockpit_graph_nodes_edges() -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for layout in list_layouts(limit=500).get("items", []):
        lid = f"cockpit_layout:{layout.get('layout_id')}"
        nodes.append({"node_id": lid, "node_type": "cockpit_layout", "title": layout.get("title"), "status": "enabled" if layout.get("enabled") else "disabled", "timestamp": layout.get("updated_at"), "summary": layout.get("description"), "secret_values_returned": False})
        for panel_id in layout.get("panel_ids", []) if isinstance(layout.get("panel_ids"), list) else []:
            edges.append({"edge_id": f"edge:{lid}:includes:cockpit_panel:{panel_id}", "from": lid, "to": f"cockpit_panel:{panel_id}", "relationship": "includes", "secret_values_returned": False})
    for panel in list_panels(limit=500).get("items", []):
        nodes.append({"node_id": f"cockpit_panel:{panel.get('panel_id')}", "node_type": "cockpit_panel", "title": panel.get("title"), "status": panel.get("refresh_mode"), "timestamp": panel.get("updated_at"), "summary": panel.get("panel_type"), "secret_values_returned": False})
    for focus in focus_modes().get("items", []):
        fid = f"cockpit_focus_mode:{focus.get('focus_mode_id')}"
        nodes.append({"node_id": fid, "node_type": "cockpit_focus_mode", "title": focus.get("title"), "status": "available", "timestamp": focus.get("updated_at"), "summary": focus.get("suggested_next_safe_action"), "secret_values_returned": False})
        edges.append({"edge_id": f"edge:{fid}:focuses:cockpit_layout:{focus.get('layout_id')}", "from": fid, "to": f"cockpit_layout:{focus.get('layout_id')}", "relationship": "focuses", "secret_values_returned": False})
    for action in command_palette_actions().get("items", []):
        nodes.append({"node_id": f"command_palette_action:{action.get('action_id')}", "node_type": "command_palette_action", "title": action.get("title"), "status": "safe", "timestamp": _now(), "summary": action.get("target"), "secret_values_returned": False})
    for shortcut in keyboard_shortcuts().get("items", []):
        nodes.append({"node_id": f"keyboard_shortcut:{shortcut.get('shortcut_id')}", "node_type": "keyboard_shortcut", "title": shortcut.get("keys"), "status": "enabled", "timestamp": _now(), "summary": shortcut.get("description"), "secret_values_returned": False})
    return {"nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), **_safety()}


def create_demo_cockpit_records(write_runtime: bool = True) -> dict[str, Any]:
    layout = default_layouts()[0]
    panel = default_panels()[0]
    focus = focus_modes().get("items", [])[0]
    command = command_palette_actions().get("items", [])[0]
    shortcut = keyboard_shortcuts().get("items", [])[0]
    fixture = {"layout": layout, "panel": panel, "focus_mode": focus, "command": command, "shortcut": shortcut, "dependency_visualization": dependency_view()}
    if write_runtime:
        _write_jsonl(LAYOUTS_PATH, layout)
        _write_jsonl(PANELS_PATH, panel)
        start_focus_mode(focus["focus_mode_id"])
    return {"version": APP_VERSION, "created": redact_data(fixture), "demo_data_is_fake": True, "contains_sensitive_values": False, **_safety()}


def demo_fixture() -> dict[str, Any]:
    return {
        "operator_cockpit": {
            "fake_cockpit_daily_ops_layout": default_layouts()[0],
            "fake_cockpit_weekly_review_layout": default_layouts()[1],
            "fake_cockpit_task_triage_layout": default_layouts()[2],
            "fake_cockpit_blocked_task_layout": default_layouts()[3],
            "fake_cockpit_source_review_layout": default_layouts()[4],
            "fake_cockpit_panel_set": default_panels()[:4],
            "fake_command_palette_action_manifest": command_palette_actions().get("items", [])[:5],
            "fake_keyboard_shortcut_manifest": keyboard_shortcuts().get("items", [])[:5],
            "fake_cockpit_export_manifest": {"export_id": "demo-cockpit-export-v39", "kind": "cockpit_layout", **_safety()},
            "fake_dependency_visualization_example": {"nodes": [{"node_id": "operator_task:demo"}], "edges": [{"from": "operator_task:demo", "to": "operator_task:prereq", "relationship": "depends_on"}], **_safety()},
            "safe_demo_data": True,
            "contains_sensitive_values": False,
        },
        **_safety(),
    }
