# Configurable AI Odds Adjustment Guide - v4.12.0-real

AI odds adjustment remains draft, advisory, and review-only.

## Operator Workflow

1. Open `/v3/markets/demo_france_world_cup/news-odds`.
2. Review market YES price, model fair price, AI-adjusted fair price, raw adjustment, evidence-weighted adjustment, final adjustment, cap decision, confidence, and recommended side.
3. Use Plan search for a search-plan preview with feedback.
4. Use Preview manual evidence for non-persistent evidence analysis feedback.
5. Use Save draft adjustment to persist a local draft adjustment and open its detail page.
6. On the detail page, accept to review context, reject, or archive the draft.

## Caps and Clamps

The hidden 2.5 percentage-point ceiling is not an absolute ceiling. The final adjustment is controlled by configured mode caps, hard cap, weak-evidence clamps, contradiction checks, and operator confirmation thresholds. Conservative mode keeps the old 2.5 pp posture by default.

## Safety

Accepting a draft to review context does not place orders, cancel orders, approve trades, arm live trading, or bypass backend gates. Runtime records and audit rows are local and excluded from release ZIPs.
