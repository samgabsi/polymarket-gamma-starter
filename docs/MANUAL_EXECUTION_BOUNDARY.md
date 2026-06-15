# Manual Execution Boundary

v0.6.0 adds manual execution review scaffolding after adapter request validation.

This is a local final-review/checklist record for future manual live execution design. It is not order placement. It does not sign payloads, submit orders, cancel orders, call the network, touch wallets, or receive exchange acknowledgements.

## UI

Open:

```text
/manual-execution-boundary
```

The page lists adapter request candidates and saved manual execution review records.

## API

```text
GET  /manual-execution-boundary
GET  /api/live/manual-execution-reviews
GET  /api/live/manual-execution-reviews/{review_id}
GET  /api/live/manual-execution-reviews.csv
POST /api/live/execution-packets/{packet_id}/manual-execution-review/preview
POST /api/live/execution-packets/{packet_id}/manual-execution-review
```

Record saves to `data/live/manual_execution_reviews.json`.

## CLI

```bash
python -m app.cli --manual-execution-reviews --json
python -m app.cli --preview-manual-execution-review --manual-execution-review-packet-id lep_abc123 --json
python -m app.cli --record-manual-execution-review --manual-execution-review-packet-id lep_abc123 --manual-execution-ack --live-adapter-note "final local review"
python -m app.cli --manual-execution-review-detail mer_abc123 --json
python -m app.cli --export-manual-execution-reviews manual_execution_reviews.csv
```

## Checklist

Manual execution review records snapshot:

- adapter request readiness
- manual authorization requirement
- kill switch state
- final local acknowledgement
- signed payload absence
- network-not-attempted flag
- submission implementation absence

## Review states

- `manual_execution_review_ready`: local checklist is complete, but nothing was submitted.
- `manual_execution_review_ready_with_warnings`: checklist is complete with warnings.
- `operator_final_confirmation_required`: final local acknowledgement is missing.
- `execution_submission_disabled`: submit is disabled, which is the safe default.
- `blocked_by_kill_switch`: kill switch is active.
- `blocked_by_adapter_request`: adapter request validation is not ready.

## Safety boundary

Manual execution reviews always keep:

```text
execution_submission_disabled=true
not_submitted=true
network_not_attempted=true
network_submission_attempted=false
signed_payload_present=false
exchange_acknowledgement=false
order_submission_enabled=false
order_cancellation_enabled=false
secret_values_returned=false
```

Any future real manual submission path should be implemented separately, with explicit operator confirmation, kill switch checks, risk enforcement, audit writes, and tests.
