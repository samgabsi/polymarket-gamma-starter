# V3 Operator Intelligence Os Guide - v4.6.0-real

This guide is updated for v4.6.0-real and preserves the v4.5 safety boundaries while adding opportunity-review workflow context.


## v4.6 Scope

v4.6.0-real adds the Opportunity Review Workbench, Market Detail / Opportunity Review pages, Market Family Comparison pages, AI Edge Packet Lifecycle summaries, operator notes/review records, safe watchlist and paper-review queue states, visual QA hardening, route smoke hardening, and no-live-mutation validation.

## Review-Only Boundary

All opportunity review records, operator notes, watchlist states, paper-review queue states, market-edge recommendations, AI Edge packets, calibration summaries, and evidence reviews are research/review-only. They do not approve trades, place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or bypass backend gates.

## Key Routes

- `/v3/opportunities` and `/opportunities` — Opportunity Review Workbench.
- `/v3/markets/{market_id_or_slug}` and `/market/{market_id_or_slug}` — Market Detail / Opportunity Review.
- `/v3/markets/family/{family_id}` — Market Family Comparison.
- `/v3/ai/edge/packets` — AI Edge packet list and lifecycle context.
- `/api/v3/opportunities/reviews` — review record list.
- `/api/v3/opportunities/review/{market_id_or_slug}/notes` — operator notes update API.
- `/api/v3/opportunities/review/{market_id_or_slug}/status` — review status update API.

## Favorite vs Edge

Favorite means most likely outcome in a detected market family. Edge means possible model-fair versus market-implied price mismatch. A favorite can have no edge, and an underdog can have draft edge. This distinction is displayed in the workbench, detail pages, and family comparison pages.

## Safety Confirmations

- No real order placement.
- No real order cancellation.
- No AI trade approval.
- No automatic live trading arming.
- No hidden autonomous trading.
- No release ZIP runtime ledgers, credentials, AI responses, operator notes, review records, watchlists, paper-review queues, screenshots with secrets, local logs, `.env`, venvs, or node modules.

## Preserved Prior Guidance

# V3 OPERATOR INTELLIGENCE OS GUIDE v4.6.0-real

This v4.6.0-real reference preserves the v3 feature behavior while adding platform stabilization, plugin manifest boundaries, diagnostics, storage compatibility notes, centralized safety helpers, and validation hardening. Existing live/paper/task/workspace/cockpit safety gates remain intact.

The OS now includes a Freshness Scheduler layer for local-first, read-only collection planning and dataset readiness. It improves the command center without weakening live trading gates.


## v3.7 Task Planner Addendum

The v3.7 release adds a local-first Operator Task Planner, task inbox, task board, daily ops checklist, weekly planning packet, review cadence manager, task templates, and task exports. These features are human-in-the-loop workflow records only. They do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, or provide financial advice.

## v4.5 Note

This guide remains compatible with v4.6.0-real. The new market-edge recommendation layer and AI Edge row wiring are review-only and do not alter the safety guarantees described above.
