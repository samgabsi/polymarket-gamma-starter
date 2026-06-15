# Live Trading Setup Guide — v2.1.0-real

This guide describes the intended operator path for enabling live trading. Do not skip directly to armed mode.

## 1. Start safe

Default posture in `.env.example` is:

```env
POLYMARKET_V2_TRADING_MODE=research_only
READ_ONLY=true
LIVE_TRADING_ENABLED=false
POLYMARKET_LIVE_KILL_SWITCH=true
POLYMARKET_LIVE_ALLOW_REAL_NETWORK=false
POLYMARKET_LIVE_ENABLE_SUBMIT=false
POLYMARKET_LIVE_ENABLE_CANCEL=false
POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=false
POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED=false
```

Launch the app and inspect `/v2-live/readiness` before entering any secrets.

## 2. Install optional live dependencies

In a dedicated virtual environment, after reviewing current official Polymarket docs:

```bash
pip install -r requirements-live-optional.txt
```

The core app can run without this file; live SDK availability is shown in the readiness checklist.

## 3. Configure read-only live inspection

Use `/settings/configuration` where possible. Prefer dropdowns, booleans, and numeric fields rather than raw `.env` editing.

For read-only account inspection:

```env
POLYMARKET_V2_TRADING_MODE=live_read_only
POLYMARKET_LIVE_NETWORK_READONLY=true
POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true
POLYMARKET_WALLET_ADDRESS=0x...
```

Keep submit/cancel gates false while validating market data, order books, open orders, positions, and reconciliation.

## 4. Configure risk limits before arming

Set non-zero caps:

```env
POLYMARKET_LIVE_MAX_ORDER_NOTIONAL=25
POLYMARKET_LIVE_MAX_DAILY_NOTIONAL=100
POLYMARKET_LIVE_MAX_OPEN_ORDERS=3
POLYMARKET_LIVE_MAX_POSITION_NOTIONAL=50
POLYMARKET_LIVE_MAX_DAILY_LOSS=25
```

Use conservative numbers first.

## 5. Configure credentials locally only

Never put real secrets in a release ZIP or public repo.

```env
POLYMARKET_PRIVATE_KEY=...
POLYMARKET_CLOB_API_KEY=...
POLYMARKET_CLOB_SECRET=...
POLYMARKET_CLOB_PASSPHRASE=...
POLYMARKET_FUNDER_ADDRESS=...
POLYMARKET_CHAIN_ID=137
POLYMARKET_SIGNATURE_TYPE=
```

Secrets are masked in the UI, redacted in JSON, and redacted in the v2 audit ledger.

## 6. Arm deliberately

Only after readiness passes and you understand the jurisdictional/account restrictions:

```env
POLYMARKET_V2_TRADING_MODE=live_trading_armed
READ_ONLY=false
POLYMARKET_LIVE_KILL_SWITCH=false
POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true
POLYMARKET_LIVE_ENABLE_SUBMIT=true
POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=true
POLYMARKET_V2_REQUIRE_APPROVAL=true
POLYMARKET_V2_CONFIRMATION_PHRASE=LIVE ORDER APPROVED
```

Cancellation requires separate gates:

```env
POLYMARKET_LIVE_ENABLE_CANCEL=true
POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED=true
```

## 7. Submit workflow

1. Search markets.
2. Select the CLOB token id.
3. Build a ticket preview with `POST /api/v2/live/ticket/preview`.
4. Resolve all failures.
5. Re-run preview with human approval and warning acknowledgement.
6. Submit only with `POST /api/v2/live/order/submit` and the exact typed confirmation phrase.
7. Review `/v2-live/audit` and reconcile.

## Legal and compliance note

The operator is responsible for using Polymarket only where permitted and in accordance with Polymarket terms and applicable law. The app does not bypass geofencing, KYC, jurisdiction, wallet, allowance, funding, or account restrictions.
