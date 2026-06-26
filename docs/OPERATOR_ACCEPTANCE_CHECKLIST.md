# Operator Acceptance Checklist - v4.17.0-real

This checklist reflects current package behavior. It is not a roadmap and does not claim external venues, live execution, or AI approval are complete.

Status legend: Pass means the workflow is wired and covered by automated or direct route checks. Partial means the visible workflow is honest but depends on external configuration, live network state, or manual browser QA. Disabled means the feature is intentionally unavailable by default.

## v4.17 Acceptance Run Summary

| Area | Status | Evidence | Operator implication |
| --- | --- | --- | --- |
| Launch and main routes | Pass | Version metadata and route tests are retained; startup/import validation is part of release validation. | Launch helpers remain local and do not enable live trading. |
| Cockpit layout/focus | Pass | Existing cockpit tests cover layout selection, persistence, focus navigation, saved layouts, and readiness surfacing. | Cockpit actions are workflow aids only. |
| Feature readiness | Pass | `/api/v3/features/status` and `/api/v3/features/stub-burndown` include status, reason, operator implication, next action, data state, safe review-only, live-disabled, and error-status support. | Operators can distinguish working, partial, config-required, scaffolded, disabled, unavailable, and error states before trusting visible controls. |
| Settings/configuration | Pass | v4.15 settings tests remain passing and v4.17 exposes paper-trading UI-safe preferences through `/v3/settings`. | Process-level env changes still require restart; `/v3/settings` saves local operator preferences only and does not mutate `.env` or process env. |
| AI odds review | Pass | v4.12 workflow tests still cover page feedback, saved draft adjustments, detail review, accept/reject/archive, and review-only safety. | AI odds output is review context, not market manipulation, financial advice, or order approval. |
| Review Queue / operator action | Pass | v4.15 tests cover Review Queue page action wiring, browser POST feedback, API persistence, audit fields, persisted state, and readiness truthfulness. | Mark reviewed/watchlist/paper-review/dismiss are local review records only and preserve source/data-state metadata. |
| Opportunity review / operator action | Pass | v4.15 tests cover explicit data-mode UI, sample data-state labeling, browser status POST persistence, JSON notes/status metadata, enriched audit history, and readiness truthfulness. | Notes/watchlist/paper-review/reject/archive are local review records only and preserve source/data-state metadata. |
| Cross-market arbitrage review | Pass | v4.13 tests still cover data-state UI/API fields, visible scan snapshot recording, review actions, and enriched audit metadata. | Sample scans are labeled sample; live read-only interpretation requires deliberate venue configuration. |
| Kalshi | Disabled/Config-required | Feature readiness and arbitrage venue status label Kalshi disabled by default unless `KALSHI_ENABLED=true`. | Missing Kalshi credentials do not crash startup and do not imply live data coverage. |
| Audit/review persistence | Pass | Review Queue actions, opportunity review records, scan snapshots, and candidate decisions write local JSONL audit rows with source route, target, state transition, reason, data state, review-only, and live-disabled fields. | Runtime records are local operator evidence and are excluded from release ZIPs. |
| Automated paper trading | Pass | v4.17 tests cover `/v3/paper-trading`, paper-only safety banners, run-once/reset routes, simulated fills, ledger updates, risk rejections, audit rows, and feature readiness. | Paper automation can be enabled separately from live trading and never submits or cancels real orders. |
| No automatic live execution | Pass | Safety fields and tests assert no order submission, cancellation, trade approval, or live arming. | The package remains fail-closed and human-in-the-loop. |
| Browser screenshot QA | Partial | Automated route tests cover rendering; screenshot QA remains a manual or local Playwright run. | Use screenshot QA before relying on visual layout polish across devices. |

## Launch and Main Routes

- [x] Start the app with `python run.py`.
- [x] Open `/` and confirm the dashboard renders after setup/login.
- [x] Open `/v3` and confirm the Operator Intelligence OS renders.
- [x] Open `/api/v3/features/status` and `/api/v3/features/stub-burndown` and confirm statuses are explicit.

## Cockpit Workflow

- [x] Open `/v3/cockpit`.
- [x] Select each visible cockpit layout card and confirm the selected state changes.
- [x] Refresh `/v3/cockpit` and confirm the selected layout persists.
- [x] Start a focused review mode and confirm it switches the related layout and navigates to the focus route.
- [x] Save the current layout copy and confirm a local layout record is selected.
- [x] Confirm cockpit actions are labeled as workflow aids only and do not submit orders.

## Feature Readiness

- [x] Open `/v3/feature-readiness` and confirm the page renders.
- [x] Filter readiness rows by status and area.
- [x] Confirm the page explains cached/local data state, review-only posture, live-disabled posture, and no-order behavior.
- [x] Submit Record readiness review and confirm redirect feedback.
- [x] Confirm `/api/v3/features/readiness/acknowledgements` returns the local acknowledgement row.
- [x] Confirm acknowledgement records do not enable disabled/scaffolded/config-required features.
- [x] Confirm Cockpit System Readiness displays feature status and stub burn-down tables.
- [x] Confirm working, partial, disabled, config-required, scaffolded, unavailable, and error labels are present where applicable.
- [x] Confirm disabled, scaffolded, config-required, and error rows include reason, operator implication, and next action.
- [x] Confirm data state is one of `live`, `cached`, `sample`, `stale`, or `unavailable` where applicable.
- [x] Confirm live execution remains disabled/gated by default.

## Settings and Configuration

- [x] Open `/v3/settings` and confirm the Settings / Feature Readiness workflow renders.
- [x] Confirm grouped AI odds adjustment, arbitrage scanner, and Kalshi UI-safe preferences are visible.
- [x] Confirm each settings row shows runtime value, saved preference, effective operator value, value source, and restart-required state.
- [x] Save a UI-safe preference through `POST /v3/settings/preferences/save` and confirm redirect feedback.
- [x] Refresh `/v3/settings` or call `/api/v3/settings` and confirm the saved preference is reflected as `ui_preference`.
- [x] Submit an invalid numeric value and confirm the value is rejected without overwriting the previous saved preference.
- [x] Confirm secrets are masked/unavailable and are not echoed in browser or API responses.
- [x] Confirm settings saves write local audit/event rows but do not mutate `.env`, process environment variables, place orders, approve trades, or arm live trading.
- [x] Confirm missing credentials show config-required/default-safe state rather than crashing.
- [x] Open `/settings/configuration` when deeper schema-backed env editing is needed and confirm process-level env changes still require restart.

## AI Odds Review

- [x] Open `/v3/ai/news-odds`.
- [x] Open `/v3/ai/news-odds/run`.
- [x] Open `/v3/markets/demo_france_world_cup/news-odds`.
- [x] Confirm market price, model fair price, AI-adjusted fair price, raw adjustment, evidence-weighted adjustment, final adjustment, cap decision, confidence, and recommended side are visible.
- [x] Use Plan search and confirm redirect feedback.
- [x] Use Preview manual evidence and confirm redirect feedback without claiming persistence.
- [x] Use Save draft adjustment and confirm the saved adjustment detail page opens.
- [x] On the detail page, confirm Accept to review context, Reject draft, and Archive draft forms are visible.
- [x] Submit one review action and confirm feedback plus persisted local action state.
- [x] Confirm AI odds output is advisory, review-only, not financial advice, and not an order or trade approval.

## Review Queue / Operator Action

- [x] Open `/review-queue`.
- [x] Confirm data state and review-only/live-disabled safety posture are visible.
- [x] Confirm Mark reviewed, Watchlist, Send to paper review, and Dismiss are real POST-backed forms.
- [x] Submit one Review Queue action and confirm redirect feedback.
- [x] Refresh `/review-queue` or call `/api/review-queue` and confirm persisted review status is reflected.
- [x] Open `/api/review-queue/actions` and confirm the local action/audit row exists.
- [x] Confirm the row includes source route/component, previous/new state, data state, review-only, live-disabled, order_submitted=false, and trade_approved=false.
- [x] Confirm Review Queue actions do not place orders, cancel orders, approve trades, or arm live trading.

## Opportunity Review / Operator Action

- [x] Open `/v3/opportunities?demo=true`.
- [x] Confirm the Data mode control is a select with Demo fixtures and Configured local/live source choices.
- [x] Confirm no `name="demo"` checkbox is rendered on the opportunity workbench.
- [x] Confirm top-level and row-level data state are visible.
- [x] Confirm sample fixtures are labeled `sample`.
- [x] Save operator notes and confirm redirect feedback.
- [x] Submit Add to Watchlist, Send to Paper Review, Reject, or Archive and confirm redirect feedback.
- [x] Open `/v3/markets/demo_france_world_cup` and confirm audit history shows previous/new state, data state, and source component.
- [x] Confirm JSON notes/status APIs accept source route, source component, data state, freshness, and reason.
- [x] Confirm review records are local runtime records and are excluded from release ZIPs.

## Cross-Market Arbitrage Review

- [x] Open `/v3/arbitrage?demo=true`.
- [x] Confirm scanner status, venue status, Polymarket status, Kalshi status, and data state are visible.
- [x] Confirm demo/sample fixture state is explicit when demo mode is used.
- [x] Confirm Kalshi is disabled/config-required unless deliberately configured.
- [x] Record a scan snapshot and confirm redirect feedback plus local scan/audit persistence.
- [x] If candidates exist, confirm gross margin, fees, slippage, liquidity, net margin, confidence/equivalence, mismatch risk, and risk flags are visible.
- [x] Submit Send to review queue, Add to watchlist, Ignore for now, or Reject/ignore and confirm redirect feedback.
- [x] Confirm action persistence in the local arbitrage audit file where runtime storage is enabled.
- [x] Confirm candidates are not presented as guaranteed profit and no automatic execution is possible.

## Audit and Review

- [x] Confirm review actions either persist local runtime records or clearly state preview/config-required behavior.
- [x] Confirm audit records exist where infrastructure is present: cockpit, AI odds, arbitrage, opportunity review, and live-control-adjacent actions.
- [x] Confirm visible operator-impacting actions include timestamp/source/target/state/data-state metadata where the subsystem has audit infrastructure.
- [x] Confirm runtime records are excluded from release ZIPs.

## No Automatic Live Execution

- [x] Confirm no workflow places orders, cancels orders, approves trades, signs transactions, arms live trading, disables read-only mode, disables kill switch controls, or bypasses backend gates.
- [x] Confirm live execution controls remain gated or disabled unless every existing manual backend safety gate is explicitly satisfied.

## Automated Paper Trading v4.17

- [x] Open `/v3/paper-trading`.
- [x] Confirm the page shows `Paper trading only`, `No real orders will be placed`, and `live_execution_used=false` safety posture.
- [x] Confirm run-once is disabled with a clear reason when `PAPER_TRADING_ENABLED=false` or `PAPER_TRADING_AUTOMATION_ENABLED=false`.
- [x] Enable `PAPER_TRADING_ENABLED=true` and `PAPER_TRADING_AUTOMATION_ENABLED=true`.
- [x] Submit `Run paper strategy once` and confirm redirect feedback.
- [x] Confirm the last run summary shows candidates considered, paper trades placed, rejected/skipped counts, simulated notional, and data state.
- [x] Confirm recent orders and fills are marked `paper_only=true` and `live_execution_used=false`.
- [x] Confirm open paper positions and simulated P/L update locally.
- [x] Confirm rejected candidates produce decision rows with risk reasons.
- [x] Confirm `/api/v3/paper/status`, `/account`, `/orders`, `/fills`, `/positions`, `/decisions`, and `/audit` return explicit paper-only safety flags.
- [x] Confirm reset only resets the local paper account/positions and does not mutate live/exchange state.
- [x] Confirm no real order placement, real order cancellation, live arming, or kill-switch bypass occurs.
