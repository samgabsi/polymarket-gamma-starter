# V4 Router Architecture Guide - v4.2.0-real

## Purpose

v4.2.0-real begins path-preserving FastAPI router extraction for Polymarket OP Console. The goal is maintainability without changing public URLs, auth behavior, response compatibility, or backend safety gates.

## Extracted In v4.2

- `app/routers/platform.py` registers the v4 platform UI and `/api/v3/platform/*` diagnostics, route, schema, plugin, storage, migration, export, and settings endpoints.
- `app/routers/v3_core.py` registers low-risk `/api/v3/ux/*` status/navigation/design-system endpoints.
- `app/platform_route_registry.py` records route family ownership, router module, current location, extraction status, safety class, live-mutation risk, auth notes, docs links, route count, and representative paths.

## Families Still In app/main.py

Live-control, paper execution, v2 compatibility, core v3 UI, cockpit, workspace, tasks, datasets, freshness, simulation, analytics, research, monitoring, portfolio, governance, and training/data routes remain in `app/main.py` for this release. These are marked `metadata-only`, `planned`, `legacy-preserved`, or `do-not-move-yet` in the route registry.

## Compatibility Rules

- Existing public paths must remain identical.
- Existing auth and setup behavior must remain identical.
- Existing response shapes must remain backward compatible.
- Router extraction must not call live mutation endpoints.
- Router extraction must not remove warnings, blockers, unknown/unavailable data, safety statements, audit behavior, approval checks, typed confirmation phrases, read-only gates, kill-switch gates, or backend risk checks.

## Future Extraction Plan

Move one family at a time after API contract tests and route smoke tests cover the family. Suggested order: platform-adjacent read-only APIs, cockpit, workspace, tasks, datasets, freshness, simulation, analytics, then broader legacy UI routes. Live-control and paper execution-adjacent routes should remain do-not-move-yet until safety-gate coverage is stronger.

## Testing Expectations

Router changes must run import checks, route smoke checks, API contract tests, platform validation, UX validation, generated manual checks, and package cleanliness scans. A route family is not considered safe to move unless path preservation and safety behavior are tested.
