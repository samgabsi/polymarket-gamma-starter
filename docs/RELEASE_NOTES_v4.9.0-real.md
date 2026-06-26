# Release Notes - v4.9.0-real

## Functional Completion and Surfacing Pass

v4.9.0-real focuses on making visible cockpit and review controls honest, selectable, persistent, and testable instead of adding another layer of unfinished features.

### Completed / surfaced

- Cockpit Layout Selector cards are now real POST-backed controls.
- Selecting a layout updates the active cockpit layout, changes the selected panel set, persists through the cockpit settings store, and writes a local audit event.
- Focused Review Mode cards now start a local focus session, switch the related cockpit layout, and navigate to the corresponding cockpit review route.
- Added a Save current layout copy action so the saved-layout surface is functional rather than decorative.
- Added a System Readiness / Feature Status registry and `/api/v3/features/status` endpoint so visible features can be marked working, disabled, partial, config-required, scaffolded, or unavailable.
- Surfaced AI odds adjustment and cross-market arbitrage readiness as review-only statuses without implying fake execution.
- Added UI regression tests for layout selection, persistence, focus mode navigation, saved layout creation, and feature status honesty.

### Safety posture

- No autonomous order placement was added.
- Cockpit cards, focus modes, and saved layouts do not place orders, cancel orders, approve trades, sign transactions, arm live trading, bypass backend gates, or provide financial advice.
- Missing Kalshi credentials continue to leave the adapter disabled/config-required instead of crashing the app.

### Known limitations

- This pass does not complete every historical page in the project; it adds an explicit feature-status map and fixes the highest-visibility cockpit gap first.
- Kalshi remains disabled/config-required unless configured by the operator.
- Cross-market arbitrage remains detection/review only.
