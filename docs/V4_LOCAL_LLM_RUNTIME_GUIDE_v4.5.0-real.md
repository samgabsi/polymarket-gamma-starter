# Local LLM Runtime Guide - v4.5.0-real

Local LLM runtime support remains disabled by default and review-only. A local model such as Qwen through Ollama can review app-provided evidence packets, but this app does not give it native web browsing. Web search requires an enabled web-search-capable provider or manual evidence input.

## Defaults

- `LOCAL_LLM_ENABLE=false`
- `LOCAL_LLM_DRY_RUN_ONLY=true`
- `LOCAL_LLM_EDGE_CAN_SEARCH_WEB=false`
- `AI_EDGE_DRY_RUN_ONLY=true`


## AI and Web Search Limits

OpenAI web search is disabled by default and can only be used for explicit research packet workflows when configured by the operator. Local LLMs such as Qwen through Ollama do not natively browse the web in this app; they can review app-provided evidence packets only. AI Edge packet output remains draft/review-only and does not become an accepted task, trade, order, or approval without explicit human action in the appropriate safe workflow.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
