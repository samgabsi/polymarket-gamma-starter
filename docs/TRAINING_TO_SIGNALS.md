# Training to Signals

Training-generated signal candidates enter the existing strategy signal ledger as manual-review candidates. They are not orders and do not directly trade.

Signals include model/backtest references, strategy ID, market/token, side, limit price, size, confidence, edge estimate, rationale, feature snapshot hash, and status. The default operational posture is `queued_for_manual_review`.

## v1.3.0 data foundation addendum

The Training Lab now has a local-first data foundation: data source registry, explicit ingestion jobs, raw snapshots, normalized records, labeling workbench, dataset builder, and dataset manifests. Data collection does not trade, generated signals require manual review, leakage checks are warnings rather than proof, and generated runtime data is excluded from release packages.
