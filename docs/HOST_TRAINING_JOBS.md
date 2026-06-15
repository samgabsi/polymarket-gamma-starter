# Host Training Jobs

Version: 1.7.0-real

Host training jobs let the operator start approved internal training, backtest, feature, dataset-quality, and signal-preview tasks on the local host. In v1.7.0-real these jobs are dataset-backed: they resolve local Training Lab datasets, Dataset Builder manifests, scoped/category dataset metadata, raw snapshots, normalized records, and custom CSV/JSON/JSONL files where available.

Safety defaults:

- `POLYMARKET_TRAINING_HOST_JOBS_ENABLED=false`
- only approved internal job types are allowed
- no arbitrary shell commands from user input
- no wallet access, signing, order submission, cancellation, or autonomous live execution
- artifacts are runtime data under `data/host_training_jobs/artifacts/` and are excluded from release ZIPs
- training outputs are `manual_review_only=true` and `can_live_trade=false`

Supported job types:

- `dataset_quality_scan`
- `feature_build`
- `baseline_training`
- `threshold_training`
- `momentum_training`
- `walk_forward_backtest`
- `signal_generation_preview`

## 100K local training configuration

A safe 100K-row local run can be enabled in `.env` like this:

```env
POLYMARKET_TRAINING_HOST_JOBS_ENABLED=true
POLYMARKET_TRAINING_MAX_ROWS=100000
POLYMARKET_TRAINING_DEFAULT_MAX_ROWS=100000
POLYMARKET_TRAINING_HARD_MAX_ROWS=1000000
POLYMARKET_TRAINING_BATCH_SIZE=5000
POLYMARKET_TRAINING_BLOCK_OVER_HARD_MAX_ROWS=true
POLYMARKET_TRAINING_MAX_RUNTIME_SECONDS=900
POLYMARKET_TRAINING_MAX_ARTIFACT_BYTES=50000000
POLYMARKET_TRAINING_ALLOWED_JOB_TYPES=baseline_training,threshold_training,momentum_training,walk_forward_backtest,dataset_quality_scan,feature_build,signal_generation_preview
```

Starts still require the operator confirmation phrase:

`I_UNDERSTAND_HOST_TRAINING_RUNS_LOCAL_JOBS`

## Batch processing behavior

The runner resolves the dataset reference, selects up to the configured row cap, and processes records in batches. Job telemetry records:

- `rows_available`, `rows_selected`, `rows_processed`, `rows_skipped`
- `batch_size`, `batches_total`, `batches_completed`
- `progress_percent`, `runtime_seconds`, `started_at`, `finished_at`
- `dataset_reference`, `metrics`, `artifact_refs`, `artifact_hashes`, `warnings`, `blockers`, and `log_tail`

If a dataset exists only as metadata and no local records are readable, the job fails clearly rather than inventing success metrics.

## Metrics and artifacts

Every completed job writes JSON artifacts under the runtime data directory:

- `job_summary.json`
- `metrics.json`
- `rows_sample_audit.json` with secret-like fields redacted
- `feature_schema.json` when applicable
- `signal_preview.json` for signal preview jobs

Each artifact is SHA-256 hashed and recorded in the job ledger.

## Signal preview safety

`signal_generation_preview` creates manual-review signal candidates only. Candidates include confidence, edge estimate, rationale, and feature snapshot hash. They are not executable orders and cannot bypass strategy-signal review queues, risk checks, approvals, or live gates.

## Troubleshooting: why did this only process 100 rows?

In v1.6.0 the internal host job completion path capped processing around 100 rows. v1.7.0 removes that placeholder cap. If a job still processes fewer than expected, check:

1. `/api/training/host-jobs/caps` for current row caps and hard cap.
2. The dataset reference has readable local rows, not just metadata.
3. `.env` contains `POLYMARKET_TRAINING_MAX_ROWS=100000` or the desired cap.
4. The requested cap does not exceed `POLYMARKET_TRAINING_HARD_MAX_ROWS` when blocking is enabled.
5. The file is UTF-8 CSV, JSON, or JSONL and has no parse blockers.

## 16 GB RAM guidance

For a typical 16 GB local workstation, prefer:

- 100K rows as the normal safe cap
- 5K rows per batch
- 900 seconds max runtime
- one host job at a time
- no browser-heavy or unrelated training tasks during larger runs

Larger runs should be scoped/category-filtered first, then increased gradually only after reviewing runtime, artifact size, and memory behavior.
