# UI/UX Guide — v2.1.0-real

The v2.1 interface is designed as a calm live-operator console. It uses progressive disclosure: summaries first, raw payloads only when expanded.

## Navigation

The Live v2 console is organized by task:

- Dashboard — current posture, blockers, recent activity, and next action.
- Markets — market search and order-book inspection.
- Trade Ticket — step-by-step ticket preview, risk, approval, and submit/rehearse flow.
- Orders — open orders and targeted cancellation workflow.
- Positions — read-only balances/positions and reconciliation.
- Risk — readiness and blocking dependencies.
- Audit — human-readable ledger plus JSON, CSV, and Markdown export.
- Settings — grouped configuration map and validation-only endpoint.
- Emergency — kill-switch/read-only/disable-orders/cancel-preview actions.
- Docs — task-based guide links.

## Persistent status bar

Every Live v2 page shows:

- Version
- Mode
- Live armed state
- Read-only state
- Kill-switch state
- Readiness
- Gamma/CLOB posture
- Refresh timestamp

This makes paper/live/read-only/armed states visible without scrolling.

## Performance choices

- No large live panels auto-fetch on page load.
- Buttons fetch orders, positions, reconciliation, and order books only when requested.
- Client-side caching avoids duplicate GET requests for a short window.
- Slow actions show loading/error output in their own panel instead of blocking the whole UI.
- Raw payloads are collapsed by default.

## Safety UX

Live actions still require backend gates. The UI adds clarity but does not weaken security. Submit stays locked until preview passes, and backend submit still enforces risk checks, approval, warning acknowledgement, typed confirmation, live armed mode, kill switch off, read-only false, and submit gates enabled.
