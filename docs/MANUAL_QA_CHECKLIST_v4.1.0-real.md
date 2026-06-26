# MANUAL QA CHECKLIST v4.1.0-real

This v4.1.0-real reference preserves the v3 feature behavior while adding API schema inventory, shared response envelopes, route/module boundary metadata, runtime migration planning, plugin manifest compatibility, diagnostics, storage compatibility notes, centralized safety helpers, and validation hardening. Existing live/paper/task/workspace/cockpit safety gates remain intact.

- Open `/v3/platform`, `/v3/platform/schema`, `/v3/platform/migrations`, `/v3/platform/migrations/plan`, and `/v3/platform/migrations/storage-map`.
- Confirm schema and migration pages state that they are local-first, non-destructive, and do not place/cancel orders.
- Confirm migration plan steps include backup/manual-review guidance and destructive-action prohibition.
- Open `/v3/cockpit`, `/v3/cockpit/layouts`, `/v3/cockpit/focus`, `/v3/cockpit/review`, `/v3/cockpit/tasks`, `/v3/cockpit/dependencies`, `/v3/cockpit/source`, `/v3/cockpit/packets`, `/v3/cockpit/command-palette`, `/v3/cockpit/shortcuts`, and `/v3/cockpit/settings`.
- Confirm cockpit pages show safety statements.
- Confirm layouts, panels, focus modes, shortcuts, command-palette actions, source context, dependencies, and packets render with empty states.
- Confirm command-palette forbidden live actions are rejected by API.
- Confirm shortcuts are navigation/local workflow only.
- Confirm v3.7 task routes and v3.8 workspace routes still render.
- Confirm v2 live controls still require backend gates.
- Confirm no screenshots, runtime cockpit records, schema inventories, migration plans, storage maps, runtime exports, or local data are included in the release ZIP.
