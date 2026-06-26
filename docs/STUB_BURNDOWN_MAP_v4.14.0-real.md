# Stub Burn-down Map - v4.14.0-real

The live map is available at `/api/v3/features/stub-burndown` and is surfaced in readiness views.

## v4.14 Changes

- The review queue row now calls out opportunity review data-state/source metadata.
- Opportunity review actions are marked working with local JSONL persistence, POST-backed browser forms, and enriched audit fields.
- The map keeps `operator_implication`, `next_action`, `data_state`, `safe_review_only`, and `live_disabled` on each readiness row.
- Data-state values remain `live`, `cached`, `sample`, `stale`, and `unavailable`.
- Kalshi and future venues remain disabled/config-required/scaffolded until deliberately configured and tested.

## Current Honest Statuses

- Opportunity review actions: working for local notes/watchlist/paper-review/reject/archive workflow; live execution is disabled.
- Review queue and audit log: working where local runtime storage exists.
- Cross-market arbitrage scanner/review: partial by default because live scanner is disabled; scan recording and review actions remain working local workflows.
- AI news odds: working for review-only draft adjustment workflow; web search remains config-gated.
- AI Edge research: working for draft research packets.
- Polymarket discovery/pricing/orderbook: partial. Live reads depend on network/API availability and freshness.
- Kalshi: disabled/config-required by default.
- Venue registry: partial; future competitors are disabled scaffolds.
- Cockpit layouts/focus: working.
- Settings/config: working.
- Export/import: partial; export coverage is broad while restore/import is deliberately gated.
- Live execution controls: disabled/gated by default.

