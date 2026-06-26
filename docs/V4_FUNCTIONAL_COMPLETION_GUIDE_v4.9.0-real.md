# v4.9.0 Functional Completion Guide

v4.9.0-real is a wiring and honesty pass. The rule for visible UI is: a visible action must work, navigate to a real route, save state, or explain why it is unavailable.

## Layout selector

The `/v3/cockpit` Layout Selector now uses real form-backed cards. Selecting a layout calls the cockpit layout-selection path, stores `selected_layout_id`, updates the displayed panels, and records an audit event.

## Focused review modes

Focused review cards start a local session snapshot, set `active_focus_mode_id`, select the matching layout, and redirect to the configured cockpit review route.

## Saved layouts

The Save current layout copy action creates an operator-owned layout copy in the local cockpit layout store and selects it.

## Feature status

Open `/api/v3/features/status` for the readiness registry. Status values include `working`, `partial`, `disabled`, `config_required`, `scaffolded`, and `unavailable`.

## Safety

The feature status registry is descriptive. It does not execute adapters, call AI, place orders, cancel orders, arm live trading, or bypass any backend gate.
