# Feature Sets

Feature sets are deterministic metadata definitions that describe which feature groups should be derived from a dataset. v1.2.0 includes a lightweight feature-set registry and preview system. It does not require heavy machine-learning dependencies.

Supported groups include market metadata, price movement, spread/liquidity, volume/depth, order-book imbalance, time-to-resolution, volatility, paper workflow, execution quality, risk controls, and signal history.

## v1.3.0 data foundation addendum

The Training Lab now has a local-first data foundation: data source registry, explicit ingestion jobs, raw snapshots, normalized records, labeling workbench, dataset builder, and dataset manifests. Data collection does not trade, generated signals require manual review, leakage checks are warnings rather than proof, and generated runtime data is excluded from release packages.
