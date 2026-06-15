# Environment Variables Reference — v2.1.0-real

## v2 control-plane mode

| Key | Default | Purpose |
|---|---:|---|
| `POLYMARKET_V2_TRADING_MODE` | `research_only` | One of `research_only`, `paper`, `live_read_only`, `live_trading_armed`. |
| `POLYMARKET_V2_REQUIRE_APPROVAL` | `true` | Requires explicit human approval before live submit. |
| `POLYMARKET_V2_CONFIRMATION_PHRASE` | `LIVE ORDER APPROVED` | Typed phrase required for live submit/cancel. |
| `POLYMARKET_V2_FORCE_READ_ONLY` | `false` | Extra read-only override. |
| `POLYMARKET_V2_ALLOW_MARKET_ORDERS` | `false` | Allows FOK/FAK marketable behavior when true. |
| `POLYMARKET_V2_ALLOW_LIMIT_ORDERS` | `true` | Allows regular limit-order tickets. |
| `POLYMARKET_V2_DEFAULT_SLIPPAGE_BPS` | `150` | Default slippage warning/control value. |
| `POLYMARKET_V2_MAX_TOTAL_EXPOSURE` | `0` | Optional total exposure cap. |
| `POLYMARKET_V2_SDK_FAMILY` | `official_unified_python_sdk_then_clob_fallback` | SDK/runtime preference label surfaced in readiness. |

## API hosts

| Key | Default | Purpose |
|---|---:|---|
| `GAMMA_BASE_URL` | `https://gamma-api.polymarket.com` | Gamma market/event discovery. |
| `CLOB_BASE_URL` | `https://clob.polymarket.com` | CLOB order-book and adapter host. |
| `POLYMARKET_CLOB_HOST` | `https://clob.polymarket.com` | Adapter-specific CLOB host alias. |
| `POLYMARKET_DATA_API_BASE_URL` | `https://data-api.polymarket.com` | Positions/activity/value Data API host. |

## Live execution gates

| Key | Safe default | Purpose |
|---|---:|---|
| `READ_ONLY` | `true` | Blocks live submission when true. |
| `POLYMARKET_LIVE_KILL_SWITCH` | `true` | Global live-order kill switch. |
| `POLYMARKET_LIVE_ALLOW_REAL_NETWORK` | `false` | Allows real network adapter paths. |
| `POLYMARKET_LIVE_ENABLE_SUBMIT` | `false` | Enables real submit outer gate. |
| `POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED` | `false` | Enables manual submit control plane. |
| `POLYMARKET_LIVE_ENABLE_CANCEL` | `false` | Enables real cancel outer gate. |
| `POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED` | `false` | Enables manual cancel control plane. |
| `POLYMARKET_LIVE_NETWORK_READONLY` | `false` | Allows read-only account/network inspection when paired with real-network permission. |

## Risk controls

| Key | Default | Purpose |
|---|---:|---|
| `POLYMARKET_LIVE_MAX_ORDER_NOTIONAL` | `0` | Per-order notional cap. Non-zero required for readiness. |
| `POLYMARKET_LIVE_MAX_DAILY_NOTIONAL` | `0` | Daily notional cap. Non-zero required for readiness. |
| `POLYMARKET_LIVE_MAX_OPEN_ORDERS` | `0` | Max open order cap. Non-zero required for readiness. |
| `POLYMARKET_LIVE_MAX_POSITION_NOTIONAL` | `0` | Per-market/position cap. |
| `POLYMARKET_LIVE_MAX_DAILY_LOSS` | `0` | Daily loss cap if reliable data is available. |
| `POLYMARKET_LIVE_MARKET_ALLOWLIST` | empty | Optional comma-separated market allowlist. |
| `POLYMARKET_LIVE_TOKEN_ALLOWLIST` | empty | Optional comma-separated CLOB token allowlist. |

## Credentials

Keep these only in local `.env` or process environment:

- `POLYMARKET_PRIVATE_KEY` / `POLY_PRIVATE_KEY` / `PK`
- `POLYMARKET_CLOB_API_KEY` / `POLY_API_KEY` / `CLOB_API_KEY`
- `POLYMARKET_CLOB_SECRET` / `POLY_SECRET` / `CLOB_SECRET`
- `POLYMARKET_CLOB_PASSPHRASE` / `POLY_PASSPHRASE` / `CLOB_PASSPHRASE`
- `POLYMARKET_WALLET_ADDRESS` / `POLY_ADDRESS`
- `POLYMARKET_FUNDER_ADDRESS`
- `POLYMARKET_CHAIN_ID`
- `POLYMARKET_SIGNATURE_TYPE`

Secrets are redacted by the v2 API and audit layer.
