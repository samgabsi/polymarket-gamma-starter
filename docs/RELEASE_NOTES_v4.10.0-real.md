# Release Notes - v4.10.0-real

## Route and Action Honesty Pass

v4.10.0-real continues the functional-completion work from v4.9 and closes the highest-visibility action gaps in opportunity review, market detail, AI News Odds, and cross-market arbitrage.

### Completed

- Replaced Opportunity Review Workbench status API links with POST-backed page forms for watchlist, paper-review, reject, and archive decisions.
- Added POST-backed operator-notes forms on the workbench and market detail review surfaces.
- Added page POST wrappers for AI News Odds plan, gated search preview, manual evidence, and draft adjustment generation so browser controls work without a JSON client.
- Replaced arbitrage review GET action links with POST-backed page forms.
- Hardened the compatibility GET arbitrage review endpoint so it returns method-required guidance instead of recording a review action.
- Pointed AI Edge market actions at real AI Edge market pages instead of exposing POST-only analyze APIs as normal links.
- Expanded `/api/v3/features/status` with explicit statuses for opportunity review actions, AI odds page actions, arbitrage review actions, and AI/arbitrage configuration surfacing.
- Fixed a Python 3.11 compatibility issue in strategy markdown export that blocked local focused tests.

### Safety posture

- No autonomous trading, order placement, cancellation, trade approval, live arming, signing, or backend-gate bypass was added.
- Opportunity review records, AI odds adjustments, and arbitrage review actions remain local, review-only workflow records.
- Kalshi remains disabled/config-required unless explicitly configured by the operator.

### Known limitations

- The broad historical app still contains many older compatibility pages; this pass focused on the currently surfaced v3 review/AI/arbitrage controls.
- Web search remains disabled unless all provider and operator-confirmation gates are configured.
- Arbitrage candidates are not guaranteed profits and still require manual review for fees, liquidity, timing, and resolution mismatch.
