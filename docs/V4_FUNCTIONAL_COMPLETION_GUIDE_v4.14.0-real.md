# Functional Completion Guide - v4.14.0-real

v4.14 keeps the visible-control rule: a visible action must work, navigate to a real route, persist local state, export data, or clearly explain preview/config-required/disabled behavior.

## Completed in v4.14

- Opportunity Review Workbench data mode is explicit and cannot silently depend on an unchecked checkbox.
- Workbench rows label `sample`, `cached`, `live`, `stale`, or `unavailable` data state.
- Notes and review-status forms persist source route/component, previous/new state, reason, data state, freshness, and no-live-mutation audit fields.
- JSON review APIs accept the same source metadata as browser forms.
- Market detail pages show data state and enriched audit history.
- Feature readiness and stub burn-down rows describe opportunity review actions as local review metadata only.

## Still Partial by Design

- Polymarket live read breadth depends on network/API availability.
- Kalshi is disabled/config-required by default.
- Import/restore paths remain deliberately gated.
- Browser screenshot QA is still manual unless a local QA run is performed.

