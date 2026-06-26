from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_monitoring, live_portfolio, live_research, live_strategy, live_v2
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_portfolio(tmp_path, monkeypatch):
    live_dir = tmp_path / "live_v2"
    strategy_dir = tmp_path / "strategy"
    research_dir = tmp_path / "research"
    monitoring_dir = tmp_path / "monitoring"
    portfolio_dir = tmp_path / "portfolio"
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
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v2-live/portfolio"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_version_is_v2_7():
    assert APP_VERSION == "4.17.0-real"


def test_portfolio_snapshot_bankroll_warnings_exports_and_safety():
    thesis = live_strategy.create_thesis({"market_title": "Exposure market", "market_id": "m1", "outcome": "YES", "thesis_summary": "test", "maximum_acceptable_exposure": 125, "tags": "macro"})
    tid = thesis["item"]["id"]
    bankroll = live_portfolio.update_bankroll({"total_bankroll": 1000, "max_portfolio_exposure": 100, "max_per_market_exposure": 50, "max_per_thesis_exposure": 75, "max_per_tag_exposure": 75})
    assert bankroll["ok"] is True
    exposure = live_portfolio.list_exposure()
    assert exposure["summary"]["total_notional_exposure"] >= 125
    warnings = live_portfolio.list_warnings()
    assert warnings["count"] >= 1
    assert any(item["warning_type"] in {"portfolio_limit_exceeded", "market_limit_exceeded", "thesis_limit_exceeded", "tag_limit_exceeded"} for item in warnings["items"])
    snapshot = live_portfolio.generate_portfolio_snapshot(record=True)
    assert snapshot["order_submitted"] is False
    assert snapshot["order_cancelled"] is False
    scenario = live_portfolio.create_scenario({"scenario_name": "Thesis fails", "scenario_type": "thesis_fails", "related_thesis_id": tid, "planned_notional": 10})
    sid = scenario["item"]["id"]
    evaluated = live_portfolio.evaluate_scenario(sid)
    assert evaluated["ok"] is True
    assert evaluated["order_submitted"] is False
    impact = live_portfolio.planned_trade_impact({"market_id": "m1", "thesis_id": tid, "price": 0.5, "size": 10, "strategy_tag": "macro"})
    assert impact["ok"] is True
    assert impact["order_submitted"] is False
    assert "Portfolio / Exposure Export" in live_portfolio.portfolio_export_markdown()
    assert "exposure_type" in live_portfolio.portfolio_csv("exposure")
    assert "warning_type" in live_portfolio.portfolio_csv("warnings")
    assert "scenario_type" in live_portfolio.portfolio_csv("scenarios")


def test_portfolio_actions_create_audit_events():
    live_portfolio.update_bankroll({"total_bankroll": 500})
    live_portfolio.generate_portfolio_snapshot(record=True)
    rows = live_v2.list_audit_records()
    assert any(row["action"].startswith("portfolio_bankroll_setting_updated") for row in rows)
    assert any(row["action"].startswith("portfolio_portfolio_snapshot_generated") for row in rows)


def test_portfolio_routes_and_api_endpoints(authed_client):
    page = authed_client.get("/v2-live/portfolio")
    assert page.status_code == 200
    assert "Portfolio / Exposure Intelligence" in page.text
    assert "v4.7.0-real" in page.text
    assert authed_client.get("/api/v2/live/portfolio").status_code == 200
    assert authed_client.get("/api/v2/live/portfolio/snapshot").status_code == 200
    assert authed_client.post("/api/v2/live/portfolio/snapshot").status_code == 200
    bankroll = authed_client.post("/api/v2/live/portfolio/bankroll", json={"total_bankroll": 1000, "max_portfolio_exposure": 100}).json()
    assert bankroll["order_submitted"] is False
    exposure_group = authed_client.post("/api/v2/live/portfolio/exposure-groups", json={"group_name": "API group", "related_market_id": "api-market", "notional_estimate": 125, "max_loss_estimate": 125})
    assert exposure_group.status_code == 200
    group_id = exposure_group.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/portfolio/exposure-groups/{group_id}", json={"notional_estimate": 150}).status_code == 200
    scenario = authed_client.post("/api/v2/live/portfolio/scenarios", json={"scenario_name": "API scenario", "scenario_type": "market_resolves_no", "related_market_id": "api-market"})
    assert scenario.status_code == 200
    sid = scenario.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/portfolio/scenarios/{sid}/evaluate", json={}).status_code == 200
    impact = authed_client.post("/api/v2/live/portfolio/planned-impact", json={"market_id": "api-market", "price": 0.5, "size": 10})
    assert impact.status_code == 200
    assert impact.json()["order_submitted"] is False
    assert authed_client.get("/api/v2/live/portfolio/exposure").status_code == 200
    assert authed_client.get("/api/v2/live/portfolio/warnings").status_code == 200
    assert authed_client.get("/api/v2/live/portfolio/bankroll").status_code == 200
    assert authed_client.get("/api/v2/live/portfolio/scenarios").status_code == 200
    assert authed_client.get("/api/v2/live/portfolio/export.json").status_code == 200
    md = authed_client.get("/api/v2/live/portfolio/export.md")
    assert md.status_code == 200
    assert "Portfolio / Exposure Export" in md.text
    assert authed_client.get("/api/v2/live/portfolio/export/exposure.csv").status_code == 200
    assert authed_client.get("/api/v2/live/portfolio/export/warnings.csv").status_code == 200


def test_portfolio_exports_redact_secrets(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "portfolio-secret-token")
    live_portfolio.create_exposure_group({"group_name": "portfolio-secret-token", "operator_notes": "portfolio-secret-token", "notional_estimate": 10})
    exported = live_portfolio.portfolio_export_json()
    assert "portfolio-secret-token" not in json.dumps(exported)
    assert "portfolio-secret-token" not in live_portfolio.portfolio_export_markdown()


def test_existing_routes_and_gates_still_render_and_block(authed_client):
    for route in ["/v2-live/monitoring", "/v2-live/research", "/v2-live/strategy"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
    submit = authed_client.post("/api/v2/live/order/submit", json={"mode": "live_trading_armed", "side": "BUY", "price": 0.5, "size": 1})
    assert submit.status_code == 200
    assert submit.json().get("network_attempted") is False
    assert submit.json().get("status") in {"blocked_by_risk", "blocked_by_confirmation", "blocked"}
