# Release Notes - v4.7.0-real

## v4.7 AI News Odds Adjustment Engine

v4.7.0-real adds an AI-assisted, evidence-weighted fair probability workflow:

Market -> search plan -> web/news evidence or manual evidence -> source credibility scoring -> duplicate/syndication detection -> independent corroboration scoring -> event extraction -> bounded fair-probability adjustment -> before/after YES/NO edge -> AI Edge packet -> operator review.

“Adjust odds” means adjusting the app's internal draft model fair probability / fair odds for review. It never means changing Polymarket market prices, manipulating market prices, automatically placing or canceling orders, arming live trading, or approving trades.

OpenAI web search is disabled by default unless explicitly configured. Manual evidence mode is available by default. Local LLM review does not browse the web by itself; it can only analyze evidence supplied by the app/operator.

## Source weighting and corroboration

Default source-type weights are transparent and configurable: primary official source 1.00, government/regulator 0.95, wire 0.85, major news 0.80, specialist 0.70, local 0.55, blog 0.40, social 0.30, forum/rumor 0.20, and unknown 0.25. Recency, relevance, independence, specificity, contradiction penalties, duplicate/syndication penalties, and source diversity are also represented.

More sites do not automatically increase confidence. Copied or syndicated coverage is clustered and discounted. Independent high-quality corroboration carries more weight than low-quality duplicate coverage. Primary sources carry more weight when the market question depends on that primary source's domain.

## Fair probability adjustment

The deterministic code starts from the existing base fair YES probability when available, converts it to log odds, applies bounded evidence shifts, caps total adjustment, caps per-cluster adjustment, caps low-confidence adjustments, caps no-primary-source adjustments, applies contradiction penalties, clamps probabilities, recalculates YES/NO edge, and labels the result as a draft fair odds adjustment.

If the base fair probability is unavailable, the engine reports insufficient data rather than inventing an anchored final adjusted probability.

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

## Safety boundary

This surface is research/review-only. It is not financial advice, not a profitability claim, not trade approval, and not an order instruction. It does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, bypass backend gates, or modify live trading configuration. Source weighting does not prove truth, corroboration does not prove certainty, favorite ranking does not imply edge, and calibration does not imply future performance.
