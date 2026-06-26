# AI Safety And Privacy Guide - v4.2.0-real

The AI layer is local-first, draft-only, redacted, and fail-closed by default.

## Safety Invariants

- AI cannot place orders.
- AI cannot cancel orders.
- AI cannot approve trades.
- AI cannot arm live trading.
- AI cannot disable read-only mode.
- AI cannot disable the kill switch.
- AI cannot bypass backend gates.
- AI cannot create accepted tasks without explicit human acceptance.
- AI output is not financial advice.

## Runtime Storage

AI records live under `data/ai/`:

- `data/ai/suggestions.jsonl`
- `data/ai/review_packets.jsonl`
- `data/ai/ai_audit.jsonl`

These files are runtime records and must not be included in release ZIPs.

## Redaction

The AI client redacts secret-looking keys and values before building model payloads. It also runs a secret scan before any real API call is allowed. Audit records are redacted and store prompt/response hashes instead of raw prompt or response bodies.

## Network Posture

OpenAI API calls require all of the following: API key configured, API enabled, Responses API enabled, dry-run-only disabled, operator approval supplied, data-category send permission enabled, redaction applied, and secret scan passing.



## Local LLM Provider Path

The v4.2 multi-provider AI layer supports a disabled-by-default local LLM path for Ollama, llama.cpp server, LM Studio, and generic OpenAI-compatible localhost endpoints. `qwen3:8b` is the recommended default for Mac mini M4 16GB; `qwen3:4b` and `gemma3:4b` are fast/privacy-friendly fallbacks; `gemma3:12b` is experimental on 16GB. Local LLMs still require redaction, prompt governance, human review, audit hashes, and no-live-mutation controls.
