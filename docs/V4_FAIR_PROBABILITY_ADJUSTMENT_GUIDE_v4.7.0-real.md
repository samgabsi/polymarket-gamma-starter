# Fair Probability Adjustment Guide - v4.7.0-real

## Fair probability adjustment

The deterministic code starts from the existing base fair YES probability when available, converts it to log odds, applies bounded evidence shifts, caps total adjustment, caps per-cluster adjustment, caps low-confidence adjustments, caps no-primary-source adjustments, applies contradiction penalties, clamps probabilities, recalculates YES/NO edge, and labels the result as a draft fair odds adjustment.

If the base fair probability is unavailable, the engine reports insufficient data rather than inventing an anchored final adjusted probability.

## Source weighting and corroboration

Default source-type weights are transparent and configurable: primary official source 1.00, government/regulator 0.95, wire 0.85, major news 0.80, specialist 0.70, local 0.55, blog 0.40, social 0.30, forum/rumor 0.20, and unknown 0.25. Recency, relevance, independence, specificity, contradiction penalties, duplicate/syndication penalties, and source diversity are also represented.

More sites do not automatically increase confidence. Copied or syndicated coverage is clustered and discounted. Independent high-quality corroboration carries more weight than low-quality duplicate coverage. Primary sources carry more weight when the market question depends on that primary source's domain.

## Safety boundary

This surface is research/review-only. It is not financial advice, not a profitability claim, not trade approval, and not an order instruction. It does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, bypass backend gates, or modify live trading configuration. Source weighting does not prove truth, corroboration does not prove certainty, favorite ranking does not imply edge, and calibration does not imply future performance.
