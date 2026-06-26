# Release Notes - v4.13.0-real

Target version: `4.13.0-real`.

v4.13.0-real is an arbitrage review and feature-readiness truthfulness pass. It keeps the v4.12 AI odds and arbitrage review workflows and completes the next highest-value gap: a visible, persisted, audited scan snapshot workflow with explicit data-state labeling.

## Operator Workflow Completed

- `/v3/arbitrage` now exposes a `Record scan snapshot` POST action.
- `POST /v3/arbitrage/scan/record` records the current scan filters, writes a local scan JSONL row, writes an audit row, and redirects with feedback.
- `POST /api/v3/arbitrage/scan/record` gives API clients the same persisted scan behavior without relying on the GET `write` query flag.
- Scan JSON now reports `scanner_status`, `scanner_status_reason`, `data_state`, `data_state_reason`, `sample_data`, `persisted`, `scanner_readiness`, and enriched venue statuses.

## Feature Truthfulness

- Feature-status and stub burn-down rows now include `operator_implication`, `next_action`, `data_state`, `safe_review_only`, and `live_disabled`.
- Status values now explicitly include `error`.
- Data-state values are standardized as `live`, `cached`, `sample`, `stale`, and `unavailable`.
- The arbitrage page shows relevant readiness rows for scanner, review actions, Polymarket, Kalshi, venue registry, audit, settings, and live execution posture.

## Safety

No autonomous execution was added. Scan recording and candidate decisions are local review records only. Sample/demo data is labeled as sample. Arbitrage candidates remain not guaranteed profits and never place orders, cancel orders, approve trades, or arm live trading.

