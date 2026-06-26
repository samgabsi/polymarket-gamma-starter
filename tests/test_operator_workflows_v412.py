from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import (
    ai_edge_calibration,
    ai_edge_research,
    ai_evidence,
    ai_news_odds,
    ai_openai_client,
    auth,
    cross_market_arbitrage,
)
from app.config import APP_VERSION, settings
from app.feature_status import build_stub_burndown_map
from app.main import app


@pytest.fixture(autouse=True)
def isolated_operator_workflow_runtime(monkeypatch, tmp_path):
    news_dir = tmp_path / "ai_news_odds"
    audit_dir = tmp_path / "ai_news_odds_audit"
    sources_dir = tmp_path / "ai_news_sources"
    adjustments_dir = tmp_path / "ai_news_adjustments"
    monkeypatch.setattr(ai_news_odds, "AI_NEWS_RUNTIME_DIR", news_dir)
    monkeypatch.setattr(ai_news_odds, "AI_NEWS_AUDIT_DIR", audit_dir)
    monkeypatch.setattr(ai_news_odds, "AI_NEWS_SOURCES_DIR", sources_dir)
    monkeypatch.setattr(ai_news_odds, "AI_NEWS_ADJUSTMENTS_DIR", adjustments_dir)
    monkeypatch.setattr(ai_news_odds, "ADJUSTMENTS_PATH", adjustments_dir / "adjustments.jsonl")
    monkeypatch.setattr(ai_news_odds, "SOURCES_PATH", sources_dir / "sources.jsonl")
    monkeypatch.setattr(ai_news_odds, "AUDIT_PATH", audit_dir / "audit.jsonl")

    edge_dir = tmp_path / "ai" / "edge"
    ai_dir = tmp_path / "ai"
    monkeypatch.setattr(ai_edge_research, "EDGE_DIR", edge_dir)
    monkeypatch.setattr(ai_edge_research, "RESEARCH_PACKETS_PATH", edge_dir / "research_packets.jsonl")
    monkeypatch.setattr(ai_evidence, "EDGE_DIR", edge_dir)
    monkeypatch.setattr(ai_evidence, "EVIDENCE_SOURCES_PATH", edge_dir / "evidence_sources.jsonl")
    monkeypatch.setattr(ai_edge_calibration, "EDGE_DIR", edge_dir)
    monkeypatch.setattr(ai_edge_calibration, "CALIBRATION_RECORDS_PATH", edge_dir / "calibration_records.jsonl")
    monkeypatch.setattr(ai_openai_client, "AI_DIR", ai_dir)
    monkeypatch.setattr(ai_openai_client, "AI_AUDIT_PATH", ai_dir / "ai_audit.jsonl")

    arb_dir = tmp_path / "cross_market_arbitrage"
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_RUNTIME_DIR", arb_dir)
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_AUDIT_PATH", arb_dir / "audit.jsonl")
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_SCANS_PATH", arb_dir / "scans.jsonl")
    monkeypatch.setattr(settings, "arbitrage_scanner_enabled", False)
    monkeypatch.setattr(settings, "arbitrage_review_only", True)
    monkeypatch.setattr(settings, "arbitrage_fetch_orderbooks", False)
    monkeypatch.setattr(settings, "kalshi_enabled", False)
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def _adjustment_id_from_location(location: str) -> str:
    marker = "/v3/ai/news-odds/adjustment/"
    assert marker in location
    return location.split(marker, 1)[1].split("?", 1)[0]


def test_v412_ai_odds_browser_workflow_saves_reviews_and_feedback(authed_client):
    assert APP_VERSION == "4.17.0-real"
    page = authed_client.get("/v3/markets/demo_france_world_cup/news-odds")
    assert page.status_code == 200
    for text in [
        "Market price",
        "Model fair price",
        "AI-adjusted fair price",
        "Raw AI adjustment",
        "Final adjustment",
        "Recommended side",
        "Preview manual evidence",
        "Save draft adjustment",
    ]:
        assert text in page.text
    assert 'name="write" value="true"' in page.text

    plan = authed_client.post("/v3/ai/news-odds/market/demo_france_world_cup/plan", follow_redirects=False)
    manual = authed_client.post(
        "/v3/ai/news-odds/market/demo_france_world_cup/manual-evidence",
        data={"evidence_text": "Official roster update confirms key player available."},
        follow_redirects=False,
    )
    search = authed_client.post("/v3/ai/news-odds/market/demo_france_world_cup/search", follow_redirects=False)
    for response in [plan, manual, search]:
        assert response.status_code in {303, 307}
        assert "action_status=" in response.headers["location"]
        assert "order_submitted" not in response.headers["location"]

    adjust = authed_client.post(
        "/v3/ai/news-odds/market/demo_france_world_cup/adjust",
        data={"evidence_text": "Official roster update confirms key player available.", "write": "true"},
        follow_redirects=False,
    )
    assert adjust.status_code in {303, 307}
    assert "news_odds_adjustment_saved" in adjust.headers["location"]
    adjustment_id = _adjustment_id_from_location(adjust.headers["location"])

    detail = authed_client.get(adjust.headers["location"])
    assert detail.status_code == 200
    for text in [
        "News Odds Adjustment Saved",
        "Market YES price",
        "Raw AI adjustment",
        "Evidence-weighted",
        "Final adjustment",
        "Recommended side",
        "Operator confirmation required",
        "Accept to review context",
        "Reject draft",
        "Archive draft",
    ]:
        assert text in detail.text

    accept = authed_client.post(
        f"/v3/ai/news-odds/adjustment/{adjustment_id}/accept-to-review-context",
        data={"operator_note": "Accept for review context only."},
        follow_redirects=False,
    )
    assert accept.status_code in {303, 307}
    assert "news_odds_review_action_recorded" in accept.headers["location"]
    accepted = ai_news_odds.get_adjustment(adjustment_id)
    assert accepted["ok"] is True
    assert accepted["adjustment"]["accepted_to_review_context"] is True
    assert accepted["adjustment"]["order_submitted"] is False
    assert ai_news_odds.AUDIT_PATH.exists()


def test_v412_arbitrage_browser_review_actions_persist_audit_feedback(authed_client):
    page = authed_client.get("/v3/arbitrage?demo=true")
    assert page.status_code == 200
    for text in [
        "Cross-Market Arbitrage",
        "Review actions persist local audit rows only",
        "Add to watchlist",
        "Ignore for now",
        "Reject / ignore",
        "not guaranteed profits",
    ]:
        assert text in page.text
    assert "Kalshi" in page.text

    scan = authed_client.get("/api/v3/arbitrage/scan?demo=true")
    assert scan.status_code == 200
    body = scan.json()
    assert body["review_only"] is True
    assert body["order_submitted"] is False
    opportunity_id = body["items"][0]["opportunity_id"]

    review = authed_client.post(
        f"/v3/arbitrage/opportunity/{opportunity_id}/review",
        data={"action": "watchlist", "return_to": "/v3/arbitrage?demo=true"},
        follow_redirects=False,
    )
    assert review.status_code in {303, 307}
    assert "arbitrage_review=recorded" in review.headers["location"]
    assert "action=watchlist" in review.headers["location"]
    feedback = authed_client.get(review.headers["location"])
    assert feedback.status_code == 200
    assert "Recorded" in feedback.text
    assert "Watchlist" in feedback.text
    assert cross_market_arbitrage.ARBITRAGE_AUDIT_PATH.exists()
    audit_rows = [
        json.loads(line)
        for line in cross_market_arbitrage.ARBITRAGE_AUDIT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert audit_rows[-1]["action"] == "watchlist"
    assert audit_rows[-1]["order_submitted"] is False
    assert audit_rows[-1]["live_trading_armed"] is False


def test_v412_settings_and_feature_status_acceptance_surfaces(authed_client):
    settings_page = authed_client.get("/settings/configuration")
    assert settings_page.status_code == 200
    for text in [
        "Configuration Console",
        "Current effective value",
        "Saved .env value",
        "Source",
        "Restart",
        "Secrets remain masked",
    ]:
        assert text in settings_page.text

    status = authed_client.get("/api/v3/features/stub-burndown")
    assert status.status_code == 200
    body = status.json()
    assert body["operator_acceptance"]["ai_odds_review"] == "working"
    assert body["operator_acceptance"]["arbitrage_review"] == "working"
    assert body["operator_acceptance"]["live_execution"] == "disabled"
    assert body["operator_acceptance"]["kalshi"] == "disabled"
    assert body["secret_values_returned"] is False

    direct = build_stub_burndown_map()
    assert direct["operator_acceptance"] == body["operator_acceptance"]
