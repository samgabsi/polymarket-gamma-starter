# Functional Completion Guide - v4.12.0-real

v4.12 keeps the visible-control rule: a visible action must work, navigate to a real route, persist local state, export data, or clearly explain preview/config-required/disabled behavior.

## Completed in v4.12

- AI News Odds page forms no longer drop the operator into raw JSON for browser workflows.
- Saved AI odds draft adjustments redirect to detail pages with feedback.
- AI odds review decisions persist locally and the detail lookup returns the latest decision record.
- Arbitrage candidate actions now cover review, watchlist, ignore, and reject states.
- Global operator feedback appears for redirected workflow actions.

## Still Partial by Design

- Polymarket live read breadth depends on network/API availability.
- Kalshi is disabled/config-required by default.
- Import/restore paths remain deliberately gated.
- Browser screenshot QA is still manual unless a local QA run is performed.
