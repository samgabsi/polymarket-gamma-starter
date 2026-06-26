# Validation - v4.1.0-real

## Scope

v4.1 validation covers package identity, version consistency, imports, route smoke checks, API schema inventory, response envelope validation, runtime migration planner safety, storage compatibility, plugin manifest compatibility, route/module boundary inventory, platform exports, migration exports, secret scanning, package cleanliness, command-palette safety, cockpit safety, task completion safety, guided review safety, and no-live-mutation behavior.

## Commands

Recommended validation commands:

```bash
python -m compileall -q app tests scripts
python scripts/check_versions.py
python scripts/smoke_startup.py
python scripts/capture_v3_screenshots.py --dry-run
pytest
python scripts/validate_v3_release.py --quick
python scripts/validate_v3_release.py
python scripts/check_release_package.py .
```

## Required Confirmations

- Version is `4.1.0-real`.
- Package name is Polymarket OP Console.
- Package slug is `polymarket-op-console`.
- API schema inventory returns route families, schema objects, response envelope metadata, warnings, limitations, unknown/unavailable data, and safety statements.
- Migration planner is non-destructive and does not delete, move, rewrite, copy, or migrate runtime data automatically.
- Platform diagnostics do not mutate live trading state.
- Plugin manifests do not execute code.
- Command-palette actions and keyboard shortcuts do not place or cancel orders.
- Task completion and guided review completion do not approve trades.
- Cockpit, platform, schema, and migration workflows are local-first and non-autonomous by default.
- No real order placement or cancellation occurs during validation.

## Known Limitations

Full browser screenshot capture requires local Playwright/browser setup. The default route-list dry run is dependency-free and safe.
