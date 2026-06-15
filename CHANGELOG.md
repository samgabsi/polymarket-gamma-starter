# Changelog

## v2.1.0-real

- Redesigned the Live v2 UI into a cleaner, faster operator console with compact task navigation.
- Added a persistent status bar showing version, mode, live armed state, read-only state, kill switch, readiness, Gamma/CLOB posture, refresh time, and recent critical issue.
- Reworked dashboard, markets, trade ticket, orders, positions, risk, audit, settings, emergency, and docs areas with progressive disclosure and explicit refresh actions.
- Added settings schema/validation endpoints and a grouped settings UI that never returns secret values.
- Added Markdown audit export and in-app markdown docs serving.
- Added UI route smoke tests and validation tests while preserving all v2.0 live-trading backend gates and fail-closed defaults.

## v2.0.0-real

- Added guarded Live Trading v2 console and API namespace.
- Added live readiness checklist covering credentials, wallet derivability, SDK/runtime, risk limits, kill switch, read-only mode, real-network permission, submit/cancel gates, and CLOB adapter boundary.
- Added live trade-ticket preview, risk checks, approval requirement, warning acknowledgement, typed confirmation, real CLOB adapter submit/cancel handoff, emergency controls, and local v2 audit ledger exports.
- Added live market discovery, CLOB order-book fetch, read-only open-order/position visibility, and reconciliation endpoints.
- Added v2 environment variables and optional live dependency guidance.
- Preserved v1.9 settings UX, research, paper workflows, data ingestion, training, existing live-readiness/manual-control routes, and fail-closed defaults.

## v1.9.0-real

- Streamlined settings and configuration UX with settings hub, configuration console, setup wizard, runtime status, and audit history.
