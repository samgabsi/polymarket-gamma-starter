from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import ai_edge_research, ai_evidence, ai_openai_client, ai_suggestions, auth, live_v2, live_v3_tasks, live_v3_workspace
from app.config import APP_VERSION
from app.feature_status import build_feature_status_map, build_stub_burndown_map
from app.main import app


@pytest.fixture(autouse=True)
def isolated_v411_runtime(tmp_path, monkeypatch):
    ai_dir = tmp_path / "ai"
    edge_dir = ai_dir / "edge"
    workspace_dir = tmp_path / "live_v3" / "workspace"
    tasks_dir = tmp_path / "live_v3" / "tasks"
    live_dir = tmp_path / "live_v2"

    monkeypatch.setattr(ai_openai_client, "AI_DIR", ai_dir)
    monkeypatch.setattr(ai_openai_client, "AI_AUDIT_PATH", ai_dir / "ai_audit.jsonl")
    monkeypatch.setattr(ai_suggestions, "AI_DIR", ai_dir)
    monkeypatch.setattr(ai_suggestions, "SUGGESTIONS_PATH", ai_dir / "suggestions.jsonl")
    monkeypatch.setattr(ai_suggestions, "REVIEW_PACKETS_PATH", ai_dir / "review_packets.jsonl")
    monkeypatch.setattr(ai_edge_research, "EDGE_DIR", edge_dir)
    monkeypatch.setattr(ai_edge_research, "RESEARCH_PACKETS_PATH", edge_dir / "research_packets.jsonl")
    monkeypatch.setattr(ai_evidence, "EDGE_DIR", edge_dir)
    monkeypatch.setattr(ai_evidence, "EVIDENCE_SOURCES_PATH", edge_dir / "evidence_sources.jsonl")

    monkeypatch.setattr(live_v3_workspace, "WORKSPACE_DIR", workspace_dir)
    monkeypatch.setattr(live_v3_workspace, "WORKSPACE_EVENTS_PATH", workspace_dir / "workspace_events.jsonl")
    monkeypatch.setattr(live_v3_workspace, "FLOWS_PATH", workspace_dir / "guided_review_flows.jsonl")
    monkeypatch.setattr(live_v3_workspace, "SESSIONS_PATH", workspace_dir / "guided_review_sessions.jsonl")
    monkeypatch.setattr(live_v3_workspace, "PACKETS_PATH", workspace_dir / "guided_review_packets.jsonl")
    monkeypatch.setattr(live_v3_workspace, "DEPENDENCIES_PATH", workspace_dir / "task_dependencies.jsonl")
    monkeypatch.setattr(live_v3_workspace, "SOURCE_PREVIEWS_PATH", workspace_dir / "source_previews.jsonl")
    monkeypatch.setattr(live_v3_workspace, "SAVED_VIEWS_PATH", workspace_dir / "saved_task_views.jsonl")
    monkeypatch.setattr(live_v3_workspace, "SETTINGS_PATH", workspace_dir / "settings.json")
    monkeypatch.setattr(live_v3_workspace, "EXPORT_MANIFESTS_PATH", workspace_dir / "export_manifests.jsonl")

    monkeypatch.setattr(live_v3_tasks, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(live_v3_tasks, "TASK_EVENTS_PATH", tasks_dir / "task_events.jsonl")
    monkeypatch.setattr(live_v3_tasks, "TASKS_PATH", tasks_dir / "operator_tasks.jsonl")
    monkeypatch.setattr(live_v3_tasks, "INBOX_PATH", tasks_dir / "task_inbox.jsonl")
    monkeypatch.setattr(live_v3_tasks, "TEMPLATES_PATH", tasks_dir / "task_templates.jsonl")
    monkeypatch.setattr(live_v3_tasks, "CADENCE_PATH", tasks_dir / "cadence_rules.jsonl")
    monkeypatch.setattr(live_v3_tasks, "CADENCE_EVENTS_PATH", tasks_dir / "cadence_events.jsonl")
    monkeypatch.setattr(live_v3_tasks, "DAILY_OPS_PATH", tasks_dir / "daily_ops_packets.jsonl")
    monkeypatch.setattr(live_v3_tasks, "WEEKLY_OPS_PATH", tasks_dir / "weekly_ops_packets.jsonl")
    monkeypatch.setattr(live_v3_tasks, "SETTINGS_PATH", tasks_dir / "settings.json")
    monkeypatch.setattr(live_v3_tasks, "EXPORT_MANIFESTS_PATH", tasks_dir / "export_manifests.jsonl")

    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", live_dir)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", live_dir / "audit_ledger.jsonl")
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/cockpit"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_v411_stub_burndown_map_covers_required_surfaces():
    assert APP_VERSION == "4.17.0-real"
    data = build_stub_burndown_map()
    ids = {item["feature_id"] for item in data["items"]}
    required = {
        "polymarket.discovery_pricing_orderbook",
        "ai.news_odds",
        "ai.edge_research",
        "ai.yes_no_recommendation",
        "arbitrage.scanner_review",
        "venues.kalshi",
        "venues.registry",
        "review.queue_actions",
        "audit.operator_log",
        "cockpit.layouts_focus",
        "tasks.triage_blockers",
        "settings.config",
        "features.readiness_registry",
        "data.export_import",
        "launch.helpers",
        "live.execution_controls",
    }
    assert required.issubset(ids)
    assert data["review_only"] is True
    assert data["order_submitted"] is False
    assert data["counts"]["working"] >= 8
    assert data["counts"]["partial"] >= 1
    assert "broken_visible_ui" in data["audit_categories"]

    feature_status = build_feature_status_map()
    assert feature_status["stub_burndown"]["count"] == data["count"]


def test_v411_stub_burndown_endpoint_and_cockpit_render(authed_client):
    response = authed_client.get("/api/v3/features/stub-burndown")
    assert response.status_code == 200
    body = response.json()
    assert body["map_is_static_no_live_probe"] is True
    assert body["secret_values_returned"] is False

    cockpit = authed_client.get("/v3/cockpit")
    assert cockpit.status_code == 200
    assert "Stub Burn-down Map" in cockpit.text
    assert "polymarket.discovery_pricing_orderbook" in cockpit.text
    assert 'href="/api/v3/features/stub-burndown"' in cockpit.text


def test_v411_post_only_controls_are_page_forms(authed_client):
    workspace = authed_client.get("/v3/workspace")
    assert workspace.status_code == 200
    assert 'action="/v3/workspace/daily-review/start"' in workspace.text
    assert 'action="/v3/workspace/weekly-review/start"' in workspace.text
    assert 'action="/v3/workspace/task-triage/start"' in workspace.text
    assert 'href="/api/v3/workspace/daily-review/start"' not in workspace.text
    assert 'href="/api/v3/workspace/weekly-review/start"' not in workspace.text
    assert 'href="/api/v3/workspace/task-triage/start"' not in workspace.text

    ai_page = authed_client.get("/v3/ai")
    assert ai_page.status_code == 200
    for action in [
        "/v3/ai/providers/test-dry-run",
        "/v3/ai/edge/packets/generate",
        "/v3/ai/edge/evidence/normalize",
        "/v3/ai/review-packets/generate",
    ]:
        assert f'action="{action}"' in ai_page.text
    for dead_href in [
        "/api/v3/ai/providers/test-dry-run",
        "/api/v3/ai/edge/packets/generate",
        "/api/v3/ai/edge/evidence/normalize",
        "/api/v3/ai/review-packets/generate",
    ]:
        assert f'href="{dead_href}"' not in ai_page.text


def test_v411_page_post_wrappers_redirect_with_operator_feedback(authed_client):
    posts = [
        "/v3/workspace/daily-review/start",
        "/v3/workspace/weekly-review/start",
        "/v3/workspace/task-triage/start",
        "/v3/ai/providers/test-dry-run",
        "/v3/ai/edge/packets/generate",
        "/v3/ai/edge/evidence/normalize",
        "/v3/ai/review-packets/generate",
    ]
    for route in posts:
        response = authed_client.post(route, follow_redirects=False)
        assert response.status_code in {303, 307}, route
        assert "action_status=" in response.headers["location"]

    feedback = authed_client.get("/v3/ai/edge/packets?action_status=ai_edge_packet_generated&action_detail=test_packet")
    assert feedback.status_code == 200
    assert "Ai Edge Packet Generated" in feedback.text
    assert "test_packet" in feedback.text
