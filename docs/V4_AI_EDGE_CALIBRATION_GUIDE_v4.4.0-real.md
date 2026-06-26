# AI Edge Calibration Guide - v4.4.0-real

AI Edge calibration tracks draft probability estimates against resolved outcomes. It is research-only and does not approve trades or generate orders.

## Records

Packet generation creates a pending calibration record when `AI_EDGE_ALLOW_CALIBRATION_TRACKING=true`. Outcome recording uses:

`POST /api/v3/ai/edge/calibration/outcome`

The record stores:

- packet ID
- provider
- draft probability
- resolved outcome
- Brier score
- operator notes
- safety flags proving no live mutation

## Exports

- `GET /api/v3/ai/edge/calibration/summary`
- `GET /api/v3/ai/edge/calibration/export.json`
- `GET /api/v3/ai/edge/calibration/export.md`
- `GET /api/v3/ai/edge/calibration/export.csv`

Calibration is for model-quality review only. It is not a trading signal and not financial advice.
