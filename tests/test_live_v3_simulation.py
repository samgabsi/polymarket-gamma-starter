from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_data, live_governance, live_monitoring, live_portfolio, live_research, live_strategy, live_v2, live_v3, live_v3_analytics, live_v3_simulation, live_v3_datasets
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_v3_simulation(tmp_path, monkeypatch):
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
    monkeypatch.setattr(live_data, "SUBSYSTEM_PATHS", {"audit": live_dir / "audit_ledger.jsonl", "strategy": strategy_dir, "research": research_dir, "monitoring": monitoring_dir, "portfolio": portfolio_dir, "governance": governance_dir, "settings": live_dir / "settings"})
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


def seed_simulation_objects():
    thesis = live_strategy.create_thesis({"market_title": "DEMO replay market", "market_id": "sim-mkt", "outcome": "YES", "thesis_summary": "Fake thesis for simulation tests", "status": "ready_for_ticket"})["item"]
    live_strategy.create_evidence({"thesis_id": thesis["id"], "market_id": "sim-mkt", "title": "Support", "direction": "supports", "freshness_status": "fresh"})
    live_strategy.create_evidence({"thesis_id": thesis["id"], "market_id": "sim-mkt", "title": "Counter", "direction": "contradicts", "freshness_status": "fresh"})
    live_strategy.create_evidence({"thesis_id": thesis["id"], "market_id": "sim-mkt", "title": "Stale", "direction": "supports", "freshness_status": "stale", "status": "stale"})
    live_monitoring.create_rule({"rule_name": "Fake alert rule", "rule_type": "thesis_alert", "related_market_id": "sim-mkt", "related_thesis_id": thesis["id"], "severity": "warning"})
    live_portfolio.update_bankroll({"total_bankroll": 1000, "max_per_market_exposure": 50})
    live_governance.create_checklist({"checklist_title": "Fake checklist", "checklist_type": "pre_trade", "related_market_id": "sim-mkt", "related_thesis_id": thesis["id"], "status": "draft"})
    live_governance.create_journal_entry({"decision_title": "Fake simulation decision", "decision_type": "thesis_decision", "related_market_id": "sim-mkt", "related_thesis_id": thesis["id"], "status": "active", "confidence_level": 75})
    return thesis


def assert_safe(result):
    dumped = json.dumps(result, sort_keys=True, default=str).lower()
    assert result.get("order_submitted") is False
    assert result.get("order_cancelled") is False
    assert result.get("live_trading_armed") is False
    assert result.get("secret_values_returned") is False
    assert "sk-" not in dumped


def test_v34_version_and_simulation_core():
    assert APP_VERSION == "4.17.0-real"
    thesis = seed_simulation_objects()
    created = live_v3_simulation.create_session({"session_title": "Replay", "simulation_type": "pre_trade_replay", "market_id": "sim-mkt", "thesis_id": thesis["id"], "assumptions": {"hypothetical_fill_percentage": 50}})
    assert_safe(created)
    session_id = created["session"]["session_id"]
    updated = live_v3_simulation.update_session(session_id, {"status": "ready"})
    assert updated["session"]["status"] == "ready"
    run = live_v3_simulation.run_session(session_id)
    assert_safe(run)
    assert run["report"]["status"] == "completed"
    assert live_v3_simulation.list_sessions()["count"] >= 1
    assert live_v3_simulation.list_reports()["count"] >= 1


def test_v34_simulation_outputs_and_exports_are_safe():
    thesis = seed_simulation_objects()
    payload = {"market_id": "sim-mkt", "thesis_id": thesis["id"], "replay_time": "2099-01-01T00:00:00+00:00"}
    for result in [
        live_v3_simulation.reconstruct_historical_state(payload),
        live_v3_simulation.simulate_pre_trade(payload),
        live_v3_simulation.simulate_thesis(payload),
        live_v3_simulation.simulate_alerts(payload),
        live_v3_simulation.simulate_portfolio(payload),
        live_v3_simulation.simulate_governance(payload),
        live_v3_simulation.simulate_no_trade(payload),
        live_v3_simulation.process_quality_backtest(payload),
        live_v3_simulation.compare_then_now(payload),
    ]:
        assert_safe(result)
        assert "unknown" in json.dumps(result).lower() or "unavailable" in json.dumps(result).lower()
        assert "assumption" in json.dumps(result).lower() or result["simulation_type"] == "what_i_knew_then_vs_now"
    export = live_v3_simulation.export_simulation_json()
    assert_safe(export)
    md = live_v3_simulation.simulation_report_markdown()
    assert "Simulation Lab Report" in md
    assert "does not place" in md
    csv_text = live_v3_simulation.export_csv("sessions")
    assert "simulation_type" in csv_text


def test_v34_simulation_integrates_with_command_search_graph_and_templates():
    seed_simulation_objects()
    created = live_v3_simulation.create_session({"session_title": "Replay search", "simulation_type": "process_quality_backtest"})
    live_v3_simulation.run_session(created["session"]["session_id"])
    command = live_v3.build_command_center()
    assert "simulation" in command["groups"]
    search = live_v3.search_local("simulation", limit=50)
    assert any(item["result_type"] in {"simulation_session", "simulation_report"} for item in search["items"])
    graph = live_v3.build_decision_graph(limit=100)
    assert graph.get("simulation_nodes", 0) >= 1
    assert any("simulation" in node["node_type"] for node in graph["nodes"])
    templates = live_v3.workflow_templates()
    assert any(t["workflow_id"] == "simulation_lab_report" for t in templates["templates"])


def test_v34_simulation_routes_and_apis_render(authed_client):
    for route in ["/v3/simulation", "/v3/simulation/replay", "/v3/simulation/sessions", "/v3/simulation/scenarios", "/v3/simulation/pre-trade", "/v3/simulation/thesis", "/v3/simulation/alerts", "/v3/simulation/portfolio", "/v3/simulation/governance", "/v3/simulation/no-trade", "/v3/simulation/reports"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.7.0-real" in response.text
        assert "Simulation Lab" in response.text
        assert "No Live Orders" in response.text or "Simulation Only" in response.text
    summary = authed_client.get("/api/v3/simulation")
    assert summary.status_code == 200
    assert summary.json()["secret_values_returned"] is False
    created = authed_client.post("/api/v3/simulation/sessions", json={"session_title": "API replay", "simulation_type": "process_quality_backtest"})
    assert created.status_code == 200
    session_id = created.json()["session"]["session_id"]
    run = authed_client.post(f"/api/v3/simulation/sessions/{session_id}/run", json={})
    assert run.status_code == 200
    assert run.json()["live_trading_armed"] is False
    for route in ["/api/v3/simulation/replay", "/api/v3/simulation/export.json", "/api/v3/simulation/export.md", "/api/v3/simulation/export/sessions.csv", "/api/v3/simulation/export/findings.csv"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route


def test_v34_docs_exist():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in [
        "docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md",
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]:
        assert (root / rel).exists(), rel
