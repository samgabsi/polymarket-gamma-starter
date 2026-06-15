# 100K Dataset-Backed Host Training Jobs

Version: 1.7.0-real

This guide covers the v1.7.0-real host training runner for local 100K-row dataset jobs.

## Enable safely

Host jobs are disabled by default. Enable only in your local `.env`:

```env
POLYMARKET_TRAINING_HOST_JOBS_ENABLED=true
POLYMARKET_TRAINING_MAX_ROWS=100000
POLYMARKET_TRAINING_DEFAULT_MAX_ROWS=100000
POLYMARKET_TRAINING_HARD_MAX_ROWS=1000000
POLYMARKET_TRAINING_BATCH_SIZE=5000
POLYMARKET_TRAINING_BLOCK_OVER_HARD_MAX_ROWS=true
POLYMARKET_TRAINING_MAX_RUNTIME_SECONDS=900
POLYMARKET_TRAINING_MAX_ARTIFACT_BYTES=50000000
```

Keep all live-trading settings default-off unless separately performing a manual live-readiness exercise. Host training does not require live trading.

## CLI examples

Preview a job:

```bash
python -m app.cli --preview-training-host-job --job-type dataset_quality_scan --dataset-id ds_example --training-max-rows 100000
```

Start a quality scan:

```bash
python -m app.cli --run-dataset-quality-scan --dataset-id ds_example --training-max-rows 100000 --confirmation I_UNDERSTAND_HOST_TRAINING_RUNS_LOCAL_JOBS
```

Start a manual-review-only signal preview:

```bash
python -m app.cli --run-signal-generation-preview --dataset-id ds_example --training-max-rows 100000 --confirmation I_UNDERSTAND_HOST_TRAINING_RUNS_LOCAL_JOBS
```

Inspect caps:

```bash
python -m app.cli --training-job-caps
```

## API examples

- `GET /api/training/host-jobs/caps`
- `POST /api/training/host-jobs/preview`
- `POST /api/training/host-jobs/start`
- `POST /api/training/host-jobs/dataset-quality-scan`
- `POST /api/training/host-jobs/signal-generation-preview`
- `GET /api/training/host-jobs.csv`

All start endpoints require the confirmation phrase and admin authentication.
