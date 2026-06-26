from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import APP_VERSION
from app import auth, live_data, live_governance, live_monitoring, live_portfolio, live_research, live_strategy, live_v2, live_v3, live_v3_analytics, live_v3_simulation, live_v3_datasets
from app.main import app


@pytest.fixture(autouse=True)
def isolated_v3_ux(tmp_path, monkeypatch):
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


def test_v33_version_and_design_system_files_exist():
    assert APP_VERSION == "4.17.0-real"
    root = Path(__file__).resolve().parents[1]
    assert (root / "app/static/v3_design.css").exists()
    assert (root / "app/static/v3_interactions.js").exists()
    status = live_v3.design_system_status()
    assert status["status"] == "pass"
    assert status["order_submitted"] is False
    assert status["order_cancelled"] is False
    assert status["live_trading_armed"] is False


def test_v33_navigation_and_ux_status_are_safe():
    nav = live_v3.navigation_groups()
    groups = {row["group"] for row in nav["groups"]}
    assert {"Operate", "Analyze", "Build Thesis", "Govern", "Output"}.issubset(groups)
    ux = live_v3.ux_release_status()
    assert ux["overall_status"] == "pass"
    assert ux["redesigned_ui_does_not_bypass_backend_gates"] is True
    assert ux["screenshots_included_in_release_zip"] is False
    assert ux["order_submitted"] is False


def test_v33_routes_render_redesigned_layout(authed_client):
    for route in ["/v3", "/v3/search", "/v3/graph"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.7.0-real" in response.text
        assert "Dataset Builder / Simulation Lab / Operator Intelligence" in response.text
        assert "v3_design.css" in response.text
        assert "Operator Intelligence OS" in response.text


def test_v33_command_center_has_redesigned_sections(authed_client):
    response = authed_client.get("/v3")
    text = response.text
    for phrase in ["System Safety", "Operator Attention Queue", "Workbench Shortcuts", "Intelligence Summary", "Recent Activity", "Safe Next Actions"]:
        assert phrase in text
    assert "redesigned UI" in text or "redesigned pages" in text
    assert "does not place orders" in text or "do not place orders" in text


def test_v33_search_graph_workflow_and_analytics_polish(authed_client):
    assert "Object type" in authed_client.get("/v3/search").text or "All object types" in authed_client.get("/v3/search").text
    assert "Relationship" in authed_client.get("/v3/graph").text
    assert "Read-Only Workflow Orchestrator" in authed_client.get("/v3/workflows").text
    assert "Learning Report Generator" in authed_client.get("/v3/analytics").text


def test_v33_ux_apis_and_scripts_are_safe(authed_client):
    for route in ["/api/v3/ux/status", "/api/v3/ux/design-system", "/api/v3/ux/navigation"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        data = response.json()
        assert data["secret_values_returned"] is False
    root = Path(__file__).resolve().parents[1]
    assert (root / "scripts/validate_v3_ux_release.py").exists()
    assert (root / "scripts/capture_v3_screenshots.py").exists()


def test_v33_docs_exist():
    root = Path(__file__).resolve().parents[1]
    for rel in [
        "docs/V3_UI_UX_REDESIGN_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]:
        assert (root / rel).exists(), rel
