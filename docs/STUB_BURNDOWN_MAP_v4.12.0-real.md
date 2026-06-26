# Stub Burn-down Map - v4.12.0-real

The live map is available at `/api/v3/features/stub-burndown` and is surfaced in the cockpit readiness section.

## v4.12 Changes

- AI odds review is now marked working for the browser workflow scope: plan feedback, manual evidence preview feedback, saved draft adjustments, detail review, and accept/reject/archive actions.
- Arbitrage review is working for local review decisions: review, watchlist, ignore, reject, redirect feedback, and audit persistence.
- Feature readiness includes an `operator_acceptance` object for cockpit, AI odds, arbitrage, settings, readiness, live execution, and Kalshi.

## Current Honest Statuses

- Polymarket discovery/pricing/orderbook: partial. Live reads depend on network/API availability and freshness.
- AI news odds: working for review-only draft adjustment workflow; web search remains config-gated.
- AI Edge research: working for draft research packets.
- YES/NO recommendation clarity: working as review-only guidance.
- Arbitrage scanner/review: partial by default because live scanner is disabled; review workflow is working.
- Kalshi: disabled/config-required by default.
- Venue registry: partial; future competitors are disabled scaffolds.
- Review queue and audit log: working where local runtime storage exists.
- Cockpit layouts/focus: working.
- Settings/config: working.
- Export/import: partial; export coverage is broad while restore/import is deliberately gated.
- Live execution controls: disabled/gated by default.
