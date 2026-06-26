from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, review_queue
from app.config import APP_VERSION
from app.feature_status import build_feature_status_map, build_stub_burndown_map
from app.main import app


@pytest.fixture(autouse=True)
def isolated_review_queue_runtime(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "review_queue"
    monkeypatch.setattr(review_queue, "REVIEW_QUEUE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(review_queue, "REVIEW_QUEUE_DECISIONS_PATH", runtime_dir / "decisions.jsonl")
    monkeypatch.setattr(review_queue, "REVIEW_QUEUE_ACTIONS_PATH", runtime_dir / "actions.jsonl")
    monkeypatch.setattr(review_queue, "REVIEW_QUEUE_AUDIT_PATH", runtime_dir / "audit.jsonl")
    yield runtime_dir


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "test-password-123", "next": "/review-queue"},
            follow_redirects=False,
        )
        assert response.status_code in {303, 307}
        yield client


def test_v415_version_identity():
    assert APP_VERSION == "4.17.0-real"


def test_v415_review_queue_demo_api_is_truthful_and_review_only(authed_client):
    response = authed_client.get("/api/review-queue?demo=true&limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "4.17.0-real"
    assert body["data_state"] == "sample"
    assert body["requested_data_mode"] == "demo_fixtures"
    assert body["source_state"] == "demo_fixture"
    assert body["review_only"] is True
    assert body["live_disabled"] is True
    assert body["order_submitted"] is False
    assert body["order_cancelled"] is False
    assert body["trade_approved"] is False
    assert body["secret_values_returned"] is False
    assert body["items"]
    assert {row["action"] for row in body["available_actions"]} >= {"mark_reviewed", "add_to_watchlist", "reject"}
    first = body["items"][0]
    assert first["data_state"] == "sample"
    assert first["review_status"] == "UNREVIEWED"
    assert first["actions"]


def test_v415_review_queue_page_has_working_forms_and_empty_state(authed_client):
    page = authed_client.get("/review-queue?demo=true&limit=5")
    assert page.status_code == 200
    for text in [
        "Review Queue",
        "Data state",
        "Demo fixtures",
        "Mark Reviewed",
        "Add to Watchlist",
        "No order is submitted or cancelled",
    ]:
        assert text in page.text
    assert 'method="post" action="/review-queue/' in page.text
    assert 'name="source_component" value="review_queue.table_action"' in page.text

    empty = authed_client.get("/review-queue?demo=false&limit=1")
    assert empty.status_code == 200
    assert "Configured source" in empty.text
    assert "No review queue items" in empty.text or "Queue items" in empty.text


def test_v415_review_queue_browser_action_persists_state_and_audit(authed_client):
    body = authed_client.get("/api/review-queue?demo=true&limit=5").json()
    market_id = body["items"][0]["market_id"]
    title = body["items"][0]["title"]

    response = authed_client.post(
        f"/review-queue/{market_id}/action",
        data={
            "action": "add_to_watchlist",
            "market_title": title,
            "previous_state": "UNREVIEWED",
            "queue_stage": body["items"][0]["stage"],
            "queue_action": body["items"][0]["action"],
            "reason": "Regression test added review item to watchlist.",
            "data_state": "sample",
            "data_freshness": "sample_fixture",
            "source_state": "demo_fixture",
            "source_route": "/review-queue?demo=true",
            "source_component": "review_queue.table_action",
            "return_to": "/review-queue?demo=true",
        },
        follow_redirects=False,
    )
    assert response.status_code in {303, 307}
    assert "rq_action=recorded" in response.headers["location"]
    assert "status=WATCHING" in response.headers["location"]

    page = authed_client.get(response.headers["location"])
    assert page.status_code == 200
    assert "WATCHING" in page.text
    assert "Recorded" in page.text

    actions = review_queue.list_review_queue_actions(market_id=market_id)
    assert actions
    latest = actions[0]
    assert latest["new_state"] == "WATCHING"
    assert latest["previous_state"] == "UNREVIEWED"
    assert latest["source_component"] == "review_queue.table_action"
    assert latest["data_state"] == "sample"
    assert latest["review_only"] is True
    assert latest["live_disabled"] is True
    assert latest["order_submitted"] is False
    assert latest["order_cancelled"] is False
    assert latest["trade_approved"] is False
    assert latest["live_trading_armed"] is False
    assert latest["audit_history"][-1]["action_type"] == "operator_decision"
    assert latest["audit_history"][-1]["source_route"] == "/review-queue?demo=true"

    refreshed = authed_client.get("/api/review-queue?demo=true&limit=5").json()
    refreshed_item = next(row for row in refreshed["items"] if row["market_id"] == market_id)
    assert refreshed_item["review_status"] == "WATCHING"
    assert refreshed_item["last_action"] == "add_to_watchlist"


def test_v415_review_queue_json_action_rejects_secret_like_notes(authed_client):
    market_id = authed_client.get("/api/review-queue?demo=true&limit=1").json()["items"][0]["market_id"]
    response = authed_client.post(
        f"/api/review-queue/{market_id}/action",
        json={"action": "mark_reviewed", "operator_note": "api_key=super-secret-value"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "secret_like_content_rejected"
    assert body["review_only"] is True
    assert body["live_disabled"] is True


def test_v415_feature_readiness_reports_review_queue_truthfully():
    stub = build_stub_burndown_map()
    queue_stub = next(row for row in stub["items"] if row["feature_id"] == "review.queue_actions")
    assert queue_stub["status"] == "working"
    assert queue_stub["route"] == "/review-queue"
    assert queue_stub["safe_review_only"] is True
    assert "Review Queue POST actions" in queue_stub["backend_wiring"]

    status = build_feature_status_map()
    queue_status = next(row for row in status["items"] if row["feature_id"] == "review.queue_actions")
    assert queue_status["status"] == "working"
    assert queue_status["api_route"] == "/api/review-queue/{market_id}/action"
    assert queue_status["live_disabled"] is True
    assert "cannot approve" in queue_status["operator_implication"]
