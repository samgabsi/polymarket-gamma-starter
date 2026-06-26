# Validation - v4.2.0-real

## Scope

Validation covers version identity, OpenAI safe defaults, AI dry-run workflows, prompt governance, structured schemas, redaction, AI suggestion human acceptance, ChatGPT connector forbidden tools, router imports, extracted route preservation, route ownership registry, API contract tests, generated manual output, API schema inventory, runtime migration planner, plugin manifest safety, platform diagnostics, startup smoke, screenshot dry-run planning, and package cleanliness.

## Expected Commands

- `python -m compileall -q app tests scripts`
- `python -m pytest -q tests/test_ai_v4.py tests/test_live_v3_platform.py tests/test_api_contracts_v4.py`
- `python scripts/generate_operator_manual.py`
- `python scripts/check_versions.py`
- `python scripts/smoke_startup.py`
- `python scripts/capture_v3_screenshots.py --dry-run`
- `python scripts/validate_v3_release.py`
- `python scripts/validate_v3_ux_release.py`
- `python scripts/check_release_package.py .`

## Safety Confirmations

- No real order placement occurred.
- No real cancellation occurred.
- Routers, API contracts, manual generation, schema inventory, migration planner, platform diagnostics, plugin manifests, command palette, keyboard shortcuts, task completion, guided review completion, and cockpit workflows do not arm live trading.
- Generated manual contains no obvious secrets and no runtime records.
- OpenAI API and Responses API are disabled by default.
- AI dry-run mode is enabled by default and makes no network calls.
- AI task suggestions require explicit human acceptance before local task creation.
- ChatGPT connector blueprint is read-only, auth-required, and disabled by default.
- `data/ai/` runtime records are excluded from release ZIPs.
- Migration planner does not delete, move, rewrite, copy, export, or migrate runtime data automatically.
- Platform diagnostics do not mutate live trading state.
- Plugin manifests do not execute code.
- Screenshots are not included in the release ZIP unless explicitly reviewed and intended.
