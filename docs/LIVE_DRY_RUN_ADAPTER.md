# Live Dry-Run Adapter Receipts

v0.5.11 adds an offline adapter dry-run layer after live execution packets.

The feature is intentionally non-executing. It validates saved unsigned execution packets against an adapter-shaped request/response contract and records local receipts for audit/review. It does **not** derive credentials, sign payloads, submit orders, cancel orders, touch wallets, send network requests, or automate trading.

## UI

Open:

```text
/live-dry-run-adapter
```

The page lists ready unsigned execution packets and saved dry-run receipts. A receipt can be recorded from a ready packet after operator review.

## API

```text
GET  /api/live/dry-run-adapter
GET  /api/live/dry-run-adapter/{receipt_id}
GET  /api/live/dry-run-adapter.csv
POST /api/live/execution-packets/{packet_id}/dry-run/preview
POST /api/live/execution-packets/{packet_id}/dry-run
```

The preview endpoint builds a receipt without saving. The record endpoint saves a local receipt under `data/live/live_dry_run_adapter_receipts.json`.

## CLI

```bash
python -m app.cli --live-dry-run-adapter --json
python -m app.cli --preview-live-dry-run-adapter --live-dry-run-packet-id lep_abc123 --json
python -m app.cli --record-live-dry-run-adapter --live-dry-run-packet-id lep_abc123 --live-intent-operator sam --live-intent-note "offline check"
python -m app.cli --live-dry-run-receipt-detail ldr_abc123 --json
python -m app.cli --export-live-dry-run-adapter live_dry_run_adapter_receipts.csv
```

Useful filters:

```text
--live-dry-run-status
--live-dry-run-packet-id
--live-execution-packet-intent-id
--live-intent-market
--live-intent-operator
```

## Receipt states

- `dry_run_validated`: packet shape and guard posture passed with no warnings.
- `dry_run_validated_with_warnings`: packet shape passed, but warnings should be reviewed.
- `blocked_by_packet`: packet is missing, not ready, signed, acknowledged, malformed, or otherwise not suitable for offline adapter validation.
- `blocked_by_guard`: live guard settings are unsafe for this stage, such as dry-run-only or read-only controls being disabled.
- `invalid`: source packet could not be found or inputs are invalid.

## Receipt contents

Each receipt snapshots:

- packet ID/hash/status
- intent ID and authorization ID/hash
- preflight state
- source ticket and approval IDs
- market/token/order fields
- offline adapter request preview
- offline adapter response preview
- live guard snapshot
- blockers and warnings
- deterministic receipt hash

## Safety boundary

A receipt is local evidence only. It is not an order, not a signature, not a CLOB acknowledgement, and not an authorization for autonomous execution.

`execution_allowed`, `network_attempted`, `signed_payload_present`, `exchange_acknowledgement`, `order_submission_enabled`, `order_cancellation_enabled`, and `autonomous_trading_enabled` remain false.

## v0.5.11 follow-on: dry-run review board

`v0.5.11-real` adds `/live-dry-run-review`, a read-only reconciliation board that compares saved unsigned execution packets with their latest offline dry-run receipts. It flags missing receipts, stale receipt snapshots, blocked receipts, and current validated receipts without creating approvals or enabling execution.
