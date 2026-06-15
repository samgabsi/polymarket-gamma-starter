# Live Order Intent Preview (v0.5.6-real)

Live Order Intent Preview is the first staged order-shape layer after live configuration readiness. It lets an operator populate future live-order fields and save a local dry-run preview that can be reviewed and audited before any execution adapter exists.

This feature is intentionally non-executing. It does **not** derive credentials, sign messages, submit orders, cancel orders, connect wallets, bypass paper approvals, or automate trading.

## What an intent captures

Each saved intent preview records:

- `market_id`
- optional future `token_id` / CLOB asset ID
- `outcome`
- `side` (`BUY` or `SELL`)
- `order_type` (`limit` or `marketable_limit`)
- `time_in_force` (`GTC`, `FOK`, or `FAK`)
- `price`
- `size`
- computed `notional`
- optional source paper `ticket_id` and approval ID
- operator label and note
- live configuration guard snapshot
- blockers and warnings

## Guard checks

The preview checks the staged live-configuration fields from `.env` and blocks future live-readiness when guard posture is unsafe. Current checks include:

- `READ_ONLY` must remain true while there is no execution adapter.
- `LIVE_DRY_RUN_ONLY` must remain true.
- `LIVE_REQUIRE_MANUAL_APPROVAL` must remain true.
- `LIVE_PRETRADE_CHECKS_ENABLED` must remain true.
- `LIVE_AUDIT_REQUIRED` must remain true.
- `LIVE_MAX_ORDER_NOTIONAL` must be deliberately set above zero and the preview notional must not exceed it.
- `LIVE_ALLOWED_MARKET_IDS` must include the preview market before it can be marked ready for manual review.

Credential presence is reported as a warning, not a blocker, because this build cannot place orders.

## Browser routes

```http
GET  /live-order-intents
GET  /api/live/order-intents
GET  /api/live/order-intents/{intent_id}
GET  /api/live/order-intents.csv
POST /api/live/order-intents/preview
POST /api/live/order-intents
```

`POST /api/live/order-intents/preview` returns a preview without saving it. `POST /api/live/order-intents` saves the preview to the local ledger.

## CLI examples

```bash
python3 -m app.cli --live-order-intents
python3 -m app.cli --preview-live-order-intent \
  --live-intent-market <market_id> \
  --live-intent-token-id <token_id> \
  --live-intent-price 0.45 \
  --live-intent-size 5 \
  --json
python3 -m app.cli --record-live-order-intent \
  --live-intent-market <market_id> \
  --live-intent-token-id <token_id> \
  --live-intent-price 0.45 \
  --live-intent-size 5 \
  --live-intent-note "manual preview only"
python3 -m app.cli --export-live-order-intents live_order_intents.csv
```

## Audit behavior

Saved previews appear in the unified audit ledger under category `live_order_intent`.

The ledger entry is documentation only. It does not prove a trade was placed, approved, or executable.

## Current limitation

This layer only prepares order intent shape and guard checks. Later stages still need authenticated client validation, order-intent-to-approval binding, deterministic pre-trade risk checks, dry-run adapter tests, explicit manual authorization, and a separate execution adapter before any live action path exists.

## v0.5.7 follow-on: live-intent preflight

`v0.5.7-real` adds a separate read-only preflight review for saved intent previews. Use `/live-order-intent-preflight` or `python3 -m app.cli --live-order-intent-preflight --json` to verify explicit paper ticket binding, explicit paper approval binding, current paper preflight, token ID presence, and live guard state before any future execution-capable build is considered.

## v0.5.11 follow-on: operator authorization snapshots

`v0.5.11-real` adds `/live-order-authorizations`, a local ledger for explicit human authorization/reject/defer snapshots after live-intent preflight. It preserves operator review state for future staged live testing without signing, submitting, cancelling, or automating orders.
