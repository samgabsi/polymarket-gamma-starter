# Validation - v4.4.0-real

Validation focuses on version consistency, navigation discoverability, alias route safety, system map rendering, v2/v3/AI/platform bridge links, import/startup checks, package cleanliness, and no-live-mutation safety boundaries.

Expected confirmations:

- Root dashboard links to Operator OS, AI Copilot, Live Controls, Platform, Cockpit, Tasks, and System Map.
- Alias routes redirect to canonical pages and do not mutate state.
- AI remains disabled/dry-run by default.
- OpenAI and local LLM providers remain disabled by default.
- AI Edge remains disabled, mock, dry-run-only, and approval-gated by default.
- OpenAI web search is disabled by default and dry-run review packets do not call the network.
- Local LLM edge review requires app-provided evidence and cannot claim web search.
- AI Edge packets include citations, contradictions, missing-information tracking, and calibration metadata.
- AI Edge exports do not include secrets, raw prompts, or raw responses.
- No real order placement or cancellation occurs.
- Release ZIP excludes runtime data, secrets, caches, screenshots, venvs, and logs.
