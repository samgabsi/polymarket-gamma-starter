from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import auth, cross_market_arbitrage
from app.config import APP_VERSION, settings
from app.main import app
from app.navigation_registry import get_route_aliases, get_system_map


@pytest.fixture(autouse=True)
def isolated_arbitrage_runtime(monkeypatch, tmp_path):
    arb_dir = tmp_path / "cross_market_arbitrage"
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_RUNTIME_DIR", arb_dir)
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_AUDIT_PATH", arb_dir / "audit.jsonl")
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_SCANS_PATH", arb_dir / "scans.jsonl")
    monkeypatch.setattr(settings, "arbitrage_scanner_enabled", False)
    monkeypatch.setattr(settings, "arbitrage_review_only", True)
    monkeypatch.setattr(settings, "arbitrage_fetch_orderbooks", False)
    monkeypatch.setattr(settings, "arbitrage_min_net_margin_pct", 1.0)
    monkeypatch.setattr(settings, "arbitrage_min_confidence", 0.72)
    monkeypatch.setattr(settings, "arbitrage_min_liquidity", 10.0)
    monkeypatch.setattr(settings, "arbitrage_default_slippage_bps", 50.0)
    monkeypatch.setattr(settings, "arbitrage_max_resolution_mismatch_risk", 0.35)
    monkeypatch.setattr(settings, "kalshi_enabled", False)
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/arbitrage"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def _fixtures():
    markets = cross_market_arbitrage.demo_venue_markets()
    polymarket = next(row for row in markets if row.venue_market_id == "pm_france_2026_world_cup")
    kalshi_same = next(row for row in markets if row.venue_market_id == "KXWORLDCP-FRANCE")
    kalshi_group = next(row for row in markets if row.venue_market_id == "KXWORLDCP-FRANCE-GROUP")
    return markets, polymarket, kalshi_same, kalshi_group


def test_version_and_config_safe_defaults():
    summary = cross_market_arbitrage.arbitrage_settings_summary()
    assert APP_VERSION == "4.17.0-real"
    assert summary["arbitrage_scanner_enabled"] is False
    assert summary["arbitrage_review_only"] is True
    assert summary["kalshi_enabled"] is False
    assert summary["order_submitted"] is False
    assert summary["live_trading_armed"] is False


def test_candidate_matching_separates_clean_equivalence_from_scope_mismatch():
    markets, polymarket, kalshi_same, kalshi_group = _fixtures()
    pairs = cross_market_arbitrage.generate_candidate_pairs(markets)
    same = cross_market_arbitrage.score_market_equivalence(polymarket, kalshi_same)
    mismatch = cross_market_arbitrage.score_market_equivalence(polymarket, kalshi_group)
    assert pairs
    assert same["equivalence_score"] >= 0.90
    assert same["resolution_mismatch_risk"] <= 0.20
    assert mismatch["resolution_mismatch_risk"] > same["resolution_mismatch_risk"]
    assert "close_dates_differ_materially" in mismatch["mismatch_flags"]
    assert mismatch["mismatch_flags"]


def test_arbitrage_math_classifies_positive_clean_fixture_and_risky_mismatch():
    _, polymarket, kalshi_same, kalshi_group = _fixtures()
    clean_match = cross_market_arbitrage.score_market_equivalence(polymarket, kalshi_same)
    clean_items = cross_market_arbitrage.calculate_arbitrage_for_pair(polymarket, kalshi_same, clean_match)
    positive = next(item for item in clean_items if item["direction"] == "buy_yes_a_buy_no_b")
    assert positive["classification"] == "clean_arbitrage_candidate"
    assert positive["gross_arbitrage_margin_pct"] > 0
    assert positive["net_arbitrage_margin_pct"] > 0
    assert positive["estimated_fees_pct"] >= 0
    assert positive["estimated_slippage_pct"] > 0
    assert positive["not_guaranteed_profit"] is True
    assert positive["order_submitted"] is False
    assert positive["trade_approved"] is False

    mismatch = cross_market_arbitrage.score_market_equivalence(polymarket, kalshi_group)
    risky_items = cross_market_arbitrage.calculate_arbitrage_for_pair(polymarket, kalshi_group, mismatch)
    assert any(item["classification"] in {"resolution_mismatch_risk", "semantic_mismatch_risk"} for item in risky_items)


def test_fees_and_slippage_can_erase_gross_arbitrage(monkeypatch):
    _, polymarket, kalshi_same, _ = _fixtures()
    monkeypatch.setattr(settings, "arbitrage_default_slippage_bps", 900.0)
    kalshi_same.fees_bps = 900.0
    match = cross_market_arbitrage.score_market_equivalence(polymarket, kalshi_same)
    items = cross_market_arbitrage.calculate_arbitrage_for_pair(polymarket, kalshi_same, match)
    erased = next(item for item in items if item["direction"] == "buy_yes_a_buy_no_b")
    assert erased["gross_arbitrage_margin_pct"] > 0
    assert erased["estimated_fees_pct"] + erased["estimated_slippage_pct"] > erased["gross_arbitrage_margin_pct"]
    assert erased["net_arbitrage_margin_pct"] < 0
    assert erased["classification"] == "reject"
    assert erased["order_submitted"] is False


def test_demo_scan_routes_and_review_actions_are_review_only(authed_client):
    scan = asyncio.run(cross_market_arbitrage.scan_cross_market_arbitrage(demo=True, write=True))
    assert scan["review_only"] is True
    assert scan["not_guaranteed_profit"] is True
    assert scan["order_submitted"] is False
    assert scan["opportunity_count"] >= 1
    assert cross_market_arbitrage.ARBITRAGE_SCANS_PATH.exists()

    page = authed_client.get("/v3/arbitrage?demo=true")
    assert page.status_code == 200
    assert "Cross-Market Arbitrage" in page.text
    assert "not guaranteed profits" in page.text
    assert 'action="/v3/arbitrage/opportunity/' in page.text
    assert "/api/v3/arbitrage/opportunity/" not in page.text

    response = authed_client.get("/api/v3/arbitrage/scan?demo=true")
    assert response.status_code == 200
    body = response.json()
    assert body["review_only"] is True
    assert body["order_submitted"] is False

    item_id = body["items"][0]["opportunity_id"]
    review_get = authed_client.get(f"/api/v3/arbitrage/opportunity/{item_id}/review?action=review_requested")
    assert review_get.status_code == 200
    assert review_get.json()["method_required"] == "POST"
    assert review_get.json()["order_submitted"] is False
    reject_post = authed_client.post(f"/api/v3/arbitrage/opportunity/{item_id}/review", json={"action": "rejected", "operator_note": "Not equivalent enough."})
    review_form = authed_client.post(
        f"/v3/arbitrage/opportunity/{item_id}/review",
        data={"action": "review_requested", "return_to": "/v3/arbitrage?demo=true"},
        follow_redirects=False,
    )
    assert review_form.status_code in {303, 307}
    assert "arbitrage_review=recorded" in review_form.headers["location"]
    for action_response in [reject_post]:
        assert action_response.status_code == 200
        action_body = action_response.json()
        assert action_body["review_only"] is True
        assert action_body["order_submitted"] is False
        assert action_body["live_trading_armed"] is False


def test_navigation_and_system_map_include_arbitrage_review_surface():
    aliases = get_route_aliases()
    system_map = get_system_map()
    assert aliases["/arbitrage"] == "/v3/arbitrage"
    assert system_map["includes_cross_market_arbitrage"] is True
    assert system_map["cross_market_arbitrage_is_review_only"] is True
    assert system_map["arbitrage_candidates_are_not_guaranteed_profit"] is True
