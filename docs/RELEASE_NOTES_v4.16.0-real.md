# v4.17.0-real Release Notes

## Summary

v4.17.0-real adds automated paper trading as the next automation step. The new subsystem can run a deterministic strategy loop, apply risk checks, create simulated paper orders/fills, update local paper positions and P/L, and record decisions/audit rows.

This release does **not** add live execution. The paper broker never calls real submit or cancel APIs.

## New surfaces

- `/v3/paper-trading` — paper trading UI with safety banner, run-once/reset controls, status cards, last-run summary, positions, orders, fills, decisions, and config snapshot.
- `/api/v3/paper/status`
- `/api/v3/paper/config`
- `/api/v3/paper/account`
- `/api/v3/paper/orders`
- `/api/v3/paper/fills`
- `/api/v3/paper/positions`
- `/api/v3/paper/decisions`
- `/api/v3/paper/runs`
- `/api/v3/paper/audit`
- `POST /api/v3/paper/run-once`
- `POST /api/v3/paper/reset`
- `POST /api/v3/paper/orders/{order_id}/cancel-paper`

## New implementation

- `app/paper_automation.py` implements the paper config reader, simulated broker, risk gates, ledger, strategy runner, and local audit rows.
- `app/templates/paper_trading_v416.html` renders the operator UI.
- Feature readiness and stub burn-down maps now include paper trading engine, automation, scheduler, broker/ledger/risk, and UI statuses.

## Safety

Every paper trading response includes paper-only safety fields such as:

- `paper_only: true`
- `live_execution_used: false`
- `can_place_real_orders: false`
- `can_cancel_real_orders: false`
- `real_order_submitted: false`
- `real_order_cancelled: false`

Paper P/L is simulated and should not be interpreted as live profitability.
