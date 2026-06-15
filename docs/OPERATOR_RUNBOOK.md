# v1.4.0 Mobile Runbook Update

The runbook remains read-only. On mobile, use the global safety banner and collapsible menu before starting a workflow. Confirm LIVE DISABLED, REAL NETWORK DISABLED, KILL SWITCH ACTIVE, SUBMIT DISABLED, CANCEL DISABLED, AUTONOMOUS OFF, and DATA INGESTION LOCAL ONLY unless deliberately changing a lab setting.

# Operator Runbook

Polymarket Gamma Starter v1.1.0 adds a practical runbook for live operations. The runbook is available at `/operator-runbook`, `/api/operator-runbook`, and `--operator-runbook`.

The runbook is instructional only. It never changes environment variables, starts a scheduler, submits an order, cancels an order, signs a payload, or touches wallet material.

## Required operating sequence

1. Start the app on a trusted host.
2. Confirm `/health` reports the expected version.
3. Confirm authentication and administrator status.
4. Review `/live-trading` and the live readiness checklist.
5. Confirm the kill switch is active until the final live-operation window.
6. Review `/live-clob-adapter` and the verification report.
7. Confirm market and token allowlists are exact and minimal.
8. Confirm notional/risk limits are tiny for first live tests.
9. Review paper approvals, preflight, live authorizations, and execution packets.
10. Run fake-local submit/cancel checks first.
11. Run read-only reconciliation.
12. Only then consider optional read-only network checks.
13. Only then consider manual live submit/cancel with explicit confirmation.
14. Restore kill switch and disable live flags after the session.

## Safety reminders

Live trading is dangerous. This software is not financial advice. Automated validation does not submit or cancel real orders. Fake adapter receipts are local simulations and not exchange acknowledgements.

## v1.5.0 Internet ingestion and host training jobs

This release adds an operator-controlled internet ingestion and host training job runner milestone. Internet ingestion is disabled by default, requires approved sources and allowlisted domains, and is limited to public/read-only data fetches. Data ingestion does not trade. Host training jobs are disabled by default, use approved internal job types only, and write artifacts to runtime data directories that are excluded from release ZIPs. Training outputs remain manual-review-only and do not directly live-trade.
