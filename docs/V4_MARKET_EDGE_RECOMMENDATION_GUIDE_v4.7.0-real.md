# Market Edge Recommendation Guide - v4.7.0-real

## Fair probability adjustment

The deterministic code starts from the existing base fair YES probability when available, converts it to log odds, applies bounded evidence shifts, caps total adjustment, caps per-cluster adjustment, caps low-confidence adjustments, caps no-primary-source adjustments, applies contradiction penalties, clamps probabilities, recalculates YES/NO edge, and labels the result as a draft fair odds adjustment.

If the base fair probability is unavailable, the engine reports insufficient data rather than inventing an anchored final adjusted probability.

Market-edge helper still provides YES/NO/HOLD recommendation labels. News Odds adjusts only model fair probability context and then recalculates draft edge.

## Safety boundary

This surface is research/review-only. It is not financial advice, not a profitability claim, not trade approval, and not an order instruction. It does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, bypass backend gates, or modify live trading configuration. Source weighting does not prove truth, corroboration does not prove certainty, favorite ranking does not imply edge, and calibration does not imply future performance.
