from __future__ import annotations

from pathlib import Path

from app.config import APP_VERSION
from app.market_edge import (
    FAVORITE_VS_EDGE_EXPLAINER,
    build_market_recommendation_row,
    calculate_yes_no_edges,
    edge_recommendation_legend,
    enrich_markets_with_recommendations,
    group_related_markets,
    rank_market_family,
    recommend_wager_side,
)
from app.navigation_registry import get_route_aliases, get_system_map
from app.platform_api import PACKAGE_NAME, PACKAGE_SLUG
from app.ui import NAV_SECTIONS


def _market(question: str, yes: float, fair: float, market_id: str) -> dict[str, object]:
    return {
        "id": market_id,
        "question": question,
        "outcomes": [{"name": "YES", "price": yes}, {"name": "NO", "price": 1 - yes}],
        "probability_model": {"market_probability": yes, "model_probability": fair, "confidence": "medium"},
        "volume_24hr": 50000,
        "liquidity": 25000,
        "data_age_minutes": 1,
    }


def test_version_identity_and_package_identity():
    assert APP_VERSION == "4.17.0-real"
    assert PACKAGE_NAME == "Polymarket OP Console"
    assert PACKAGE_SLUG == "polymarket-op-console"


def test_sidebar_has_one_desktop_unified_surface_heading_and_distinct_mobile_heading():
    assert [section["label"] for section in NAV_SECTIONS].count("Unified Surface") == 1
    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    assert "Mobile · {{ section.label }}" in base
    assert base.count("<h2>{{ section.label }}</h2>") == 1
    assert "NAV_SECTIONS.insert" not in Path("app/ui.py").read_text(encoding="utf-8")


def test_navigation_registry_includes_ai_edge_and_market_edge_without_alias_mutation():
    aliases = get_route_aliases()
    system_map = get_system_map()
    assert aliases["/edge"] == "/v3/ai/edge"
    assert aliases["/edge/legend"] == "/api/markets/edge-legend"
    assert system_map["includes_ai_edge_market_row_routes"] is True
    assert system_map["favorite_ranking_does_not_imply_edge"] is True
    assert system_map["edge_recommendations_are_review_only"] is True
    assert system_map["aliases_bypass_backend_gates"] is False


def test_yes_edge_calculation_and_label():
    edge = calculate_yes_no_edges(0.18, 0.82, 0.205)
    assert edge["yes_edge_pp"] == 2.5
    decision = recommend_wager_side(edge, {"yes_pp": 2.0, "no_pp": 2.0}, {"passes": True, "blockers": []})
    assert decision["recommended_side"] == "YES"
    assert decision["side_badge"] == "DRAFT YES EDGE"


def test_no_edge_calculation_and_label():
    edge = calculate_yes_no_edges(0.18, 0.82, 0.12)
    assert edge["no_edge_pp"] == 6.0
    decision = recommend_wager_side(edge, {"yes_pp": 2.0, "no_pp": 2.0}, {"passes": True, "blockers": []})
    assert decision["recommended_side"] == "NO"
    assert decision["side_badge"] == "DRAFT NO EDGE"


def test_hold_and_insufficient_data_labels():
    hold = recommend_wager_side(calculate_yes_no_edges(0.18, 0.82, 0.19), {"yes_pp": 2.0, "no_pp": 2.0}, {"passes": True, "blockers": []})
    assert hold["recommended_side"] == "HOLD"
    assert hold["side_badge"] == "NO CLEAR EDGE"
    missing = recommend_wager_side(calculate_yes_no_edges(0.18, 0.82, None), {"yes_pp": 2.0, "no_pp": 2.0}, {"passes": True, "blockers": []})
    assert missing["recommended_side"] == "INSUFFICIENT DATA"


def test_market_row_model_source_explanation_and_safety_flags():
    row = build_market_recommendation_row(_market("Will France win the 2026 FIFA World Cup?", 0.18, 0.205, "france"))
    assert row["recommended_side"] == "YES"
    assert row["model_fair_source"] == "deterministic baseline model"
    assert "Model fair YES 20.5% vs market YES 18.0%" in row["explanation"]
    assert "Favorite means" in row["favorite_vs_edge_note"]
    assert row["research_only"] is True
    assert row["order_submitted"] is False
    assert row["order_cancelled"] is False
    assert row["no_trade_approval"] is True
    assert row["live_trading_armed"] is False


def test_market_family_detector_groups_world_cup_and_ranks_favorite_separately_from_edge():
    markets = [
        _market("Will France win the 2026 FIFA World Cup?", 0.18, 0.205, "france"),
        _market("Will Brazil win the 2026 FIFA World Cup?", 0.16, 0.18, "brazil"),
        _market("Will Germany win the 2026 FIFA World Cup?", 0.12, 0.10, "germany"),
    ]
    contexts = group_related_markets(markets)
    assert set(contexts) == {"france", "brazil", "germany"}
    assert contexts["france"]["is_market_favorite"] is True
    assert contexts["brazil"]["rank_by_market_yes_price"] == 2
    rows = enrich_markets_with_recommendations(markets)
    france = next(row for row in rows if row["id"] == "france")
    germany = next(row for row in rows if row["id"] == "germany")
    assert "Group favorite" in france["market_edge_recommendation"]["group_rank_label"]
    assert germany["market_edge_recommendation"]["recommended_side"] == "NO"
    ranked = rank_market_family(rows)
    assert ranked[0]["market_id"] == "france"


def test_market_family_detector_does_not_force_unrelated_markets_together():
    markets = [
        _market("Will it rain in New York tomorrow?", 0.40, 0.41, "rain"),
        _market("Will a tech stock close higher this week?", 0.52, 0.50, "stock"),
    ]
    assert group_related_markets(markets) == {}


def test_market_table_and_detail_templates_include_clear_recommendation_labels_and_ai_edge_actions():
    dashboard = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
    detail = Path("app/templates/market_detail.html").read_text(encoding="utf-8")
    live_v2 = Path("app/templates/live_v2_dashboard.html").read_text(encoding="utf-8")
    assert "Recommended Side" in dashboard
    assert "Model Fair / Edge" in dashboard
    assert "Analyze with AI Edge" in dashboard
    assert "Favorite ranking and wager edge are separate" in detail
    assert "v4.7 Market Edge Recommendation" in detail
    assert "recommended side" in live_v2.lower()
    assert "Favorite means highest price/probability" in live_v2


def test_edge_legend_is_review_only_and_clear():
    legend = edge_recommendation_legend()
    assert {"YES", "NO", "HOLD", "NEEDS REVIEW", "INSUFFICIENT DATA"}.issubset(set(legend["recommended_sides"]))
    assert FAVORITE_VS_EDGE_EXPLAINER in legend["favorite_vs_edge"]
    assert legend["order_submitted"] is False
    assert legend["order_cancelled"] is False
    assert legend["no_trade_approval"] is True
