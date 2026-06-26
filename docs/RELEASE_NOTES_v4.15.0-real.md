# Release Notes - v4.15.0-real

Target version: `4.15.0-real`.

v4.15.0-real is a Pro Extended functional-completion and operator-workflow pass. It completes the v3 Settings / Feature Readiness workflow while preserving the v4.15 Review Queue and Feature Readiness acknowledgement work present in the source.

## Settings / Feature Readiness workflow

- `/v3/settings` now shows grouped, editable UI-safe preference rows instead of only raw settings output.
- Settings rows expose runtime value, saved preference, effective operator value, source, restart-required state, validation metadata, and review-only/live-disabled flags.
- The browser form posts through `POST /v3/settings/preferences/save` and redirects back with operator feedback.
- `GET /api/v3/settings` and `POST /api/v3/settings` support contract-safe reads/writes for UI-safe preferences.
- Invalid numeric inputs are rejected without overwriting the previous saved preferences.
- Secret-backed values are masked or unavailable for browser saves; no secret values are echoed.
- Settings saves and rejections write local v3 event/audit rows with source route/component, previous/new state, runtime-env-not-mutated, review-only, and live-disabled metadata.
- `settings.v3_operator_preferences` is reported through feature readiness and the stub burn-down map.

## Review Queue and Feature Readiness preservation

- `/review-queue` remains backed by local POST actions for review-only operator decisions.
- `/api/review-queue`, `/api/review-queue/actions`, and `POST /api/review-queue/{market_id}/action` continue to expose persisted decisions and audit metadata.
- `/v3/feature-readiness` remains a review surface for feature-status and stub burn-down rows, with local acknowledgement records.
- Feature status distinguishes working, partial, config-required, scaffolded, disabled, unavailable, and error states where applicable.

## Safety posture

No autonomous execution was added. The settings workflow does not mutate `.env` files or process environment variables. Review Queue decisions, Feature Readiness acknowledgements, Opportunity Review actions, AI odds drafts, and arbitrage reviews remain local review-only metadata. They do not place orders, cancel orders, approve trades, arm live trading, bypass backend gates, or provide financial advice.

## Targeted validation

- `python -m py_compile app/main.py app/live_v3.py app/feature_status.py app/config.py app/review_queue.py`
- `PYTHONPATH=. pytest -q tests/test_operator_settings_v415.py --maxfail=1`
- `PYTHONPATH=. pytest -q tests/test_operator_workflows_v415.py --maxfail=1`
- `PYTHONPATH=. pytest -q tests/test_feature_readiness_v415.py --maxfail=1`
- `PYTHONPATH=. pytest -q tests/test_operator_workflows_v414.py tests/test_operator_workflows_v413.py tests/test_operator_workflows_v412.py tests/test_stub_burndown_v411.py --maxfail=1`
