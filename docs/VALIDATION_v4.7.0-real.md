# Validation - v4.7.0-real

## Release identity

- Package: Polymarket OP Console
- Slug: polymarket-op-console
- Version: v4.7.0-real
- Release theme: AI News Odds Adjustment Engine, Source-Weighted Evidence Scoring, and Fair Probability Updates
- ZIP SHA-256: computed after the release ZIP is sealed and reported in the final response.

## Implementation status

- AI News Odds Adjustment Engine: implemented in `app/ai_news_odds.py`.
- Provider abstraction/manual evidence/local LLM no-browse guard: implemented in `app/ai_news_providers.py`.
- Source weighting/corroboration/duplicate detection: implemented with deterministic scoring and tests.
- Fair probability adjustment: implemented with log-odds adjustment, caps, confidence warnings, and review-only safety flags.
- News Odds UI: added AI News Odds console, run page, adjustments list/detail, source weights, market panel, and family panel.
- Market Detail integration: added News Odds panel and market-specific news odds route.
- Opportunity Workbench integration: added News Odds status/action fields.
- AI Edge packet integration: packet summaries include news odds snapshot/source weights/before-after edge fields.
- Family News Odds: added family plan/search/adjust APIs and family UI panel.
- Manual evidence mode: available by default.
- OpenAI web-search provider: wired as a gated provider path and disabled by default.
- Local LLM evidence-review: clarifies that local LLM does not browse unless evidence is supplied.
- System map/route inventory/screenshot dry-run: updated with AI News Odds routes and safety boundaries.
- Safety status: review-only, no-live-mutation, not financial advice, not trade approval.

## Validation commands run

```text
find app scripts tests -name '*.py' -print0 | xargs -0 python -m py_compile
pass
```

```text
PYTHONPATH=. pytest -q tests/test_ai_news_odds_v47.py
9 passed, 8 existing Starlette TemplateResponse deprecation warnings
```

```text
PYTHONPATH=. pytest -q tests/test_market_edge_v45.py tests/test_navigation_v4.py tests/test_ai_edge_v44.py tests/test_opportunity_review_v46.py tests/test_ai_news_odds_v47.py
40 passed, 18 existing Starlette TemplateResponse deprecation warnings
```

```text
PYTHONPATH=. pytest -q tests/test_ai_v4.py tests/test_api_contracts_v4.py tests/test_live_v2.py tests/test_live_v2_data.py tests/test_live_v2_verification.py
37 passed, 24 existing Starlette TemplateResponse deprecation warnings
```

```text
PYTHONPATH=. python scripts/check_versions.py
pass
```

```text
PYTHONPATH=. python scripts/capture_v3_screenshots.py --dry-run
pass
```

```text
PYTHONPATH=. python scripts/generate_operator_manual.py
pass
```

```text
PYTHONPATH=. python scripts/validate_v3_release.py --quick
overall_status: pass
```

```text
PYTHONPATH=. python scripts/smoke_startup.py
pass; included AI News Odds UI routes and API route smoke checks; network_mutation=False; orders_placed=False; orders_cancelled=False
```

```text
PYTHONPATH=. python scripts/check_release_package.py .
pass; blocked_findings=[]; count=0
```

ZIP package cleanliness and direct ZIP inspection are run after final packaging.

## Known limitations

- The monolithic full test suite was not claimed as passed.
- Browser-rendered screenshot capture was not executed; screenshot routes were validated in dry-run mode.
- Live Polymarket endpoints were not exercised.
- Live OpenAI web-search calls were not tested because no safe credentials and explicit live-provider permission were provided.
- Live local LLM/Ollama calls were not tested because no endpoint was provided.
- News odds adjustments are draft fair-probability research outputs, not market-price changes, not financial advice, not profitability claims, and not trade approvals.

## Safety confirmations

- No real order placement occurred.
- No real cancellation occurred.
- AI news odds adjustments do not approve trades.
- AI news odds adjustments do not place or cancel orders.
- AI news odds adjustments do not arm live trading.
- Accepted fair-probability updates do not place or cancel orders.
- Edge recommendations do not approve trades.
- Edge recommendations do not place or cancel orders.
- AI Edge does not approve trades.
- AI Edge does not place or cancel orders.
- AI Edge does not arm live trading.
- OpenAI API/web search is disabled by default unless explicitly configured.
- Local LLM is disabled by default unless explicitly configured.
- No OpenAI API key is included.
- No secrets are included intentionally.
- AI News Odds exports are designed to contain no secrets.
- Market-implied comparison is research-only.
- Source weighting does not imply truth.
- Corroboration does not imply certainty.
- Favorite ranking does not imply edge.
- Calibration does not imply future performance.
- Navigation aliases do not bypass safety gates.
- Command-palette actions do not place or cancel orders.
- Keyboard shortcuts do not place or cancel orders.
- Task completion does not approve trades.
- Guided review completion does not approve trades.
- Screenshots are not included in the release ZIP unless explicitly safe and intended.

## Changed files

### Added files
- `app/ai_news_odds.py`
- `app/ai_news_providers.py`
- `app/templates/ai_news_odds.html`
- `app/templates/ai_news_odds_adjustment_detail.html`
- `app/templates/ai_news_odds_adjustments.html`
- `app/templates/ai_news_odds_run.html`
- `app/templates/ai_news_odds_source_weights.html`
- `app/templates/family_news_odds.html`
- `app/templates/market_news_odds.html`
- `docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md`
- `docs/RELEASE_CHECKLIST_v4.7.0-real.md`
- `docs/RELEASE_NOTES_v4.7.0-real.md`
- `docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md`
- `docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md`
- `docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md`
- `docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md`
- `docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md`
- `docs/V3_OPERATOR_COCKPIT_GUIDE_v4.7.0-real.md`
- `docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md`
- `docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md`
- `docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_EDGE_CALIBRATION_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_EDGE_PACKET_LIFECYCLE_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_EDGE_PRIVACY_AND_SAFETY_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_EDGE_RESEARCH_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_EVIDENCE_PACKET_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_MODEL_CALIBRATION_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_NEWS_ODDS_ADJUSTMENT_ENGINE_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_NEWS_ODDS_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_NEWS_SEARCH_PROVIDER_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_OPERATOR_COPILOT_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_SAFETY_AND_PRIVACY_GUIDE_v4.7.0-real.md`
- `docs/V4_AI_WEB_SEARCH_RESEARCH_GUIDE_v4.7.0-real.md`
- `docs/V4_API_CONTRACTS_GUIDE_v4.7.0-real.md`
- `docs/V4_API_SCHEMA_GUIDE_v4.7.0-real.md`
- `docs/V4_CHATGPT_CONNECTOR_BLUEPRINT_v4.7.0-real.md`
- `docs/V4_FAIR_PROBABILITY_ADJUSTMENT_GUIDE_v4.7.0-real.md`
- `docs/V4_FAVORITE_VS_EDGE_GUIDE_v4.7.0-real.md`
- `docs/V4_LOCAL_LLM_EDGE_REVIEW_GUIDE_v4.7.0-real.md`
- `docs/V4_LOCAL_LLM_RUNTIME_GUIDE_v4.7.0-real.md`
- `docs/V4_MARKET_DETAIL_DRILLDOWN_GUIDE_v4.7.0-real.md`
- `docs/V4_MARKET_EDGE_RECOMMENDATION_GUIDE_v4.7.0-real.md`
- `docs/V4_MARKET_FAMILY_COMPARISON_GUIDE_v4.7.0-real.md`
- `docs/V4_MARKET_FAMILY_RANKING_GUIDE_v4.7.0-real.md`
- `docs/V4_NEWS_EVIDENCE_PACKET_GUIDE_v4.7.0-real.md`
- `docs/V4_OPENAI_INTEGRATION_GUIDE_v4.7.0-real.md`
- `docs/V4_OPENAI_WEB_SEARCH_EDGE_GUIDE_v4.7.0-real.md`
- `docs/V4_OPPORTUNITY_REVIEW_WORKBENCH_GUIDE_v4.7.0-real.md`
- `docs/V4_PLATFORM_ARCHITECTURE_GUIDE_v4.7.0-real.md`
- `docs/V4_PLATFORM_DIAGNOSTICS_GUIDE_v4.7.0-real.md`
- `docs/V4_PLUGIN_BOUNDARY_GUIDE_v4.7.0-real.md`
- `docs/V4_ROUTER_ARCHITECTURE_GUIDE_v4.7.0-real.md`
- `docs/V4_RUNTIME_MIGRATION_PLANNER_GUIDE_v4.7.0-real.md`
- `docs/V4_SOURCE_WEIGHTING_AND_CORROBORATION_GUIDE_v4.7.0-real.md`
- `docs/V4_STORAGE_COMPATIBILITY_GUIDE_v4.7.0-real.md`
- `docs/V4_SYSTEM_MAP_GUIDE_v4.7.0-real.md`
- `docs/V4_UNIFIED_NAVIGATION_GUIDE_v4.7.0-real.md`
- `docs/VALIDATION_v4.7.0-real.md`
- `docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md`
- `docs/generated/API_SCHEMA_INVENTORY_v4.7.0-real.md`
- `docs/generated/OPERATOR_MANUAL_v4.7.0-real.md`
- `docs/generated/ROUTE_INVENTORY_v4.7.0-real.md`
- `docs/generated/RUNTIME_MIGRATION_PLAN_TEMPLATE_v4.7.0-real.md`
- `tests/test_ai_news_odds_v47.py`

### Modified files
- `.env.example`
- `CHANGELOG.md`
- `README.md`
- `VERSION`
- `app/__init__.py`
- `app/ai_edge_research.py`
- `app/ai_prompt_governance.py`
- `app/config.py`
- `app/config_console.py`
- `app/live_v2.py`
- `app/live_v3.py`
- `app/main.py`
- `app/navigation_registry.py`
- `app/opportunity_review.py`
- `app/platform_api.py`
- `app/platform_diagnostics.py`
- `app/platform_migrations.py`
- `app/platform_route_registry.py`
- `app/platform_routes.py`
- `app/platform_storage.py`
- `app/platform_version.py`
- `app/routers/ai.py`
- `app/static/style.css`
- `app/templates/live_v2_dashboard.html`
- `app/templates/live_v3_dashboard.html`
- `app/templates/market_detail.html`
- `app/templates/market_detail_v46.html`
- `app/templates/market_family_comparison.html`
- `app/templates/opportunities.html`
- `app/templates/opportunity_workbench.html`
- `app/ui.py`
- `scripts/capture_v2_6_screenshots.py`
- `scripts/capture_v2_7_screenshots.py`
- `scripts/capture_v2_8_screenshots.py`
- `scripts/capture_v2_9_screenshots.py`
- `scripts/capture_v3_screenshots.py`
- `scripts/check_release_package.py`
- `scripts/check_versions.py`
- `scripts/generate_operator_manual.py`
- `scripts/smoke_startup.py`
- `scripts/validate_v3_release.py`
- `scripts/validate_v3_ux_release.py`
- `tests/test_ai_edge_v44.py`
- `tests/test_ai_v4.py`
- `tests/test_api_contracts_v4.py`
- `tests/test_live_v2.py`
- `tests/test_live_v2_data.py`
- `tests/test_live_v2_governance.py`
- `tests/test_live_v2_monitoring.py`
- `tests/test_live_v2_portfolio.py`
- `tests/test_live_v2_research.py`
- `tests/test_live_v2_strategy.py`
- `tests/test_live_v2_ui.py`
- `tests/test_live_v2_verification.py`
- `tests/test_live_v3.py`
- `tests/test_live_v3_cockpit.py`
- `tests/test_live_v3_datasets.py`
- `tests/test_live_v3_freshness.py`
- `tests/test_live_v3_platform.py`
- `tests/test_live_v3_simulation.py`
- `tests/test_live_v3_tasks.py`
- `tests/test_live_v3_ux.py`
- `tests/test_live_v3_workspace.py`
- `tests/test_market_edge_v45.py`
- `tests/test_navigation_v4.py`
- `tests/test_navigation_v43.py`
- `tests/test_opportunity_review_v46.py`

### Removed files
- None
