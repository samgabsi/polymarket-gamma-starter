# v1.4.0 Mobile Operator Console Update

Use the global safety banner before starting any workflow. On mobile, open `Menu · Safety · Workflows` to navigate between Dashboard, Live Ops, Training Lab, Data Lab, and Operator Runbook. Live trading remains dangerous and disabled by default; automated tests do not submit or cancel live orders.

# Operators Manual

The operator manual for v1.1.0 focuses on safe live operations, verification, reconciliation, and autonomous-to-manual review.

## Key concepts

- Live trading is disabled by default.
- Autonomous trading is disabled by default.
- Real network access is disabled by default.
- Submit/cancel are disabled by default.
- The kill switch is active by default.
- Local generated state must never be included in release ZIPs.

## Live verification

Use `/live-clob-adapter` or `--live-clob-adapter-verify` before any live session. The verification center performs offline/default-safe checks and reports dependency, credential, gate, fake-adapter, and smoke-test readiness without submitting, cancelling, signing, or touching wallets.

## Readiness checklist

Use `/live-trading`, `/api/live/trading/readiness-checklist`, or `--live-readiness-checklist` to inspect blockers and remediation hints.

## Autonomous readiness

Autonomous live trading should remain blocked. Use dry-run/fake-adapter modes to queue validated strategy signals for manual review rather than live submission.

## Training & Evaluation Lab

Use `/training` for offline data-learning workflows. Register datasets, validate quality, define feature sets, run lightweight baselines, backtest offline, register model metadata, and queue generated signals for manual review. Do not treat training outputs as financial advice or as execution authorization.

## v1.3.0 data foundation addendum

The Training Lab now has a local-first data foundation: data source registry, explicit ingestion jobs, raw snapshots, normalized records, labeling workbench, dataset builder, and dataset manifests. Data collection does not trade, generated signals require manual review, leakage checks are warnings rather than proof, and generated runtime data is excluded from release packages.

## v1.5.0 Internet ingestion and host training jobs

This release adds an operator-controlled internet ingestion and host training job runner milestone. Internet ingestion is disabled by default, requires approved sources and allowlisted domains, and is limited to public/read-only data fetches. Data ingestion does not trade. Host training jobs are disabled by default, use approved internal job types only, and write artifacts to runtime data directories that are excluded from release ZIPs. Training outputs remain manual-review-only and do not directly live-trade.

## v1.6.0 scoped/category workflow note

For medium-large local training, prefer scoped/category backfills over broad ingest-everything jobs. Use `/data/scopes`, `/data/backfills`, and `/training/category-datasets` to cap records, preview pagination/storage/RAM risk, and keep dataset builds reproducible. Network ingestion remains disabled by default and no data/training workflow trades.

## v1.7.0 dataset-backed host training jobs

v1.7.0 replaces the earlier placeholder-style host job completion path with a real local dataset-backed runner. Host jobs now resolve Training Lab datasets, Dataset Builder manifests, category datasets, raw snapshots, normalized records, and custom CSV/JSON/JSONL files where available. The runner processes rows in batches, records actual rows available/selected/processed/skipped, emits metrics, and writes hashed runtime artifacts.

Recommended 16 GB local caps are 100K rows, 5K rows per batch, a 900-second runtime cap, and one host job at a time. Jobs remain disabled by default and require the confirmation phrase. Signal preview jobs create manual-review candidates only; they do not create executable orders and cannot bypass review, risk, approval, or live gates.
