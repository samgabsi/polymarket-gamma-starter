# Backtesting

Backtests are offline simulations only. They do not place orders and do not guarantee future performance.

The backtest registry records strategy ID, dataset/feature bindings, simulated signals, accepted/rejected counts, notional simulated, estimated P&L, max drawdown, hit rate, assumptions, warnings, blockers, and a backtest hash.

Operators must watch for leakage risk, insufficient sample size, and unstable performance across chronological windows.

## v1.3.0 data foundation addendum

The Training Lab now has a local-first data foundation: data source registry, explicit ingestion jobs, raw snapshots, normalized records, labeling workbench, dataset builder, and dataset manifests. Data collection does not trade, generated signals require manual review, leakage checks are warnings rather than proof, and generated runtime data is excluded from release packages.
