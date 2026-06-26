# Local LLM Edge Review Guide - v4.4.0-real

Local LLM edge review is designed for app-provided evidence only. It is disabled by default and cannot claim web-search capability.

## Defaults

- `LOCAL_LLM_ENABLE_EDGE_REVIEW=false`
- `LOCAL_LLM_EDGE_REQUIRES_APP_EVIDENCE=true`
- `LOCAL_LLM_EDGE_CAN_SEARCH_WEB=false`
- `LOCAL_LLM_EDGE_MODEL=qwen3:8b`
- `LOCAL_LLM_EDGE_MAX_INPUT_CHARS=8000`
- `LOCAL_LLM_EDGE_TIMEOUT_SECONDS=90`

The packaged dry-run path returns a review boundary object with `local_llm_claimed_web_search=false`, `external_network_called=false`, and `ai_model_called=false`.

## Evidence Boundary

Local LLM edge review should only receive normalized evidence sources from `/api/v3/ai/edge/evidence/normalize` or an edge packet generation request. The model must not be asked to browse, fetch, or infer facts outside the supplied evidence.
