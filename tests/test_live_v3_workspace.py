from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_v2, live_v3, live_v3_workspace, live_v3_tasks
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    live_dir = tmp_path / "live_v2"
    tasks_dir = tmp_path / "live_v3" / "tasks"
    workspace_dir = tmp_path / "live_v3" / "workspace"
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
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/workspace"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_v38_version():
    assert APP_VERSION == "4.17.0-real"


def test_guided_flow_session_dependency_preview_saved_view_packet_exports_are_safe():
    flows = live_v3_workspace.list_guided_flows()
    assert flows["count"] >= 10
    flow = live_v3_workspace.create_guided_flow({"title": "Custom review", "flow_type": "custom", "target_subsystem": "validation", "steps": ["Review", "Packet"]})
    started = live_v3_workspace.start_flow(flow["flow_id"])
    assert started["ok"] is True
    assert started["order_submitted"] is False
    session_id = started["session"]["session_id"]
    step = live_v3_workspace.update_session_step(session_id, {"step_id": "step_01", "unresolved_items": ["Need source review"]})
    assert "step_01" in step["completed_steps"]
    complete = live_v3_workspace.complete_session(session_id)
    assert complete["guided_review_completion_is_not_trade_approval"] is True
    assert complete["order_cancelled"] is False
    abandoned = live_v3_workspace.start_task_triage({"title": "Triage to abandon"})
    abandon = live_v3_workspace.abandon_session(abandoned["session"]["session_id"], {"notes": "stop"})
    assert abandon["status"] == "abandoned"

    task = live_v3_tasks.create_task({"title": "Blocked workspace task", "status": "planned"})
    prereq = live_v3_tasks.create_task({"title": "Prerequisite workspace task", "status": "planned"})
    dep = live_v3_workspace.create_dependency({"task_id": task["task_id"], "depends_on_task_id": prereq["task_id"]})
    assert dep["dependency_id"]
    assert dep["live_trading_armed"] is False
    deleted = live_v3_workspace.delete_dependency(dep["dependency_id"])
    assert deleted["ok"] is True

    blocked = live_v3_workspace.blocked_review(write=True)
    assert blocked["packet"]["order_submitted"] is False
    preview = live_v3_workspace.create_source_preview({"title": "Preview finding", "source_subsystem": "freshness", "severity": "warning"}, write=True)
    assert preview["preview_id"]
    view = live_v3_workspace.create_saved_view({"title": "Blocked only", "filters": {"status": "blocked"}})
    assert view["view_id"]
    packet = live_v3_workspace.generate_review_packet({"title": "Dependency review", "packet_type": "dependency-review", "included_task_ids": [task["task_id"]]}, write=True)
    assert packet["packets_do_not_place_or_cancel_orders"] is True

    exported = live_v3_workspace.export_json()
    md = live_v3_workspace.export_markdown()
    dep_export = live_v3_workspace.export_dependency_json()
    saved_export = live_v3_workspace.export_saved_views_json()
    csv_text = live_v3_workspace.export_csv("dependencies")
    dumped = json.dumps(exported).lower()
    assert exported["secret_values_returned"] is False
    assert dep_export["secret_values_returned"] is False
    assert saved_export["secret_values_returned"] is False
    assert "private_key" not in dumped
    assert "do not place" in md.lower() or "does not place" in md.lower()
    assert "dependency_id" in csv_text


def test_workspace_integrates_with_v3_search_graph_workflows_demo():
    live_v3_workspace.create_demo_workspace_records(write_runtime=True)
    search = live_v3.search_local("guided", limit=250)
    assert any(item.get("result_type") in {"guided_review_flow", "guided_review_session", "guided_review_packet", "saved_task_view"} for item in search["items"])
    graph = live_v3.build_decision_graph(limit=500)
    assert graph.get("workspace_nodes", 0) >= 1
    command = live_v3.build_command_center()
    assert "workspace" in command["groups"]
    templates = live_v3.workflow_templates()
    assert any(t["workflow_id"] == "guided_daily_review_packet" for t in templates["templates"])
    run = live_v3.run_workflow({"workflow_id": "guided_daily_review_packet"})
    assert run["status"] == "completed"
    assert run["order_submitted"] is False
    fixture = live_v3.build_demo_fixture()
    assert fixture["guided_workspace"]["safe_demo_data"] is True


def test_workspace_routes_and_apis_render(authed_client):
    for route in ["/v3/workspace", "/v3/workspace/daily-review", "/v3/workspace/dependencies"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.7.0-real" in response.text
        assert "Guided" in response.text or "guided" in response.text
        assert "not trade approval" in response.text or "do not place" in response.text

    assert authed_client.get("/api/v3/workspace/summary").status_code == 200
    flow = authed_client.post("/api/v3/workspace/flows", json={"title": "API flow", "flow_type": "custom", "steps": ["Review", "Packet"]})
    assert flow.status_code == 200
    flow_id = flow.json()["flow_id"]
    assert authed_client.get("/api/v3/workspace/flows").status_code == 200
    started = authed_client.post(f"/api/v3/workspace/flows/{flow_id}/start", json={})
    assert started.status_code == 200
    session_id = started.json()["session"]["session_id"]
    assert authed_client.get("/api/v3/workspace/sessions").status_code == 200
    assert authed_client.post(f"/api/v3/workspace/sessions/{session_id}/step", json={"step_id": "step_01"}).status_code == 200
    complete = authed_client.post(f"/api/v3/workspace/sessions/{session_id}/complete", json={})
    assert complete.json()["guided_review_completion_is_not_trade_approval"] is True
    assert authed_client.post("/api/v3/workspace/daily-review/start", json={}).status_code == 200
    assert authed_client.post("/api/v3/workspace/weekly-review/start", json={}).status_code == 200
    assert authed_client.post("/api/v3/workspace/task-triage/start", json={}).status_code == 200
    dep = authed_client.post("/api/v3/workspace/dependencies", json={"task_id": "api-task", "depends_on_task_id": "api-prereq"})
    assert dep.status_code == 200
    assert authed_client.post(f"/api/v3/workspace/dependencies/{dep.json()['dependency_id']}/delete").status_code == 200
    assert authed_client.post("/api/v3/workspace/blocked/review", json={}).status_code == 200
    assert authed_client.post("/api/v3/workspace/source-preview", json={"title": "API source", "source_subsystem": "validation"}).status_code == 200
    assert authed_client.post("/api/v3/workspace/saved-views", json={"title": "API view", "filters": {"status": "blocked"}}).status_code == 200
    assert authed_client.post("/api/v3/workspace/review-packets", json={"title": "API packet"}).status_code == 200
    for route in ["/api/v3/workspace/export.json", "/api/v3/workspace/export.md", "/api/v3/workspace/export/dependencies.json", "/api/v3/workspace/export/dependencies.md", "/api/v3/workspace/export/saved-views.json", "/api/v3/workspace/export/saved-views.md", "/api/v3/workspace/export/dependencies.csv", "/api/v3/workspace/export/saved-views.csv"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "private_key" not in response.text.lower()
