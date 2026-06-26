# Stub Burn-down Map - v4.13.0-real

The live map is available at `/api/v3/features/stub-burndown` and is surfaced in readiness views.

## v4.13 Changes

- Added `operator_implication`, `next_action`, `data_state`, `safe_review_only`, and `live_disabled` to each readiness row.
- Added `data_state_values`: `live`, `cached`, `sample`, `stale`, `unavailable`.
- Added `error` to the status vocabulary for venue/API failures that should not be hidden behind generic unavailable language.
- Marked the default arbitrage scanner data state as `sample` when the scanner is disabled and deterministic fixtures are used.
- Clarified that Kalshi and future venues are disabled/config-required/scaffolded until deliberately configured and tested.

## Current Honest Statuses

- Polymarket discovery/pricing/orderbook: partial. Live reads depend on network/API availability and freshness.
- AI news odds: working for review-only draft adjustment workflow; web search remains config-gated.
- AI Edge research: working for draft research packets.
- YES/NO recommendation clarity: working as review-only guidance.
- Arbitrage scanner/review: partial by default because live scanner is disabled; scan recording and review actions are working local workflows.
- Kalshi: disabled/config-required by default.
- Venue registry: partial; future competitors are disabled scaffolds.
- Review queue and audit log: working where local runtime storage exists.
- Cockpit layouts/focus: working.
- Settings/config: working.
- Export/import: partial; export coverage is broad while restore/import is deliberately gated.
- Live execution controls: disabled/gated by default.

