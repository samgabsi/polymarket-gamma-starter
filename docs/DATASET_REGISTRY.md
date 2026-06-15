# Dataset Registry

The dataset registry stores metadata about local training datasets without packaging the datasets themselves. Supported dataset types include market snapshots, order book snapshots, Gamma market metadata, paper workflow history, execution-quality simulations, live/fake order ledger exports, strategy signal history, custom CSV, and synthetic/demo data.

Each registry row records dataset ID, creation time, name, dataset type, source path, row/column counts, schema hash, content hash, quality status, warnings, blockers, and notes.

Quality checks include empty data, missing headers, duplicate rows, invalid timestamps, invalid price/probability ranges, insufficient sample size, and leakage-risk warnings.

## v1.3.0 data foundation addendum

The Training Lab now has a local-first data foundation: data source registry, explicit ingestion jobs, raw snapshots, normalized records, labeling workbench, dataset builder, and dataset manifests. Data collection does not trade, generated signals require manual review, leakage checks are warnings rather than proof, and generated runtime data is excluded from release packages.
