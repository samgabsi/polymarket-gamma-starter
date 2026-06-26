# API Contracts Guide - v4.5.0-real

v4.5 adds review-only market edge and AI Edge market-row contracts.

## Added/Updated Contracts

- `GET /api/markets/edge-legend`
- `GET /api/markets/family-rankings`
- `GET /api/markets/{market_id}/edge-recommendation`
- `POST /api/v3/ai/edge/market/analyze`
- `GET /api/v3/ai/edge/market/{market_id_or_slug}/summary`
- `GET /api/v3/ai/edge/market/{market_id_or_slug}/packet`
- `GET /api/v3/ai/edge/family/{family_id}/summary`

Responses include review-only safety flags and must not report order placement, cancellation, trade approval, or live arming.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
