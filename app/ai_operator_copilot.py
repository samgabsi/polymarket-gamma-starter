from __future__ import annotations

import json
from typing import Any

from . import ai_openai_client, ai_prompt_governance, ai_schemas, ai_providers
from .config import APP_VERSION
from .platform_safety import redact_data, safety_flags

WORKFLOW_SCHEMAS = {
    "summarize_daily_review_context": ("daily_review_summary", "AIReviewSummary", "tasks"),
    "summarize_weekly_review_context": ("weekly_review_summary", "AIReviewSummary", "tasks"),
    "summarize_platform_diagnostics": ("platform_diagnostics_summary", "AIReviewSummary", "platform_diagnostics"),
    "explain_validation_failure": ("validation_failure_explanation", "AIValidationFailureExplanation", "validation"),
    "explain_blockers": ("validation_failure_explanation", "AIBlockerExplanation", "runtime_data"),
    "explain_unknown_unavailable_data": ("validation_failure_explanation", "AIUnknownUnavailableExplanation", "runtime_data"),
    "draft_task_suggestions": ("task_suggestion", "AITaskSuggestion", "tasks"),
    "draft_source_preview_summary": ("source_preview_summary", "AIReviewSummary", "runtime_data"),
    "draft_dataset_readiness_summary": ("dataset_readiness_summary", "AIDatasetReadinessSummary", "runtime_data"),
    "draft_freshness_summary": ("freshness_summary", "AIFreshnessSummary", "runtime_data"),
    "draft_simulation_report_summary": ("simulation_summary", "AISimulationSummary", "runtime_data"),
    "draft_analytics_learning_summary": ("analytics_summary", "AIAnalyticsSummary", "runtime_data"),
    "draft_governance_review_summary": ("governance_summary", "AIGovernanceSummary", "runtime_data"),
    "draft_migration_plan_summary": ("migration_plan_summary", "AIMigrationPlanSummary", "migration_reports"),
    "draft_release_notes": ("release_notes_draft", "AIReleaseNotesDraft", "docs"),
    "draft_operator_manual_section": ("operator_manual_section_draft", "AIOperatorManualSectionDraft", "docs"),
    "draft_api_schema_explanation": ("api_schema_explanation", "AIReviewSummary", "platform_diagnostics"),
    "classify_task_priority_review_only": ("task_suggestion", "AITaskSuggestion", "tasks"),
    "classify_safety_label_review_only": ("task_suggestion", "AITaskSuggestion", "tasks"),
    "chatgpt_connector_tool_description": ("chatgpt_connector_tool_description", "AIChatGPTConnectorToolDescription", "connector_blueprint"),
}

REVIEW_PACKET_WORKFLOWS = {
    "AI Daily Review Summary": "summarize_daily_review_context",
    "AI Weekly Review Summary": "summarize_weekly_review_context",
    "AI Platform Diagnostics Summary": "summarize_platform_diagnostics",
    "AI Migration Plan Summary": "draft_migration_plan_summary",
    "AI Dataset/Freshness Summary": "draft_freshness_summary",
    "AI Simulation/Analytics Summary": "draft_simulation_report_summary",
    "AI Governance Summary": "draft_governance_review_summary",
    "AI Release Notes Draft": "draft_release_notes",
    "AI Operator Manual Draft Section": "draft_operator_manual_section",
}


def _context_snapshot(context_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    context_type = str(context_type or "generic")
    snapshot: dict[str, Any] = {"context_type": context_type, "payload": redact_data(payload), "app_version": APP_VERSION}
    try:
        if context_type in {"daily", "weekly", "tasks"}:
            from . import live_v3_tasks

            snapshot["task_summary"] = live_v3_tasks.task_summary()
            snapshot["tasks"] = live_v3_tasks.list_tasks(limit=20)
            snapshot["task_inbox"] = live_v3_tasks.list_inbox(limit=20)
        if context_type in {"platform", "diagnostics", "api"}:
            from . import platform_diagnostics, platform_api, platform_migrations

            snapshot["platform_summary"] = platform_diagnostics.platform_summary()
            snapshot["api_schema"] = platform_api.summarize_api_schema_consistency()
            snapshot["migration_summary"] = platform_migrations.migration_summary()
        if context_type in {"dataset", "freshness"}:
            from . import live_v3_datasets, live_v3_freshness

            snapshot["datasets_summary"] = live_v3_datasets.datasets_summary()
            snapshot["freshness_summary"] = live_v3_freshness.summary()
        if context_type in {"simulation", "analytics"}:
            from . import live_v3_simulation, live_v3_analytics

            snapshot["simulation_summary"] = live_v3_simulation.simulation_summary()
            snapshot["analytics_summary"] = live_v3_analytics.build_analytics_summary()
        if context_type == "governance":
            from . import live_governance

            snapshot["governance"] = live_governance.build_governance_workspace(limit=20)
    except Exception as exc:
        snapshot["unknown_unavailable_data"] = [f"Context snapshot failed safely: {str(exc)[:220]}"]
    return redact_data(snapshot)


def copilot_status() -> dict[str, Any]:
    settings_summary = ai_openai_client.openai_settings_summary()
    provider_summary = ai_providers.list_providers()
    prompt_summary = ai_prompt_governance.prompt_summary()
    schema_registry = ai_schemas.schema_registry()
    return safety_flags({
        "version": APP_VERSION,
        "title": "Multi-Provider AI Operator Copilot",
        "settings": settings_summary,
        "providers": provider_summary,
        "active_provider": provider_summary["active_provider"],
        "prompt_summary": prompt_summary,
        "schema_count": schema_registry["count"],
        "workflow_count": len(WORKFLOW_SCHEMAS),
        "review_packet_types": sorted(REVIEW_PACKET_WORKFLOWS),
        "api_disabled_by_default": settings_summary["openai_enable_api"] is False,
        "dry_run_only_by_default": provider_summary.get("active_provider") == "mock" or settings_summary["openai_dry_run_only"] is True,
        "no_network_by_default": provider_summary.get("openai", {}).get("openai_enable_api", False) is False and provider_summary.get("local_llm", {}).get("local_llm_enable", False) is False,
        "human_approval_required_by_default": settings_summary["openai_require_operator_approval"] is True,
        "tool_calling_disabled_by_default": settings_summary["openai_enable_tool_calling"] is False,
        "safety_statement": ai_schemas.AI_DRAFT_SAFETY_STATEMENT,
    })


def run_copilot_workflow(workflow_id: str, payload: dict[str, Any] | None = None, *, operator_approved: bool = False) -> dict[str, Any]:
    payload = payload or {}
    workflow_id = str(workflow_id or "summarize_daily_review_context")
    template_category, schema_name, data_category = WORKFLOW_SCHEMAS.get(workflow_id, WORKFLOW_SCHEMAS["summarize_daily_review_context"])
    template = ai_prompt_governance.get_prompt_template(template_category) or {}
    context = _context_snapshot(str(payload.get("context_type") or data_category), payload)
    instructions = template.get("prompt_preview") or ai_prompt_governance.SAFE_SYSTEM_INSTRUCTIONS
    result = ai_providers.request_structured_output(
        workflow_id=workflow_id,
        template_id=str(template.get("template_id") or template_category),
        instructions=instructions,
        input_data=context,
        schema_name=schema_name,
        input_category=data_category,
        operator_approved=operator_approved,
        model=payload.get("model"),
        provider_id=payload.get("provider"),
    )
    output = dict(result.get("output") or ai_schemas.default_payload(schema_name))
    output["workflow_id"] = workflow_id
    output["template_id"] = template.get("template_id") or template_category
    output["schema_name"] = schema_name
    return safety_flags({
        "ok": result.get("ok", False),
        "version": APP_VERSION,
        "workflow_id": workflow_id,
        "template_id": output["template_id"],
        "schema_name": schema_name,
        "mode": result.get("mode", "dry_run"),
        "provider": result.get("provider") or ai_providers.active_provider_id(),
        "model": result.get("model"),
        "draft": output,
        "prompt_hash": result.get("prompt_hash"),
        "response_hash": result.get("response_hash"),
        "audit_id": (result.get("audit") or {}).get("audit_id"),
        "api_blockers": result.get("api_blockers", []),
        "send_permission": result.get("send_permission", {}),
        "safety_statement": ai_schemas.AI_DRAFT_SAFETY_STATEMENT,
        "ai_outputs_are_drafts_only": True,
        "ai_cannot_place_or_cancel_orders": True,
        "ai_cannot_approve_trades": True,
        "ai_cannot_arm_live_trading": True,
        "ai_cannot_disable_safety_gates": True,
    })


def summarize_daily_review_context(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("summarize_daily_review_context", payload or {"context_type": "daily"})


def summarize_weekly_review_context(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("summarize_weekly_review_context", payload or {"context_type": "weekly"})


def summarize_platform_diagnostics(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("summarize_platform_diagnostics", payload or {"context_type": "platform"})


def explain_validation_failure(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("explain_validation_failure", payload or {"context_type": "validation"})


def explain_blockers(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("explain_blockers", payload or {"context_type": "blockers"})


def explain_unknown_unavailable_data(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("explain_unknown_unavailable_data", payload or {"context_type": "unknowns"})


def draft_task_suggestions(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_task_suggestions", payload or {"context_type": "tasks"})


def draft_source_preview_summary(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_source_preview_summary", payload or {"context_type": "source_preview"})


def draft_dataset_readiness_summary(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_dataset_readiness_summary", payload or {"context_type": "dataset"})


def draft_freshness_summary(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_freshness_summary", payload or {"context_type": "freshness"})


def draft_simulation_report_summary(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_simulation_report_summary", payload or {"context_type": "simulation"})


def draft_analytics_learning_summary(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_analytics_learning_summary", payload or {"context_type": "analytics"})


def draft_governance_review_summary(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_governance_review_summary", payload or {"context_type": "governance"})


def draft_migration_plan_summary(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_migration_plan_summary", payload or {"context_type": "migration_reports"})


def draft_release_notes(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_release_notes", payload or {"context_type": "docs"})


def draft_operator_manual_section(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_operator_manual_section", payload or {"context_type": "docs"})


def draft_api_schema_explanation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("draft_api_schema_explanation", payload or {"context_type": "api"})


def classify_task_priority_review_only(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("classify_task_priority_review_only", payload or {"context_type": "tasks"})


def classify_safety_label_review_only(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_copilot_workflow("classify_safety_label_review_only", payload or {"context_type": "tasks"})


def workflow_templates() -> list[dict[str, Any]]:
    return [
        {
            "workflow_id": workflow_id,
            "name": workflow_id.replace("_", " ").title(),
            "read_only": True,
            "mutates_trading_state": False,
            "description": f"AI-assisted draft workflow using {schema_name}; human review required.",
            "sections": ["Redacted Context", "Draft", "Warnings", "Blockers", "Unknowns", "Human Next Actions", "Safety"],
            "output_schema": schema_name,
            "template_category": template_category,
            "data_category": data_category,
            "markdown_ready": True,
            "output_is_draft": True,
            "order_submitted": False,
            "order_cancelled": False,
            "live_trading_armed": False,
            "safety_statement": ai_schemas.AI_DRAFT_SAFETY_STATEMENT,
        }
        for workflow_id, (template_category, schema_name, data_category) in sorted(WORKFLOW_SCHEMAS.items())
    ]


def workflow_output_markdown(result: dict[str, Any]) -> str:
    draft = result.get("draft", {})
    return "\n".join([
        f"# {str(result.get('workflow_id', 'AI Workflow')).replace('_', ' ').title()}",
        "",
        ai_schemas.AI_DRAFT_SAFETY_STATEMENT,
        "",
        f"Mode: `{result.get('mode', 'dry_run')}`",
        f"Schema: `{result.get('schema_name', 'AIReviewSummary')}`",
        f"Prompt hash: `{result.get('prompt_hash', '')}`",
        f"Response hash: `{result.get('response_hash', '')}`",
        "",
        "## Summary",
        str(draft.get("summary", "")),
        "",
        "## Warnings",
        "\n".join(f"- {item}" for item in draft.get("warnings", [])) or "- None.",
        "",
        "## Blockers",
        "\n".join(f"- {item}" for item in draft.get("blockers", [])) or "- None.",
        "",
        "## Unknown / Unavailable Data",
        "\n".join(f"- {item}" for item in draft.get("unknown_unavailable_data", [])) or "- None.",
        "",
        "## Human Next Actions",
        "\n".join(f"- {item}" for item in draft.get("suggested_human_next_actions", [])) or "- Review manually.",
        "",
    ]) + "\n"


def export_copilot_json() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "status": copilot_status(),
        "workflows": workflow_templates(),
        "prompts": ai_prompt_governance.list_prompt_templates()["items"],
        "schemas": ai_schemas.schema_registry()["items"],
        "safety_statement": ai_schemas.AI_DRAFT_SAFETY_STATEMENT,
    })


def export_copilot_markdown() -> str:
    data = export_copilot_json()
    lines = [f"# Multi-Provider AI Operator Copilot - {APP_VERSION}", "", ai_schemas.AI_DRAFT_SAFETY_STATEMENT, ""]
    lines.append("## Safe Defaults")
    for key in ["api_disabled_by_default", "dry_run_only_by_default", "no_network_by_default", "human_approval_required_by_default", "tool_calling_disabled_by_default"]:
        lines.append(f"- {key}: `{data['status'].get(key)}`")
    lines.extend(["", "## Workflows"])
    for workflow in data["workflows"]:
        lines.append(f"- `{workflow['workflow_id']}` -> `{workflow['output_schema']}`")
    return "\n".join(lines) + "\n"
