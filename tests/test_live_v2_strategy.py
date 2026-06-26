from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_strategy, live_v2
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_strategy(tmp_path, monkeypatch):
    strategy_dir = tmp_path / "strategy"
    monkeypatch.setattr(live_strategy, "STRATEGY_DIR", strategy_dir)
    monkeypatch.setattr(live_strategy, "STRATEGY_EVENTS_PATH", strategy_dir / "strategy_events.jsonl")
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", tmp_path / "live_v2")
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", tmp_path / "live_v2" / "audit_ledger.jsonl")
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v2-live/strategy"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_version_is_v2_4():
    assert APP_VERSION == "4.17.0-real"


def test_strategy_create_edit_archive_and_exports():
    created = live_strategy.create_thesis({"market_title": "Will test pass?", "market_id": "m1", "outcome": "YES", "thesis_summary": "Unit test", "probability_estimate": 0.62})
    assert created["ok"] is True
    thesis_id = created["item"]["id"]
    edited = live_strategy.update_thesis(thesis_id, {"status": "ready_for_ticket", "entry_criteria": "price <= .55"})
    assert edited["item"]["status"] == "ready_for_ticket"
    evidence = live_strategy.create_evidence({"thesis_id": thesis_id, "title": "Source", "direction": "supports", "relevance_score": 4, "credibility_score": 4})
    assert evidence["ok"] is True
    watch = live_strategy.create_watchlist_item({"market_title": "Will test pass?", "market_id": "m1", "priority": "high"})
    assert watch["item"]["priority"] == "high"
    score = live_strategy.create_scorecard({"thesis_id": thesis_id, "liquidity": 5, "spread": 4, "market_clarity": 5, "information_quality": 4, "evidence_strength": 4, "risk_reward": 3, "operator_confidence": 4, "execution_readiness": 3})
    assert score["item"]["total_score"] > 0
    review = live_strategy.create_review({"thesis_id": thesis_id, "risk_rules_followed": True, "lesson_learned": "Review process worked"})
    assert review["ok"] is True
    draft = live_strategy.build_ticket_from_thesis(thesis_id)
    assert draft["order_submitted"] is False
    assert draft["network_attempted"] is False
    assert draft["ticket"]["strategy_ref"] == thesis_id
    exported = live_strategy.strategy_export_json()
    text = json.dumps(exported)
    assert thesis_id in text
    assert "secret_values_returned" in text
    md = live_strategy.strategy_export_markdown()
    assert "Strategy / Playbook Export" in md
    archived = live_strategy.archive_thesis(thesis_id)
    assert archived["ok"] is True
    assert live_strategy.get_strategy_item("theses", thesis_id)["status"] == "archived"


def test_strategy_actions_create_audit_events():
    live_strategy.create_thesis({"market_title": "Audit test", "market_id": "audit-market"})
    rows = live_v2.list_audit_records()
    assert any(row["action"].startswith("strategy_thesis_created") for row in rows)


def test_strategy_route_and_api_endpoints(authed_client):
    page = authed_client.get("/v2-live/strategy")
    assert page.status_code == 200
    assert "Strategy Workspace" in page.text
    created = authed_client.post("/api/v2/live/strategy/theses", json={"market_title": "API market", "market_id": "api-1", "outcome": "YES", "thesis_summary": "API thesis"})
    assert created.status_code == 200
    thesis_id = created.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/strategy/theses/{thesis_id}", json={"status": "watching"}).status_code == 200
    assert authed_client.post("/api/v2/live/strategy/evidence", json={"thesis_id": thesis_id, "title": "Manual source", "direction": "neutral"}).status_code == 200
    assert authed_client.post("/api/v2/live/strategy/watchlist", json={"market_id": "api-1", "market_title": "API market"}).status_code == 200
    assert authed_client.post("/api/v2/live/strategy/scorecards", json={"thesis_id": thesis_id, "liquidity": 4}).status_code == 200
    assert authed_client.post("/api/v2/live/strategy/reviews", json={"thesis_id": thesis_id, "lesson_learned": "test"}).status_code == 200
    ticket = authed_client.post(f"/api/v2/live/strategy/theses/{thesis_id}/ticket-draft")
    assert ticket.status_code == 200
    assert ticket.json()["order_submitted"] is False
    assert authed_client.get("/api/v2/live/strategy/export.json").status_code == 200
    md = authed_client.get("/api/v2/live/strategy/export.md")
    assert md.status_code == 200
    assert "Strategy / Playbook Export" in md.text
    assert authed_client.get("/api/v2/live/strategy/evidence.csv").status_code == 200


def test_strategy_exports_redact_secrets(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "super-secret-test-value")
    live_strategy.create_thesis({"market_title": "Secret super-secret-test-value", "operator_notes": "super-secret-test-value"})
    exported = live_strategy.strategy_export_json()
    assert "super-secret-test-value" not in json.dumps(exported)
    assert "super-secret-test-value" not in live_strategy.strategy_export_markdown()
