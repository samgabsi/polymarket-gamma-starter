# Review Queue Workflow Guide - v4.15.0-real

The Review Queue is a review-only operator workflow. Its actions persist local review metadata and audit rows only. They do not place orders, cancel orders, approve trades, arm live trading, disable read-only mode, bypass backend gates, or provide financial advice.

## Browser workflow

1. Open `/review-queue` for configured/local source mode or `/review-queue?demo=true` for clearly labeled demo fixtures.
2. Confirm the data-state card says configured source, cached, sample, stale, unavailable, or demo fixture as appropriate.
3. Review the item title, edge, confidence, risk, evidence, stage/action, and persisted review status.
4. Use one of the row actions: Add to Watchlist, Send to Paper Review, Needs More Evidence, Mark Reviewed, Reject, or Archive.
5. Confirm the redirect feedback banner shows `Recorded` and the new review status.
6. Refresh or reopen `/api/review-queue` to confirm the persisted status is reflected.
7. Inspect `/api/review-queue/actions` or `/api/review-queue/audit` for local JSONL action and audit rows.

## API workflow

- `GET /api/review-queue?demo=true` returns a review-only workflow payload with data-state labels, available actions, persisted review status, and safety flags.
- `POST /api/review-queue/{market_id}/action` records one local operator action and returns the decision, action record, and audit event.
- `GET /api/review-queue/actions` lists local Review Queue action records.
- `GET /api/review-queue/audit` lists local Review Queue audit events.

## Persisted audit fields

Review Queue action records include timestamp, feature area, action type, target id/name, previous state, new state, reason, source route, source component, data state, freshness, review-only, safe-review-only, live-disabled, no-live-mutation, and no-order-submitted fields.

## Data-state meanings

- `sample`: deterministic demo fixtures for workflow validation.
- `cached`: local/runtime or cached opportunity data, not a fresh external venue read.
- `live`: configured read-only data was returned; it still requires market-rule, freshness, liquidity, and operator review.
- `stale`: stale data only.
- `unavailable`: no usable configured source is available.

## Safety posture

Review Queue actions are local operator workflow metadata. They cannot approve, submit, cancel, or arm live trading.
