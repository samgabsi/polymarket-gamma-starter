# Live Adapter Requests

v0.6.0 adds adapter request validation after unsigned execution packets and offline dry-run receipts.

The feature converts a saved unsigned execution packet into an adapter-shaped request preview, validates it against strict local schema and safety gates, and records a local validation result. It does not sign, submit, cancel, call the network, touch wallets, or create exchange acknowledgements.

## UI

Open:

```text
/live-adapter-requests
```

The page lists ready execution packets and saved adapter request validation records.

## API

```text
GET  /live-adapter-requests
GET  /api/live/adapter/requests
GET  /api/live/adapter/requests/{request_or_packet_id}
GET  /api/live/adapter/requests.csv
POST /api/live/execution-packets/{packet_id}/adapter-request/preview
POST /api/live/execution-packets/{packet_id}/adapter-request
```

Preview builds the validation without saving. Record saves to `data/live/live_adapter_requests.json`.

## CLI

```bash
python -m app.cli --live-adapter-requests --json
python -m app.cli --preview-live-adapter-request --live-adapter-request-packet-id lep_abc123 --json
python -m app.cli --record-live-adapter-request --live-adapter-request-packet-id lep_abc123 --live-adapter-note "schema check"
python -m app.cli --live-adapter-request-detail lar_abc123 --json
python -m app.cli --export-live-adapter-requests live_adapter_requests.csv
```

Useful filters:

```text
--live-adapter-request-status
--live-adapter-request-packet-id
--live-execution-packet-intent-id
--live-intent-market
--live-adapter-operator
```

## Validation checks

The validator checks:

- execution packet exists
- packet hash matches current packet fields
- operator authorization exists and is acknowledged
- authorization decision/status allows carry-forward
- preflight snapshot is ready or ready-with-warnings
- current offline dry-run receipt exists when required
- token ID and market ID are present
- side, order type, and time-in-force are valid
- price is a valid decimal greater than 0 and less than 1
- size is a valid decimal greater than zero
- notional is within `LIVE_MAX_ORDER_NOTIONAL`
- market is present in `LIVE_ALLOWED_MARKET_IDS`
- kill switch is not active
- manual auth remains required
- no signed payload, exchange acknowledgement, or network submission exists

## Request states

- `adapter_request_ready`: adapter request shape and gates are ready for manual review, but not submitted.
- `adapter_request_ready_with_warnings`: shape is ready with warnings.
- `blocked_by_missing_packet`: packet was not found.
- `blocked_by_missing_authorization`: authorization is missing or not acceptable.
- `blocked_by_preflight`: preflight snapshot is not ready.
- `blocked_by_dry_run`: dry-run receipt is missing, stale, or unsafe.
- `blocked_by_kill_switch`: kill switch is active.
- `blocked_by_risk_limit`: notional/allowlist/risk gates block the request.
- `blocked_by_invalid_order_fields`: order payload shape is invalid.
- `blocked_by_submit_disabled`: submit configuration is off, which is the safe default.
- `invalid`: other safety blockers exist.

## Safety boundary

Adapter request records keep these flags false:

```text
order_submission_enabled=false
network_submission_attempted=false
signed_payload_present=false
exchange_acknowledgement=false
order_cancellation_enabled=false
secret_values_returned=false
```

`blocked_by_submit_disabled` is expected in the safe default posture. It means the request shape can be inspected locally, not that any live order can be placed.
