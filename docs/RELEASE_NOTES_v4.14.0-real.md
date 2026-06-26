# Release Notes - v4.14.0-real

Target version: `4.14.0-real`.

v4.14.0-real is an Opportunity Review / Operator Action workflow hardening pass. It keeps the v4.13 arbitrage scan persistence workflow and completes the next highest-priority review gap: visible data-mode selection, row-level data-state truthfulness, and enriched audit metadata for opportunity notes, watchlist, paper-review, reject, and archive actions.

## Operator Workflow Completed

- `/v3/opportunities` now uses an explicit data-mode selector instead of a demo checkbox.
- Workbench JSON and HTML expose `data_state`, `resolved_data_mode`, `source_state`, `data_state_reason`, `operator_implication`, `safe_review_only`, and `live_disabled`.
- Opportunity rows carry data-state, freshness, source route/component, review source, row-level no-live-mutation flags, and next-action metadata.
- Browser POST forms for notes and status decisions now submit source route, source component, previous state, reason, data state, and freshness.
- Market detail pages show the active data state and render enriched audit history.
- JSON APIs for review notes/status accept the same source metadata as browser forms.

## Audit and Persistence

- Opportunity review records now preserve previous/new review state, action type, requested action, target id/name, reason, source route/component, data state, freshness, review-only, safe-review-only, live-disabled, and no-live-mutation flags.
- Operator notes JSONL rows include data state, freshness, source route, source component, and live-disabled metadata.
- Runtime review records remain local and excluded from release ZIPs.

## Safety

No autonomous execution was added. Opportunity review actions are local operator workflow state only. They do not place orders, cancel orders, approve trades, arm live trading, disable read-only mode, bypass backend gates, or provide financial advice.

