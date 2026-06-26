from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .config import APP_VERSION
from .platform_safety import safety_flags


@dataclass(frozen=True)
class RouteFamilyOwner:
    family_id: str
    title: str
    owner_module: str
    router_module: str
    current_location: str
    ui_api_classification: str
    safety_class: str
    live_mutation_risk: str
    auth_protection_notes: str
    docs_link: str
    extraction_status: str
    compatibility_notes: str
    representative_paths: list[str]


ROUTE_FAMILY_OWNERS: tuple[RouteFamilyOwner, ...] = (
    RouteFamilyOwner("v2_live", "V2 Live-Control UI", "live_v2/live_*", "app/main.py", "app/main.py", "ui", "gated-live-action-reference", "live-adjacent gated by backend controls", "Authenticated UI; backend submit/cancel gates remain authoritative.", "/docs/LIVE_TRADING_V2.md", "do-not-move-yet", "Live-control UI stays monolithic until dedicated safety regression coverage is broader.", ["/v2-live", "/v2-live/strategy", "/v2-live/data"]),
    RouteFamilyOwner("v3_command_center", "V3 Command Center UI", "live_v3", "app/main.py", "app/main.py", "ui", "informational", "none", "Authenticated UI.", "/docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md", "metadata-only", "Core v3 UI remains in main.py while platform router extraction is validated.", ["/v3", "/v3/search", "/v3/graph", "/v3/workflows"]),
    RouteFamilyOwner("v3_tasks", "V3 Task Planner UI", "live_v3_tasks", "app/main.py", "app/main.py", "ui", "review-only", "none", "Authenticated UI.", "/docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md", "planned", "Task completion remains workflow state only and is not trade approval.", ["/v3/tasks", "/v3/tasks/board", "/v3/tasks/cadence"]),
    RouteFamilyOwner("v3_workspace", "Guided Operator Workspace UI", "live_v3_workspace", "app/main.py", "app/main.py", "ui", "review-only", "none", "Authenticated UI.", "/docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md", "planned", "Guided reviews stay separate from approvals and execution.", ["/v3/workspace", "/v3/workspace/daily-review", "/v3/workspace/review-packets"]),
    RouteFamilyOwner("v3_cockpit", "Operator Cockpit UI", "live_v3_cockpit", "app/main.py", "app/main.py", "ui", "review-only", "none", "Authenticated UI.", "/docs/V3_OPERATOR_COCKPIT_GUIDE_v4.7.0-real.md", "planned", "Cockpit shortcuts and command palette remain safe local actions.", ["/v3/cockpit", "/v3/cockpit/command-palette", "/v3/cockpit/shortcuts"]),
    RouteFamilyOwner("v4_ai", "Multi-Provider AI Copilot UI", "ai_*", "app/routers/ai.py", "app/routers/ai.py", "ui", "review-only", "none", "Authenticated UI.", "/docs/V4_AI_OPERATOR_COPILOT_GUIDE_v4.7.0-real.md", "extracted", "AI pages are draft-only, dry-run-by-default, redacted, and do not mutate live trading state.", ["/v3/ai", "/v3/ai/copilot", "/v3/ai/suggestions"]),
    RouteFamilyOwner("v4_ai_news_odds", "AI News Odds Adjustment UI", "ai_news_odds", "app/main.py", "app/main.py", "ui", "review-only", "none", "Authenticated UI.", "/docs/V4_AI_NEWS_ODDS_ADJUSTMENT_ENGINE_GUIDE_v4.7.0-real.md", "planned", "News odds pages produce source-weighted draft fair-probability updates only and never mutate live trading.", ["/v3/ai/news-odds", "/v3/ai/news-odds/run", "/v3/ai/news-odds/adjustments", "/v3/ai/news-odds/source-weights"]),
    RouteFamilyOwner("v4_platform", "V4 Platform UI", "platform_*", "app/routers/platform.py", "app/routers/platform.py", "ui", "informational", "none", "Authenticated UI.", "/docs/V4_PLATFORM_ARCHITECTURE_GUIDE_v4.7.0-real.md", "extracted", "Platform UI is local-first diagnostics and does not call live mutation paths.", ["/v3/platform", "/v3/platform/routes", "/v3/platform/migrations"]),
    RouteFamilyOwner("v3_datasets", "Dataset Builder UI", "live_v3_datasets", "app/main.py", "app/main.py", "ui", "read-only-action", "none", "Authenticated UI.", "/docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md", "planned", "Dataset actions are explicit read-only/demo-safe collection and validation flows.", ["/v3/datasets", "/v3/datasets/collector", "/v3/datasets/quality"]),
    RouteFamilyOwner("v3_freshness", "Freshness Scheduler UI", "live_v3_freshness", "app/main.py", "app/main.py", "ui", "read-only-action", "none", "Authenticated UI.", "/docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md", "planned", "Freshness planning is not trading automation.", ["/v3/freshness", "/v3/freshness/jobs", "/v3/freshness/notifications"]),
    RouteFamilyOwner("v3_simulation", "Simulation Lab UI", "live_v3_simulation", "app/main.py", "app/main.py", "ui", "review-only", "none", "Authenticated UI.", "/docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md", "planned", "Simulation is descriptive and does not authorize execution.", ["/v3/simulation", "/v3/simulation/replay", "/v3/simulation/no-trade"]),
    RouteFamilyOwner("v3_analytics", "Operator Analytics UI", "live_v3_analytics", "app/main.py", "app/main.py", "ui", "informational", "none", "Authenticated UI.", "/docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md", "planned", "Analytics are descriptive and do not claim profitability.", ["/v3/analytics", "/v3/analytics/learning-report"]),
    RouteFamilyOwner("api_v3_platform", "V4 Platform APIs", "platform_*", "app/routers/platform.py", "app/routers/platform.py", "api", "informational", "none", "Authenticated API; returns 401/403 before setup/login.", "/docs/V4_API_CONTRACTS_GUIDE_v4.7.0-real.md", "extracted", "Read-only platform contract, schema, registry, migration, plugin, storage, diagnostics, and export endpoints.", ["/api/v3/platform/summary", "/api/v3/platform/routes", "/api/v3/platform/route-registry"]),
    RouteFamilyOwner("api_v3_core", "V3 Core UX APIs", "live_v3", "app/routers/v3_core.py", "app/routers/v3_core.py", "api", "informational", "none", "Authenticated API; returns 401/403 before setup/login.", "/docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md", "extracted", "Small v3 UX status API family extracted as a low-risk router pilot.", ["/api/v3/ux/status", "/api/v3/ux/design-system", "/api/v3/ux/navigation"]),
    RouteFamilyOwner("api_v3_ai", "AI Copilot APIs", "ai_*", "app/routers/ai.py", "app/routers/ai.py", "api", "review-only", "none", "Authenticated API; OpenAI network calls are disabled/dry-run-only by default.", "/docs/V4_OPENAI_INTEGRATION_GUIDE_v4.7.0-real.md", "extracted", "AI APIs generate drafts, suggestions, audit summaries, and exports without live mutation. Suggestions require explicit human acceptance.", ["/api/v3/ai/summary", "/api/v3/ai/suggestions", "/api/v3/ai/copilot/dry-run"]),
    RouteFamilyOwner("api_v3_ai_news_odds", "AI News Odds Adjustment APIs", "ai_news_odds", "app/main.py", "app/main.py", "api", "review-only", "none", "Authenticated API; web search is disabled unless explicitly configured and approved.", "/docs/V4_AI_NEWS_ODDS_ADJUSTMENT_ENGINE_GUIDE_v4.7.0-real.md", "planned", "News odds APIs store review records and draft model context only; they cannot submit, cancel, approve, or arm live orders.", ["/api/v3/ai/news-odds/config", "/api/v3/ai/news-odds/market/{market_id_or_slug}/adjust", "/api/v3/ai/news-odds/adjustments"]),
    RouteFamilyOwner("v4_cross_market_arbitrage", "Cross-Market Arbitrage UI/APIs", "cross_market_arbitrage", "app/main.py", "app/main.py", "ui+api", "review-only", "none", "Authenticated UI/API; scanner disabled by default and never submits orders.", "/docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.15.0-real.md", "planned", "Arbitrage candidates and scan snapshots are review-only local records, not guaranteed profits or execution instructions.", ["/v3/arbitrage", "/v3/arbitrage/scan/record", "/api/v3/arbitrage/config", "/api/v3/arbitrage/scan", "/api/v3/arbitrage/scan/record"]),
    RouteFamilyOwner("api_v3_cockpit", "Cockpit APIs", "live_v3_cockpit", "app/main.py", "app/main.py", "api", "review-only", "none", "Authenticated API.", "/docs/V3_OPERATOR_COCKPIT_GUIDE_v4.7.0-real.md", "planned", "Command-palette actions reject forbidden live capabilities.", ["/api/v3/cockpit/summary", "/api/v3/cockpit/command-palette"]),
    RouteFamilyOwner("api_v3_workspace", "Workspace APIs", "live_v3_workspace", "app/main.py", "app/main.py", "api", "review-only", "none", "Authenticated API.", "/docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md", "planned", "Workspace completion remains separate from approvals.", ["/api/v3/workspace/summary", "/api/v3/workspace/flows"]),
    RouteFamilyOwner("api_v3_tasks", "Task APIs", "live_v3_tasks", "app/main.py", "app/main.py", "api", "review-only", "none", "Authenticated API.", "/docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md", "planned", "Task APIs never approve trades.", ["/api/v3/tasks", "/api/v3/tasks/summary"]),
    RouteFamilyOwner("api_v3_datasets", "Dataset APIs", "live_v3_datasets", "app/main.py", "app/main.py", "api", "read-only-action", "none", "Authenticated API.", "/docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md", "planned", "Dataset APIs remain explicit and non-trading.", ["/api/v3/datasets", "/api/v3/datasets/summary"]),
    RouteFamilyOwner("api_v3_freshness", "Freshness APIs", "live_v3_freshness", "app/main.py", "app/main.py", "api", "read-only-action", "none", "Authenticated API.", "/docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md", "planned", "Freshness jobs and notifications do not trade.", ["/api/v3/freshness", "/api/v3/freshness/summary"]),
    RouteFamilyOwner("api_v3_simulation", "Simulation APIs", "live_v3_simulation", "app/main.py", "app/main.py", "api", "review-only", "none", "Authenticated API.", "/docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md", "planned", "Simulation APIs are descriptive and do not submit/cancel orders.", ["/api/v3/simulation", "/api/v3/simulation/sessions"]),
    RouteFamilyOwner("api_v3_analytics", "Analytics APIs", "live_v3_analytics", "app/main.py", "app/main.py", "api", "informational", "none", "Authenticated API.", "/docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md", "planned", "Analytics APIs are local descriptive reports.", ["/api/v3/analytics", "/api/v3/analytics/summary"]),
    RouteFamilyOwner("api_v3", "V3 General APIs", "live_v3/*", "app/main.py", "app/main.py", "api", "informational", "none", "Authenticated API.", "/docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md", "metadata-only", "General v3 APIs remain in main.py until route-family modules are split.", ["/api/v3", "/api/v3/search", "/api/v3/graph", "/api/v3/workflows"]),
    RouteFamilyOwner("api_v2", "V2 Live-Control APIs", "live_v2/live_*", "app/main.py", "app/main.py", "api", "gated-live-action-reference", "live-adjacent gated by backend controls", "Authenticated API plus backend live/paper/read-only/kill-switch gates.", "/docs/LIVE_TRADING_V2.md", "do-not-move-yet", "V2 live-control APIs stay in main.py until dedicated safety gate contract tests are broadened.", ["/api/v2/live/status", "/api/v2/live/verify"]),
)


def registry_map() -> dict[str, dict[str, Any]]:
    return {row.family_id: asdict(row) for row in ROUTE_FAMILY_OWNERS}


def route_ownership_registry(app: Any | None = None, route_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = registry_map()
    if route_items is None and app is not None:
        route_items = []
        for route in getattr(app, "routes", []):
            path = getattr(route, "path", "")
            if path:
                route_items.append({"path": path})
    counts = {family_id: 0 for family_id in rows}
    if route_items is not None:
        from .platform_routes import _family

        for item in route_items:
            family = _family(str(item.get("path", "")))
            if family in counts:
                counts[family] += 1
    items = []
    for family_id, row in rows.items():
        enriched = dict(row)
        enriched["route_count"] = counts.get(family_id, 0)
        items.append(enriched)
    status_counts: dict[str, int] = {}
    for item in items:
        status_counts[item["extraction_status"]] = status_counts.get(item["extraction_status"], 0) + 1
    return safety_flags({
        "version": APP_VERSION,
        "count": len(items),
        "items": items,
        "extraction_status_counts": status_counts,
        "extracted_router_modules": sorted({item["router_module"] for item in items if item["extraction_status"] == "extracted"}),
        "future_extraction_plan": [
            "Keep live-control and paper execution-adjacent routes metadata-only until safety-gate contract coverage is broader.",
            "Move cockpit, workspace, task, dataset, freshness, simulation, and analytics families one router at a time with path-preservation tests.",
            "Adopt shared API envelopes additively after endpoint-specific templates and clients are covered by contracts.",
        ],
        "route_registry_does_not_call_handlers": True,
        "route_registry_does_not_mutate_live_trading_state": True,
    })
