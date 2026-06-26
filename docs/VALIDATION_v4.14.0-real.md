# Validation Notes - v4.14.0-real

## Automated Coverage Added

- `tests/test_operator_workflows_v414.py`
  - Confirms version identity is `4.14.0-real`.
  - Confirms the opportunity workbench labels demo fixtures as `sample`.
  - Confirms `/v3/opportunities?demo=true` uses an explicit `select name="demo"` data-mode control and no longer renders a `name="demo"` checkbox.
  - Confirms browser review actions persist previous/new state, source route/component, data state, safe-review-only, live-disabled, and no-live-mutation fields.
  - Confirms market detail renders enriched audit history after a browser action.
  - Confirms JSON notes/status APIs accept and persist source metadata.
  - Confirms feature-status and stub burn-down maps report opportunity review actions truthfully.

## Existing Coverage Preserved

- v4.13 arbitrage scan recording, data-state surfacing, enriched arbitrage audit fields, readiness schema fields, and no-live-mutation assertions.
- v4.12 AI odds browser feedback, draft adjustment persistence, accept/reject/archive actions, and review-only safety.
- v4.11 stub burn-down coverage and cockpit/system readiness surfacing.
- v4.6 opportunity review routes, market detail pages, AI Edge packet lifecycle, family comparison, and review-only safety.

## Manual QA Still Recommended

- Browser screenshot QA across desktop and mobile.
- Manual clickthrough of `/v3/opportunities`, `/v3/markets/demo_france_world_cup`, `/v3/ai/news-odds`, `/v3/arbitrage`, `/settings/configuration`, and `/v3/cockpit`.
- Live Polymarket/Kalshi read checks only in an explicitly configured safe environment.

## Known Warnings

The local Python/FastAPI/Starlette stack can emit deprecation warnings. Assertion failures are blockers; warnings alone do not prove a workflow failed.

