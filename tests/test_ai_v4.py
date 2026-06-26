from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import ai_openai_client, ai_operator_copilot, ai_prompt_governance, ai_schemas, ai_suggestions, ai_providers, ai_local_llm_client, ai_model_recommendations
from app import auth, live_v2, live_v3, live_v3_tasks, platform_routes, platform_storage
from app.config import APP_VERSION
from app.main import app
from app.routers import create_ai_router


@pytest.fixture(autouse=True)
def isolated_ai_runtime(tmp_path, monkeypatch):
    ai_dir = tmp_path / "ai"
    tasks_dir = tmp_path / "live_v3" / "tasks"
    live_dir = tmp_path / "live_v2"
    monkeypatch.setattr(ai_openai_client, "AI_DIR", ai_dir)
    monkeypatch.setattr(ai_openai_client, "AI_AUDIT_PATH", ai_dir / "ai_audit.jsonl")
    monkeypatch.setattr(ai_suggestions, "AI_DIR", ai_dir)
    monkeypatch.setattr(ai_suggestions, "SUGGESTIONS_PATH", ai_dir / "suggestions.jsonl")
    monkeypatch.setattr(ai_suggestions, "REVIEW_PACKETS_PATH", ai_dir / "review_packets.jsonl")
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
    monkeypatch.setattr(live_v3, "V3_DIR", tmp_path / "live_v3")
    monkeypatch.setattr(live_v3, "V3_EVENTS_PATH", tmp_path / "live_v3" / "v3_events.jsonl")
    monkeypatch.setattr(live_v3, "V3_WORKFLOW_RUNS_PATH", tmp_path / "live_v3" / "workflow_runs.jsonl")
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/ai"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_ai_version_router_and_safe_defaults():
    assert APP_VERSION == "4.17.0-real"
    assert callable(create_ai_router)
    summary = ai_openai_client.openai_settings_summary()
    provider_summary = ai_providers.list_providers()
    generic = ai_providers.generic_ai_settings_summary()
    assert generic["ai_enable"] is False
    assert generic["ai_provider"] == "mock"
    assert generic["ai_dry_run_only"] is True
    assert generic["ai_allow_network"] is False
    assert provider_summary["active_provider"] == "mock"
    assert provider_summary["count"] >= 6
    assert summary["openai_enable_api"] is False
    assert summary["openai_enable_responses_api"] is False
    assert summary["openai_dry_run_only"] is True
    assert summary["openai_redact_before_send"] is True
    assert summary["openai_require_operator_approval"] is True
    assert summary["openai_enable_tool_calling"] is False
    assert summary["openai_enable_remote_mcp"] is False
    assert summary["chatgpt_mcp_server_enabled"] is False
    assert summary["safe_default_posture"] is True
    assert summary["openai_api_key_value_returned"] is False
    local = ai_local_llm_client.local_llm_settings_summary()
    assert local["local_llm_enable"] is False
    assert local["local_llm_model"] == "qwen3:8b"
    assert local["local_llm_require_localhost"] is True
    assert local["safe_default_posture"] is True


def test_ai_local_model_recommendations_for_mac_mini_m4_16gb():
    recs = ai_model_recommendations.list_model_recommendations()
    names = {item["model"] for item in recs["items"]}
    assert {"qwen3:8b", "qwen3:4b", "gemma3:4b", "gemma3:12b"}.issubset(names)
    qwen8 = [item for item in recs["items"] if item["model"] == "qwen3:8b"][0]
    assert qwen8["recommended_default_for_mac_mini_m4_16gb"] is True
    assert qwen8["install_command"] == "ollama pull qwen3:8b"
    large = [item for item in recs["items"] if "27b" in item["model"].lower()][0]
    assert large["experimental_for_16gb"] is True
    assert large["recommended_for_16gb_default"] is False


def test_ai_redaction_prompts_and_schemas_are_safe():
    redacted = ai_openai_client.redact_ai_data({"OPENAI_API_KEY": "redaction-placeholder-key", "authorization": "Bearer redacted-token", "note": "safe"})
    dumped = json.dumps(redacted).lower()
    assert "redaction-placeholder-key" not in dumped
    assert "redacted-token" not in dumped
    prompts = ai_prompt_governance.prompt_summary()
    assert prompts["all_require_redaction"] is True
    assert prompts["all_require_human_approval"] is True
    assert prompts["all_include_safety_statement"] is True
    assert all("mock" in item.get("provider_compatibility", []) and "ollama" in item.get("provider_compatibility", []) for item in ai_prompt_governance.list_prompt_templates()["items"])
    registry = ai_schemas.schema_registry()
    assert registry["count"] >= 10
    assert all(item["contains_no_live_mutation"] and item["contains_no_trade_approval"] for item in registry["items"])
    assert ai_schemas.validate_payload("AIReviewSummary", ai_schemas.default_payload("AIReviewSummary"))["ok"] is True


def test_ai_copilot_dry_run_never_calls_network():
    result = ai_operator_copilot.run_copilot_workflow("summarize_daily_review_context", {"context_type": "tasks"})
    assert result["mode"] == "dry_run"
    assert result["provider"] == "mock"
    assert result["external_network_called"] is False
    assert result["ai_model_called"] is False
    assert result["ai_cannot_place_or_cancel_orders"] is True
    assert result["ai_cannot_approve_trades"] is True
    assert result["draft"]["no_live_mutation"] is True
    audit = ai_openai_client.list_audit_records()
    assert audit["count"] >= 1
    assert "sk-" not in json.dumps(audit).lower()


def test_ai_suggestions_require_human_acceptance_before_task_creation():
    generated = ai_suggestions.generate_suggestions({"source_context_type": "tasks", "source_context_id": "pytest"}, write=True)
    assert generated["ai_task_suggestions_require_human_acceptance"] is True
    suggestion = generated["items"][0]
    assert suggestion["human_status"] == "draft"
    assert live_v3_tasks.list_tasks(limit=10)["count"] == 0
    accepted = ai_suggestions.accept_suggestion(suggestion["suggestion_id"], {"status": "planned"})
    assert accepted["ok"] is True
    assert accepted["acceptance_required_explicit_human_action"] is True
    assert accepted["task"]["order_submitted"] is False
    assert accepted["task"]["order_cancelled"] is False
    assert accepted["task"]["live_trading_armed"] is False
    assert accepted["task"]["task_completion_is_not_trade_approval"] is True
    assert live_v3_tasks.list_tasks(limit=10)["count"] == 1


def test_chatgpt_blueprint_route_storage_and_exports_are_safe():
    blueprint = ai_suggestions.chatgpt_connector_blueprint()
    assert blueprint["read_only"] is True
    assert blueprint["auth_required"] is True
    assert blueprint["mcp_server_enabled"] is False
    for forbidden in ["place_order", "cancel_order", "approve_trade", "arm_live_trading", "export_secrets"]:
        assert forbidden in blueprint["forbidden_tools"]
    routes = platform_routes.route_inventory(app)
    assert routes["families"].get("v4_ai", 0) >= 1
    assert routes["families"].get("api_v3_ai", 0) >= 1
    storage = platform_storage.storage_summary()
    ai_namespaces = [item for item in storage["items"] if item["namespace"] == "v4_ai"]
    assert ai_namespaces and ai_namespaces[0]["package_excluded"] is True
    exported = ai_suggestions.export_json()
    assert exported["secret_values_returned"] is False
    assert exported["raw_prompts_included"] is False
    assert exported["raw_responses_included"] is False


def test_ai_routes_and_apis_render(authed_client):
    for route in [
        "/v3/ai",
        "/v3/ai/providers",
        "/v3/ai/local-llm",
        "/v3/ai/model-recommendations",
    ]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "AI" in response.text or "OpenAI" in response.text
        assert "supersecret" not in response.text.lower()
    for route in [
        "/api/v3/ai/summary",
        "/api/v3/ai/settings",
        "/api/v3/ai/providers",
        "/api/v3/ai/providers/health",
        "/api/v3/ai/openai/status",
        "/api/v3/ai/local-llm/status",
        "/api/v3/ai/model-recommendations",
        "/api/v3/ai/prompts",
        "/api/v3/ai/schemas",
        "/api/v3/ai/suggestions",
        "/api/v3/ai/chatgpt-connector",
        "/api/v3/ai/redaction-preview",
    ]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "begin private key" not in response.text.lower()
        assert "sk-test-secret" not in response.text.lower()
        assert "supersecret" not in response.text.lower()
    dry_run = authed_client.post("/api/v3/ai/copilot/dry-run", json={"workflow_id": "summarize_platform_diagnostics", "context_type": "platform"})
    assert dry_run.status_code == 200
    assert dry_run.json()["external_network_called"] is False


def test_ai_provider_dry_run_and_exports_are_safe(authed_client):
    provider_result = ai_providers.test_dry_run({"provider": "ollama", "schema_name": "AIReviewSummary"})
    assert provider_result["mode"] == "dry_run"
    assert provider_result["provider"] == "ollama"
    assert provider_result["external_network_called"] is False
    assert provider_result["ai_model_called"] is False
    resp = authed_client.post("/api/v3/ai/providers/test-dry-run", json={"provider": "ollama"})
    assert resp.status_code == 200
    assert resp.json()["external_network_called"] is False
    for route in ["/api/v3/ai/providers/export.md", "/api/v3/ai/model-recommendations/export.md", "/api/v3/ai/chatgpt-connector/blueprint"]:
        response = authed_client.get(route)
        assert response.status_code == 200
        assert "sk-test-secret" not in response.text.lower()
        assert "place_order" in response.text or "qwen3:8b" in response.text or "provider" in response.text.lower()
