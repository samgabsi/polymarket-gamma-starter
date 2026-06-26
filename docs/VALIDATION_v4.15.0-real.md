# Validation Notes - v4.15.0-real

## Version identity

- `VERSION` reads `4.15.0-real`.
- `app.config.APP_VERSION` reads `4.15.0-real`.
- `scripts/check_versions.py` expects `4.15.0-real`.

## Functional workflow validated

### v3 Settings / Feature Readiness

- `/v3/settings` renders the Settings / Feature Readiness workflow.
- Editable settings rows show runtime value, saved preference, source, restart-required state, and control type.
- `POST /v3/settings/preferences/save` persists UI-safe preferences and redirects with feedback.
- `POST /api/v3/settings` rejects invalid numeric values and preserves the prior saved state.
- Saved preferences are reflected after refresh/remount through `GET /api/v3/settings`.
- Settings saves and rejections write local v3 event/audit records.
- No secrets are returned and no process environment or `.env` values are mutated.

### Review Queue / Feature Readiness regression coverage

- `/review-queue` POST-backed actions still persist local decisions and audit rows.
- `/v3/feature-readiness` still filters feature/status rows and records local acknowledgement records.
- Feature readiness reports the settings workflow, Review Queue, and live execution posture truthfully.

## Targeted commands

```bash
python -m py_compile app/main.py app/live_v3.py app/feature_status.py app/config.py app/review_queue.py
PYTHONPATH=. pytest -q tests/test_operator_settings_v415.py --maxfail=1
PYTHONPATH=. pytest -q tests/test_operator_workflows_v415.py --maxfail=1
PYTHONPATH=. pytest -q tests/test_feature_readiness_v415.py --maxfail=1
PYTHONPATH=. pytest -q tests/test_operator_workflows_v414.py tests/test_operator_workflows_v413.py tests/test_operator_workflows_v412.py tests/test_stub_burndown_v411.py --maxfail=1
python scripts/check_versions.py
```

## Safety validation

- Settings saves do not place orders, cancel orders, approve trades, arm live trading, mutate `.env`, or mutate process environment variables.
- Review Queue and Feature Readiness actions remain local metadata only.
- Missing Kalshi credentials remain safe and are represented as disabled/config-required/scaffolded status rather than app-start blockers.
