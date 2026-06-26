# Release Notes - v4.4.0-real

## Evidence-Backed AI Edge Research

v4.4.0-real adds an AI Edge Research surface to the unified AI navigation. It creates evidence-backed research packets with source metadata, citations, contradictions, missing-information tracking, draft probability/fair-probability estimates, dry-run OpenAI web-search request plans, local LLM evidence-review boundaries, and calibration records.

Safe defaults remain fail-closed: AI Edge is disabled, mock, dry-run-only, approval-gated, web search disabled, runtime/private data blocked, market-implied comparison disabled, local LLM web-search claims prohibited, and raw prompts/responses are not stored.

## Unified Operator Surface, Navigation Bridge, and v2/v3/AI Shell Flattening

v4.4.0-real turns Polymarket OP Console into a more discoverable single-surface application. It preserves all existing v2, v3, v4, AI, platform, cockpit, workspace, task, dataset, freshness, simulation, analytics, migration, plugin, and live-control features while adding unified navigation, bridge panels, friendly aliases, and a system map.

### Highlights

- Root dashboard upgraded into a unified operator home.
- Global navigation now exposes Home, Operator OS, AI Copilot, Live Controls, Platform, Cockpit, Workspace, Tasks, Data/Freshness, Simulation/Analytics, Settings, and Route Map.
- v2 live console includes bridge links to v3, AI, Platform, Cockpit, Tasks, Settings, and Route Map.
- v3 command center includes a System Bridge explaining v2, v3, AI, and Platform roles.
- Friendly aliases such as `/ai`, `/platform`, `/cockpit`, `/workspace`, `/tasks`, `/live`, and `/operator-os` redirect to canonical routes.
- `/system-map` and `/routes` provide canonical path, alias, safety class, and mutation-risk guidance.

### Safety

Navigation links and aliases are safe entry points only. They do not place orders, cancel orders, approve trades, arm live trading, disable safety gates, or bypass backend enforcement.
