# V3 OPERATOR TASK PLANNER GUIDE v4.3.0-real

This v4.3.0-real reference preserves the v3 feature behavior while adding platform stabilization, plugin manifest boundaries, diagnostics, storage compatibility notes, centralized safety helpers, and validation hardening. Existing live/paper/task/workspace/cockpit safety gates remain intact.

v4.3.0-real adds the **Operator Task Planner, Review Cadence Manager, and Human-in-the-Loop Daily Ops Layer**. It gives the operator a cockpit for “what do I need to do next?” without creating autonomous trading, hidden execution, order placement, order cancellation, live arming, or financial advice.

## What operator tasks are

Operator tasks are local workflow records. A task can capture a follow-up from a notification, freshness finding, dataset warning, simulation replay, analytics report, governance checklist, monitoring alert, research queue item, portfolio warning, missing prerequisite scan, or manual operator note.

Each task records an ID, timestamps, app version, title, description, source subsystem, source object type and ID, related object IDs, task type, priority, status, due date, cadence tag, safety class, operator notes, completion notes, blockers, unknown/unavailable data, tags, follow-up notes, dependencies, and audit metadata.

## What operator tasks are not

Operator tasks are not orders, authorizations, signatures, approvals, market predictions, financial advice, or execution instructions. Completing a task means only that the operator completed a workflow review. It does not approve or submit a trade.

## Boundaries between modes

- **Live trading** remains controlled by existing backend gates, approval checkbox, typed confirmation phrase, warning acknowledgements, read-only state, kill switch state, and audit enforcement.
- **Paper trading** remains local simulation and does not become live execution.
- **Demo data** is fake, secret-free, and clearly labeled.
- **Simulation/replay** is descriptive and never submits or cancels orders.
- **Dataset collection/freshness scheduling** is read-only and operator-triggered unless explicitly configured otherwise.
- **Task planning/cadence** only creates local workflow records or review packets.

## Routes

UI routes:

- `/v3/tasks`
- `/v3/tasks/board`
- `/v3/tasks/inbox`
- `/v3/tasks/today`
- `/v3/tasks/week`
- `/v3/tasks/cadence`
- `/v3/tasks/reviews`
- `/v3/tasks/templates`
- `/v3/tasks/exports`
- `/v3/tasks/settings`

Core APIs include `/api/v3/tasks`, `/api/v3/tasks/summary`, `/api/v3/tasks/inbox`, `/api/v3/tasks/inbox/scan`, `/api/v3/tasks/board`, `/api/v3/tasks/daily-ops`, `/api/v3/tasks/weekly-plan`, `/api/v3/tasks/cadence`, `/api/v3/tasks/cadence/run`, `/api/v3/tasks/templates`, and export endpoints for JSON, Markdown, and CSV.

## Task inbox

The task inbox gathers reviewable suggestions from local notifications, freshness findings, dataset readiness warnings, simulation findings, analytics warnings, governance items, monitoring alerts, research queue items, stale evidence, portfolio warnings, data health warnings, workflow warnings, missing prerequisite findings, and manual operator-created items.

Inbox actions are local only: create task, dismiss, archive, snooze, link to source, and bulk safe review. These actions do not mutate live trading state.

## Task board

The board uses local statuses:

- inbox
- planned
- active
- waiting
- blocked
- done
- dismissed
- archived

The board supports creating tasks, editing tasks, changing priority/status, due dates, tags, notes, related objects, blockers, completion notes, and exports. A task that references a gated live action is labeled `gated-live-action-reference`; completing it means review is complete, not that live execution is authorized.

## Priorities

Priorities are operator workflow priorities only:

- low
- medium
- high
- urgent
- critical

Priority can be influenced by source severity, due date, stale age, critical alert flag, dataset readiness impact, simulation readiness impact, governance blocker, portfolio/risk relevance, or manual priority. Priority is not a trading recommendation.

## Daily ops checklist

The daily ops checklist covers system safety posture, live armed/read-only/kill-switch state, data health, freshness notifications, dataset readiness, monitoring alerts, research queue, stale evidence, portfolio warnings, governance items, analytics warnings, simulation follow-ups, open tasks, blocked tasks, exports/backups, and safe next actions.

Daily ops packets include date, summary, completed checks, unresolved items, tasks created, tasks completed, blockers, unknown/unavailable data, task summary, and safety statement.

## Weekly planning

Weekly planning rolls up open tasks, overdue tasks, recurring blockers, stale data, unresolved research, thesis review needs, dataset/freshness review, simulation/replay review, analytics learning report review, governance improvements, backup/data integrity review, next-week focus, and task plan for the week.

## Review cadence manager

Cadence rules can target thesis reviews, evidence freshness, research queue, monitoring alerts, portfolio risk, governance, data health, dataset readiness, simulation review, analytics learning reports, weekly planning, and daily ops. Cadence generation is operator-triggered and does not create hidden tasks unexpectedly.

## Notification-to-task and finding-to-task conversion

Local freshness notifications and findings can be converted into tasks. The converted task links back to its source object and preserves safety labels. Acknowledging a notification after task creation remains local and does not change live trading state.

## Integrations

v3.7 integrates tasks into the command center, global search, decision graph, workflow templates, freshness pages, dataset pages, simulation pages, analytics pages, and exports. The integration is intentionally descriptive and local-first.

## Exports

Task exports include JSON, Markdown, and CSV. Daily ops packets and weekly ops packets export to JSON and Markdown. Exports include timestamps, app version, task IDs, related object IDs, status summaries, blockers, warnings, limitations, unknown/unavailable data, and safety statements. Exports are redacted and secret-safe.

## Known limitations

The task planner does not run background jobs on startup, does not perform network-heavy scans automatically, and does not call AI/model providers on page load. Some source objects may be unavailable if their module has no local records yet; those cases are shown as unknown/unavailable rather than invented.