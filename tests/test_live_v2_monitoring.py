from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_monitoring, live_research, live_strategy, live_v2
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_monitoring(tmp_path, monkeypatch):
    monitoring_dir = tmp_path / "monitoring"
    research_dir = tmp_path / "research"
    strategy_dir = tmp_path / "strategy"
    live_dir = tmp_path / "live_v2"
    monkeypatch.setattr(live_monitoring, "MONITORING_DIR", monitoring_dir)
    monkeypatch.setattr(live_monitoring, "MONITORING_EVENTS_PATH", monitoring_dir / "monitoring_events.jsonl")
    monkeypatch.setattr(live_research, "RESEARCH_DIR", research_dir)
    monkeypatch.setattr(live_research, "RESEARCH_EVENTS_PATH", research_dir / "research_events.jsonl")
    monkeypatch.setattr(live_strategy, "STRATEGY_DIR", strategy_dir)
    monkeypatch.setattr(live_strategy, "STRATEGY_EVENTS_PATH", strategy_dir / "strategy_events.jsonl")
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", live_dir)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", live_dir / "audit_ledger.jsonl")
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v2-live/monitoring"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_version_is_v2_6():
    assert APP_VERSION == "4.17.0-real"


def test_monitoring_rule_lifecycle_exports_and_safety():
    rule = live_monitoring.create_rule({
        "rule_name": "Entry price reached",
        "rule_type": "price_threshold",
        "condition": "above",
        "threshold_value": 0.55,
        "severity": "warning",
        "related_market_id": "market-1",
    })
    assert rule["ok"] is True
    assert rule["order_submitted"] is False
    rid = rule["item"]["id"]
    updated = live_monitoring.update_rule(rid, {"threshold_value": 0.50})
    assert updated["item"]["threshold_value"] == 0.50
    result = live_monitoring.evaluate_rule(rid, {"current_value": 0.75})
    assert result["triggered"] is True
    assert result["order_submitted"] is False
    assert result["order_cancelled"] is False
    alert = result["alert"]
    assert alert["status"] == "active"
    ack = live_monitoring.acknowledge_alert(alert["id"])
    assert ack["item"]["status"] == "acknowledged"
    result2 = live_monitoring.evaluate_rule(rid, {"current_value": 0.75})
    snooze = live_monitoring.snooze_alert(result2["alert"]["id"], minutes=5)
    assert snooze["item"]["status"] == "snoozed"
    disabled = live_monitoring.disable_rule(rid)
    assert disabled["item"]["status"] == "disabled"
    archived = live_monitoring.archive_rule(rid)
    assert archived["item"]["status"] == "archived"
    exported = live_monitoring.monitoring_export_json()
    assert exported["summary"]["rules"] >= 1
    md = live_monitoring.monitoring_export_markdown()
    assert "Monitoring / Alerts Export" in md
    assert "does not approve, place, or cancel orders" in md
    assert "rule_name" in live_monitoring.monitoring_csv("rules")
    assert "recommended_operator_action" in live_monitoring.monitoring_csv("alerts")


def test_monitoring_actions_create_audit_events():
    live_monitoring.create_rule({"rule_name": "Audit monitor", "rule_type": "watchlist", "condition": "manual"})
    rows = live_v2.list_audit_records()
    assert any(row["action"].startswith("monitoring_monitor_rule_created") for row in rows)


def test_monitoring_routes_and_api_endpoints(authed_client):
    page = authed_client.get("/v2-live/monitoring")
    assert page.status_code == 200
    assert "Monitoring / Alert Workflow" in page.text
    assert "v4.7.0-real" in page.text
    create = authed_client.post("/api/v2/live/monitoring/rules", json={"rule_name": "Route rule", "rule_type": "price_threshold", "condition": "above", "threshold_value": 0.1, "severity": "watch"})
    assert create.status_code == 200
    rid = create.json()["item"]["id"]
    assert authed_client.get("/api/v2/live/monitoring/rules").status_code == 200
    assert authed_client.get(f"/api/v2/live/monitoring/rules/{rid}").status_code == 200
    assert authed_client.post(f"/api/v2/live/monitoring/rules/{rid}", json={"severity": "critical"}).status_code == 200
    evaluated = authed_client.post(f"/api/v2/live/monitoring/rules/{rid}/evaluate", json={"current_value": 0.9})
    assert evaluated.status_code == 200
    body = evaluated.json()
    assert body["triggered"] is True
    assert body["order_submitted"] is False
    alert_id = body["alert"]["id"]
    assert authed_client.get("/api/v2/live/monitoring/alerts").status_code == 200
    assert authed_client.post(f"/api/v2/live/monitoring/alerts/{alert_id}/acknowledge").status_code == 200
    evaluated2 = authed_client.post(f"/api/v2/live/monitoring/rules/{rid}/evaluate", json={"current_value": 0.9}).json()
    assert authed_client.post(f"/api/v2/live/monitoring/alerts/{evaluated2['alert']['id']}/snooze", json={"minutes": 10}).status_code == 200
    assert authed_client.post(f"/api/v2/live/monitoring/rules/{rid}/disable").status_code == 200
    assert authed_client.post(f"/api/v2/live/monitoring/rules/{rid}/archive").status_code == 200
    assert authed_client.post("/api/v2/live/monitoring/evaluate", json={"current_value": 1.0}).status_code == 200
    assert authed_client.get("/api/v2/live/monitoring/history").status_code == 200
    assert authed_client.get("/api/v2/live/monitoring/export.json").status_code == 200
    md = authed_client.get("/api/v2/live/monitoring/export.md")
    assert md.status_code == 200
    assert "Monitoring / Alerts Export" in md.text
    assert authed_client.get("/api/v2/live/monitoring/export/rules.csv").status_code == 200
    assert authed_client.get("/api/v2/live/monitoring/export/alerts.csv").status_code == 200


def test_monitoring_exports_redact_secrets(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "monitoring-secret-token")
    live_monitoring.create_rule({"rule_name": "monitoring-secret-token", "operator_notes": "monitoring-secret-token", "rule_type": "watchlist"})
    exported = live_monitoring.monitoring_export_json()
    assert "monitoring-secret-token" not in json.dumps(exported)
    assert "monitoring-secret-token" not in live_monitoring.monitoring_export_markdown()


def test_existing_research_strategy_routes_still_render(authed_client):
    assert authed_client.get("/v2-live/research").status_code == 200
    assert authed_client.get("/v2-live/strategy").status_code == 200
    preview = authed_client.post("/api/v2/live/ticket/preview", json={"mode": "paper", "side": "BUY", "price": 0.5, "size": 1})
    assert preview.status_code == 200
    submit = authed_client.post("/api/v2/live/order/submit", json={"mode": "live_trading_armed", "side": "BUY", "price": 0.5, "size": 1})
    assert submit.status_code == 200
    assert submit.json().get("network_attempted") is False
    assert submit.json().get("status") in {"blocked_by_risk", "blocked_by_confirmation", "blocked"}
