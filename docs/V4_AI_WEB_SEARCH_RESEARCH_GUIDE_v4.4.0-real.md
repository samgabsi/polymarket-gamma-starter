# AI Web Search Research Guide - v4.4.0-real

AI web-search research in v4.4.0-real is a gated review-packet workflow for AI Edge Research. It is disabled by default and dry-run-only by default.

## Default Posture

- `AI_EDGE_ENABLE=false`
- `AI_EDGE_ALLOW_WEB_SEARCH=false`
- `OPENAI_ENABLE_WEB_SEARCH=false`
- `AI_EDGE_DRY_RUN_ONLY=true`
- `OPENAI_WEB_SEARCH_REQUIRE_OPERATOR_CONFIRMATION=true`
- `OPENAI_WEB_SEARCH_REQUIRE_CITATIONS=true`
- `OPENAI_WEB_SEARCH_ALLOW_PRIVATE_DATA=false`

The packaged dry-run path builds a request plan and blocker list without making network calls, calling OpenAI, sending private data, placing orders, canceling orders, approving trades, or arming live trading.

## Dry-Run Route

`POST /api/v3/ai/edge/openai-web-dry-run`

The response includes planned queries, source limits, citation requirements, closed-gate blockers, and a draft AI Edge packet marked `external_network_called=false` and `openai_api_called=false`.

## Source Expectations

When live web search is explicitly enabled outside safe defaults, operator review must still require citations or source metadata, recency notes, source limitations, contradictions, missing information, and assumptions. Web-search results remain research evidence only and are never executable order instructions.

See also `docs/V4_OPENAI_WEB_SEARCH_EDGE_GUIDE_v4.4.0-real.md`.
