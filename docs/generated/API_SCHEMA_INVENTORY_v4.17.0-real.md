# API Schema Inventory - v4.17.0-real

Package: Polymarket OP Console (`polymarket-op-console`)

The shared response envelope and API schema inventory are additive documentation and validation aids. They do not bypass backend safety gates.

## Envelope Adoption

| Metric | Value |
| --- | --- |
| normalized_family_ids | ['platform', 'ai'] |
| normalized_family_count | 2 |
| unnormalized_family_count | 12 |
| api_route_count | 868 |
| unnormalized_endpoint_count | 762 |

## API Families

| Family | Title | Prefixes | Owner | Normalized | Docs |
| --- | --- | --- | --- | --- | --- |
| platform | Platform APIs | /api/v3/platform | platform_* | True | /docs/V4_API_CONTRACTS_GUIDE_v4.7.0-real.md |
| ai | AI Copilot APIs | /api/v3/ai | ai_* | True | /docs/V4_OPENAI_INTEGRATION_GUIDE_v4.7.0-real.md |
| ai_news_odds | AI News Odds Adjustment APIs | /api/v3/ai/news-odds | ai_news_odds | False | /docs/V4_AI_NEWS_ODDS_ADJUSTMENT_ENGINE_GUIDE_v4.7.0-real.md |
| cross_market_arbitrage | Cross-Market Arbitrage APIs | /api/v3/arbitrage | cross_market_arbitrage | False | /docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.15.0-real.md |
| v3_core | V3 Core UX APIs | /api/v3/ux | live_v3 | False | /docs/V4_ROUTER_ARCHITECTURE_GUIDE_v4.7.0-real.md |
| cockpit | Cockpit APIs | /api/v3/cockpit | live_v3_cockpit | False | /docs/V3_OPERATOR_COCKPIT_GUIDE_v4.7.0-real.md |
| workspace | Guided Workspace APIs | /api/v3/workspace | live_v3_workspace | False | /docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md |
| tasks | Task APIs | /api/v3/tasks | live_v3_tasks | False | /docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md |
| datasets | Dataset APIs | /api/v3/datasets | live_v3_datasets | False | /docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md |
| freshness | Freshness APIs | /api/v3/freshness | live_v3_freshness | False | /docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md |
| simulation | Simulation APIs | /api/v3/simulation | live_v3_simulation | False | /docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md |
| analytics | Analytics APIs | /api/v3/analytics | live_v3_analytics | False | /docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md |
| search_graph_workflows | Search, Graph, and Workflow APIs | /api/v3/search,/api/v3/graph,/api/v3/workflows | live_v3 | False | /docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md |
| live_control | Live-Control Adjacent APIs | /api/live,/api/v2/live,/v2-live | live_* | False | /docs/LIVE_TRADING_V2.md |

## Recommended Next Normalization Targets

- api_v3_core
- api_v3_cockpit
- api_v3_workspace
- api_v3_tasks
- api_v3_datasets

## Unnormalized Endpoints

| Path | Family | Owner | Reason |
| --- | --- | --- | --- |
| /api/auth/me | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/users | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/ui/workflow | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/users | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/users/{username} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/users/{username} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/maintenance/status | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/maintenance/backups | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/maintenance/backups/{filename}/download | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/maintenance/backups/{filename} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/schema | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/status | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/validate | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/diff | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/save | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/export-sanitized | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/audit-history | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/export-sanitized.env | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/presets | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/presets/{preset_id}/preview | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/config/presets/{preset_id}/apply | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/setup/status | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/deployment/status | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/config/readiness | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/config/readiness.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/config/template.env | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/dry-run-adapter | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/dry-run-adapter.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/dry-run-adapter/{receipt_id} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/dry-run-review | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/dry-run-review.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/dry-run-review/{packet_id} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-packets/{packet_id}/dry-run/preview | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-packets/{packet_id}/dry-run | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/readiness | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/readiness.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/readonly-validations | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/readonly-validations.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/readonly-validations/{validation_id} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/readonly-validation/preview | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/readonly-validation | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/requests | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/requests.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/requests/{request_or_packet_id} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-packets/{packet_id}/adapter-request/preview | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-packets/{packet_id}/adapter-request | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/manual-execution-reviews | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/manual-execution-reviews.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/manual-execution-reviews/{review_id} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-packets/{packet_id}/manual-execution-review/preview | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-packets/{packet_id}/manual-execution-review | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-control/readiness | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-control/readiness.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-attempts | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-attempts.csv | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/execution-attempts/{attempt_id} | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/requests/{adapter_request_id}/manual-submit/preview | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/adapter/requests/{adapter_request_id}/manual-submit | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/manual-cancel/preview | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/live/manual-cancel | api_other | unclassified | family not yet adopted into shared platform envelope |
| /api/v3/operator-os | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/operator-os/{workspace} | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/config | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/status | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/account | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/orders | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/fills | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/positions | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/decisions | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/runs | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/audit | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/run-once | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/reset | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3/paper/orders/{order_id}/cancel-paper | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
| /api/v3 | api_v3 | live_v3/* | family not yet adopted into shared platform envelope |
