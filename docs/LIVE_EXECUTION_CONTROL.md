# Live Execution Control

Version: v0.9.0-real

The manual live execution control plane is the final local boundary after live order intent preview, live preflight, operator authorization, unsigned execution packet creation, offline dry-run receipt creation, and live adapter request validation.

It adds:

- Final manual submit preview and attempt records.
- Manual cancel preview and attempt records.
- A local execution attempt ledger at `data/live/live_execution_attempts.json`.
- Deterministic attempt hashes.
- Fake-local submit/cancel receipts for no-network validation.
- Staleness checks for authorizations, dry-run receipts, adapter requests, and packet/preflight bindings.
- Kill-switch, submit-enabled, cancel-enabled, fake-adapter, final-confirmation, risk-limit, and market-allowlist gates.
- Unified audit categories for readiness, derived submit/cancel previews, saved submit/cancel attempts, and fake-local receipts.

Real live submit and cancel are implemented only through the guarded CLOB adapter boundary. `real_live` adapter mode calls the SDK only after every manual gate passes; normal validation never runs it.

## Routes

```text
GET  /api/live/execution-control/readiness
GET  /api/live/execution-control/readiness.csv
GET  /api/live/execution-attempts
GET  /api/live/execution-attempts.csv
GET  /api/live/execution-attempts/{attempt_id}
POST /api/live/adapter/requests/{adapter_request_id}/manual-submit/preview
POST /api/live/adapter/requests/{adapter_request_id}/manual-submit
POST /api/live/manual-cancel/preview
POST /api/live/manual-cancel
```

UI pages:

```text
/live-manual-execution
/live-execution-attempts
/live-manual-cancel
```

## Safety posture

The default posture is blocked:

- `POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=false`
- `POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED=false`
- `POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED=false`
- no final confirmation phrase configured
- no real adapter implementation
- no autonomous loop
- no signing
- no wallet mutation
- no network submit/cancel

This software is not financial advice. Operators must understand Polymarket and CLOB risks before enabling any live-facing configuration.
