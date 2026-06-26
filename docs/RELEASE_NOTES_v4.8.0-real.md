# Release Notes - v4.9.0-real

## Configurable AI odds adjustment

v4.9 replaces the old hidden 2.5 percentage-point ceiling with a transparent three-stage adjustment model:

- `raw_ai_adjustment_pct`: model/evidence movement before risk controls.
- `evidence_weighted_adjustment_pct`: source quality, recency, relevance, agreement, and contradiction weighted movement.
- `final_adjustment_pct`: risk-controlled value used for edge and wager-review suggestions.

Conservative mode defaults to 2.5 pp. Balanced and aggressive modes can exceed 2.5 pp when evidence supports it. Every mode remains bounded by `AI_ABSOLUTE_HARD_CAP_PCT`, weak-evidence clamps, contradiction clamps, liquidity/spread/resolution warnings, and operator-confirmation thresholds.

## Cross-market arbitrage review

v4.9 adds a review-only Cross-Market Arbitrage surface at `/v3/arbitrage`.

The engine normalizes Polymarket and Kalshi-style binary markets into one schema, generates deterministic candidate matches, scores equivalence, flags resolution/semantic mismatch risk, computes buy-YES/buy-NO cross-venue combinations, subtracts estimated fees and slippage, constrains executable size by liquidity, and classifies candidates.

Candidates are not guaranteed profits. They are review artifacts only and do not submit orders.

## Venue adapter status

- Polymarket: adapter uses existing Gamma/CLOB code paths. Live scans are disabled unless `ARBITRAGE_SCANNER_ENABLED=true`; fixture mode is used by default.
- Kalshi: adapter supports public market/orderbook discovery when explicitly enabled. Authenticated private calls are not used by default and require operator-provided config.
- Future competitors: registry supports disabled placeholder adapters only; unsupported venues are clearly marked as not live.

## Official docs inspected

- Polymarket docs: Gamma/Data/CLOB read endpoints are public; CLOB order placement remains authenticated; CLOB orderbook, price, midpoint, spread, and WebSocket docs were reviewed.
- Kalshi docs: public market-data quickstart, orderbook bid/implied-ask semantics, API environments, authentication headers, WebSocket authentication, and token-bucket rate limits were reviewed.

## Safety boundary

No autonomous trading, blind execution, order placement, cancellation, live arming, or risk-control bypass was added. All arbitrage actions are review/audit records and require manual operator review.
