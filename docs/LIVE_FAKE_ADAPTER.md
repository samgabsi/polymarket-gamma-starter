# Live Fake Adapter

Version: v0.9.0-real

The fake adapter is a deterministic local execution-boundary simulator. It is not paper trading and it is not Polymarket trading.

Properties:

- no network
- no wallet
- no signing
- no external SDK import
- no exchange acknowledgement
- deterministic fake submit and cancel receipt IDs
- fully recorded in the execution attempt ledger

Enable it only for local validation:

```text
POLYMARKET_LIVE_ENABLE_SUBMIT=true
POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=true
POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED=true
POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE=<local phrase>
```

For fake cancel simulation:

```text
POLYMARKET_LIVE_ENABLE_CANCEL=true
POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED=true
```

Fake receipt fields include:

- `fake_submit_receipt_id`
- `fake_cancel_receipt_id`
- `fake_order_id`
- `adapter_mode=fake_local`
- `network_attempted=false`
- `signed_payload_present=false`
- `exchange_acknowledgement_present=false`
- `simulated_status`
- `simulated_reason`

Real adapter integration remains a future task. The old `py-clob-client` package should not be assumed safe or current without reviewing official Polymarket guidance; the control plane keeps the app behind an internal adapter boundary for that reason.
