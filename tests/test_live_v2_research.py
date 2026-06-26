from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_research, live_strategy, live_v2
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_research(tmp_path, monkeypatch):
    research_dir = tmp_path / "research"
    strategy_dir = tmp_path / "strategy"
    live_dir = tmp_path / "live_v2"
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
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v2-live/research"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_version_is_v2_6():
    assert APP_VERSION == "4.17.0-real"


def test_research_source_queue_note_candidate_conversion_and_exports():
    thesis = live_strategy.create_thesis({"market_title": "Research market", "market_id": "m-research", "thesis_summary": "Research thesis"})["item"]
    source = live_research.create_source({"title": "Official source", "source_url": "https://example.com/report", "source_type": "official_announcement", "related_thesis_id": thesis["id"], "credibility_rating": 5, "relevance_rating": 4, "freshness_status": "fresh"})
    assert source["ok"] is True
    source_id = source["item"]["id"]
    assert live_research.mark_source_reviewed(source_id)["item"]["status"] == "reviewed"
    assert live_research.mark_source_stale(source_id, "old catalyst")["item"]["status"] == "stale"
    queue = live_research.create_queue_item({"title": "Review source", "source_id": source_id, "priority": "high", "related_thesis_id": thesis["id"], "research_question": "Does this support the thesis?"})
    assert queue["item"]["priority"] == "high"
    updated_queue = live_research.update_queue_item(queue["item"]["id"], {"status": "in_review"})
    assert updated_queue["item"]["status"] == "in_review"
    note = live_research.create_note({"title": "Source note", "source_id": source_id, "related_thesis_id": thesis["id"], "summary": "Important claim"})
    assert note["ok"] is True
    candidate = live_research.create_evidence_candidate({"title": "Candidate evidence", "source_id": source_id, "note_id": note["item"]["id"], "related_thesis_id": thesis["id"], "direction": "supports", "evidence_relevance_score": 5, "credibility_score": 5, "freshness_score": 4, "freshness_status": "fresh"})
    converted = live_research.convert_candidate(candidate["item"]["id"])
    assert converted["ok"] is True
    assert converted["order_submitted"] is False
    assert converted["network_attempted"] is False
    assert converted["evidence"]["thesis_id"] == thesis["id"]
    freshness = live_research.freshness_summary()
    assert freshness["summary"]["stale_sources"] >= 1
    comparison = live_research.build_thesis_comparison(thesis["id"])
    assert comparison["supporting_evidence_count"] >= 1
    exported = live_research.research_export_json()
    assert exported["summary"]["sources"] >= 1
    md = live_research.research_export_markdown()
    assert "Research Intake Export" in md
    assert "does not place" in md
    assert "source_url" in live_research.research_csv("sources")


def test_research_actions_create_audit_events():
    live_research.create_source({"title": "Audit source", "source_type": "operator_note"})
    rows = live_v2.list_audit_records()
    assert any(row["action"].startswith("research_source_created") for row in rows)


def test_research_routes_and_api_endpoints(authed_client):
    page = authed_client.get("/v2-live/research")
    assert page.status_code == 200
    assert "Research Intake Workspace" in page.text
    assert "v4.7.0-real" in page.text
    thesis = authed_client.post("/api/v2/live/strategy/theses", json={"market_title": "Route market", "market_id": "route-1", "thesis_summary": "route thesis"}).json()["item"]
    source_resp = authed_client.post("/api/v2/live/research/sources", json={"title": "Route source", "source_type": "news", "related_thesis_id": thesis["id"]})
    assert source_resp.status_code == 200
    source_id = source_resp.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/research/sources/{source_id}", json={"status": "queued"}).status_code == 200
    assert authed_client.post(f"/api/v2/live/research/sources/{source_id}/mark-reviewed").status_code == 200
    assert authed_client.post(f"/api/v2/live/research/sources/{source_id}/mark-stale", json={"stale_reason": "test"}).status_code == 200
    queue = authed_client.post("/api/v2/live/research/queue", json={"title": "Route queue", "source_id": source_id, "related_thesis_id": thesis["id"]})
    assert queue.status_code == 200
    assert authed_client.post(f"/api/v2/live/research/queue/{queue.json()['item']['id']}", json={"status": "reviewed"}).status_code == 200
    note = authed_client.post("/api/v2/live/research/notes", json={"title": "Route note", "source_id": source_id, "related_thesis_id": thesis["id"]})
    assert note.status_code == 200
    candidate = authed_client.post("/api/v2/live/research/evidence-candidates", json={"title": "Route candidate", "source_id": source_id, "note_id": note.json()["item"]["id"], "related_thesis_id": thesis["id"], "direction": "supports"})
    assert candidate.status_code == 200
    converted = authed_client.post(f"/api/v2/live/research/evidence-candidates/{candidate.json()['item']['id']}/convert")
    assert converted.status_code == 200
    assert converted.json()["order_submitted"] is False
    assert authed_client.get("/api/v2/live/research/freshness").status_code == 200
    assert authed_client.get(f"/api/v2/live/research/thesis-comparison?thesis_id={thesis['id']}").status_code == 200
    assert authed_client.get("/api/v2/live/research/export.json").status_code == 200
    md = authed_client.get("/api/v2/live/research/export.md")
    assert md.status_code == 200
    assert "Research Intake Export" in md.text
    assert authed_client.get("/api/v2/live/research/sources.csv").status_code == 200


def test_research_exports_redact_secrets(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "research-secret-token")
    live_research.create_source({"title": "Secret research-secret-token", "operator_notes": "research-secret-token", "source_url": "https://example.com/research-secret-token"})
    exported = live_research.research_export_json()
    assert "research-secret-token" not in json.dumps(exported)
    assert "research-secret-token" not in live_research.research_export_markdown()
