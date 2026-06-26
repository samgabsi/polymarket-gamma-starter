# v4.17.0-real Release Notes

v4.17.0-real is a UI/UX consolidation release. The application had accumulated many route families and detail pages. This release introduces a five-workspace Operator OS model so operators can start from a smaller, clearer navigation surface while retaining compatibility with existing detailed workflows.

## Five primary workspaces

1. **Command Center** (`/v3`) — safety posture, readiness warnings, paper automation status, review activity, AI/opportunity counts, and next recommended operator action.
2. **Opportunities** (`/v3/opportunities`) — existing opportunity workbench plus source-specific links to AI Odds, Arbitrage, Paper Strategy, and Review Queue records.
3. **Automation / Paper Trading** (`/v3/automation`) — paper-only automation summary, run-once control, paper account, latest run, decisions, paper orders, and links to the detailed `/v3/paper-trading` page.
4. **Review & Audit** (`/v3/review-audit`) — review queue actions, opportunity decisions, paper decisions, paper audit rows, and accountability events.
5. **Settings & System** (`/v3/settings-system`) — feature readiness highlights, AI/OpenAI status, venues, paper limits, arbitrage config, diagnostics, and advanced links.

## Compatibility

Detailed/source routes remain available. `/v3/paper-trading`, `/v3/arbitrage`, `/v3/ai/news-odds`, `/review-queue`, `/v3/settings`, `/v3/feature-readiness`, `/v3/cockpit`, and `/v2-live` are preserved and linked from the consolidated workspaces.

## Safety

This release does not enable live trading. It does not submit orders, cancel orders, approve trades, arm autonomous live execution, bypass kill switches, or present sample/scaffolded data as live. Paper trading APIs continue to report `paper_only=true` and `live_execution_used=false`.
