# Release Notes - v4.6.0-real

Release notes for v4.6.0-real. Changed files include new opportunity-review helpers, new templates, AI Edge packet lifecycle wiring, route/API additions, docs, tests, and validation/package scripts.


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

# Release Notes - v4.6.0-real

Polymarket OP Console v4.6.0-real is a UI/UX polish and wiring-completion release focused on market recommendation clarity. It fixes duplicate Unified Surface navigation, makes market rows say exactly whether the draft recommendation is YES, NO, HOLD, NO CLEAR EDGE, NEEDS REVIEW, or INSUFFICIENT DATA, separates favorite ranking from wager edge, and connects rows to AI Edge review packets.

## Highlights

- Unified sidebar renders one clean Unified Surface group.
- Market rows now show Recommended Side and a plain-English reason.
- YES and NO edge are shown in percentage points against the model fair probability.
- Model fair probability source is labelled instead of implied.
- Market-family ranking is detected conservatively for mutually exclusive outcomes such as World Cup winner markets.
- AI Edge actions are wired from rows and remain draft/review-only.
- System map, route aliases, screenshot dry-run routes, validation, README, docs, and checklists are updated for v4.5.


## Calculation Model

`market_yes_price` is the current YES price or implied YES probability when available. `market_no_price` is the current NO price or implied NO probability when available. `model_fair_yes` is the current fair YES probability estimate and `model_fair_no` defaults to `1 - model_fair_yes` unless a more explicit model output exists.

- `yes_edge_pp = (model_fair_yes - market_yes_price) * 100`
- `no_edge_pp = (model_fair_no - market_no_price) * 100`

A YES recommendation is shown only when YES edge meets the configured threshold and is larger than the NO edge. A NO recommendation is shown only when NO edge meets the configured threshold and is larger than the YES edge. HOLD or NO CLEAR EDGE is shown when neither side clears the threshold. INSUFFICIENT DATA is shown when prices or model fair probability are unavailable. NEEDS REVIEW is shown when data is inconsistent or quality gates fail.

If YES plus NO prices do not sum close to 1.0, the UI keeps an overround/spread note visible. If only simple outcome prices are available, calculations are labelled approximate and do not imply fee/slippage modeling.


## Favorite vs Edge

Favorite means the highest-probability outcome in a detected group, such as a World Cup winner family. Edge means a possible model/price mismatch versus the current market YES or NO price. A favorite can have no edge if the price is already too high. A long shot can have edge if the price is too low. Group rank never means a trade is approved.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
