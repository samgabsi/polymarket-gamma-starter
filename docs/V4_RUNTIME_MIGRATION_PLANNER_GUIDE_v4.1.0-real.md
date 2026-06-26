# V4 Runtime Migration Planner Guide - v4.1.0-real

## Purpose

v4.1.0-real adds a non-destructive runtime migration planner in `app/platform_migrations.py`. It inventories known runtime namespaces and proposes safe operator-reviewed steps for future v4.x migrations.

## Non-Destructive Contract

The planner does not delete, move, rewrite, copy, or migrate user runtime data automatically. It does not mutate live trading state. It does not place orders, cancel orders, approve trades, sign transactions, arm live trading, or bypass backend gates.

## Runtime Namespaces

The planner uses storage metadata from `app/platform_storage.py`, including v2 audit, strategy, research, monitoring, portfolio, governance, v3 workflows, analytics, simulation, datasets, freshness, tasks, workspace, cockpit, and v4 platform runtime folders.

## Backup Recommendations

Existing namespaces are marked with backup recommendations before future schema changes. Namespaces that may contain sensitive or account-adjacent records require manual review. Clean-package missing namespaces are treated as not-created-yet unless the operator expected local data.

## Compatibility Checks

The planner reports current app version, known compatibility range, expected file format, detected path kind, package-excluded status, lazily-created status, sensitivity marker, and compatibility notes.

## Classification Meanings

- `no-op`: namespace is absent or requires no action.
- `backup recommended`: namespace exists and should be backed up before future migration.
- `manual review required`: sensitive or account-adjacent data requires operator review.
- `safe copy suggested`: future manually controlled copy may be appropriate.
- `schema unknown`: detected format does not match documented expectation.
- `destructive action prohibited`: automatic delete, rewrite, move, order placement, order cancellation, or live arming is rejected.

## Package-Excluded Runtime Data

Runtime namespaces must not be included in release ZIPs. This includes ledgers, strategy data, research data, monitoring data, portfolio data, governance data, v3 indexes, graph files, workflow outputs, analytics snapshots, simulation sessions, dataset payloads, freshness jobs, task records, workspace records, cockpit layouts, platform diagnostics, migration plans, schema inventories, plugin runtime data, backups, screenshots, logs, credentials, and local `.env` values.

## Known Limitations

v4.1 only reports file presence, type, and lightweight counts. It does not inspect full contents, validate every historical record schema, or perform automatic migrations.
