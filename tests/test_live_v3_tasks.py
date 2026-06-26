from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import APP_VERSION
from app import auth, live_v2, live_v3, live_v3_tasks, live_v3_freshness
from app.main import app


@pytest.fixture(autouse=True)
def isolated_v3_tasks(tmp_path, monkeypatch):
    live_dir = tmp_path / "live_v2"
    tasks_dir = tmp_path / "live_v3" / "tasks"
    freshness_dir = tmp_path / "live_v3" / "freshness"
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
    monkeypatch.setattr(live_v3_freshness, "FRESHNESS_DIR", freshness_dir)
    monkeypatch.setattr(live_v3_freshness, "FRESHNESS_EVENTS_PATH", freshness_dir / "freshness_events.jsonl")
    monkeypatch.setattr(live_v3_freshness, "POLICIES_PATH", freshness_dir / "policies.jsonl")
    monkeypatch.setattr(live_v3_freshness, "JOBS_PATH", freshness_dir / "collection_jobs.jsonl")
    monkeypatch.setattr(live_v3_freshness, "FINDINGS_PATH", freshness_dir / "findings.jsonl")
    monkeypatch.setattr(live_v3_freshness, "READINESS_PATH", freshness_dir / "readiness_reports.jsonl")
    monkeypatch.setattr(live_v3_freshness, "NOTIFICATIONS_PATH", freshness_dir / "notifications.jsonl")
    monkeypatch.setattr(live_v3_freshness, "SETTINGS_PATH", freshness_dir / "settings.json")
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/tasks"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_v37_version():
    assert APP_VERSION == "4.17.0-real"


def test_task_lifecycle_packets_cadence_exports_are_safe():
    task = live_v3_tasks.create_task({"title": "Review stale evidence", "priority": "high", "status": "planned", "source_subsystem": "research", "due_date": "2099-01-01"})
    assert task["task_id"]
    assert task["order_submitted"] is False
    updated = live_v3_tasks.update_task(task["task_id"], {"operator_notes": "Human review note.", "follow_up_note": "Follow up locally."})
    assert updated["operator_notes"] == "Human review note."
    active = live_v3_tasks.change_task_status(task["task_id"], "active")
    assert active["status"] == "active"
    done = live_v3_tasks.complete_task(task["task_id"], notes="Completed workflow review only.")
    assert done["status"] == "done"
    assert done["task_completion_is_not_trade_approval"] is True
    assert done["order_submitted"] is False
    archived = live_v3_tasks.archive_task(task["task_id"])
    assert archived["status"] == "archived"

    daily = live_v3_tasks.generate_daily_ops_packet(write=True)
    weekly = live_v3_tasks.generate_weekly_plan(write=True)
    assert daily["order_cancelled"] is False
    assert weekly["live_trading_armed"] is False
    cadence = live_v3_tasks.create_cadence_rule({"title": "Weekly dataset review", "target_subsystem": "datasets", "cadence_type": "weekly"})
    run = live_v3_tasks.run_cadence({"create_tasks": False})
    assert cadence["cadence_id"]
    assert run["order_submitted"] is False
    assert run["event"]["operator_triggered"] is True

    exported = live_v3_tasks.export_json()
    md = live_v3_tasks.export_markdown()
    csv_text = live_v3_tasks.export_csv("tasks")
    dumped = json.dumps(exported).lower()
    assert exported["secret_values_returned"] is False
    assert "private_key" not in dumped
    assert "does not place" in md.lower()
    assert "task_id" in csv_text


def test_inbox_scan_notification_and_finding_conversion():
    note = live_v3_freshness.create_notification({"title": "Dataset stale", "message": "Fake freshness note", "severity": "warning"})
    scan = live_v3_tasks.scan_inbox(write=True)
    assert scan["order_submitted"] is False
    assert scan["new_count"] >= 1
    inbox = live_v3_tasks.list_inbox(status="new")
    assert inbox["count"] >= 1
    converted = live_v3_tasks.create_task_from_inbox(inbox["items"][0]["inbox_id"], {"status": "planned"})
    assert converted["ok"] is True
    assert converted["task"]["order_submitted"] is False
    note_task = live_v3_tasks.create_task_from_notification(note["notification_id"], {"status": "planned"})
    assert note_task.get("ok") is True or note_task.get("error") == "notification_not_found"
    finding = live_v3_tasks.create_task_from_finding({"title": "Finding review", "source_subsystem": "validation", "severity": "critical"})
    assert finding["ok"] is True
    assert finding["task"]["priority"] == "critical"


def test_tasks_integrate_with_v3_search_graph_workflows_demo():
    live_v3_tasks.create_demo_task_records(write_runtime=True)
    search = live_v3.search_local("task", limit=200)
    assert any(item.get("result_type") in {"operator_task", "task_inbox_item", "cadence_rule"} for item in search["items"])
    graph = live_v3.build_decision_graph(limit=500)
    assert graph.get("task_nodes", 0) >= 1
    command = live_v3.build_command_center()
    assert "tasks" in command["groups"]
    templates = live_v3.workflow_templates()
    assert any(t["workflow_id"] == "daily_ops_packet" for t in templates["templates"])
    run = live_v3.run_workflow({"workflow_id": "daily_ops_packet"})
    assert run["status"] == "completed"
    assert run["order_submitted"] is False
    fixture = live_v3.build_demo_fixture()
    assert fixture["tasks"]["safe_demo_data"] is True


def test_task_routes_and_apis_render(authed_client):
    for route in ["/v3/tasks", "/v3/tasks/board", "/v3/tasks/inbox"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.7.0-real" in response.text
        assert "Task" in response.text or "task" in response.text
        assert "not trade approval" in response.text or "not orders" in response.text

    created = authed_client.post("/api/v3/tasks", json={"title": "API task", "priority": "urgent", "status": "planned"})
    assert created.status_code == 200
    task_id = created.json()["task_id"]
    assert created.json()["order_submitted"] is False
    assert authed_client.get("/api/v3/tasks/summary").status_code == 200
    assert authed_client.get("/api/v3/tasks/board").status_code == 200
    assert authed_client.post(f"/api/v3/tasks/{task_id}/status", json={"status": "active"}).json()["status"] == "active"
    complete = authed_client.post(f"/api/v3/tasks/{task_id}/complete", json={"notes": "review complete"})
    assert complete.json()["task_completion_is_not_trade_approval"] is True
    assert authed_client.post("/api/v3/tasks/inbox/scan", json={"write": True}).status_code == 200
    assert authed_client.post("/api/v3/tasks/daily-ops", json={}).status_code == 200
    assert authed_client.post("/api/v3/tasks/weekly-plan", json={}).status_code == 200
    assert authed_client.post("/api/v3/tasks/cadence", json={"title": "API cadence"}).status_code == 200
    assert authed_client.post("/api/v3/tasks/cadence/run", json={}).status_code == 200
    assert authed_client.get("/api/v3/tasks/templates").status_code == 200
    for route in ["/api/v3/tasks/export.json", "/api/v3/tasks/export.md", "/api/v3/tasks/export.csv", "/api/v3/tasks/daily-ops/export.json", "/api/v3/tasks/weekly-plan/export.md"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "private_key" not in response.text.lower()
