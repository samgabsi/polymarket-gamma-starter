# Stub Burn-down Map - v4.11.0-real

Open `/api/v3/features/stub-burndown` for the machine-readable map. The Cockpit page also renders the map in the System Readiness section.

## Status Values

- `working`: wired and visible for its stated review-only scope.
- `partial`: meaningful behavior exists, but coverage/configuration is incomplete.
- `config_required`: backend exists but requires explicit local configuration.
- `scaffolded`: deliberately present as future-facing metadata or disabled boundary.
- `disabled`: intentionally off in the packaged safe default.
- `unavailable`: not available in this package/runtime state.
- `needs_tests`: useful coverage exists but should be broadened before claiming complete coverage.
- `needs_ui_wiring`: backend exists but visible UI needs a real control.
- `needs_backend_wiring`: UI exists but backend behavior is incomplete.
- `needs_docs`: operator docs need more detail.

## v4.11 Coverage

- Polymarket discovery/pricing/orderbook: `partial`.
- AI news odds: `working` for review-only manual evidence and draft adjustment, with web search config-gated.
- AI Edge research: `working` for local draft packets and evidence review.
- YES/NO recommendation clarity: `working`.
- Cross-market arbitrage scanner/review: `partial` by default because live venue breadth is config-gated.
- Kalshi: `disabled` or `config_required` depending local settings.
- Venue registry: `partial`.
- Review queue and audit log: `working`.
- Cockpit layouts and focus modes: `working`.
- Task triage, blocked/dependency/source/dataset review: `working`.
- Settings/config and feature readiness: `working`.
- Export/import: `partial`; export coverage is broad, restore/import remains gated.
- Launch helpers: `working`.
- Live execution controls: `disabled` by safe default and still backend-gated.

## Safety Boundary

The map is static and local. It does not probe networks, call AI models, place orders, cancel orders, approve trades, sign transactions, arm live trading, disable read-only mode, or bypass the kill switch.
