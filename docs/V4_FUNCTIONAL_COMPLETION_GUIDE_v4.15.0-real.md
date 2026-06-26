# Functional Completion Guide - v4.15.0-real

v4.15 continues the visible-control rule: every visible action should work, navigate to a real route, persist local state, export data, or clearly explain why it is disabled/config-required/scaffolded.

## Completed in v4.15

The Review Queue page now has a complete local operator workflow:

1. Open `/review-queue`.
2. Review data state and review-only/live-disabled posture.
3. Use Mark reviewed, Watchlist, Send to paper review, or Dismiss on a queue row.
4. Receive redirect feedback.
5. Refresh the page or call `/api/review-queue` to confirm persisted status.
6. Inspect `/api/review-queue/actions` for local audit rows.

## Remaining rule

Future iterations should continue selecting one high-value visible workflow, eliminate silent no-ops inside that workflow, add persistence/audit where appropriate, and update readiness/docs/tests.
