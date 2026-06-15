# BATCH TRAINING

Version: 1.6.0-real

This document describes the v1.6.0 scoped backfill and category-training workflow.

## Safety posture

- Scoped backfill is operator-controlled.
- Network ingestion remains disabled by default.
- Data ingestion does not trade, cancel orders, or sign orders.
- Category datasets reduce RAM and disk risk by limiting scope before training.
- Estimates are approximate and should be treated as warnings, not guarantees.
- Deduplication is best-effort and based on stable record hashes and identifying fields.
- Batch training is local, capped, and disabled unless host-training gates are enabled.
- Training outputs are not financial advice.
- Generated signals require manual review.
- No model may live-trade directly by default.

## Operator flow

1. Register a data scope such as crypto, sports, politics/elections, daily price up/down, a market ID list, or a date-limited resolved-market scope.
2. Preview the scope and review estimated row counts and warnings.
3. Link or select approved internet sources.
4. Preview a scoped backfill to review pagination, max records, max requests, storage estimate, RAM risk, and deduplication plan.
5. Start only if the configured caps and operator confirmation are acceptable.
6. Normalize and label records in batches.
7. Build a category dataset with chronological, walk-forward, holdout-by-market, or holdout-by-date split.
8. Preview host training and stay within row caps.
9. Queue generated signals for manual review only.

## Recommended local caps for a 16 GB RAM host

- 100k rows: safe small.
- 250k rows: safe medium.
- 500k rows: caution large.
- 1M rows: high caution and blocked above hard default unless explicitly overridden.

## Environment controls

- POLYMARKET_DATA_MAX_BACKFILL_RECORDS
- POLYMARKET_DATA_MAX_BACKFILL_REQUESTS
- POLYMARKET_DATA_BACKFILL_BATCH_SIZE
- POLYMARKET_DATA_MAX_STORAGE_MB_PER_JOB
- POLYMARKET_DATA_BLOCK_LARGE_BACKFILLS_BY_DEFAULT
- POLYMARKET_TRAINING_DEFAULT_MAX_ROWS
- POLYMARKET_TRAINING_HARD_MAX_ROWS
- POLYMARKET_TRAINING_BATCH_SIZE
- POLYMARKET_TRAINING_BLOCK_OVER_HARD_MAX_ROWS
