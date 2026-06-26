from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, opportunity_review
from app.config import APP_VERSION
from app.main import app
from app.navigation_registry import get_route_aliases, get_system_map
from app.opportunity_review import (
    AI_EDGE_PACKET_LIFECYCLE_STATES,
    REVIEW_STATUSES,
    build_family_comparison,
    build_market_detail_context,
    build_opportunity_workbench,
    build_packet_lifecycle_summary,
    demo_markets,
    opportunity_review_settings,
    update_review_notes,
    update_review_status,
)
from app.platform_api import PACKAGE_NAME, PACKAGE_SLUG


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


def test_version_identity_and_package_identity():
    assert APP_VERSION == "4.17.0-real"
    assert PACKAGE_NAME == "Polymarket OP Console"
    assert PACKAGE_SLUG == "polymarket-op-console"


def test_opportunity_review_settings_are_review_only():
    settings = opportunity_review_settings()
    assert settings["opportunity_review_enabled"] is True
    assert settings["ai_edge_review_only"] is True
    assert settings["watchlist_review_only"] is True
    assert settings["paper_review_draft_only"] is True
    assert settings["runtime_records_excluded_from_release_zip"] is True
    assert "PAPER_REVIEW" in REVIEW_STATUSES
    assert "AI_ANALYZED" in AI_EDGE_PACKET_LIFECYCLE_STATES
    assert settings["order_submitted"] is False
    assert settings["order_cancelled"] is False
    assert settings["live_trading_armed"] is False


def test_workbench_contains_review_status_actions_and_no_live_mutation(isolated_review_store):
    rows = demo_markets()
    workbench = build_opportunity_workbench(rows, packets=[], limit=10)
    assert workbench["title"] == "Opportunity Review Workbench"
    assert workbench["review_only"] is True
    assert workbench["order_submitted"] is False
    assert workbench["order_cancelled"] is False
    item = workbench["items"][0]
    assert item["review_status"] == "UNREVIEWED"
    assert item["detail_href"].startswith("/v3/markets/")
    assert item["ai_edge_analyze_href"].startswith("/v3/ai/edge/market/")
    assert item["status_api_href"].startswith("/api/v3/opportunities/review/")
    assert item["recommended_side"] in {"YES", "NO", "HOLD", "NO CLEAR EDGE", "INSUFFICIENT DATA", "NEEDS REVIEW"}


def test_market_detail_context_includes_edge_lifecycle_notes_and_review_only(isolated_review_store):
    market = next(row for row in demo_markets() if row["id"] == "demo_france_world_cup")
    detail = build_market_detail_context(market, packets=[])
    assert detail["market_id"] == "demo_france_world_cup"
    assert detail["edge"]["recommended_side"] == "YES"
    assert detail["edge"]["model_fair_source"]
    assert detail["ai_edge_packet_lifecycle"]["lifecycle_state"] == "DRAFT"
    assert detail["ai_edge_packet_lifecycle"]["no_live_mutation_confirmation"] is True
    assert detail["review_record"]["review_status"] == "UNREVIEWED"
    assert detail["order_submitted"] is False
    assert detail["order_cancelled"] is False


def test_family_comparison_separates_favorite_from_edge():
    family = build_family_comparison(demo_markets(), "2026_fifa_world_cup_winner")
    assert family["family_title"] == "2026 FIFA World Cup winner"
    assert family["family_size"] >= 3
    assert family["favorite_by_market_price"]["market_id"] == "demo_france_world_cup"
    assert family["best_draft_yes_edge"]
    assert "Favorite does not equal best wager." in family["warnings"]
    assert family["review_only"] is True
    assert family["order_submitted"] is False
    assert family["order_cancelled"] is False


def test_packet_lifecycle_states_serialize_without_order_mutation():
    draft = build_packet_lifecycle_summary({}, current_recommendation={"recommended_side": "YES"})
    assert draft["lifecycle_state"] == "DRAFT"
    analyzed = build_packet_lifecycle_summary({"packet_id": "p1", "ai_model_called": True, "evidence_sources": ["source"]}, current_recommendation={"recommended_side": "NO"}, operator_notes_count=2)
    assert analyzed["lifecycle_state"] == "AI_ANALYZED"
    assert analyzed["operator_notes_count"] == 2
    assert analyzed["draft_review_only"] is True
    assert analyzed["no_live_mutation_confirmation"] is True
    assert analyzed["order_submitted"] is False
    assert analyzed["order_cancelled"] is False


def test_notes_watchlist_paper_review_reject_archive_are_review_only(isolated_review_store):
    notes = update_review_notes("demo_france_world_cup", {"market_title": "Will France win the 2026 FIFA World Cup?", "operator_notes": "Track injury and squad news only."})
    assert notes["ok"] is True
    assert notes["item"]["operator_notes"]
    assert notes["item"]["order_submitted"] is False
    for action, expected in [("add_to_watchlist", "WATCHING"), ("send_to_paper_review", "PAPER_REVIEW"), ("reject", "REJECTED"), ("archive", "ARCHIVED")]:
        updated = update_review_status("demo_france_world_cup", {"action": action, "market_title": "Will France win the 2026 FIFA World Cup?"})
        assert updated["ok"] is True
        assert updated["item"]["review_status"] == expected
        assert updated["item"]["trade_approved"] is False
        assert updated["item"]["order_submitted"] is False
        assert updated["item"]["order_cancelled"] is False
        assert updated["item"]["live_trading_armed"] is False


def test_new_routes_render_and_expose_review_only_language(authed_client):
    checks = {
        "/v3/opportunities?demo=true": ["Opportunity Review Workbench", "Review Status", "Add to Watchlist", "Send to Paper Review", "AI Edge Packet Lifecycle"],
        "/opportunities?demo=true": ["Opportunity Review Workbench", "Operator Notes", "Review-only"],
        "/v3/markets/demo_france_world_cup": ["Market Detail / Opportunity Review", "Recommended Side", "YES Price", "NO Price", "Model Fair Source", "Edge Explanation", "review-only, not financial advice, not trade approval"],
        "/v3/markets/family/2026_fifa_world_cup_winner?demo=true": ["Market Family Comparison", "Favorite does not equal best wager", "All output is review-only"],
    }
    for route, expected_texts in checks.items():
        response = authed_client.get(route)
        assert response.status_code == 200
        for text in expected_texts:
            assert text in response.text
        assert response.text.count("<h2>Unified Surface</h2>") == 1


def test_workbench_review_controls_are_post_backed_not_api_links(authed_client):
    page = authed_client.get("/v3/opportunities?demo=true")
    assert page.status_code == 200
    assert 'action="/v3/opportunities/review/demo_france_world_cup/status"' in page.text
    assert 'method="post"' in page.text
    assert 'href="/api/v3/opportunities/review/demo_france_world_cup/status"' not in page.text
    assert 'Add/Edit Notes API' not in page.text

    response = authed_client.post(
        "/v3/opportunities/review/demo_france_world_cup/status",
        data={"action": "add_to_watchlist", "market_title": "Will France win the 2026 FIFA World Cup?", "return_to": "/v3/opportunities?demo=true"},
        follow_redirects=False,
    )
    assert response.status_code in {303, 307}
    assert "review_status=WATCHING" in response.headers["location"]


def test_new_apis_do_not_mutate_live_state(authed_client):
    workbench = authed_client.get("/api/v3/opportunities?demo=true")
    assert workbench.status_code == 200
    data = workbench.json()
    assert data["review_only"] is True
    assert data["order_submitted"] is False
    assert data["order_cancelled"] is False

    detail = authed_client.get("/api/v3/markets/demo_france_world_cup/summary")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["edge"]["recommended_side"] == "YES"
    assert detail_data["order_submitted"] is False

    status = authed_client.post("/api/v3/opportunities/review/demo_france_world_cup/status", json={"action": "send_to_paper_review"})
    assert status.status_code == 200
    status_data = status.json()
    assert status_data["item"]["review_status"] == "PAPER_REVIEW"
    assert status_data["item"]["order_submitted"] is False
    assert status_data["item"]["order_cancelled"] is False
    assert status_data["item"]["trade_approved"] is False


def test_navigation_system_map_includes_v46_surfaces():
    aliases = get_route_aliases()
    system_map = get_system_map()
    assert aliases["/opportunity-review"] == "/v3/opportunities"
    assert aliases["/market-review"] == "/v3/markets/demo_france_world_cup"
    assert aliases["/family-review"] == "/v3/markets/family/2026_fifa_world_cup_winner"
    assert system_map["includes_opportunity_review_workbench"] is True
    assert system_map["includes_market_detail_pages"] is True
    assert system_map["includes_market_family_comparison"] is True
    assert system_map["includes_ai_edge_packet_lifecycle"] is True
    assert system_map["opportunity_review_records_are_review_only"] is True
    assert system_map["aliases_bypass_backend_gates"] is False
