# V3 GUIDED OPERATOR WORKSPACE GUIDE v4.2.0-real

This v4.2.0-real reference preserves the v3 feature behavior while adding platform stabilization, plugin manifest boundaries, diagnostics, storage compatibility notes, centralized safety helpers, and validation hardening. Existing live/paper/task/workspace/cockpit safety gates remain intact.

v4.2.0-real adds the **Guided Operator Workspace, Interactive Review Flows, and Task Dependency Intelligence** layer. It is a local-first human-in-the-loop workflow aid for understanding what needs attention, what depends on what, what source context should be reviewed, and what safe manual next action can be considered.

## What guided reviews are

Guided reviews are step-by-step local review sessions for daily review, weekly planning, task triage, blocked-task review, dataset review, freshness review, simulation review, analytics review, governance review, monitoring review, portfolio review, and research review. They create local session records, unresolved-item lists, blocker notes, task links, and review packets.

## What guided reviews are not

Guided reviews are not orders, not trade approval, not live automation, not paper execution, not financial advice, not model calls, and not a bypass around existing backend safety gates. Completing a guided review only means the operator completed a workflow review. It does not approve, submit, cancel, sign, or arm anything.

## Relationship to other modes

- **Live trading** remains behind the existing live gates, approval checkbox, typed confirmation phrase, warning acknowledgements, audit logging, read-only gate, and kill-switch controls.
- **Paper trading** remains separate from guided workspace sessions and tasks.
- **Demo data** is fake and must never be presented as real market data.
- **Simulation/replay** remains descriptive and local; guided reviews can create follow-up tasks or packets only.
- **Dataset collection/freshness scheduling** remains read-only and operator-triggered.
- **Task planning** tracks workflow items; guided workspace adds review paths, dependency edges, source previews, saved views, and packets.

## Daily guided review

The daily flow walks through safety posture, live/read-only/kill-switch state, notifications, freshness, datasets, monitoring, research, portfolio warnings, governance, analytics, simulation follow-ups, open tasks, blocked tasks, due/overdue work, safe next actions, and packet generation. Each step records notes, unknowns, blockers, and safe follow-up tasks.

## Weekly guided review

The weekly flow rolls up open work, overdue tasks, recurring blockers, stale data, research backlog, thesis review needs, dataset/freshness review, simulation/replay review, analytics learning review, governance improvements, backup/data-integrity review, next-week focus, and weekly task planning.

## Task triage

Task triage lets the operator review inbox items, preview source context, convert safe findings into local tasks, dismiss irrelevant suggestions, identify blockers, and generate a triage packet.

## Task dependencies and blocked-task review

Dependencies are workflow-only edges between task IDs. They help the operator see blockers, blocked-by relationships, dependency chains, and unresolved prerequisites. Dependency completion is not trade approval and does not mutate live trading state.

## Source previews

Source previews show subsystem, object type, object ID, finding title, severity, timestamp, related objects, safe summary, unknown/unavailable data, recommended template, safety class, and source link where available. Missing source data is shown honestly and is not invented.

## Saved task views

Saved views are reusable filters such as Due Today, Overdue, Urgent/Critical, Blocked, Waiting, Freshness-related, Dataset-related, Simulation follow-ups, Governance follow-ups, Analytics follow-ups, Monitoring alerts, Research review, Live-action references, No due date, and Recently completed. Saved views are not trading recommendations and do not perform actions.

## Review packets and exports

Guided workspace exports include JSON/Markdown workspace exports, dependency reports, saved-view reports, CSV dependency exports, CSV saved-view exports, and guided session exports. Packets include timestamp, app version, flow/session IDs, task IDs, related object IDs, unresolved items, blockers, limitations, unknown/unavailable data, and safety statements.

## Integrations

The guided workspace is exposed in command center, task planner, local search, decision graph, workflows, demo fixtures, validation, docs, screenshot planning, and module review entry points for freshness, datasets, simulation, analytics, governance, monitoring, portfolio, and research.

## Known limitations

The workspace is intentionally local-first and non-autonomous. It does not run expensive scans on startup, does not generate packets on every page load, does not perform network-heavy work, and does not call AI/model providers. Some source context may be unavailable until the operator creates records or opens the related module.