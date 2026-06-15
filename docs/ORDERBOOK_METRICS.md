# Order-Book Metrics

Version: v0.9.0-real

The order-book parser accepts normalized local JSON with bid and ask levels. A level can be a two-item array such as `["0.49", "100"]` or an object with `price` and `size` fields.

Example:

```json
{
  "market_id": "demo-market",
  "token_id": "demo-yes",
  "active": true,
  "closed": false,
  "accepting_orders": true,
  "bids": [["0.49", "100"], ["0.48", "150"]],
  "asks": [["0.51", "80"], ["0.52", "120"]]
}
```

## Computed Metrics

- best bid,
- best ask,
- midpoint,
- absolute spread,
- spread bps,
- top bid/ask size,
- depth within 1% and 5% of midpoint,
- total bid/ask depth,
- market/book status,
- warnings and blockers.

The implementation uses Python `Decimal` for price, size, notional, midpoint, spread, depth, and fill calculations before converting response fields to rounded JSON numbers.

## Statuses

Common snapshot statuses:

- `liquid`
- `thin`
- `wide_spread`
- `closed`
- `not_accepting_orders`
- `invalid_book`

Statuses are local quality signals. They are not exchange guarantees and do not imply fill availability.

## Thresholds

Configure thresholds in `.env`:

- `POLYMARKET_MARKET_DATA_MAX_AGE_SECONDS`
- `POLYMARKET_MARKET_DATA_MAX_SPREAD_BPS`
- `POLYMARKET_MARKET_DATA_MIN_TOP_DEPTH`
- `POLYMARKET_MARKET_DATA_MIN_TOTAL_DEPTH`

Release defaults are conservative and public fetch remains off by default.
