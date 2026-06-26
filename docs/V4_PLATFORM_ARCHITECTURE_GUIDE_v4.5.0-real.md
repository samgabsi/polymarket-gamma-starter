# Platform Architecture Guide - v4.5.0-real

v4.5 preserves the v4 platform architecture and adds market-edge recommendation wiring as a deterministic helper plus review-only AI Edge endpoints.

## Components

- `app/market_edge.py` for deterministic recommendation objects, family detection, rank labels, thresholds, and explanations.
- `app/main.py` market APIs for edge legends, family rankings, and per-market recommendation summaries.
- `app/routers/ai.py` market-row AI Edge review endpoints.
- `app/ui.py` centralized navigation sections and quick actions.
- `app/navigation_registry.py` route aliases and system-map metadata.
- Templates for dashboard, market detail, opportunities, and v2 market search display.

The architecture keeps deterministic safety checks separate from AI judgment.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
