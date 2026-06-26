# Validation Notes - v4.13.0-real

## Automated Coverage Added

- `tests/test_operator_workflows_v413.py`
  - Confirms `/v3/arbitrage` surfaces data state, feature readiness, and `Record scan snapshot`.
  - Confirms the page POST scan-recording workflow redirects with feedback and writes scan/audit JSONL rows.
  - Confirms `/api/v3/arbitrage/scan` exposes scanner status, data state, sample-data, readiness, and enriched venue status fields.
  - Confirms `POST /api/v3/arbitrage/scan/record` persists a scan without live mutation.
  - Confirms candidate review audit rows include source route/component, target id/name, previous/new state, scan id, data state, review-only, and live-disabled fields.
  - Confirms feature-status and stub burn-down maps include `operator_implication`, `next_action`, `data_state`, `safe_review_only`, `live_disabled`, `data_state_values`, and `error`.

## Existing Coverage Preserved

- AI odds browser workflow feedback, draft adjustment persistence, accept/reject/archive actions, and no-live-mutation assertions.
- Cross-market arbitrage math, resolution mismatch classification, disabled Kalshi posture, and review-only candidate actions.
- Cockpit layout/focus persistence, settings/configuration rendering, feature readiness surfacing, route inventory, API contracts, and live-control safety gates.

## Manual QA Still Recommended

- Browser screenshot QA across desktop and mobile.
- Manual clickthrough after packaging.
- Live Polymarket/Kalshi read checks only in an explicitly configured safe environment.

## Known Warnings

The test environment may show framework deprecation warnings depending on local Python/FastAPI/Starlette versions. Treat assertion failures as blockers; warnings alone do not prove a workflow failed.

