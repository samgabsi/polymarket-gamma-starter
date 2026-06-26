from __future__ import annotations

import json

from fastapi.testclient import TestClient
import pytest

from app import auth, main as main_module, review_queue
from app.config import APP_VERSION
from app.feature_status import build_stub_burndown_map
from app.main import app


@pytest.fixture()
def isolated_review_queue_store(monkeypatch, tmp_path):
    runtime = tmp_path / "review_queue"
    monkeypatch.setattr(review_queue, "REVIEW_QUEUE_RUNTIME_DIR", runtime)
    monkeypatch.setattr(review_queue, "REVIEW_QUEUE_DECISIONS_PATH", runtime / "decisions.jsonl")
    monkeypatch.setattr(review_queue, "REVIEW_QUEUE_ACTIONS_PATH", runtime / "actions.jsonl")
    monkeypatch.setattr(review_queue, "REVIEW_QUEUE_AUDIT_PATH", runtime / "audit.jsonl")
    yield runtime


@pytest.fixture()
def authed_client(monkeypatch, tmp_path, isolated_review_queue_store):
    async def fake_ranked_opportunities(limit: int = 50):
        return [
            {
                "id": "demo_review_queue_france",
                "market_id": "demo_review_queue_france",
                "title": "Will France win the 2026 FIFA World Cup?",
                "edge": 0.07,
                "confidence_score": 0.64,
                "risk_score": 0.42,
                "evidence_score": 0.72,
            }
        ]

    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    monkeypatch.setattr(main_module, "_ranked_opportunities", fake_ranked_opportunities)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/review-queue"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_v415_review_queue_page_surfaces_real_post_actions_and_safety(authed_client):
    assert APP_VERSION == "4.17.0-real"
    page = authed_client.get("/review-queue?limit=10")
    assert page.status_code == 200
    for text in [
        "Review Queue",
        "Data state:",
        "Review queue actions persist local audit rows only",
        "Mark Reviewed",
        "Add to Watchlist",
        "Send to Paper Review",
        "Reject",
        "Archive",
        "order_submitted=false",
        "trade_approved=false",
    ]:
        assert text in page.text
    assert 'action="/review-queue/demo_review_queue_france/action"' in page.text
    assert 'name="source_component" value="review_queue.table_action"' in page.text


def test_v415_review_queue_browser_action_persists_feedback_and_audit(authed_client, isolated_review_queue_store):
    response = authed_client.post(
        "/review-queue/demo_review_queue_france/action",
        data={
            "action": "add_to_watchlist",
            "market_title": "Will France win the 2026 FIFA World Cup?",
            "previous_state": "UNREVIEWED",
            "reason": "Operator wants to keep monitoring from v4.15 regression test.",
            "data_state": "cached",
            "data_freshness": "cached_runtime",
            "source_route": "/review-queue",
            "source_component": "review_queue.table_action",
            "return_to": "/review-queue?limit=10",
        },
        follow_redirects=False,
    )
    assert response.status_code in {303, 307}
    assert "rq_action=recorded" in response.headers["location"]
    assert "action=add_to_watchlist" in response.headers["location"]
    assert "status=WATCHING" in response.headers["location"]

    feedback = authed_client.get(response.headers["location"])
    assert feedback.status_code == 200
    assert "Recorded" in feedback.text
    assert "WATCHING" in feedback.text

    assert (isolated_review_queue_store / "actions.jsonl").exists()
    rows = [json.loads(line) for line in (isolated_review_queue_store / "actions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[-1]["action"] == "add_to_watchlist"
    assert rows[-1]["previous_state"] == "UNREVIEWED"
    assert rows[-1]["new_state"] == "WATCHING"
    assert rows[-1]["source_component"] == "review_queue.table_action"
    assert rows[-1]["data_state"] == "cached"
    assert rows[-1]["review_only"] is True
    assert rows[-1]["live_disabled"] is True
    assert rows[-1]["order_submitted"] is False
    assert rows[-1]["trade_approved"] is False

    api = authed_client.get("/api/review-queue/actions?market_id=demo_review_queue_france")
    assert api.status_code == 200
    body = api.json()
    assert body["count"] == 1
    assert body["items"][0]["new_state"] == "WATCHING"
    assert body["secret_values_returned"] is False


def test_v415_review_queue_api_contract_and_persisted_state(authed_client):
    created = authed_client.post(
        "/api/review-queue/demo_review_queue_france/action",
        json={
            "action": "send_to_paper_review",
            "market_title": "Will France win the 2026 FIFA World Cup?",
            "previous_state": "UNREVIEWED",
            "reason": "Queue this for paper review context only.",
            "source_route": "/api/review-queue",
            "source_component": "pytest.review_queue_api",
        },
    )
    assert created.status_code == 200
    row = created.json()["item"]
    assert row["new_state"] == "PAPER_REVIEW"
    assert row["source_component"] == "pytest.review_queue_api"
    assert row["order_submitted"] is False

    queue = authed_client.get("/api/review-queue?limit=10")
    assert queue.status_code == 200
    body = queue.json()
    item = body["items"][0]
    assert item["review_status"] == "PAPER_REVIEW"
    assert item["last_action"] == "send_to_paper_review"
    assert body["review_only"] is True
    assert body["trade_approved"] is False
    assert body["secret_values_returned"] is False


def test_v415_feature_readiness_reports_review_queue_completion_truthfully():
    stub_map = build_stub_burndown_map()
    queue = next(row for row in stub_map["items"] if row["feature_id"] == "review.queue_actions")
    assert queue["status"] == "working"
    assert queue["data_state"] == "cached"
    assert queue["safe_review_only"] is True
    assert queue["live_disabled"] is True
    assert "v4.15" in queue["backend_wiring"]
    assert "Review Queue" in queue["visible_surface"]
