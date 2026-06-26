from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_v2
from app.config import APP_VERSION
from app.main import app


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", tmp_path / "live_v2")
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", tmp_path / "live_v2" / "audit_ledger.jsonl")
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v2-live"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_version_is_v2_4():
    assert APP_VERSION == "4.17.0-real"


def test_verification_report_without_network_is_safe(monkeypatch):
    for key in ["POLYMARKET_LIVE_ALLOW_REAL_NETWORK", "POLYMARKET_LIVE_NETWORK_READONLY", "POLYMARKET_V2_TRADING_MODE"]:
        monkeypatch.delenv(key, raising=False)
    import asyncio
    report = asyncio.run(live_v2.build_live_v2_verification_report(attempt_network=False))
    assert report["version"] == "4.17.0-real"
    assert report["secret_values_returned"] is False
    assert "No real order placement" in report["safety_statement"]
    assert any(row["name"] == "network_checks" and row["status"] == "skipped" for row in report["checks"])
    assert "private" not in json.dumps(report).lower() or "[redacted]" in json.dumps(report).lower()


def test_demo_readiness_report():
    report = live_v2.build_live_v2_demo_readiness()
    assert report["version"] == "4.17.0-real"
    assert report["secret_values_returned"] is False
    assert any(row["name"] == "live_not_armed_by_default" for row in report["checks"])


def test_verification_markdown_export():
    md = live_v2.live_v2_verification_to_markdown({"version": "4.17.0-real", "generated_at": "now", "overall_status": "pass", "checks": [{"name": "x", "status": "pass", "explanation": "ok", "error_redacted": ""}], "safety_statement": "No real order placement or cancellation was performed."})
    assert "Live Read-Only Verification Report" in md
    assert "No real order placement" in md


def test_verify_routes_render_and_export(authed_client):
    response = authed_client.get("/v2-live/verify")
    assert response.status_code == 200
    assert "Live Read-Only Verification Harness" in response.text
    api = authed_client.get("/api/v2/live/verify")
    assert api.status_code == 200
    assert api.json()["secret_values_returned"] is False
    md = authed_client.get("/api/v2/live/verify/report.md")
    assert md.status_code == 200
    assert "Live Read-Only Verification Report" in md.text
    demo = authed_client.get("/api/v2/live/demo-readiness")
    assert demo.status_code == 200
    assert demo.json()["secret_values_returned"] is False


def test_required_v2_live_routes_still_exist(authed_client):
    routes = ["/v2-live", "/v2-live/markets", "/v2-live/trade-ticket", "/v2-live/strategy", "/v2-live/portfolio", "/v2-live/orders", "/v2-live/positions", "/v2-live/risk", "/v2-live/audit", "/v2-live/settings", "/v2-live/emergency", "/v2-live/verify", "/v2-live/docs"]
    for route in routes:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.7.0-real" in response.text
