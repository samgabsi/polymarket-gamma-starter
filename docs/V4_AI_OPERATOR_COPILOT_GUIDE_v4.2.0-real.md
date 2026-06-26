# AI Operator Copilot Guide - v4.2.0-real

The The multi-provider AI Operator Copilot helps with review, summarization, explanation, classification, and drafting. It does not trade.

## UI And API

- UI: `/v3/ai`, `/v3/ai/copilot`, `/v3/ai/suggestions`, `/v3/ai/prompts`, `/v3/ai/audit`, `/v3/ai/settings`, `/v3/ai/chatgpt-connector`, `/v3/ai/review-packets`
- API: `/api/v3/ai/summary`, `/api/v3/ai/prompts`, `/api/v3/ai/schemas`, `/api/v3/ai/suggestions`, `/api/v3/ai/copilot/dry-run`, `/api/v3/ai/copilot/review`

## Workflows

Copilot workflows cover daily review, weekly review, source previews, dataset readiness, freshness, simulation reports, analytics warnings, governance items, platform diagnostics, API schema explanation, validation failure explanation, release-note drafting, operator-manual drafting, and runtime migration plan explanation.

Every workflow returns a structured draft with warnings, blockers, unknown/unavailable data, limitations, human next actions, and a safety statement.

## Task Suggestions

AI task suggestions are created with `human_status=draft`. They do not become tasks until a human explicitly accepts them through the suggestion acceptance path. Accepted suggestions create local task planner records only; they do not approve trades, place orders, cancel orders, arm live trading, or change live configuration.

## Review Packets

Review packets are local drafts for operator review. They are useful for daily/weekly summaries and release checks, but they are never evidence of execution readiness or trading approval.



## Local LLM Provider Path

The v4.2 multi-provider AI layer supports a disabled-by-default local LLM path for Ollama, llama.cpp server, LM Studio, and generic OpenAI-compatible localhost endpoints. `qwen3:8b` is the recommended default for Mac mini M4 16GB; `qwen3:4b` and `gemma3:4b` are fast/privacy-friendly fallbacks; `gemma3:12b` is experimental on 16GB. Local LLMs still require redaction, prompt governance, human review, audit hashes, and no-live-mutation controls.
