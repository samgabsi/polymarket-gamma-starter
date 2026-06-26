# OpenAI Web Search Edge Guide - v4.5.0-real

OpenAI web search can only support AI Edge research packets when explicitly enabled by the operator. It is disabled in packaged defaults. Web-search results must be treated as evidence context, not as trade approval or objective pricing truth.

# AI Web Search Research Guide - v4.5.0-real

OpenAI web search remains an optional research-packet input, not an execution signal. Packaged defaults disable web search and require explicit operator configuration.

## Defaults

- `AI_EDGE_ALLOW_WEB_SEARCH=false`
- `OPENAI_ENABLE_WEB_SEARCH=false`
- `OPENAI_API_ENABLE=false`
- `OPENAI_DRY_RUN_ONLY=true`
- `AI_EDGE_DRY_RUN_ONLY=true`
- `AI_EDGE_REQUIRE_OPERATOR_APPROVAL=true`

When enabled by the operator, web search may support source discovery, source quality notes, recency checks, contradiction tracking, and missing-information lists. It does not place orders, approve trades, disable safety gates, or make model fair probabilities objective truth.


## AI and Web Search Limits

OpenAI web search is disabled by default and can only be used for explicit research packet workflows when configured by the operator. Local LLMs such as Qwen through Ollama do not natively browse the web in this app; they can review app-provided evidence packets only. AI Edge packet output remains draft/review-only and does not become an accepted task, trade, order, or approval without explicit human action in the appropriate safe workflow.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
