# v4.17.0-real — Operator OS UI/UX Consolidation and Five-Workspace Navigation

- Consolidated the primary UI model into five operator workspaces: Command Center, Opportunities, Automation / Paper Trading, Review & Audit, and Settings & System.
- Added `app/operator_os.py` as a local-first workspace context layer that summarizes safety posture, feature readiness, paper automation, opportunity sources, review/audit rows, compatibility routes, and UI sprawl classifications.
- Added `app/templates/operator_os_v417.html` for the consolidated Operator OS shell.
- Updated `/v3` and `/v3/command-center` to render the new Command Center workspace.
- Added `/v3/automation`, `/v3/review-audit`, and `/v3/settings-system` workspaces plus `/api/v3/operator-os` workspace context endpoints.
- Preserved existing backend functionality and source-specific pages. Old routes such as `/v3/opportunities`, `/v3/ai/news-odds`, `/v3/arbitrage`, `/v3/paper-trading`, `/review-queue`, `/v3/settings`, and `/v3/feature-readiness` remain available as compatibility/detail routes.
- Reduced the primary sidebar model to the consolidated workspace flow while demoting detailed/source/legacy routes into Source Details and Advanced / Legacy groups.
- Added workspace bridge links to the opportunity workbench, paper trading detail page, and review queue page.
- Added Operator OS feature-readiness and stub burn-down rows so the consolidation is visible in readiness/status reports.
- Added targeted v4.17 tests for workspace rendering, compatibility routes, safe Operator OS API responses, paper-only preservation, and feature readiness truthfulness.

Safety posture: v4.17 is an information-architecture and UI consolidation pass only. It does not enable live trading, submit orders, cancel orders, approve trades, arm autonomous live execution, bypass kill switches, or turn sample/cached/scaffolded data into live data.

# v4.16.0-real — Automated Paper Trading, Simulated Broker, and Risk-Gated Strategy Loop

- Added a paper-only automated strategy runner that can evaluate candidate signals, apply edge/confidence/freshness/spread/slippage/mismatch/risk-budget gates, and create simulated orders only when `PAPER_TRADING_ENABLED=true` and `PAPER_TRADING_AUTOMATION_ENABLED=true`.
- Added `app/paper_automation.py` with local JSON/JSONL account, order, fill, position, decision, run, and audit storage.
- Added a conservative simulated paper broker that never calls real submit/cancel APIs, marks every order/fill as `paper_only=true`, and returns `live_execution_used=false`.
- Added `/v3/paper-trading` plus `/api/v3/paper/*` endpoints for paper account, orders, fills, positions, decisions, runs, audit, run-once, reset, and paper cancellation.
- Added paper trading config variables to `.env.example`, settings validation, feature readiness, docs, and targeted regression tests.

Safety posture: v4.16 adds automation only for paper trading. It does not place real orders, cancel real orders, arm live trading, bypass kill switches, or claim paper trading proves profitability. Live execution remains separately gated.
