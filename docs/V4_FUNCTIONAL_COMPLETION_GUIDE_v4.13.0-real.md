# Functional Completion Guide - v4.13.0-real

v4.13 keeps the visible-control rule: a visible action must work, navigate to a real route, persist local state, export data, or clearly explain preview/config-required/disabled behavior.

## Completed in v4.13

- Arbitrage scan persistence is now a visible POST-backed browser action with redirect feedback.
- Arbitrage scan JSON makes sample/live/unavailable data state explicit.
- Arbitrage review audit rows include source route/component, target, state transition, reason, scan id, data state, review-only, and live-disabled metadata.
- Feature readiness rows now include operator implication and next action.
- The data-mode selector replaces the ambiguous demo checkbox.

## Still Partial by Design

- Polymarket live read breadth depends on network/API availability.
- Kalshi is disabled/config-required by default.
- Import/restore paths remain deliberately gated.
- Browser screenshot QA is still manual unless a local QA run is performed.

