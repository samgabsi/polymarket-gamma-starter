# System Map Guide - v4.7.0-real

## Routes and workflow

Key UI routes:

- `/v3/ai/news-odds`
- `/v3/ai/news-odds/run`
- `/v3/ai/news-odds/adjustments`
- `/v3/ai/news-odds/source-weights`
- `/v3/markets/{market_id_or_slug}/news-odds`
- `/v3/markets/family/{family_id}/news-odds`

Key API routes:

- `/api/v3/ai/news-odds/config`
- `/api/v3/ai/news-odds/market/{market_id_or_slug}/plan`
- `/api/v3/ai/news-odds/market/{market_id_or_slug}/search`
- `/api/v3/ai/news-odds/market/{market_id_or_slug}/manual-evidence`
- `/api/v3/ai/news-odds/market/{market_id_or_slug}/adjust`
- `/api/v3/ai/news-odds/adjustments`
- `/api/v3/ai/news-odds/adjustment/{adjustment_id}`
- `/api/v3/ai/news-odds/adjustment/{adjustment_id}/accept-to-review-context`
- `/api/v3/ai/news-odds/adjustment/{adjustment_id}/reject`
- `/api/v3/ai/news-odds/adjustment/{adjustment_id}/archive`

The system map includes AI News Odds Adjustment Engine, search planning, source scoring, corroboration, duplicate detection, News Odds panels, Family News Odds, AI Edge integration, and safety boundaries.

## Safety boundary

This surface is research/review-only. It is not financial advice, not a profitability claim, not trade approval, and not an order instruction. It does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, bypass backend gates, or modify live trading configuration. Source weighting does not prove truth, corroboration does not prove certainty, favorite ranking does not imply edge, and calibration does not imply future performance.
