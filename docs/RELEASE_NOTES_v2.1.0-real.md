# Release Notes — v2.1.0-real

`v2.1.0-real` is a UI/UX redesign, cleanup, declutter, smoothness, and speed pass on top of the v2.0 live-trading control plane.

## Highlights

- Cleaner Live v2 navigation: Dashboard, Markets, Trade Ticket, Orders, Positions, Risk, Audit, Settings, Emergency, Docs.
- Persistent status bar across Live v2 pages with mode, live armed state, read-only state, kill-switch state, readiness, Gamma/CLOB posture, refresh time, and last critical issue.
- Dashboard cards answer: Am I safe? Am I connected? Can I trade? What needs attention? What happened recently?
- Step-based Trade Ticket workflow with preview/risk/approval/confirmation before live submit is even enabled in the UI.
- Markets, Orders, Positions, Audit, and Emergency sections now use explicit refresh/action buttons instead of noisy automatic fetching.
- Raw API payloads are collapsed behind details panels.
- Settings are grouped by operator task with secret masking and validation-only JSON endpoint.
- Markdown audit export added at `/api/v2/live/audit.md`.
- Task-based docs are reachable inside the console through `/v2-live/docs` and `/docs/{file}`.

## Safety preserved

- Backend remains the source of truth for risk, approval, confirmation, kill-switch, read-only, submit, cancel, and adapter gates.
- Live submit remains default-off and fail-closed.
- No real orders are placed during tests or startup.
- Secrets are still masked/redacted in UI, API, and audit output.

## Migration from v2.0.0-real

Existing v2.0 environment variables and local runtime data remain compatible. The primary user-facing change is navigation and presentation. Existing `/v2-live/market-data` still works; `/v2-live/markets` is added as the cleaner canonical route.
