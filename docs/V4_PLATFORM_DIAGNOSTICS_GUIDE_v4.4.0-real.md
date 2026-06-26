# V4 Platform Diagnostics Guide — v4.4.0-real

v4.4 diagnostics report platform health, route inventory, route ownership registry, extracted router modules, API contract status, generated manual status, plugin metadata boundaries, storage compatibility, schema inventory, response envelopes, migration planning, and no-live-mutation safety posture.

## UI Routes

- `/v3/platform`
- `/v3/platform/health`
- `/v3/platform/routes`
- `/v3/platform/schema`
- `/v3/platform/plugins`
- `/v3/platform/storage`
- `/v3/platform/migrations`
- `/v3/platform/migrations/plan`
- `/v3/platform/migrations/storage-map`
- `/v3/platform/diagnostics`
- `/v3/platform/exports`
- `/v3/platform/settings`

## API Routes

- `/api/v3/platform/summary`
- `/api/v3/platform/health`
- `/api/v3/platform/routes`
- `/api/v3/platform/route-registry`
- `/api/v3/platform/routes/export.json`
- `/api/v3/platform/routes/export.md`
- `/api/v3/platform/schema`
- `/api/v3/platform/schema/families`
- `/api/v3/platform/schema/envelopes`
- `/api/v3/platform/schema/objects`
- `/api/v3/platform/schema/export.json`
- `/api/v3/platform/schema/export.md`
- `/api/v3/platform/plugins`
- `/api/v3/platform/storage`
- `/api/v3/platform/storage/export.json`
- `/api/v3/platform/storage/export.md`
- `/api/v3/platform/migrations/summary`
- `/api/v3/platform/migrations/plan`
- `/api/v3/platform/migrations/storage-map`
- `/api/v3/platform/migrations/export.json`
- `/api/v3/platform/migrations/export.md`
- `/api/v3/platform/diagnostics`
- `/api/v3/platform/export.json`
- `/api/v3/platform/export.md`
- `/api/v3/platform/settings`

## What Diagnostics Show

Diagnostics show app version, route inventory, module inventory, API schema inventory, response envelope summary, migration planner summary, storage map, local storage namespaces, plugin manifests, validation capability summary, export capability summary, safety posture, unknown/unavailable data, and no-live-mutation statements.

## What Diagnostics Do Not Do

Diagnostics do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, run network-heavy workflows on startup, call AI/model providers, expose secrets, automatically migrate runtime data, or mutate live trading state.
