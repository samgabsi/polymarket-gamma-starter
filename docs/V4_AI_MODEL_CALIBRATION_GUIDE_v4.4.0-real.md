# AI Model Calibration Guide - v4.4.0-real

AI model calibration in v4.4.0-real tracks historical AI Edge draft probability estimates after outcomes are known. It is a model-quality review aid, not a trading signal.

## What Calibration Stores

- AI Edge packet ID
- provider and model metadata
- draft probability estimate
- optional question tags and notes
- resolved outcome when entered by the operator
- Brier score and absolute error when enough data exists
- web-search-used versus no-web-search metadata
- safety flags proving no trade approval and no live mutation

## Routes

- `GET /api/v3/ai/edge/calibration`
- `GET /api/v3/ai/edge/calibration/summary`
- `POST /api/v3/ai/edge/calibration/outcome`
- `GET /api/v3/ai/edge/calibration/export.json`
- `GET /api/v3/ai/edge/calibration/export.md`
- `GET /api/v3/ai/edge/calibration/export.csv`

Calibration evaluates prior research estimates only. It does not guarantee future performance, approve trades, place or cancel orders, arm live trading, or weaken existing safety gates.

See also `docs/V4_AI_EDGE_CALIBRATION_GUIDE_v4.4.0-real.md`.
