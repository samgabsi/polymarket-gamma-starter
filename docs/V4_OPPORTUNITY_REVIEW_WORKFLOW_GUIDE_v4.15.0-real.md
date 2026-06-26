# Opportunity and Review Queue Workflow Guide - v4.15.0-real

v4.15 preserves the v4.15 Opportunity Review Workbench and adds a completed Review Queue operator-action workflow.

## Review Queue actions

The legacy `/review-queue` page now supports local review actions:

- Mark reviewed
- Watchlist
- Send to paper review
- Dismiss

Each action writes local JSONL records only. The action record captures target id/name, previous/new state, reason, source route/component, data state, freshness, review-only posture, live-disabled posture, and no-order flags.

## Opportunity Review Workbench

The v4.15 Opportunity Review Workbench remains available at `/v3/opportunities` and keeps explicit data-mode selection plus notes/watchlist/paper-review/reject/archive actions.

## Safety

Neither Review Queue nor Opportunity Review actions place orders, cancel orders, approve trades, arm live trading, or bypass safety gates.
