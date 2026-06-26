from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import APP_VERSION
from .platform_exports import export_manifest, to_markdown
from .platform_safety import NO_LIVE_MUTATION_STATEMENT, STANDARD_SAFETY_STATEMENT, redact_data, safety_flags

PACKAGE_NAME = "Polymarket OP Console"
PACKAGE_SLUG = "polymarket-op-console"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ApiFamily:
    family_id: str
    title: str
    route_prefixes: list[str]
    module_owner: str
    safety_class: str
    normalized_response: bool
    compatibility_note: str
    docs_link: str


@dataclass(frozen=True)
class SchemaObject:
    schema_id: str
    title: str
    owner_module: str
    fields: list[str]
    safety_note: str


@dataclass(frozen=True)
class ResponseEnvelopeSpec:
    envelope_id: str
    title: str
    required_fields: list[str]
    optional_fields: list[str]
    backward_compatibility_rule: str


REQUIRED_ENVELOPE_FIELDS = [
    "success",
    "app_version",
    "generated_at",
    "module",
    "action",
    "warnings",
    "blockers",
    "unknown_unavailable_data",
    "limitations",
    "safety_statement",
]

OPTIONAL_ENVELOPE_FIELDS = [
    "package_name",
    "package_slug",
    "data",
    "items",
    "summary",
    "request_id",
    "correlation_id",
    "pagination",
    "filters",
    "export_manifest",
    "no_live_mutation_statement",
]

API_FAMILIES = [
    ApiFamily("platform", "Platform APIs", ["/api/v3/platform"], "platform_*", "informational", True, "v4.3 keeps platform APIs envelope-normalized while extracting them to app/routers/platform.py.", "/docs/V4_API_CONTRACTS_GUIDE_v4.7.0-real.md"),
    ApiFamily("ai", "AI Copilot APIs", ["/api/v3/ai"], "ai_*", "review-only", True, "AI APIs are draft-only, dry-run-by-default, redacted, and extracted to app/routers/ai.py.", "/docs/V4_OPENAI_INTEGRATION_GUIDE_v4.7.0-real.md"),
    ApiFamily("ai_news_odds", "AI News Odds Adjustment APIs", ["/api/v3/ai/news-odds"], "ai_news_odds", "review-only", False, "AI News Odds APIs produce source-weighted draft fair-probability adjustments; they do not approve, submit, cancel, or arm live trading.", "/docs/V4_AI_NEWS_ODDS_ADJUSTMENT_ENGINE_GUIDE_v4.7.0-real.md"),
    ApiFamily("cross_market_arbitrage", "Cross-Market Arbitrage APIs", ["/api/v3/arbitrage"], "cross_market_arbitrage", "review-only", False, "Arbitrage APIs normalize venue snapshots, score equivalence, label data state, and store review-only scan/candidate records without live mutation.", "/docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.15.0-real.md"),
    ApiFamily("v3_core", "V3 Core UX APIs", ["/api/v3/ux"], "live_v3", "informational", False, "Small low-risk v3 UX endpoints are extracted to app/routers/v3_core.py and remain backward compatible.", "/docs/V4_ROUTER_ARCHITECTURE_GUIDE_v4.7.0-real.md"),
    ApiFamily("cockpit", "Cockpit APIs", ["/api/v3/cockpit"], "live_v3_cockpit", "review-only", False, "Existing cockpit response fields remain backward compatible.", "/docs/V3_OPERATOR_COCKPIT_GUIDE_v4.7.0-real.md"),
    ApiFamily("workspace", "Guided Workspace APIs", ["/api/v3/workspace"], "live_v3_workspace", "review-only", False, "Guided completion is not trade approval.", "/docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md"),
    ApiFamily("tasks", "Task APIs", ["/api/v3/tasks"], "live_v3_tasks", "review-only", False, "Task completion is workflow state only.", "/docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md"),
    ApiFamily("datasets", "Dataset APIs", ["/api/v3/datasets"], "live_v3_datasets", "read-only-action", False, "Dataset collection remains read-only/demo-gated where applicable.", "/docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md"),
    ApiFamily("freshness", "Freshness APIs", ["/api/v3/freshness"], "live_v3_freshness", "read-only-action", False, "Freshness jobs do not submit or cancel orders.", "/docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md"),
    ApiFamily("simulation", "Simulation APIs", ["/api/v3/simulation"], "live_v3_simulation", "review-only", False, "Simulation outputs are descriptive and not trading instructions.", "/docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md"),
    ApiFamily("analytics", "Analytics APIs", ["/api/v3/analytics"], "live_v3_analytics", "informational", False, "Analytics are descriptive and do not claim profitability.", "/docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md"),
    ApiFamily("search_graph_workflows", "Search, Graph, and Workflow APIs", ["/api/v3/search", "/api/v3/graph", "/api/v3/workflows"], "live_v3", "informational", False, "Local indexes and graph/workflow outputs are not financial advice.", "/docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md"),
    ApiFamily("live_control", "Live-Control Adjacent APIs", ["/api/live", "/api/v2/live", "/v2-live"], "live_*", "gated-live-action-reference", False, "Existing backend gates remain authoritative and fail closed.", "/docs/LIVE_TRADING_V2.md"),
]

SCHEMA_OBJECTS = [
    SchemaObject("api_response_envelope", "Shared API Response Envelope", "platform_api", REQUIRED_ENVELOPE_FIELDS + OPTIONAL_ENVELOPE_FIELDS, "Schemas document responses; they do not bypass backend gates."),
    SchemaObject("ai_review_summary", "AI Review Summary", "ai_schemas", ["summary", "rationale", "warnings", "blockers", "unknown_unavailable_data", "limitations", "suggested_human_next_actions", "safety_statement", "no_financial_advice", "no_trade_approval", "no_live_mutation"], "AI schemas are structured draft outputs only."),
    SchemaObject("ai_news_odds_adjustment", "AI News Odds Adjustment Packet", "ai_news_odds", ["adjustment_id", "source_weights", "claim_clusters", "base_fair_yes", "adjusted_fair_yes", "review_only", "does_not_place_orders", "does_not_cancel_orders"], "News odds packets adjust internal draft fair probabilities only and are not trade approvals."),
    SchemaObject("cross_market_arbitrage_opportunity", "Cross-Market Arbitrage Opportunity", "cross_market_arbitrage", ["opportunity_id", "venue_pair", "legs", "equivalence", "gross_arbitrage_margin_pct", "estimated_fees_pct", "estimated_slippage_pct", "net_arbitrage_margin_pct", "classification", "requires_manual_approval", "data_state", "scanner_status", "persisted"], "Arbitrage opportunities are candidates only, not guaranteed profits or executable orders."),
    SchemaObject("ai_task_suggestion", "AI Task Suggestion", "ai_suggestions", ["suggestion_id", "human_status", "accepted_task_id", "safety_label", "prompt_hash", "response_hash", "no_live_mutation"], "AI suggestions require explicit human acceptance before creating local tasks."),
    SchemaObject("ai_audit_record", "AI Audit Record", "ai_openai_client", ["audit_id", "workflow_id", "mode", "input_category", "prompt_hash", "response_hash", "no_secret_values"], "AI audit records store hashes and metadata, not raw secrets."),
    SchemaObject("chatgpt_connector_blueprint", "ChatGPT Connector Blueprint", "ai_suggestions", ["allowed_read_only_tools", "forbidden_tools", "read_only", "auth_required", "mcp_server_enabled"], "Connector blueprint is read-only, auth-required, and disabled by default."),
    SchemaObject("api_family", "API Family Record", "platform_api", ["family_id", "title", "route_prefixes", "module_owner", "safety_class", "normalized_response"], "Route families are inventory records only."),
    SchemaObject("route_boundary_record", "Route/Module Boundary Record", "platform_routes", ["path", "methods", "family", "owner_module", "safety_class", "docs_link"], "Route inventories do not call handlers."),
    SchemaObject("runtime_namespace_record", "Runtime Namespace Record", "platform_storage", ["namespace", "path", "expected_format", "introduced_in", "package_excluded", "may_contain_sensitive_data"], "Storage records are compatibility metadata."),
    SchemaObject("migration_plan", "Runtime Migration Plan", "platform_migrations", ["plan_id", "steps", "classification", "backup_recommended", "destructive_action_prohibited"], "Migration plans are non-destructive recommendations only."),
    SchemaObject("plugin_manifest", "Plugin Manifest Compatibility Record", "platform_plugins", ["plugin_id", "capabilities", "no_live_mutation", "no_secret_access", "no_network_by_default"], "Plugin manifests are metadata only and do not execute code."),
    SchemaObject("export_manifest", "Platform Export Manifest", "platform_exports", ["generated_at", "app_version", "export_type", "included_object_ids", "unknown_unavailable_data", "limitations"], "Exports are redacted and secret-safe."),
]


def api_response_envelope(
    module: str,
    action: str,
    *,
    success: bool = True,
    data: Any | None = None,
    items: list[Any] | None = None,
    summary: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
    unknown_unavailable_data: list[str] | None = None,
    limitations: list[str] | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
    pagination: dict[str, Any] | None = None,
    filters: dict[str, Any] | None = None,
    export_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = {
        "success": bool(success),
        "app_version": APP_VERSION,
        "generated_at": _now(),
        "package_name": PACKAGE_NAME,
        "package_slug": PACKAGE_SLUG,
        "module": str(module or "unknown"),
        "action": str(action or "unknown"),
        "data": redact_data(data or {}),
        "items": redact_data(items or []),
        "summary": redact_data(summary or {}),
        "warnings": warnings or [],
        "blockers": blockers or [],
        "unknown_unavailable_data": unknown_unavailable_data or ["Runtime data may be absent in a clean package."],
        "limitations": limitations or ["Schema inventory reflects local registered helpers and route metadata only."],
        "safety_statement": STANDARD_SAFETY_STATEMENT,
        "no_live_mutation_statement": NO_LIVE_MUTATION_STATEMENT,
        "request_id": request_id or f"req_{uuid4().hex[:12]}",
        "correlation_id": correlation_id or f"corr_{uuid4().hex[:12]}",
        "pagination": pagination or {"limit": None, "cursor": None, "has_more": False},
        "filters": filters or {},
        "export_manifest": redact_data(export_manifest or {}),
    }
    return safety_flags(envelope)


def list_api_families() -> dict[str, Any]:
    rows = [asdict(item) for item in API_FAMILIES]
    return api_response_envelope(
        "platform_api",
        "list_api_families",
        items=rows,
        summary={"count": len(rows), "normalized_families": sum(1 for row in rows if row["normalized_response"])},
        unknown_unavailable_data=["Route-level OpenAPI schema extraction is not performed on page load."],
    )


def list_response_envelopes() -> dict[str, Any]:
    specs = [
        ResponseEnvelopeSpec(
            "standard_v4_2_response_envelope",
            "Standard v4.3 platform response envelope",
            REQUIRED_ENVELOPE_FIELDS,
            OPTIONAL_ENVELOPE_FIELDS,
            "Additive only: existing endpoint-specific fields should be preserved when adopting the envelope.",
        )
    ]
    return api_response_envelope(
        "platform_api",
        "list_response_envelopes",
        items=[asdict(item) for item in specs],
        summary={"count": len(specs), "required_field_count": len(REQUIRED_ENVELOPE_FIELDS), "optional_field_count": len(OPTIONAL_ENVELOPE_FIELDS)},
    )


def list_known_schema_objects() -> dict[str, Any]:
    rows = [asdict(item) for item in SCHEMA_OBJECTS]
    return api_response_envelope(
        "platform_api",
        "list_known_schema_objects",
        items=rows,
        summary={"count": len(rows), "owner_modules": sorted({row["owner_module"] for row in rows})},
    )


def validate_envelope_shape(envelope: dict[str, Any] | None) -> dict[str, Any]:
    value = envelope or {}
    missing = [field for field in REQUIRED_ENVELOPE_FIELDS if field not in value]
    type_problems = []
    if "success" in value and not isinstance(value["success"], bool):
        type_problems.append("success must be boolean")
    for field in ["warnings", "blockers", "unknown_unavailable_data", "limitations"]:
        if field in value and not isinstance(value[field], list):
            type_problems.append(f"{field} must be a list")
    unsafe_flags = []
    if value.get("order_submitted") is True:
        unsafe_flags.append("order_submitted unexpectedly true")
    if value.get("order_cancelled") is True:
        unsafe_flags.append("order_cancelled unexpectedly true")
    if value.get("live_trading_armed") is True:
        unsafe_flags.append("live_trading_armed unexpectedly true")
    ok = not missing and not type_problems and not unsafe_flags
    return safety_flags({
        "ok": ok,
        "status": "pass" if ok else "fail",
        "missing_required_fields": missing,
        "type_problems": type_problems,
        "unsafe_flags": unsafe_flags,
        "validated_field_count": len(value.keys()),
    })


def summarize_api_schema_consistency(app: Any | None = None) -> dict[str, Any]:
    from .platform_routes import route_inventory

    routes = route_inventory(app)
    families = [asdict(item) for item in API_FAMILIES]
    route_family_counts = routes.get("families", {})
    normalized = [family for family in families if family["normalized_response"]]
    api_route_items = [item for item in routes.get("items", []) if str(item.get("path", "")).startswith("/api/")]
    normalized_prefixes = [prefix for family in normalized for prefix in family["route_prefixes"]]
    unnormalized = [
        {"path": item.get("path"), "family": item.get("family"), "owner_module": item.get("owner_module"), "reason": "family not yet adopted into shared platform envelope"}
        for item in api_route_items
        if not any(str(item.get("path", "")).startswith(prefix) for prefix in normalized_prefixes)
    ]
    route_family_schema_counts = {
        family["family_id"]: {
            "route_count": sum(route_family_counts.get(key, 0) for key in route_family_counts if key.endswith(family["family_id"]) or key == family["family_id"] or key == f"api_v3_{family['family_id']}"),
            "normalized_response": family["normalized_response"],
        }
        for family in families
    }
    return api_response_envelope(
        "platform_api",
        "summarize_api_schema_consistency",
        data={
            "api_families": families,
            "route_family_counts": route_family_counts,
            "route_family_schema_counts": route_family_schema_counts,
            "envelope_adoption_summary": {
                "normalized_family_ids": [family["family_id"] for family in normalized],
                "normalized_family_count": len(normalized),
                "unnormalized_family_count": len(families) - len(normalized),
                "api_route_count": len(api_route_items),
                "unnormalized_endpoint_count": len(unnormalized),
            },
            "unnormalized_endpoint_list": unnormalized[:75],
            "recommended_next_normalization_targets": [
                "api_v3_core",
                "api_v3_cockpit",
                "api_v3_workspace",
                "api_v3_tasks",
                "api_v3_datasets",
            ],
            "response_envelope": list_response_envelopes()["items"][0],
            "schema_objects": [asdict(item) for item in SCHEMA_OBJECTS],
        },
        summary={
            "api_family_count": len(families),
            "schema_object_count": len(SCHEMA_OBJECTS),
            "route_count": routes.get("count", 0),
            "normalized_family_count": len(normalized),
            "backward_compatible": True,
        },
        warnings=["Only v4.3 platform schema helpers are fully envelope-normalized in this release; other families preserve legacy response shapes."],
        unknown_unavailable_data=["Endpoint body models are not exhaustively inferred from FastAPI internals."],
    )


def export_schema_inventory_json(app: Any | None = None) -> dict[str, Any]:
    inventory = summarize_api_schema_consistency(app)
    return export_manifest(
        "api_schema_inventory_json",
        "v4.3 API Schema Inventory",
        included_object_ids=["api_families", "response_envelope", "schema_objects", "route_family_counts", "route_family_schema_counts", "envelope_adoption_summary", "unnormalized_endpoint_list"],
        related_object_ids=["platform_routes", "platform_storage", "platform_migrations", "platform_plugins"],
        unknown_unavailable_data=inventory.get("unknown_unavailable_data", []),
        payload=inventory,
    )


def export_schema_inventory_markdown(app: Any | None = None) -> str:
    return to_markdown(export_schema_inventory_json(app))
