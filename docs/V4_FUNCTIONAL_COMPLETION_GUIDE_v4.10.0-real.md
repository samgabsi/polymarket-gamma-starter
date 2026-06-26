# v4.10.0 Functional Completion Guide

v4.10.0-real keeps the visible-control rule: a visible action must work, navigate to a real route, save state, or clearly state why it is unavailable.

## Cockpit

The `/v3/cockpit` layout selector, saved-layout copy action, and focused review modes remain POST-backed and persisted through the cockpit settings store. Layout and focus changes write local audit records and do not mutate live trading state.

## Opportunity review

The Opportunity Review Workbench and Market Detail review panel now use browser POST forms for operator notes and review status transitions. The JSON APIs remain available for programmatic clients, but the UI no longer presents those POST APIs as normal GET links.

## AI News Odds

Market News Odds controls now submit to page POST wrappers for search planning, gated web-search preview, manual evidence, and draft adjustment generation. The wrapper responses preserve the same review-only flags as the JSON APIs.

## Cross-market arbitrage

Arbitrage review decisions are POST-backed from the UI. The old compatibility GET route is informational and reports that POST is required instead of recording a local review action.

## Feature status

Open `/api/v3/features/status` for the readiness registry. v4.10 adds explicit entries for opportunity review actions, AI odds page actions, arbitrage review actions, and AI/arbitrage configuration surfacing.

## Safety

These controls record local review state only. They do not place orders, cancel orders, approve trades, sign transactions, arm live trading, call AI or web providers unless explicitly configured, bypass backend gates, or provide financial advice.
