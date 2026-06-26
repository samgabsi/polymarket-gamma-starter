# Validation - v4.9.0-real

## Release identity

- Package: Polymarket OP Console
- Slug: polymarket-op-console
- Version: v4.9.0-real
- Release theme: Configurable AI Odds Adjustment and Cross-Market Arbitrage Review

## Implementation status

- Configurable AI odds adjustment: implemented in `app/ai_news_odds.py`.
- Cross-market arbitrage engine: implemented in `app/cross_market_arbitrage.py`.
- Polymarket adapter: uses existing Gamma/CLOB code paths and fixture mode by default.
- Kalshi adapter: public market/orderbook read scaffold implemented; disabled by default.
- Future competitors: disabled placeholder registry only.
- UI/API: `/v3/arbitrage`, `/api/v3/arbitrage/*`, and updated AI News Odds pages.
- Safety: review-only, no live mutation, no guaranteed-profit claims.

## Validation commands

Run before packaging:

```text
find app tests -name '*.py' -print0 | xargs -0 python -m py_compile
PYTHONPATH=. pytest -q tests/test_ai_news_odds_v47.py tests/test_cross_market_arbitrage_v48.py
```

Full-suite validation is recommended after focused tests pass.
