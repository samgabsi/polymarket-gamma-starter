# AI Edge Research Guide - v4.4.0-real

AI Edge Research is a draft-only research layer inside `/v3/ai/edge`. It builds evidence-backed packets from app-provided evidence, source metadata, citations, contradiction tracking, missing-information lists, draft fair-probability estimates, and calibration records.

## Safe Defaults

- `AI_EDGE_ENABLE=false`
- `AI_EDGE_PROVIDER=mock`
- `AI_EDGE_DRY_RUN_ONLY=true`
- `AI_EDGE_REQUIRE_OPERATOR_APPROVAL=true`
- `AI_EDGE_ALLOW_WEB_SEARCH=false`
- `OPENAI_ENABLE_WEB_SEARCH=false`
- `LOCAL_LLM_EDGE_CAN_SEARCH_WEB=false`
- `AI_EDGE_ALLOW_MARKET_IMPLIED_COMPARISON=false`

AI Edge output is not financial advice, not trade approval, and cannot place orders, cancel orders, arm live trading, or disable safety gates.

## UI Routes

- `/v3/ai/edge`
- `/v3/ai/edge/new`
- `/v3/ai/edge/packets`
- `/v3/ai/edge/evidence`
- `/v3/ai/edge/calibration`
- `/v3/ai/edge/settings`

Aliases are navigation-only: `/edge`, `/edge/new`, `/edge/packets`, `/edge/evidence`, `/edge/calibration`, and `/edge/settings`.

## API Routes

- `GET /api/v3/ai/edge/summary`
- `GET|POST /api/v3/ai/edge/settings`
- `GET /api/v3/ai/edge/schemas`
- `GET|POST /api/v3/ai/edge/packets`
- `POST /api/v3/ai/edge/research/dry-run`
- `POST /api/v3/ai/edge/openai-web-dry-run`
- `GET|POST /api/v3/ai/edge/evidence`
- `GET|POST /api/v3/ai/edge/calibration`
- `GET /api/v3/ai/edge/export.json`
- `GET /api/v3/ai/edge/export.md`
- `GET /api/v3/ai/edge/export.csv`

## Packet Contents

Each packet includes:

- evidence sources with citation labels and source metadata
- evidence-backed findings linked to citation labels
- contradictions and mixed evidence
- missing information and stale/unknown source metadata
- draft probability and fair-probability fields
- optional market-implied comparison only when explicitly enabled
- local LLM review metadata proving no web-search claim
- OpenAI web-search dry-run request plan when requested
- calibration tracking metadata
- prompt and response hashes only; raw prompts/responses are not stored

Runtime records are written under `data/ai/edge/` only after explicit operator-triggered actions and are excluded from release ZIPs.
