# Live Trading Configuration Readiness

Version: v0.9.0-real

This iteration starts the staged live-readiness path without adding live execution. It exposes a redacted configuration-readiness surface for future Polymarket/CLOB identity fields, CLOB L2 credential fields, guard switches, and live risk-limit placeholders.

## What it adds

- UI: `/live-config`
- API:
  - `GET /api/live/config/readiness`
  - `GET /api/live/config/readiness.csv`
  - `GET /api/live/config/template.env`
- CLI:
  - `--live-config-readiness`
  - `--export-live-config-readiness live_config_readiness.csv`
  - `--export-live-config-template live_config_template.env`

## Important boundary

This is a configuration and readiness layer only. It does not:

- derive or create CLOB credentials
- sign messages
- place live orders
- cancel live orders
- subscribe to private user streams
- bypass paper approvals, preflight, risk budget, audit, or operator closeout controls
- provide investment advice

## Field groups

### Runtime gates

- `APP_MODE`
- `READ_ONLY`
- `LIVE_TRADING_ENABLED`
- `LIVE_DRY_RUN_ONLY`
- `LIVE_REQUIRE_MANUAL_APPROVAL`
- `LIVE_PRETRADE_CHECKS_ENABLED`
- `LIVE_AUDIT_REQUIRED`

For v0.5.6, the intended safe posture is still:

```env
APP_MODE=read_only
READ_ONLY=true
LIVE_TRADING_ENABLED=false
LIVE_DRY_RUN_ONLY=true
LIVE_REQUIRE_MANUAL_APPROVAL=true
LIVE_PRETRADE_CHECKS_ENABLED=true
LIVE_AUDIT_REQUIRED=true
```

### Polymarket identity and credential placeholders

- `POLY_ADDRESS`
- `POLYMARKET_WALLET_ADDRESS` alias
- `POLYMARKET_FUNDER_ADDRESS`
- `POLYMARKET_CHAIN_ID`
- `POLY_PRIVATE_KEY`
- `POLYMARKET_PRIVATE_KEY` alias
- `POLY_API_KEY`
- `POLYMARKET_CLOB_API_KEY` alias
- `CLOB_API_KEY` alias
- `POLY_SECRET`
- `POLYMARKET_CLOB_SECRET` alias
- `CLOB_SECRET` alias
- `POLY_PASSPHRASE`
- `POLYMARKET_CLOB_PASSPHRASE` alias
- `CLOB_PASSPHRASE` alias

Secret values are never returned by the UI, API, or CLI. The readiness report only shows configured/missing status plus a redacted mask for configured secret fields.

### Future live risk placeholders

- `LIVE_MAX_ORDER_NOTIONAL`
- `LIVE_MAX_MARKET_NOTIONAL`
- `LIVE_MAX_DAILY_NOTIONAL`
- `LIVE_MAX_OPEN_ORDERS`
- `LIVE_ALLOWED_MARKET_IDS`

The default numeric values are `0` so a later execution adapter can treat the safest state as blocking live order fanout until the operator deliberately sets limits.

### Live adapter boundary fields

The live-readiness path includes these readiness-only fields:

- `POLYMARKET_LIVE_MODE`
- `POLYMARKET_LIVE_NETWORK_READONLY`
- `POLYMARKET_LIVE_ENABLE_SUBMIT`
- `POLYMARKET_LIVE_ENABLE_CANCEL`
- `POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH`
- `POLYMARKET_LIVE_KILL_SWITCH`
- `POLYMARKET_LIVE_REQUIRE_DRY_RUN_RECEIPT`
- `POLYMARKET_LIVE_READONLY_TIMEOUT_SECONDS`
- `POLYMARKET_CLOB_HOST`
- `POLYMARKET_SIGNATURE_TYPE`

They feed `/live-adapter`, adapter request validation, and manual execution review scaffolding. They do not enable live order submission or cancellation in this release.

## Operator workflow

1. Open `/live-config` or run `python3 -m app.cli --live-config-readiness`.
2. Export a blank local template with `python3 -m app.cli --export-live-config-template live_config_template.env`.
3. Copy the needed fields into your local `.env` only.
4. Restart the app and verify that the readiness report shows configured fields without exposing values.
5. Do not treat configured credentials as execution readiness. v0.9.0 can record optional read-only validation, local adapter/manual review records, fake-local attempt receipts, and local market-data quality records, but real live submission and cancellation still require a later explicit implementation.

## Safe packaging rule

Do not package `.env`, populated templates, credential files, user databases, session files, local paper state, local live attempt ledgers, generated market-data snapshots, generated simulations, or cache directories. The v0.9.0 ZIP includes only code, docs, and blank examples.
