from __future__ import annotations

import json
from typing import Any

from .config import APP_VERSION, settings
from .platform_safety import safety_flags
from . import ai_local_llm_client, ai_model_recommendations, ai_openai_client

PROVIDER_TYPES = ["mock", "openai", "local_openai_compatible", "ollama", "llama_cpp", "lm_studio"]
LOCAL_PROVIDER_IDS = {"local_openai_compatible", "ollama", "llama_cpp", "lm_studio"}


def generic_ai_settings_summary() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "ai_enable": settings.ai_enable,
        "ai_provider": settings.ai_provider,
        "ai_dry_run_only": settings.ai_dry_run_only,
        "ai_require_operator_approval": settings.ai_require_operator_approval,
        "ai_redact_before_send": settings.ai_redact_before_send,
        "ai_allow_network": settings.ai_allow_network,
        "ai_allow_runtime_data": settings.ai_allow_runtime_data,
        "ai_allow_market_data": settings.ai_allow_market_data,
        "ai_allow_task_data": settings.ai_allow_task_data,
        "ai_allow_docs_data": settings.ai_allow_docs_data,
        "ai_allow_platform_diagnostics": settings.ai_allow_platform_diagnostics,
        "ai_allow_migration_reports": settings.ai_allow_migration_reports,
        "ai_log_prompt_hashes_only": settings.ai_log_prompt_hashes_only,
        "ai_store_raw_prompts": settings.ai_store_raw_prompts,
        "ai_store_raw_responses": settings.ai_store_raw_responses,
        "ai_audit_enabled": settings.ai_audit_enabled,
        "ai_max_input_chars": settings.ai_max_input_chars,
        "ai_max_output_tokens": settings.ai_max_output_tokens,
        "ai_timeout_seconds": settings.ai_timeout_seconds,
        "safe_default_posture": settings.ai_enable is False and settings.ai_provider == "mock" and settings.ai_dry_run_only is True and settings.ai_allow_network is False and settings.ai_redact_before_send is True,
        "safety_statement": "AI is disabled by default, mock/dry-run by default, redacted by default, and cannot place or cancel orders.",
        "secret_values_returned": False,
        "no_live_mutation": True,
    })


def _provider_card(provider_id: str) -> dict[str, Any]:
    provider_id = provider_id if provider_id in PROVIDER_TYPES else "mock"
    is_local = provider_id in LOCAL_PROVIDER_IDS
    title_map = {
        "mock": "Mock / dry-run provider",
        "openai": "OpenAI / ChatGPT cloud provider",
        "local_openai_compatible": "Local OpenAI-compatible endpoint",
        "ollama": "Ollama local runtime",
        "llama_cpp": "llama.cpp server",
        "lm_studio": "LM Studio local runtime",
    }
    if provider_id == "openai":
        configured = bool(settings.openai_api_key) and settings.openai_enable_api and settings.ai_enable
        base_url = settings.openai_base_url
        model = settings.openai_model_review
        enabled = settings.openai_enable_api and settings.ai_enable
        network_allowed = settings.ai_allow_network
    elif is_local:
        configured = settings.local_llm_enable and settings.ai_enable
        base_url = settings.local_llm_base_url
        model = settings.local_llm_model
        enabled = settings.local_llm_enable and settings.ai_enable
        network_allowed = settings.local_llm_allow_network and settings.ai_allow_network
    else:
        configured = True
        base_url = "local deterministic mock"
        model = "mock-dry-run"
        enabled = True
        network_allowed = False
    return safety_flags({
        "provider_id": provider_id,
        "provider_title": title_map[provider_id],
        "enabled": bool(enabled),
        "configured": bool(configured),
        "dry_run": settings.ai_dry_run_only or provider_id == "mock",
        "network_allowed": bool(network_allowed),
        "base_url": base_url,
        "model": model,
        "local_only": provider_id in LOCAL_PROVIDER_IDS or provider_id == "mock",
        "localhost_required": provider_id in LOCAL_PROVIDER_IDS,
        "structured_output_support": True,
        "tool_calling_support": False,
        "max_input_chars": settings.local_llm_max_input_chars if is_local else settings.openai_max_input_chars if provider_id == "openai" else settings.ai_max_input_chars,
        "max_output_tokens": settings.local_llm_max_output_tokens if is_local else settings.openai_max_output_tokens if provider_id == "openai" else settings.ai_max_output_tokens,
        "timeout": settings.local_llm_timeout_seconds if is_local else settings.openai_timeout_seconds if provider_id == "openai" else settings.ai_timeout_seconds,
        "safety_warnings": [
            "Provider outputs are drafts for human review.",
            "Provider cannot place orders, cancel orders, approve trades, arm live trading, or disable safety gates.",
        ],
        "limitations": ["Live calls require explicit AI_ENABLE plus provider-specific opt-in flags.", "Package validation uses mock/dry-run without network."],
        "no_live_mutation": True,
        "secret_values_returned": False,
    })


def list_providers() -> dict[str, Any]:
    items = [_provider_card(pid) for pid in PROVIDER_TYPES]
    active = active_provider_id()
    return safety_flags({
        "version": APP_VERSION,
        "active_provider": active,
        "items": items,
        "count": len(items),
        "openai": ai_openai_client.openai_settings_summary(),
        "local_llm": ai_local_llm_client.local_llm_settings_summary(),
        "model_recommendations": ai_model_recommendations.list_model_recommendations(),
        "safety_statement": "All AI providers are draft-only and no-live-mutation.",
        "no_live_mutation": True,
        "secret_values_returned": False,
    })


def active_provider_id() -> str:
    provider = str(settings.ai_provider or "mock").strip().lower()
    if provider not in PROVIDER_TYPES:
        return "mock"
    return provider


def providers_health(dry_run: bool = True) -> dict[str, Any]:
    provider_health: list[dict[str, Any]] = []
    for item in list_providers()["items"]:
        pid = item["provider_id"]
        if pid in LOCAL_PROVIDER_IDS:
            health = ai_local_llm_client.health_check(dry_run=True if dry_run else not (settings.ai_enable and settings.local_llm_enable and settings.local_llm_allow_network and not settings.ai_dry_run_only))
        elif pid == "openai":
            health = safety_flags({"provider": "openai", "status": "configured" if settings.openai_api_key else "missing_api_key", "available": bool(settings.openai_api_key), "external_network_called": False, "ai_model_called": False, "dry_run": True, "no_live_mutation": True, "secret_values_returned": False})
        else:
            health = safety_flags({"provider": "mock", "status": "available", "available": True, "external_network_called": False, "ai_model_called": False, "dry_run": True, "no_live_mutation": True, "secret_values_returned": False})
        provider_health.append(health)
    return safety_flags({"version": APP_VERSION, "items": provider_health, "count": len(provider_health), "no_network_by_default": True, "no_live_mutation": True, "secret_values_returned": False})


def test_dry_run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    provider = str(payload.get("provider") or active_provider_id())
    schema = str(payload.get("schema_name") or "AIReviewSummary")
    result = request_structured_output(workflow_id="provider_test_dry_run", template_id="provider_test", instructions="Return a safe structured draft only.", input_data={"test": "dry_run", "provider": provider}, schema_name=schema, input_category="redacted_local_summary", operator_approved=False, provider_id=provider)
    result["provider_test"] = True
    return result


def request_structured_output(
    *,
    workflow_id: str,
    template_id: str,
    instructions: str,
    input_data: Any,
    schema_name: str = "AIReviewSummary",
    input_category: str = "runtime_data",
    operator_approved: bool = False,
    model: str | None = None,
    provider_id: str | None = None,
) -> dict[str, Any]:
    provider = str(provider_id or active_provider_id()).strip().lower()
    if provider not in PROVIDER_TYPES:
        provider = "mock"
    if provider == "openai" and settings.ai_enable and not settings.ai_dry_run_only and settings.ai_allow_network:
        result = ai_openai_client.request_structured_output(workflow_id=workflow_id, template_id=template_id, instructions=instructions, input_data=input_data, schema_name=schema_name, input_category=input_category, operator_approved=operator_approved, model=model)
        result["provider"] = "openai"
        return result
    if provider in LOCAL_PROVIDER_IDS:
        result = ai_local_llm_client.request_structured_output(workflow_id=workflow_id, template_id=template_id, instructions=instructions, input_data=input_data, schema_name=schema_name, input_category=input_category, operator_approved=operator_approved, model=model)
        result["provider"] = provider
        return result
    result = ai_openai_client.request_structured_output(workflow_id=workflow_id, template_id=template_id, instructions=instructions, input_data=input_data, schema_name=schema_name, input_category=input_category, operator_approved=False, model=model)
    result["provider"] = "mock"
    result["mode"] = "dry_run"
    result["external_network_called"] = False
    result["ai_model_called"] = False
    return result


def export_json() -> dict[str, Any]:
    return list_providers()


def export_markdown() -> str:
    data = list_providers()
    lines = [f"# AI Provider Summary - {APP_VERSION}", "", "All providers are no-live-mutation and draft-only.", ""]
    lines.append(f"Active provider: `{data['active_provider']}`")
    lines.append("")
    for item in data["items"]:
        lines.extend([
            f"## {item['provider_title']}",
            f"- Provider ID: `{item['provider_id']}`",
            f"- Enabled: `{item['enabled']}`",
            f"- Dry-run: `{item['dry_run']}`",
            f"- Network allowed: `{item['network_allowed']}`",
            f"- Model: `{item['model']}`",
            "",
        ])
    return "\n".join(lines)


def search_items() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list_providers()["items"]:
        rows.append({"result_id": f"ai_provider:{item['provider_id']}", "result_type": "ai_provider", "title": item["provider_title"], "summary": f"model={item['model']} dry_run={item['dry_run']}", "status": "enabled" if item["enabled"] else "disabled", "timestamp": "", "url": "/v3/ai/providers", "quick_link": "/v3/ai/providers", "tags": ["ai", "provider"], "search_text": f"ai provider {item['provider_id']} {item['provider_title']} {item['model']}", "secret_values_returned": False})
    for rec in ai_model_recommendations.list_model_recommendations()["items"]:
        rows.append({"result_id": f"ai_model:{rec['model']}", "result_type": "local_llm_model", "title": rec["model"], "summary": rec["intended_use_case"], "status": "recommended" if rec.get("recommended_for_16gb_default") else "experimental", "timestamp": "", "url": "/v3/ai/model-recommendations", "quick_link": "/v3/ai/model-recommendations", "tags": ["ai", "local_llm", "model"], "search_text": f"local llm model {rec['model']} {rec['install_command']} {rec['memory_tier']}", "secret_values_returned": False})
    return rows


def graph_nodes() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for item in list_providers()["items"]:
        node_id = f"ai_provider:{item['provider_id']}"
        nodes.append({"node_id": node_id, "node_type": "ai_provider", "title": item["provider_title"], "status": "enabled" if item["enabled"] else "disabled", "summary": f"{item['model']} / dry_run={item['dry_run']}"})
        edges.append({"source_node": node_id, "target_node": "ai:prompt_governance", "relationship_type": "governed_by"})
    for rec in ai_model_recommendations.list_model_recommendations()["items"]:
        node_id = f"local_llm_model:{rec['model']}"
        nodes.append({"node_id": node_id, "node_type": "local_llm_model", "title": rec["model"], "status": "recommended" if rec.get("recommended_for_16gb_default") else "experimental", "summary": rec["intended_use_case"]})
        edges.append({"source_node": node_id, "target_node": "ai_provider:ollama", "relationship_type": "provided_by"})
    return nodes, edges
