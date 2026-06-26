# Opportunity Review Workflow Guide - v4.14.0-real

Opportunity review remains review-only. Notes, watchlist, paper-review, reject, and archive actions are local operator workflow state and never execute trades.

## Browser Workflow

1. Open `/v3/opportunities?demo=true`.
2. Confirm the data-mode selector shows either Demo fixtures or Configured local/live source.
3. Confirm the top-level data state and each row data state are visible.
4. Save operator notes or submit Add to Watchlist, Send to Paper Review, Reject, or Archive.
5. Confirm redirect feedback.
6. Open the market detail page and inspect the enriched audit history.

## API Workflow

- `GET /api/v3/opportunities?demo=true` returns workbench rows with data-state/source metadata.
- `POST /api/v3/opportunities/review/{market_id}/notes` stores local notes and audit metadata.
- `POST /api/v3/opportunities/review/{market_id}/status` stores local status decisions and audit metadata.
- `GET /api/v3/opportunities/review/{market_id}` returns the latest local review record.

## Audit Fields

Opportunity audit events include timestamp, feature area, action type, requested action, target id/name, previous state, new state, reason, source route, source component, data state, data freshness, review-only, safe-review-only, live-disabled, and no-live-mutation flags.

## Data State

- `sample`: deterministic fixtures; use for workflow validation only.
- `live`: configured read-only market data was returned; still requires freshness/rules/manual review.
- `cached`: local/runtime or cached enrichment, not a fresh external venue read.
- `stale`: stale data only.
- `unavailable`: no usable data or disabled/config-required/scaffolded source.

## Safety

Opportunity review output is not financial advice. No opportunity review action places orders, cancels orders, approves trades, arms live trading, disables read-only mode, or bypasses backend gates.

