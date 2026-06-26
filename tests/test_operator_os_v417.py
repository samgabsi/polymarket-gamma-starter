from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app import auth, paper_automation
from app.config import APP_VERSION
from app.feature_status import build_feature_status_map, build_stub_burndown_map
from app.main import app
from app.operator_os import build_workspace_context


@pytest.fixture(autouse=True)
def isolated_paper_runtime(monkeypatch, tmp_path):
    runtime = tmp_path / "paper_automation"
    monkeypatch.setattr(paper_automation, "PAPER_AUTOMATION_DIR", runtime)
    monkeypatch.setattr(paper_automation, "PAPER_ACCOUNT_PATH", runtime / "account.json")
    monkeypatch.setattr(paper_automation, "PAPER_ORDERS_PATH", runtime / "orders.jsonl")
    monkeypatch.setattr(paper_automation, "PAPER_FILLS_PATH", runtime / "fills.jsonl")
    monkeypatch.setattr(paper_automation, "PAPER_POSITIONS_PATH", runtime / "positions.json")
    monkeypatch.setattr(paper_automation, "PAPER_DECISIONS_PATH", runtime / "decisions.jsonl")
    monkeypatch.setattr(paper_automation, "PAPER_RUNS_PATH", runtime / "runs.jsonl")
    monkeypatch.setattr(paper_automation, "PAPER_AUDIT_PATH", runtime / "audit.jsonl")
    for key in list(paper_automation.os.environ):
        if key.startswith("PAPER_TRADING_"):
            monkeypatch.delenv(key, raising=False)
    yield runtime


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "test-password-123", "next": "/v3"},
            follow_redirects=False,
        )
        assert response.status_code in {303, 307}
        yield client


def test_v417_version_identity():
    assert APP_VERSION == "4.17.0-real"


def test_v417_operator_os_context_has_five_primary_workspaces():
    context = build_workspace_context("command_center")
    labels = [row["label"] for row in context["workspaces"]]
    assert labels == [
        "Command Center",
        "Opportunities",
        "Automation / Paper Trading",
        "Review & Audit",
        "Settings & System",
    ]
    assert context["shell_status"]["live_execution_used"] is False
    assert context["shell_status"]["order_submitted"] is False
    assert context["compatibility_routes"]
    assert any(row["old_route"] == "/v3/paper-trading" and row["new_route"] == "/v3/automation" for row in context["compatibility_routes"])


def test_v417_primary_workspaces_render_and_show_safety_posture(authed_client):
    expected = {
        "/v3": ["Command Center", "What needs attention right now?", "UI sprawl audit summary"],
        "/v3/automation": ["Automation / Paper Trading", "PAPER ONLY", "Run paper strategy once"],
        "/v3/review-audit": ["Review & Audit", "Pending reviews", "No review or audit events"],
        "/v3/settings-system": ["Settings & System", "Feature readiness highlights", "Advanced and compatibility links"],
    }
    for path, texts in expected.items():
        response = authed_client.get(path)
        assert response.status_code == 200
        assert "Operator OS consolidation" in response.text
        assert "No real orders" in response.text or "does not enable live trading" in response.text
        for text in texts:
            assert text in response.text


def test_v417_api_workspaces_are_safe_and_explicit(authed_client):
    for workspace in ["command_center", "opportunities", "automation", "review_audit", "settings_system"]:
        response = authed_client.get(f"/api/v3/operator-os/{workspace}")
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "4.17.0-real"
        assert body["active_workspace"] == workspace
        assert body["live_execution_used"] is False
        assert body["order_submitted"] is False
        assert body["order_cancelled"] is False
        assert len(body["workspaces"]) == 5


def test_v417_opportunities_route_remains_compatible_while_part_of_workspace(authed_client):
    page = authed_client.get("/v3/opportunities?demo=true")
    assert page.status_code == 200
    assert "Opportunity Review Workbench" in page.text
    assert "Opportunities Workspace" in page.text
    assert "Automation / Paper Trading" in page.text
    assert 'action="/v3/opportunities/review/demo_france_world_cup/status"' in page.text


def test_v417_paper_detail_route_remains_compatible_and_api_is_paper_only(authed_client):
    page = authed_client.get("/v3/paper-trading")
    assert page.status_code == 200
    assert "Automated Paper Trading" in page.text
    assert "Automation Workspace" in page.text
    assert "Paper trading only" in page.text
    api = authed_client.get("/api/v3/paper/status")
    assert api.status_code == 200
    body = api.json()
    assert body["paper_only"] is True
    assert body["live_execution_used"] is False
    assert body["can_place_real_orders"] is False
    assert body["can_cancel_real_orders"] is False


def test_v417_readiness_and_stub_map_include_operator_os_truthfulness():
    status = build_feature_status_map()
    ids = {row["feature_id"]: row for row in status["items"]}
    assert ids["operator_os.command_center"]["status"] == "working"
    assert ids["operator_os.automation_workspace"]["route"] == "/v3/automation"
    assert ids["operator_os.automation_workspace"]["live_disabled"] is True
    stub = build_stub_burndown_map()
    stub_ids = {row["feature_id"]: row for row in stub["items"]}
    assert stub_ids["operator_os.five_workspace_shell"]["status"] == "working"
    assert stub_ids["operator_os.compatibility_routes"]["operator_implication"]
