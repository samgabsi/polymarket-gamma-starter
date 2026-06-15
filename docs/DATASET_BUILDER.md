# Dataset Builder

The Dataset Builder combines sources, snapshots, normalized records, labels, feature groups, split strategies, filters, and quality rules into reproducible Training Lab datasets.

Default split preference is chronological/walk-forward to reduce leakage risk. Supported split methods include chronological, market-grouped, fixed random seed, walk-forward, holdout by market, and holdout by date.

Dataset builds produce manifests with source hashes, snapshot hashes, normalization schema version, label configuration, feature configuration, split method, row counts, schema/content hashes, software version, warnings, and blockers.

Built datasets are runtime artifacts and excluded from release ZIPs.

## v1.5.0 Internet ingestion and host training jobs

This release adds an operator-controlled internet ingestion and host training job runner milestone. Internet ingestion is disabled by default, requires approved sources and allowlisted domains, and is limited to public/read-only data fetches. Data ingestion does not trade. Host training jobs are disabled by default, use approved internal job types only, and write artifacts to runtime data directories that are excluded from release ZIPs. Training outputs remain manual-review-only and do not directly live-trade.

## v1.6.0 scoped/category workflow note

For medium-large local training, prefer scoped/category backfills over broad ingest-everything jobs. Use `/data/scopes`, `/data/backfills`, and `/training/category-datasets` to cap records, preview pagination/storage/RAM risk, and keep dataset builds reproducible. Network ingestion remains disabled by default and no data/training workflow trades.
