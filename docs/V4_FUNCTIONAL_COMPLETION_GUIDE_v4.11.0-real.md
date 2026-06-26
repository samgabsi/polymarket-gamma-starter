# v4.11.0 Functional Completion Guide

v4.11.0-real keeps the visible-control rule: a visible action must work, navigate to a real route, save local state, export data, or clearly state why it is unavailable.

## Burn-down Registry

Use:

- `/api/v3/features/status`
- `/api/v3/features/stub-burndown`
- `/v3/cockpit`

The burn-down map is the operator-facing truth table for partially wired, config-required, disabled, scaffolded, and tested surfaces.

## Completed v4.11 Wiring

- Workspace daily review, weekly review, and task triage now use page POST forms.
- AI provider dry-run now uses a page POST form.
- AI Edge packet generation now uses a page POST form.
- AI Edge evidence normalization preview now uses a page POST form.
- AI review-packet generation now uses a page POST form.
- POST wrappers redirect with visible `action_status` feedback.

## Review-only Boundary

Completing a task, starting a guided review, generating an AI draft, generating an AI Edge packet, reviewing an arbitrage candidate, or saving a cockpit layout does not approve a trade or mutate live execution state.
