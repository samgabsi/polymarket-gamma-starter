from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import APP_VERSION
from app import auth, live_data, live_governance, live_monitoring, live_portfolio, live_research, live_strategy, live_v2, live_v3, live_v3_analytics, live_v3_simulation, live_v3_datasets
from app.main import app


@pytest.fixture(autouse=True)
def isolated_v3_datasets(tmp_path, monkeypatch):
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
    monkeypatch.setattr(live_data, "SUBSYSTEM_PATHS", {
        "audit": live_dir / "audit_ledger.jsonl",
        "strategy": strategy_dir,
        "research": research_dir,
        "monitoring": monitoring_dir,
        "portfolio": portfolio_dir,
        "governance": governance_dir,
        "settings": live_dir / "settings",
    })
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


def _collect_sample_dataset():
    collected = live_v3_datasets.collect_snapshots({
        "collection_mode": "demo",
        "snapshot_types": ["market_metadata", "order_book", "local_strategy", "local_research", "local_monitoring", "local_portfolio", "local_governance", "local_analytics", "local_simulation", "data_health"],
        "market": {"market_id": "demo-dataset-market", "condition_id": "demo-cond", "question": "DEMO dataset market?", "outcomes": ["YES", "NO"], "status": "active"},
        "order_book": {"market_id": "demo-dataset-market", "token_id": "yes-token", "outcome": "YES", "bids": [[0.45, 100]], "asks": [[0.55, 100]], "best_bid": 0.45, "best_ask": 0.55},
        "notes": "Fake dataset collection for tests.",
    })
    manifest = live_v3_datasets.build_dataset_manifest({"title": "Test Replay Dataset", "include_demo_data": True})
    return collected, manifest


def test_v35_version():
    assert APP_VERSION == "4.17.0-real"


def test_dataset_collection_validation_quality_exports_are_read_only():
    collected, manifest = _collect_sample_dataset()
    assert collected["ok"] is True
    assert collected["order_submitted"] is False
    assert collected["order_cancelled"] is False
    assert collected["live_trading_armed"] is False
    assert len(collected["snapshots"]) >= 3

    snapshot = collected["snapshots"][0]
    validation = live_v3_datasets.validate_snapshot(snapshot_id=snapshot["snapshot_id"])
    assert validation["validation_status"] in {"pass", "warning"}
    assert validation["secret_values_returned"] is False

    assert manifest["manifest"]["dataset_id"]
    quality = live_v3_datasets.dataset_quality_report(manifest["manifest"]["dataset_id"])
    assert quality["quality_status"] in {"excellent", "good", "usable", "partial", "incomplete", "blocked"}
    assert quality["order_submitted"] is False

    ready = live_v3_datasets.replay_ready_datasets()
    assert ready["secret_values_returned"] is False

    for exported in [live_v3_datasets.export_dataset_json(), {"markdown": live_v3_datasets.export_dataset_markdown()}, {"csv": live_v3_datasets.export_csv("snapshots")}]:
        dumped = json.dumps(exported)
        assert "private_key" not in dumped.lower()
        assert "api_key=" not in dumped.lower()


def test_dataset_search_graph_analytics_and_command_center_integration():
    _collect_sample_dataset()
    search = live_v3.search_local("dataset", limit=100)
    assert any("dataset" in item.get("result_type", "") or "snapshot" in item.get("result_type", "") for item in search["items"])
    graph = live_v3.build_decision_graph(limit=100)
    assert graph.get("dataset_nodes", 0) >= 1
    command = live_v3.build_command_center()
    assert "datasets" in command["groups"]
    assert command["groups"]["datasets"]["snapshot_count"] >= 1
    analytics = live_v3_analytics.build_analytics_summary()
    assert "dataset_snapshot_count" in analytics
    sim = live_v3_simulation.simulation_summary()
    assert "dataset_context" in sim


def test_dataset_workflow_templates_and_runs_are_safe():
    _collect_sample_dataset()
    templates = live_v3.workflow_templates()
    assert any(t["workflow_id"] == "dataset_quality_review" for t in templates["templates"])
    run = live_v3.run_workflow({"workflow_id": "dataset_quality_review"})
    assert run["status"] == "completed"
    assert run["order_submitted"] is False
    assert run["order_cancelled"] is False
    assert run["live_trading_armed"] is False


def test_dataset_routes_and_apis_render(authed_client):
    for route in ["/v3/datasets", "/v3/datasets/snapshots", "/v3/datasets/collector", "/v3/datasets/builder", "/v3/datasets/quality", "/v3/datasets/provenance", "/v3/datasets/replay", "/v3/datasets/exports", "/v3/datasets/settings"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.7.0-real" in response.text
        assert "Dataset" in response.text
        assert "read-only" in response.text.lower()

    collect = authed_client.post("/api/v3/datasets/snapshots/collect", json={"snapshot_types": ["market_metadata", "order_book"], "collection_mode": "demo", "market": {"market_id": "api-demo", "question": "API demo?"}, "order_book": {"market_id": "api-demo", "token_id": "yes", "bids": [], "asks": []}})
    assert collect.status_code == 200
    assert collect.json()["order_submitted"] is False
    snapshot_id = collect.json()["snapshots"][0]["snapshot_id"]
    validate = authed_client.post("/api/v3/datasets/snapshots/validate", json={"snapshot_id": snapshot_id})
    assert validate.status_code == 200
    build = authed_client.post("/api/v3/datasets/build", json={"title": "API Dataset", "include_demo_data": True})
    assert build.status_code == 200
    dataset_id = build.json()["manifest"]["dataset_id"]
    for route in ["/api/v3/datasets", "/api/v3/datasets/summary", "/api/v3/datasets/snapshots", "/api/v3/datasets/collector", "/api/v3/datasets/runs", "/api/v3/datasets/manifests", f"/api/v3/datasets/manifests/{dataset_id}", "/api/v3/datasets/quality", "/api/v3/datasets/provenance", "/api/v3/datasets/replay-ready", "/api/v3/datasets/settings"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
    assert authed_client.post(f"/api/v3/datasets/manifests/{dataset_id}/validate").status_code == 200
    for route in ["/api/v3/datasets/export.json", "/api/v3/datasets/export.md", "/api/v3/datasets/export/snapshots.csv", "/api/v3/datasets/export/quality.csv", "/api/v3/datasets/export/provenance.csv"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "private_key" not in response.text.lower()


def test_v35_docs_exist():
    root = Path(__file__).resolve().parents[1]
    for rel in [
        "docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md",
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]:
        assert (root / rel).exists(), rel
