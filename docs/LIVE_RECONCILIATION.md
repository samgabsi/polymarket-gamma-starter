# Live Reconciliation

Version: 1.0.0-real

Reconciliation is read-only. It compares local live order ledger events against local state and, when a future operator explicitly enables safe remote checks, adapter order/open-order status. Reconciliation never submits, cancels, or mutates exchange state.

Without credentials or network enablement it degrades to local-only status.


## v1.1.0 reconciliation hardening

Reconciliation now reports severity, suggested operator action, lifecycle status, next recommended check, and whether remote network was attempted. Reconciliation may suggest actions but must not submit or cancel.
