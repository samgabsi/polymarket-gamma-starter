# Operator Console Guide

Version: v0.9.0-real

Polymarket Gamma Starter is a local-first, human-in-the-loop console for Polymarket research, paper operations, risk review, audit, and staged live-readiness. The console is organized around visible workflow stages so the operator can see what is paper-only, what needs review, what is blocked, what can be exported, and what has not been submitted.

## Start Here

1. Open `/` after signing in.
2. Review the safety badges: `LOCAL`, `PAPER ONLY`, and `LIVE DISABLED`.
3. Check the recommended next operator actions.
4. Open `/workflow` when you need a stage-by-stage map.

## Workflow Stages

Research:
Use market pages, opportunity scan, source checks, and evidence packets to decide whether a market deserves further review.

Playbooks:
Use playbook fit and decisions to tie a market to a repeatable strategy before paper workflow activity.

Market Data:
Use `/market-data` and `/execution-quality` to inspect local order-book snapshots, stale data, spread, depth, estimated fill quality, slippage, and insufficient-depth blockers before paper or live-readiness review.

Paper Tickets:
Use `/trade-tickets` for human-in-the-loop paper decisions. Tickets remain local records and do not place real trades.

Review / Approvals:
Use `/approvals` to document review state before paper execution. Approval records do not bypass preflight or risk checks.

Risk / Preflight:
Use paper preflight and risk pages to inspect exposure, position limits, blockers, warnings, and readiness state before any paper action.

Ops / Closeout:
Use briefing, handoffs, aging, escalation, reconciliation, closeout, and signoff pages to manage paper operations and hand over unresolved work.

Live Readiness:
Use `/live-config`, `/live-order-intents`, `/live-order-intent-preflight`, `/live-order-authorizations`, `/live-execution-packets`, `/live-dry-run-adapter`, `/live-dry-run-review`, `/live-adapter`, and `/live-adapter-requests` to inspect staged live-readiness artifacts. These pages do not submit or cancel exchange orders.

Manual Execution Boundary:
Use `/manual-execution-boundary`, `/live-manual-execution`, `/live-execution-attempts`, and `/live-manual-cancel` for final local control-plane records. Fake-local receipts are simulations only and are not exchange acknowledgements.

Audit / Reports:
Use `/audit`, CSV export links, and API links to inspect what happened and preserve operator traceability.

## Safety Rules

- Treat all live-readiness pages as review and documentation surfaces.
- Treat market-data and execution-quality outputs as estimates, not fill guarantees.
- Do not interpret `ready`, `validated`, or `authorized` UI states as exchange submission.
- Confirm that `LIVE_TRADING_ENABLED=false`, `POLYMARKET_LIVE_ENABLE_SUBMIT=false`, and `POLYMARKET_LIVE_ENABLE_CANCEL=false` unless you are intentionally testing a future execution-capable build.
- Keep `.env`, credential files, private keys, user records, sessions, local ledgers, and generated state out of shared ZIPs.
- Use the kill switch whenever reviewing live-adjacent workflows under uncertainty.

## Exports And APIs

Most workflow pages preserve existing JSON and CSV routes. The v0.8 UI adds presentation-only navigation and cross-links; it does not change the meaning of exported records.

## First-Run Notes

On a fresh install, many sections will show empty states. That is expected. Create research evidence, paper tickets, approvals, preflight records, handoffs, closeout records, and live-readiness previews through the existing workflows or CLI commands before expecting populated tables.
