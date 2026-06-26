# Cross-Market Arbitrage Guide - v4.10.0-real

## Purpose

The Cross-Market Arbitrage engine surfaces candidate price differences across Polymarket, Kalshi, and future venue adapters. It is review-only and never executes orders.

## Configuration

```bash
KALSHI_ENABLED=false
KALSHI_API_BASE_URL=https://external-api.kalshi.com/trade-api/v2
KALSHI_API_KEY_ID=
KALSHI_PRIVATE_KEY_PATH=

ARBITRAGE_SCANNER_ENABLED=false
ARBITRAGE_REVIEW_ONLY=true
ARBITRAGE_FETCH_ORDERBOOKS=false
ARBITRAGE_MIN_NET_MARGIN_PCT=1.0
ARBITRAGE_MIN_CONFIDENCE=0.72
ARBITRAGE_MAX_STALE_SECONDS=300
ARBITRAGE_MAX_RESOLUTION_MISMATCH_RISK=0.35
ARBITRAGE_SCAN_INTERVAL_SECONDS=300
ARBITRAGE_DEFAULT_SLIPPAGE_BPS=50
ARBITRAGE_MIN_LIQUIDITY=10
ARBITRAGE_COMPETITOR_VENUES=
```

The app starts with Kalshi disabled and no credentials. Fixture mode powers the UI when live scanning is disabled.

## Matching

Matching is deterministic-first. The engine compares titles, outcome labels, close times, resolution rules, category, and venue mapping confidence. AI semantic matching is not used as final proof of equivalence.

## Math

For binary markets the engine evaluates:

- buy YES on venue A plus buy NO on venue B
- buy NO on venue A plus buy YES on venue B

It computes gross margin, estimated fees, estimated slippage, top-of-book size, depth-adjusted size, net margin, annualized return when close time is available, worst-case loss if markets are not equivalent, and a confidence-adjusted score.

## Classification

Candidates are classified as:

- `clean_arbitrage_candidate`
- `fee_sensitive_candidate`
- `liquidity_limited_candidate`
- `resolution_mismatch_risk`
- `semantic_mismatch_risk`
- `watchlist_only`
- `reject`

## Limitations

Kalshi authenticated/private calls are scaffolded by config only and disabled by default. Unsupported venues are disabled placeholders and excluded from scans. Candidate profitability is never guaranteed.
