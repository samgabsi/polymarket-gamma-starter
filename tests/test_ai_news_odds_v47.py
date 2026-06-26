from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_edge_calibration, ai_edge_research, ai_evidence, ai_news_odds, ai_news_providers, ai_openai_client, auth
from app.config import APP_VERSION
from app.main import app
from app.navigation_registry import get_route_aliases, get_system_map
from app.opportunity_review import demo_markets
from app.platform_api import PACKAGE_NAME, PACKAGE_SLUG


@pytest.fixture(autouse=True)
def isolated_news_runtime(monkeypatch, tmp_path):
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
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/ai/news-odds"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def _market() -> dict[str, object]:
    return next(row for row in demo_markets() if row["id"] == "demo_france_world_cup")


def _sources() -> list[dict[str, object]]:
    return [
        {
            "title": "France official World Cup roster update confirmed",
            "url": "https://www.fifa.com/news/france-roster-update?utm_source=newsletter",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "snippet": "Official France 2026 World Cup roster update confirmed by FIFA and team staff.",
            "source_type": "primary",
            "claim_stance": "supports",
        },
        {
            "title": "France official World Cup roster update confirmed",
            "url": "https://reuters.com/sports/soccer/france-roster-update",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "snippet": "France 2026 World Cup roster update was confirmed; Reuters cites team sources.",
            "source_type": "wire",
            "claim_stance": "supports",
        },
        {
            "title": "France official World Cup roster update confirmed",
            "url": "https://aggregator.example/france-roster-update-copy",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "snippet": "France 2026 World Cup roster update was confirmed; Reuters cites team sources.",
            "source_type": "blog",
            "claim_stance": "supports",
        },
        {
            "title": "France injury rumor denied as unconfirmed",
            "url": "https://example.com/france-injury-rumor-denied",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "snippet": "A rumored France injury is denied as unconfirmed and not true.",
            "source_type": "blog",
            "claim_stance": "contradicts",
        },
    ]


def test_version_identity_and_package_identity():
    assert APP_VERSION == "4.17.0-real"
    assert PACKAGE_NAME == "Polymarket OP Console"
    assert PACKAGE_SLUG == "polymarket-op-console"


def test_url_domain_source_type_and_scores_are_transparent():
    normalized = ai_news_odds.normalize_source_url("https://www.reuters.com/sports/story?utm_source=x&b=2")
    assert normalized == "https://reuters.com/sports/story?b=2"
    assert ai_news_odds.canonicalize_source_domain(normalized) == "reuters.com"
    assert ai_news_odds.classify_source_type({"url": normalized}) == "wire"
    cred = ai_news_odds.score_source_credibility({"url": normalized, "title": "Reuters report"})
    assert cred["credibility_score"] >= 0.8
    recency = ai_news_odds.score_source_recency(datetime.now(timezone.utc).isoformat())
    assert recency["recency_score"] >= 0.85
    relevance = ai_news_odds.score_source_relevance(_sources()[0], _market())
    assert relevance["relevance_score"] > 0


def test_duplicate_detection_claim_clustering_and_corroboration():
    dedup = ai_news_odds.detect_duplicate_or_syndicated_sources(_sources())
    assert dedup["source_count"] == 4
    assert dedup["duplicate_source_count"] >= 1
    clusters = ai_news_odds.cluster_evidence_claims(_sources())
    assert clusters
    assert any(cluster["contradiction_detected"] for cluster in clusters)
    corroboration = ai_news_odds.score_independent_corroboration({"sources": _sources()[:3]})
    assert corroboration["independent_source_count"] >= 1
    assert corroboration["corroboration_score"] <= 1


def test_log_odds_probability_adjustment_caps_and_base_missing_behavior():
    adjusted = ai_news_odds.apply_probability_adjustment(0.42, 4.0, {"min_probability": 0.01, "max_probability": 0.99})
    assert adjusted["ok"] is True
    assert adjusted["adjusted_probability"] > adjusted["base_probability"]
    capped = ai_news_odds.calculate_news_adjustment(
        0.42,
        [{"direction": "YES_UP", "magnitude_pp": 99, "corroboration_score": 1, "relevance_score": 1, "independent_source_count": 1}],
        {"has_primary_source": False, "high_credibility_source_count": 0, "independent_source_count": 1},
        {"max_adjustment_pp": 8.0, "max_cluster_adjustment_pp": 3.0, "max_no_primary_source_adjustment_pp": 2.0},
    )
    assert abs(capped["adjustment_pp"]) <= 2.0
    missing = ai_news_odds.calculate_news_adjustment(None, [])
    assert missing["confidence"] == "INSUFFICIENT_DATA"
    assert missing["order_submitted"] is False


def test_configurable_ai_odds_caps_can_exceed_legacy_cap_with_evidence():
    event = {
        "direction": "YES_UP",
        "magnitude_pp": 12,
        "corroboration_score": 1.0,
        "relevance_score": 1.0,
        "independent_source_count": 3,
    }
    source_summary = {
        "source_count": 3,
        "independent_source_count": 3,
        "high_credibility_source_count": 2,
        "has_primary_source": True,
        "contradiction_count": 0,
    }
    conservative = ai_news_odds.calculate_news_adjustment(
        0.42,
        [event],
        source_summary,
        {"ai_odds_adjustment_mode": "conservative", "max_cluster_adjustment_pp": 12.0},
        {"liquidity": 5000, "resolution_source": "official"},
    )
    balanced = ai_news_odds.calculate_news_adjustment(
        0.42,
        [event],
        source_summary,
        {"ai_odds_adjustment_mode": "balanced", "max_cluster_adjustment_pp": 12.0},
        {"liquidity": 5000, "resolution_source": "official"},
    )
    hard_capped = ai_news_odds.calculate_news_adjustment(
        0.42,
        [event],
        source_summary,
        {"ai_odds_adjustment_mode": "aggressive", "absolute_hard_cap_pct": 4.0, "max_cluster_adjustment_pp": 12.0},
        {"liquidity": 5000, "resolution_source": "official"},
    )
    custom = ai_news_odds.calculate_news_adjustment(
        0.42,
        [event],
        source_summary,
        {"ai_odds_adjustment_mode": "custom", "max_adjustment_pp": 9.0, "max_cluster_adjustment_pp": 12.0},
        {"liquidity": 5000, "resolution_source": "official"},
    )
    disabled = ai_news_odds.calculate_news_adjustment(
        0.42,
        [event],
        source_summary,
        {"ai_odds_adjustment_enabled": "false", "ai_odds_adjustment_mode": "balanced", "max_cluster_adjustment_pp": 12.0},
    )
    assert abs(conservative["final_adjustment_pct"]) <= 2.5
    assert balanced["final_adjustment_pct"] > 2.5
    assert balanced["old_2_5_cap_exceeded"] is True
    assert balanced["cap_mode"] == "balanced"
    assert abs(hard_capped["final_adjustment_pct"]) <= 4.0
    assert "absolute_hard_cap_pct" in hard_capped
    assert custom["final_adjustment_pct"] > 2.5
    assert custom["configured_cap_pct"] == 9.0
    assert disabled["final_adjustment_pct"] == 0.0


def test_news_adjustment_packet_schema_safety_and_explanation():
    packet = ai_news_odds.build_news_odds_adjustment_packet(_market(), _sources())
    assert packet["review_only"] is True
    assert packet["not_financial_advice"] is True
    assert packet["does_not_place_orders"] is True
    assert packet["does_not_cancel_orders"] is True
    assert packet["does_not_arm_live"] is True
    assert packet["source_weighting_does_not_imply_truth"] is True
    assert packet["corroboration_does_not_imply_certainty"] is True
    assert packet["base_fair_yes"] is not None
    assert packet["adjusted_fair_yes"] is not None
    assert "adjusted_edge" in packet
    assert "raw_ai_adjustment_pct" in packet
    assert "evidence_weighted_adjustment_pct" in packet
    assert "final_adjustment_pct" in packet
    assert "cap_decision" in packet
    assert ai_news_odds.validate_news_adjustment_safety(packet)["ok"] is True
    explanation = ai_news_odds.explain_news_odds_adjustment(packet)
    assert "review-only" in explanation
    assert "not financial advice" in explanation
    assert "does not place or cancel orders" in explanation


def test_manual_evidence_and_provider_modes_do_not_call_network_by_default():
    manual = ai_news_providers.run_manual_evidence_news_analysis({"items": _sources()})
    assert manual["manual_evidence_mode_available"] is True
    assert manual["external_network_called"] is False
    local = ai_news_providers.run_local_llm_evidence_analysis({"items": _sources()})
    assert local["local_llm_can_browse_web"] is False
    assert "does not browse" in local["warning"]
    search = ai_news_providers.run_openai_web_news_search({"requests": [{"query": "France World Cup official update"}]}, {})
    assert search["external_network_called"] is False
    assert search["web_search_allowed_now"] is False
    assert "Web search unavailable" in search["message"]


def test_routes_render_and_include_news_odds_review_language(authed_client):
    routes = {
        "/v3/ai/news-odds": ["AI News Odds Adjustment Engine", "review-only", "Source weights"],
        "/v3/ai/news-odds/run": ["Run News Odds Research", "Web search unavailable", "manual evidence"],
        "/v3/ai/news-odds/adjustments": ["News Odds Adjustments", "draft fair odds"],
        "/v3/ai/news-odds/source-weights": ["Source Weighting", "corroboration", "does not prove truth"],
        "/v3/markets/demo_france_world_cup/news-odds": ["Market News Odds", "Base fair YES", "News-adjusted fair YES"],
        "/v3/markets/family/2026_fifa_world_cup_winner/news-odds?demo=true": ["Family News Odds", "family normalization not applied", "review-only"],
    }
    for route, expected_texts in routes.items():
        response = authed_client.get(route)
        assert response.status_code == 200
        for text in expected_texts:
            assert text in response.text
        assert response.text.count("<h2>Unified Surface</h2>") <= 1
    market_page = authed_client.get("/v3/markets/demo_france_world_cup/news-odds")
    assert 'action="/v3/ai/news-odds/market/demo_france_world_cup/adjust"' in market_page.text
    assert 'href="/api/v3/ai/news-odds/market/demo_france_world_cup/adjust"' not in market_page.text


def test_api_plan_search_manual_adjust_lifecycle_and_no_live_mutation(authed_client):
    plan = authed_client.post("/api/v3/ai/news-odds/market/demo_france_world_cup/plan", json={"operator_notes": "Track official roster news."})
    assert plan.status_code == 200
    assert plan.json()["order_submitted"] is False
    assert plan.json()["queries"]

    search = authed_client.post("/api/v3/ai/news-odds/market/demo_france_world_cup/search", json={})
    assert search.status_code == 200
    assert search.json()["external_network_called"] is False

    manual = authed_client.post("/api/v3/ai/news-odds/market/demo_france_world_cup/manual-evidence", json={"items": _sources()})
    assert manual.status_code == 200
    assert manual.json()["external_network_called"] is False

    adjust = authed_client.post("/api/v3/ai/news-odds/market/demo_france_world_cup/adjust", json={"items": _sources(), "write": True})
    assert adjust.status_code == 200
    data = adjust.json()
    assert data["review_only"] is True
    assert data["order_submitted"] is False
    assert data["order_cancelled"] is False
    assert "raw_ai_adjustment_pct" in data["adjustment"]
    assert "evidence_weighted_adjustment_pct" in data["adjustment"]
    assert "final_adjustment_pct" in data["adjustment"]
    assert "cap_decision" in data["adjustment"]
    adjustment_id = data["adjustment"]["adjustment_id"]

    page_plan = authed_client.post("/v3/ai/news-odds/market/demo_france_world_cup/plan", data={"operator_notes": "Plan from browser form."}, follow_redirects=False)
    page_adjust = authed_client.post("/v3/ai/news-odds/market/demo_france_world_cup/adjust", data={"evidence_text": "Manual evidence from browser form.", "write": "false"}, follow_redirects=False)
    assert page_plan.status_code in {303, 307}
    assert page_adjust.status_code in {303, 307}
    assert "news_odds_plan_previewed" in page_plan.headers["location"]
    assert "news_odds_adjustment_previewed" in page_adjust.headers["location"]

    accepted = authed_client.post(f"/api/v3/ai/news-odds/adjustment/{adjustment_id}/accept-to-review-context", json={"operator_note": "Accept into review context only."})
    rejected = authed_client.post(f"/api/v3/ai/news-odds/adjustment/{adjustment_id}/reject", json={})
    archived = authed_client.post(f"/api/v3/ai/news-odds/adjustment/{adjustment_id}/archive", json={})
    for response in [accepted, rejected, archived]:
        assert response.status_code == 200
        body = response.json()
        assert body["review_only"] is True
        assert body["order_submitted"] is False
        assert body["order_cancelled"] is False
        assert body["live_trading_armed"] is False


def test_market_detail_workbench_ai_edge_and_system_map_include_news_odds(authed_client):
    detail = authed_client.get("/v3/markets/demo_france_world_cup")
    workbench = authed_client.get("/v3/opportunities?demo=true")
    assert detail.status_code == 200
    assert workbench.status_code == 200
    assert "News Odds Adjustment" in detail.text
    assert "News Odds" in workbench.text
    edge_packet = ai_edge_research.generate_edge_packet({
        "market_id": "demo_france_world_cup",
        "market_title": "Will France win the 2026 FIFA World Cup?",
        "evidence_sources": _sources()[:2],
        "news_odds_adjustment_snapshot": ai_news_odds.build_news_odds_adjustment_packet(_market(), _sources()),
    }, write=False)
    packet = edge_packet["packet"]
    assert packet["news_odds_adjustment_snapshot"]
    assert packet["order_submitted"] is False
    aliases = get_route_aliases()
    system_map = get_system_map()
    assert aliases["/news-odds"] == "/v3/ai/news-odds"
    assert system_map["includes_ai_news_odds_adjustment_engine"] is True
    assert system_map["source_weighting_does_not_imply_truth"] is True
    assert system_map["corroboration_does_not_imply_certainty"] is True
