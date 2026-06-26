from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import APP_VERSION
from app.main import app
from app.navigation_registry import get_route_aliases, get_system_map


def test_navigation_registry_contract():
    system_map = get_system_map()
    aliases = get_route_aliases()
    assert APP_VERSION == "4.17.0-real"
    assert system_map["recommended_starting_point"] == "/v3"
    assert system_map["aliases_bypass_backend_gates"] is False
    assert system_map["aliases_mutate_state"] is False
    assert aliases["/ai"] == "/v3/ai"
    assert aliases["/platform"] == "/v3/platform"
    assert aliases["/operator-os"] == "/v3"
    assert aliases["/live"] == "/v2-live"
    assert any(item["id"] == "ai_copilot" and item["mutation_risk"] == "draft/review only" for item in system_map["items"])
    assert any(item["id"] == "live_controls" and item["mutation_risk"] == "live-control gated" for item in system_map["items"])


def test_major_alias_routes_are_registered_and_redirect_or_auth_gate():
    registered_paths = {getattr(route, "path", "") for route in app.routes}
    for alias in ["/operator-os", "/ai", "/ai/settings", "/ai/providers", "/ai/openai", "/ai/local-llm", "/platform", "/cockpit", "/workspace", "/tasks", "/live", "/live-controls", "/configuration"]:
        assert alias in registered_paths
    with TestClient(app) as client:
        response = client.get("/ai", follow_redirects=False)
        # On fresh installs auth/setup middleware can 303 before the alias route. Either way, no mutation occurs.
        assert response.status_code in {303, 307, 308}


def test_templates_expose_unified_navigation_and_bridge_links():
    dashboard = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
    v2 = Path("app/templates/live_v2_dashboard.html").read_text(encoding="utf-8")
    v3 = Path("app/templates/live_v3_dashboard.html").read_text(encoding="utf-8")
    system_map = Path("app/templates/system_map.html").read_text(encoding="utf-8")
    base = Path("app/templates/base.html").read_text(encoding="utf-8")

    assert "Unified Operator Dashboard" in dashboard
    assert "primary_entry_points" in dashboard and "system-map" in dashboard
    assert "Unified Surface Bridge" in v2
    assert "/v3" in v2 and "/v3/ai" in v2 and "/v3/platform" in v2
    assert "Unified System Bridge" in v3
    assert "AI Copilot In The Unified Surface" in v3
    assert "Platform Bridge" in v3
    assert "/system-map" in v3
    assert "System Map / Route Map" in system_map
    assert "global_nav_items" in base
    assert "place_order" not in dashboard.lower()
