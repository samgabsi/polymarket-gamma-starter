# AI Prompt Governance Guide - v4.3.0-real

Prompt governance is implemented in `app/ai_prompt_governance.py`.

## Required Rules

- Redaction is required before send.
- Human approval is required before any real API call.
- Prompt templates must include the AI safety statement.
- Prompt audit records store hashes, not raw prompts.
- Prompt outputs must use structured draft schemas.
- Prompts must preserve blockers, warnings, stale data, unknown data, unavailable data, and limitations.

## Prohibited Data

Do not send private keys, API keys, wallet secrets, auth headers, session cookies, passwords, raw database files, raw runtime files, sensitive account data, or unredacted operator secrets to OpenAI or any model provider.

## Prompt Categories

The registry includes daily review, weekly review, task suggestion, source preview, dataset readiness, freshness, simulation, analytics, governance, platform diagnostics, migration plan, validation failure, release notes, operator manual, API schema, and ChatGPT connector tool description prompts.

## Structured Outputs

Each prompt is mapped to a schema in `app/ai_schemas.py`. Required fields include `no_financial_advice=true`, `no_trade_approval=true`, and `no_live_mutation=true`.



## Local LLM Provider Path

The v4.3 multi-provider AI layer supports a disabled-by-default local LLM path for Ollama, llama.cpp server, LM Studio, and generic OpenAI-compatible localhost endpoints. `qwen3:8b` is the recommended default for Mac mini M4 16GB; `qwen3:4b` and `gemma3:4b` are fast/privacy-friendly fallbacks; `gemma3:12b` is experimental on 16GB. Local LLMs still require redaction, prompt governance, human review, audit hashes, and no-live-mutation controls.
