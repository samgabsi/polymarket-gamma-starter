# V2 TO V3 MIGRATION GUIDE v4.3.0-real

This v4.3.0-real reference preserves the v3 feature behavior while adding platform stabilization, plugin manifest boundaries, diagnostics, storage compatibility notes, centralized safety helpers, and validation hardening. Existing live/paper/task/workspace/cockpit safety gates remain intact.

Existing v2 routes and safety controls remain compatible. v3.7 adds `/v3/freshness` and `/api/v3/freshness/*` while preserving v3 datasets, simulation, analytics, workflows, search, graph, and command center.


## v3.7 Task Planner Addendum

The v3.7 release adds a local-first Operator Task Planner, task inbox, task board, daily ops checklist, weekly planning packet, review cadence manager, task templates, and task exports. These features are human-in-the-loop workflow records only. They do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, or provide financial advice.