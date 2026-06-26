from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import APP_VERSION
from app.main import app
from app import auth, live_v2
from app import platform_api, platform_diagnostics, platform_migrations, platform_plugins, platform_routes, platform_safety, platform_storage, platform_exports
from app import live_v3, live_v3_cockpit


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    live_dir = tmp_path / "live_v2"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", live_dir)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", live_dir / "audit_ledger.jsonl")
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/platform"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_v42_version_and_safety_helpers():
    assert APP_VERSION == "4.17.0-real"
    statements = platform_safety.safety_statements()
    assert statements["platform_diagnostics_do_not_mutate_live_trading_state"] is True
    assert platform_safety.action_is_forbidden("place_order") is True
    assert platform_safety.action_is_forbidden("cancel_order") is True
    assert platform_safety.action_is_forbidden("arm_live_trading") is True
    assert "supersecret" not in platform_safety.redact_text("api_key=supersecret").lower()
    assert platform_safety.validate_safety_class("bad") == "informational"


def test_api_schema_inventory_and_response_envelope_are_safe():
    envelope = platform_api.api_response_envelope(
        "tests",
        "schema_probe",
        data={"ok": True},
        unknown_unavailable_data=["test unknown"],
    )
    validation = platform_api.validate_envelope_shape(envelope)
    schema = platform_api.summarize_api_schema_consistency(app)
    export_json = platform_api.export_schema_inventory_json(app)
    export_md = platform_api.export_schema_inventory_markdown(app)
    assert validation["ok"] is True
    assert envelope["success"] is True
    assert envelope["app_version"] == "4.17.0-real"
    assert envelope["package_name"] == "Polymarket OP Console"
    assert envelope["package_slug"] == "polymarket-op-console"
    assert envelope["unknown_unavailable_data"]
    assert "do not place" in envelope["safety_statement"].lower()
    assert schema["summary"]["api_family_count"] >= 8
    assert schema["summary"]["schema_object_count"] >= 5
    assert export_json["secret_values_returned"] is False
    assert "API Schema Inventory" in export_md


def test_runtime_migration_planner_is_non_destructive(monkeypatch, tmp_path):
    monkeypatch.setattr(platform_migrations, "DATA_DIR", tmp_path / "data")
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    summary = platform_migrations.migration_summary()
    plan = platform_migrations.migration_plan()
    storage_map = platform_migrations.storage_map()
    export_json = platform_migrations.export_migration_plan_json()
    export_md = platform_migrations.export_migration_plan_markdown()
    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert before == after
    assert summary["migration_planner_does_not_mutate_runtime_data"] is True
    assert plan["automatic_runtime_migration"] is False
    assert plan["migration_planner_does_not_delete_move_rewrite_or_migrate_data"] is True
    assert any(step["classification"] == "destructive action prohibited" for step in plan["steps"])
    assert storage_map["package_excluded_runtime_data"] is True
    assert export_json["secret_values_returned"] is False
    assert "Runtime Migration Plan" in export_md


def test_plugin_manifests_are_metadata_only_and_reject_forbidden_capabilities():
    loaded = platform_plugins.load_plugin_manifests(include_runtime=False)
    assert loaded["count"] >= 3
    assert loaded["plugin_manifests_do_not_execute_code"] is True
    assert all(item["validation"]["ok"] is True for item in loaded["items"])
    bad = platform_plugins.validate_manifest({
        "plugin_id": "bad_live_plugin",
        "plugin_type": "local-ui-extension",
        "capabilities": ["place_order"],
        "no_live_mutation": True,
        "no_secret_access": True,
        "no_network_by_default": True,
    })
    assert bad["ok"] is False
    assert bad["arbitrary_code_executed"] is False
    assert bad["remote_code_loaded"] is False


def test_route_storage_diagnostics_and_exports_are_safe():
    routes = platform_routes.route_inventory(app)
    storage = platform_storage.storage_summary()
    diag = platform_diagnostics.diagnostics_summary(app)
    export = platform_diagnostics.export_json(app)
    markdown = platform_diagnostics.export_markdown(app)
    assert routes["count"] > 0
    assert routes["route_inventory_does_not_mutate_live_trading_state"] is True
    assert storage["count"] >= 5
    assert storage["migration_policy"].startswith("non-destructive")
    assert diag["api_schema"]["summary"]["api_family_count"] >= 8
    assert diag["migrations"]["destructive_actions_prohibited"] is True
    assert diag["diagnostics_do_not_mutate_live_trading_state"] is True
    assert export["secret_values_returned"] is False
    assert platform_exports.validate_export_secret_safe(export)["ok"] is True
    assert "do not place" in markdown.lower() or "does not place" in markdown.lower()
    assert "private_key" not in json.dumps(export).lower()


def test_platform_integrates_with_search_graph_workflows_demo_and_command_center():
    search = live_v3.search_local("platform", limit=500)
    assert any(str(item.get("result_type", "")).startswith("platform") for item in search["items"])
    graph = live_v3.build_decision_graph(limit=500)
    assert graph.get("platform_nodes", 0) >= 1
    center = live_v3.build_command_center()
    assert "platform" in center["groups"]
    templates = live_v3.workflow_templates()
    assert any(t["workflow_id"] == "platform_health_review" for t in templates["templates"])
    assert any(t["workflow_id"] == "api_schema_consistency_review" for t in templates["templates"])
    assert any(t["workflow_id"] == "runtime_migration_planning_review" for t in templates["templates"])
    run = live_v3.run_workflow({"workflow_id": "runtime_migration_planning_review"})
    assert run["status"] == "completed"
    assert run["order_submitted"] is False
    fixture = live_v3.build_demo_fixture()
    assert fixture["v4_platform"]["safe_demo_data"] is True
    assert fixture["v4_platform"]["fake_api_schema_inventory"]["success"] is True
    assert fixture["v4_platform"]["fake_runtime_migration_plan"]["automatic_runtime_migration"] is False


def test_platform_routes_and_apis_render(authed_client):
    for route in ["/v3/platform", "/v3/platform/health", "/v3/platform/routes", "/v3/platform/schema", "/v3/platform/plugins", "/v3/platform/storage", "/v3/platform/migrations", "/v3/platform/migrations/plan", "/v3/platform/migrations/storage-map", "/v3/platform/diagnostics", "/v3/platform/exports", "/v3/platform/settings"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "v4.7.0-real" in response.text
        assert "Platform" in response.text or "platform" in response.text
        assert "do not place" in response.text or "do not execute" in response.text
    for route in ["/api/v3/platform/summary", "/api/v3/platform/health", "/api/v3/platform/routes", "/api/v3/platform/route-registry", "/api/v3/platform/routes/export.json", "/api/v3/platform/routes/export.md", "/api/v3/platform/schema", "/api/v3/platform/schema/families", "/api/v3/platform/schema/envelopes", "/api/v3/platform/schema/objects", "/api/v3/platform/schema/export.json", "/api/v3/platform/schema/export.md", "/api/v3/platform/plugins", "/api/v3/platform/storage", "/api/v3/platform/storage/export.json", "/api/v3/platform/storage/export.md", "/api/v3/platform/migrations/summary", "/api/v3/platform/migrations/plan", "/api/v3/platform/migrations/storage-map", "/api/v3/platform/migrations/export.json", "/api/v3/platform/migrations/export.md", "/api/v3/platform/diagnostics", "/api/v3/platform/export.json", "/api/v3/platform/export.md", "/api/v3/platform/settings"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "private_key" not in response.text.lower()
        assert "supersecret" not in response.text.lower()
    post = authed_client.post("/api/v3/platform/settings", json={"show_unknown_unavailable_data": True})
    assert post.status_code == 200
    assert post.json()["order_cancelled"] is False


def test_cockpit_existing_forbidden_action_still_rejected():
    forbidden = live_v3_cockpit.run_command_palette_action({"action_id": "place_order"})
    assert forbidden["status"] == "rejected"
    assert forbidden["order_submitted"] is False
    assert forbidden["order_cancelled"] is False
