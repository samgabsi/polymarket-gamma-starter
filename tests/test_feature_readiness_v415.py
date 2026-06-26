from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app import auth, feature_status
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_feature_readiness(monkeypatch, tmp_path):
    readiness_dir = tmp_path / "feature_readiness"
    monkeypatch.setattr(feature_status, "FEATURE_READINESS_RUNTIME_DIR", readiness_dir)
    monkeypatch.setattr(feature_status, "FEATURE_READINESS_AUDIT_PATH", readiness_dir / "readiness_acknowledgements.jsonl")
    yield readiness_dir


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "test-password-123", "next": "/v3/feature-readiness"},
            follow_redirects=False,
        )
        assert response.status_code in {303, 307}
        yield client


def test_v415_feature_readiness_version_identity():
    assert APP_VERSION == "4.17.0-real"


def test_v415_feature_readiness_page_filters_and_explains_truthfulness(authed_client):
    response = authed_client.get("/v3/feature-readiness?status=working&area=settings")
    assert response.status_code == 200
    for text in [
        "Feature Readiness",
        "Record readiness review",
        "Feature status registry",
        "Stub burn-down map",
        "review-only",
        "live disabled",
        "Settings and configuration",
        "v3 settings UI preferences",
    ]:
        assert text in response.text
    assert "secrets masked" in response.text.lower() or "Secrets returned" in response.text
    assert 'method="post" action="/v3/feature-readiness/acknowledge"' in response.text


def test_v415_feature_readiness_acknowledgement_persists_audit_and_feedback(authed_client, isolated_feature_readiness):
    response = authed_client.post(
        "/v3/feature-readiness/acknowledge",
        data={
            "status_filter": "working",
            "area_filter": "settings",
            "operator_note": "Reviewed settings readiness before operating.",
            "return_to": "/v3/feature-readiness?status=working&area=settings",
        },
        follow_redirects=False,
    )
    assert response.status_code in {303, 307}
    location = response.headers["location"]
    assert "action_status=feature_readiness_acknowledged" in location
    assert "action_detail=readiness_ack_" in location

    ack_path = isolated_feature_readiness / "readiness_acknowledgements.jsonl"
    assert ack_path.exists()
    ack = feature_status.list_feature_readiness_acknowledgements(limit=5)
    assert ack["count"] == 1
    item = ack["items"][0]
    assert item["action_type"] == "readiness_review_acknowledgement"
    assert item["status_filter"] == "working"
    assert item["area_filter"] == "settings"
    assert item["review_only"] is True
    assert item["live_disabled"] is True
    assert item["order_submitted"] is False
    assert item["trade_approved"] is False
    assert item["secret_values_returned"] is False

    feedback = authed_client.get(location)
    assert feedback.status_code == 200
    assert "Feature Readiness Acknowledged" in feedback.text
    assert item["acknowledgement_id"] in feedback.text


def test_v415_feature_readiness_api_is_secret_safe_and_review_only(authed_client):
    posted = authed_client.post(
        "/api/v3/features/readiness/acknowledgements",
        json={
            "status_filter": "working",
            "area_filter": "settings",
            "note": "API acknowledgement regression check.",
            "source_component": "pytest.api",
        },
    )
    assert posted.status_code == 200
    posted_body = posted.json()
    assert posted_body["ok"] is True
    assert posted_body["item"]["live_disabled"] is True
    assert posted_body["item"]["order_submitted"] is False
    assert posted_body["item"]["order_cancelled"] is False
    assert posted_body["item"]["trade_approved"] is False
    assert posted_body["item"]["secret_values_returned"] is False

    response = authed_client.get("/api/v3/features/readiness?status=working&area=settings")
    assert response.status_code == 200
    body = response.json()
    assert body["app_version"] == "4.17.0-real"
    assert body["data_state"] == "cached"
    assert body["secret_values_returned"] is False
    assert body["live_disabled"] is True
    assert body["safe_review_only"] is True
    assert body["feature_rows"]
    assert body["stub_rows"]
    assert all(row["status"] == "working" for row in body["feature_rows"] + body["stub_rows"])
    assert all(row["area"] == "settings" for row in body["feature_rows"] + body["stub_rows"])


def test_v415_feature_readiness_status_entries_are_truthful():
    status = feature_status.build_feature_status_map()
    readiness = next(row for row in status["items"] if row["feature_id"] == "features.readiness_review_page")
    assert readiness["status"] == "working"
    assert readiness["route"] == "/v3/feature-readiness"
    assert readiness["api_route"] == "/api/v3/features/readiness/acknowledgements"
    assert readiness["data_state"] == "cached"
    assert readiness["live_disabled"] is True

    stub = feature_status.build_stub_burndown_map()
    row = next(item for item in stub["items"] if item["feature_id"] == "features.readiness_page")
    assert row["status"] == "working"
    assert row["route"] == "/v3/feature-readiness"
    assert row["api_route"] == "/api/v3/features/readiness/acknowledgements"
    assert "acknowledgement" in row["ui_wiring"].lower()
