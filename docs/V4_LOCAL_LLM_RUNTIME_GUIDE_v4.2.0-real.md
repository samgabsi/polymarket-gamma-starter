# Local LLM Runtime Guide - v4.2.0-real

Polymarket OP Console v4.2.0-real adds a local LLM provider path for privacy-first operator review drafts. Local LLMs are **disabled by default**, **localhost-required by default**, **dry-run-only by default**, and governed by the same no-live-mutation rules as OpenAI.

## Supported local runtime targets

- Ollama OpenAI-compatible endpoint: `http://127.0.0.1:11434/v1`
- llama.cpp server OpenAI-compatible endpoint: `http://127.0.0.1:8080/v1`
- LM Studio OpenAI-compatible endpoint: `http://127.0.0.1:1234/v1`
- Generic local OpenAI-compatible endpoint with `LOCAL_LLM_OPENAI_COMPATIBLE=true`

## Recommended Mac mini M4 16GB profile

| Model | Use | Install command | 16GB posture |
| --- | --- | --- | --- |
| `qwen3:8b` | Default local copilot for summaries, validation explanations, task-draft review | `ollama pull qwen3:8b` | Recommended default |
| `qwen3:4b` | Fast fallback for labels and short summaries | `ollama pull qwen3:4b` | Supported |
| `gemma3:4b` | Privacy-first summarization and drafting | `ollama pull gemma3:4b` | Supported |
| `gemma3:12b` | Quality mode when performance is acceptable | `ollama pull gemma3:12b` | Experimental/tighter memory |
| 27B/30B/32B+ | Larger local experiments | Not recommended by default | Experimental/not recommended for 16GB |

## Safe defaults

```env
AI_ENABLE=false
AI_PROVIDER=mock
AI_DRY_RUN_ONLY=true
AI_ALLOW_NETWORK=false
LOCAL_LLM_ENABLE=false
LOCAL_LLM_PROVIDER=ollama
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=qwen3:8b
LOCAL_LLM_REQUIRE_LOCALHOST=true
LOCAL_LLM_ALLOW_NETWORK=false
```

## Operator rules

- Local LLMs are not automatically safe just because they are local.
- Redaction, prompt governance, audit hashes, human review, and no-live-mutation controls still apply.
- Local LLM outputs are drafts only.
- Local LLM outputs are not financial advice and not trade approval.
- Local LLM workflows do not place orders, cancel orders, approve trades, arm live trading, disable read-only mode, disable the kill switch, or mutate live configuration.

## GUI surfaces

- `/v3/ai` main AI dashboard.
- `/v3/ai/providers` provider inventory and dry-run health.
- `/v3/ai/local-llm` local endpoint settings and Ollama setup guidance.
- `/v3/ai/model-recommendations` model fit table for Apple Silicon / Mac mini M4 16GB.
- `/api/v3/ai/model-recommendations` JSON model recommendation export.
- `/api/v3/ai/local-llm/status` local LLM safety/status summary.

## Validation expectations

Normal validation should use mock/dry-run provider paths. It must not require Ollama, llama.cpp, LM Studio, OpenAI credentials, or network access.
