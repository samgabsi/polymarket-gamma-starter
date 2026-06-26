# Manual Qa Checklist - v4.6.0-real

Manual QA checklist: review Opportunity Workbench, market detail, family comparison, AI Edge packet lifecycle, notes/status APIs, and live safety gates without submitting or cancelling real orders.


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

# Manual QA Checklist - v4.6.0-real

## Navigation

- Verify the sidebar renders one Unified Surface group.
- Verify aliases `/operator-os`, `/ai`, `/edge`, `/platform`, `/live`, `/workspace`, `/tasks`, `/cockpit`, and `/routes` resolve without bypassing safety gates.
- Verify System Map lists AI Edge and market recommendation surfaces.

## Market Recommendations

- Verify a YES edge row says Recommended: YES and explains model fair YES vs market YES.
- Verify a NO edge row says Recommended: NO and explains model fair NO vs market NO.
- Verify close/noisy data says HOLD or NO CLEAR EDGE.
- Verify missing fair probability says INSUFFICIENT DATA.
- Verify favorite rank is separate from recommended side.
- Verify stale, liquidity, volume, or evidence warnings are visible where available.

## AI Edge

- Verify Analyze with AI Edge opens review-only packet context.
- Verify Open Packet, Evidence, and Calibration links do not place or cancel orders.
- Verify market-family comparison is labelled as research-only.

## Safety

- Verify read-only mode blocks live submits.
- Verify kill switch blocks live submits.
- Verify paper mode avoids live endpoints.
- Verify typed live-order confirmation remains required.
- Verify task completion and guided review completion do not approve trades.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
