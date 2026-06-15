# Polymarket Gamma Starter v2.1.0-real

Local-first Polymarket market-intelligence, paper-ops, staged live-readiness, guarded execution-control, and decluttered live-operator console.

## What changed in v2.1.0-real

UI/UX Redesign, Cleanup, Declutter, Smoothness, and Speed Pass milestone:

- Redesigned `/v2-live` into a cleaner operator console with compact top-level sections: Dashboard, Markets, Trade Ticket, Orders, Positions, Risk, Audit, Settings, Emergency, and Docs.
- Added a persistent Live v2 status bar showing app version, trading mode, live armed state, read-only state, kill-switch state, readiness, Gamma/CLOB posture, refresh time, and recent critical issue state.
- Reworked the v2 dashboard into concise status cards for mode, readiness, kill switch, open orders, positions, daily notional, risk state, audit events, and next recommended action.
- Rebuilt the Trade Ticket page as a step-by-step workflow: market/outcome, order details, preview, risk check, human approval, and submit/rehearse. Live submit remains disabled until backend gates pass.
- Cleaned up Markets, Orders, Positions, Risk, Audit, Settings, Emergency, and Docs sections with progressive disclosure, explicit refresh buttons, collapsed raw payloads, loading/error states, and compact tables/cards.
- Added GUI-first Live v2 settings schema and validation endpoints: `/api/v2/live/settings/schema` and `/api/v2/live/settings/validate`. They never return secret values and do not write files.
- Added Markdown audit export at `/api/v2/live/audit.md` alongside JSON and CSV exports.
- Added a safe `/docs/{file}` markdown/text route for task-based operator docs inside the UI.
- Added UI route smoke tests, settings validation tests, Markdown audit export tests, and docs route tests.
- Preserved all v2.0 live-trading safety: risk checks, human approval, warning acknowledgement, typed confirmation phrase, kill switch, read-only gate, submit/cancel gates, CLOB adapter boundary, audit ledger, and fail-closed defaults.

### Primary Live v2 console routes

- Dashboard: `/v2-live`
- Markets: `/v2-live/markets`
- Trade Ticket: `/v2-live/trade-ticket`
- Orders: `/v2-live/orders`
- Positions: `/v2-live/positions`
- Risk: `/v2-live/risk`
- Audit: `/v2-live/audit`
- Settings: `/v2-live/settings`
- Emergency: `/v2-live/emergency`
- Docs: `/v2-live/docs`

## What changed in v2.0.0-real

Fully Functional Live Trading Build milestone:

- Added a new guarded Live Trading v2 console at `/v2-live` with dedicated pages for readiness, market data, trade tickets, orders, positions, risk, audit, and emergency controls.
- Added `app/live_v2.py`, a live-trading control plane that builds ticket previews, calculates notional/max-loss, enforces risk checks, requires human approval and typed confirmation, writes a local JSONL/CSV audit ledger, and routes real submit/cancel attempts through the existing fail-closed CLOB adapter boundary.
- Added public Gamma market search and CLOB order-book endpoints under `/api/v2/live/*`, plus read-only open-order, position, and reconciliation endpoints that degrade safely when credentials/network are disabled.
- Added v2 environment controls such as `POLYMARKET_V2_TRADING_MODE`, `POLYMARKET_V2_REQUIRE_APPROVAL`, `POLYMARKET_V2_CONFIRMATION_PHRASE`, order-type toggles, slippage/default exposure controls, Data API base URL, and SDK-family selection.
- Added a live readiness checklist covering environment, Gamma/CLOB/Data URLs, credentials, wallet derivability, SDK/runtime availability, risk caps, kill switch, read-only mode, real-network mode, submit/cancel gates, approval requirements, and CLOB boundary readiness.
- Added documentation for live setup, environment variables, risk controls, order lifecycle, emergency/kill switch usage, troubleshooting, and v2 release notes.
- Preserved all v1.9 settings/configuration UX, data ingestion, training, research, paper workflow, audit, and existing manual live control-plane routes.
- Preserved safety boundaries: live trading remains default-off, kill switch remains default-on, READ_ONLY remains default-true, submit/cancel gates remain default-off, no tests place real orders, and secrets are masked/redacted in UI/API/audit outputs.

## What changed in v1.9.0-real

Streamlined Settings & Configuration UX Refresh milestone:

- Added a unified `/settings` landing page that acts as a dashboard for configuration health, operator mode, feature enablement, LAN exposure, restart-needed state, changed-from-default counts, warnings, blockers, missing secrets, last save, and last backup/audit references.
- Reworked `/settings/configuration` into a streamlined console with Simple Mode and Advanced Mode, search by env key/label/help text, category filters, changed/restart/warning/blocker/secret/advanced/dangerous/live/training/LAN filters, sticky quick navigation, compact setting rows, reset/source metadata, and copy-key buttons.
- Added a Recommended Setup panel that explains safe next actions and links directly to the relevant wizard preset or filtered configuration section without making automatic changes.
- Improved `/setup/wizard` with richer preset cards showing safety level, use case, enabled keys, disabled keys, LAN/internet/host-training/live-readiness impact, restart expectations, and a final review checkbox before applying.
- Improved diff previews by grouping changes into safe, warning, dangerous/live-related, restart-required, and blocked sections while keeping secrets masked.
- Improved `/setup/status` into read-only App, Python, Virtual Environment, Launch, Filesystem, Environment, Dependencies, and Restart Status sections with copyable recommended commands. The UI still does not execute shell commands, run pip, or mutate virtual environments.
- Added configuration health states: Safe, Needs Attention, Restart Required, Blocked, and Advanced / Dangerous Values Present.
- Added `/api/config/audit-history` for secret-safe runtime audit history inspection.
- Added docs for the Settings overview, Simple vs Advanced Mode, improved configuration UX, preset flow, diff preview, runtime status, and safe 100K host-training configuration through the GUI.
- Preserved v1.8 functionality: schema-backed config registry, safe .env read/write, unknown-key preservation where practical, backups, audits, validation, sanitized exports, setup/runtime status, CLI/API commands, setup wizard, no arbitrary shell execution, secret masking, and live-trading safety gates.
- Preserved safety boundaries: no autonomous live trading, no order submission, no cancellation, no signing, no wallet access, no pip execution, no venv mutation, no secret exposure, no weakened auth/LAN warnings, and training/signal outputs remain `manual_review_only=true` and `can_live_trade=false`.

### GUI routes

- Settings landing dashboard: `/settings`
- Full configuration console: `/settings/configuration`
- Alias: `/setup/environment`
- Guided setup wizard: `/setup/wizard`
- Runtime/venv status: `/setup/status`
- Secret-safe audit history: `/api/config/audit-history`

### Configuration CLI examples

```bash
python -m app.cli --config-schema
python -m app.cli --config-status
python -m app.cli --config-validate --config-changes '{"POLYMARKET_TRAINING_MAX_ROWS":"100000"}'
python -m app.cli --config-diff --config-changes '{"POLYMARKET_TRAINING_HOST_JOBS_ENABLED":"true"}'
python -m app.cli --config-export-sanitized
python -m app.cli --config-presets
python -m app.cli --setup-status
```

## What changed in v1.7.0-real

Dataset-backed Host Training Job Runner milestone:

- Replaced the v1.6 placeholder-style 100-row host job completion path with a real local dataset-backed runner.
- Host jobs now resolve Training Lab datasets, Dataset Builder manifests, scoped/category dataset metadata, raw snapshots, normalized records, and custom CSV/JSON/JSONL files where available.
- Added explicit row-cap handling for `POLYMARKET_TRAINING_MAX_ROWS`, `POLYMARKET_TRAINING_DEFAULT_MAX_ROWS`, `POLYMARKET_TRAINING_HARD_MAX_ROWS`, `POLYMARKET_TRAINING_BATCH_SIZE`, `POLYMARKET_TRAINING_BLOCK_OVER_HARD_MAX_ROWS`, `POLYMARKET_TRAINING_MAX_RUNTIME_SECONDS`, `POLYMARKET_TRAINING_MAX_ARTIFACT_BYTES`, and `POLYMARKET_TRAINING_HOST_JOBS_ENABLED`.
- Added batch telemetry: rows available/selected/processed/skipped, batch size, total/completed batches, runtime, progress, dataset references, warnings, blockers, and log tails.
- Added deterministic lightweight metrics for dataset quality scans, feature builds, baseline training, threshold training, momentum training, walk-forward backtests, and manual-review-only signal generation previews.
- Added hashed runtime artifacts for job summaries, metrics, feature schemas, sample audits, and signal previews. Runtime artifacts stay under `data/host_training_jobs/artifacts/` and are excluded from release ZIPs.
- Added host training caps API/CLI visibility plus direct dataset-quality-scan and signal-generation-preview API/CLI paths.
- Updated `/training/host-jobs` so operators can see configured caps, actual row counts, batch progress, warning/blocker counts, and artifact counts.
- Preserved all safety boundaries: host jobs are disabled by default, require explicit operator confirmation, do not execute shell commands, do not touch wallets, do not sign, do not submit/cancel orders, and keep `manual_review_only=true` / `can_live_trade=false`.

### Safe 100K local host-training `.env` snippet

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

## What changed in v1.6.0-real

Automated Internet Data Ingestion + Host Training Job Runner milestone:

- Added an approved **internet data source registry** for public/read-only Gamma, CLOB, CSV, JSON, and HTTP snapshot sources.
- Added explicit internet ingestion preview/run flows with disabled-by-default network gates, domain allowlists, timeouts, rate limits, request-size limits, redacted URLs, audit events, and no trading behavior.
- Added a disabled-by-default internet ingestion scheduler registry with due-job preview only; no daemon starts on app boot.
- Added a local **host training job runner** for approved internal Python job types such as baseline training, threshold training, momentum training, walk-forward backtest, dataset quality scan, feature build, and signal generation preview.
- Added host-job status, progress, log-tail, metrics, artifact hash tracking, and cancellation records while keeping artifacts under runtime data directories.
- Added `/data/internet-sources`, `/data/internet-ingestion`, `/data/internet-workflow`, and `/training/host-jobs` UI pages plus JSON/CSV APIs and CLI commands.
- Added docs for internet ingestion, source registry, ingestion scheduler, host training jobs, and internet-to-training workflow.
- Preserved all live-trading and autonomous safety defaults: internet ingestion and host training are disabled by default, data ingestion does not trade, and training outputs cannot directly live-trade.

## What changed in v1.1.0-real

Live operations hardening milestone:

- Added a default-safe live CLOB adapter verification center for offline dependency, credential, client-init, gate, fake-adapter, and real-smoke-test readiness checks.
- Added `/api/live/clob-adapter/verification`, `/api/live/clob-adapter/verification.csv`, and matching CLI verification/export commands.
- Added an operator live readiness checklist with remediation hints for manual live submit/cancel, fake validation, reconciliation, and autonomous readiness.
- Added `/operator-runbook`, `/api/operator-runbook`, and `--operator-runbook` for a practical live-operations workflow.
- Hardened live order lifecycle reporting with explicit lifecycle statuses and richer read-only reconciliation suggestions.
- Preserved the `/positions` hardening from v1.0.1 and added regression-oriented validation for empty/malformed local data.
- Preserved v1.0.0 manual-live adapter behavior and fail-closed live trading defaults.

## What changed in v1.0.0-real

- Implements the first guarded **manual live trading adapter mapping** inside `app/live_clob_adapter.py`.
- Maps the optional `py-clob-client` runtime to `ClobClient`, `ApiCreds`, `OrderArgs`, `OrderType`, `OpenOrderParams`, `BUY`/`SELL`, `create_order`, `post_order`, `cancel`, `get_order`, and `get_orders`.
- Keeps all real SDK calls isolated behind the CLOB adapter boundary; routes, CLI commands, templates, and autonomous code do not call the SDK directly.
- Wires `adapter_mode=real_live` manual submit/cancel record paths to the adapter, but only after the existing manual gates pass: live mode, real-network flag, submit/cancel flags, kill switch off, credentials, SDK dependency, fresh source records, risk limits, allowlists, and final confirmation.
- Preserves no-network automated validation. Status pages and probes do not sign, submit, cancel, touch wallets, or contact the CLOB.
- Keeps autonomous live trading blocked; autonomous remains explicit dry-run/fake-adapter only until manual live operation is separately operator-validated.
- Updates docs and optional live requirements for the new manual-live adapter boundary.

## What changed in v0.10.0-real

- Adds a guarded **Live Trading Bridge** status layer that consolidates live mode, submit/cancel flags, kill switch, real-network flag, credential presence, allowlists, budgets, fake adapter posture, dependency availability, blockers, warnings, and recommended next action.
- Adds `/live-trading`, `/live-orders`, `/live-reconciliation`, `/strategy-signals`, `/autonomous-trading`, and `/autonomous-runs` UI pages plus matching JSON/CSV APIs.
- Adds a local **Live Order Ledger** derived from manual/fake/blocked execution attempts. Fake-local receipts remain local simulations and are not exchange acknowledgements.
- Adds a read-only **Live Reconciliation** scaffold that degrades safely without credentials/network and never submits/cancels.
- Adds deterministic **Strategy Signal** records for future autonomous operation. The app does not invent trades from LLM output.
- Adds an explicit-run **Autonomous Trading Bridge** with `off`, `dry_run`, `paper_only`, `fake_adapter`, and `live_guarded` modes. Default mode is off; no background scheduler starts on import.
- Adds audit coverage for live trading status, live order events, strategy signals, and autonomous runs.
- Expands `.env.example` with fail-closed live/autonomous placeholders.
- Keeps automated validation no-network and no-real-money; live submit/cancel require deliberate local configuration and manual gates.

## What changed in v0.9.0-real

- Adds **Market Data Intelligence**: local public/fixture order-book snapshots with best bid/ask, midpoint, spread bps, top depth, 1%/5% depth, total depth, market status, and freshness signals.
- Adds **Execution Quality Simulator**: deterministic local estimates for fill quantity, average fill price, notional, unfilled size, spread, slippage, and liquidity/depth blockers.
- Adds `/market-data`, `/market-data/snapshots/{snapshot_id}`, `/execution-quality`, and `/execution-quality/{simulation_id}` UI pages.
- Adds JSON/CSV APIs and CLI commands for snapshot preview/record/export, optional public-fetch boundary status, execution-quality preview/record/export, and detail lookups.
- Integrates market-data quality into paper preflight as warnings and into live intent preflight, adapter request validation, and manual execution readiness as live/manual safety gates when configured.
- Adds audit rows for saved `market_data_snapshot` and `execution_quality_simulation` records.
- Adds dashboard and workflow-map summary cards for snapshot freshness, wide spreads, thin books, and execution-quality blockers.
- Keeps public fetch disabled by default. The v0.9.0 build supports local/manual JSON snapshots first and reports `public_fetch_disabled` or `public_fetch_unimplemented` rather than faking network success.
- Keeps autonomous/live execution disabled: v0.9.0-real does not sign payloads, place real orders, cancel real orders, touch wallets, send submit/cancel network requests, or add autonomous trading loops. Execution-quality outputs are estimates only and not fill guarantees.

## What changed in v0.8.0-real

- Adds a coherent **Operator Console** shell with grouped navigation, environment badges, breadcrumbs, consistent footer safety posture, responsive layout, and keyboard-visible focus states.
- Upgrades the home dashboard at `/` into an operator overview with paper workflow, approvals, preflight, ops closeout, live-readiness, manual boundary, execution-attempt, and audit summary cards.
- Adds a read-only workflow map at `/workflow` that links Research -> Paper Workflow -> Risk / Ops -> Live Readiness -> Manual Boundary -> Audit without mutating state.
- Adds a local UI/design-system reference at `/ui-system` for badges, callouts, cards, metadata grids, forms, empty states, and table styling.
- Standardizes status badges, severity callouts, action bars, table wrappers, empty states, metadata grids, and cross-links across the main dashboard, live-readiness/manual pages, paper tickets, approvals, audit, and closeout pages.
- Improves first-run readability and operator next-step guidance while preserving old URLs, APIs, CSV exports, CLI commands, and local file formats.
- Keeps autonomous/live execution disabled: v0.8.0-real does not sign payloads, place real orders, cancel real orders, touch wallets, send submit/cancel network requests, or add autonomous trading loops.

## What changed in v0.7.0-real

- Adds **Manual Live Execution Control Plane**: final manual submit/cancel previews, explicit operator confirmation gates, local attempt records, and deterministic attempt hashes.
- Adds **Execution Attempt Ledger** at `data/live/live_execution_attempts.json`, recording both blocked attempts and fake-local receipts without secrets.
- Adds **Fake Local Adapter** for no-network submit/cancel simulation. Fake receipts are not exchange orders and never imply exchange acknowledgement.
- Adds real adapter interface scaffolding with `live_submit_unimplemented` and `live_cancel_unimplemented` statuses. Real live submit/cancel are implemented only behind the manual control plane and all explicit live gates.
- Adds staleness/replay checks for authorization age, dry-run age, adapter request age, packet hash drift, repeated attempts, risk limits, market allowlists, kill switch, submit/cancel flags, and final confirmation phrase.
- Adds UI pages `/live-manual-execution`, `/live-execution-attempts`, and `/live-manual-cancel`, plus JSON/CSV APIs and CLI commands for readiness, attempts, manual submit, and manual cancel.
- Adds audit categories: `live_execution_control_readiness`, `live_manual_submit_preview`, `live_manual_submit_attempt`, `live_manual_cancel_preview`, `live_manual_cancel_attempt`, and `live_fake_adapter_receipt`.
- Keeps autonomous/live execution disabled: v0.7.0-real does not sign payloads, place real orders, cancel real orders, touch wallets, send submit/cancel network requests, or add autonomous trading loops.


## What changed in v0.6.0-real

- Adds **Live Adapter Readiness**: a redacted, default-off live adapter boundary report for future Polymarket CLOB client work.
- Adds optional read-only validation receipts behind `POLYMARKET_LIVE_NETWORK_READONLY=false` by default. Missing dependencies or incomplete credentials degrade safely without network or execution.
- Adds **Live Adapter Request Validation**: converts saved unsigned execution packets into adapter-shaped request previews and validates schema, packet hash, authorization, preflight, dry-run receipt, risk limit, allowlist, kill switch, and manual-auth gates.
- Adds **Manual Execution Boundary**: local final-review checklist records with explicit non-submission flags and optional final operator acknowledgement.
- Adds UI pages `/live-adapter`, `/live-adapter-requests`, and `/manual-execution-boundary`, plus JSON/CSV APIs and CLI flags for readiness, read-only validation, adapter requests, and manual reviews.
- Adds new audit categories: `live_adapter_readiness`, `live_adapter_readonly_validation`, `live_adapter_request`, and `manual_execution_review`.
- Keeps live execution disabled: v0.6.0 does not sign payloads, place orders, cancel orders, touch wallets, send order-submission network requests, or automate trading.


## What changed in v0.5.11-real

- Adds **Live Dry-Run Review Board**: a read-only reconciliation layer that compares saved unsigned execution packets with their latest offline dry-run adapter receipts.
- Adds `/live-dry-run-review`, `/api/live/dry-run-review`, `/api/live/dry-run-review/{packet_id}`, and `/api/live/dry-run-review.csv`.
- Adds CLI support: `--live-dry-run-review`, `--live-dry-run-review-detail <packet_id>`, `--live-dry-run-review-state <state>`, and `--export-live-dry-run-review live_dry_run_review.csv`.
- Classifies packet/receipt state as `validated_ready`, `validated_with_warnings`, `needs_dry_run_receipt`, `stale_dry_run_receipt`, `dry_run_blocked`, `packet_blocked`, or `invalid`.
- Surfaces missing, stale, blocked, and validated dry-run review state in dashboard/operator alerts without creating another mutable approval record.
- Keeps the live boundary unchanged: the review board is derived local reporting only; it does not derive credentials, sign messages, submit/cancel orders, touch wallets, send network requests, authorize trading, or automate execution.

## What changed in v0.5.10-real

- Adds **Live Dry-Run Adapter Receipts**: offline, non-network validation records for saved unsigned live execution packets.
- Adds `/live-dry-run-adapter`, `/api/live/dry-run-adapter`, `/api/live/dry-run-adapter/{receipt_id}`, `/api/live/dry-run-adapter.csv`, `POST /api/live/execution-packets/{packet_id}/dry-run/preview`, and `POST /api/live/execution-packets/{packet_id}/dry-run`.
- Adds CLI support: `--live-dry-run-adapter`, `--preview-live-dry-run-adapter`, `--record-live-dry-run-adapter`, `--live-dry-run-receipt-detail`, dry-run filters, and `--export-live-dry-run-adapter live_dry_run_adapter_receipts.csv`.
- Receipts snapshot packet hash, authorization/preflight binding, public wire-order fields, offline adapter request/response preview, live guard posture, blockers/warnings, and a deterministic receipt hash.
- Adds dry-run adapter rows to the unified audit ledger under `live_dry_run_adapter` and surfaces validated/blocked dry-run states in dashboard/operator alerts.
- Keeps the live boundary unchanged: dry-run receipts never derive credentials, sign messages, submit/cancel orders, touch wallets, send network requests, automate trading, or bypass preflight/risk/audit controls.

## What changed in v0.5.9-real

- Adds **Live Execution Packets**: deterministic unsigned local packets assembled from saved live-order intent preflight and acknowledged operator authorization snapshots.
- Adds `/live-execution-packets`, `/api/live/execution-packets`, `/api/live/execution-packets/{packet_id}`, `/api/live/execution-packets.csv`, `POST /api/live/order-intents/{intent_id}/execution-packet/preview`, and `POST /api/live/order-intents/{intent_id}/execution-packet`.
- Adds CLI support: `--live-execution-packets`, `--preview-live-execution-packet`, `--record-live-execution-packet`, `--live-execution-packet-detail`, packet filters, and `--export-live-execution-packets live_execution_packets.csv`.
- Packets snapshot the current preflight, source authorization hash, paper ticket/approval binding, token/order fields, public wire-order preview, blockers/warnings, and deterministic packet hash.
- Adds packet rows to the unified audit ledger under `live_execution_packet` and surfaces ready/blocked packet states in dashboard/operator alerts.
- Keeps the live boundary unchanged: packets are unsigned review/export records only; they do not derive credentials, sign messages, submit/cancel orders, touch wallets, automate trading, or bypass preflight/risk/audit controls.

## What changed in v0.5.8-real

- Adds **Live Operator Authorization Ledger**: local documentation-only authorization/reject/defer snapshots for saved live-order intent preflight reviews.
- Adds `/live-order-authorizations`, `/api/live/order-intents/authorizations`, `/api/live/order-intents/authorizations/{authorization_id}`, `/api/live/order-intents/{intent_id}/authorization`, and `/api/live/order-intents/authorizations.csv`.
- Adds CLI support: `--live-order-authorizations`, `--record-live-order-authorization <intent_id>`, `--live-order-authorization-detail <authorization_id>`, authorization filters, `--live-authorization-ack`, and `--export-live-order-authorizations live_order_authorizations.csv`.
- Authorization records snapshot the current preflight state, paper-ticket/approval bindings, token/order fields, blockers/warnings, operator acknowledgement, and a deterministic authorization hash.
- Adds authorization rows to the unified audit ledger under `live_order_authorization` and surfaces blocked/authorized/deferred authorization states in dashboard/operator alerts.
- Keeps the live boundary unchanged: authorization snapshots do not sign, submit, cancel, touch wallets, derive credentials, automate trading, or bypass preflight/risk/audit controls.


## What changed in v0.5.7-real

- Adds **Live Order Intent Preflight**: a read-only governance review for saved live-order intent previews before any future execution-capable build.
- Adds `/live-order-intent-preflight`, `/api/live/order-intents/preflight`, `/api/live/order-intents/{intent_id}/preflight`, and `/api/live/order-intents/preflight.csv`.
- Adds CLI support: `--live-order-intent-preflight`, `--live-order-intent-preflight-detail <intent_id>`, `--live-preflight-state <state>`, and `--export-live-order-intent-preflight live_order_intent_preflight.csv`.
- Reviews each saved intent against explicit paper ticket binding, explicit paper approval binding, current paper preflight, live guard settings, token ID presence, notional/stake alignment, and execution-disabled sanity checks.
- Classifies reviews as `ready_for_operator_authorization`, `ready_with_warnings`, `needs_paper_binding`, `blocked_by_live_guard`, `blocked`, or `invalid`.
- Adds live-intent preflight rows to the unified audit ledger under `live_order_preflight` and surfaces blocked/binding/ready review states in dashboard/operator alerts.
- Keeps this build non-executing: ready preflight states do not sign, submit, cancel, automate, or authorize live orders.


## What changed in v0.5.6-real

- Adds **Live Order Intent Preview**: local, dry-run-only order-intent records for future Polymarket/CLOB live-order fields.
- Adds `/live-order-intents`, `/api/live/order-intents`, `/api/live/order-intents/{intent_id}`, `/api/live/order-intents.csv`, `POST /api/live/order-intents/preview`, and `POST /api/live/order-intents`.
- Adds CLI support: `--live-order-intents`, `--preview-live-order-intent`, `--record-live-order-intent`, `--live-order-intent-detail`, live-intent field flags, and `--export-live-order-intents live_order_intents.csv`.
- Each intent snapshots market/token/outcome/side/order type/time-in-force/price/size/notional plus live-config guard state, allowlist/risk-limit checks, blockers, warnings, source ticket/approval IDs, operator label, and note.
- Adds local intent records to the unified audit ledger under `live_order_intent` and surfaces blocked/reviewable intent previews in dashboard/operator alerts.
- Keeps this build non-executing: intent previews do not derive credentials, sign messages, submit orders, cancel orders, bypass approvals, touch wallets, or automate trading.

## What changed in v0.5.5-real

- Adds **Live Configuration Readiness**: a gated, non-executing control surface for local Polymarket/CLOB credential fields, live guard switches, and live risk-limit placeholders.
- Adds `/live-config`, `/api/live/config/readiness`, `/api/live/config/readiness.csv`, and `/api/live/config/template.env`.
- Adds CLI support: `--live-config-readiness`, `--export-live-config-readiness live_config_readiness.csv`, and `--export-live-config-template live_config_template.env`.
- Expands `.env.example` with redacted/readiness-only fields for CLOB L2 credentials, wallet/funder metadata, dry-run/manual-approval/pre-trade/audit gates, and future live notional/open-order limits.
- Surfaces live-readiness summaries in dashboard/status flows and warns if guard settings imply unsafe live-readiness posture.
- Keeps this build non-executing: it does not derive credentials, sign messages, place orders, cancel orders, bypass paper approvals, or automate live trading.

## What changed in v0.5.4-real

- Adds **Paper Ops Closeout Signoffs**: explicit local operator records that snapshot the current closeout board after human review.
- Adds `/paper-ops-closeout-signoffs`, `/api/paper/ops-closeout/signoffs`, `/api/paper/ops-closeout/signoffs/{signoff_id}`, `/api/paper/ops-closeout/signoffs.csv`, and `POST /api/paper/ops-closeout/signoffs`.
- Adds CLI support: `--paper-ops-closeout-signoffs`, `--record-ops-closeout-signoff`, `--ops-closeout-signoff-detail`, signoff status/operator filters, and `--export-ops-closeout-signoffs paper_ops_closeout_signoffs.csv`.
- Signoffs snapshot closeout status, handoff-required counts, blocked/action-required/aging/escalation counts, component summaries, top closeout rows, operator label, note, and closure gate.
- Adds closeout signoff rows to the unified paper audit ledger under `ops_closeout_signoff` and surfaces latest follow-up/blocked signoffs in dashboard/operator alerts.
- Keeps signoffs as operator documentation only: they do not auto-close handoffs or escalations, approve/reject tickets, execute paper trades, settle positions, connect wallets, sign messages, or provide investment advice.


## What changed in v0.5.3-real

- Adds **Paper Ops Closeout**: a read-only end-of-shift checklist across daily briefing, ops aging, handoff reconciliation, escalation register, and escalation review.
- Adds `/paper-ops-closeout`, `/api/paper/ops-closeout`, and `/api/paper/ops-closeout.csv`.
- Classifies closeout rows by source, status/state, severity, priority, handoff requirement, and closure gate so unresolved work can be handed off explicitly.
- Adds CLI support: `--paper-ops-closeout`, `--ops-closeout-source`, `--ops-closeout-status`, `--ops-closeout-market`, `--ops-closeout-handoff-required`, and `--export-ops-closeout paper_ops_closeout.csv`.
- Dashboard/operator alerts now surface blocked or attention-level closeout state before ending an operator pass.
- Keeps closeout read-only: it does not record handoffs, close escalations, approve/reject tickets, execute paper trades, settle positions, connect wallets, sign messages, or provide investment advice.

## What changed in v0.5.2-real

- Adds **Paper Ops Escalation Review**: a read-only reconciliation layer between saved escalation records and the current paper ops aging board.
- Adds `/paper-ops-escalation-review`, `/api/paper/ops-escalations/review`, `/api/paper/ops-escalations/{escalation_id}/review`, and `/api/paper/ops-escalations/review.csv`.
- Classifies escalations as `active_followup`, `verify_resolution`, `deescalation_candidate`, `closed_but_reappeared`, or `closed_record`.
- Adds CLI support: `--paper-ops-escalation-review`, `--ops-escalation-review-detail <escalation_id>`, `--ops-escalation-review-state <state>`, and `--export-ops-escalation-review paper_ops_escalation_review.csv`.
- Dashboard/operator alerts now surface escalation-review rows that still need human verification, including closed records whose source aging item reappeared.
- Keeps the review layer read-only: it does not update escalation records, approve tickets, mutate handoffs, execute paper trades, settle positions, touch wallets, or provide investment advice.


## What changed in v0.5.1-real

- Adds **Paper Ops Escalation Register**: a local human-in-the-loop follow-up log for stale, blocked, repeated, or follow-up paper-ops items identified by the aging review.
- Adds `/paper-ops-escalations`, `/api/paper/ops-escalations`, `/api/paper/ops-escalations/{escalation_id}`, and `/api/paper/ops-escalations.csv`.
- Adds `POST /api/paper/ops-escalations` and `POST /api/paper/ops-escalations/{escalation_id}` for local escalation creation and status updates.
- Adds CLI support: `--paper-ops-escalations`, `--create-ops-escalation <aging_item_id>`, `--update-ops-escalation <escalation_id>`, `--ops-escalation-detail <escalation_id>`, and `--export-ops-escalations paper_ops_escalations.csv`.
- Escalations snapshot the source aging item, source severity/status, age, handoff count, recommended action, owner, note, and update history.
- Escalation records now appear in the unified audit ledger under `operator_escalation` and dashboard/operator alerts surface active escalations and high-priority escalation candidates.
- Keeps escalation records as operator follow-up only: they do not approve, reject, execute, settle, or advise trades.

## What changed in v0.5.0-real

- Adds **Paper Ops Aging Review**: a read-only stale-workload report across unresolved paper ops briefing items and saved operator handoffs.
- Adds `/paper-ops-aging`, `/api/paper/ops-aging`, `/api/paper/ops-aging/{item_id}`, and `/api/paper/ops-aging.csv`.
- Classifies unresolved items by `critical`, `stale`, `followup`, `repeat`, `fresh`, or `unknown_age` using source timestamps, handoff history, and status-specific thresholds.
- Adds CLI support: `--paper-ops-aging`, `--ops-aging-detail <item_id>`, aging filters, and `--export-ops-aging paper_ops_aging.csv`.
- Dashboard/operator alerts now surface stale or repeated paper-ops items before the next handoff or execution review.
- Keeps aging review read-only: it does not mutate handoffs, tickets, approvals, positions, paper trades, or live trading state.

## What changed in v0.4.9-real

- Adds **Paper Handoff Reconciliation**: a deterministic read-only comparison between saved handoff packets and the current daily paper ops briefing.
- Adds `/paper-handoff-reconciliation`, `/api/paper/handoffs/reconciliation`, `/api/paper/handoffs/{handoff_id}/reconciliation`, and `/api/paper/handoffs/reconciliation.csv`.
- Reconciliation classifies saved handoff items as `still_open`, `changed_open`, `not_visible`, or `no_longer_unresolved` so incoming operators can verify follow-up before acting.
- Adds CLI support: `--handoff-reconciliation`, `--handoff-reconciliation-detail <handoff_id>`, and `--export-handoff-reconciliation paper_handoff_reconciliation.csv`.
- Dashboard handoff metrics now show reconciliation follow-up, still-open items, and not-visible items.
- Keeps handoff reconciliation read-only: it does not mutate handoffs, tickets, approvals, positions, execution queues, or paper trades.
- Keeps the boundary unchanged: deterministic local paper operations only; no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.4.8-real

- Adds **Paper Operator Handoffs**: saved local shift/desk handoff packets built from the current daily paper ops briefing.
- Adds `/paper-handoffs`, `/api/paper/handoffs`, `/api/paper/handoffs/{handoff_id}`, `/api/paper/handoffs.csv`, and `POST /api/paper/handoffs`.
- Handoff packets snapshot unresolved briefing items, blockers, action-required counts, ready stake, recent briefing checkpoints, and next-operator focus notes.
- Adds CLI support: `--paper-handoffs`, `--record-handoff`, `--handoff-detail <handoff_id>`, handoff filters, operator labels, and `--export-handoffs paper_operator_handoffs.csv`.
- Saved handoff records are included in the unified audit ledger under the `operator_handoff` category.
- Dashboard/operator alerts now surface unresolved handoff workload and saved handoff records marked `needs_followup`.
- Keeps the boundary unchanged: deterministic local paper operations only; no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.4.7-real

- Adds **Daily Paper Ops Briefing**: one local paper-only control surface across the operator runbook, entry execution queue, risk budget, post-trade review flags, playbook performance, and paper portfolio health.
- Adds `/paper-ops-briefing`, `/api/paper/briefing`, `/api/paper/briefing.csv`, `/api/paper/briefing/checkpoints`, and `POST /api/paper/briefing/checkpoint`.
- Adds local briefing checkpoints (`reviewed`, `needs_followup`, `skipped`) so morning/evening operator review passes can be preserved without touching any live trading path.
- Adds CLI support: `--paper-ops-briefing`, `--briefing-section`, `--briefing-status`, `--briefing-market`, `--briefing-checkpoints`, `--record-briefing-checkpoint`, and `--export-briefing paper_ops_briefing.csv`.
- Briefing checkpoint records are included in the unified audit ledger under the `ops_briefing` category.
- Dashboard/operator alerts now surface ready, blocked, and action-required briefing items.
- Keeps the boundary unchanged: deterministic local paper operations only; no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.4.6-real

- Adds **Paper Operator Runbook**: a generated local checklist across entry execution, exit execution, settlement candidates, risk-budget flags, and post-trade review flags.
- Adds `/runbook`, `/api/paper/runbook`, `/api/paper/runbook/item/{item_id}`, `/api/paper/runbook/item/{item_id}/ack`, and `/api/paper/runbook.csv`.
- Adds local runbook acknowledgements (`done`, `needs_followup`, `skipped`) so human workflow decisions are tracked separately from simulated trades.
- Adds CLI support: `--runbook`, `--runbook-detail <item_id>`, runbook filters for scope/status/market/item, `--ack-runbook-item <item_id>`, and `--export-runbook paper_operator_runbook.csv`.
- Runbook acknowledgement records are included in the unified audit ledger under the `operator_runbook` category.
- Dashboard/operator alerts now surface ready, blocked, and action-required runbook items.
- Keeps the boundary unchanged: deterministic local paper operations only; no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.4.5-real

- Adds **Paper Execution Queue**: a local pre-execution workbench that separates entry tickets into `approved_ready`, `needs_approval`, `stale_approval`, `blocked`, `rejected`, and `executed`.
- Adds `/execution-queue`, `/api/paper/execution-queue`, `/api/paper/execution-queue/{ticket_id}`, and `/api/paper/execution-queue.csv`.
- Adds CLI support: `--execution-queue`, `--execution-queue-detail <ticket_id>`, queue filters for status/market/ticket, `--strict-execution-queue`, and `--export-execution-queue paper_execution_queue.csv`.
- Simulated paper buys from entry tickets now require both a passing preflight result and a matching latest local approval record; unapproved execution attempts are blocked and recorded as approval/audit events.
- Queue rows snapshot latest preflight status, latest approval status/ID, stake, price, recommended operator action, and reason summaries.
- Adds queue alerts to the dashboard/operator alert stream so approved-ready and approval-needed tickets are visible before execution.
- Keeps the boundary unchanged: deterministic local paper governance only; no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.4.4-real

- Adds **Paper Execution Approvals**: a local governance log for entry-ticket approvals, blocks, rejections, and executed paper buys.
- Adds `/approvals`, `/api/paper/approvals`, `/api/paper/approvals/{approval_id}`, `/api/paper/approvals.csv`, `POST /api/trade-tickets/{ticket_id}/approval`, and `POST /api/trade-tickets/{ticket_id}/reject`.
- Approval records snapshot the current preflight result, blocker/warning summaries, operator note, ticket state, and any simulated paper-trade ID created from an approved ticket.
- Paper-buy execution from entry tickets now records an approval/audit event for both blocked preflight attempts and successful simulated executions.
- Approval records are included in the unified paper audit ledger under the `execution_approval` category.
- Adds CLI support: `--approvals`, `--approval-detail <approval_id>`, `--approve-ticket <ticket_id>`, `--reject-ticket <ticket_id>`, filters for approval status/market/ticket, and `--export-approvals paper_execution_approvals.csv`.
- Fixes the risk-budget page template context so `/risk-budget` renders cleanly.
- Keeps the boundary unchanged: deterministic local paper approval only; no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.4.3-real

- Adds **Paper Entry Preflight Gate**: a local execution-time guardrail for paper entry tickets before a simulated buy is allowed.
- Adds `/preflight`, `/api/paper/preflight`, `/api/paper/preflight/{ticket_id}`, `/api/paper/preflight.csv`, and `POST /api/trade-tickets/{ticket_id}/preflight`.
- Re-checks ticket status, ticket execution flag, stake, readiness, paper risk, paper risk-budget state, playbook-decision discipline, risk warnings, and ticket freshness.
- Paper buys from entry tickets now run preflight at execution time instead of trusting an older ticket snapshot.
- Adds CLI support: `--preflight`, `--preflight-ticket <ticket_id>`, `--preflight-status <status>`, `--strict-playbook-preflight`, and `--export-preflight paper_preflight.csv`.
- Keeps the boundary unchanged: deterministic local paper preflight only; no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.4.2-real

- Adds **Paper Risk Budget Review**: a local portfolio guardrail report across open paper exposure, pending entry tickets, per-market concentration, and position lifecycle warnings.
- Adds `/risk-budget`, `/api/paper/risk-budget`, `/api/paper/risk-budget/{market_id}`, and `/api/paper/risk-budget.csv`.
- Calculates total budget utilization, remaining exposure room, room after pending tickets, open position slots, max next paper allocation, and per-market budget state (`ok`, `watch`, `tight`, `blocked`).
- Surfaces risk-budget flags in the dashboard and local alert stream so new tickets can be reviewed against current simulated exposure before paper execution.
- Adds CLI support: `--risk-budget`, `--risk-budget-detail <market_id>`, `--risk-budget-market <market_id>`, and `--export-risk-budget paper_risk_budget.csv`.
- Keeps the boundary unchanged: deterministic local paper-risk review only; no wallet, no live orders, no autonomous execution, and no investment advice.


## What changed in v0.4.1-real

- Adds **Playbook Performance Review**: local paper analytics that connect strategy playbook decisions to the paper review report.
- Adds `/playbook-performance`, `/api/playbook-performance`, `/api/playbook-performance/{playbook_id}`, and `/api/playbook-performance.csv`.
- Aggregates each playbook by decision count, unique markets, paper lifecycle follow-through, realized/unrealized/net simulated P&L, win/loss/breakeven counts, discipline warnings, positive process flags, and recent market lessons.
- Counts financial results once per unique market per playbook, so repeated decisions do not double-count P&L.
- Adds CLI support: `--playbook-performance`, `--playbook-performance-detail <playbook_id>`, `--export-playbook-performance playbook_performance.csv`, and `--decision-status-filter <status>`.
- Keeps the boundary unchanged: deterministic local paper-review analytics only; no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.4.0-real

- Adds **Strategy Playbooks**: deterministic local rule sets between readiness and entry/exit workflows.
- Adds `/playbooks`, `/api/playbooks`, `/api/playbooks/board`, `/api/markets/{market_id}/playbook-fit`, and `/api/playbook-decisions`.
- Ships default paper-only playbooks for edge+evidence confluence, research/watchlist candidates, negative/low-confidence filtering, and managed position review.
- Adds local playbook decision logging so strategy classifications become part of the audit ledger and post-trade review discipline flags.
- Adds CLI support: `--playbooks`, `--playbook-board`, `--playbook-fit <market_id>`, `--playbook-decisions`, and `--assign-playbook <market_id> --playbook-id <id>`.
- Keeps playbooks deliberately non-autonomous: they classify workflow state, but they never place live orders, touch wallets, or bypass human approval.

## What changed in v0.3.9-real

- Adds **Paper Review Report**: a market-level post-trade review layer built from the local paper audit ledger.
- Adds `/review-report`, `/api/paper/review-report`, `/api/paper/review-report/{market_id}`, and `/api/paper/review-report.csv`.
- Rolls entry tickets, simulated buys/sells, lifecycle plans, exit tickets, and settlements into realized/unrealized P&L, lifecycle status, discipline flags, and first-pass lessons.
- Adds CLI support: `--review-report`, `--review-market <market_id>`, `--review-status <status>`, and `--export-review-report paper_review_report.csv`.
- Keeps review deliberately retrospective and paper-only: no wallet, no live orders, no autonomous execution, and no investment advice.

## What changed in v0.3.8-real

- Adds **Paper Audit Ledger**: a unified local timeline across entry tickets, simulated buys/sells, position lifecycle plans, exit tickets, and manual settlements.
- Adds `/audit`, `/api/paper/audit`, `/api/paper/audit/{market_id}`, and `/api/paper/audit.csv`.
- Adds market-level audit-chain review so a single market can be traced from idea/readiness through entry, lifecycle management, exit, and settlement.
- Adds CSV export for the combined paper audit trail, separate from the raw paper trades CSV.
- Adds CLI support: `--audit-log`, `--audit-market <market_id>`, `--audit-category <category>`, and `--export-audit paper_audit.csv`.
- Fixes the CLI analytics import path so `--paper-analytics` and `--export-trades` remain usable.
- Preserves the paper-only boundary: audit rows are local records only; no wallet, signing, live orders, or automated execution.

## What changed in v0.3.7-real

- Adds **Paper Exit Tickets**: a human-in-the-loop simulated sell workflow for open paper positions.
- Adds `/exit-tickets`, `/api/exit-tickets`, and position-to-exit-ticket creation from `/positions`.
- Adds `POST /api/exit-tickets/{ticket_id}/paper-sell` so an approved exit ticket can close part or all of a local paper position.
- Exit tickets snapshot open shares, exit price, estimated proceeds, estimated cost reduction, and estimated realized P&L before simulated execution.
- Adds CLI support: `--exit-tickets`, `--create-exit-ticket`, `--exit-ticket-detail`, `--update-exit-ticket`, and `--execute-exit-ticket`.
- Preserves the paper-only boundary: exit tickets create local review records and simulated sells only; no wallet, signing, CLOB posting, or live execution.

## What changed in v0.3.6-real

- Adds v0.3.6 Paper Position Lifecycle Controls: a `/positions` page for managing open simulated positions after entry.
- Adds local target price, stop price, max-hold review days, status, and review-note fields per open paper position.
- Adds target/stop/review alerts through `/api/paper/position-alerts` and folds them into the existing local alerts feed.
- Adds `/api/paper/positions` and `POST /api/paper/positions/{market_id}/plan` for machine-readable position management.
- Adds CLI support: `--paper-positions`, `--position-alerts`, and `--set-position-plan <market_id> --outcome YES --target-price 0.75 --stop-price 0.35`.
- Preserves the paper-only boundary: lifecycle controls create review prompts only; they never place live orders, touch wallets, or auto-execute sells.

## What changed in v0.3.5-real

- Adds v0.3.5 Manual Paper Settlements: close resolved local paper positions, credit simulated payouts, and record settlement P&L without live trading.
- Adds `/settlements`, `/api/paper/settlements`, `/api/paper/settlement-candidates`, `/api/paper/settlement-preview/{market_id}`, and `/api/paper/settle/{market_id}`.
- Adds CLI settlement commands: `--settlements`, `--settlement-candidates`, `--settlement-preview`, and `--settle-market --winning-outcome`.
- Updates paper analytics and trade CSV export so settlement rows count toward realized P&L and include settlement metadata.
- Keeps settlement deliberately manual: the operator must verify the real market resolution before closing simulated positions.

## What changed in v0.3.4-real


- Adds v0.3.4 Paper Trade Tickets: a human-in-the-loop decision ticket between readiness review and paper execution.
- Adds `/trade-tickets`, `/api/trade-tickets`, `/api/markets/{market_id}/trade-ticket`, and paper-ticket execution routes.
- Fixes a v0.3.2/v0.3.3 evidence import regression where automated evidence helpers shadowed the original evidence-packet functions.
- Fixes review/readiness helper plumbing so the review queue, readiness board, and evidence workbench use live Gamma market data instead of placeholder sync helpers.
- Improves readiness scoring to read `edge_percent`, numeric `confidence_score`, market evidence scores, thesis scores, and the composite readiness gate correctly.
- Refocuses on usability from the original roadmap: data -> evidence -> probability -> risk -> paper trading
- Adds a unified Operator Dashboard at `/operator`
- Adds `/api/operator/brief` for a single machine-readable daily brief
- Combines research targets, evidence gaps, alerts, paper recommendations, movers, portfolio status, and risk status
- Keeps all actions paper-only; no wallet, no signing, no live trading

Previous features remain available: Gamma ingestion, public CLOB read-only order books, snapshots, movers, watchlist, research/source registry, saved evidence packets, evidence-adjusted probability inputs, paper trading, local authentication, LAN access, and maintenance backups.

Security note: LAN exposure is for trusted local networks only. The app is not yet hardened for public internet exposure. Use a VPN, reverse proxy, or proper TLS/auth hardening before exposing it outside your LAN.

## Quick start

```bash
cd polymarket-gamma-starter-v1.0.0-real
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

Open locally:

```text
http://127.0.0.1:8000
```

For LAN access, v0.3.0 binds to `0.0.0.0` by default and prints detected LAN URLs on startup, such as:

```text
http://192.168.0.25:8000
```

From another device on the same LAN, open the printed LAN URL. If macOS prompts for firewall permission, allow incoming connections for Python/Terminal. To disable LAN access and return to local-only mode, set `HOST=127.0.0.1` in `.env`.

On first launch, the app redirects to `/setup`. Use username `admin` and create the first password there. After that, sign in at `/login`. Admin users can open `/users` to manage local accounts.

## Useful CLI commands

```bash
python3 -m app.cli --markets --limit 20
python3 -m app.cli --probabilities --limit 20
python3 -m app.cli --recommendations --limit 20
python3 -m app.cli --portfolio
python3 -m app.cli --risk
python3 -m app.cli --risk-check <market_id> --stake 100
python3 -m app.cli --risk-budget
python3 -m app.cli --risk-budget-detail <market_id>
python3 -m app.cli --export-risk-budget paper_risk_budget.csv
python3 -m app.cli --preflight
python3 -m app.cli --preflight-ticket <ticket_id>
python3 -m app.cli --export-preflight paper_preflight.csv
python3 -m app.cli --runbook
python3 -m app.cli --runbook-detail entry:<ticket_id>
python3 -m app.cli --ack-runbook-item entry:<ticket_id> --runbook-ack-status done --note "operator reviewed"
python3 -m app.cli --export-runbook paper_operator_runbook.csv
python3 -m app.cli --paper-ops-briefing
python3 -m app.cli --paper-ops-briefing --briefing-status action_required
python3 -m app.cli --record-briefing-checkpoint --briefing-checkpoint-status reviewed --note "morning review complete"
python3 -m app.cli --briefing-checkpoints
python3 -m app.cli --export-briefing paper_ops_briefing.csv
python3 -m app.cli --paper-handoffs
python3 -m app.cli --record-handoff --handoff-status handed_off --handoff-incoming evening --note "ready for next review"
python3 -m app.cli --handoff-detail <handoff_id>
python3 -m app.cli --export-handoffs paper_operator_handoffs.csv
python3 -m app.cli --handoff-reconciliation
python3 -m app.cli --handoff-reconciliation-detail <handoff_id>
python3 -m app.cli --export-handoff-reconciliation paper_handoff_reconciliation.csv
python3 -m app.cli --paper-ops-aging
python3 -m app.cli --ops-aging-detail <aging_item_id>
python3 -m app.cli --export-ops-aging paper_ops_aging.csv
python3 -m app.cli --paper-ops-escalations
python3 -m app.cli --create-ops-escalation <aging_item_id> --note "needs operator follow-up"
python3 -m app.cli --update-ops-escalation <escalation_id> --ops-escalation-status resolved --note "closed after review"
python3 -m app.cli --ops-escalation-detail <escalation_id>
python3 -m app.cli --export-ops-escalations paper_ops_escalations.csv
python3 -m app.cli --paper-ops-escalation-review
python3 -m app.cli --ops-escalation-review-detail <escalation_id>
python3 -m app.cli --export-ops-escalation-review paper_ops_escalation_review.csv
python3 -m app.cli --paper-ops-closeout
python3 -m app.cli --paper-ops-closeout-signoffs
python3 -m app.cli --record-ops-closeout-signoff --ops-closeout-signoff-status handed_off --note "handoff recorded"
python3 -m app.cli --live-config-readiness
python3 -m app.cli --export-live-config-template live_config_template.env
python3 -m app.cli --live-order-intents
python3 -m app.cli --preview-live-order-intent --live-intent-market <market_id> --live-intent-token-id <token_id> --live-intent-price 0.45 --live-intent-size 5
python3 -m app.cli --record-live-order-intent --live-intent-market <market_id> --live-intent-token-id <token_id> --live-intent-price 0.45 --live-intent-size 5 --live-intent-note "manual preview only"
python3 -m app.cli --export-live-order-intents live_order_intents.csv
python3 -m app.cli --live-order-intent-preflight
python3 -m app.cli --live-order-authorizations
python3 -m app.cli --live-execution-packets
python3 -m app.cli --live-dry-run-adapter
python3 -m app.cli --live-dry-run-review
python3 -m app.cli --live-dry-run-review-detail <packet_id> --json
python3 -m app.cli --export-live-dry-run-review live_dry_run_review.csv
python3 -m app.cli --live-adapter-readiness
python3 -m app.cli --preview-live-adapter-readonly-validation --json
python3 -m app.cli --record-live-adapter-readonly-validation --live-adapter-note "read-only validation"
python3 -m app.cli --live-adapter-requests
python3 -m app.cli --preview-live-adapter-request --live-adapter-request-packet-id <packet_id> --json
python3 -m app.cli --record-live-adapter-request --live-adapter-request-packet-id <packet_id> --live-adapter-note "request shape review"
python3 -m app.cli --manual-execution-reviews
python3 -m app.cli --record-manual-execution-review --manual-execution-review-packet-id <packet_id> --manual-execution-ack --live-adapter-note "final local review"
python3 -m app.cli --live-execution-control-readiness
python3 -m app.cli --preview-live-manual-submit --adapter-request-id <request_id> --adapter-mode fake_local --json
python3 -m app.cli --record-live-manual-submit --adapter-request-id <request_id> --adapter-mode fake_local --final-confirmation "<local phrase>"
python3 -m app.cli --live-execution-attempts
python3 -m app.cli --preview-live-manual-cancel --original-attempt-id <attempt_id> --adapter-mode fake_local --cancel-reason "operator test" --json
python3 -m app.cli --record-live-manual-cancel --original-attempt-id <attempt_id> --adapter-mode fake_local --final-confirmation "<local phrase>" --cancel-reason "operator test"
python3 -m app.cli --export-live-adapter-readiness live_adapter_readiness.csv
python3 -m app.cli --export-live-adapter-requests live_adapter_requests.csv
python3 -m app.cli --export-manual-execution-reviews manual_execution_reviews.csv
python3 -m app.cli --export-live-execution-attempts live_execution_attempts.csv
python3 -m app.cli --trades
python3 -m app.cli --notes
python3 -m app.cli --add-note <market_id> --note-text "Need to verify primary source" --note-tag research
python3 -m app.cli --run-backtest

python3 -m app.cli --sources
python3 -m app.cli --source-status
python3 -m app.cli --source-links "bitcoin ETF" --json
python3 -m app.cli --source-pack <market_id>
python3 -m app.cli --collection-targets <market_id>
python3 -m app.cli --collect-evidence <market_id>
python3 -m app.cli --evidence
python3 -m app.cli --evidence-score <packet_id_or_market_id>
python3 -m app.cli --playbooks
python3 -m app.cli --playbook-board --limit 20
python3 -m app.cli --playbook-fit <market_id>
python3 -m app.cli --assign-playbook <market_id> --playbook-id edge_evidence_confluence --note "operator reviewed"
python3 -m app.cli --playbook-decisions
python3 -m app.cli --playbook-performance
python3 -m app.cli --playbook-performance-detail edge_evidence_confluence
python3 -m app.cli --export-playbook-performance playbook_performance.csv
python3 -m app.cli --trade-tickets
python3 -m app.cli --create-ticket <market_id> --stake 50 --outcome YES
python3 -m app.cli --ticket-detail <ticket_id>
python3 -m app.cli --update-ticket <ticket_id> --ticket-status archived
python3 -m app.cli --settlement-candidates
python3 -m app.cli --settlement-preview <market_id> --winning-outcome YES
python3 -m app.cli --settle-market <market_id> --winning-outcome YES --note "Resolved YES"
python3 -m app.cli --settlements
python3 -m app.cli --paper-positions
python3 -m app.cli --position-alerts
python3 -m app.cli --set-position-plan <market_id> --outcome YES --target-price 0.75 --stop-price 0.35 --position-status watch
python3 -m app.cli --exit-tickets
python3 -m app.cli --create-exit-ticket <market_id> --outcome YES --shares 10 --exit-price 0.62
python3 -m app.cli --execute-exit-ticket <ticket_id>
python3 -m app.cli --audit-log
python3 -m app.cli --audit-market <market_id>
python3 -m app.cli --export-audit paper_audit.csv
python3 -m app.cli --review-report
python3 -m app.cli --review-market <market_id>
python3 -m app.cli --export-review-report paper_review_report.csv
```

Main browser views:

```text
/                       main dashboard
/operator               daily operator brief
/readiness              paper readiness board
/playbooks              strategy playbook classifier
/playbook-performance   playbook performance review
/risk-budget            paper risk budget review
/preflight              paper entry preflight gate
/approvals              paper execution approvals
/execution-queue        paper execution queue
/runbook                paper operator runbook/checklist
/paper-ops-briefing    daily paper ops briefing/checkpoints
/paper-handoffs        saved paper operator handoff packets
/paper-handoff-reconciliation
                        read-only handoff reconciliation board
/paper-ops-aging       stale-workload and handoff aging review
/paper-ops-escalations local escalation register for aging items
/paper-ops-escalation-review
                        read-only escalation review against current aging
/paper-ops-closeout    end-of-shift closeout checklist
/paper-ops-closeout-signoffs
                        local closeout signoff snapshots
/live-config           redacted live configuration readiness
/live-order-intents    dry-run live order intent preview ledger
/live-order-intent-preflight
                        read-only live intent preflight/binding review
/live-order-authorizations
                        local live operator authorization snapshots
/live-execution-packets
                        unsigned local execution packet review
/live-dry-run-adapter
                        offline dry-run adapter receipt ledger
/live-dry-run-review
                        read-only packet/receipt reconciliation board
/live-adapter          live adapter readiness and read-only validation
/live-adapter-requests local adapter request validation ledger
/manual-execution-boundary
                        local manual execution review scaffold
/live-manual-execution
                        final manual submit control plane
/live-execution-attempts
                        local execution attempt ledger
/live-manual-cancel    manual cancel scaffold
/trade-tickets          paper trade ticket queue
/settlements            manual paper settlement workflow
/positions              paper position lifecycle manager
/exit-tickets           paper exit ticket queue
/audit                  unified paper audit ledger
/review-report          paper post-trade review report
/research/sources       source registry
/research/evidence      saved evidence packets
/users                  admin user management
```

## Risk limits

Defaults are intentionally conservative for simulation:

```env
PAPER_MAX_STAKE_PER_TRADE=250
PAPER_MAX_MARKET_EXPOSURE=500
PAPER_MAX_TOTAL_EXPOSURE=2500
PAPER_MAX_OPEN_POSITIONS=20
PAPER_MIN_LIQUIDITY=1000
PAPER_MIN_VOLUME_24HR=10
PAPER_BLOCK_EXTREME_PRICES=true
PAPER_MIN_PRICE=0.02
PAPER_MAX_PRICE=0.98
```

Risk checks block paper buys that exceed stake, market exposure, total exposure, position-count, cash, or price-bound limits. Liquidity and volume are warnings in v0.2.2 so the scanner remains usable on small markets.

## API routes added in v0.2.2

```http
GET  /api/notes
GET  /api/markets/{market_id}/notes
POST /api/markets/{market_id}/notes?text=...&tag=research
```

Strategy playbook routes added in v0.4.0 and v0.4.1:

```http
GET  /api/playbooks
GET  /api/playbooks/board
GET  /api/playbooks/{playbook_id}
GET  /api/markets/{market_id}/playbook-fit
GET  /api/playbook-decisions
POST /api/markets/{market_id}/playbook-decision
GET  /api/playbook-performance
GET  /api/playbook-performance/{playbook_id}
GET  /api/playbook-performance.csv
GET  /api/paper/risk-budget
GET  /api/paper/risk-budget/{market_id}
GET  /api/paper/risk-budget.csv
GET  /api/paper/preflight
GET  /api/paper/preflight/{ticket_id}
GET  /api/paper/preflight.csv
POST /api/trade-tickets/{ticket_id}/preflight
```

Paper operator routes added in v0.4.7 through v0.5.4:

```http
GET  /api/paper/briefing
GET  /api/paper/briefing.csv
GET  /api/paper/briefing/checkpoints
POST /api/paper/briefing/checkpoint
GET  /api/paper/handoffs
GET  /api/paper/handoffs/{handoff_id}
GET  /api/paper/handoffs.csv
POST /api/paper/handoffs
GET  /api/paper/handoffs/reconciliation
GET  /api/paper/handoffs/{handoff_id}/reconciliation
GET  /api/paper/handoffs/reconciliation.csv
GET  /api/paper/ops-aging
GET  /api/paper/ops-aging/{item_id}
GET  /api/paper/ops-aging.csv
GET  /api/paper/ops-escalations
GET  /api/paper/ops-escalations/{escalation_id}
GET  /api/paper/ops-escalations.csv
POST /api/paper/ops-escalations
POST /api/paper/ops-escalations/{escalation_id}
GET  /api/paper/ops-escalations/review
GET  /api/paper/ops-escalations/{escalation_id}/review
GET  /api/paper/ops-escalations/review.csv
GET  /api/paper/ops-closeout
GET  /api/paper/ops-closeout.csv
GET  /api/paper/ops-closeout/signoffs
GET  /api/paper/ops-closeout/signoffs/{signoff_id}
GET  /api/paper/ops-closeout/signoffs.csv
POST /api/paper/ops-closeout/signoffs
```

Operator console routes added in v0.8.0:

```http
GET  /
GET  /workflow
GET  /api/ui/workflow
GET  /ui-system
```

The console groups existing routes into Overview, Research, Paper Workflow, Risk / Ops, Live Readiness, Manual Boundary, Audit / Reports, and Settings / Config. These routes are navigation and presentation improvements only; they do not introduce trading automation or loosen existing approval, preflight, risk, audit, dry-run, authorization, or manual-execution controls.

Operator console docs:

- `docs/UI_UX_REFRESH.md`
- `docs/OPERATOR_CONSOLE_GUIDE.md`

Market data intelligence routes added in v0.9.0:

```http
GET  /market-data
GET  /market-data/snapshots
GET  /market-data/snapshots/{snapshot_id}
GET  /api/market-data/snapshots
GET  /api/market-data/snapshots/{snapshot_id}
GET  /api/market-data/snapshots.csv
POST /api/market-data/snapshots
POST /api/market-data/snapshots/parse-preview
POST /api/market-data/snapshots/fetch-preview
POST /api/market-data/snapshots/fetch-record
GET  /execution-quality
GET  /execution-quality/{simulation_id}
GET  /api/execution-quality
GET  /api/execution-quality/{simulation_id}
GET  /api/execution-quality.csv
POST /api/execution-quality/preview
POST /api/execution-quality/record
```

Market data CLI commands added in v0.9.0:

```bash
python -m app.cli --market-data-snapshots --json
python -m app.cli --parse-market-data-snapshot-preview --orderbook-json @fixture.json --json
python -m app.cli --record-market-data-snapshot --orderbook-json @fixture.json --source local_fixture --json
python -m app.cli --fetch-market-data-snapshot-preview --market-id <market_id> --token-id <token_id> --json
python -m app.cli --export-market-data-snapshots market_data_snapshots.csv
python -m app.cli --preview-execution-quality --market-id <market_id> --token-id <token_id> --side BUY --price 0.51 --size 10 --json
python -m app.cli --record-execution-quality --snapshot-id <snapshot_id> --side BUY --price 0.51 --size 10 --json
python -m app.cli --execution-quality --json
python -m app.cli --export-execution-quality execution_quality.csv
```

Market data docs:

- `docs/MARKET_DATA_INTELLIGENCE.md`
- `docs/ORDERBOOK_METRICS.md`
- `docs/EXECUTION_QUALITY_SIMULATOR.md`

Live configuration readiness routes added in v0.5.5:

```http
GET  /live-config
GET  /api/live/config/readiness
GET  /api/live/config/readiness.csv
GET  /api/live/config/template.env
```

Live order intent preview routes added in v0.5.6, preflight routes added in v0.5.7, authorization snapshot routes added in v0.5.8, unsigned execution packet routes added in v0.5.9, dry-run adapter receipt routes added in v0.5.10, and dry-run review routes added in v0.5.11:

```http
GET  /live-order-intents
GET  /api/live/order-intents
GET  /api/live/order-intents/{intent_id}
GET  /api/live/order-intents.csv
POST /api/live/order-intents/preview
POST /api/live/order-intents
GET  /live-order-intent-preflight
GET  /api/live/order-intents/preflight
GET  /api/live/order-intents/{intent_id}/preflight
GET  /api/live/order-intents/preflight.csv
GET  /live-order-authorizations
GET  /api/live/order-intents/authorizations
GET  /api/live/order-intents/authorizations/{authorization_id}
GET  /api/live/order-intents/authorizations.csv
POST /api/live/order-intents/{intent_id}/authorization
GET  /live-execution-packets
GET  /api/live/execution-packets
GET  /api/live/execution-packets/{packet_id}
GET  /api/live/execution-packets.csv
POST /api/live/order-intents/{intent_id}/execution-packet/preview
POST /api/live/order-intents/{intent_id}/execution-packet
GET  /live-dry-run-adapter
GET  /api/live/dry-run-adapter
GET  /api/live/dry-run-adapter/{receipt_id}
GET  /api/live/dry-run-adapter.csv
POST /api/live/execution-packets/{packet_id}/dry-run/preview
POST /api/live/execution-packets/{packet_id}/dry-run
GET  /live-dry-run-review
GET  /api/live/dry-run-review
GET  /api/live/dry-run-review/{packet_id}
GET  /api/live/dry-run-review.csv
```

Live adapter readiness, adapter request validation, and manual execution boundary routes added in v0.6.0:

```http
GET  /live-adapter
GET  /api/live/adapter/readiness
GET  /api/live/adapter/readiness.csv
GET  /api/live/adapter/readonly-validations
GET  /api/live/adapter/readonly-validations/{validation_id}
GET  /api/live/adapter/readonly-validations.csv
POST /api/live/adapter/readonly-validation/preview
POST /api/live/adapter/readonly-validation
GET  /live-adapter-requests
GET  /api/live/adapter/requests
GET  /api/live/adapter/requests/{request_or_packet_id}
GET  /api/live/adapter/requests.csv
POST /api/live/execution-packets/{packet_id}/adapter-request/preview
POST /api/live/execution-packets/{packet_id}/adapter-request
GET  /manual-execution-boundary
GET  /api/live/manual-execution-reviews
GET  /api/live/manual-execution-reviews/{review_id}
GET  /api/live/manual-execution-reviews.csv
POST /api/live/execution-packets/{packet_id}/manual-execution-review/preview
POST /api/live/execution-packets/{packet_id}/manual-execution-review
```

Manual live execution control-plane routes added in v0.7.0:

```http
GET  /live-manual-execution
GET  /live-execution-attempts
GET  /live-manual-cancel
GET  /api/live/execution-control/readiness
GET  /api/live/execution-control/readiness.csv
GET  /api/live/execution-attempts
GET  /api/live/execution-attempts/{attempt_id}
GET  /api/live/execution-attempts.csv
POST /api/live/adapter/requests/{adapter_request_id}/manual-submit/preview
POST /api/live/adapter/requests/{adapter_request_id}/manual-submit
POST /api/live/manual-cancel/preview
POST /api/live/manual-cancel
```

Paper analytics routes retained from v0.1.3:

```http
GET /api/paper/analytics
GET /api/paper/trades.csv
GET /api/paper/audit
GET /api/paper/audit/{market_id}
GET /api/paper/audit.csv
GET /api/paper/review-report
GET /api/paper/review-report/{market_id}
GET /api/paper/review-report.csv
GET /api/paper/settlements
GET /api/paper/settlement-candidates
GET /api/paper/settlement-preview/{market_id}
POST /api/paper/settle/{market_id}
GET /api/paper/positions
GET /api/paper/position-alerts
POST /api/paper/positions/{market_id}/plan
GET /api/exit-tickets
POST /api/paper/positions/{market_id}/exit-ticket
POST /api/exit-tickets/{ticket_id}/paper-sell
```

Risk routes retained from v0.1.2:

```http
GET /api/risk/status
GET /api/risk/check/{market_id}?stake=100&outcome=YES
```

Existing paper-trading routes:

```http
GET  /api/portfolio
GET  /api/paper/trades
POST /api/paper/buy/{market_id}
POST /api/paper/sell/{market_id}
POST /api/paper/reset
```

## API keys

None required for v0.2.2.

Gamma, public CLOB book reads, local probability scoring, local strategy recommendations, paper trading, backtests, and paper risk controls all run without keys.

Future optional keys:

- `OPENAI_API_KEY` or another LLM key for AI research summaries
- News/search API key for automated source retrieval
- Polymarket wallet/private key/API credentials only when a future execution-gated live trading phase is explicitly built

Do not enter wallet/private-key material into this project yet.


## v0.2.2 additions

- Paper analytics summary for simulated trades
- Recent trade journal on the dashboard
- CSV export at `/api/paper/trades.csv`
- JSON analytics at `/api/paper/analytics`
- CLI analytics/export commands:

```bash
python3 -m app.cli --paper-analytics
python3 -m app.cli --export-trades paper_trades.csv
```

No API keys are needed for v0.2.2. This version is still local, read-only, and paper-only.


## Auth and user-management routes added in v0.2.2

```http
GET  /setup
POST /setup
GET  /login
POST /login
GET  /logout
GET  /users
POST /users/create
POST /users/update/{username}
POST /users/delete/{username}
GET  /api/auth/me
GET  /api/users
POST /api/users?username=...&password=...&role=read_only
PATCH /api/users/{username}?role=admin&status=active
DELETE /api/users/{username}
```

Initial account:

```text
username: admin
password: prompted during first-run setup
```

Roles:

- `admin`: full local app access, including paper trades, notes, watchlist edits, snapshots, backtests, and user management.
- `read_only`: dashboard/API viewing only; no mutating actions.

The local session secret is stored in `data/session_secret.txt`. User records are stored in `data/users.json`. Do not commit either file to Git.

## Network security routes added in v0.2.2

- `GET /api/network/status` — Admin-only LAN/security diagnostics.

## LAN hardening notes

For quick LAN use, keep `ALLOWED_HOSTS=*`. For a stable workstation/NAS IP, prefer:

```env
HOST=0.0.0.0
PORT=8000
ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.50
```

Set `SESSION_COOKIE_SECURE=true` only when serving the app over HTTPS.


## v0.2.2 - Deployment/Admin Configuration

This release adds an admin-only deployment configuration panel at `/administration/config` and JSON status at `/api/deployment/status`.

It shows:

- local and LAN URLs
- bind host and port
- allowed hosts
- startup safety checks
- masked runtime environment settings
- warnings for LAN-friendly but less strict settings such as `ALLOWED_HOSTS=*`

Recommended LAN test settings in `.env`:

```env
HOST=0.0.0.0
PORT=8000
ALLOWED_HOSTS=*
SESSION_COOKIE_SECURE=false
```

For a stable LAN deployment, replace `ALLOWED_HOSTS=*` with the machine IP and localhost values, for example:

```env
ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.50
```

No Polymarket, OpenAI, or trading API keys are required for this version.

## v0.2.2 Maintenance

Admin users can open `/administration/maintenance` to view local data inventory and create/download/delete local backup ZIPs.

Backup scope: local `data/` files, snapshots, users, watchlist, notes, portfolio, and paper-trading journal. Restore is intentionally not exposed in the browser yet to avoid accidental overwrite.

## v0.2.2 - Research/Data Collection Refocus

This iteration intentionally returns to the original roadmap instead of expanding unrelated administration features.

Added:

- Local research source registry
- `/research/sources` page
- `/api/sources`
- `/api/source-links?q=...`
- `/api/markets/{market_id}/source-pack`
- Market-detail source packs grouped by news, social, government data, and market lookup
- CLI source commands:

```bash
python3 -m app.cli --sources
python3 -m app.cli --source-links "bitcoin ETF approval"
python3 -m app.cli --source-pack MARKET_ID
```

Keys needed: still none. These are no-key research entry points only. Later AI/LLM extraction may use OpenAI/Anthropic keys, and live trading will require Polymarket/Polygon credentials, but neither is part of this release.

## v0.2.4 - Evidence Packet Collection

v0.2.4 continues the original roadmap by strengthening the research/data collection layer before any AI model keys or live trading are introduced.

New local-only features:

- Saved evidence packets in `data/evidence_packets/`
- Evidence packet page at `/research/evidence`
- Market detail button to create an evidence packet
- Evidence packet APIs:
  - `GET /api/evidence`
  - `GET /api/evidence/{packet_id}`
  - `DELETE /api/evidence/{packet_id}`
  - `POST /api/markets/{market_id}/evidence-packet`
  - `GET /api/markets/{market_id}/evidence-packets`
- CLI commands:
  - `python3 -m app.cli --evidence`
  - `python3 -m app.cli --collect-evidence <market_id>`
  - `python3 -m app.cli --evidence-detail <packet_file.json>`

Evidence packets are manual research artifacts. They create source checklists and analysis templates, but they do not scrape paywalled pages, call LLMs, place trades, sign orders, or require external API keys.

Keys needed: none.

## v0.3.0 - Operator dashboard

New in v0.3.0:

- `/operator` daily operator dashboard
- `/api/operator/brief` unified JSON brief
- Action queue that merges alerts and paper recommendations
- Research target list based on watchlist, opportunity score, volume, and model/market gap
- Evidence-gap list for high-interest markets without enough saved evidence

## v0.2.6 - Evidence-adjusted probability inputs

This release stays on the original roadmap: data collection -> evidence -> probability -> risk -> paper trading.

New in v0.2.6:

- Evidence packets now feed a conservative probability-input layer.
- Market detail pages show an Evidence-Adjusted Probability panel.
- New API endpoints:
  - `GET /api/markets/{market_id}/evidence-probability`
  - `GET /api/evidence-probabilities`
- New CLI commands:
  - `python3 -m app.cli --evidence-probability <market_id>`
  - `python3 -m app.cli --evidence-probabilities --limit 20`

This does not enable live trading, wallet integration, signing, or authenticated Polymarket order execution.


## v0.3.1 - Thesis Scoring + Review Queue

Continues the original roadmap:

`data -> evidence -> thesis -> probability -> risk -> paper trading`

New routes:

- `/review-queue`
- `/api/review-queue`
- `/api/thesis-scores`
- `/api/markets/{market_id}/thesis-score`

Purpose:

- Turn opportunities into actionable workflow stages.
- Identify which markets need evidence, thesis work, risk review, or paper-trade review.
- Add explainable thesis scoring so notes/theses become model inputs instead of static text.

No external API keys are required.
No wallet or live trading is included.


## v0.3.2 - Evidence Automation Workbench

Continues the original roadmap:

`data -> evidence -> thesis -> probability -> risk -> paper trading`

New routes:

- `/evidence-workbench`
- `/api/evidence-workbench`
- `/api/markets/{market_id}/evidence/auto-packet`
- `/api/markets/{market_id}/evidence-tasks`

Purpose:

- Make evidence collection practical instead of purely manual.
- Generate market-specific evidence packets.
- Suggest queries and credible source targets.
- Create task lists for supporting evidence, contradicting evidence, and claim extraction.

No external API keys are required.
No wallet or live trading is included.


## v0.3.3 - Paper Readiness Board

Continues the original roadmap:

`data -> evidence -> thesis -> probability -> risk -> paper trading`

New routes:

- `/readiness`
- `/api/readiness-board`
- `/api/markets/{market_id}/readiness`

Purpose:

- Add a decision gate before simulated paper trades.
- Combine edge, confidence, evidence score, thesis score, and risk score.
- Classify markets as Evidence Needed, Thesis Needed, Risk Review, Monitor, Review, or Paper Trade Ready.
- Make the app more usable as a daily operator tool.

No external API keys are required.
No wallet or live trading is included.


## v0.3.4 - Paper Trade Tickets

This iteration adds the missing operator handoff between the readiness board and simulated paper trading. A trade ticket captures:

- market ID/title and Polymarket URL snapshot
- outcome, price, stake, estimated shares
- readiness score and blockers
- risk-check result at the proposed stake
- human-review checklist
- local operator decision and notes
- optional simulated paper-buy execution status

Browser routes:

```text
GET  /trade-tickets
GET  /api/trade-tickets
GET  /api/trade-tickets/{ticket_id}
POST /api/markets/{market_id}/trade-ticket
POST /markets/{market_id}/trade-ticket
POST /api/trade-tickets/{ticket_id}/status
POST /api/trade-tickets/{ticket_id}/paper-buy
```

The paper-buy route still uses the existing paper-trading engine and risk checks. It does not connect to a wallet, sign orders, or perform live trading.

## v0.3.4 maintenance fixes

- Aliased the original evidence module and the v0.3.2 evidence-automation module so their similarly named functions no longer collide at runtime.
- Updated the review queue/readiness/evidence-workbench data helpers to call the async Gamma client correctly.
- Updated readiness scoring to handle opportunity-engine rows correctly, including `edge_percent` and `confidence_score`.


## v1.5.0 Market Data Ingestion + Dataset Builder

This release adds a local-first data foundation for the Training & Evaluation Lab:

- data source registry for local/import and disabled network sources,
- explicit ingestion job registry,
- raw snapshot registry with hashes,
- normalized market-data records,
- labeling workbench,
- reproducible dataset builder,
- dataset manifest inspection,
- leakage and bias warnings,
- UI/API/CLI surfaces under `/data` and `/training/dataset-builder`.

Safety posture remains fail-closed: data ingestion does not trade, network ingestion is disabled by default, ingestion schedulers are disabled, training outputs do not directly live-trade, and generated runtime data is excluded from release ZIPs.


## v1.6.0-real Mobile-Friendly Operator Console

This release refreshes the operator console UI/UX for desktop, tablet, mobile browser, narrow Atlas side panels, and LAN use from a phone or tablet. It adds a responsive base layout, collapsible mobile navigation, a global safety banner, larger touch targets, cleaner cards, safer table wrappers, improved empty states, and clearer operator next-step guidance.

Safety posture is unchanged: the UI never bypasses backend gates. Live trading, real network, submit, cancel, autonomous mode, and data network ingestion remain disabled by default. Dangerous actions remain separated from read-only status areas and require backend confirmations/gates.

## v1.5.0 Internet ingestion and host training jobs

This release adds an operator-controlled internet ingestion and host training job runner milestone. Internet ingestion is disabled by default, requires approved sources and allowlisted domains, and is limited to public/read-only data fetches. Data ingestion does not trade. Host training jobs are disabled by default, use approved internal job types only, and write artifacts to runtime data directories that are excluded from release ZIPs. Training outputs remain manual-review-only and do not directly live-trade.

## v1.6.0 scoped historical backfill and category datasets

This release adds an operator-controlled medium-large data workflow for hundreds-of-thousands-scale local training: reusable market/category scopes, scoped backfill previews, pagination/cursor/offset plans, deduplication plans, dataset size estimates for 16 GB RAM-class hosts, category dataset builds, and batch-training guardrails. Network ingestion remains disabled by default, data ingestion does not trade, and generated training outputs remain manual-review only.
