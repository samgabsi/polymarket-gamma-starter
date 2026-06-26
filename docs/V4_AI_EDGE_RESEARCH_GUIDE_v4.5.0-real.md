# AI Edge Research Guide - v4.5.0-real

AI Edge Research is a draft-only research layer inside `/v3/ai/edge`. v4.5 keeps the v4.4 evidence, citation, contradiction, missing-information, draft fair-probability, and calibration packet model and adds market-row entry points.

## UI Routes

- `/v3/ai/edge`
- `/v3/ai/edge/new`
- `/v3/ai/edge/packets`
- `/v3/ai/edge/evidence`
- `/v3/ai/edge/calibration`
- `/v3/ai/edge/settings`
- `/v3/ai/edge/market/{market_id_or_slug}`
- `/v3/ai/edge/family/{family_id}`

Aliases include `/edge`, `/edge/new`, `/edge/packets`, `/edge/evidence`, `/edge/calibration`, `/edge/settings`, `/edge/legend`, and `/edge/families`.

## Market Row APIs

- `POST /api/v3/ai/edge/market/analyze`
- `GET /api/v3/ai/edge/market/{market_id_or_slug}/summary`
- `GET /api/v3/ai/edge/market/{market_id_or_slug}/packet`
- `GET /api/v3/ai/edge/family/{family_id}/summary`

Market row analysis prefills title, slug, YES price, NO price, volume, liquidity, data freshness, family/rank context, model fair estimate, and operator notes when supplied.


## AI and Web Search Limits

OpenAI web search is disabled by default and can only be used for explicit research packet workflows when configured by the operator. Local LLMs such as Qwen through Ollama do not natively browse the web in this app; they can review app-provided evidence packets only. AI Edge packet output remains draft/review-only and does not become an accepted task, trade, order, or approval without explicit human action in the appropriate safe workflow.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
