from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import APP_VERSION
from app import auth, live_data, live_governance, live_monitoring, live_portfolio, live_research, live_strategy, live_v2, live_v3, live_v3_analytics, live_v3_simulation, live_v3_datasets, live_v3_freshness
from app.main import app


@pytest.fixture(autouse=True)
def isolated_v3_freshness(tmp_path, monkeypatch):
    live_dir = tmp_path / "live_v2"
    strategy_dir = live_dir / "strategy"
    research_dir = live_dir / "research"
    monitoring_dir = live_dir / "monitoring"
    portfolio_dir = live_dir / "portfolio"
    governance_dir = live_dir / "governance"
    data_dir = live_dir / "data_integrity"
    v3_dir = tmp_path / "live_v3"
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", live_dir)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", live_dir / "audit_ledger.jsonl")
    monkeypatch.setattr(live_strategy, "STRATEGY_DIR", strategy_dir)
    monkeypatch.setattr(live_strategy, "STRATEGY_EVENTS_PATH", strategy_dir / "strategy_events.jsonl")
    monkeypatch.setattr(live_research, "RESEARCH_DIR", research_dir)
    monkeypatch.setattr(live_research, "RESEARCH_EVENTS_PATH", research_dir / "research_events.jsonl")
    monkeypatch.setattr(live_monitoring, "MONITORING_DIR", monitoring_dir)
    monkeypatch.setattr(live_monitoring, "MONITORING_EVENTS_PATH", monitoring_dir / "monitoring_events.jsonl")
    monkeypatch.setattr(live_portfolio, "PORTFOLIO_DIR", portfolio_dir)
    monkeypatch.setattr(live_portfolio, "PORTFOLIO_EVENTS_PATH", portfolio_dir / "portfolio_events.jsonl")
    monkeypatch.setattr(live_governance, "GOVERNANCE_DIR", governance_dir)
    monkeypatch.setattr(live_governance, "GOVERNANCE_EVENTS_PATH", governance_dir / "governance_events.jsonl")
    monkeypatch.setattr(live_data, "RUNTIME_ROOT", live_dir)
    monkeypatch.setattr(live_data, "DATA_LAYER_DIR", data_dir)
    monkeypatch.setattr(live_data, "BACKUP_DIR", data_dir / "backups")
    monkeypatch.setattr(live_data, "EXPORT_DIR", data_dir / "exports")
    monkeypatch.setattr(live_data, "REPORT_DIR", data_dir / "reports")
    monkeypatch.setattr(live_data, "DATA_EVENTS_PATH", data_dir / "data_events.jsonl")
    monkeypatch.setattr(live_v3, "V3_DIR", v3_dir)
    monkeypatch.setattr(live_v3, "V3_EVENTS_PATH", v3_dir / "v3_events.jsonl")
    monkeypatch.setattr(live_v3, "V3_WORKFLOW_RUNS_PATH", v3_dir / "workflow_runs.jsonl")
    monkeypatch.setattr(live_v3, "V3_SETTINGS_PATH", v3_dir / "settings.json")
    monkeypatch.setattr(live_v3, "V3_DEMO_DATA_PATH", v3_dir / "demo_fixture.json")
    monkeypatch.setattr(live_v3_analytics, "ANALYTICS_DIR", v3_dir / "analytics")
    monkeypatch.setattr(live_v3_analytics, "ANALYTICS_EVENTS_PATH", v3_dir / "analytics" / "analytics_events.jsonl")
    monkeypatch.setattr(live_v3_analytics, "ANALYTICS_SNAPSHOTS_PATH", v3_dir / "analytics" / "analytics_snapshots.jsonl")
    monkeypatch.setattr(live_v3_analytics, "ANALYTICS_REPORTS_PATH", v3_dir / "analytics" / "learning_reports.jsonl")
    monkeypatch.setattr(live_v3_simulation, "SIMULATION_DIR", v3_dir / "simulation")
    monkeypatch.setattr(live_v3_simulation, "SIMULATION_EVENTS_PATH", v3_dir / "simulation" / "simulation_events.jsonl")
    monkeypatch.setattr(live_v3_simulation, "SIMULATION_SESSIONS_PATH", v3_dir / "simulation" / "simulation_sessions.jsonl")
    monkeypatch.setattr(live_v3_simulation, "SIMULATION_REPORTS_PATH", v3_dir / "simulation" / "simulation_reports.jsonl")
    monkeypatch.setattr(live_v3_datasets, "DATASETS_DIR", v3_dir / "datasets")
    monkeypatch.setattr(live_v3_datasets, "DATASET_EVENTS_PATH", v3_dir / "datasets" / "dataset_events.jsonl")
    monkeypatch.setattr(live_v3_datasets, "SNAPSHOTS_PATH", v3_dir / "datasets" / "snapshots.jsonl")
    monkeypatch.setattr(live_v3_datasets, "COLLECTION_RUNS_PATH", v3_dir / "datasets" / "collection_runs.jsonl")
    monkeypatch.setattr(live_v3_datasets, "DATASET_MANIFESTS_PATH", v3_dir / "datasets" / "dataset_manifests.jsonl")
    monkeypatch.setattr(live_v3_datasets, "QUALITY_REPORTS_PATH", v3_dir / "datasets" / "quality_reports.jsonl")
    monkeypatch.setattr(live_v3_datasets, "PROVENANCE_PATH", v3_dir / "datasets" / "provenance.jsonl")
    monkeypatch.setattr(live_v3_datasets, "DATASET_SETTINGS_PATH", v3_dir / "datasets" / "settings.json")
    monkeypatch.setattr(live_v3_freshness, "FRESHNESS_DIR", v3_dir / "freshness")
    monkeypatch.setattr(live_v3_freshness, "FRESHNESS_EVENTS_PATH", v3_dir / "freshness" / "freshness_events.jsonl")
    monkeypatch.setattr(live_v3_freshness, "POLICIES_PATH", v3_dir / "freshness" / "policies.jsonl")
    monkeypatch.setattr(live_v3_freshness, "JOBS_PATH", v3_dir / "freshness" / "collection_jobs.jsonl")
    monkeypatch.setattr(live_v3_freshness, "FINDINGS_PATH", v3_dir / "freshness" / "findings.jsonl")
    monkeypatch.setattr(live_v3_freshness, "READINESS_PATH", v3_dir / "freshness" / "readiness_reports.jsonl")
    monkeypatch.setattr(live_v3_freshness, "NOTIFICATIONS_PATH", v3_dir / "freshness" / "notifications.jsonl")
    monkeypatch.setattr(live_v3_freshness, "SETTINGS_PATH", v3_dir / "freshness" / "settings.json")
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_v36_version():
    assert APP_VERSION == "4.17.0-real"


def test_freshness_policy_job_scan_notifications_exports_are_safe():
    policy = live_v3_freshness.create_policy({"title": "Test freshness", "target_snapshot_types": ["market_metadata"], "freshness_threshold_minutes": 1})
    assert policy["policy_id"]
    scan = live_v3_freshness.freshness_scan(write=True)
    assert scan["order_submitted"] is False
    assert scan["order_cancelled"] is False
    assert scan["live_trading_armed"] is False
    assert scan["finding_count"] >= 1
    job = live_v3_freshness.create_collection_job({"source_policy_id": policy["policy_id"], "snapshot_types": ["market_metadata", "order_book"], "run_mode": "demo"})
    assert job["status"] in {"queued", "draft"}
    run = live_v3_freshness.run_collection_job(job["job_id"], {"collection_mode": "demo"})
    assert run["ok"] is True
    assert run["job"]["status"] == "completed"
    assert run["order_submitted"] is False
    report = live_v3_freshness.readiness_report(write=True)
    assert report["readiness_status"] in {"ready", "needs_review", "not_ready"}
    note = live_v3_freshness.create_notification({"title": "Test note", "message": "Fake freshness note"})
    ack = live_v3_freshness.update_notification(note["notification_id"], "ack")
    snooze = live_v3_freshness.update_notification(note["notification_id"], "snooze", snooze_minutes=10)
    resolved = live_v3_freshness.update_notification(note["notification_id"], "resolve")
    assert ack["notification"]["status"] == "acknowledged"
    assert snooze["notification"]["status"] == "snoozed"
    assert resolved["notification"]["status"] == "resolved"
    for exported in [live_v3_freshness.export_freshness_json(), {"md": live_v3_freshness.export_freshness_markdown()}, {"csv": live_v3_freshness.export_csv("notifications")}]:
        dumped = json.dumps(exported).lower()
        assert "private_key" not in dumped
        assert "api_key=" not in dumped


def test_freshness_integrates_with_v3_search_graph_analytics_workflows():
    live_v3_freshness.create_demo_freshness_records()
    search = live_v3.search_local("freshness", limit=100)
    assert any(item.get("result_type") in {"freshness_policy", "collection_job", "operator_notification", "stale_dataset_finding"} for item in search["items"])
    graph = live_v3.build_decision_graph(limit=200)
    assert graph.get("freshness_nodes", 0) >= 1
    command = live_v3.build_command_center()
    assert "freshness" in command["groups"]
    analytics = live_v3_analytics.build_analytics_summary()
    assert "freshness_context" in analytics
    sim = live_v3_simulation.simulation_summary()
    assert "freshness_context" in sim
    templates = live_v3.workflow_templates()
    assert any(t["workflow_id"] == "freshness_review" for t in templates["templates"])
    run = live_v3.run_workflow({"workflow_id": "freshness_review"})
    assert run["status"] == "completed"
    assert run["order_submitted"] is False


def test_freshness_routes_and_apis_render(authed_client):
    for route in ["/v3/freshness", "/v3/freshness/planner", "/v3/freshness/schedules", "/v3/freshness/jobs", "/v3/freshness/notifications", "/v3/freshness/readiness", "/v3/freshness/history", "/v3/freshness/settings"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.7.0-real" in response.text
        assert "Freshness" in response.text
        assert "read-only" in response.text.lower()

    policy = authed_client.post("/api/v3/freshness/policies", json={"title": "API policy", "target_snapshot_types": ["market_metadata"]})
    assert policy.status_code == 200
    job = authed_client.post("/api/v3/freshness/jobs", json={"snapshot_types": ["market_metadata"], "run_mode": "demo"})
    assert job.status_code == 200
    job_id = job.json()["job_id"]
    run = authed_client.post(f"/api/v3/freshness/jobs/{job_id}/run", json={"collection_mode": "demo"})
    assert run.status_code == 200
    assert run.json()["order_submitted"] is False
    readiness = authed_client.post("/api/v3/freshness/readiness", json={})
    assert readiness.status_code == 200
    scan = authed_client.post("/api/v3/freshness/scan", json={"write": True})
    assert scan.status_code == 200
    notifications = authed_client.get("/api/v3/freshness/notifications")
    assert notifications.status_code == 200
    note = live_v3_freshness.create_notification({"title": "API note", "message": "fake"})
    for action in ["ack", "dismiss", "snooze", "resolve"]:
        resp = authed_client.post(f"/api/v3/freshness/notifications/{note['notification_id']}/{action}", json={"snooze_minutes": 5})
        assert resp.status_code == 200
    assert authed_client.get("/api/v3/freshness/export.json").status_code == 200
    assert authed_client.get("/api/v3/freshness/export.md").status_code == 200
    assert authed_client.get("/api/v3/freshness/export/jobs.csv").status_code == 200


def test_freshness_no_live_mutation_and_demo_secret_free():
    demo = live_v3_freshness.create_demo_freshness_records()
    assert demo["demo_data_is_fake"] is True
    dumped = json.dumps(demo).lower()
    assert "private_key" not in dumped
    assert "api_key=" not in dumped
    assert demo["order_submitted"] is False
    assert demo["order_cancelled"] is False
    assert demo["live_trading_armed"] is False
    settings = live_v3_freshness.build_settings()
    assert settings["scheduler_enabled_by_default"] is False
    assert settings["external_collection_on_startup"] is False
