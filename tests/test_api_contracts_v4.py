from __future__ import annotations

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app import auth, live_v2, live_v3_cockpit, live_v3_tasks, live_v3_workspace
from app import platform_api, platform_migrations, platform_plugins, platform_route_registry, platform_routes
from app.config import APP_VERSION, PROJECT_ROOT
from app.main import app
from app.routers import create_platform_router, create_v3_core_router


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


def test_version_package_and_router_import_contracts():
    assert APP_VERSION == "4.17.0-real"
    assert platform_api.PACKAGE_NAME == "Polymarket OP Console"
    assert platform_api.PACKAGE_SLUG == "polymarket-op-console"
    assert callable(create_platform_router)
    assert callable(create_v3_core_router)


def test_extracted_routes_are_mounted_and_path_preserving():
    paths = {getattr(route, "path", "") for route in app.routes}
    for path in [
        "/v3/platform",
        "/v3/platform/routes",
        "/api/v3/platform/summary",
        "/api/v3/platform/route-registry",
        "/api/v3/platform/migrations/plan",
        "/api/v3/ux/status",
        "/api/v3/ux/design-system",
        "/api/v3/ux/navigation",
    ]:
        assert path in paths
    names = {getattr(route, "name", "") for route in app.routes}
    assert "v3_platform_page" in names
    assert "api_v3_ux_status" in names


def test_route_ownership_registry_contract():
    registry = platform_route_registry.route_ownership_registry(app)
    extracted = {item["family_id"]: item for item in registry["items"] if item["extraction_status"] == "extracted"}
    assert registry["route_registry_does_not_call_handlers"] is True
    assert registry["route_registry_does_not_mutate_live_trading_state"] is True
    assert extracted["v4_platform"]["router_module"] == "app/routers/platform.py"
    assert extracted["api_v3_platform"]["router_module"] == "app/routers/platform.py"
    assert extracted["api_v3_core"]["router_module"] == "app/routers/v3_core.py"
    assert any(item["extraction_status"] == "do-not-move-yet" for item in registry["items"])


def test_route_inventory_and_schema_contracts():
    routes = platform_routes.route_inventory(app)
    schema = platform_api.summarize_api_schema_consistency(app)
    envelope = platform_api.api_response_envelope("tests", "contract")
    assert routes["route_ownership_registry"]["extracted_router_modules"]
    assert any(item["router_module"] == "app/routers/platform.py" for item in routes["items"])
    assert platform_api.validate_envelope_shape(envelope)["ok"] is True
    assert schema["summary"]["api_family_count"] >= 10
    assert "envelope_adoption_summary" in schema["data"]
    assert schema["data"]["recommended_next_normalization_targets"]
    assert schema["secret_values_returned"] is False


def test_migration_planner_contract_is_dry_run_only(monkeypatch, tmp_path):
    monkeypatch.setattr(platform_migrations, "DATA_DIR", tmp_path / "data")
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    plan = platform_migrations.migration_plan()
    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert before == after
    assert plan["source_version"] == "4.2.0-real"
    assert plan["target_version"] == "4.17.0-real"
    assert plan["dry_run_only"] is True
    assert plan["automatic_runtime_migration"] is False
    assert plan["export_safety_validation"]["ok"] is True
    assert plan["migration_planner_does_not_delete_move_rewrite_or_migrate_data"] is True


def test_plugin_and_safe_summary_contracts():
    plugins = platform_plugins.load_plugin_manifests(include_runtime=False)
    assert plugins["plugin_manifests_do_not_execute_code"] is True
    assert plugins["invalid_count"] == 0
    assert live_v3_cockpit.cockpit_summary()["secret_values_returned"] is False
    assert live_v3_workspace.workspace_summary()["secret_values_returned"] is False
    assert live_v3_tasks.task_summary()["secret_values_returned"] is False
    forbidden = live_v3_cockpit.run_command_palette_action({"action_id": "place_order"})
    assert forbidden["status"] == "rejected"
    assert forbidden["order_submitted"] is False
    assert forbidden["order_cancelled"] is False


def test_authenticated_platform_api_contracts(authed_client):
    for path in [
        "/api/v3/platform/summary",
        "/api/v3/platform/routes",
        "/api/v3/platform/route-registry",
        "/api/v3/platform/schema",
        "/api/v3/platform/migrations/plan",
        "/api/v3/platform/plugins",
        "/api/v3/ux/status",
    ]:
        response = authed_client.get(path)
        assert response.status_code == 200, path
        body = response.text.lower()
        assert "supersecret" not in body
        assert "private_key" not in body


def test_live_control_routes_are_auth_protected_without_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "USERS_PATH", tmp_path / "missing-users.json")
    with TestClient(app) as client:
        response = client.get("/api/v2/live/status")
    assert response.status_code in {401, 403}


def test_generated_manual_script_and_outputs_are_secret_free():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run([sys.executable, "scripts/generate_operator_manual.py"], cwd=PROJECT_ROOT, env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    manual = PROJECT_ROOT / "docs/generated/OPERATOR_MANUAL_v4.17.0-real.md"
    route_inventory = PROJECT_ROOT / "docs/generated/ROUTE_INVENTORY_v4.17.0-real.md"
    assert manual.exists()
    assert route_inventory.exists()
    text = manual.read_text(encoding="utf-8")
    assert "Polymarket OP Console Operator Manual - v4.17.0-real" in text
    assert "Safety Notice" in text
    assert "supersecret" not in text.lower()
    assert "begin private key" not in text.lower()
