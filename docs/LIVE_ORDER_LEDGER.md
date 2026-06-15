# Live Order Ledger

Version: 1.0.0-real

The live order ledger derives local audit events from manual execution attempts. It records blocked attempts, fake-local events, and real adapter results when they occur. It stores response hashes and redacted summaries, not private keys or raw secrets.

Real submit/cancel events include `network_attempted`, `signed_payload_present`, `exchange_acknowledgement_present`, `exchange_order_id` where available, and redacted response metadata. Fake-local receipts remain simulations and are not exchange acknowledgements.


## v1.1.0 lifecycle model

Live order events now expose a lifecycle status such as preview_blocked, preview_ready, submit_blocked, submit_attempted, submit_succeeded, submit_failed, open, partially_filled, filled, cancel_blocked, cancel_attempted, cancel_succeeded, cancel_failed, cancelled, expired, unknown, or reconciliation_unavailable.
