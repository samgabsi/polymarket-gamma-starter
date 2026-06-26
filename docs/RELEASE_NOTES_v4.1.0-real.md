# Release Notes - v4.1.0-real

## API Schema Normalization, Route/Module Boundary Cleanup, And Runtime Migration Planner

v4.1.0-real is a maintainability and safety-hardening release for Polymarket OP Console. It preserves existing v2, v3, v4 platform, cockpit, guided workspace, task, dataset, freshness, simulation, analytics, research, monitoring, portfolio, governance, paper, and live-control behavior while adding deeper internal consistency.

## Added

- Shared platform API response envelope helper in `app/platform_api.py`.
- API family, response envelope, schema object, and schema consistency inventory.
- Non-destructive runtime migration planner in `app/platform_migrations.py`.
- Runtime namespace inventory, migration plan, storage map, and JSON/Markdown exports.
- Route/module boundary metadata with owner modules, safety classes, docs links, and future modularization notes.
- Platform diagnostics coverage for schema, response envelopes, migrations, storage maps, route families, plugins, validation, unknown/unavailable data, and safety posture.
- Search, graph, workflow, demo fixture, validation, smoke, and screenshot-route-list integration for v4.1 platform objects.
- Plugin compatibility checks for required fields, no-live-mutation, no-secret-access, no-network-by-default, forbidden live capabilities, namespace declarations, and current app compatibility.

## Safety

This release does not add autonomous trading, hidden execution, order placement, order cancellation, auto-arming, or financial advice. Migration helpers and schema helpers do not mutate live trading state and do not automatically migrate user runtime data.

## Package

Release ZIP name: `polymarket-op-console-v4.1.0-real.zip`

Package identity remains Polymarket OP Console with slug `polymarket-op-console`.
