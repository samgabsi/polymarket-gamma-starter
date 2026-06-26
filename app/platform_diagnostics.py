from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_VERSION, PROJECT_ROOT
from . import platform_api, platform_migrations
from .platform_exports import export_manifest, to_markdown
from .platform_plugins import load_plugin_manifests, plugin_summary
from .platform_route_registry import route_ownership_registry
from .platform_routes import route_inventory, module_inventory
from .platform_safety import safety_flags, safety_statements
from .platform_storage import storage_summary
from .platform_version import version_metadata

PLATFORM_SETTINGS = {
    "diagnostics_run_on_startup": False,
    "platform_exports_run_on_page_load": False,
    "plugin_manifests_execute_code": False,
    "network_diagnostics_enabled_by_default": False,
    "show_unknown_unavailable_data": True,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def health_summary(app: Any | None = None) -> dict[str, Any]:
    routes = route_inventory(app)
    registry = route_ownership_registry(app)
    plugins = plugin_summary()
    storage = storage_summary()
    schema = platform_api.summarize_api_schema_consistency(app)
    migrations = platform_migrations.migration_summary()
    return safety_flags({
        "version": APP_VERSION,
        "generated_at": _now(),
        "overall_status": "pass" if plugins.get("invalid_plugin_count", 0) == 0 else "warning",
        "route_count": routes.get("count", 0),
        "route_families": routes.get("families", {}),
        "route_registry_family_count": registry.get("count", 0),
        "extracted_router_modules": registry.get("extracted_router_modules", []),
        "extracted_router_count": len(registry.get("extracted_router_modules", [])),
        "plugin_count": plugins.get("plugin_count", 0),
        "invalid_plugin_count": plugins.get("invalid_plugin_count", 0),
        "storage_namespace_count": storage.get("count", 0),
        "api_schema_family_count": schema.get("summary", {}).get("api_family_count", 0),
        "schema_object_count": schema.get("summary", {}).get("schema_object_count", 0),
        "migration_step_count": migrations.get("step_count", 0),
        "migration_destructive_actions_prohibited": migrations.get("destructive_actions_prohibited", True),
        "api_contract_status": "metadata_contract_tests_available",
        "generated_manual_status": generated_manual_status(),
        "validation_capabilities": ["version", "routers", "route-registry", "api-contracts", "generated-manual", "routes", "plugins", "storage", "schema", "migrations", "exports", "ai-safe-defaults", "ai-redaction", "chatgpt-blueprint", "secret-safety", "no-live-mutation"],
        "known_unknown_unavailable_data": ["Runtime records may be absent in a clean package.", "Authenticated route status is summarized from path conventions only."],
    })


def generated_manual_status() -> dict[str, Any]:
    manual = PROJECT_ROOT / "docs" / "generated" / f"OPERATOR_MANUAL_v{APP_VERSION}.md"
    return safety_flags({
        "path": f"docs/generated/OPERATOR_MANUAL_v{APP_VERSION}.md",
        "exists": manual.exists(),
        "format": "markdown",
        "pdf_generated": False,
        "pdf_export_options": ["pandoc", "print-to-pdf from GitHub-rendered Markdown", "Markdown-capable editor export"],
        "contains_runtime_data": False,
        "contains_secrets": False,
    })


def diagnostics_summary(app: Any | None = None) -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "generated_at": _now(),
        "version_metadata": version_metadata(),
        "health": health_summary(app),
        "routes": route_inventory(app),
        "route_ownership_registry": route_ownership_registry(app),
        "modules": module_inventory(),
        "plugins": load_plugin_manifests(),
        "storage": storage_summary(),
        "api_schema": platform_api.summarize_api_schema_consistency(app),
        "response_envelopes": platform_api.list_response_envelopes(),
        "migrations": platform_migrations.migration_summary(),
        "migration_plan": platform_migrations.migration_plan(),
        "storage_map": platform_migrations.storage_map(),
        "generated_manual": generated_manual_status(),
        "api_contracts": {
            "version": APP_VERSION,
            "contract_groups": ["platform_summary", "route_inventory", "route_registry", "api_schema", "migration_planner", "plugin_summary", "cockpit_workspace_task_summaries"],
            "tests_file": "tests/test_api_contracts_v4.py",
            "no_live_mutation": True,
            "requires_network": False,
            "requires_credentials": False,
        },
        "safety": safety_statements(),
        "settings": build_settings(),
        "diagnostics_do_not_mutate_live_trading_state": True,
    })


def platform_summary(app: Any | None = None) -> dict[str, Any]:
    h = health_summary(app)
    return safety_flags({
        "version": APP_VERSION,
        "overall_status": h["overall_status"],
        "route_count": h["route_count"],
        "plugin_count": h["plugin_count"],
        "invalid_plugin_count": h["invalid_plugin_count"],
        "storage_namespace_count": h["storage_namespace_count"],
        "api_schema_family_count": h.get("api_schema_family_count", 0),
        "migration_step_count": h.get("migration_step_count", 0),
        "extracted_router_count": h.get("extracted_router_count", 0),
        "extracted_router_modules": h.get("extracted_router_modules", []),
        "api_contract_status": h.get("api_contract_status"),
        "generated_manual_status": h.get("generated_manual_status", {}),
        "safety_posture": "fail-closed, local-first, human-in-the-loop",
        "release_candidate_stage": "v4.17.0-real Feature Readiness Review Workflow",
        "next_platform_action": "Review AI safe defaults, extracted AI/platform/v3-core routers, route ownership registry, API contracts, generated manual output, runtime migration plan, plugin manifests, and storage compatibility before broader APIRouter migration.",
    })


def build_settings() -> dict[str, Any]:
    return safety_flags({"version": APP_VERSION, "settings": PLATFORM_SETTINGS.copy()})


def update_settings(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    # In v4.0 settings are intentionally non-persistent to avoid surprising runtime writes from diagnostics.
    requested = payload or {}
    return safety_flags({"ok": True, "settings": {**PLATFORM_SETTINGS, **{k: bool(v) for k, v in requested.items() if k in PLATFORM_SETTINGS}}, "persisted": False})


def export_json(app: Any | None = None) -> dict[str, Any]:
    diag = diagnostics_summary(app)
    return export_manifest(
        "platform_diagnostics_json",
        "v4.3 Platform Diagnostics Export",
        included_object_ids=["platform_version", "route_inventory", "route_ownership_registry", "plugin_manifests", "storage_namespaces", "generated_manual", "api_contracts", "safety_policy"],
        related_object_ids=["api_schema_inventory", "response_envelopes", "runtime_migration_plan", "storage_map", "router_modules"],
        unknown_unavailable_data=diag.get("health", {}).get("known_unknown_unavailable_data", []),
        payload=diag,
    )


def export_markdown(app: Any | None = None) -> str:
    return to_markdown(export_json(app))


def search_items(app: Any | None = None) -> list[dict[str, Any]]:
    diag = diagnostics_summary(app)
    rows = [
        {"id": "platform:version", "result_id": "platform:version", "result_type": "platform_version", "title": "Platform Version Metadata", "summary": diag["version_metadata"]["release_title"], "status": "active", "tags": ["platform", "version", "v4"], "quick_link": "/v3/platform", "search_text": "platform version v4 diagnostics metadata"},
        {"id": "platform:routes", "result_id": "platform:routes", "result_type": "platform_route_inventory", "title": "Platform Route Inventory", "summary": f"{diag['routes']['count']} route entries inventoried.", "status": "diagnostic", "tags": ["platform", "routes"], "quick_link": "/v3/platform/routes", "search_text": "platform routes inventory api ui"},
        {"id": "platform:route-registry", "result_id": "platform:route-registry", "result_type": "route_ownership_record", "title": "Route Ownership Registry", "summary": f"{diag['route_ownership_registry']['count']} route families with ownership metadata.", "status": "documented", "tags": ["platform", "routes", "router"], "quick_link": "/api/v3/platform/route-registry", "search_text": "route ownership records router extraction status owner module"},
        {"id": "platform:router-platform", "result_id": "platform:router-platform", "result_type": "router_module", "title": "Extracted Platform Router", "summary": "v4 platform UI and API routes are registered from app/routers/platform.py.", "status": "extracted", "tags": ["platform", "router"], "quick_link": "/docs/V4_ROUTER_ARCHITECTURE_GUIDE_v4.7.0-real.md", "search_text": "router module extracted platform apirouter"},
        {"id": "platform:api-contracts", "result_id": "platform:api-contracts", "result_type": "api_contract", "title": "API Contract Test Groups", "summary": "Contract tests cover AI safe defaults, platform envelopes, route inventory, schema, migration, plugins, and safe summary endpoints.", "status": "tested", "tags": ["platform", "contracts", "tests", "ai"], "quick_link": "/docs/V4_API_CONTRACTS_GUIDE_v4.7.0-real.md", "search_text": "api contract tests ai openai envelope route inventory migration plugin no live mutation"},
        {"id": "platform:plugins", "result_id": "platform:plugins", "result_type": "platform_plugin_manifest", "title": "Plugin Manifest Boundary", "summary": f"{diag['plugins']['count']} metadata-only plugin manifests.", "status": "safe", "tags": ["platform", "plugins", "manifest"], "quick_link": "/v3/platform/plugins", "search_text": "platform plugins manifests metadata only no code execution"},
        {"id": "platform:storage", "result_id": "platform:storage", "result_type": "platform_storage_namespace", "title": "Storage Compatibility", "summary": f"{diag['storage']['count']} local storage namespaces documented.", "status": "documented", "tags": ["platform", "storage"], "quick_link": "/v3/platform/storage", "search_text": "platform storage compatibility migration runtime data"},
        {"id": "platform:api-schema", "result_id": "platform:api-schema", "result_type": "api_schema", "title": "API Schema Inventory", "summary": f"{diag['api_schema']['summary']['api_family_count']} API families and {diag['api_schema']['summary']['schema_object_count']} schema objects.", "status": "documented", "tags": ["platform", "schema", "api"], "quick_link": "/v3/platform/schema", "search_text": "api schema inventory response envelope schema consistency"},
        {"id": "platform:response-envelope", "result_id": "platform:response-envelope", "result_type": "api_response_envelope", "title": "Shared Response Envelope", "summary": "v4.3 envelope fields include success, app_version, generated_at, warnings, blockers, unknown data, limitations, and safety statements.", "status": "documented", "tags": ["platform", "schema", "envelope"], "quick_link": "/docs/V4_API_SCHEMA_GUIDE_v4.7.0-real.md", "search_text": "response envelope success app_version generated_at warnings blockers unknown unavailable safety statement"},
        {"id": "platform:migrations", "result_id": "platform:migrations", "result_type": "migration_plan", "title": "Runtime Migration Planner", "summary": f"{diag['migrations']['step_count']} non-destructive migration planning steps.", "status": "non-destructive", "tags": ["platform", "migration", "storage"], "quick_link": "/v3/platform/migrations", "search_text": "runtime migration planner non destructive backup manual review storage map"},
        {"id": "platform:storage-map", "result_id": "platform:storage-map", "result_type": "storage_compatibility_record", "title": "Storage Namespace Map", "summary": f"{diag['storage_map']['count']} runtime namespaces mapped for compatibility.", "status": "documented", "tags": ["platform", "storage", "compatibility"], "quick_link": "/v3/platform/migrations/storage-map", "search_text": "storage namespace map backup package excluded runtime data"},
        {"id": "platform:manual", "result_id": "platform:manual", "result_type": "generated_manual", "title": "Generated Operator Manual", "summary": f"Manual source exists: {diag['generated_manual']['exists']}.", "status": "generated" if diag["generated_manual"]["exists"] else "pending", "tags": ["platform", "manual", "docs"], "quick_link": "/docs/generated/OPERATOR_MANUAL_v4.17.0-real.md", "search_text": "generated operator manual route inventory api schema migration router architecture"},
        {"id": "platform:generated-route-inventory", "result_id": "platform:generated-route-inventory", "result_type": "generated_inventory", "title": "Generated Route Inventory", "summary": "Deterministic route inventory source for docs and manual regeneration.", "status": "generated" if (PROJECT_ROOT / "docs/generated/ROUTE_INVENTORY_v4.17.0-real.md").exists() else "pending", "tags": ["platform", "generated", "routes"], "quick_link": "/docs/generated/ROUTE_INVENTORY_v4.17.0-real.md", "search_text": "generated route inventory ownership registry"},
        {"id": "platform:safety", "result_id": "platform:safety", "result_type": "platform_safety_policy", "title": "Platform Safety Boundary", "summary": diag['safety']['standard_safety_statement'], "status": "fail-closed", "tags": ["platform", "safety"], "quick_link": "/v3/platform/diagnostics", "search_text": "platform safety no live mutation no orders no cancellations"},
    ]
    return rows


def graph_nodes(app: Any | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = search_items(app)
    nodes = [{"node_id": row["id"], "node_type": row["result_type"], "title": row["title"], "status": row["status"], "summary": row["summary"]} for row in rows]
    edges = [
        {"source_node": "platform:version", "target_node": "platform:routes", "relationship_type": "documents"},
        {"source_node": "platform:routes", "target_node": "platform:route-registry", "relationship_type": "owns"},
        {"source_node": "platform:route-registry", "target_node": "platform:router-platform", "relationship_type": "extracted_to"},
        {"source_node": "platform:api-contracts", "target_node": "platform:routes", "relationship_type": "validates"},
        {"source_node": "platform:manual", "target_node": "platform:routes", "relationship_type": "generated_from"},
        {"source_node": "platform:manual", "target_node": "platform:api-schema", "relationship_type": "documents"},
        {"source_node": "platform:version", "target_node": "platform:plugins", "relationship_type": "defines_boundary"},
        {"source_node": "platform:plugins", "target_node": "platform:safety", "relationship_type": "protected_by"},
        {"source_node": "platform:storage", "target_node": "platform:safety", "relationship_type": "respects"},
        {"source_node": "platform:api-schema", "target_node": "platform:response-envelope", "relationship_type": "describes"},
        {"source_node": "platform:migrations", "target_node": "platform:storage-map", "relationship_type": "documents"},
        {"source_node": "platform:migrations", "target_node": "platform:safety", "relationship_type": "prohibits"},
        {"source_node": "platform:routes", "target_node": "platform:api-schema", "relationship_type": "exposes"},
    ]
    return nodes, edges


def workflow_output(workflow_id: str) -> dict[str, Any]:
    diag = diagnostics_summary()
    titles = {
        "platform_health_review": "Platform Health Review",
        "route_inventory_review": "Route Inventory Review",
        "plugin_boundary_review": "Plugin Boundary Review",
        "storage_compatibility_review": "Storage Compatibility Review",
        "release_candidate_readiness_review": "Release Candidate Readiness Review",
        "package_cleanliness_review": "Package Cleanliness Review",
        "safety_boundary_review": "Safety Boundary Review",
        "api_schema_consistency_review": "API Schema Consistency Review",
        "runtime_migration_planning_review": "Runtime Migration Planning Review",
        "storage_namespace_backup_review": "Storage Namespace Backup Review",
        "route_boundary_review": "Route Boundary Review",
        "router_extraction_readiness_review": "Router Extraction Readiness Review",
        "api_contract_review": "API Contract Review",
        "operator_manual_regeneration_review": "Operator Manual Regeneration Review",
        "v4_2_release_readiness_review": "v4.3 Release Readiness Review",
    }
    return safety_flags({
        "workflow_id": workflow_id,
        "title": titles.get(workflow_id, "Platform Review"),
        "status": "completed",
        "generated_at": _now(),
        "sections": ["Summary", "Routers", "Route Registry", "API Contracts", "Generated Manual", "API Schema", "Migrations", "Plugins", "Storage", "Safety", "Unknowns", "Next Actions"],
        "summary": platform_summary(),
        "diagnostics": diag,
        "next_actions": ["Review invalid plugin manifests if any.", "Confirm release ZIP excludes runtime data and data/ai records.", "Regenerate operator manual after route/docs changes.", "Keep AI outputs draft-only and human-reviewed.", "Keep router extraction additive and path-preserving.", "Keep plugin manifests metadata-only for v4.x."],
    })
