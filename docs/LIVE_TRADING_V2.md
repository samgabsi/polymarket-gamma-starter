# Live Trading v2 — v2.1.0-real

`v2.1.0-real` adds the first full live-trading control plane for the Polymarket Gamma Starter package. The implementation is intentionally operator-controlled and fail-closed: it can build and preview live tickets, run strict risk checks, require explicit human approval, require a typed confirmation phrase, route real submit/cancel attempts through the isolated CLOB adapter, record a local audit ledger, inspect read-only account state where supported, and reconcile local records against remote open-order state.

## Main routes

- `/v2-live` — consolidated v2 dashboard.
- `/v2-live/readiness` — pass/fail readiness checklist.
- `/v2-live/market-data` — market discovery and order-book API links.
- `/v2-live/trade-ticket` — ticket payload requirements and preview/submit flow.
- `/v2-live/orders` — open-order and reconciliation entry points.
- `/v2-live/positions` — read-only positions/balances entry point.
- `/v2-live/risk` — risk-control overview.
- `/v2-live/audit` — local JSONL/CSV audit ledger view.
- `/v2-live/emergency` — emergency-control action documentation.

## Main API routes

- `GET /api/v2/live/status`
- `GET /api/v2/live/readiness`
- `GET /api/v2/live/markets?q=<query>&limit=25`
- `GET /api/v2/live/orderbook/<token_id>`
- `POST /api/v2/live/ticket/preview`
- `POST /api/v2/live/order/submit`
- `POST /api/v2/live/order/cancel`
- `GET /api/v2/live/orders/open`
- `GET /api/v2/live/positions`
- `POST /api/v2/live/reconcile`
- `GET /api/v2/live/audit`
- `GET /api/v2/live/audit.csv`
- `POST /api/v2/live/emergency`

## Safety model

Live submission is blocked unless all of these are true:

1. `POLYMARKET_V2_TRADING_MODE=live_trading_armed`.
2. `READ_ONLY=false`.
3. `POLYMARKET_LIVE_KILL_SWITCH=false`.
4. `POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true`.
5. `POLYMARKET_LIVE_ENABLE_SUBMIT=true`.
6. `POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=true`.
7. Required credentials are present in the local environment.
8. Optional SDK/runtime dependency is available.
9. Risk checks pass.
10. The operator provides `human_approval=true`.
11. Warnings are acknowledged with `acknowledge_warnings=true`.
12. The typed confirmation phrase exactly matches the configured phrase.

Cancellation is similarly gated through `POLYMARKET_LIVE_ENABLE_CANCEL`, `POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED`, real-network permission, an order id, a reason, and the typed confirmation phrase.

## What is real versus mocked

The v2 control plane is real application code and not a mock UI. Public Gamma and CLOB order-book endpoints call the configured public APIs. The submit/cancel path calls the existing isolated `FailClosedPolymarketClobAdapter`, which can use the optional live SDK when the operator installs dependencies and configures all gates. Tests and startup smoke checks never place real orders.

## Current SDK note

As of the v2.1.0-real build, Polymarket documentation points developers toward official clients and a newer unified Python SDK. The older `py-clob-client` package is retained only as a legacy compatibility fallback for the existing isolated adapter boundary. The app surfaces SDK availability in readiness rather than pretending an unavailable runtime is usable.

## v2.1.0 UI/UX redesign

The v2.1 console keeps the v2.0 live control plane but reorganizes operator workflows around a persistent status bar, compact dashboard, step-based trade ticket, explicit refresh buttons, collapsed raw payloads, grouped settings, Markdown audit export, and task-based docs. Backend risk and execution gates remain unchanged and authoritative.
