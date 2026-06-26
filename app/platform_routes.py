from __future__ import annotations

from typing import Any
from .config import APP_VERSION
from .platform_exports import export_manifest, to_markdown
from .platform_route_registry import registry_map, route_ownership_registry
from .platform_safety import safety_flags

ROUTE_FAMILY_HINTS = [
    ("v2_live", "/v2-live"), ("v3_tasks", "/v3/tasks"), ("v3_workspace", "/v3/workspace"),
    ("v3_cockpit", "/v3/cockpit"), ("v4_platform", "/v3/platform"), ("v3_datasets", "/v3/datasets"),
    ("v3_freshness", "/v3/freshness"), ("v3_simulation", "/v3/simulation"), ("v3_analytics", "/v3/analytics"),
    ("v4_ai_news_odds", "/v3/ai/news-odds"),
    ("v4_ai", "/v3/ai"),
    ("api_v3_platform", "/api/v3/platform"), ("api_v3_core", "/api/v3/ux"), ("api_v3_cockpit", "/api/v3/cockpit"),
    ("api_v3_workspace", "/api/v3/workspace"), ("api_v3_tasks", "/api/v3/tasks"), ("api_v3_datasets", "/api/v3/datasets"),
    ("api_v3_freshness", "/api/v3/freshness"), ("api_v3_simulation", "/api/v3/simulation"), ("api_v3_analytics", "/api/v3/analytics"),
    ("api_v3_ai_news_odds", "/api/v3/ai/news-odds"),
    ("api_v3_ai", "/api/v3/ai"),
    ("v3_command_center", "/v3"), ("api_v3", "/api/v3"), ("api_v2", "/api/v2"),
]
ROUTE_FAMILY_METADATA = registry_map()


def _family(path: str) -> str:
    for name, prefix in ROUTE_FAMILY_HINTS:
        if path == prefix or path.startswith(prefix + "/"):
            return name
    if path.startswith("/api"):
        return "api_other"
    return "ui_other"


def _metadata(family: str) -> dict[str, Any]:
    return ROUTE_FAMILY_METADATA.get(family, {
        "owner_module": "unclassified",
        "router_module": "app/main.py",
        "current_location": "app/main.py",
        "ui_api_classification": "unknown",
        "safety_class": "informational",
        "live_mutation_risk": "unknown; existing route-specific gates apply",
        "auth_protection_notes": "Existing app middleware and route dependencies apply.",
        "docs_link": "/docs/V4_PLATFORM_ARCHITECTURE_GUIDE_v4.7.0-real.md",
        "extraction_status": "legacy-preserved",
        "compatibility_notes": "Unclassified route; route inventory is diagnostic only.",
        "representative_paths": [],
    })


def route_inventory(app: Any | None = None) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if app is not None:
        for route in getattr(app, "routes", []):
            path = getattr(route, "path", "")
            if not path:
                continue
            methods = sorted([m for m in getattr(route, "methods", []) if m not in {"HEAD", "OPTIONS"}])
            family = _family(path)
            meta = _metadata(family)
            items.append({
                "path": path,
                "name": getattr(route, "name", ""),
                "methods": methods,
                "family": family,
                "owner_module": meta["owner_module"],
                "router_module": meta["router_module"],
                "current_location": meta["current_location"],
                "ui_api_classification": meta["ui_api_classification"],
                "safety_class": meta["safety_class"],
                "live_mutation_risk": meta["live_mutation_risk"],
                "auth_protection_notes": meta["auth_protection_notes"],
                "docs_link": meta["docs_link"],
                "extraction_status": meta["extraction_status"],
                "route_kind": "api" if path.startswith("/api") else "ui",
                "protected_or_authenticated": path.startswith("/v3") or path.startswith("/api/v3") or path.startswith("/v2-live"),
                "mutates_live_trading_state": False if path.startswith("/v3/platform") or path.startswith("/api/v3/platform") else "existing route-specific gates apply",
                "safety_notes": "Route inventory is diagnostic only and does not call route handlers.",
                "compatibility_notes": meta["compatibility_notes"],
                "future_modularization_note": "Candidate for APIRouter grouping after contract tests cover route-specific behavior.",
            })
    else:
        for name, prefix in ROUTE_FAMILY_HINTS:
            meta = _metadata(name)
            items.append({"path": prefix, "name": name, "methods": ["GET"], "family": name, "owner_module": meta["owner_module"], "router_module": meta["router_module"], "current_location": meta["current_location"], "ui_api_classification": meta["ui_api_classification"], "safety_class": meta["safety_class"], "live_mutation_risk": meta["live_mutation_risk"], "auth_protection_notes": meta["auth_protection_notes"], "docs_link": meta["docs_link"], "extraction_status": meta["extraction_status"], "protected_or_authenticated": True, "safety_notes": "Static route family hint.", "compatibility_notes": meta["compatibility_notes"], "future_modularization_note": "Candidate for APIRouter grouping after contract tests cover route-specific behavior."})
    families: dict[str, int] = {}
    for item in items:
        families[item["family"]] = families.get(item["family"], 0) + 1
    return safety_flags({
        "version": APP_VERSION,
        "count": len(items),
        "items": items,
        "families": families,
        "family_metadata": ROUTE_FAMILY_METADATA,
        "route_ownership_registry": route_ownership_registry(route_items=items),
        "route_inventory_does_not_mutate_live_trading_state": True,
        "route_inventory_does_not_call_handlers": True,
    })


def module_inventory() -> dict[str, Any]:
    modules = [
        "live_v2", "live_v3", "live_v3_tasks", "live_v3_workspace", "live_v3_cockpit", "platform_version", "platform_safety",
        "platform_exports", "platform_routes", "platform_plugins", "platform_storage", "platform_diagnostics", "platform_api",
        "platform_migrations", "live_v3_datasets", "live_v3_freshness", "live_v3_simulation", "live_v3_analytics",
        "platform_route_registry", "ai_openai_client", "ai_operator_copilot", "ai_prompt_governance", "ai_schemas",
        "ai_suggestions", "routers.platform", "routers.v3_core", "routers.ai",
    ]
    items = [{
        "module": m,
        "family": "ai_assistance" if m.startswith("ai_") or m == "routers.ai" else ("platform" if m.startswith("platform") else "operator_intelligence"),
        "module_boundary": "AI draft/review helper" if m.startswith("ai_") or m == "routers.ai" else ("shared platform helper" if m.startswith("platform") else "feature module"),
        "safety_notes": "Module inventory only; no module action is executed.",
        "future_migration_note": "Prepared for future v4.x APIRouter/module split; v4.3 extracts platform, AI, and v3 core UX routers first.",
    } for m in modules]
    return safety_flags({"version": APP_VERSION, "count": len(items), "items": items})


def export_route_boundary_json(app: Any | None = None) -> dict[str, Any]:
    payload = {"routes": route_inventory(app), "modules": module_inventory()}
    return export_manifest(
        "route_module_boundary_json",
        "v4.3 Route and Module Boundary Inventory with Router Registry",
        included_object_ids=["route_inventory", "module_inventory", "route_family_metadata", "route_ownership_registry"],
        related_object_ids=["api_schema_inventory", "runtime_migration_plan"],
        unknown_unavailable_data=["Route handler body schemas are not inferred by route inventory."],
        payload=payload,
    )


def export_route_boundary_markdown(app: Any | None = None) -> str:
    return to_markdown(export_route_boundary_json(app))
