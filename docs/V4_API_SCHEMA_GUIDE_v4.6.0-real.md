# V4 Api Schema Guide - v4.6.0-real

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

# API Schema Guide - v4.6.0-real

API schema inventory is generated under `docs/generated/`. v4.5 schema review should include market recommendation objects, model fair source labels, favorite-vs-edge metadata, and AI Edge no-live-mutation flags.

# API Contracts Guide - v4.6.0-real

v4.5 adds review-only market edge and AI Edge market-row contracts.

## Added/Updated Contracts

- `GET /api/markets/edge-legend`
- `GET /api/markets/family-rankings`
- `GET /api/markets/{market_id}/edge-recommendation`
- `POST /api/v3/ai/edge/market/analyze`
- `GET /api/v3/ai/edge/market/{market_id_or_slug}/summary`
- `GET /api/v3/ai/edge/market/{market_id_or_slug}/packet`
- `GET /api/v3/ai/edge/family/{family_id}/summary`

Responses include review-only safety flags and must not report order placement, cancellation, trade approval, or live arming.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
