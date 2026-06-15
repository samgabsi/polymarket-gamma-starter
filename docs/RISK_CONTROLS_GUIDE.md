# Risk Controls Guide — v2.1.0-real

The v2 risk engine runs before live submission. Failures block submission. Warnings must be explicitly acknowledged.

## Blocking checks

- Required fields: market id, token id, side, price, size.
- Price bounds: price must be greater than 0 and less than 1.
- Side must be `BUY` or `SELL`.
- Order type must be `GTC`, `FOK`, `GTD`, or `FAK`.
- Limit orders must be allowed.
- FOK/FAK marketable behavior requires `POLYMARKET_V2_ALLOW_MARKET_ORDERS=true`.
- Per-order notional must be under `POLYMARKET_LIVE_MAX_ORDER_NOTIONAL` when that cap is non-zero.
- Daily notional cap must be configured and respected.
- Max open orders must be configured.
- Kill switch must be off.
- Read-only mode must be off.
- v2 trading mode must be `live_trading_armed`.
- Real network must be allowed.
- Submit gates must be enabled.
- Human approval must be present when approval is required.
- Market/token allowlists must match if configured.

## Warning checks

Warnings are intended to catch conditions that may need operator judgment, such as local-only duplicate detection or stale/unknown external state. Submission requires `acknowledge_warnings=true` when warnings are present.

## Audit behavior

Every preview and submission attempt writes a redacted audit record containing:

- timestamp
- app version
- mode
- action/status
- public order fields
- risk status
- approval state
- network-attempt flag
- redacted details
- stable ticket/risk hashes

Exports are available at `/api/v2/live/audit.csv`.
