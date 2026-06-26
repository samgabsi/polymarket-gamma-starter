from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app import auth, opportunity_review
from app.config import APP_VERSION
from app.feature_status import build_feature_status_map, build_stub_burndown_map
from app.main import app
from app.opportunity_review import build_opportunity_workbench, demo_markets, get_review_record


@pytest.fixture()
def isolated_review_store(monkeypatch, tmp_path):
    review_dir = tmp_path / "opportunity_reviews"
    monkeypatch.setattr(opportunity_review, "REVIEW_RUNTIME_DIR", review_dir)
    monkeypatch.setattr(opportunity_review, "REVIEW_RECORDS_PATH", review_dir / "review_records.jsonl")
    monkeypatch.setattr(opportunity_review, "OPERATOR_NOTES_PATH", review_dir / "operator_notes.jsonl")
    yield review_dir


@pytest.fixture()
def authed_client(monkeypatch, tmp_path, isolated_review_store):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/opportunities"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_v414_version_identity():
    assert APP_VERSION == "4.17.0-real"


def test_v414_workbench_labels_data_mode_and_sample_rows(isolated_review_store):
    workbench = build_opportunity_workbench(demo_markets(), packets=[], limit=10, requested_demo=True)
    assert workbench["data_state"] == "sample"
    assert workbench["requested_data_mode"] == "demo_fixtures"
    assert workbench["resolved_data_mode"] == "demo_fixtures"
    assert workbench["source_state"] == "demo_fixture"
    assert workbench["safe_review_only"] is True
    assert workbench["live_disabled"] is True

    item = workbench["items"][0]
    assert item["data_state"] == "sample"
    assert item["data_freshness"] == "sample_fixture"
    assert item["review_source"] == "demo_fixture"
    assert item["source_component"] == "opportunity_workbench"
    assert item["order_submitted"] is False
    assert item["order_cancelled"] is False


def test_v414_workbench_page_uses_explicit_data_mode_selector(authed_client):
    page = authed_client.get("/v3/opportunities?demo=true")
    assert page.status_code == 200
    assert '<select name="demo">' in page.text
    assert 'type="checkbox" name="demo"' not in page.text
    assert "<strong>sample</strong><span>Data state</span>" in page.text
    assert "Configured local/live source" in page.text
    assert 'name="source_component" value="opportunity_workbench.status_form"' in page.text
    assert 'name="data_state" value="sample"' in page.text
    assert "Review actions record local operator decisions only" in page.text


def test_v414_browser_review_action_persists_enriched_audit_metadata(authed_client):
    response = authed_client.post(
        "/v3/opportunities/review/demo_france_world_cup/status",
        data={
            "action": "add_to_watchlist",
            "market_title": "Will France win the 2026 FIFA World Cup?",
            "data_state": "sample",
            "data_freshness": "sample_fixture",
            "source_route": "/v3/opportunities?demo=true",
            "source_component": "opportunity_workbench.status_form",
            "previous_state": "UNREVIEWED",
            "reason": "Operator added opportunity to watchlist from regression test.",
            "return_to": "/v3/opportunities?demo=true",
        },
        follow_redirects=False,
    )
    assert response.status_code in {303, 307}
    assert "review_status=WATCHING" in response.headers["location"]

    record = get_review_record("demo_france_world_cup")["item"]
    assert record["review_status"] == "WATCHING"
    assert record["data_state"] == "sample"
    assert record["last_action_source_route"] == "/v3/opportunities?demo=true"
    event = record["audit_history"][-1]
    assert event["action_type"] == "status"
    assert event["previous_state"] == "UNREVIEWED"
    assert event["new_state"] == "WATCHING"
    assert event["target_id"] == "demo_france_world_cup"
    assert event["source_component"] == "opportunity_workbench.status_form"
    assert event["data_state"] == "sample"
    assert event["safe_review_only"] is True
    assert event["live_disabled"] is True
    assert event["order_submitted"] is False
    assert event["order_cancelled"] is False
    assert event["trade_approved"] is False

    detail = authed_client.get("/v3/markets/demo_france_world_cup")
    assert detail.status_code == 200
    assert "UNREVIEWED -> WATCHING" in detail.text
    assert "opportunity_workbench.status_form" in detail.text


def test_v414_json_review_api_accepts_source_metadata_and_notes_are_review_only(authed_client):
    status = authed_client.post(
        "/api/v3/opportunities/review/demo_france_world_cup/status",
        json={
            "action": "send_to_paper_review",
            "market_title": "Will France win the 2026 FIFA World Cup?",
            "data_state": "sample",
            "data_freshness": "sample_fixture",
            "source_route": "/api/v3/opportunities?demo=true",
            "source_component": "pytest.api_status",
            "reason": "Regression test paper-review status update.",
        },
    )
    assert status.status_code == 200
    data = status.json()
    assert data["item"]["review_status"] == "PAPER_REVIEW"
    assert data["item"]["audit_history"][-1]["source_component"] == "pytest.api_status"
    assert data["item"]["audit_history"][-1]["data_state"] == "sample"
    assert data["item"]["trade_approved"] is False

    notes = authed_client.post(
        "/api/v3/opportunities/review/demo_france_world_cup/notes",
        json={
            "operator_notes": "Track lineup and injury news before paper review.",
            "market_title": "Will France win the 2026 FIFA World Cup?",
            "data_state": "sample",
            "data_freshness": "sample_fixture",
            "source_route": "/api/v3/opportunities/review/demo_france_world_cup/notes",
            "source_component": "pytest.api_notes",
            "reason": "Regression test notes update.",
        },
    )
    assert notes.status_code == 200
    note_data = notes.json()
    assert note_data["item"]["operator_notes"].startswith("Track lineup")
    assert note_data["item"]["audit_history"][-1]["action_type"] == "notes"
    assert note_data["item"]["audit_history"][-1]["source_component"] == "pytest.api_notes"
    assert note_data["item"]["order_submitted"] is False
    assert note_data["item"]["order_cancelled"] is False


def test_v414_feature_readiness_reports_opportunity_review_truthfully():
    feature_status = build_feature_status_map()
    opportunity = next(row for row in feature_status["items"] if row["feature_id"] == "opportunity.review_actions")
    assert opportunity["status"] == "working"
    assert opportunity["data_state"] == "cached"
    assert opportunity["safe_review_only"] is True
    assert opportunity["live_disabled"] is True
    assert "source metadata" in opportunity["reason"]

    stub_map = build_stub_burndown_map()
    queue = next(row for row in stub_map["items"] if row["feature_id"] == "review.queue_actions")
    assert queue["status"] == "working"
    assert queue["data_state"] == "cached"
    assert queue["safe_review_only"] is True
    assert "data-state" in queue["backend_wiring"]
