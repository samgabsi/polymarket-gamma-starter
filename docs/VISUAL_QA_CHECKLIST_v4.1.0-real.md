# VISUAL QA CHECKLIST v4.1.0-real

This v4.1.0-real reference preserves the v3 feature behavior while adding platform schema inventory, response envelope summaries, runtime migration planning, route/module boundary metadata, plugin manifest boundaries, diagnostics, storage compatibility notes, centralized safety helpers, and validation hardening. Existing live/paper/task/workspace/cockpit safety gates remain intact.

Use `python scripts/capture_v3_screenshots.py --dry-run` to verify route coverage. Capture real screenshots only in a local runtime folder after confirming no secrets are visible.

Platform routes to inspect: `/v3/platform`, `/v3/platform/schema`, `/v3/platform/migrations`, `/v3/platform/migrations/plan`, `/v3/platform/migrations/storage-map`, `/v3/platform/routes`, `/v3/platform/storage`, `/v3/platform/plugins`, `/v3/platform/diagnostics`.

Cockpit routes to inspect: `/v3/cockpit`, `/v3/cockpit/layouts`, `/v3/cockpit/focus`, `/v3/cockpit/review`, `/v3/cockpit/tasks`, `/v3/cockpit/dependencies`, `/v3/cockpit/source`, `/v3/cockpit/packets`, `/v3/cockpit/command-palette`, `/v3/cockpit/shortcuts`, `/v3/cockpit/settings`.

Confirm responsive behavior, clear safety labels, empty states, warning states, unknown/unavailable states, readable multi-panel layout, and no dangerous action styling confusion.
