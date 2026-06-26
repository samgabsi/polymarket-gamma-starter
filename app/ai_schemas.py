from __future__ import annotations

from copy import deepcopy
from typing import Any

from .config import APP_VERSION
from .platform_safety import safety_flags

AI_DRAFT_SAFETY_STATEMENT = (
    "AI-generated draft for human review. Not financial advice. Not trade approval. "
    "Does not place or cancel orders."
)

BASE_REQUIRED_FIELDS = [
    "summary",
    "rationale",
    "warnings",
    "blockers",
    "unknown_unavailable_data",
    "limitations",
    "suggested_human_next_actions",
    "safety_statement",
    "no_financial_advice",
    "no_trade_approval",
    "no_live_mutation",
]

BASE_PROPERTIES: dict[str, Any] = {
    "summary": {"type": "string"},
    "rationale": {"type": "string"},
    "warnings": {"type": "array", "items": {"type": "string"}},
    "blockers": {"type": "array", "items": {"type": "string"}},
    "unknown_unavailable_data": {"type": "array", "items": {"type": "string"}},
    "limitations": {"type": "array", "items": {"type": "string"}},
    "suggested_human_next_actions": {"type": "array", "items": {"type": "string"}},
    "safety_statement": {"type": "string", "const": AI_DRAFT_SAFETY_STATEMENT},
    "no_financial_advice": {"type": "boolean", "const": True},
    "no_trade_approval": {"type": "boolean", "const": True},
    "no_live_mutation": {"type": "boolean", "const": True},
}


def _schema(name: str, title: str, extra_properties: dict[str, Any] | None = None, extra_required: list[str] | None = None) -> dict[str, Any]:
    properties = deepcopy(BASE_PROPERTIES)
    if extra_properties:
        properties.update(extra_properties)
    required = list(BASE_REQUIRED_FIELDS)
    if extra_required:
        required.extend(extra_required)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"polymarket-op-console.ai.{name}.{APP_VERSION}",
        "title": title,
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


SCHEMAS: dict[str, dict[str, Any]] = {
    "AIReviewSummary": _schema("AIReviewSummary", "AI Review Summary", {"review_type": {"type": "string"}, "status": {"type": "string"}}),
    "AITaskSuggestion": _schema(
        "AITaskSuggestion",
        "AI Task Suggestion",
        {
            "title": {"type": "string"},
            "suggested_task_type": {"type": "string"},
            "suggested_priority": {"type": "string", "enum": ["low", "medium", "high", "urgent", "critical"]},
            "suggested_due_window": {"type": "string"},
            "safety_label": {"type": "string"},
        },
        ["title", "suggested_task_type", "suggested_priority", "safety_label"],
    ),
    "AIBlockerExplanation": _schema("AIBlockerExplanation", "AI Blocker Explanation", {"blocked_object_id": {"type": "string"}}),
    "AIUnknownUnavailableExplanation": _schema("AIUnknownUnavailableExplanation", "AI Unknown/Unavailable Data Explanation", {"data_category": {"type": "string"}}),
    "AIDatasetReadinessSummary": _schema("AIDatasetReadinessSummary", "AI Dataset Readiness Summary", {"readiness_status": {"type": "string"}}),
    "AIFreshnessSummary": _schema("AIFreshnessSummary", "AI Freshness Summary", {"freshness_status": {"type": "string"}}),
    "AISimulationSummary": _schema("AISimulationSummary", "AI Simulation Summary", {"simulation_status": {"type": "string"}}),
    "AIAnalyticsSummary": _schema("AIAnalyticsSummary", "AI Analytics Summary", {"analytics_status": {"type": "string"}}),
    "AIGovernanceSummary": _schema("AIGovernanceSummary", "AI Governance Summary", {"governance_status": {"type": "string"}}),
    "AIMigrationPlanSummary": _schema("AIMigrationPlanSummary", "AI Migration Plan Summary", {"migration_status": {"type": "string"}}),
    "AIValidationFailureExplanation": _schema("AIValidationFailureExplanation", "AI Validation Failure Explanation", {"failure_id": {"type": "string"}}),
    "AIReleaseNotesDraft": _schema("AIReleaseNotesDraft", "AI Release Notes Draft", {"draft_markdown": {"type": "string"}}),
    "AIOperatorManualSectionDraft": _schema("AIOperatorManualSectionDraft", "AI Operator Manual Section Draft", {"section_markdown": {"type": "string"}}),
    "AIChatGPTConnectorToolDescription": _schema(
        "AIChatGPTConnectorToolDescription",
        "AI ChatGPT Connector Tool Description",
        {
            "tool_name": {"type": "string"},
            "read_only": {"type": "boolean", "const": True},
            "auth_required": {"type": "boolean", "const": True},
            "forbidden_actions": {"type": "array", "items": {"type": "string"}},
        },
        ["tool_name", "read_only", "auth_required", "forbidden_actions"],
    ),
}


def schema_for(schema_name: str) -> dict[str, Any]:
    return deepcopy(SCHEMAS.get(schema_name, SCHEMAS["AIReviewSummary"]))


def schema_registry() -> dict[str, Any]:
    rows = [
        {
            "schema_id": name,
            "app_version": APP_VERSION,
            "title": schema["title"],
            "required_fields": schema["required"],
            "contains_no_live_mutation": "no_live_mutation" in schema["required"],
            "contains_no_trade_approval": "no_trade_approval" in schema["required"],
            "contains_no_financial_advice": "no_financial_advice" in schema["required"],
            "safety_statement": AI_DRAFT_SAFETY_STATEMENT,
            "secret_values_returned": False,
        }
        for name, schema in sorted(SCHEMAS.items())
    ]
    return safety_flags({
        "version": APP_VERSION,
        "count": len(rows),
        "items": rows,
        "schemas": deepcopy(SCHEMAS),
        "structured_outputs_enabled_by_default": True,
        "schema_outputs_are_drafts_only": True,
    })


def default_payload(schema_name: str, *, summary: str = "", rationale: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "summary": summary or f"Dry-run {schema_name} draft generated from redacted local context.",
        "rationale": rationale or "Generated deterministically because OpenAI API calls are disabled or dry-run mode is active.",
        "warnings": ["Review source context manually before acting."],
        "blockers": [],
        "unknown_unavailable_data": ["Real model output is unavailable in dry-run mode."],
        "limitations": ["Dry-run output is deterministic test data and may omit nuanced context."],
        "suggested_human_next_actions": ["Review the draft.", "Verify blockers, warnings, and unknown data.", "Accept any task suggestion explicitly before task creation."],
        "safety_statement": AI_DRAFT_SAFETY_STATEMENT,
        "no_financial_advice": True,
        "no_trade_approval": True,
        "no_live_mutation": True,
    }
    if schema_name == "AITaskSuggestion":
        payload.update({
            "title": "Review AI-generated draft suggestion",
            "suggested_task_type": "review",
            "suggested_priority": "medium",
            "suggested_due_window": "operator-defined",
            "safety_label": "review-only",
        })
    elif schema_name == "AIChatGPTConnectorToolDescription":
        payload.update({
            "tool_name": "draft_review_summary",
            "read_only": True,
            "auth_required": True,
            "forbidden_actions": ["place_order", "cancel_order", "approve_trade", "arm_live_trading"],
        })
    elif schema_name == "AIReleaseNotesDraft":
        payload["draft_markdown"] = "# AI-generated release notes draft\n\nReview manually before publishing."
    elif schema_name == "AIOperatorManualSectionDraft":
        payload["section_markdown"] = "## AI-generated operator manual draft\n\nReview manually before publishing."
    else:
        optional_defaults = {
            "review_type": "operator_review",
            "status": "draft",
            "blocked_object_id": "",
            "data_category": "",
            "readiness_status": "needs_review",
            "freshness_status": "needs_review",
            "simulation_status": "draft",
            "analytics_status": "draft",
            "governance_status": "draft",
            "migration_status": "dry_run_only",
            "failure_id": "",
        }
        for key, value in optional_defaults.items():
            if key in schema_for(schema_name).get("properties", {}):
                payload[key] = value
    return payload


def validate_payload(schema_name: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    schema = schema_for(schema_name)
    value = payload or {}
    missing = [field for field in schema.get("required", []) if field not in value]
    unsafe = []
    if value.get("no_live_mutation") is not True:
        unsafe.append("no_live_mutation must be true")
    if value.get("no_trade_approval") is not True:
        unsafe.append("no_trade_approval must be true")
    if value.get("no_financial_advice") is not True:
        unsafe.append("no_financial_advice must be true")
    lowered = str(value).lower()
    imperative_markers = [
        "place an order",
        "place a live order",
        "submit order",
        "submit a live order",
        "cancel an order",
        "approve trade",
        "arm live trading",
        "disable kill switch",
    ]
    negated_markers = ["do not place", "does not place", "cannot place", "do not cancel", "does not cancel", "cannot cancel"]
    if any(marker in lowered for marker in imperative_markers) and not any(marker in lowered for marker in negated_markers):
        unsafe.append("payload must not instruct order placement/cancellation")
    ok = not missing and not unsafe
    return safety_flags({
        "ok": ok,
        "status": "pass" if ok else "fail",
        "schema_name": schema_name,
        "missing_required_fields": missing,
        "unsafe_findings": unsafe,
    })
