# V4 Platform Architecture Guide — v4.1.0-real

## What v4.1 Stabilizes

v4.1.0-real stabilizes the operator intelligence platform after the v3 feature expansion. It adds shared version metadata, safety helpers, export helpers, route inventory, plugin manifest validation, platform diagnostics, storage compatibility notes, API schema inventory, shared response envelope helpers, route/module boundary metadata, and a non-destructive runtime migration planner.

## What v4.1 Does Not Change

It does not change live order placement, cancellation, approval, signing, live arming, read-only gates, kill switch behavior, risk checks, audit logging, or emergency controls. Existing v2 and v3 routes remain available.

## Module Boundary Philosophy

The v4 platform modules are additive and low-risk:

- `platform_version.py` centralizes release metadata.
- `platform_safety.py` centralizes standard safety statements and forbidden live-mutation capability names.
- `platform_exports.py` provides common JSON/Markdown/CSV export helpers.
- `platform_routes.py` inventories route families without calling handlers.
- `platform_plugins.py` validates metadata-only plugin manifests.
- `platform_storage.py` documents local runtime storage namespaces.
- `platform_api.py` documents API families, response envelopes, and schema objects.
- `platform_migrations.py` inventories runtime namespaces and proposes non-destructive migration steps.
- `platform_diagnostics.py` combines health, routes, plugins, storage, schemas, migrations, and safety into a local diagnostics layer.

## Route Registry Philosophy

Route inventory is diagnostic only. It lists route families and methods but does not call live mutation endpoints or infer trading approval.

## API Schema Philosophy

API schemas are documentation and validation aids. The shared response envelope is additive and backward-compatible. It does not replace backend safety gates or hide blockers, warnings, stale data, unavailable data, or unknown data.

## Plugin Manifest Boundary

Plugin manifests are metadata only. They describe future extension capabilities, allowed namespaces, forbidden capabilities, safety class, and no-live-mutation flags. v4.1 does not execute plugin code, load remote code, or grant secret access.

## Diagnostics Philosophy

Diagnostics are local operational aids. They are designed to be fast, redacted, secret-safe, non-network-heavy, and non-mutating.

## Local-First Storage Philosophy

Runtime stores are created lazily under `data/` and excluded from release ZIPs. v4.1 documents compatibility for v3.5 dataset stores, v3.6 freshness stores, v3.7 task stores, v3.8 workspace stores, v3.9 cockpit stores, and v4.1 platform stores.

## Runtime Migration Planner Philosophy

Migration plans are advisory only. The planner does not delete, move, rewrite, copy, or migrate user data automatically. It never mutates live trading state and classifies destructive actions as prohibited.

## Export Helper Philosophy

Exports include timestamp, app version, included IDs, related IDs, unknown/unavailable data, limitations, and the standard safety statement. Exports must be secret-safe.

## Live Mutation Boundary

No platform, plugin, diagnostic, route inventory, export, task, guided review, cockpit, shortcut, command-palette, dataset, freshness, simulation, or analytics helper may place orders, cancel orders, arm live trading, approve trades, sign transactions, or bypass gates.

## Future v4.x Guidance

Future v4.x features should attach through safe local modules, metadata-first manifests, explicit operator-triggered actions, tests, docs, route inventory, and validation harness updates.
