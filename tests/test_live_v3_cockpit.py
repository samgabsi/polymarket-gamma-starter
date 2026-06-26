from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import APP_VERSION
from app.main import app
from app import auth, live_v2, live_v3, live_v3_tasks, live_v3_workspace, live_v3_cockpit


@pytest.fixture(autouse=True)
def isolated_cockpit(tmp_path, monkeypatch):
    live_dir = tmp_path / "live_v2"
    tasks_dir = tmp_path / "live_v3" / "tasks"
    workspace_dir = tmp_path / "live_v3" / "workspace"
    cockpit_dir = tmp_path / "live_v3" / "cockpit"
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", live_dir)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", live_dir / "audit_ledger.jsonl")
    monkeypatch.setattr(live_v3_tasks, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(live_v3_tasks, "TASK_EVENTS_PATH", tasks_dir / "task_events.jsonl")
    monkeypatch.setattr(live_v3_tasks, "TASKS_PATH", tasks_dir / "operator_tasks.jsonl")
    monkeypatch.setattr(live_v3_tasks, "INBOX_PATH", tasks_dir / "task_inbox.jsonl")
    monkeypatch.setattr(live_v3_tasks, "TEMPLATES_PATH", tasks_dir / "task_templates.jsonl")
    monkeypatch.setattr(live_v3_tasks, "CADENCE_PATH", tasks_dir / "cadence_rules.jsonl")
    monkeypatch.setattr(live_v3_tasks, "CADENCE_EVENTS_PATH", tasks_dir / "cadence_events.jsonl")
    monkeypatch.setattr(live_v3_tasks, "DAILY_OPS_PATH", tasks_dir / "daily_ops_packets.jsonl")
    monkeypatch.setattr(live_v3_tasks, "WEEKLY_OPS_PATH", tasks_dir / "weekly_ops_packets.jsonl")
    monkeypatch.setattr(live_v3_tasks, "SETTINGS_PATH", tasks_dir / "settings.json")
    monkeypatch.setattr(live_v3_tasks, "EXPORT_MANIFESTS_PATH", tasks_dir / "export_manifests.jsonl")
    monkeypatch.setattr(live_v3_workspace, "WORKSPACE_DIR", workspace_dir)
    monkeypatch.setattr(live_v3_workspace, "WORKSPACE_EVENTS_PATH", workspace_dir / "workspace_events.jsonl")
    monkeypatch.setattr(live_v3_workspace, "FLOWS_PATH", workspace_dir / "guided_review_flows.jsonl")
    monkeypatch.setattr(live_v3_workspace, "SESSIONS_PATH", workspace_dir / "guided_review_sessions.jsonl")
    monkeypatch.setattr(live_v3_workspace, "PACKETS_PATH", workspace_dir / "guided_review_packets.jsonl")
    monkeypatch.setattr(live_v3_workspace, "DEPENDENCIES_PATH", workspace_dir / "task_dependencies.jsonl")
    monkeypatch.setattr(live_v3_workspace, "SOURCE_PREVIEWS_PATH", workspace_dir / "source_previews.jsonl")
    monkeypatch.setattr(live_v3_workspace, "SAVED_VIEWS_PATH", workspace_dir / "saved_task_views.jsonl")
    monkeypatch.setattr(live_v3_workspace, "SETTINGS_PATH", workspace_dir / "settings.json")
    monkeypatch.setattr(live_v3_workspace, "EXPORT_MANIFESTS_PATH", workspace_dir / "export_manifests.jsonl")
    monkeypatch.setattr(live_v3_cockpit, "COCKPIT_DIR", cockpit_dir)
    monkeypatch.setattr(live_v3_cockpit, "COCKPIT_EVENTS_PATH", cockpit_dir / "cockpit_events.jsonl")
    monkeypatch.setattr(live_v3_cockpit, "LAYOUTS_PATH", cockpit_dir / "cockpit_layouts.jsonl")
    monkeypatch.setattr(live_v3_cockpit, "PANELS_PATH", cockpit_dir / "cockpit_panels.jsonl")
    monkeypatch.setattr(live_v3_cockpit, "SETTINGS_PATH", cockpit_dir / "settings.json")
    monkeypatch.setattr(live_v3_cockpit, "SESSION_SNAPSHOTS_PATH", cockpit_dir / "session_snapshots.jsonl")
    monkeypatch.setattr(live_v3_cockpit, "EXPORT_MANIFESTS_PATH", cockpit_dir / "export_manifests.jsonl")
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/cockpit"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_v39_version():
    assert APP_VERSION == "4.17.0-real"


def test_cockpit_layout_focus_shortcuts_commands_exports_are_safe():
    layouts = live_v3_cockpit.list_layouts()
    assert layouts["count"] >= 10
    layout = live_v3_cockpit.create_layout({"title": "Custom cockpit", "layout_type": "custom", "panel_ids": ["panel_task_list", "panel_safe_next"]})
    assert layout["order_submitted"] is False
    updated = live_v3_cockpit.update_layout(layout["layout_id"], {"operator_notes": "updated"})
    assert updated["layout_id"] == layout["layout_id"]
    selected = live_v3_cockpit.select_layout(layout["layout_id"])
    assert selected["ok"] is True
    reset = live_v3_cockpit.reset_default_layouts()
    assert reset["live_trading_armed"] is False

    focus = live_v3_cockpit.start_focus_mode("focus_daily_review")
    assert focus["ok"] is True
    panel = live_v3_cockpit.create_panel({"title": "Custom panel", "panel_type": "task-list", "source_subsystem": "validation"})
    assert panel["mutates_live_trading_state"] is False
    shortcuts = live_v3_cockpit.keyboard_shortcuts()
    commands = live_v3_cockpit.command_palette_actions()
    assert shortcuts["keyboard_shortcuts_do_not_place_or_cancel_orders"] is True
    assert commands["command_palette_actions_do_not_place_or_cancel_orders"] is True
    safe = live_v3_cockpit.run_command_palette_action({"action_id": "navigate_cockpit"})
    forbidden = live_v3_cockpit.run_command_palette_action({"action_id": "place_order"})
    assert safe["ok"] is True
    assert safe["order_cancelled"] is False
    assert forbidden["status"] == "rejected"

    dep = live_v3_workspace.create_dependency({"task_id": "cockpit-task", "depends_on_task_id": "cockpit-prereq"})
    view = live_v3_cockpit.dependency_view("cockpit-task")
    assert view["dependency_warnings"] >= 1
    preview = live_v3_workspace.create_source_preview({"title": "Cockpit source", "source_subsystem": "freshness"}, write=True)
    assert live_v3_cockpit.source_context()["count"] >= 1
    export = live_v3_cockpit.export_json()
    md = live_v3_cockpit.export_markdown()
    assert export["secret_values_returned"] is False
    assert "private_key" not in json.dumps(export).lower()
    assert "do not place" in md.lower() or "does not place" in md.lower()
    assert "layout_id" in live_v3_cockpit.export_csv("layouts")
    assert "action_id" in live_v3_cockpit.export_csv("command_palette")
    assert "shortcut_id" in live_v3_cockpit.export_csv("shortcuts")


def test_cockpit_integrates_with_search_graph_workflows_demo():
    live_v3_cockpit.create_demo_cockpit_records(write_runtime=True)
    search = live_v3.search_local("cockpit", limit=500)
    assert any(item.get("result_type") in {"cockpit_layout", "cockpit_panel", "cockpit_focus_mode", "command_palette_action", "keyboard_shortcut"} for item in search["items"])
    graph = live_v3.build_decision_graph(limit=500)
    assert graph.get("cockpit_nodes", 0) >= 1
    command = live_v3.build_command_center()
    assert "cockpit" in command["groups"]
    templates = live_v3.workflow_templates()
    assert any(t["workflow_id"] == "cockpit_layout_review" for t in templates["templates"])
    run = live_v3.run_workflow({"workflow_id": "cockpit_command_palette_safety_review"})
    assert run["status"] == "completed"
    assert run["order_submitted"] is False
    fixture = live_v3.build_demo_fixture()
    assert fixture["operator_cockpit"]["safe_demo_data"] is True


def test_cockpit_routes_and_apis_render(authed_client):
    for route in ["/v3/cockpit", "/v3/cockpit/dependencies", "/v3/cockpit/command-palette"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.17.0-real" in response.text
        assert "Cockpit" in response.text or "cockpit" in response.text
        assert "do not place" in response.text or "not trade approval" in response.text

    assert authed_client.get("/api/v3/cockpit/summary").status_code == 200
    layout = authed_client.post("/api/v3/cockpit/layouts", json={"title": "API layout", "layout_type": "custom"})
    assert layout.status_code == 200
    layout_id = layout.json()["layout_id"]
    assert authed_client.get("/api/v3/cockpit/layouts").status_code == 200
    assert authed_client.get(f"/api/v3/cockpit/layouts/{layout_id}").status_code == 200
    assert authed_client.post(f"/api/v3/cockpit/layouts/{layout_id}", json={"operator_notes": "api"}).status_code == 200
    assert authed_client.post(f"/api/v3/cockpit/layouts/{layout_id}/select").status_code == 200
    assert authed_client.post("/api/v3/cockpit/layouts/reset-defaults").status_code == 200
    assert authed_client.get("/api/v3/cockpit/focus-modes").status_code == 200
    assert authed_client.get("/api/v3/cockpit/focus-modes/focus_daily_review").status_code == 200
    assert authed_client.post("/api/v3/cockpit/focus-modes/focus_daily_review/start").status_code == 200
    assert authed_client.get("/api/v3/cockpit/panels").status_code == 200
    assert authed_client.post("/api/v3/cockpit/panels", json={"title": "API panel", "panel_type": "task-list"}).status_code == 200
    assert authed_client.get("/api/v3/cockpit/shortcuts").status_code == 200
    assert authed_client.get("/api/v3/cockpit/command-palette").status_code == 200
    safe = authed_client.post("/api/v3/cockpit/command-palette/run", json={"action_id": "navigate_cockpit"})
    assert safe.status_code == 200 and safe.json()["ok"] is True
    forbidden = authed_client.post("/api/v3/cockpit/command-palette/run", json={"action_id": "place_order"})
    assert forbidden.status_code == 200 and forbidden.json()["status"] == "rejected"
    assert authed_client.get("/api/v3/cockpit/dependencies").status_code == 200
    assert authed_client.get("/api/v3/cockpit/source-context").status_code == 200
    for route in ["/api/v3/cockpit/export.json", "/api/v3/cockpit/export.md", "/api/v3/cockpit/export/command-palette.md", "/api/v3/cockpit/export/shortcuts.md", "/api/v3/cockpit/export/layouts.csv"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "private_key" not in response.text.lower()


def test_v410_layout_selector_cards_select_persist_and_render(authed_client):
    page = authed_client.get("/v3/cockpit")
    assert page.status_code == 200
    assert "Layout Selector" in page.text
    assert "selectable + persistent" in page.text
    assert "data-v3-layout-card" in page.text

    response = authed_client.post("/v3/cockpit/layouts/layout_weekly_review/select", follow_redirects=False)
    assert response.status_code in {303, 307}
    settings = live_v3_cockpit.build_settings()
    assert settings["selected_layout_id"] == "layout_weekly_review"

    refreshed = authed_client.get("/v3/cockpit")
    assert refreshed.status_code == 200
    assert "Weekly Review Cockpit" in refreshed.text
    assert "selected" in refreshed.text
    assert "panel_review_packet" in refreshed.text


def test_v410_focus_modes_start_navigate_and_feature_status_is_honest(authed_client):
    focus = authed_client.post("/v3/cockpit/focus-modes/focus_task_triage/start", follow_redirects=False)
    assert focus.status_code in {303, 307}
    assert "/v3/cockpit/tasks" in focus.headers.get("location", "")
    settings = live_v3_cockpit.build_settings()
    assert settings["selected_layout_id"] == "layout_task_triage"
    assert settings["active_focus_mode_id"] == "focus_task_triage"

    saved = authed_client.post("/v3/cockpit/layouts/save-selected", data={"title": "Operator saved triage"}, follow_redirects=False)
    assert saved.status_code in {303, 307}
    assert live_v3_cockpit.build_settings()["selected_layout_id"].startswith("layout_") or live_v3_cockpit.build_settings()["selected_layout_id"].startswith("cockpit")

    status = authed_client.get("/api/v3/features/status")
    assert status.status_code == 200
    body = status.json()
    statuses = {row["feature_id"]: row["status"] for row in body["items"]}
    assert statuses["cockpit.layout_selector"] == "working"
    assert statuses["cockpit.focus_modes"] == "working"
    assert statuses["opportunity.review_actions"] == "working"
    assert statuses["ai.odds_page_actions"] == "working"
    assert statuses["arbitrage.review_actions"] == "working"
    assert statuses["settings.ai_arbitrage_config"] == "working"
    assert statuses["arbitrage.kalshi_adapter"] in {"disabled", "config_required", "partial"}
    assert body["order_submitted"] is False
