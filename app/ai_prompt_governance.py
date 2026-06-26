from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from .ai_schemas import AI_DRAFT_SAFETY_STATEMENT, SCHEMAS
from .config import APP_VERSION
from .platform_safety import redact_text, safety_flags, secret_scan

SAFE_SYSTEM_INSTRUCTIONS = (
    "You are an operator copilot for Polymarket OP Console. Produce a draft for human review only. "
    "Do not provide financial advice. Do not approve trades. Do not place or cancel orders. "
    "Do not arm live trading. Do not disable safety gates. Be explicit about blockers, warnings, "
    "unknown data, unavailable data, stale data, and limitations."
)

PROHIBITED_DATA_CATEGORIES = [
    "private_keys",
    "api_keys",
    "wallet_secrets",
    "auth_headers",
    "session_cookies",
    "passwords",
    "database_files",
    "raw_runtime_files",
    "sensitive_account_data",
]


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    template_version: str
    category: str
    title: str
    prompt: str
    allowed_data_categories: list[str]
    prohibited_data_categories: list[str]
    required_redaction: bool
    required_safety_statements: list[str]
    output_schema_reference: str
    model_preference: str
    dry_run_supported: bool
    human_approval_required: bool
    risk_classification: str

    def to_record(self) -> dict[str, Any]:
        prompt_preview = redact_text(self.prompt[:900])
        return {
            **asdict(self),
            "app_version": APP_VERSION,
            "provider_compatibility": ["mock", "openai", "ollama", "local_openai_compatible", "llama_cpp", "lm_studio"],
            "prompt_hash": prompt_hash(self.prompt),
            "prompt_preview": prompt_preview,
            "contains_secret_values": not secret_scan(self.prompt)["ok"],
            "secret_values_returned": False,
            "no_live_mutation": True,
            "no_trade_approval": True,
            "no_financial_advice": True,
            "safety_statement": AI_DRAFT_SAFETY_STATEMENT,
        }


def prompt_hash(text: str) -> str:
    return hashlib.sha256(redact_text(text).encode("utf-8")).hexdigest()


def _template(category: str, schema: str, title: str, allowed: list[str] | None = None, model: str = "review") -> PromptTemplate:
    allowed = allowed or ["redacted_local_summary"]
    prompt = "\n".join([
        SAFE_SYSTEM_INSTRUCTIONS,
        f"Workflow category: {category}.",
        f"Task: {title}.",
        "AI output is a draft. It is not financial advice, not trade approval, and must not cause live mutation.",
        "Do not invent data. List unknowns, source limitations, contradictions, assumptions, blockers, and missing information.",
        "Require citations or source metadata whenever sources are used, and separate model opinion from deterministic data.",
        f"Return JSON compatible with {schema}.",
        f"Every response must include this exact safety statement: {AI_DRAFT_SAFETY_STATEMENT}",
    ])
    return PromptTemplate(
        template_id=f"ai_{category}_v1",
        template_version="1.0",
        category=category,
        title=title,
        prompt=prompt,
        allowed_data_categories=allowed,
        prohibited_data_categories=PROHIBITED_DATA_CATEGORIES,
        required_redaction=True,
        required_safety_statements=[AI_DRAFT_SAFETY_STATEMENT],
        output_schema_reference=schema,
        model_preference=model,
        dry_run_supported=True,
        human_approval_required=True,
        risk_classification="review-only",
    )


PROMPT_TEMPLATES: tuple[PromptTemplate, ...] = (
    _template("daily_review_summary", "AIReviewSummary", "Summarize the daily operator review context.", ["tasks", "workspace", "freshness", "datasets", "analytics"]),
    _template("weekly_review_summary", "AIReviewSummary", "Summarize the weekly operator review context.", ["tasks", "workspace", "analytics", "governance"]),
    _template("task_suggestion", "AITaskSuggestion", "Draft task suggestions for explicit human acceptance.", ["tasks", "freshness", "datasets", "monitoring"]),
    _template("source_preview_summary", "AIReviewSummary", "Summarize source-preview context without inventing missing facts.", ["workspace", "research"]),
    _template("dataset_readiness_summary", "AIDatasetReadinessSummary", "Summarize dataset readiness blockers and unknowns.", ["datasets", "freshness"]),
    _template("freshness_summary", "AIFreshnessSummary", "Summarize stale data, collection-readiness, and freshness findings.", ["freshness", "datasets"]),
    _template("simulation_summary", "AISimulationSummary", "Summarize simulation/replay outputs as descriptive process review.", ["simulation", "datasets"]),
    _template("analytics_summary", "AIAnalyticsSummary", "Summarize analytics warnings and process-learning items.", ["analytics", "tasks"]),
    _template("governance_summary", "AIGovernanceSummary", "Summarize governance items, blockers, and review gaps.", ["governance", "tasks"]),
    _template("platform_diagnostics_summary", "AIReviewSummary", "Summarize platform diagnostics and route/schema warnings.", ["platform_diagnostics"]),
    _template("migration_plan_summary", "AIMigrationPlanSummary", "Summarize non-destructive runtime migration plan.", ["migration_reports"]),
    _template("validation_failure_explanation", "AIValidationFailureExplanation", "Explain validation failure context and next human checks.", ["validation"]),
    _template("release_notes_draft", "AIReleaseNotesDraft", "Draft release notes for human editing.", ["docs", "platform_diagnostics"]),
    _template("operator_manual_section_draft", "AIOperatorManualSectionDraft", "Draft operator manual section for human editing.", ["docs", "route_inventory"]),
    _template("api_schema_explanation", "AIReviewSummary", "Explain API schema and route inventory for operators.", ["platform_diagnostics", "route_inventory"]),
    _template("chatgpt_connector_tool_description", "AIChatGPTConnectorToolDescription", "Describe read-only ChatGPT connector tools.", ["connector_blueprint"]),
    _template("edge_research_packet", "AIEdgeResearchPacket", "Draft an evidence-backed AI Edge Research packet with citations, contradictions, missing information, probability draft, and calibration hooks.", ["edge_evidence", "redacted_local_summary"]),
    _template("evidence_source_summary", "AIEvidenceSource", "Summarize supplied evidence sources with citation metadata, quality, recency, relevance, and limitations.", ["edge_evidence"]),
    _template("contradiction_analysis", "AIContradictionNote", "Compare supplied evidence and identify contradiction notes for human review.", ["edge_evidence"]),
    _template("missing_information_analysis", "AIMissingInformationNote", "Identify missing information, unknowns, unavailable data, and source gaps in an edge research packet.", ["edge_evidence"]),
    _template("market_implied_comparison", "AIMarketImpliedComparison", "Compare an AI draft probability with a supplied market-implied probability as research-only context.", ["edge_evidence", "market_context"]),
    _template("edge_web_search_review_plan", "AIEdgeResearchPacket", "Draft a web-search review plan without making a network call unless every explicit web-search gate is enabled.", ["edge_evidence", "redacted_local_summary"]),
    _template("edge_calibration_summary", "AIEdgeCalibrationRecord", "Summarize AI Edge draft probability calibration records as research-only outcome tracking.", ["edge_calibration"]),
    _template("outcome_review", "AIEdgeOutcomeRecord", "Review an entered outcome for a prior AI Edge research packet without approving trades or future decisions.", ["edge_calibration"]),
    _template("edge_research_export_summary", "AIResearchExport", "Summarize AI Edge research exports with safety notices, citations, and limitations.", ["edge_evidence", "edge_calibration"]),
    _template("news_search_planning", "AIReviewSummary", "Plan market-specific news searches for source-backed evidence without including secrets or trade instructions.", ["market_context", "redacted_operator_notes"]),
    _template("news_source_summarization", "AIReviewSummary", "Summarize news sources with citations, dates, source type, facts, speculation, and uncertainty.", ["news_evidence"]),
    _template("news_claim_extraction", "AIReviewSummary", "Extract market-relevant claims, stance, relevance, and source metadata from supplied news evidence.", ["news_evidence", "market_context"]),
    _template("news_contradiction_detection", "AIReviewSummary", "Detect denials, disputes, contradictions, rumors, stale evidence, and source limitations in news evidence.", ["news_evidence"]),
    _template("news_market_relevance_assessment", "AIReviewSummary", "Assess whether supplied evidence is relevant to market resolution criteria without inventing facts.", ["news_evidence", "market_context"]),
    _template("news_event_impact_estimation", "AIReviewSummary", "Estimate event direction and magnitude as draft research; deterministic code must apply final caps and validation.", ["news_evidence", "market_context"]),
    _template("news_uncertainty_explanation", "AIReviewSummary", "Explain confidence, uncertainty, source weighting, corroboration limits, and contradictions for operators.", ["news_evidence", "source_weights"]),
    _template("news_operator_summary", "AIReviewSummary", "Summarize before/after fair probability, before/after edge, evidence, warnings, and review-only safety boundaries.", ["news_evidence", "market_context", "source_weights"]),
)


def list_prompt_templates() -> dict[str, Any]:
    rows = [template.to_record() for template in PROMPT_TEMPLATES]
    return safety_flags({
        "version": APP_VERSION,
        "count": len(rows),
        "items": rows,
        "prompt_governance_enabled": True,
        "redaction_required_by_default": True,
        "human_approval_required_by_default": True,
        "tool_calling_enabled_by_default": False,
        "remote_mcp_enabled_by_default": False,
        "secret_values_returned": False,
    })


def get_prompt_template(template_id_or_category: str) -> dict[str, Any] | None:
    needle = str(template_id_or_category or "").strip()
    for template in PROMPT_TEMPLATES:
        if needle in {template.template_id, template.category}:
            return template.to_record()
    return None


def prompt_summary() -> dict[str, Any]:
    rows = list_prompt_templates()["items"]
    return safety_flags({
        "version": APP_VERSION,
        "template_count": len(rows),
        "schema_count": len(SCHEMAS),
        "categories": [row["category"] for row in rows],
        "all_require_redaction": all(row["required_redaction"] for row in rows),
        "all_require_human_approval": all(row["human_approval_required"] for row in rows),
        "all_include_safety_statement": all(AI_DRAFT_SAFETY_STATEMENT in row.get("required_safety_statements", []) for row in rows),
        "prohibited_data_categories": PROHIBITED_DATA_CATEGORIES,
    })


def build_prompt_preview(template_id_or_category: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    template = get_prompt_template(template_id_or_category)
    if not template:
        return safety_flags({"ok": False, "error": "prompt_template_not_found", "template_id": redact_text(template_id_or_category)})
    context_summary = redact_text(str(context or {}))[:1800]
    full = f"{template['prompt_preview']}\n\nRedacted context summary:\n{context_summary}"
    scan = secret_scan(full)
    return safety_flags({
        "ok": scan["ok"],
        "template_id": template["template_id"],
        "category": template["category"],
        "prompt_hash": prompt_hash(full),
        "prompt_preview": redact_text(full),
        "secret_scan": scan,
        "send_allowed_without_operator_approval": False,
        "safety_statement": AI_DRAFT_SAFETY_STATEMENT,
    })


def export_prompt_registry_json() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "export_type": "ai_prompt_registry",
        "summary": prompt_summary(),
        "items": list_prompt_templates()["items"],
        "raw_prompts_included": False,
        "prompt_hashes_only_for_audit": True,
    })


def export_prompt_registry_markdown() -> str:
    registry = export_prompt_registry_json()
    lines = [
        f"# AI Prompt Governance Registry - {APP_VERSION}",
        "",
        AI_DRAFT_SAFETY_STATEMENT,
        "",
        "Raw prompts and secrets are not included in this export.",
        "",
    ]
    for item in registry["items"]:
        lines.append(f"## {item['title']}")
        lines.append(f"- Template: `{item['template_id']}` `{item['template_version']}`")
        lines.append(f"- Category: `{item['category']}`")
        lines.append(f"- Schema: `{item['output_schema_reference']}`")
        lines.append(f"- Redaction required: `{item['required_redaction']}`")
        lines.append(f"- Human approval required: `{item['human_approval_required']}`")
        lines.append(f"- Prompt hash: `{item['prompt_hash']}`")
        lines.append("")
    return "\n".join(lines)
