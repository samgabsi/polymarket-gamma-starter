# Live CLOB Adapter

Version: 1.0.0-real

The CLOB adapter is the only module allowed to call the Polymarket trading SDK. All routes, CLI commands, UI pages, and autonomous workflows must go through the existing manual control plane and adapter boundary.

## v1.0.0 manual-live implementation

`v1.0.0-real` implements manual live submit/cancel mapping for the `py-clob-client` runtime:

- `ClobClient(host, chain_id, key, creds, signature_type, funder)`
- `ApiCreds(api_key, api_secret, api_passphrase)`
- `OrderArgs(token_id, price, size, side)`
- `create_order(...)`
- `post_order(..., OrderType.GTC/FOK/...)`
- `cancel(order_id)`
- `get_order(order_id)` and `get_orders(OpenOrderParams())` where available

Normal status checks and automated validation do not construct signed payloads, submit orders, cancel orders, or contact the CLOB. Real SDK calls are reached only from the record path when all live gates pass.

## Required gates for real submit

Real submit requires all of the following before the SDK is invoked:

- `POLYMARKET_LIVE_MODE=true`
- `POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true`
- `POLYMARKET_LIVE_ENABLE_SUBMIT=true`
- `POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=true`
- `POLYMARKET_LIVE_KILL_SWITCH=false`
- current `py-clob-client` dependency available
- private key and L2 API credentials present locally
- fresh adapter request, execution packet, authorization, and dry-run receipt
- passing risk checks and market allowlist
- configured and matching final confirmation phrase

## Required gates for real cancel

Real cancel requires all of the following before the SDK is invoked:

- `POLYMARKET_LIVE_MODE=true`
- `POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true`
- `POLYMARKET_LIVE_ENABLE_CANCEL=true`
- `POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED=true` or explicit emergency cancel mode
- `POLYMARKET_LIVE_KILL_SWITCH=false` unless emergency policy is deliberately extended in a future release
- current `py-clob-client` dependency available
- private key and L2 API credentials present locally
- operator-supplied exchange order id or previously recorded real attempt
- configured and matching final confirmation phrase
- audit/ledger recording

## Safety notes

Live trading is dangerous. Live trading is disabled by default. Autonomous trading is disabled by default. Operators are responsible for credentials, token allowances, balances, risk limits, and all real-money outcomes. Automated tests do not submit or cancel live orders. Fake adapter receipts are not exchange acknowledgements. Market-data and execution-quality estimates are not fill guarantees. This software is not financial advice.


## v1.1.0 verification center

The CLOB adapter page now includes an offline/default-safe verification center. It checks configuration, dependency presence, credential presence, client-init readiness, submit/cancel gates, fake adapter readiness, and real-smoke guard state without submitting or cancelling orders.
