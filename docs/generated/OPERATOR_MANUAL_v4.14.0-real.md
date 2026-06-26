# Polymarket OP Console Operator Manual - v4.15.0-real

Package slug: `polymarket-op-console`

Repository: https://github.com/samgabsi/polymarket-op-console

Version: `4.15.0-real`

## Safety Notice

Platform diagnostics, AI drafts, AI suggestions, ChatGPT connector blueprints, plugin manifests, route inventories, storage summaries, exports, tasks, guided reviews, cockpit views, command-palette actions, keyboard shortcuts, and workflow packets are local-first operator aids. They do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, or provide financial advice.

This manual is documentation. It is not financial advice, not trading approval, and not execution readiness.

## Executive Overview

Polymarket OP Console is a local-first, human-in-the-loop console for AI News Odds draft fair-probability adjustment, source-weighted evidence scoring, opportunity review, market drilldowns, AI Edge packet lifecycle, operator notes, watchlist and paper-review workflows, research, paper workflows, live-control readiness, datasets, freshness planning, simulation, analytics, tasks, guided reviews, cockpit navigation, v4 platform diagnostics, AI-assisted draft review, and AI Edge Research.

## Safety Model

- Live order submission remains backend-gated and fail-closed.
- Approval checkbox, warning acknowledgement, typed confirmation phrase, read-only checks, live armed checks, kill switch checks, risk checks, and audit logging remain authoritative.
- AI drafts, routers, API contracts, generated docs, schemas, migration plans, diagnostics, plugins, tasks, guided reviews, and cockpit actions do not place or cancel orders.
- AI Edge Research packets are evidence-backed drafts with citations, contradictions, missing-information tracking, probability drafts, and calibration records; they are not financial advice or trade approval.
- OpenAI API calls are disabled and dry-run-only by default; prompt audit records store hashes and redacted metadata, not raw secrets.
- OpenAI web-search review packets are blocked by default and local LLM edge review cannot claim web search.
- Unknown or unavailable data must be shown honestly and must not be invented.

## Installation And Launch

Create a virtual environment, install `requirements.txt`, run `python run.py`, create the first admin user, then open `/v3` or `/v3/platform`.

## Configuration

Use `.env` locally for real values and keep it out of release packages. `.env.example` contains safe placeholders and environment variable names only.

## Navigation Map

- /v3
- /v3/opportunities
- /v3/markets/{market_id_or_slug}
- /v3/markets/family/{family_id}
- /v3/ai
- /v3/ai/edge
- /v3/ai/edge/packets
- /v3/ai/news-odds
- /v3/ai/news-odds/adjustments
- /v3/platform
- /v3/cockpit
- /v3/workspace
- /v3/tasks
- /v3/datasets
- /v3/freshness
- /v3/simulation
- /v3/analytics
- /v2-live

## Route Families

| Family | Title | Router | Status | Safety |
| --- | --- | --- | --- | --- |
| v2_live | V2 Live-Control UI | app/main.py | do-not-move-yet | gated-live-action-reference |
| v3_command_center | V3 Command Center UI | app/main.py | metadata-only | informational |
| v3_tasks | V3 Task Planner UI | app/main.py | planned | review-only |
| v3_workspace | Guided Operator Workspace UI | app/main.py | planned | review-only |
| v3_cockpit | Operator Cockpit UI | app/main.py | planned | review-only |
| v4_ai | Multi-Provider AI Copilot UI | app/routers/ai.py | extracted | review-only |
| v4_ai_news_odds | AI News Odds Adjustment UI | app/main.py | planned | review-only |
| v4_platform | V4 Platform UI | app/routers/platform.py | extracted | informational |
| v3_datasets | Dataset Builder UI | app/main.py | planned | read-only-action |
| v3_freshness | Freshness Scheduler UI | app/main.py | planned | read-only-action |
| v3_simulation | Simulation Lab UI | app/main.py | planned | review-only |
| v3_analytics | Operator Analytics UI | app/main.py | planned | informational |
| api_v3_platform | V4 Platform APIs | app/routers/platform.py | extracted | informational |
| api_v3_core | V3 Core UX APIs | app/routers/v3_core.py | extracted | informational |
| api_v3_ai | AI Copilot APIs | app/routers/ai.py | extracted | review-only |
| api_v3_ai_news_odds | AI News Odds Adjustment APIs | app/main.py | planned | review-only |
| v4_cross_market_arbitrage | Cross-Market Arbitrage UI/APIs | app/main.py | planned | review-only |
| api_v3_cockpit | Cockpit APIs | app/main.py | planned | review-only |
| api_v3_workspace | Workspace APIs | app/main.py | planned | review-only |
| api_v3_tasks | Task APIs | app/main.py | planned | review-only |
| api_v3_datasets | Dataset APIs | app/main.py | planned | read-only-action |
| api_v3_freshness | Freshness APIs | app/main.py | planned | read-only-action |
| api_v3_simulation | Simulation APIs | app/main.py | planned | review-only |
| api_v3_analytics | Analytics APIs | app/main.py | planned | informational |
| api_v3 | V3 General APIs | app/main.py | metadata-only | informational |
| api_v2 | V2 Live-Control APIs | app/main.py | do-not-move-yet | gated-live-action-reference |

## Router Architecture Overview

Extracted router modules: app/routers/ai.py, app/routers/platform.py, app/routers/v3_core.py. Remaining families stay in `app/main.py` until path-preservation and safety-gate coverage is broadened.

## API Schema And Contracts

API families: 14. Contract tests live in `tests/test_api_contracts_v4.py` and use local TestClient/fakes only.

## Runtime Migration Planner

Plan `runtime_migration_plan_v4_3_0` is dry-run only from `4.2.0-real` to `4.15.0-real`. Automatic runtime migration is `False`.

## Platform Diagnostics

Overall platform status: `pass`. Generated manual status is tracked locally and excludes runtime data.

## Plugin Manifest Boundary

Metadata-only manifests loaded: 3. Plugin manifests do not execute code.

## OpenAI Operator Copilot

The AI layer produces structured drafts for human review, task suggestions requiring explicit acceptance, prompt-governed review packets, redacted/hashing audit records, and a ChatGPT connector blueprint. It is not autonomous trading, not financial advice, and not trade approval.

## AI Edge Research

AI Edge Research creates evidence-backed draft packets from app-provided evidence, source metadata, citations, contradictions, missing information, draft fair-probability estimates, dry-run OpenAI web-search plans, local LLM evidence-review boundaries, and calibration records. It is disabled/mock/dry-run-only by default and writes runtime records under `data/ai/edge/` only after explicit operator actions.

## Daily Workflow

- Review `/v3` command center.
- Check blockers, unknown data, alerts, freshness, task inbox, and cockpit panels.
- Use packets and reports as review aids only.

## Weekly Workflow

- Run weekly review/task workflows.
- Review storage and migration planning reports.
- Regenerate manual/inventories after route or docs changes.

## V3 Command Center

The command center aggregates local summaries, warnings, blockers, unknowns, tasks, workflows, and safety posture.

## Task Planner, Guided Workspace, And Cockpit

Tasks, guided sessions, dependencies, saved views, cockpit layouts, shortcuts, and command-palette actions are local workflow tools. Completion is not trade approval.

## Datasets, Freshness, Simulation, And Analytics

Datasets and freshness are explicit read-only/local workflows. Simulation and analytics are descriptive and do not claim profitability or execution readiness.

## Research, Monitoring, Portfolio, Governance, And V2 Live Control

V2 live-control compatibility remains guarded by existing backend controls. Research, monitoring, portfolio, and governance records are local operator context.

## Exports, Audit, And Evidence Handling

Exports are redacted and release packages must exclude runtime audit ledgers, screenshots, dataset payloads, generated runtime reports, credentials, logs, and local `.env` values.

## Demo Data And Runtime Storage

Known runtime namespaces: 17. Runtime data is lazily created under `data/` and excluded from clean packages.

## Validation And Package Checks

Run compile/import checks, API contract tests, release validators, startup smoke, generated manual checks, secret scans, and package cleanliness checks before packaging.

## Troubleshooting

- If API routes return 401/403 before setup or login, create the first admin user and authenticate.
- If runtime namespaces are missing in a clean package, treat them as lazily created unless local data was expected.
- If PDF output is needed, export this Markdown with pandoc or a trusted local Markdown editor.

## Appendix A - Key Environment Controls

- READ_ONLY
- LIVE_TRADING_ENABLED
- LIVE_REQUIRE_MANUAL_APPROVAL
- LIVE_DRY_RUN_ONLY
- POLYMARKET_V2_TRADING_MODE
- POLYMARKET_V2_REQUIRE_APPROVAL
- POLYMARKET_V2_CONFIRMATION_PHRASE
- OPENAI_ENABLE_API
- OPENAI_ENABLE_WEB_SEARCH
- OPENAI_DRY_RUN_ONLY
- OPENAI_REDACT_BEFORE_SEND
- OPENAI_REQUIRE_OPERATOR_APPROVAL
- AI_EDGE_ENABLE
- AI_EDGE_ALLOW_WEB_SEARCH
- AI_EDGE_ALLOW_MARKET_IMPLIED_COMPARISON
- AI_NEWS_ODDS_ENABLED
- AI_NEWS_ODDS_WEB_SEARCH_ENABLED
- AI_NEWS_ODDS_CAN_PLACE_ORDERS
- AI_NEWS_ODDS_CAN_CANCEL_ORDERS
- LOCAL_LLM_ENABLE_EDGE_REVIEW
- LOCAL_LLM_EDGE_CAN_SEARCH_WEB
- CHATGPT_MCP_SERVER_ENABLED

## Appendix B - Source Documents

- docs/RELEASE_NOTES_v4.15.0-real.md
- docs/VALIDATION_v4.15.0-real.md
- docs/OPERATOR_ACCEPTANCE_CHECKLIST.md
- docs/STUB_BURNDOWN_MAP_v4.15.0-real.md
- docs/V4_FUNCTIONAL_COMPLETION_GUIDE_v4.15.0-real.md
- docs/V4_OPPORTUNITY_REVIEW_WORKFLOW_GUIDE_v4.15.0-real.md
- docs/V4_CONFIGURABLE_AI_ODDS_ADJUSTMENT_GUIDE_v4.15.0-real.md
- docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.15.0-real.md
- docs/OPERATOR_NOTES_v4.15.0-real.md
- docs/RELEASE_CHECKLIST_v4.15.0-real.md
- docs/V4_AI_NEWS_ODDS_ADJUSTMENT_ENGINE_GUIDE_v4.7.0-real.md
- docs/V4_SOURCE_WEIGHTING_AND_CORROBORATION_GUIDE_v4.7.0-real.md
- docs/V4_NEWS_EVIDENCE_PACKET_GUIDE_v4.7.0-real.md
- docs/V4_AI_NEWS_SEARCH_PROVIDER_GUIDE_v4.7.0-real.md
- docs/V4_FAIR_PROBABILITY_ADJUSTMENT_GUIDE_v4.7.0-real.md
- docs/V4_AI_NEWS_ODDS_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md
- docs/V4_OPPORTUNITY_REVIEW_WORKBENCH_GUIDE_v4.7.0-real.md
- docs/V4_MARKET_DETAIL_DRILLDOWN_GUIDE_v4.7.0-real.md
- docs/V4_MARKET_FAMILY_COMPARISON_GUIDE_v4.7.0-real.md
- docs/V4_AI_EDGE_PACKET_LIFECYCLE_GUIDE_v4.7.0-real.md
- docs/V4_OPERATOR_NOTES_AND_REVIEW_RECORDS_GUIDE_v4.7.0-real.md
- docs/V4_WATCHLIST_AND_PAPER_REVIEW_QUEUE_GUIDE_v4.7.0-real.md
- docs/V4_OPENAI_INTEGRATION_GUIDE_v4.7.0-real.md
- docs/V4_LOCAL_LLM_RUNTIME_GUIDE_v4.7.0-real.md
- docs/V4_AI_OPERATOR_COPILOT_GUIDE_v4.7.0-real.md
- docs/V4_AI_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md
- docs/V4_AI_SAFETY_AND_PRIVACY_GUIDE_v4.7.0-real.md
- docs/V4_AI_EDGE_RESEARCH_GUIDE_v4.7.0-real.md
- docs/V4_AI_WEB_SEARCH_RESEARCH_GUIDE_v4.7.0-real.md
- docs/V4_AI_EVIDENCE_PACKET_GUIDE_v4.7.0-real.md
- docs/V4_AI_MODEL_CALIBRATION_GUIDE_v4.7.0-real.md
- docs/V4_OPENAI_WEB_SEARCH_EDGE_GUIDE_v4.7.0-real.md
- docs/V4_LOCAL_LLM_EDGE_REVIEW_GUIDE_v4.7.0-real.md
- docs/V4_AI_EDGE_CALIBRATION_GUIDE_v4.7.0-real.md
- docs/V4_AI_EDGE_PRIVACY_AND_SAFETY_GUIDE_v4.7.0-real.md
- docs/V4_CHATGPT_CONNECTOR_BLUEPRINT_v4.7.0-real.md
- docs/V4_ROUTER_ARCHITECTURE_GUIDE_v4.7.0-real.md
- docs/V4_API_CONTRACTS_GUIDE_v4.7.0-real.md
- docs/V4_API_SCHEMA_GUIDE_v4.7.0-real.md
- docs/V4_RUNTIME_MIGRATION_PLANNER_GUIDE_v4.7.0-real.md
- docs/V4_PLATFORM_ARCHITECTURE_GUIDE_v4.7.0-real.md
- docs/V3_OPERATOR_COCKPIT_GUIDE_v4.7.0-real.md
- docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md
- docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md
- docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md
- docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md
- docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md
- docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md
