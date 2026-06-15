# v1.4.0 Mobile Training Lab Update

Training pages are now easier to use on mobile. Training outputs are not financial advice, do not directly live-trade, and generated signals remain queued for manual review.

# Training & Evaluation Lab

The Training & Evaluation Lab is an offline, local-first area for data inspection, feature-set definition, lightweight baseline training, backtesting, model registry records, and manual-review signal generation.

It is available at `/training` and through `/api/training/*` endpoints and CLI commands.

## Safety posture

Training outputs are not trades. Generated signals are queued for manual review and must still pass strategy validation, paper workflow, risk controls, live readiness, operator approval, execution-packet flow, kill switch, and manual confirmation before any live execution path can be considered.

The lab never submits or cancels orders. Backtests are simulations and are not guarantees of future performance. This software is not financial advice.

## Runtime state

Generated datasets, feature sets, training runs, model registry rows, backtests, and training audit rows live under local runtime state, typically `data/training/`. They are excluded from release ZIPs.

## v1.3.0 data foundation addendum

The Training Lab now has a local-first data foundation: data source registry, explicit ingestion jobs, raw snapshots, normalized records, labeling workbench, dataset builder, and dataset manifests. Data collection does not trade, generated signals require manual review, leakage checks are warnings rather than proof, and generated runtime data is excluded from release packages.

## v1.5.0 Internet ingestion and host training jobs

This release adds an operator-controlled internet ingestion and host training job runner milestone. Internet ingestion is disabled by default, requires approved sources and allowlisted domains, and is limited to public/read-only data fetches. Data ingestion does not trade. Host training jobs are disabled by default, use approved internal job types only, and write artifacts to runtime data directories that are excluded from release ZIPs. Training outputs remain manual-review-only and do not directly live-trade.
