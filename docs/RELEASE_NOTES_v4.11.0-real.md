# Release Notes - v4.11.0-real

v4.11.0-real is a stub burn-down, end-to-end wiring, and functional truthfulness pass.

## Added

- `/api/v3/features/stub-burndown` with operator-facing statuses for working, partial, config-required, scaffolded, disabled, unavailable, needs-tests, needs-UI-wiring, needs-backend-wiring, and needs-docs surfaces.
- Stub burn-down coverage for Polymarket discovery/pricing/orderbook, AI odds, AI Edge, YES/NO recommendation clarity, arbitrage, Kalshi, venue registry, review queue, audit, cockpit layouts/focus modes, task/workspace review, settings/config, feature readiness, export/import, launch helpers, and live execution controls.
- Cockpit System Readiness table surfacing for the stub burn-down map.
- Browser POST wrappers and operator feedback redirects for v3 Workspace and AI actions that were previously exposed as POST-only API hrefs.
- Focused regression tests for burn-down coverage, endpoint rendering, cockpit surfacing, POST-only href removal, and page POST feedback.

## Changed

- `/api/v3/features/status` now nests the same stub burn-down map under `stub_burndown`.
- Workspace daily review, weekly review, and task triage controls are visible forms.
- AI provider dry-run, AI Edge packet generation, AI Edge evidence normalization preview, and AI review-packet generation are visible forms.

## Safety

No autonomous trading, order placement, order cancellation, live arming, trade approval, signing, kill-switch bypass, read-only bypass, secret export, or financial-advice behavior was added.
