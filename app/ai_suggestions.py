from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import ai_openai_client, ai_operator_copilot, ai_prompt_governance, ai_schemas, ai_providers, ai_local_llm_client, ai_model_recommendations
from .config import APP_VERSION, DATA_DIR, settings
from .platform_safety import redact_data, redact_text, safety_flags

AI_DIR = DATA_DIR / "ai"
SUGGESTIONS_PATH = AI_DIR / "suggestions.jsonl"
REVIEW_PACKETS_PATH = AI_DIR / "review_packets.jsonl"

FORBIDDEN_CONNECTOR_TOOLS = [
    "place_order",
    "cancel_order",
    "approve_trade",
    "sign_transaction",
    "arm_live_trading",
    "disable_kill_switch",
    "disable_read_only",
    "mutate_live_config",
    "export_secrets",
    "fetch_private_keys",
    "fetch_api_keys",
]

READ_ONLY_CONNECTOR_TOOLS = [
    "get_platform_summary",
    "get_route_inventory",
    "get_task_summary",
    "get_workspace_summary",
    "get_cockpit_summary",
    "get_dataset_summary",
    "get_freshness_summary",
    "get_simulation_summary",
    "get_analytics_summary",
    "get_migration_plan_summary",
    "draft_task_suggestions",
    "draft_review_summary",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _ensure_dir() -> None:
    AI_DIR.mkdir(parents=True, exist_ok=True)


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_dir()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact_data(row), sort_keys=True, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(redact_data(parsed))
        except json.JSONDecodeError:
            rows.append({"id": _record_id("invalid"), "created_at": _now(), "status": "invalid_json", "secret_values_returned": False})
    return rows


def _latest_by_id(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get(key) or row.get("id") or _record_id("row"))
        latest[rid] = row
    return sorted(latest.values(), key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)


def _base_safety() -> dict[str, Any]:
    return {
        "safety_statement": ai_schemas.AI_DRAFT_SAFETY_STATEMENT,
        "no_financial_advice": True,
        "no_trade_approval": True,
        "no_live_mutation": True,
        "no_live_mutation_statement": "AI suggestions, review packets, prompts, audit records, exports, and ChatGPT connector blueprints do not place orders, cancel orders, approve trades, arm live trading, or disable safety gates.",
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "mutates_live_trading_state": False,
        "secret_values_returned": False,
    }


def ai_settings_summary() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "ai": ai_providers.generic_ai_settings_summary(),
        "openai": ai_openai_client.openai_settings_summary(),
        "local_llm": ai_local_llm_client.local_llm_settings_summary(),
        "providers": ai_providers.list_providers(),
        "model_recommendations": ai_model_recommendations.list_model_recommendations(),
        "prompt_governance": ai_prompt_governance.prompt_summary(),
        "chatgpt_connector": chatgpt_connector_blueprint(),
        "runtime_storage_namespace": "data/ai/",
        "runtime_records_excluded_from_release_zip": True,
        **_base_safety(),
    })


def ai_summary() -> dict[str, Any]:
    suggestions = list_suggestions(limit=1000)["items"]
    packets = list_review_packets(limit=1000)["items"]
    audit = ai_openai_client.list_audit_records(limit=1000)
    return safety_flags({
        "version": APP_VERSION,
        "copilot": ai_operator_copilot.copilot_status(),
        "suggestion_count": len(suggestions),
        "draft_suggestion_count": len([s for s in suggestions if s.get("human_status") == "draft"]),
        "accepted_suggestion_count": len([s for s in suggestions if s.get("human_status") == "accepted"]),
        "review_packet_count": len(packets),
        "audit_record_count": audit["count"],
        "active_provider": ai_providers.active_provider_id(),
        "provider_count": ai_providers.list_providers()["count"],
        "recommended_local_model": ai_model_recommendations.list_model_recommendations()["recommended_default_for_mac_mini_m4_16gb"],
        "local_llm_enabled": settings.local_llm_enable,
        "api_disabled_by_default": settings.openai_enable_api is False,
        "ai_disabled_by_default": settings.ai_enable is False,
        "dry_run_only_default": settings.ai_dry_run_only is True,
        "openai_api_disabled_by_default": settings.openai_enable_api is False,
        "local_llm_disabled_by_default": settings.local_llm_enable is False,
        "chatgpt_connector_disabled_by_default": settings.chatgpt_mcp_server_enabled is False,
        "chatgpt_connector_read_only": settings.chatgpt_mcp_read_only is True,
        **_base_safety(),
    })


def _suggestion_from_draft(draft: dict[str, Any], source_context_type: str, source_context_id: str) -> dict[str, Any]:
    now = _now()
    prompt_hash = str(draft.get("prompt_hash") or "")
    response_hash = str(draft.get("response_hash") or "")
    body = draft.get("draft", draft)
    return redact_data({
        "suggestion_id": _record_id("ai_sugg"),
        "created_at": now,
        "updated_at": now,
        "app_version": APP_VERSION,
        "provider": draft.get("provider") or ai_providers.active_provider_id(),
        "model": draft.get("model") or (settings.local_llm_model if ai_providers.active_provider_id() in {"ollama", "local_openai_compatible", "llama_cpp", "lm_studio"} else settings.openai_model_review),
        "source_context_type": source_context_type,
        "source_context_id": source_context_id,
        "title": body.get("title") or "Review AI-generated operator suggestion",
        "summary": body.get("summary") or "AI generated a draft task suggestion for human review.",
        "rationale": body.get("rationale") or "Dry-run copilot output identified a review-only follow-up.",
        "suggested_task_type": body.get("suggested_task_type") or "review",
        "suggested_priority": body.get("suggested_priority") or "medium",
        "suggested_due_window": body.get("suggested_due_window") or "operator-defined",
        "safety_label": body.get("safety_label") or "review-only",
        "warnings": body.get("warnings") or ["Human acceptance is required before task creation."],
        "blockers": body.get("blockers") or [],
        "unknown_unavailable_data": body.get("unknown_unavailable_data") or [],
        "human_status": "draft",
        "accepted_task_id": "",
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        **_base_safety(),
    })


def generate_suggestions(payload: dict[str, Any] | None = None, write: bool = True) -> dict[str, Any]:
    payload = payload or {}
    source_context_type = redact_text(payload.get("source_context_type") or payload.get("context_type") or "tasks")
    source_context_id = redact_text(payload.get("source_context_id") or "local")
    result = ai_operator_copilot.draft_task_suggestions({"context_type": source_context_type, **payload})
    suggestions = [_suggestion_from_draft(result, source_context_type, source_context_id)]
    if source_context_type != "freshness":
        freshness = ai_operator_copilot.draft_freshness_summary({"context_type": "freshness", **payload})
        suggestions.append(_suggestion_from_draft({
            **freshness,
            "draft": {
                **freshness.get("draft", {}),
                "title": "Review freshness and dataset readiness AI draft",
                "suggested_priority": "high",
                "suggested_task_type": "review",
                "safety_label": "read-only-action",
            },
        }, "freshness", "local"))
    if write:
        for suggestion in suggestions:
            _write_jsonl(SUGGESTIONS_PATH, suggestion)
    return safety_flags({
        "version": APP_VERSION,
        "write": write,
        "generated_count": len(suggestions),
        "items": suggestions,
        "ai_task_suggestions_require_human_acceptance": True,
        **_base_safety(),
    })


def list_suggestions(limit: int = 250, status: str | None = None) -> dict[str, Any]:
    rows = _latest_by_id(_read_jsonl(SUGGESTIONS_PATH), "suggestion_id")
    if status:
        rows = [row for row in rows if row.get("human_status") == status]
    capped = rows[: max(1, min(int(limit or 250), 5000))]
    return safety_flags({"version": APP_VERSION, "count": len(capped), "total_count": len(rows), "items": capped, **_base_safety()})


def get_suggestion(suggestion_id: str) -> dict[str, Any] | None:
    for suggestion in _latest_by_id(_read_jsonl(SUGGESTIONS_PATH), "suggestion_id"):
        if suggestion.get("suggestion_id") == suggestion_id:
            return redact_data(suggestion)
    return None


def accept_suggestion(suggestion_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    suggestion = get_suggestion(suggestion_id)
    if not suggestion:
        return safety_flags({"ok": False, "error": "suggestion_not_found", "suggestion_id": redact_text(suggestion_id), **_base_safety()})
    payload = payload or {}
    from . import live_v3_tasks

    task = live_v3_tasks.create_task({
        "title": payload.get("title") or suggestion.get("title"),
        "description": payload.get("description") or suggestion.get("summary"),
        "source_subsystem": "ai_suggestions",
        "source_object_type": "ai_task_suggestion",
        "source_object_id": suggestion.get("suggestion_id"),
        "priority": payload.get("priority") or suggestion.get("suggested_priority") or "medium",
        "task_type": payload.get("task_type") or suggestion.get("suggested_task_type") or "review",
        "status": payload.get("status") or "planned",
        "safety_class": suggestion.get("safety_label") or "review-only",
        "unknown_unavailable_data": suggestion.get("unknown_unavailable_data", []),
        "blockers": suggestion.get("blockers", []),
        "tags": ["ai_suggestion", "human_accepted"],
        "operator_notes": "Created only after explicit human acceptance of an AI-generated draft suggestion.",
        "audit_metadata": {"ai_suggestion_id": suggestion.get("suggestion_id"), "prompt_hash": suggestion.get("prompt_hash"), "response_hash": suggestion.get("response_hash")},
    })
    updated = dict(suggestion)
    updated["human_status"] = "accepted"
    updated["accepted_task_id"] = task["task_id"]
    updated["updated_at"] = _now()
    updated.update(_base_safety())
    _write_jsonl(SUGGESTIONS_PATH, updated)
    return safety_flags({
        "ok": True,
        "suggestion": updated,
        "task": task,
        "accepted_task_id": task["task_id"],
        "acceptance_required_explicit_human_action": True,
        "task_completion_is_not_trade_approval": True,
        **_base_safety(),
    })


def dismiss_suggestion(suggestion_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    suggestion = get_suggestion(suggestion_id)
    if not suggestion:
        return safety_flags({"ok": False, "error": "suggestion_not_found", "suggestion_id": redact_text(suggestion_id), **_base_safety()})
    updated = dict(suggestion)
    updated["human_status"] = "dismissed"
    updated["dismissal_notes"] = redact_text((payload or {}).get("notes"))
    updated["updated_at"] = _now()
    updated.update(_base_safety())
    _write_jsonl(SUGGESTIONS_PATH, updated)
    return safety_flags({"ok": True, "suggestion": updated, **_base_safety()})


def generate_review_packet(payload: dict[str, Any] | None = None, write: bool = True) -> dict[str, Any]:
    payload = payload or {}
    packet_type = redact_text(payload.get("packet_type") or "AI Daily Review Summary")
    workflow_id = ai_operator_copilot.REVIEW_PACKET_WORKFLOWS.get(packet_type, "summarize_daily_review_context")
    result = ai_operator_copilot.run_copilot_workflow(workflow_id, payload)
    packet = redact_data({
        "packet_id": _record_id("ai_packet"),
        "created_at": _now(),
        "updated_at": _now(),
        "app_version": APP_VERSION,
        "packet_type": packet_type,
        "title": packet_type,
        "workflow_id": workflow_id,
        "status": "draft",
        "summary": result.get("draft", {}).get("summary", ""),
        "draft": result.get("draft", {}),
        "prompt_hash": result.get("prompt_hash"),
        "response_hash": result.get("response_hash"),
        "audit_id": result.get("audit_id"),
        "human_review_required": True,
        **_base_safety(),
    })
    if write:
        _write_jsonl(REVIEW_PACKETS_PATH, packet)
    return safety_flags({"version": APP_VERSION, "packet": packet, "write": write, **_base_safety()})


def list_review_packets(limit: int = 250) -> dict[str, Any]:
    rows = _latest_by_id(_read_jsonl(REVIEW_PACKETS_PATH), "packet_id")
    capped = rows[: max(1, min(int(limit or 250), 5000))]
    return safety_flags({"version": APP_VERSION, "count": len(capped), "items": capped, **_base_safety()})


def chatgpt_connector_blueprint() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "blueprint_enabled": settings.chatgpt_connector_blueprint_enabled,
        "mcp_server_enabled": settings.chatgpt_mcp_server_enabled,
        "read_only": settings.chatgpt_mcp_read_only,
        "auth_required": settings.chatgpt_mcp_require_auth,
        "remote_mcp_enabled": settings.openai_enable_remote_mcp,
        "ai_provider_layer": ai_providers.list_providers(),
        "allowed_read_only_tools": READ_ONLY_CONNECTOR_TOOLS,
        "forbidden_tools": FORBIDDEN_CONNECTOR_TOOLS,
        "connector_status": "blueprint_only_disabled_runtime",
        "does_not_implement_public_network_server": True,
        **_base_safety(),
    })


def redaction_preview(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    sample = payload or {"OPENAI_API_KEY": "redaction-placeholder-key", "authorization": "Bearer redacted-token", "safe": "operator review"}
    redacted = ai_openai_client.redact_ai_data(sample)
    return safety_flags({
        "input_contains_secret_marker": True,
        "redacted": redacted,
        "secret_scan": ai_openai_client.secret_scan(json.dumps(redacted, default=str)),
        **_base_safety(),
    })


def export_json() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "summary": ai_summary(),
        "settings": ai_settings_summary(),
        "providers": ai_providers.export_json(),
        "local_model_recommendations": ai_model_recommendations.list_model_recommendations(),
        "prompts": ai_prompt_governance.export_prompt_registry_json(),
        "schemas": ai_schemas.schema_registry(),
        "suggestions": list_suggestions(limit=5000),
        "review_packets": list_review_packets(limit=5000),
        "audit": ai_openai_client.list_audit_records(limit=5000),
        "chatgpt_connector_blueprint": chatgpt_connector_blueprint(),
        "raw_prompts_included": False,
        "raw_responses_included": False,
        **_base_safety(),
    })


def export_markdown() -> str:
    data = export_json()
    lines = [f"# AI Assistance Export - {APP_VERSION}", "", ai_schemas.AI_DRAFT_SAFETY_STATEMENT, ""]
    lines.extend([
        "## Safe Defaults",
        f"- AI provider: `{data['settings']['ai']['ai_provider']}`",
        f"- AI enabled: `{data['settings']['ai']['ai_enable']}`",
        f"- OpenAI API enabled: `{data['settings']['openai']['openai_enable_api']}`",
        f"- Local LLM enabled: `{data['settings']['local_llm']['local_llm_enable']}`",
        f"- Dry-run only: `{data['settings']['ai']['ai_dry_run_only']}`",
        f"- Redaction before send: `{data['settings']['ai']['ai_redact_before_send']}`",
        f"- Recommended local model for Mac mini M4 16GB: `{data['local_model_recommendations']['recommended_default_for_mac_mini_m4_16gb']}`",
        f"- ChatGPT MCP server enabled: `{data['chatgpt_connector_blueprint']['mcp_server_enabled']}`",
        "",
        "## Suggestions",
    ])
    for item in data["suggestions"]["items"]:
        lines.append(f"- `{item.get('suggestion_id')}` {item.get('title')} ({item.get('human_status')})")
    if not data["suggestions"]["items"]:
        lines.append("- No AI suggestions yet.")
    lines.extend(["", "## Review Packets"])
    for item in data["review_packets"]["items"]:
        lines.append(f"- `{item.get('packet_id')}` {item.get('title')} ({item.get('status')})")
    if not data["review_packets"]["items"]:
        lines.append("- No AI review packets yet.")
    lines.extend(["", "## Forbidden ChatGPT Connector Tools"])
    for tool in FORBIDDEN_CONNECTOR_TOOLS:
        lines.append(f"- `{tool}`")
    return "\n".join(lines) + "\n"


def suggestions_csv() -> str:
    rows = list_suggestions(limit=5000)["items"]
    out = io.StringIO()
    fields = ["suggestion_id", "created_at", "human_status", "title", "suggested_priority", "safety_label", "accepted_task_id", "no_live_mutation", "no_trade_approval"]
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return out.getvalue()


def search_items(limit: int = 250) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prompt in ai_prompt_governance.list_prompt_templates()["items"]:
        rows.append({"result_id": f"ai_prompt:{prompt['template_id']}", "result_type": "ai_prompt_template", "title": prompt["title"], "summary": prompt["category"], "status": "governed", "timestamp": "", "url": "/v3/ai/prompts", "quick_link": "/v3/ai/prompts", "tags": ["ai", "prompt"], "search_text": f"ai prompt template {prompt['title']} {prompt['category']}", "secret_values_returned": False})
    for schema in ai_schemas.schema_registry()["items"]:
        rows.append({"result_id": f"ai_schema:{schema['schema_id']}", "result_type": "ai_schema", "title": schema["title"], "summary": "Structured output schema with no-live-mutation flags.", "status": "available", "timestamp": "", "url": "/v3/ai/prompts", "quick_link": "/v3/ai/prompts", "tags": ["ai", "schema"], "search_text": f"ai schema {schema['schema_id']} no_live_mutation no_trade_approval", "secret_values_returned": False})
    for suggestion in list_suggestions(limit=limit)["items"]:
        rows.append({"result_id": f"ai_suggestion:{suggestion['suggestion_id']}", "result_type": "ai_task_suggestion", "title": suggestion["title"], "summary": suggestion["summary"], "status": suggestion["human_status"], "timestamp": suggestion["created_at"], "url": "/v3/ai/suggestions", "quick_link": "/v3/ai/suggestions", "tags": ["ai", "suggestion"], "search_text": f"ai suggestion {suggestion['title']} {suggestion['summary']}", "secret_values_returned": False})
    for packet in list_review_packets(limit=limit)["items"]:
        rows.append({"result_id": f"ai_review_packet:{packet['packet_id']}", "result_type": "ai_review_packet", "title": packet["title"], "summary": packet["summary"], "status": packet["status"], "timestamp": packet["created_at"], "url": "/v3/ai/review-packets", "quick_link": "/v3/ai/review-packets", "tags": ["ai", "review_packet"], "search_text": f"ai review packet {packet['title']} {packet['summary']}", "secret_values_returned": False})
    rows.extend(ai_providers.search_items())
    rows.append({"result_id": "ai_settings:openai", "result_type": "openai_model_config", "title": "OpenAI Safe Defaults", "summary": "API disabled, dry-run-only, no data-sharing by default.", "status": "safe-defaults", "timestamp": "", "url": "/v3/ai/settings", "quick_link": "/v3/ai/settings", "tags": ["ai", "openai"], "search_text": "openai config api disabled dry run redaction", "secret_values_returned": False})
    rows.append({"result_id": "ai_settings:local_llm", "result_type": "local_llm_config", "title": "Local LLM Safe Defaults", "summary": "Local LLM disabled by default; qwen3:8b recommended for Mac mini M4 16GB.", "status": "safe-defaults", "timestamp": "", "url": "/v3/ai/local-llm", "quick_link": "/v3/ai/local-llm", "tags": ["ai", "local_llm", "ollama"], "search_text": "local llm ollama qwen3 gemma dry run localhost", "secret_values_returned": False})
    rows.append({"result_id": "ai_chatgpt:blueprint", "result_type": "chatgpt_connector_blueprint", "title": "ChatGPT Connector Blueprint", "summary": "Read-only, auth-required, disabled runtime MCP blueprint.", "status": "blueprint", "timestamp": "", "url": "/v3/ai/chatgpt-connector", "quick_link": "/v3/ai/chatgpt-connector", "tags": ["ai", "chatgpt", "mcp"], "search_text": "chatgpt connector mcp blueprint read only forbidden tools", "secret_values_returned": False})
    return rows[: max(1, min(int(limit or 250), 5000))]


def graph_nodes() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = [
        {"node_id": "ai:provider_layer", "node_type": "ai_provider", "title": "Multi-Provider AI Layer", "status": "mock-default", "summary": "OpenAI, local LLM, and mock/dry-run providers share one safety boundary."},
        {"node_id": "ai:openai_config", "node_type": "openai_model_config", "title": "OpenAI Model Config", "status": "safe-defaults", "summary": "API disabled and dry-run-only by default."},
        {"node_id": "ai:local_llm_config", "node_type": "local_llm_model", "title": "Local LLM Config", "status": "disabled-by-default", "summary": "Ollama/qwen3:8b recommended for Mac mini M4 16GB."},
        {"node_id": "ai:prompt_governance", "node_type": "ai_safety_policy", "title": "AI Prompt Governance", "status": "active", "summary": "Redaction and human approval required."},
        {"node_id": "ai:chatgpt_blueprint", "node_type": "chatgpt_connector_blueprint", "title": "ChatGPT Connector Blueprint", "status": "blueprint", "summary": "Read-only, disabled runtime MCP plan."},
    ]
    edges = [
        {"source_node": "ai:provider_layer", "target_node": "ai:prompt_governance", "relationship_type": "governed_by"},
        {"source_node": "ai:openai_config", "target_node": "ai:provider_layer", "relationship_type": "provided_by"},
        {"source_node": "ai:local_llm_config", "target_node": "ai:provider_layer", "relationship_type": "provided_by"},
        {"source_node": "ai:chatgpt_blueprint", "target_node": "ai:prompt_governance", "relationship_type": "governed_by"},
        {"source_node": "ai:prompt_governance", "target_node": "platform:safety", "relationship_type": "protected_by"},
    ]
    for prompt in ai_prompt_governance.list_prompt_templates()["items"]:
        node_id = f"ai_prompt_template:{prompt['template_id']}"
        nodes.append({"node_id": node_id, "node_type": "ai_prompt_template", "title": prompt["title"], "status": "governed", "summary": prompt["category"]})
        edges.append({"source_node": node_id, "target_node": "ai:prompt_governance", "relationship_type": "governed_by"})
    for suggestion in list_suggestions(limit=100)["items"]:
        node_id = f"ai_task_suggestion:{suggestion['suggestion_id']}"
        nodes.append({"node_id": node_id, "node_type": "ai_task_suggestion", "title": suggestion["title"], "status": suggestion["human_status"], "summary": suggestion["summary"]})
        edges.append({"source_node": node_id, "target_node": "ai:prompt_governance", "relationship_type": "requires_human_acceptance"})
    return nodes, edges


def cleanup_runtime_records(root: Path | None = None) -> dict[str, Any]:
    root = root or AI_DIR
    removed = []
    if root.exists():
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
                removed.append(str(path))
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            root.rmdir()
        except OSError:
            pass
    return safety_flags({"removed_count": len(removed), "removed_paths": removed[:100]})
