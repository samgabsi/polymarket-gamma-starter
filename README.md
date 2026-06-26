# Polymarket OP Console

Current version: **v4.17.0-real**

Repository: https://github.com/samgabsi/polymarket-op-console

## v4.17.0-real — Operator OS UI/UX Consolidation

v4.17.0-real consolidates the app into a smaller operating model. Instead of promoting every page, panel, scanner, settings view, cockpit mode, paper workflow, AI page, and diagnostics route as a top-level destination, the main UI now revolves around five primary workspaces:

1. **Command Center** (`/v3`) — answers “what needs my attention right now?” with safety posture, readiness warnings, paper automation status, pending review activity, AI/opportunity counts, and next recommended action.
2. **Opportunities** (`/v3/opportunities`) — the existing opportunity workbench remains available and is now the consolidated entry point for AI odds, edge review, arbitrage candidates, paper strategy signals, and review queue records.
3. **Automation / Paper Trading** (`/v3/automation`) — summarizes paper-only automation, paper account, latest run, simulated orders/fills/positions, decision logs, and links to the detailed `/v3/paper-trading` page.
4. **Review & Audit** (`/v3/review-audit`) — gathers review queue actions, opportunity decisions, paper automation decisions, settings/safety audit rows, and accountability events.
5. **Settings & System** (`/v3/settings-system`) — consolidates feature readiness, settings, AI/OpenAI status, venues, paper limits, arbitrage settings, diagnostics, and advanced links.

Detailed/source routes still work. `/v3/ai/news-odds`, `/v3/arbitrage`, `/v3/paper-trading`, `/review-queue`, `/v3/settings`, `/v3/feature-readiness`, `/v3/cockpit`, and `/v2-live` are preserved as compatibility/detail routes and linked from the new workspaces.

Safety posture: this release does not enable live trading, submit orders, cancel orders, approve trades, arm autonomous live execution, bypass kill switches, or treat sample/cached/scaffolded data as live. Paper trading APIs continue to report `paper_only=true` and `live_execution_used=false`.

## Launch

```bash
python run.py
```

Then open:

```text
http://127.0.0.1:8000/v3
```

## Key routes

```text
/v3                       Command Center
/v3/opportunities          Opportunities workspace and workbench
/v3/automation             Automation / Paper Trading workspace
/v3/review-audit           Review & Audit workspace
/v3/settings-system        Settings & System workspace
/v3/paper-trading          Detailed paper-trading compatibility page
/v3/arbitrage              Detailed arbitrage compatibility page
/v3/ai/news-odds           Detailed AI News Odds compatibility page
/review-queue              Detailed review queue compatibility page
/v3/feature-readiness      Detailed feature readiness compatibility page
```

## v4.16.0-real — Automated Paper Trading and Simulated Execution

v4.16.0-real moved the console toward automation safely by adding **automated paper trading first**. The new paper subsystem can run a deterministic strategy cycle, evaluate candidate opportunities, apply risk gates, simulate fills, track local paper positions/P&L, and record every decision in an audit trail. It does **not** place real orders, cancel real orders, arm live trading, or bypass the existing kill switches and live gates.

### What changed in v4.16

- Added `app/paper_automation.py` for local paper account, orders, fills, positions, decisions, runs, and audit rows.
- Added a paper-only strategy runner that can be invoked manually from the UI/API when `PAPER_TRADING_ENABLED=true` and `PAPER_TRADING_AUTOMATION_ENABLED=true`.
- Added a simulated broker that applies slippage/fees and records fills without calling any real Polymarket/Kalshi execution endpoint.
- Added risk gates for per-order notional, market exposure, daily notional, open positions, trades per run/day, edge, confidence, data freshness, spread, slippage, semantic mismatch, and resolution mismatch.
- Added `/v3/paper-trading` with status cards, a paper-only safety banner, run-once/reset controls, last-run summary, open positions, recent orders/fills, and decision log.
- Added paper APIs under `/api/v3/paper/*` for status, config, account, orders, fills, positions, decisions, runs, audit, run-once, reset, and paper-only cancel request recording.
- Added paper trading settings to `/v3/settings` and feature-readiness rows for engine, automation, scheduler, broker/ledger/risk controls, and UI status.
- Added targeted v4.16 regression tests for disabled defaults, simulated fills, risk rejections, UI surfacing, settings validation, readiness truthfulness, and no-live-execution flags.

### How to enable automated paper trading

```bash
PAPER_TRADING_ENABLED=true \
PAPER_TRADING_AUTOMATION_ENABLED=true \
PAPER_TRADING_STARTING_BALANCE=1000 \
PAPER_TRADING_MAX_ORDER_NOTIONAL=25 \
PAPER_TRADING_MAX_DAILY_NOTIONAL=250 \
PAPER_TRADING_MIN_EDGE_PCT=2.0 \
PAPER_TRADING_MIN_CONFIDENCE=0.70 \
PAPER_TRADING_FILL_MODEL=conservative \
python run.py
```

Then open `/v3/paper-trading` and click **Run paper strategy once**. With no configured live/local candidate feed, the runner may use a clearly labeled `sample` paper-only candidate for smoke testing. All responses include `paper_only=true` and `live_execution_used=false`.

### Safety posture

Paper automation is separate from live trading. Enabling paper trading does not enable live trading. The paper broker never submits orders, cancels orders, signs transactions, arms live mode, or mutates exchange state. Paper P/L is simulated and does not prove live profitability.

## v4.15.0-real — Settings Workflow, Review Queue, and Feature Readiness Completion

v4.15.0-real continues the functional-completion path by closing another operator workflow end-to-end. The primary v4.15 Pro Extended pass completed the **v3 Settings / Feature Readiness workflow**: visible settings now show runtime values, saved UI-safe preferences, value source, restart-required status, validation behavior, and safety posture instead of behaving like a raw or decorative settings shell.

This package also preserves the v4.15 review-queue and feature-readiness work already present in the source: `/review-queue` has POST-backed local review actions, `/v3/feature-readiness` has filtered readiness acknowledgement records, and both remain review-only/live-disabled.

### What changed in v4.15

- Added a grouped **Settings / Feature Readiness Workflow** surface under `/v3/settings` with editable UI-safe controls for AI odds adjustment, arbitrage scanner thresholds, and Kalshi operator preferences.
- Added `POST /v3/settings/preferences/save` as a browser-safe settings form endpoint with redirect feedback and no silent no-op behavior.
- Expanded `POST /api/v3/settings` so UI-safe preferences are validated, persisted locally, reflected after refresh/remount, and rejected safely when numeric values are out of bounds.
- Added source and restart metadata for settings rows: runtime default, process environment / `.env`, or saved UI preference.
- Kept secrets masked and unavailable for browser-save workflows; the settings page does not echo secret values and does not mutate process environment or `.env` files.
- Added local audit/event rows for settings saves and validation rejections with source route/component, updated keys, previous/new state, review-only, and live-disabled metadata.
- Added `settings.v3_operator_preferences` to feature readiness and updated the stub burn-down map so settings persistence is represented truthfully.
- Preserved the v4.15 Review Queue workflow: local POST-backed Mark Reviewed, Watchlist, Send to Paper Review, Reject, Archive, and supporting API/action audit records.
- Preserved the v4.15 Feature Readiness workflow: filtered readiness/status review, local acknowledgements, and review-only/live-disabled safety fields.
- Added targeted v4.15 regression tests for settings rendering, browser-save persistence, invalid numeric rejection, feature-status truthfulness, Review Queue actions, and Feature Readiness acknowledgements.

### Safety posture

No autonomous execution was added. Settings saves, Review Queue decisions, Feature Readiness acknowledgements, Opportunity Review actions, AI odds adjustments, and arbitrage reviews are local operator metadata only. They do not place orders, cancel orders, approve trades, arm live trading, mutate `.env`, mutate process environment variables, bypass backend gates, or provide financial advice.

## v4.13.0-real — Arbitrage Scan Persistence and Feature Readiness Truthfulness

v4.13.0-real completes the next operator workflow slice for Cross-Market Arbitrage. The page now shows scanner status, data state, per-venue readiness, and feature readiness before candidates are trusted. Operators can record a scan snapshot through a visible POST-backed browser action, receive redirect feedback, and inspect local audit rows with source route, target, previous/new state, reason, data state, review-only, and live-disabled metadata.

### What changed in v4.13

- Added a visible `Record scan snapshot` action on `/v3/arbitrage` backed by `POST /v3/arbitrage/scan/record`.
- Added `POST /api/v3/arbitrage/scan/record` for API clients that need a persisted scan snapshot without using the hidden GET `write` flag.
- Added scanner/data-state fields to arbitrage scan payloads: `scanner_status`, `data_state`, `data_state_reason`, `sample_data`, `persisted`, `scanner_readiness`, and enriched `venue_statuses`.
- Replaced the demo checkbox with an explicit data-mode selector so demo fixtures and configured live-read mode are not ambiguous.
- Expanded arbitrage audit records with timestamp, feature area, action type, target id/name, previous/new state, reason, source route/component, scan id, data state, review-only, and live-disabled fields.
- Extended feature-status and stub burn-down maps with `operator_implication`, `next_action`, `data_state`, `safe_review_only`, `live_disabled`, `data_state_values`, and `error` status support.
- Added workflow tests for scan recording, data-state surfacing, enriched audit fields, readiness schema fields, and no-live-mutation guarantees.

### Safety posture

No autonomous execution was added. Recorded scan snapshots and review decisions are local operator records only. Sample fixture data is labeled as sample. Live read-only scan mode still requires deliberate configuration. Arbitrage candidates remain review-only, not guaranteed profits, and never submit orders, cancel orders, approve trades, or arm live trading.

## v4.12.0-real — Operator Workflow Acceptance and End-to-End Usability

v4.12.0-real turns the highest-impact review surfaces into fuller operator workflows. AI News Odds browser actions now return to operator pages with explicit feedback, saved draft adjustments open a reviewable detail page, accept/reject/archive decisions persist to local runtime records, and cross-market arbitrage exposes review, watchlist, ignore, and reject actions with local audit feedback.

### What changed in v4.12

- Added `docs/OPERATOR_ACCEPTANCE_CHECKLIST.md` to describe actual current workflows from launch through cockpit, AI odds review, arbitrage review, settings, feature readiness, and no-live-execution verification.
- Changed AI News Odds page POST handlers so browser actions redirect with feedback instead of returning raw JSON.
- Made visible “Save draft adjustment” controls persist local draft adjustment records and open the adjustment detail page.
- Added browser review forms for accepting AI odds drafts to review context, rejecting drafts, and archiving drafts.
- Fixed AI odds adjustment lookup so the detail page returns the latest persisted decision record after accept/reject/archive.
- Added market price, explicit recommended side, operator confirmation requirement, and current review action state to the adjustment detail page.
- Expanded arbitrage candidate actions to review, watchlist, ignore, and reject with redirect feedback and local audit persistence.
- Added workflow tests for AI odds browser feedback/persistence, arbitrage review feedback/audit, settings rendering, and feature readiness acceptance status.

### Safety posture

No autonomous execution was added. AI odds adjustments remain advisory draft records. Arbitrage candidates remain review-only and not guaranteed profits. Kalshi remains disabled/config-required unless deliberately configured. Live submit/cancel paths remain behind existing backend gates and are not made easier to trigger.

## v4.11.0-real — Stub Burn-down, End-to-End Wiring, and Functional Truthfulness

v4.11.0-real extends the route/action honesty work with a first-class stub burn-down map, additional browser POST wrappers, operator action feedback, and focused tests for visible controls that previously looked actionable but landed on POST-only API URLs.

### What changed in v4.11

- Added `/api/v3/features/stub-burndown` and nested the same map under `/api/v3/features/status`.
- The burn-down map classifies Polymarket discovery/pricing/orderbook, AI odds, AI Edge, YES/NO recommendation clarity, arbitrage, Kalshi, venue registry, review queue, audit, cockpit, task/workspace review, settings, feature readiness, export/import, launch helpers, and live controls.
- The Cockpit System Readiness section now shows both the feature status registry and the stub burn-down map.
- Workspace daily/weekly/task-triage launch controls now post through browser-safe page routes and redirect back with operator feedback.
- AI provider dry-run, AI Edge packet generation, evidence normalization preview, and AI review-packet generation now use browser POST controls instead of dead API hrefs.
- Added focused tests for burn-down coverage, endpoint rendering, cockpit UI surfacing, removal of POST-only hrefs, and page POST wrapper feedback.

### Safety posture

No autonomous execution was added. Stub maps, layouts, focus modes, saved layouts, feature status, opportunity review records, AI odds adjustment records, AI/AI Edge drafts, workspace sessions, and arbitrage candidates do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, or provide financial advice.

## v4.8.0-real — Configurable AI Odds Adjustment and Cross-Market Arbitrage Review

v4.8.0-real removes the hidden 2.5 percentage-point odds-adjustment ceiling as an absolute limit. AI News Odds packets show three separate values:

- `raw_ai_adjustment_pct`
- `evidence_weighted_adjustment_pct`
- `final_adjustment_pct`

The final value remains risk-controlled by mode-based caps, weak-evidence clamps, contradiction checks, hard caps, and operator-confirmation thresholds. Conservative mode defaults to the old safe 2.5 pp posture; balanced, aggressive, and custom modes can exceed 2.5 pp when evidence quality and configuration allow it.

v4.8.0-real also adds review-only cross-market arbitrage detection across Polymarket, Kalshi, and disabled future-venue scaffolds. The engine normalizes venue snapshots, scores deterministic market equivalence, flags resolution/semantic mismatch risk, computes YES/NO cross-venue combinations, subtracts estimated fees and slippage, constrains size by liquidity, and classifies candidates as clean, fee-sensitive, liquidity-limited, mismatch-risk, watchlist-only, or reject.

No autonomous execution was added. Arbitrage candidates are not guaranteed profits and require operator review.

## v4.7.0-real — AI News Odds Adjustment Engine, Source-Weighted Evidence Scoring, and Fair Probability Updates

v4.7.0-real adds a review-only **AI News Odds Adjustment Engine** that can plan market-specific news searches, ingest manual evidence or configured web-search results, score sources by credibility/recency/relevance/independence/corroboration, detect duplicate or syndicated coverage, identify contradictory claims, and produce bounded draft adjustments to the app's internal model fair probability.

**Market → search plan → evidence collection → source scoring → duplicate/syndication detection → corroboration → event extraction → fair-probability adjustment → before/after YES/NO edge → AI Edge packet → operator review.**

“Adjust odds” means adjusting internal draft model fair probability / fair odds for research. It does **not** mean changing Polymarket market prices, manipulating market prices, approving trades, placing orders, canceling orders, arming live trading, or providing financial advice.

### What changed in v4.7

- Added `app/ai_news_odds.py` for deterministic source-weighted evidence scoring, duplicate/syndication detection, claim clustering, corroboration scoring, event extraction, bounded log-odds fair-probability adjustments, packet persistence, and safety validation.
- Added `app/ai_news_providers.py` for market-specific search requests, OpenAI web-search gating, manual evidence mode, local LLM evidence-review preview, and normalized source packets.
- Added `/v3/ai/news-odds`, `/v3/ai/news-odds/run`, `/v3/ai/news-odds/adjustments`, `/v3/ai/news-odds/source-weights`, `/v3/markets/{market_id_or_slug}/news-odds`, and `/v3/markets/family/{family_id}/news-odds`.
- Added APIs for search planning, gated web-search requests, manual evidence ingestion, draft fair odds adjustment, adjustment listing/detail, accept-to-review-context, reject, archive, source lookup, and family-level news odds analysis.
- Integrated News Odds status into Market Detail, Opportunity Review Workbench, Market Family Comparison, AI Edge packets, navigation, system map, route inventory, screenshot dry-run planning, docs, tests, and validation.
- Added configurable safe defaults: web search disabled, manual evidence enabled, local LLM disabled, review-only required, human acceptance required, and all live-order capabilities false.

### Source weighting and corroboration

Default source weights favor primary/official, government/regulator, wire, major-news, and specialist sources over blogs, social media, forums, rumors, and unknown sources. Multiple independent high-quality sources increase confidence more than many copied or syndicated repeats. Contradictions, rumors, stale sources, low relevance, and duplicate coverage reduce confidence and cap adjustments.

### Draft fair odds adjustment

The deterministic adjustment algorithm starts from the existing model fair YES probability, converts it to log odds, applies bounded evidence shifts, enforces per-cluster and total adjustment caps, limits low-confidence/no-primary-source adjustments, applies contradiction penalties, clamps probabilities, and recalculates YES/NO edge. If base fair probability is unavailable, the engine reports insufficient data instead of inventing an anchored probability.

### AI / web-search / local LLM clarity

OpenAI web search is disabled by default unless every explicit provider and operator-approval gate is configured. Manual evidence mode is available by default. Local LLM review does not browse the web by itself; it can only analyze app-provided evidence packets. AI summaries can be wrong, citations must be reviewed, source weighting does not prove truth, and corroboration does not prove certainty.

## Key routes

- `/` — root dashboard
- `/v3` or `/operator-os` — Operator Intelligence OS
- `/v3/opportunities` or `/opportunities` — Opportunity Review Workbench
- `/v3/markets/{market_id_or_slug}` or `/market/{market_id_or_slug}` — Market Detail / Opportunity Review
- `/v3/markets/family/{family_id}` — Market Family Comparison
- `/api/v3/opportunities` — workbench JSON
- `/api/v3/opportunities/reviews` — review-record list
- `/api/v3/opportunities/review/{market_id_or_slug}` — review-record summary
- `/api/v3/opportunities/review/{market_id_or_slug}/notes` — operator notes update API
- `/api/v3/opportunities/review/{market_id_or_slug}/status` — review-status update API
- `/api/v3/markets/{market_id_or_slug}/summary` — market drilldown JSON
- `/api/v3/markets/family/{family_id}/summary` — family comparison JSON
- `/v3/ai` or `/ai` — AI Copilot
- `/v3/ai/edge` or `/edge` — AI Edge Research
- `/v3/ai/edge/packets` — AI Edge packet list
- `/v3/ai/news-odds` or `/news-odds` — AI News Odds Adjustment Engine
- `/v3/arbitrage` or `/arbitrage` — Cross-Market Arbitrage review
- `/v3/ai/news-odds/run` — search planning/manual evidence workflow
- `/v3/ai/news-odds/adjustments` — draft fair odds adjustment records
- `/v3/ai/news-odds/source-weights` — source weights and corroboration explanation
- `/v2-live`, `/live`, `/live-controls` — v2 live-control compatibility surface
- `/v3/platform` or `/platform` — platform diagnostics
- `/system-map` or `/routes` — route map and alias inventory

## Edge, opportunity, and AI News Odds settings

Safe defaults are included in `.env.example`:

```bash
EDGE_MIN_YES_PP=2.0
EDGE_MIN_NO_PP=2.0
EDGE_REQUIRE_FRESH_DATA=true
EDGE_SHOW_FAVORITE_RANK=true
EDGE_SHOW_FAMILY_GROUPS=true
EDGE_SHOW_AI_EDGE_ACTIONS=true
EDGE_DEFAULT_RECOMMENDATION_MODE=review_only
OPPORTUNITY_REVIEW_ENABLED=true
OPPORTUNITY_NOTES_ENABLED=true
OPPORTUNITY_REVIEW_STORE=runtime/opportunity_reviews
EDGE_DETAIL_PAGES_ENABLED=true
EDGE_FAMILY_PAGES_ENABLED=true
AI_EDGE_PACKET_LIFECYCLE_ENABLED=true
AI_EDGE_REVIEW_ONLY=true
WATCHLIST_REVIEW_ONLY=true
PAPER_REVIEW_DRAFT_ONLY=true
AI_ODDS_ADJUSTMENT_ENABLED=true
AI_ODDS_ADJUSTMENT_MODE=conservative
AI_DEFAULT_MAX_ADJUSTMENT_PCT=2.5
AI_BALANCED_MAX_ADJUSTMENT_PCT=7.5
AI_AGGRESSIVE_MAX_ADJUSTMENT_PCT=15.0
AI_ABSOLUTE_HARD_CAP_PCT=25.0
AI_REQUIRE_EXTRA_EVIDENCE_ABOVE_PCT=5.0
AI_REQUIRE_OPERATOR_CONFIRM_ABOVE_PCT=10.0
AI_ALLOW_CAP_EXCEED_WITH_EVIDENCE=false
AI_NEWS_ODDS_ENABLED=true
AI_NEWS_ODDS_WEB_SEARCH_ENABLED=false
AI_NEWS_ODDS_MANUAL_EVIDENCE_ENABLED=true
AI_NEWS_ODDS_LOCAL_LLM_ENABLED=false
AI_NEWS_ODDS_REVIEW_ONLY=true
AI_NEWS_ODDS_REQUIRE_HUMAN_ACCEPT=true
AI_NEWS_ODDS_CAN_PLACE_ORDERS=false
AI_NEWS_ODDS_CAN_CANCEL_ORDERS=false
AI_NEWS_ODDS_CAN_ARM_LIVE=false
AI_NEWS_ODDS_MAX_ADJUSTMENT_PP=8.0
AI_NEWS_ODDS_MAX_CLUSTER_ADJUSTMENT_PP=3.0
KALSHI_ENABLED=false
KALSHI_API_BASE_URL=https://external-api.kalshi.com/trade-api/v2
KALSHI_API_KEY_ID=
KALSHI_PRIVATE_KEY_PATH=
ARBITRAGE_SCANNER_ENABLED=false
ARBITRAGE_REVIEW_ONLY=true
ARBITRAGE_FETCH_ORDERBOOKS=false
ARBITRAGE_MIN_NET_MARGIN_PCT=1.0
ARBITRAGE_MIN_CONFIDENCE=0.72
ARBITRAGE_MAX_STALE_SECONDS=300
ARBITRAGE_SCAN_INTERVAL_SECONDS=300
```

These settings only label and store draft research/review context. They do not change live trading gates or approve orders.

To enable larger AI odds adjustments, set `AI_ODDS_ADJUSTMENT_MODE=balanced`, `aggressive`, or `custom`. In custom mode, `AI_NEWS_ODDS_MAX_ADJUSTMENT_PP` remains the backward-compatible custom cap. The absolute hard cap still clamps every mode.

To enable live read-only arbitrage scans, set `ARBITRAGE_SCANNER_ENABLED=true` and enable specific venues such as `KALSHI_ENABLED=true`. The app still starts with Kalshi disabled or credentials missing; authenticated Kalshi calls remain unavailable until `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` are configured.

## Safety philosophy

This package is not autonomous trading software. Live order submission remains guarded by backend safety gates, approval checkboxes, warning acknowledgements, typed confirmation phrases, read-only state, live armed state, kill-switch state, risk checks, and audit logging. Paper trading remains local simulation. Demo data is fake and must not be presented as real market data. AI, market-edge, opportunity review, calibration, command-palette, keyboard-shortcut, task, cockpit, guided review, migration, plugin, and route-alias outputs cannot place or cancel orders and cannot approve trades.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open the app, create the initial admin user, then visit `/v3`, `/v3/opportunities`, `/v2-live`, `/v3/ai`, `/v3/ai/edge`, `/v3/platform`, and `/system-map`.

## Documentation index

- [Release Notes](docs/RELEASE_NOTES_v4.7.0-real.md)
- [Release Notes v4.15](docs/RELEASE_NOTES_v4.15.0-real.md)
- [Operator Acceptance Checklist](docs/OPERATOR_ACCEPTANCE_CHECKLIST.md)
- [Stub Burn-down Map v4.15](docs/STUB_BURNDOWN_MAP_v4.15.0-real.md)
- [Validation Notes v4.15](docs/VALIDATION_v4.15.0-real.md)
- [Functional Completion Guide v4.15](docs/V4_FUNCTIONAL_COMPLETION_GUIDE_v4.15.0-real.md)
- [Feature Readiness Workflow Guide v4.15](docs/V4_FEATURE_READINESS_WORKFLOW_GUIDE_v4.15.0-real.md)
- [Review Queue Workflow Guide v4.15](docs/V4_REVIEW_QUEUE_WORKFLOW_GUIDE_v4.15.0-real.md)
- [Opportunity Review Workflow Guide v4.15](docs/V4_OPPORTUNITY_REVIEW_WORKFLOW_GUIDE_v4.15.0-real.md)
- [Configurable AI Odds Adjustment Guide v4.15](docs/V4_CONFIGURABLE_AI_ODDS_ADJUSTMENT_GUIDE_v4.15.0-real.md)
- [Cross-Market Arbitrage Guide v4.15](docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.15.0-real.md)
- [Operator Notes v4.15](docs/OPERATOR_NOTES_v4.15.0-real.md)
- [Release Notes v4.14](docs/RELEASE_NOTES_v4.14.0-real.md)
- [Stub Burn-down Map v4.14](docs/STUB_BURNDOWN_MAP_v4.14.0-real.md)
- [Validation Notes v4.14](docs/VALIDATION_v4.14.0-real.md)
- [Functional Completion Guide v4.14](docs/V4_FUNCTIONAL_COMPLETION_GUIDE_v4.14.0-real.md)
- [Feature Readiness Workflow Guide v4.14](docs/V4_FEATURE_READINESS_WORKFLOW_GUIDE_v4.14.0-real.md)
- [Opportunity Review Workflow Guide v4.14](docs/V4_OPPORTUNITY_REVIEW_WORKFLOW_GUIDE_v4.14.0-real.md)
- [Configurable AI Odds Adjustment Guide v4.14](docs/V4_CONFIGURABLE_AI_ODDS_ADJUSTMENT_GUIDE_v4.14.0-real.md)
- [Cross-Market Arbitrage Guide v4.14](docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.14.0-real.md)
- [Operator Notes v4.14](docs/OPERATOR_NOTES_v4.14.0-real.md)
- [Release Notes v4.13](docs/RELEASE_NOTES_v4.13.0-real.md)
- [Stub Burn-down Map v4.13](docs/STUB_BURNDOWN_MAP_v4.13.0-real.md)
- [Validation Notes v4.13](docs/VALIDATION_v4.13.0-real.md)
- [Functional Completion Guide v4.13](docs/V4_FUNCTIONAL_COMPLETION_GUIDE_v4.13.0-real.md)
- [Configurable AI Odds Adjustment Guide v4.13](docs/V4_CONFIGURABLE_AI_ODDS_ADJUSTMENT_GUIDE_v4.13.0-real.md)
- [Cross-Market Arbitrage Guide v4.13](docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.13.0-real.md)
- [Operator Notes v4.13](docs/OPERATOR_NOTES_v4.13.0-real.md)
- [Release Notes v4.12](docs/RELEASE_NOTES_v4.12.0-real.md)
- [Stub Burn-down Map v4.12](docs/STUB_BURNDOWN_MAP_v4.12.0-real.md)
- [Validation Notes v4.12](docs/VALIDATION_v4.12.0-real.md)
- [Functional Completion Guide v4.12](docs/V4_FUNCTIONAL_COMPLETION_GUIDE_v4.12.0-real.md)
- [Configurable AI Odds Adjustment Guide v4.12](docs/V4_CONFIGURABLE_AI_ODDS_ADJUSTMENT_GUIDE_v4.12.0-real.md)
- [Cross-Market Arbitrage Guide v4.12](docs/V4_CROSS_MARKET_ARBITRAGE_GUIDE_v4.12.0-real.md)
- [Release Notes v4.11](docs/RELEASE_NOTES_v4.11.0-real.md)
- [Stub Burn-down Map v4.11](docs/STUB_BURNDOWN_MAP_v4.11.0-real.md)
- [Validation Notes v4.11](docs/VALIDATION_v4.11.0-real.md)
- [Functional Completion Guide v4.11](docs/V4_FUNCTIONAL_COMPLETION_GUIDE_v4.11.0-real.md)
- [Validation Notes](docs/VALIDATION_v4.7.0-real.md)
- [AI News Odds Adjustment Engine Guide](docs/V4_AI_NEWS_ODDS_ADJUSTMENT_ENGINE_GUIDE_v4.7.0-real.md)
- [Source Weighting and Corroboration Guide](docs/V4_SOURCE_WEIGHTING_AND_CORROBORATION_GUIDE_v4.7.0-real.md)
- [News Evidence Packet Guide](docs/V4_NEWS_EVIDENCE_PACKET_GUIDE_v4.7.0-real.md)
- [AI News Search Provider Guide](docs/V4_AI_NEWS_SEARCH_PROVIDER_GUIDE_v4.7.0-real.md)
- [Fair Probability Adjustment Guide](docs/V4_FAIR_PROBABILITY_ADJUSTMENT_GUIDE_v4.7.0-real.md)
- [AI News Odds Prompt Governance Guide](docs/V4_AI_NEWS_ODDS_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md)
- [Opportunity Review Workbench Guide](docs/V4_OPPORTUNITY_REVIEW_WORKBENCH_GUIDE_v4.7.0-real.md)
- [Market Detail Drilldown Guide](docs/V4_MARKET_DETAIL_DRILLDOWN_GUIDE_v4.7.0-real.md)
- [Market Family Comparison Guide](docs/V4_MARKET_FAMILY_COMPARISON_GUIDE_v4.7.0-real.md)
- [AI Edge Packet Lifecycle Guide](docs/V4_AI_EDGE_PACKET_LIFECYCLE_GUIDE_v4.7.0-real.md)
- [Operator Notes and Review Records Guide](docs/V4_OPERATOR_NOTES_AND_REVIEW_RECORDS_GUIDE_v4.7.0-real.md)
- [Watchlist and Paper Review Queue Guide](docs/V4_WATCHLIST_AND_PAPER_REVIEW_QUEUE_GUIDE_v4.7.0-real.md)
- [Market Edge Recommendation Guide](docs/V4_MARKET_EDGE_RECOMMENDATION_GUIDE_v4.7.0-real.md)
- [Favorite vs Edge Guide](docs/V4_FAVORITE_VS_EDGE_GUIDE_v4.7.0-real.md)
- [Market Family Ranking Guide](docs/V4_MARKET_FAMILY_RANKING_GUIDE_v4.7.0-real.md)
- [AI Edge Research Guide](docs/V4_AI_EDGE_RESEARCH_GUIDE_v4.7.0-real.md)
- [AI Web Search Research Guide](docs/V4_AI_WEB_SEARCH_RESEARCH_GUIDE_v4.7.0-real.md)
- [OpenAI Integration Guide](docs/V4_OPENAI_INTEGRATION_GUIDE_v4.7.0-real.md)
- [Local LLM Runtime Guide](docs/V4_LOCAL_LLM_RUNTIME_GUIDE_v4.7.0-real.md)
- [AI Prompt Governance Guide](docs/V4_AI_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md)
- [AI Safety and Privacy Guide](docs/V4_AI_SAFETY_AND_PRIVACY_GUIDE_v4.7.0-real.md)
- [Unified Navigation Guide](docs/V4_UNIFIED_NAVIGATION_GUIDE_v4.7.0-real.md)
- [System Map Guide](docs/V4_SYSTEM_MAP_GUIDE_v4.7.0-real.md)
- [Platform Architecture Guide](docs/V4_PLATFORM_ARCHITECTURE_GUIDE_v4.7.0-real.md)
- [Visual QA Checklist](docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md)
- [Manual QA Checklist](docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md)
- [Release Checklist](docs/RELEASE_CHECKLIST_v4.7.0-real.md)

## History preservation

The package keeps v2, v3, v4.0 through v4.15 docs, tests, and compatibility surfaces in place. v4.15 completes Review Queue browser action persistence and preserves opportunity review data-mode/data-state/audit hardening while preserving v4.13 arbitrage scan-recording/data-state workflow, v4.12 AI odds/arbitrage review workflows, v4.11 stub burn-down truthfulness, v4.8 configurable AI odds/arbitrage, v4.7 AI News Odds, and v4.6 opportunity-review workflow without removing live trading features, paper trading features, risk controls, audit logging, emergency controls, kill switches, read-only controls, route aliases, AI Copilot, OpenAI/local LLM settings, platform diagnostics, migration planner, plugin manifests, task planner, guided workspace, cockpit, dataset/freshness, simulation, analytics, research, monitoring, portfolio, or governance modules.

## No-secrets warning

Never place real private keys, API keys, wallet secrets, auth headers, credentials, sensitive account data, runtime ledgers, AI responses, web-search responses, screenshots with secrets, local logs, `.env`, venvs, node modules, or local `data/` runtime records in a release ZIP. Use `.env.example` only with placeholders.
