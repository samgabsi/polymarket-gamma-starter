from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_data, live_governance, live_monitoring, live_portfolio, live_research, live_strategy, live_v2, live_v3, live_v3_analytics, live_v3_simulation, live_v3_datasets
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_v3(tmp_path, monkeypatch):
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


def seed_objects():
    thesis = live_strategy.create_thesis({"market_title": "Will demo pass?", "market_id": "m-v3", "outcome": "YES", "thesis_summary": "Demo quality matters", "status": "ready_for_ticket"})["item"]
    live_strategy.create_evidence({"thesis_id": thesis["id"], "market_id": "m-v3", "title": "Support", "direction": "supports"})
    live_strategy.create_evidence({"thesis_id": thesis["id"], "market_id": "m-v3", "title": "Counter", "direction": "contradicts"})
    live_research.create_source({"title": "Official source", "url": "https://example.com", "market_id": "m-v3", "related_thesis_id": thesis["id"], "credibility_rating": 5})
    live_monitoring.create_rule({"rule_name": "Review demo market", "rule_type": "thesis_alert", "related_thesis_id": thesis["id"], "severity": "warning"})
    live_governance.create_journal_entry({"decision_title": "Proceed with v3 review", "decision_type": "thesis_decision", "related_thesis_id": thesis["id"], "confidence_level": 75, "status": "active"})
    live_governance.create_checklist({"checklist_title": "Review demo setup", "checklist_type": "pre_trade", "related_thesis_id": thesis["id"], "status": "completed"})
    live_governance.create_mistake_pattern({"pattern_title": "Skipped review", "pattern_type": "unclear_reasoning", "frequency": 2, "status": "active"})
    return thesis


def test_version_is_v3():
    assert APP_VERSION == "4.17.0-real"


def test_command_center_search_graph_and_missing_prereqs_are_local_and_safe():
    thesis = seed_objects()
    command = live_v3.build_command_center()
    assert command["version"] == "4.17.0-real"
    assert command["secret_values_returned"] is False
    assert command["live_armed"] is False

    search = live_v3.search_local("demo", limit=20)
    assert search["local_only"] is True
    assert any("demo" in item["title"].lower() or "demo" in item["summary"].lower() for item in search["items"])

    graph = live_v3.build_decision_graph()
    assert graph["node_count"] >= 1
    assert graph["secret_values_returned"] is False

    findings = live_v3.missing_prerequisites_scan()
    assert findings["order_submitted"] is False
    assert findings["order_cancelled"] is False
    assert findings["live_trading_armed"] is False
    assert thesis["id"]


def test_v3_workflows_packets_exports_and_ai_boundary_do_not_trade(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "do-not-leak-secret")
    thesis = seed_objects()
    run = live_v3.run_workflow({"workflow_id": "pre_trade_intelligence_packet", "thesis_id": thesis["id"], "market_id": "m-v3"})
    dumped = json.dumps(run)
    assert run["status"] == "completed"
    assert run["order_submitted"] is False
    assert run["order_cancelled"] is False
    assert run["live_trading_armed"] is False
    assert run["ai_assistance_enabled"] is False
    assert "do-not-leak-secret" not in dumped

    packet = live_v3.pre_trade_packet({"thesis_id": thesis["id"], "market_id": "m-v3"})
    assert packet["order_submitted"] is False
    assert "do-not-leak-secret" not in json.dumps(packet)

    md = live_v3.export_report_markdown("pre_trade_packet", {"thesis_id": thesis["id"]})
    assert "does not place" in md
    assert "do-not-leak-secret" not in md

    settings = live_v3.build_v3_settings()
    assert settings["ai_assistance_enabled"] is False
    assert settings["analysis_provider"]["external_calls_allowed"] is False


def test_v3_routes_and_apis_render():
    seed_objects()
    root = live_v3.build_command_center()
    assert root["version"] == "4.17.0-real"
    assert root["secret_values_returned"] is False
    packet = live_v3.pre_trade_packet({"market_id": "m-v3"})
    assert packet["order_submitted"] is False
    workflow = live_v3.run_workflow({"workflow_id": "market_intelligence_brief", "market_id": "m-v3"})
    assert workflow["order_submitted"] is False
    graph_md = live_v3.graph_to_markdown()
    assert "Decision Graph Export" in graph_md


def test_v31_search_graph_filters_templates_demo_and_validation_are_safe():
    seed_objects()
    filters = live_v3.search_filters()
    assert filters["secret_values_returned"] is False
    assert "thesis" in filters["object_types"]

    search = live_v3.search_local("DEMO", result_type="thesis", tag="demo")
    assert search["local_only"] is True

    graph_filters = live_v3.graph_filters()
    assert graph_filters["secret_values_returned"] is False
    filtered_graph = live_v3.filtered_decision_graph(node_type="thesis")
    assert filtered_graph["secret_values_returned"] is False
    assert all(node["node_type"] == "thesis" for node in filtered_graph["nodes"])

    templates = live_v3.workflow_templates()
    assert templates["count"] >= 10
    assert any(t["workflow_id"] == "pre_trade_intelligence_packet" and "Blockers" in t["sections"] for t in templates["templates"])

    outputs = live_v3.workflow_outputs()
    assert outputs["secret_values_returned"] is False


def test_v32_analytics_engine_snapshots_reports_and_exports_are_safe():
    seed_objects()
    summary = live_v3_analytics.build_analytics_summary()
    assert summary["version"] == "4.17.0-real"
    assert summary["secret_values_returned"] is False
    assert summary["analytics_are_descriptive"] is True

    snapshot = live_v3_analytics.generate_analytics_snapshot(write=True)
    assert snapshot["order_submitted"] is False
    assert snapshot["order_cancelled"] is False
    assert snapshot["live_trading_armed"] is False
    assert snapshot["decisions"]["metrics"]["total_decisions"] >= 1
    assert snapshot["theses"]["metrics"]["theses_with_evidence"] >= 1
    assert snapshot["evidence"]["metrics"]["evidence_count"] >= 1
    assert snapshot["calibration"]["metrics"]["sample_size"] >= 1
    assert "unknown_count" in snapshot["calibration"]["metrics"]

    report = live_v3_analytics.generate_learning_report(period="weekly", write=True)
    dumped = json.dumps(report)
    assert report["analytics_are_descriptive"] is True
    assert report["order_submitted"] is False
    assert "financial advice" in report["safety_statement"].lower()
    assert "secret" not in dumped.lower() or "secret_values_returned" in dumped

    md = live_v3_analytics.export_learning_report_markdown()
    assert "Learning Report" in md
    assert "does not place" in md
    csv_text = live_v3_analytics.export_csv("decisions")
    assert "analytics_type" in csv_text


def test_v32_analytics_integrates_with_search_graph_and_workflows():
    seed_objects()
    search = live_v3.search_local("analytics", limit=50)
    assert search["secret_values_returned"] is False
    assert any("analytics" in item["result_type"] or "learning" in item["result_type"] for item in search["items"])

    graph = live_v3.build_decision_graph(limit=100)
    assert graph["analytics_nodes"] >= 1
    assert any("analytics" in node["node_type"] or "learning" in node["node_type"] for node in graph["nodes"])

    packet = live_v3.pre_trade_packet({"market_id": "m-v3"})
    assert packet["order_submitted"] is False
    assert "analytics_context" in packet
    assert packet["analytics_are_descriptive"] is True

    operator = live_v3.operator_review_packet({"period": "weekly"})
    assert operator["order_submitted"] is False
    assert "learning_report_summary" in operator


def test_v32_analytics_routes_and_apis_render():
    seed_objects()
    summary = live_v3_analytics.build_analytics_summary()
    assert summary["secret_values_returned"] is False
    report = live_v3_analytics.generate_learning_report(period="weekly", write=False)
    assert report["live_trading_armed"] is False
    assert report["order_submitted"] is False
    md = live_v3_analytics.export_learning_report_markdown()
    assert "Learning Report" in md
    csv_resp = live_v3_analytics.export_csv("calibration")
    assert "analytics_type" in csv_resp
