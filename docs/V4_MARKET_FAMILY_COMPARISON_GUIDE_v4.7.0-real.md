# Market Family Comparison Guide - v4.7.0-real

## v4.7 AI News Odds Adjustment Engine

v4.7.0-real adds an AI-assisted, evidence-weighted fair probability workflow:

Market -> search plan -> web/news evidence or manual evidence -> source credibility scoring -> duplicate/syndication detection -> independent corroboration scoring -> event extraction -> bounded fair-probability adjustment -> before/after YES/NO edge -> AI Edge packet -> operator review.

“Adjust odds” means adjusting the app's internal draft model fair probability / fair odds for review. It never means changing Polymarket market prices, manipulating market prices, automatically placing or canceling orders, arming live trading, or approving trades.

OpenAI web search is disabled by default unless explicitly configured. Manual evidence mode is available by default. Local LLM review does not browse the web by itself; it can only analyze evidence supplied by the app/operator.

Family news odds routes support event-level and outcome-level analysis. Family normalization is not applied unless a family is clearly complete and mutually exhaustive. Favorite still does not equal edge.

## Safety boundary

This surface is research/review-only. It is not financial advice, not a profitability claim, not trade approval, and not an order instruction. It does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, bypass backend gates, or modify live trading configuration. Source weighting does not prove truth, corroboration does not prove certainty, favorite ranking does not imply edge, and calibration does not imply future performance.
