# Live Adapter Readiness

v0.6.0 adds a live adapter boundary report for future Polymarket CLOB operation.

This is not live trading. It reports redacted configuration, capability, optional read-only validation state, and safety gates. It does not derive credentials, sign payloads, submit orders, cancel orders, touch wallets, or automate execution.

## UI

Open:

```text
/live-adapter
```

The page shows live mode, kill switch, read-only validation, credential-presence booleans, redacted public identifiers, allowed/blocked operations, blockers, warnings, latest validation receipt, and next operator action.

## API

```text
GET  /api/live/adapter/readiness
GET  /api/live/adapter/readiness.csv
GET  /api/live/adapter/readonly-validations
GET  /api/live/adapter/readonly-validations/{validation_id}
GET  /api/live/adapter/readonly-validations.csv
POST /api/live/adapter/readonly-validation/preview
POST /api/live/adapter/readonly-validation
```

Preview builds a local validation result without saving. Record saves to `data/live/live_adapter_readonly_validations.json`.

## CLI

```bash
python -m app.cli --live-adapter-readiness --json
python -m app.cli --preview-live-adapter-readonly-validation --json
python -m app.cli --record-live-adapter-readonly-validation --live-adapter-note "operator check"
python -m app.cli --live-adapter-readonly-validations
python -m app.cli --live-adapter-validation-detail lav_abc123 --json
python -m app.cli --export-live-adapter-readiness live_adapter_readiness.csv
python -m app.cli --export-live-adapter-validations live_adapter_validations.csv
```

## Environment fields

The adapter boundary reads these fields in addition to existing live config fields:

```text
POLYMARKET_LIVE_MODE=false
POLYMARKET_LIVE_NETWORK_READONLY=false
POLYMARKET_LIVE_ENABLE_SUBMIT=false
POLYMARKET_LIVE_ENABLE_CANCEL=false
POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH=true
POLYMARKET_LIVE_KILL_SWITCH=false
POLYMARKET_LIVE_REQUIRE_DRY_RUN_RECEIPT=true
POLYMARKET_LIVE_READONLY_TIMEOUT_SECONDS=4
POLYMARKET_CLOB_HOST=https://clob.polymarket.com
POLYMARKET_SIGNATURE_TYPE=
```

`POLYMARKET_LIVE_NETWORK_READONLY` is default-off. When enabled, validation degrades safely if `py_clob_client` is missing or credentials are incomplete. Validation output is redacted and never includes secrets.

## Readiness states

- `offline_safe_default`: default local posture; no network or execution.
- `config_incomplete`: live/read-only config was requested but required local readiness is incomplete.
- `dependency_missing`: read-only validation was requested but the optional CLOB client dependency is missing.
- `readonly_ready`: latest recorded read-only validation was successful.
- `readonly_validation_failed`: latest recorded read-only validation failed.
- `manual_execution_configured_but_disabled`: submit was requested in config, but this release still does not submit.
- `blocked_by_kill_switch`: kill switch is active.
- `unsafe_submit_config`: submit/cancel/manual-auth settings need review.
- `ready_for_manual_execution_review`: enough redacted readiness exists for manual review scaffolding, not live submission.

## Safety boundary

Readiness and validation records always report:

```text
order_submission_enabled=false
order_cancellation_enabled=false
autonomous_execution_enabled=false
secret_values_returned=false
```

Network validation is never attempted unless explicitly enabled. Live order submission and cancellation are not implemented in v0.6.0.
