# OpenAI Integration Guide - v4.4.0-real

Polymarket OP Console v4.4.0-real adds Multi-provider AI Copilot support as a draft-only review layer. It is disabled and dry-run-only by default.

## Safe Defaults

- `OPENAI_ENABLE_API=false`
- `OPENAI_ENABLE_RESPONSES_API=false`
- `OPENAI_DRY_RUN_ONLY=true`
- `OPENAI_REDACT_BEFORE_SEND=true`
- `OPENAI_REQUIRE_OPERATOR_APPROVAL=true`
- `OPENAI_ENABLE_TOOL_CALLING=false`
- `OPENAI_ENABLE_REMOTE_MCP=false`
- `CHATGPT_MCP_SERVER_ENABLED=false`

No runtime data, market data, task data, docs, diagnostics, or migration reports are sent unless the corresponding `OPENAI_ALLOW_SENDING_*` flag is explicitly enabled. `.env.example` leaves `OPENAI_API_KEY` blank.

## Runtime Modules

- `app/ai_providers.py` selects mock, OpenAI, Ollama, llama.cpp, LM Studio, or generic local OpenAI-compatible providers behind one draft-only boundary.
- `app/ai_openai_client.py` builds Responses API payloads, redacts inputs, validates send permissions, returns deterministic dry-run outputs, and writes redacted hash-only audit records.
- `app/ai_local_llm_client.py` supports localhost OpenAI-compatible local endpoints with dry-run-first health checks.
- `app/ai_model_recommendations.py` surfaces Mac mini M4 16GB model guidance for qwen3 and Gemma-family local models.
- `app/ai_operator_copilot.py` defines review workflows and structured-output schema routing.
- `app/ai_prompt_governance.py` defines governed prompt templates with redaction and human approval requirements.
- `app/ai_schemas.py` defines structured draft output schemas.
- `app/ai_suggestions.py` stores AI suggestion drafts and review packets under `data/ai/`.

## Operator Boundary

AI output is not financial advice, trade approval, order intent, execution readiness, or live-trading authorization. Existing backend gates, typed confirmation, warning acknowledgement, approval checkbox, read-only state, kill switch, risk checks, and audit logging remain authoritative.

## Audit Records

AI audit records store prompt hashes, response hashes, workflow IDs, redacted metadata, mode, and blockers. Raw prompts, raw model responses, OpenAI API keys, wallet secrets, auth headers, and private account data are not stored by default.



## Local Provider Boundary

OpenAI is the cloud provider path. Local LLMs are the privacy/offline provider path. Mock/dry-run remains the default validation path. Local endpoints are not treated as automatically safe; they still require redaction, prompt governance, human approval, audit hashes, and no-live-mutation checks.
