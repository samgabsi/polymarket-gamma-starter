# Cross-Market Arbitrage Guide - v4.12.0-real

Cross-market arbitrage remains review-only. Candidates are not guaranteed profits and do not execute trades.

## Operator Workflow

1. Open `/v3/arbitrage?demo=true`.
2. Confirm scanner status, venue status, Polymarket status, and Kalshi status.
3. Confirm demo/sample state when using fixtures.
4. Review gross margin, fees, slippage, liquidity, net margin, executable size, equivalence score, and resolution mismatch risk.
5. Use Send to review queue, Add to watchlist, Ignore for now, or Reject/ignore.
6. Confirm redirect feedback and local audit persistence.

## Kalshi

Kalshi is disabled/config-required by default. Public reads require deliberate operator configuration. Private/authenticated behavior is not presented as complete.

## Safety

No arbitrage action places orders, cancels orders, approves trades, arms live trading, or claims guaranteed profit. Resolution mismatch, stale data, fee sensitivity, slippage, and liquidity can erase apparent edge.
