# Validation - v4.3.0-real

Validation focuses on version consistency, navigation discoverability, alias route safety, system map rendering, v2/v3/AI/platform bridge links, import/startup checks, package cleanliness, and no-live-mutation safety boundaries.

Expected confirmations:

- Root dashboard links to Operator OS, AI Copilot, Live Controls, Platform, Cockpit, Tasks, and System Map.
- Alias routes redirect to canonical pages and do not mutate state.
- AI remains disabled/dry-run by default.
- OpenAI and local LLM providers remain disabled by default.
- No real order placement or cancellation occurs.
- Release ZIP excludes runtime data, secrets, caches, screenshots, venvs, and logs.
