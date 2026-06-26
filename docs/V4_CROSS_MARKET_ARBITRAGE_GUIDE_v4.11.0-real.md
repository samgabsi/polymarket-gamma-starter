# Cross-Market Arbitrage Guide - v4.11.0-real

Cross-market arbitrage remains review-only. v4.11 does not add autonomous execution or guaranteed-profit claims.

## Status

- Polymarket adapter: working for the configured/demo read scope, with unavailable status on read errors.
- Kalshi adapter: disabled/config-required by default.
- Venue registry: partial because not every venue is live-read capable in the packaged default.
- Scanner: disabled by default unless `ARBITRAGE_SCANNER_ENABLED=true`.
- Review actions: POST-backed and local-only.

## Operator Review

Every candidate must be reviewed for:

- fees
- slippage
- liquidity
- stale data
- resolution mismatch
- semantic mismatch
- venue availability
- manual execution feasibility

Candidates are not orders, not approvals, not financial advice, and not guaranteed profits.
