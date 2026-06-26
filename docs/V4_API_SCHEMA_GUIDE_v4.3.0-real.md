# V4 API Schema Guide - v4.3.0-real

## Purpose

v4.3.0-real adds an additive API schema inventory and shared response envelope helper for Polymarket OP Console. The goal is consistency, testability, route ownership clarity, and future v4.x maintainability without risky endpoint rewrites.

v4.3 extends the v4.1 inventory with envelope adoption summary, route-family schema counts, an unnormalized endpoint list, recommended next normalization targets, docs links, and API contract tests.

## Shared Response Envelope

The standard envelope helper lives in `app/platform_api.py`. New platform/schema/migration endpoints may use these fields:

- `success`
- `app_version`
- `generated_at`
- `package_name`
- `package_slug`
- `module`
- `action`
- `data`
- `items`
- `summary`
- `warnings`
- `blockers`
- `unknown_unavailable_data`
- `limitations`
- `safety_statement`
- `no_live_mutation_statement`
- `request_id`
- `correlation_id`
- `pagination`
- `filters`
- `export_manifest`

## Backward Compatibility Rules

Existing v2, v3, cockpit, workspace, task, dataset, freshness, simulation, analytics, and live-control responses are not force-rewritten in v4.3. Future adoption should be additive: preserve existing fields and add envelope fields only when tests/templates can accept them.

## Warnings, Blockers, And Unknown Data

Warnings are review items. Blockers indicate actions that should not proceed. `unknown_unavailable_data` must be used when runtime data, market data, account data, route schema detail, pagination state, or export state is unavailable. Unknown data must not be invented.

## Safety Statement Field

Every normalized platform response carries a safety statement. API schemas are documentation and validation aids only. They do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, or provide financial advice.

## Export Manifest Field

Schema exports use `app/platform_exports.py` and include timestamp, app version, included object IDs, related object IDs, limitations, unknown/unavailable data, secret-safety flags, and no-live-mutation statements.

## Pagination And Filters

The envelope reserves `pagination` and `filters`. v4.3 uses placeholder pagination for lightweight inventories. Future endpoints should populate these fields when returning large lists.

## Route Family Classification

Route family metadata lives in `app/platform_routes.py`. Families include platform, cockpit, workspace, tasks, datasets, freshness, simulation, analytics, search/graph/workflows, v2 live, v3 API, and v2 API surfaces. Inventory does not call handlers.

## Live Mutation Boundary

Schema normalization must never bypass backend gates. Live order submission and cancellation remain controlled by existing live modules, approval checkboxes, typed confirmation phrases, read-only checks, kill switch checks, risk checks, and audit logging.

## Known Limitations

v4.3 does not infer every FastAPI body model. It inventories route families, known schema objects, response-envelope expectations, and platform exports. Full model extraction is a future v4.x candidate.
