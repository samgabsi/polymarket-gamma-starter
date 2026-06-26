# V4 Market Edge Recommendation Guide - v4.6.0-real

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

# Market Edge Recommendation Guide - v4.6.0-real

The market edge layer turns market rows into explicit draft recommendation objects. It is deterministic and lives in `app/market_edge.py`.

## Recommendation Fields

Each enriched market row can include:

- `recommended_side`: YES, NO, HOLD, NO CLEAR EDGE, NEEDS REVIEW, or INSUFFICIENT DATA
- `side_badge`: DRAFT YES EDGE, DRAFT NO EDGE, HOLD, NO CLEAR EDGE, NEEDS REVIEW, or INSUFFICIENT DATA
- `market_yes_price` and `market_no_price`
- `model_fair_yes` and `model_fair_no`
- `yes_edge_pp` and `no_edge_pp`
- `edge_threshold_yes_pp` and `edge_threshold_no_pp`
- `confidence_label`
- `model_fair_source_label`
- `data_quality_warnings`
- `explanation`
- `review_only_safety_note`


## Calculation Model

`market_yes_price` is the current YES price or implied YES probability when available. `market_no_price` is the current NO price or implied NO probability when available. `model_fair_yes` is the current fair YES probability estimate and `model_fair_no` defaults to `1 - model_fair_yes` unless a more explicit model output exists.

- `yes_edge_pp = (model_fair_yes - market_yes_price) * 100`
- `no_edge_pp = (model_fair_no - market_no_price) * 100`

A YES recommendation is shown only when YES edge meets the configured threshold and is larger than the NO edge. A NO recommendation is shown only when NO edge meets the configured threshold and is larger than the YES edge. HOLD or NO CLEAR EDGE is shown when neither side clears the threshold. INSUFFICIENT DATA is shown when prices or model fair probability are unavailable. NEEDS REVIEW is shown when data is inconsistent or quality gates fail.

If YES plus NO prices do not sum close to 1.0, the UI keeps an overround/spread note visible. If only simple outcome prices are available, calculations are labelled approximate and do not imply fee/slippage modeling.


## v4.5 Edge Settings

Safe defaults are exposed through environment variables and documented in `.env.example`:

- `EDGE_MIN_YES_PP=2.0`
- `EDGE_MIN_NO_PP=2.0`
- `EDGE_MIN_LIQUIDITY=`
- `EDGE_MIN_VOLUME_24H=`
- `EDGE_REQUIRE_FRESH_DATA=true`
- `EDGE_MAX_DATA_AGE_MINUTES=`
- `EDGE_SHOW_FAVORITE_RANK=true`
- `EDGE_SHOW_FAMILY_GROUPS=true`
- `EDGE_SHOW_AI_EDGE_ACTIONS=true`
- `EDGE_DEFAULT_RECOMMENDATION_MODE=review_only`

These values tune display and review thresholds only. They do not approve trades or create executable orders.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
