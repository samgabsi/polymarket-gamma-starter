# Stub Burn-down Map - v4.15.0-real

v4.15.0-real continues the stub burn-down path by completing the v3 Settings / Feature Readiness workflow and preserving the Review Queue and Feature Readiness acknowledgement workflows.

## Working in this slice

- `settings.v3_operator_preferences` — `/v3/settings` and `/api/v3/settings` expose grouped UI-safe preference rows, validation, local persistence, source/restart metadata, masked secrets, and review-only/live-disabled fields.
- `review.queue_actions` — `/review-queue`, `/api/review-queue`, `/api/review-queue/actions`, and `POST /api/review-queue/{market_id}/action` persist local review decisions and audit metadata.
- `features.readiness_review_page` — `/v3/feature-readiness` and `/api/v3/features/readiness*` expose feature-status/stub rows and local acknowledgement records.

## Still partial / config-required / scaffolded

- Kalshi adapter remains disabled/config-required/scaffolded unless explicitly configured.
- Arbitrage remains review-only; opportunities are candidates with fees/slippage/liquidity/mismatch risk, not guaranteed profits.
- Live execution/trading controls remain disabled/gated and must not be presented as ready for uncontrolled execution.
- True `.env` editing remains outside the browser settings workflow; v3 settings preferences are local operator preferences only.

## Operator implication

The feature-status registry and stub burn-down map should be treated as the source of UI truthfulness. A surface marked partial, config-required, scaffolded, disabled, unavailable, or error must not be displayed as a fully working/live feature.
