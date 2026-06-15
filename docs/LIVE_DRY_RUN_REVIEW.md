# Live Dry-Run Review Board

v0.5.11 adds a read-only reconciliation board after offline dry-run adapter receipts.

The board compares each saved unsigned live execution packet with its latest saved dry-run receipt. It is deterministic local reporting only. It does **not** derive credentials, sign payloads, submit orders, cancel orders, touch wallets, send network requests, authorize trading, or automate execution.

## UI

Open:

```text
/live-dry-run-review
```

The page lists saved execution packets and the current review state of their latest dry-run receipt.

## API

```text
GET /api/live/dry-run-review
GET /api/live/dry-run-review/{packet_id}
GET /api/live/dry-run-review.csv
```

The API is derived from existing local packet and dry-run receipt files. It does not create a new state file.

## CLI

```bash
python -m app.cli --live-dry-run-review --json
python -m app.cli --live-dry-run-review --live-dry-run-review-state needs_dry_run_receipt
python -m app.cli --live-dry-run-review-detail lep_abc123 --json
python -m app.cli --export-live-dry-run-review live_dry_run_review.csv
```

Useful filters:

```text
--live-dry-run-review-state
--live-dry-run-packet-id
--live-execution-packet-intent-id
--live-intent-market
--live-intent-operator
```

## Review states

- `validated_ready`: latest receipt matches the current packet hash and has no warnings.
- `validated_with_warnings`: latest receipt matches the current packet hash, but packet or receipt warnings need human review.
- `needs_dry_run_receipt`: packet exists and is packageable, but no dry-run receipt has been saved.
- `stale_dry_run_receipt`: latest receipt no longer matches the current packet hash, status, intent, or authorization snapshot.
- `dry_run_blocked`: latest receipt is blocked or reports unsafe dry-run flags.
- `packet_blocked`: saved packet is not currently suitable for dry-run review.
- `invalid`: saved packet metadata is malformed.

## Safety boundary

This board is not an approval and not an execution precheck for a live adapter. It is an operator-facing report to make missing, stale, blocked, and validated dry-run evidence visible before any future execution-capable build exists.

`execution_allowed`, `network_available`, `order_submission_enabled`, `order_cancellation_enabled`, and `autonomous_trading_enabled` remain false.
