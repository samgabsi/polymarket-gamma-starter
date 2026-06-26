# V3 OPERATOR COCKPIT GUIDE v4.2.0-real

This v4.2.0-real reference preserves the v3 feature behavior while adding platform stabilization, plugin manifest boundaries, diagnostics, storage compatibility notes, centralized safety helpers, and validation hardening. Existing live/paper/task/workspace/cockpit safety gates remain intact.

v4.2.0-real adds the **Multi-Panel Operator Cockpit, Keyboard Navigation, and Review Layout System**. The cockpit is a local-first operator workspace for moving quickly between tasks, guided reviews, source previews, dependency chains, packets, datasets, freshness findings, simulations, analytics, governance, monitoring, research, and portfolio context.

## What the cockpit is

The cockpit is a navigation, layout, and safe-summary layer. It gives the operator side-by-side views of workflow objects and lets them save layouts, choose focus modes, inspect dependencies, use safe keyboard shortcuts, and open safe local command-palette actions.

## What the cockpit is not

The cockpit is not an order system, trading bot, live execution layer, financial adviser, or autonomous workflow engine. Cockpit completion, layout selection, shortcut use, command-palette use, task completion, and guided review completion never approve trades.

## Mode distinctions

- **Live trading:** backend-gated, explicit, fail-closed, and guarded by existing approval and confirmation requirements.
- **Paper trading:** local simulation only.
- **Demo:** fake, secret-free examples.
- **Simulation/replay:** descriptive process evaluation only.
- **Dataset collection:** read-only snapshots and replay manifests.
- **Freshness scheduling:** read-only collection planning and local notifications.
- **Task planning:** local workflow records and human follow-through.
- **Guided reviews:** local step-by-step review sessions and packets.
- **Cockpit:** local multi-panel navigation and review layout layer.

## Multi-panel layouts

Cockpit layouts are local JSON/JSONL records with panel definitions, default focus panel, layout type, operator notes, unknown/unavailable data, and safety metadata. Default layouts include daily ops, weekly review, task triage, blocked tasks, source review, dataset review, freshness review, simulation review, analytics review, governance review, research review, monitoring review, and portfolio review.

## Saved layouts

The operator can list, create, update, select, export, and reset cockpit layouts. Layout changes never mutate live trading state and never place or cancel orders.

## Focus modes

Focus modes combine a layout, relevant panels, entry route, safe next-action text, and explicit unknown/unavailable data handling. Focus modes are available for daily review, weekly review, task triage, blocked task review, source preview review, dependency review, dataset review, freshness review, simulation review, analytics review, governance review, monitoring review, research review, and portfolio review.

## Keyboard shortcuts

Keyboard shortcuts are safe navigation and local workflow shortcuts. They can open the command palette, jump to cockpit/tasks/workspace, move focus between panels, open detail panels, close detail panels, and refresh safe summaries manually. They do not place orders, cancel orders, approve trades, sign transactions, arm live trading, disable the kill switch, or bypass read-only mode.

## Command palette

The command palette exposes a manifest of safe local actions: navigate to pages, open tasks or reviews, create local task records, change local task metadata, generate review packets, export safe reports, switch cockpit layout, show shortcuts, and open settings. Forbidden actions such as place order, cancel order, approve trade, sign transaction, arm live trading, disable kill switch, bypass read-only mode, or mutate live trading state are rejected.

## Side-by-side task/source/review context

The cockpit can display source preview plus task detail, task detail plus dependency chain, guided review step plus linked tasks, review packet plus unresolved items, saved view plus task detail, and notification/finding plus task creation context. Missing data is shown as unknown/unavailable rather than invented.

## Dependency visualization

The dependency view shows selected task, tasks it depends on, tasks blocked by it, unresolved blockers, completed dependencies, dependency warnings, related source previews, and related review packets. Dependency chains are workflow-only relationships and never approve or execute trades.

## Integrations

The cockpit integrates with:

- Task planner: task lists, task detail, dependency counts, blockers, saved view membership, source preview links, and safe local quick actions.
- Guided workspace: daily/weekly review, task triage, blocked-task review, dependency review, and source-preview review.
- Freshness, datasets, simulation, analytics, governance, monitoring, research, and portfolio views through safe cockpit entry points.
- Search and graph through cockpit layout, panel, focus mode, command palette, keyboard shortcut, session snapshot, and export objects.
- Workflows through cockpit layout review, focus mode review, dependency review, source context review, and command-palette safety review.

## Exports

Cockpit exports include JSON and Markdown layout reports, focus mode exports, command palette safety reports, keyboard shortcut reports, and optional CSV exports. Exports include app version, timestamps, layout IDs, panel IDs, related objects where available, blockers, warnings, limitations, unknown/unavailable data, and explicit safety statements.

## Safety boundary

Cockpit actions do not bypass live trading gates. Command-palette actions do not place or cancel orders. Keyboard shortcuts do not place or cancel orders. Task completion and review completion are not trade approval. Live order submission still requires existing backend enforcement.

## Known limitations

The cockpit uses lightweight HTML/CSS panels and table/tree views rather than a heavyweight drag-and-drop dashboard framework. Source and dependency context is limited to local records available at page load or explicitly created by the operator.