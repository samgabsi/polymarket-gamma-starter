# Feature Readiness Workflow Guide - v4.15.0-real

v4.15.0-real adds a first-class Feature Readiness review page at `/v3/feature-readiness`. The page is a local, truthful operator workflow for checking whether visible surfaces are working, partial, config-required, scaffolded, disabled, unavailable, or erroring before relying on them.

## What the workflow does

1. Reads the same feature-status registry used by the cockpit and `/api/v3/features/status`.
2. Reads the same stub burn-down map exposed by `/api/v3/features/stub-burndown`.
3. Lets the operator filter by status and feature area.
4. Shows operator implications, next actions, data-state labels, review-only badges, and live-disabled badges.
5. Records a local JSONL acknowledgement when the operator confirms the current rows were reviewed.

## What the workflow does not do

- It does not enable disabled or scaffolded features.
- It does not probe live venues.
- It does not reveal secrets.
- It does not submit, cancel, approve, or arm trades.
- It does not imply a partial/config-required feature is operational.

## Browser workflow

Open `/v3/feature-readiness`, optionally choose a status and area filter, inspect both tables, add an operator note, then select **Record readiness review**. The page redirects with `Feature Readiness Acknowledged` feedback and shows the new acknowledgement in the recent acknowledgement table.

## API workflow

- `GET /api/v3/features/readiness` returns filtered feature rows, stub rows, counts, data-state metadata, safety flags, and recent acknowledgement records.
- `GET /api/v3/features/readiness/acknowledgements` returns local acknowledgement rows.
- `POST /api/v3/features/readiness/acknowledgements` records a local acknowledgement with status/area filters, reason, source route/component, counts reviewed, review-only flags, and no-live-mutation fields.

## Audit fields

Acknowledgements include timestamp, action type, operator, target id/name, previous/new state, reason, status/area filters, counts reviewed, source route/component, data state, data freshness, review-only, live-disabled, no-order-submitted, no-order-cancelled, no-trade-approved, and no-live-trading-armed fields.

## Verification

Run:

```bash
PYTHONPATH=. pytest -q tests/test_feature_readiness_v415.py --maxfail=1
```

The test verifies page rendering, filter behavior, acknowledgement persistence, API safety flags, secret-safe responses, and status-map truthfulness.
