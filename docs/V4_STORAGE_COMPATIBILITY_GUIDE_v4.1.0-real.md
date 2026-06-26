# V4 Storage Compatibility Guide — v4.1.0-real

## Local Runtime Namespaces

Known runtime namespaces include v2 audit, strategy, research, monitoring, portfolio, governance, v3 workflow runs, analytics snapshots, simulation sessions, datasets, freshness records, tasks, guided workspace records, cockpit records, and v4 platform diagnostics/plugin manifests/schema and migration reports.

## Release ZIP Policy

Release ZIPs must exclude runtime records, runtime exports, logs, screenshots, local credentials, `.env` with real values, database files with user data, cache folders, venvs, node modules, and operating system junk files.

## Compatibility Notes

- v3.5 dataset manifests are local runtime records.
- v3.6 freshness records are local runtime records.
- v3.7 task records are local runtime records.
- v3.8 workspace records are local runtime records.
- v3.9 cockpit records are local runtime records.
- v4.1 platform diagnostics, plugin manifests, schema inventories, route boundary reports, migration plans, and storage maps are local runtime records.

## Migration Policy

v4.1 provides documentation, storage maps, and non-destructive planning only. It does not automatically delete user data, move files, rewrite records, destructively migrate runtime stores, mutate live trading state, approve orders, submit orders, or cancel orders.

## Backup Guidance

Back up package-excluded runtime namespaces before future v4.x schema changes. Sensitive or account-adjacent namespaces require manual review. Missing namespaces in a clean package usually mean the store has not been created yet.
