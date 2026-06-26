# OpenAI Web Search Edge Guide - v4.4.0-real

OpenAI web search for AI Edge Research is blocked by default. The packaged app builds dry-run review packets and request plans, but it does not call OpenAI web search unless every explicit gate is changed outside the release defaults.

## Required Gates

- `AI_EDGE_ENABLE=true`
- `AI_EDGE_ALLOW_WEB_SEARCH=true`
- `OPENAI_ENABLE_WEB_SEARCH=true`
- `AI_EDGE_DRY_RUN_ONLY=false`
- `OPENAI_DRY_RUN_ONLY=false`
- `OPENAI_WEB_SEARCH_REQUIRE_OPERATOR_CONFIRMATION=true` with an explicit operator confirmation payload
- citations required by `OPENAI_WEB_SEARCH_REQUIRE_CITATIONS=true`
- recency requirements preserved by `OPENAI_WEB_SEARCH_RECENCY_REQUIRED=true`

`OPENAI_WEB_SEARCH_ALLOW_PRIVATE_DATA=false` remains the default. Private keys, API keys, auth headers, wallet data, and raw runtime/private data must not be sent.

## Dry-Run Route

`POST /api/v3/ai/edge/openai-web-dry-run` returns:

- planned queries
- source and citation limits
- blockers explaining which gates remain closed
- `external_network_called=false`
- `openai_api_called=false`

The dry-run packet is useful for operator review because it proves what would be requested without making a network call.
