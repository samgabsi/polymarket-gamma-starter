from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("POLYMARKET_OP_CONSOLE_EPHEMERAL_SESSION_SECRET", "true")

from app.config import APP_VERSION  # noqa: E402
from app.platform_api import PACKAGE_NAME, PACKAGE_SLUG, summarize_api_schema_consistency  # noqa: E402
from app.platform_diagnostics import diagnostics_summary  # noqa: E402
from app.platform_migrations import migration_plan, storage_map  # noqa: E402
from app.platform_plugins import plugin_summary  # noqa: E402
from app.platform_routes import route_inventory  # noqa: E402
from app.platform_safety import STANDARD_SAFETY_STATEMENT  # noqa: E402

REPOSITORY = "https://github.com/samgabsi/polymarket-op-console"
GENERATED_DIR = ROOT / "docs" / "generated"
ROUTE_SOURCE_FILES = [
    ROOT / "app" / "main.py",
    ROOT / "app" / "routers" / "platform.py",
    ROOT / "app" / "routers" / "v3_core.py",
    ROOT / "app" / "routers" / "ai.py",
]


@dataclass(frozen=True)
class SourceRoute:
    path: str
    methods: set[str]
    name: str


@dataclass(frozen=True)
class SourceRouteApp:
    routes: list[SourceRoute]


def _source_route_app() -> SourceRouteApp:
    routes: list[SourceRoute] = []
    route_pattern = re.compile(r"@(?:app|router)\.(get|post|put|patch|delete)\(\"([^\"]+)\"")
    def_pattern = re.compile(r"async def ([a-zA-Z0-9_]+)\(")
    for source in ROUTE_SOURCE_FILES:
        pending: list[tuple[str, str]] = []
        for line in source.read_text(encoding="utf-8").splitlines():
            match = route_pattern.search(line)
            if match:
                pending.append((match.group(1).upper(), match.group(2)))
                continue
            def_match = def_pattern.search(line)
            if def_match and pending:
                name = def_match.group(1)
                for method, path in pending:
                    routes.append(SourceRoute(path=path, methods={method}, name=name))
                pending = []
    return SourceRouteApp(routes=routes)


def _line_items(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    rendered = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        rendered.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(rendered)


def _secret_free(text: str) -> bool:
    lowered = text.lower()
    blocked = ["supersecret", "begin private key", "sk-live", "sk_test_", "x-api-key:", "authorization: bearer "]
    return not any(token in lowered for token in blocked)


def route_inventory_markdown(routes: dict[str, Any]) -> str:
    rows = [
        [
            item.get("path", ""),
            ",".join(item.get("methods", [])),
            item.get("family", ""),
            item.get("owner_module", ""),
            item.get("router_module", ""),
            item.get("extraction_status", ""),
            item.get("safety_class", ""),
        ]
        for item in routes.get("items", [])
        if not str(item.get("path", "")).startswith("/static")
    ]
    registry_rows = [
        [item["family_id"], item["title"], item["owner_module"], item["router_module"], item["extraction_status"], item["route_count"]]
        for item in routes.get("route_ownership_registry", {}).get("items", [])
    ]
    return "\n\n".join([
        f"# Route Inventory - v{APP_VERSION}",
        f"Package: {PACKAGE_NAME} (`{PACKAGE_SLUG}`)",
        "This generated inventory is diagnostic only. It does not call route handlers, place orders, cancel orders, arm live trading, or inspect runtime data.",
        f"Total route entries: {routes.get('count', 0)}",
        "## Route Families",
        _table(["Family", "Count"], sorted([[key, value] for key, value in routes.get("families", {}).items()])),
        "## Ownership Registry",
        _table(["Family", "Title", "Owner", "Router", "Status", "Routes"], registry_rows),
        "## Routes",
        _table(["Path", "Methods", "Family", "Owner", "Router", "Status", "Safety"], rows),
    ]) + "\n"


def api_schema_inventory_markdown(schema: dict[str, Any]) -> str:
    data = schema.get("data", {})
    families = data.get("api_families", [])
    rows = [
        [item.get("family_id"), item.get("title"), ",".join(item.get("route_prefixes", [])), item.get("module_owner"), item.get("normalized_response"), item.get("docs_link", "")]
        for item in families
    ]
    unnormalized = data.get("unnormalized_endpoint_list", [])
    unnormalized_rows = [[item.get("path"), item.get("family"), item.get("owner_module"), item.get("reason")] for item in unnormalized[:80]]
    return "\n\n".join([
        f"# API Schema Inventory - v{APP_VERSION}",
        f"Package: {PACKAGE_NAME} (`{PACKAGE_SLUG}`)",
        "The shared response envelope and API schema inventory are additive documentation and validation aids. They do not bypass backend safety gates.",
        "## Envelope Adoption",
        _table(["Metric", "Value"], [[key, value] for key, value in data.get("envelope_adoption_summary", {}).items()]),
        "## API Families",
        _table(["Family", "Title", "Prefixes", "Owner", "Normalized", "Docs"], rows),
        "## Recommended Next Normalization Targets",
        _line_items(data.get("recommended_next_normalization_targets", [])),
        "## Unnormalized Endpoints",
        _table(["Path", "Family", "Owner", "Reason"], unnormalized_rows),
    ]) + "\n"


def migration_template_markdown(plan: dict[str, Any]) -> str:
    rows = [
        [step.get("step_id"), step.get("namespace"), step.get("classification"), step.get("automatic_mutation_allowed"), step.get("operator_instruction")]
        for step in plan.get("steps", [])
    ]
    return "\n\n".join([
        f"# Runtime Migration Plan Template - v{APP_VERSION}",
        f"Plan ID: `{plan.get('plan_id')}`",
        f"Source version: `{plan.get('source_version')}`",
        f"Target version: `{plan.get('target_version')}`",
        "This is a dry-run-only planning template. It does not delete, move, rewrite, copy, migrate, export, or inspect full runtime records.",
        f"Dry-run guarantee: {plan.get('dry_run_only_guarantee')}",
        "## Backup Recommendation",
        str(plan.get("backup_recommendation", "")),
        "## Steps",
        _table(["Step", "Namespace", "Classification", "Auto Mutation", "Instruction"], rows),
    ]) + "\n"


def operator_manual_markdown(routes: dict[str, Any], schema: dict[str, Any], diagnostics: dict[str, Any], plan: dict[str, Any], plugins: dict[str, Any], storage: dict[str, Any]) -> str:
    route_registry = routes.get("route_ownership_registry", {})
    extracted = route_registry.get("extracted_router_modules", [])
    docs = [
        "docs/RELEASE_NOTES_v4.17.0-real.md",
        "docs/VALIDATION_v4.17.0-real.md",
        "docs/OPERATOR_ACCEPTANCE_CHECKLIST.md",
        "docs/STUB_BURNDOWN_MAP_v4.17.0-real.md",
        "docs/V4_FUNCTIONAL_COMPLETION_GUIDE_v4.17.0-real.md",
        "docs/V4_FEATURE_READINESS_WORKFLOW_GUIDE_v4.17.0-real.md",
        "docs/V4_OPPORTUNITY_REVIEW_WORKFLOW_GUIDE_v4.17.0-real.md",
        "docs/V4_CONFIGURABLE_AI_ODDS_ADJUSTMENT_GUIDE_v4.17.0-real.md",
        "docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.17.0-real.md",
        "docs/OPERATOR_NOTES_v4.17.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.17.0-real.md",
        "docs/V4_AI_NEWS_ODDS_ADJUSTMENT_ENGINE_GUIDE_v4.7.0-real.md",
        "docs/V4_SOURCE_WEIGHTING_AND_CORROBORATION_GUIDE_v4.7.0-real.md",
        "docs/V4_NEWS_EVIDENCE_PACKET_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_NEWS_SEARCH_PROVIDER_GUIDE_v4.7.0-real.md",
        "docs/V4_FAIR_PROBABILITY_ADJUSTMENT_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_NEWS_ODDS_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md",
        "docs/V4_OPPORTUNITY_REVIEW_WORKBENCH_GUIDE_v4.7.0-real.md",
        "docs/V4_MARKET_DETAIL_DRILLDOWN_GUIDE_v4.7.0-real.md",
        "docs/V4_MARKET_FAMILY_COMPARISON_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_EDGE_PACKET_LIFECYCLE_GUIDE_v4.7.0-real.md",
        "docs/V4_OPERATOR_NOTES_AND_REVIEW_RECORDS_GUIDE_v4.7.0-real.md",
        "docs/V4_WATCHLIST_AND_PAPER_REVIEW_QUEUE_GUIDE_v4.7.0-real.md",
        "docs/V4_OPENAI_INTEGRATION_GUIDE_v4.7.0-real.md",
        "docs/V4_LOCAL_LLM_RUNTIME_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_OPERATOR_COPILOT_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_SAFETY_AND_PRIVACY_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_EDGE_RESEARCH_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_WEB_SEARCH_RESEARCH_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_EVIDENCE_PACKET_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_MODEL_CALIBRATION_GUIDE_v4.7.0-real.md",
        "docs/V4_OPENAI_WEB_SEARCH_EDGE_GUIDE_v4.7.0-real.md",
        "docs/V4_LOCAL_LLM_EDGE_REVIEW_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_EDGE_CALIBRATION_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_EDGE_PRIVACY_AND_SAFETY_GUIDE_v4.7.0-real.md",
        "docs/V4_CHATGPT_CONNECTOR_BLUEPRINT_v4.7.0-real.md",
        "docs/V4_ROUTER_ARCHITECTURE_GUIDE_v4.7.0-real.md",
        "docs/V4_API_CONTRACTS_GUIDE_v4.7.0-real.md",
        "docs/V4_API_SCHEMA_GUIDE_v4.7.0-real.md",
        "docs/V4_RUNTIME_MIGRATION_PLANNER_GUIDE_v4.7.0-real.md",
        "docs/V4_PLATFORM_ARCHITECTURE_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_COCKPIT_GUIDE_v4.7.0-real.md",
        "docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md",
        "docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md",
        "docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md",
        "docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
    ]
    route_rows = [
        [item["family_id"], item["title"], item["router_module"], item["extraction_status"], item["safety_class"]]
        for item in route_registry.get("items", [])
    ]
    return "\n\n".join([
        f"# {PACKAGE_NAME} Operator Manual - v{APP_VERSION}",
        f"Package slug: `{PACKAGE_SLUG}`",
        f"Repository: {REPOSITORY}",
        f"Version: `{APP_VERSION}`",
        "## Safety Notice",
        STANDARD_SAFETY_STATEMENT,
        "This manual is documentation. It is not financial advice, not trading approval, and not execution readiness.",
        "## Executive Overview",
        "Polymarket OP Console is a local-first, human-in-the-loop console for AI News Odds draft fair-probability adjustment, source-weighted evidence scoring, opportunity review, market drilldowns, AI Edge packet lifecycle, operator notes, watchlist and paper-review workflows, research, paper workflows, live-control readiness, datasets, freshness planning, simulation, analytics, tasks, guided reviews, cockpit navigation, v4 platform diagnostics, AI-assisted draft review, and AI Edge Research.",
        "## Safety Model",
        _line_items([
            "Live order submission remains backend-gated and fail-closed.",
            "Approval checkbox, warning acknowledgement, typed confirmation phrase, read-only checks, live armed checks, kill switch checks, risk checks, and audit logging remain authoritative.",
            "AI drafts, routers, API contracts, generated docs, schemas, migration plans, diagnostics, plugins, tasks, guided reviews, and cockpit actions do not place or cancel orders.",
            "AI Edge Research packets are evidence-backed drafts with citations, contradictions, missing-information tracking, probability drafts, and calibration records; they are not financial advice or trade approval.",
            "OpenAI API calls are disabled and dry-run-only by default; prompt audit records store hashes and redacted metadata, not raw secrets.",
            "OpenAI web-search review packets are blocked by default and local LLM edge review cannot claim web search.",
            "Unknown or unavailable data must be shown honestly and must not be invented.",
        ]),
        "## Installation And Launch",
        "Create a virtual environment, install `requirements.txt`, run `python run.py`, create the first admin user, then open `/v3` or `/v3/platform`.",
        "## Configuration",
        "Use `.env` locally for real values and keep it out of release packages. `.env.example` contains safe placeholders and environment variable names only.",
        "## Navigation Map",
        _line_items(["/v3", "/v3/opportunities", "/v3/markets/{market_id_or_slug}", "/v3/markets/family/{family_id}", "/v3/ai", "/v3/ai/edge", "/v3/ai/edge/packets", "/v3/ai/news-odds", "/v3/ai/news-odds/adjustments", "/v3/platform", "/v3/cockpit", "/v3/workspace", "/v3/tasks", "/v3/datasets", "/v3/freshness", "/v3/simulation", "/v3/analytics", "/v2-live"]),
        "## Route Families",
        _table(["Family", "Title", "Router", "Status", "Safety"], route_rows),
        "## Router Architecture Overview",
        f"Extracted router modules: {', '.join(extracted)}. Remaining families stay in `app/main.py` until path-preservation and safety-gate coverage is broadened.",
        "## API Schema And Contracts",
        f"API families: {schema.get('summary', {}).get('api_family_count', 0)}. Contract tests live in `tests/test_api_contracts_v4.py` and use local TestClient/fakes only.",
        "## Runtime Migration Planner",
        f"Plan `{plan.get('plan_id')}` is dry-run only from `{plan.get('source_version')}` to `{plan.get('target_version')}`. Automatic runtime migration is `{plan.get('automatic_runtime_migration')}`.",
        "## Platform Diagnostics",
        f"Overall platform status: `{diagnostics.get('health', {}).get('overall_status')}`. Generated manual status is tracked locally and excludes runtime data.",
        "## Plugin Manifest Boundary",
        f"Metadata-only manifests loaded: {plugins.get('plugin_count', 0)}. Plugin manifests do not execute code.",
        "## OpenAI Operator Copilot",
        "The AI layer produces structured drafts for human review, task suggestions requiring explicit acceptance, prompt-governed review packets, redacted/hashing audit records, and a ChatGPT connector blueprint. It is not autonomous trading, not financial advice, and not trade approval.",
        "## AI Edge Research",
        "AI Edge Research creates evidence-backed draft packets from app-provided evidence, source metadata, citations, contradictions, missing information, draft fair-probability estimates, dry-run OpenAI web-search plans, local LLM evidence-review boundaries, and calibration records. It is disabled/mock/dry-run-only by default and writes runtime records under `data/ai/edge/` only after explicit operator actions.",
        "## Daily Workflow",
        _line_items(["Review `/v3` command center.", "Check blockers, unknown data, alerts, freshness, task inbox, and cockpit panels.", "Use packets and reports as review aids only."]),
        "## Weekly Workflow",
        _line_items(["Run weekly review/task workflows.", "Review storage and migration planning reports.", "Regenerate manual/inventories after route or docs changes."]),
        "## V3 Command Center",
        "The command center aggregates local summaries, warnings, blockers, unknowns, tasks, workflows, and safety posture.",
        "## Task Planner, Guided Workspace, And Cockpit",
        "Tasks, guided sessions, dependencies, saved views, cockpit layouts, shortcuts, and command-palette actions are local workflow tools. Completion is not trade approval.",
        "## Datasets, Freshness, Simulation, And Analytics",
        "Datasets and freshness are explicit read-only/local workflows. Simulation and analytics are descriptive and do not claim profitability or execution readiness.",
        "## Research, Monitoring, Portfolio, Governance, And V2 Live Control",
        "V2 live-control compatibility remains guarded by existing backend controls. Research, monitoring, portfolio, and governance records are local operator context.",
        "## Exports, Audit, And Evidence Handling",
        "Exports are redacted and release packages must exclude runtime audit ledgers, screenshots, dataset payloads, generated runtime reports, credentials, logs, and local `.env` values.",
        "## Demo Data And Runtime Storage",
        f"Known runtime namespaces: {storage.get('count', 0)}. Runtime data is lazily created under `data/` and excluded from clean packages.",
        "## Validation And Package Checks",
        "Run compile/import checks, API contract tests, release validators, startup smoke, generated manual checks, secret scans, and package cleanliness checks before packaging.",
        "## Troubleshooting",
        _line_items(["If API routes return 401/403 before setup or login, create the first admin user and authenticate.", "If runtime namespaces are missing in a clean package, treat them as lazily created unless local data was expected.", "If PDF output is needed, export this Markdown with pandoc or a trusted local Markdown editor."]),
        "## Appendix A - Key Environment Controls",
        _line_items(["READ_ONLY", "LIVE_TRADING_ENABLED", "LIVE_REQUIRE_MANUAL_APPROVAL", "LIVE_DRY_RUN_ONLY", "POLYMARKET_V2_TRADING_MODE", "POLYMARKET_V2_REQUIRE_APPROVAL", "POLYMARKET_V2_CONFIRMATION_PHRASE", "OPENAI_ENABLE_API", "OPENAI_ENABLE_WEB_SEARCH", "OPENAI_DRY_RUN_ONLY", "OPENAI_REDACT_BEFORE_SEND", "OPENAI_REQUIRE_OPERATOR_APPROVAL", "AI_EDGE_ENABLE", "AI_EDGE_ALLOW_WEB_SEARCH", "AI_EDGE_ALLOW_MARKET_IMPLIED_COMPARISON", "AI_NEWS_ODDS_ENABLED", "AI_NEWS_ODDS_WEB_SEARCH_ENABLED", "AI_NEWS_ODDS_CAN_PLACE_ORDERS", "AI_NEWS_ODDS_CAN_CANCEL_ORDERS", "LOCAL_LLM_ENABLE_EDGE_REVIEW", "LOCAL_LLM_EDGE_CAN_SEARCH_WEB", "CHATGPT_MCP_SERVER_ENABLED"]),
        "## Appendix B - Source Documents",
        _line_items(docs),
    ]) + "\n"


def main() -> int:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    source_app = _source_route_app()
    routes = route_inventory(source_app)
    schema = summarize_api_schema_consistency(source_app)
    diagnostics = diagnostics_summary(source_app)
    plan = migration_plan()
    plugins = plugin_summary()
    storage = storage_map()

    outputs = {
        GENERATED_DIR / f"ROUTE_INVENTORY_v{APP_VERSION}.md": route_inventory_markdown(routes),
        GENERATED_DIR / f"API_SCHEMA_INVENTORY_v{APP_VERSION}.md": api_schema_inventory_markdown(schema),
        GENERATED_DIR / f"RUNTIME_MIGRATION_PLAN_TEMPLATE_v{APP_VERSION}.md": migration_template_markdown(plan),
        GENERATED_DIR / f"OPERATOR_MANUAL_v{APP_VERSION}.md": operator_manual_markdown(routes, schema, diagnostics, plan, plugins, storage),
    }
    for path, text in outputs.items():
        if not _secret_free(text):
            raise SystemExit(f"generated output failed secret scan: {path}")
        path.write_text(text, encoding="utf-8")
    print({
        "version": APP_VERSION,
        "generated": [str(path.relative_to(ROOT)) for path in outputs],
        "manual_secret_scan": "pass",
        "runtime_data_included": False,
        "pdf_generated": False,
        "pdf_note": "Markdown source only; export with a local Markdown/PDF tool if needed.",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
