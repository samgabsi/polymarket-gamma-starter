# Visual Qa Checklist - v4.6.0-real

Visual QA checklist: verify one Unified Surface sidebar heading, mobile menu distinct headings, readable workbench table, detail cards, family comparison table, badges, notices, empty states, and responsive overflow.


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

# Visual QA Checklist - v4.6.0-real

## Routes to Dry Run

- `/`
- `/v3`
- `/v2-live`
- `/v3/ai`
- `/v3/ai/edge`
- `/v3/ai/edge/new`
- `/v3/ai/edge/packets`
- `/v3/ai/edge/evidence`
- `/v3/ai/edge/calibration`
- `/v3/platform`
- `/v3/cockpit`
- `/v3/workspace`
- `/v3/tasks`
- `/system-map`
- `/routes`
- `/ai`
- `/edge`
- `/platform`
- `/cockpit`
- `/workspace`
- `/tasks`
- `/live`
- `/operator-os`
- `/opportunities`
- `/markets/example`
- `/v3/ai/edge/market/example`
- `/v3/ai/edge/family/example`

## Checks

- Only one desktop Unified Surface group appears.
- Mobile navigation headings are distinct from desktop headings.
- Market rows show Recommended Side and Why columns.
- YES, NO, HOLD, NO CLEAR EDGE, NEEDS REVIEW, and INSUFFICIENT DATA badges are legible.
- Favorite/rank labels are visually separate from edge labels.
- AI Edge row actions are visible but clearly review-only.
- No screenshots with secrets are included in the release ZIP unless explicitly safe and intended.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
