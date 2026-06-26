# Cross-Market Arbitrage Guide - v4.15.0-real

Cross-market arbitrage remains the v4.13 review-only workflow in this release. Candidates are not guaranteed profits and do not execute trades.

## Operator Workflow

1. Open `/v3/arbitrage?demo=true`.
2. Confirm scanner status, data state, venue status, Polymarket status, and Kalshi status.
3. Confirm demo/sample fixture state is explicit when using fixtures.
4. Use `Record scan snapshot` only when the current scan should be persisted as local operator evidence.
5. Review gross margin, fees, slippage, liquidity, net margin, executable size, equivalence score, resolution mismatch risk, and risk flags.
6. Use Send to review queue, Add to watchlist, Ignore for now, or Reject/ignore.
7. Confirm redirect feedback and local audit persistence.

## API Workflow

- `GET /api/v3/arbitrage/scan` previews scan output and returns `persisted=false`.
- `POST /api/v3/arbitrage/scan/record` records a local scan snapshot and returns `persisted=true`.
- `POST /api/v3/arbitrage/opportunity/{opportunity_id}/review` records a local review decision.
- The compatibility GET review endpoint remains informational and does not record decisions.

## Data State

- `sample`: deterministic fixtures or disabled scanner fallback; use for workflow validation only.
- `live`: configured venue read-only data was returned; still requires freshness/rules/manual review.
- `cached`: local/runtime state, not a fresh external venue read.
- `stale`: stale data only.
- `unavailable`: no usable data or disabled/config-required/scaffolded venue.

## Kalshi

Kalshi is disabled/config-required by default. Public reads require deliberate operator configuration. Private/authenticated behavior is not presented as complete.

## Safety

No arbitrage action places orders, cancels orders, approves trades, arms live trading, or claims guaranteed profit. Resolution mismatch, stale data, fee sensitivity, slippage, and liquidity can erase apparent edge.

