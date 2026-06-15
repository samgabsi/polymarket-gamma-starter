# Execution Quality Simulator

Version: v0.9.0-real

The Execution Quality Simulator estimates whether an intended order could receive reasonable local fill quality against a saved market-data snapshot. It is a local simulator only. It is not a fill guarantee, not an exchange acknowledgement, and not a live trading feature.

## Inputs

- side: `BUY` or `SELL`,
- token ID,
- market ID,
- optional snapshot ID,
- limit price,
- size,
- order type,
- time in force,
- max spread bps,
- max slippage bps,
- optional source paper ticket ID,
- optional source live intent ID.

## Outputs

- estimated fill quantity,
- estimated average fill price,
- estimated notional,
- estimated unfilled size,
- estimated slippage bps,
- top-of-book depth,
- total executable-side depth,
- liquidity score,
- spread score,
- stale data flag,
- blockers and warnings,
- deterministic simulation hash,
- recommended operator action.

## States

- `quality_pass`
- `quality_pass_with_warnings`
- `blocked_by_stale_snapshot`
- `blocked_by_closed_market`
- `blocked_by_not_accepting_orders`
- `blocked_by_wide_spread`
- `blocked_by_insufficient_depth`
- `blocked_by_slippage`
- `blocked_by_invalid_order`
- `invalid_snapshot`

## Workflow Integration

Paper preflight treats missing market-data snapshots as warnings so existing paper workflows remain usable.

Live order-intent preflight, adapter request validation, and manual execution readiness use `POLYMARKET_MARKET_DATA_REQUIRE_FOR_LIVE=true` by default. With that default, missing or failing execution-quality state blocks live/manual boundary progression.

## Safety

The simulator never signs, submits, cancels, touches wallets, makes authenticated calls, or automates execution. Public fetch is disabled by default and no tests require network access.
