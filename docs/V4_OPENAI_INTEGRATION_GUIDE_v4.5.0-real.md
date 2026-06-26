# OpenAI Integration Guide - v4.5.0-real

OpenAI integration remains disabled by default. v4.5 can use OpenAI-configured research only when the operator explicitly enables it for draft review workflows.

## Defaults

- `OPENAI_API_ENABLE=false`
- `OPENAI_DRY_RUN_ONLY=true`
- `OPENAI_ENABLE_WEB_SEARCH=false`
- `AI_EDGE_ALLOW_WEB_SEARCH=false`

Never place real API keys in `.env.example`, docs, screenshots, exports, prompts, validation reports, or release ZIPs. Prompt payloads must not include wallet secrets, private keys, auth headers, session cookies, passwords, or local credentials.


## AI and Web Search Limits

OpenAI web search is disabled by default and can only be used for explicit research packet workflows when configured by the operator. Local LLMs such as Qwen through Ollama do not natively browse the web in this app; they can review app-provided evidence packets only. AI Edge packet output remains draft/review-only and does not become an accepted task, trade, order, or approval without explicit human action in the appropriate safe workflow.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
