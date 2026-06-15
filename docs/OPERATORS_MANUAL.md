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

## v1.9.0-real GUI-first configuration workflow

Use `/settings/configuration` for schema-backed environment setup. Prefer the guided controls over raw `.env` edits. Use `/setup/wizard` for common presets, including 100K host training mode. Use `/setup/status` for read-only Python, virtual environment, dependency, launch, and `.env` status.

Recommended operator flow:

1. Open `/setup/status` and verify Python/venv/runtime status.
2. Open `/setup/wizard` and choose the closest safe preset.
3. Preview the diff.
4. Resolve blockers and review warnings.
5. Save only after validation passes.
6. Restart the app so process-level env values take effect.
7. Use `/settings/configuration` for targeted adjustments.

The configuration console creates runtime-only backups under `data/config_backups/` and audit records under `data/config_audit/`. Sanitized exports mask secrets and are safe for debugging.

The web UI never executes arbitrary shell commands, never installs packages, never exposes full secret values, never bypasses authentication/admin gates, and never flips live execution gates without validation and explicit confirmation. Training outputs and signal previews remain manual-review-only and cannot live-trade.

## v1.9.0-real streamlined settings workflow

Use `/settings` as the starting point for all configuration work.

Recommended flow:

1. Open `/settings` and review the configuration health state.
2. Read the Recommended Setup panel.
3. Use `/setup/wizard` for common modes such as Locked-down Safe, Local Demo, LAN Demo, Training/Backtesting, or 100K Host Training.
4. Use `/settings/configuration` for targeted edits, search, filters, Simple Mode, Advanced Mode, and grouped diff preview.
5. Use `/setup/status` to inspect Python, virtual environment, launch, filesystem, dependency, `.env`, and restart status.
6. Export `/api/config/export-sanitized` when you need a secret-safe troubleshooting report.
7. Review `/api/config/audit-history` for runtime-only config save history.

The settings UX is guidance and configuration only. It does not live-trade, submit/cancel orders, sign messages, touch wallets, run shell commands, run pip, mutate the venv, leak secrets, or bypass manual review.

## v2.1.0-real Live Trading Control Plane

The Version 2 workflow begins at `/v2-live`. The operator should move in this order:

1. Open `/v2-live/readiness` and resolve failures.
2. Use `/v2-live/market-data` or `/api/v2/live/markets` to discover active markets.
3. Inspect CLOB order books with `/api/v2/live/orderbook/<token_id>`.
4. Build and preview a trade ticket with `/api/v2/live/ticket/preview`.
5. Resolve every risk failure.
6. Confirm human approval and acknowledge warnings.
7. Submit only with `/api/v2/live/order/submit` and the exact configured phrase.
8. Inspect `/v2-live/audit`, `/api/v2/live/orders/open`, and `/api/v2/live/positions`.
9. Reconcile with `/api/v2/live/reconcile`.
10. Use `/v2-live/emergency` to record emergency actions and then persist environment changes through settings or `.env`.

Live trading remains fail-closed: no default setting enables real submit/cancel, tests do not place orders, and the app does not bypass Polymarket terms, geography, KYC, funding, allowance, wallet, or account restrictions.

## v2.1.0-real UI/UX operator console

`v2.1.0-real` reorganizes the Live v2 area into a cleaner task-based console without weakening any live-trading gate. Use `/v2-live` for the overview, `/v2-live/markets` for public market/order-book data, `/v2-live/trade-ticket` for the step-by-step ticket workflow, `/v2-live/risk` for readiness and blockers, `/v2-live/audit` for ledger exports, `/v2-live/settings` for grouped configuration review/validation, and `/v2-live/emergency` for kill-switch and emergency action receipts.

The persistent Live v2 status bar should be checked before any ticket work. It shows mode, live armed state, read-only state, kill switch, readiness, Gamma/CLOB posture, and recent issue state. If any status is unknown or blocked, treat live submission as unavailable until investigated.
