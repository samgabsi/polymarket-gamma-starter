# Validation - v4.11.0-real

Validation target: stub burn-down coverage, v3 Workspace/AI POST-control wiring, cockpit readiness surfacing, route/action honesty, and preserved safety gates.

## Automated

Run:

```bash
python -m pytest
python scripts/check_versions.py
python scripts/generate_operator_manual.py
```

Observed in this package:

- `python -m pytest -q` under a fresh local verification venv: `182 passed, 2875 warnings in 483.88s`.
- `python scripts/check_versions.py`: passed.
- `python scripts/generate_operator_manual.py`: passed and generated v4.11 route inventory, API schema inventory, runtime migration template, and operator manual.

Expected highlights:

- `APP_VERSION` is `4.11.0-real`.
- `/api/v3/features/status` returns the feature status registry and nested `stub_burndown`.
- `/api/v3/features/stub-burndown` returns the operator-facing burn-down map without secrets.
- `/v3/cockpit` renders the Stub Burn-down Map table.
- `/v3/workspace` no longer exposes POST-only workspace start endpoints as hrefs.
- `/v3/ai` no longer exposes POST-only AI action endpoints as hrefs.
- Browser POST wrappers redirect with `action_status` feedback.

## Manual Route Smoke

Open:

- `/`
- `/v3`
- `/v3/cockpit`
- `/v3/workspace`
- `/v3/tasks`
- `/v3/ai`
- `/v3/ai/edge`
- `/v3/ai/news-odds`
- `/v3/arbitrage?demo=true`
- `/settings`
- `/settings/configuration`
- `/api/v3/features/status`
- `/api/v3/features/stub-burndown`

Confirm visible actions either submit, navigate, export, or state why they are disabled/config-required.

## Known Limits

The package does not guarantee complete live market coverage. Polymarket live reads depend on network/API availability. Kalshi and arbitrage live scans remain config-gated. Live execution stays disabled/gated by default.
