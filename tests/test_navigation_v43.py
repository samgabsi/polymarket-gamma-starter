from __future__ import annotations

from pathlib import Path

from app.config import APP_VERSION
from app.main import app
from app.navigation_registry import get_route_aliases, get_system_map


def test_v44_version_and_navigation_registry():
    assert APP_VERSION == "4.17.0-real"
    system_map = get_system_map()
    assert system_map["recommended_starting_point"] == "/v3"
    assert system_map["aliases_mutate_state"] is False
    assert system_map["aliases_bypass_backend_gates"] is False
    assert system_map["order_submitted"] is False
    assert system_map["order_cancelled"] is False
    assert system_map["live_trading_armed"] is False
    titles = {item["title"] for item in system_map["items"]}
    assert "Operator Intelligence OS" in titles
    assert "AI Copilot" in titles
    assert "AI Edge Research" in titles
    assert "Live Controls" in titles
    assert "Platform Health" in titles
    assert all("safety_class" in item and "mutation_risk" in item for item in system_map["items"])


def test_alias_registry_has_expected_safe_targets():
    aliases = get_route_aliases()
    assert aliases["/operator-os"] == "/v3"
    assert aliases["/ai"] == "/v3/ai"
    assert aliases["/edge"] == "/v3/ai/edge"
    assert aliases["/edge/packets"] == "/v3/ai/edge/packets"
    assert aliases["/edge/evidence"] == "/v3/ai/edge/evidence"
    assert aliases["/edge/calibration"] == "/v3/ai/edge/calibration"
    assert aliases["/platform"] == "/v3/platform"
    assert aliases["/cockpit"] == "/v3/cockpit"
    assert aliases["/workspace"] == "/v3/workspace"
    assert aliases["/tasks"] == "/v3/tasks"
    assert aliases["/live"] == "/v2-live"
    assert aliases["/live-controls"] == "/v2-live"
    assert aliases["/configuration"] == "/settings/configuration"
    assert all(not key.startswith("/api/live") for key in aliases)


def test_major_alias_routes_are_registered_without_live_mutation_handlers():
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    for path in ["/operator-os", "/ai", "/edge", "/edge/packets", "/edge/evidence", "/edge/calibration", "/platform", "/cockpit", "/workspace", "/tasks", "/live", "/live-controls", "/configuration", "/system-map", "/routes"]:
        assert path in paths
    # Aliases are GET-only navigation surfaces; live mutation APIs remain separate gated endpoints.
    for route in app.routes:
        if getattr(route, "path", "") in {"/operator-os", "/ai", "/edge", "/edge/packets", "/edge/evidence", "/edge/calibration", "/platform", "/cockpit", "/workspace", "/tasks", "/live", "/live-controls", "/configuration"}:
            assert getattr(route, "methods", set()) <= {"GET", "HEAD"}


def test_root_v2_v3_templates_contain_bridge_links():
    dashboard = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
    live_v2 = Path("app/templates/live_v2_dashboard.html").read_text(encoding="utf-8")
    live_v3 = Path("app/templates/live_v3_dashboard.html").read_text(encoding="utf-8")
    for text in [dashboard, live_v2, live_v3]:
        assert "/v3" in text
        assert "/v3/ai" in text
        assert "/v3/ai/edge" in text
        assert "/v2-live" in text
        assert ("/v3/platform" in text or "/platform" in text or "Platform" in text)
        assert "/system-map" in text
    assert "Unified Operator Dashboard" in dashboard
    assert "Unified Operator Surface Bridge" in live_v2
    assert "Unified System Bridge" in live_v3


def test_system_map_template_documents_navigation_safety():
    template = Path("app/templates/system_map.html").read_text(encoding="utf-8")
    assert "Unified System Map" in template
    assert "Navigation links and aliases are safe entry points only" in template
    assert "AI remains draft/review-only" in template
    assert "v2 live controls remain the safety-critical live-control plane" in template
