# Configurable AI Odds Adjustment Guide - v4.9.0-real

## Fields

AI News Odds packets expose:

- `raw_ai_adjustment_pct`
- `evidence_weighted_adjustment_pct`
- `final_adjustment_pct`
- `cap_decision`
- `old_2_5_cap_exceeded`
- `operator_confirmation_required`

`adjustment_pp` remains as a backward-compatible alias for the final adjustment.

## Modes

```bash
AI_ODDS_ADJUSTMENT_ENABLED=true
AI_ODDS_ADJUSTMENT_MODE=conservative
AI_DEFAULT_MAX_ADJUSTMENT_PCT=2.5
AI_BALANCED_MAX_ADJUSTMENT_PCT=7.5
AI_AGGRESSIVE_MAX_ADJUSTMENT_PCT=15.0
AI_ABSOLUTE_HARD_CAP_PCT=25.0
AI_REQUIRE_EXTRA_EVIDENCE_ABOVE_PCT=5.0
AI_REQUIRE_OPERATOR_CONFIRM_ABOVE_PCT=10.0
AI_ALLOW_CAP_EXCEED_WITH_EVIDENCE=false
```

Use `balanced` or `aggressive` only when operators want larger reviewed adjustments. Use `custom` to make the backward-compatible `AI_NEWS_ODDS_MAX_ADJUSTMENT_PP` the active cap.

## Guardrails

Large final adjustments require independent, high-quality, recent, relevant evidence. Single-source, stale, low-relevance, no-primary-source, contradictory, thin-liquidity, wide-spread, or ambiguous-resolution cases are capped or confidence-degraded.

## Interpretation

The final adjustment changes the app's internal draft fair probability only. It does not change venue prices, approve trades, place orders, cancel orders, or arm live trading.
