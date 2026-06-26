from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, live_v2
from app.main import app


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "test-password-123", "next": "/v2-live"},
            follow_redirects=False,
        )
        assert response.status_code in {303, 307}
        yield client


def test_live_v2_ui_routes_render_without_network(monkeypatch, tmp_path, authed_client):
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", tmp_path / "live_v2")
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", tmp_path / "live_v2" / "audit_ledger.jsonl")
    routes = [
        "/v2-live",
        "/v2-live/markets",
        "/v2-live/trade-ticket",
        "/v2-live/strategy",
        "/v2-live/research",
        "/v2-live/monitoring",
        "/v2-live/portfolio",
        "/v2-live/orders",
        "/v2-live/positions",
        "/v2-live/risk",
        "/v2-live/audit",
        "/v2-live/settings",
        "/v2-live/emergency",
        "/v2-live/docs",
    ]
    for route in routes:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "Live v2 Console" in response.text
        assert "v4.7.0-real" in response.text


def test_live_v2_settings_schema_and_validation_do_not_return_secrets(authed_client):
    schema = authed_client.get("/api/v2/live/settings/schema")
    assert schema.status_code == 200
    body = schema.json()
    assert body["secret_values_returned"] is False
    assert any(section["title"] == "Risk Limits" for section in body["sections"])

    response = authed_client.post("/api/v2/live/settings/validate", json={"POLYMARKET_V2_TRADING_MODE": "live_trading_armed", "READ_ONLY": "true"})
    assert response.status_code == 200
    result = response.json()
    assert result["valid"] is True
    assert result["secret_values_returned"] is False
    assert result["warnings"]


def test_live_v2_markdown_audit_export(monkeypatch, tmp_path, authed_client):
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", tmp_path / "live_v2")
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", tmp_path / "live_v2" / "audit_ledger.jsonl")
    live_v2.record_audit("ui_test", "ok", details={"hello": "world"})
    response = authed_client.get("/api/v2/live/audit.md")
    assert response.status_code == 200
    assert "Live v2 Audit Report" in response.text
    assert "ui_test" in response.text


def test_docs_route_serves_markdown_safely(authed_client):
    response = authed_client.get("/docs/LIVE_TRADING_V2.md")
    assert response.status_code == 200
    assert "Live Trading" in response.text
    assert authed_client.get("/docs/../README.md").status_code == 404


def test_live_v2_preferences_schema_api(authed_client):
    response = authed_client.get("/api/v2/live/ui/preferences/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["secret_values_allowed"] is False
    assert body["sensitive_data_allowed"] is False
    assert body["storage_key"] == "polymarketGamma.liveV2.uiPrefs.v2"


def test_live_v2_audit_filter_api(monkeypatch, tmp_path, authed_client):
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", tmp_path / "live_v2")
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", tmp_path / "live_v2" / "audit_ledger.jsonl")
    live_v2.record_audit("ticket_preview", "blocked", details={"hello": "world"})
    live_v2.record_audit("emergency_control", "recorded", details={"hello": "emergency"})
    response = authed_client.get("/api/v2/live/audit?action=emergency&search=emergency&limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["action"] == "emergency_control"
