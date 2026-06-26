from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_v2, live_v3
from app.config import APP_VERSION
from app.feature_status import build_feature_status_map, build_stub_burndown_map
from app.main import app


@pytest.fixture()
def isolated_v3_settings_runtime(monkeypatch, tmp_path):
    v3_dir = tmp_path / "live_v3"
    monkeypatch.setattr(live_v3, "V3_DIR", v3_dir)
    monkeypatch.setattr(live_v3, "V3_SETTINGS_PATH", v3_dir / "settings.json")
    monkeypatch.setattr(live_v3, "V3_EVENTS_PATH", v3_dir / "v3_events.jsonl")
    live_dir = tmp_path / "live_v2"
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", live_dir)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", live_dir / "audit_ledger.jsonl")
    return v3_dir


@pytest.fixture()
def authed_client(monkeypatch, tmp_path, isolated_v3_settings_runtime):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "test-password-123", "next": "/v3/settings"},
            follow_redirects=False,
        )
        assert response.status_code in {303, 307}
        yield client


def _settings_item(body: dict, key: str) -> dict:
    for section in body["sections"]:
        for item in section["items"]:
            if item["key"] == key:
                return item
    raise AssertionError(f"Missing settings item {key}")


def test_v415_settings_version_identity():
    assert APP_VERSION == "4.17.0-real"


def test_v415_v3_settings_page_surfaces_editable_sources_and_readiness(authed_client):
    page = authed_client.get("/v3/settings")
    assert page.status_code == 200
    for text in [
        "Settings / Feature Readiness Workflow",
        "Editable UI-Safe Preferences",
        "AI odds adjustment mode",
        "Minimum arbitrage confidence",
        "Kalshi adapter enabled",
        "restart required",
        "process environment and .env values remain the runtime source of truth",
        "Feature Readiness Linked to Settings",
        "settings.v3_operator_preferences",
        "saving this v3 preference form never places orders",
    ]:
        assert text in page.text
    assert 'action="/v3/settings/preferences/save"' in page.text
    assert 'name="setting__ai_odds_adjustment_mode"' in page.text
    assert 'name="setting__arbitrage_min_confidence"' in page.text


def test_v415_v3_settings_browser_save_persists_feedback_and_audit(authed_client, isolated_v3_settings_runtime):
    response = authed_client.post(
        "/v3/settings/preferences/save",
        data={
            "setting__ai_odds_adjustment_mode": "balanced",
            "setting__arbitrage_min_confidence": "0.84",
            "setting__kalshi_enabled": "false",
        },
        follow_redirects=False,
    )
    assert response.status_code in {303, 307}
    assert "settings_preferences_saved" in response.headers["location"]
    assert "ai_odds_adjustment_mode" in response.headers["location"]

    feedback = authed_client.get(response.headers["location"])
    assert feedback.status_code == 200
    assert "Settings Preferences Saved" in feedback.text
    assert "ui_preference" in feedback.text
    assert "0.84" in feedback.text

    api = authed_client.get("/api/v3/settings")
    assert api.status_code == 200
    body = api.json()
    assert body["configured_preference_count"] >= 3
    assert body["operator_feedback"]["secrets_masked"] is True
    assert body["operator_feedback"]["runtime_env_not_mutated"] is True
    assert body["order_submitted"] is False
    assert body["live_disabled"] is True
    mode = _settings_item(body, "ai_odds_adjustment_mode")
    confidence = _settings_item(body, "arbitrage_min_confidence")
    assert mode["saved_preference"] == "balanced"
    assert mode["source"] == "ui_preference"
    assert confidence["saved_preference"] == 0.84
    assert confidence["requires_restart"] is True

    saved = json.loads((isolated_v3_settings_runtime / "settings.json").read_text(encoding="utf-8"))
    assert saved["preferences"]["ai_odds_adjustment_mode"] == "balanced"
    assert saved["preferences"]["arbitrage_min_confidence"] == 0.84
    assert saved["source_component"] == "v3_settings.preferences_form"
    assert saved["order_submitted"] is False
    assert saved["trade_approved"] is False

    events = [json.loads(line) for line in (isolated_v3_settings_runtime / "v3_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    saved_events = [row for row in events if row.get("action") == "settings_preferences_saved"]
    assert saved_events
    saved_event = saved_events[-1]
    assert saved_event["status"] == "ok"
    assert saved_event["details"]["source_component"] == "v3_settings.preferences_form"
    assert saved_event["details"]["runtime_env_mutated"] is False
    assert saved_event["details"]["live_disabled"] is True


def test_v415_v3_settings_invalid_numeric_rejected_without_overwriting(authed_client, isolated_v3_settings_runtime):
    ok = authed_client.post("/api/v3/settings", json={"arbitrage_min_confidence": "0.75"})
    assert ok.status_code == 200
    assert ok.json()["ok"] is True

    bad = authed_client.post("/api/v3/settings", json={"arbitrage_min_confidence": "2.0"})
    assert bad.status_code == 200
    body = bad.json()
    assert body["ok"] is False
    assert body["order_submitted"] is False
    assert body["trade_approved"] is False
    assert body["errors"][0]["key"] == "arbitrage_min_confidence"
    assert "<= 1.0" in body["errors"][0]["error"]

    saved = json.loads((isolated_v3_settings_runtime / "settings.json").read_text(encoding="utf-8"))
    assert saved["preferences"]["arbitrage_min_confidence"] == 0.75
    events = [json.loads(line) for line in (isolated_v3_settings_runtime / "v3_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert events[-1]["action"] == "settings_preferences_rejected"
    assert events[-1]["status"] == "blocked"


def test_v415_feature_status_reports_v3_settings_workflow_truthfully():
    feature_status = build_feature_status_map()
    item = next(row for row in feature_status["items"] if row["feature_id"] == "settings.v3_operator_preferences")
    assert item["status"] == "working"
    assert item["data_state"] == "cached"
    assert item["safe_review_only"] is True
    assert item["live_disabled"] is True
    assert "does not mutate process env" in item["reason"]
    assert "Saved v3 preferences" in item["operator_implication"]

    stub_map = build_stub_burndown_map()
    settings_row = next(row for row in stub_map["items"] if row["feature_id"] == "settings.config")
    assert settings_row["status"] == "working"
    assert "v3 settings persistence" in settings_row["backend_wiring"]
    assert settings_row["safe_review_only"] is True
