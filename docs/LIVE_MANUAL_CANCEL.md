# Live Manual Cancel

Version: v0.9.0-real

Manual cancel records operator attempts to cross a cancellation boundary. Real live cancellation is implemented only through the guarded CLOB adapter boundary and remains disabled by default.

Required gates:

- Kill switch clear.
- `POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED=true`.
- `POLYMARKET_LIVE_ENABLE_CANCEL=true`.
- `POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE` is configured and matched.
- A target original attempt ID or fake-local order ID is supplied.
- A cancel reason is supplied.
- For `fake_local`, the target must be a fake-local submit attempt and `POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED=true`.

Adapter modes:

- `blocked`: records a disabled cancel attempt.
- `fake_local`: can create a deterministic fake-local cancel receipt.
- `real_live`: calls the SDK cancel method only after every explicit live/cancel gate passes; otherwise it records `cancel_blocked`.

CLI:

```text
python3 -m app.cli --preview-live-manual-cancel --original-attempt-id <attempt_id> --adapter-mode fake_local --cancel-reason "operator test"
python3 -m app.cli --record-live-manual-cancel --original-attempt-id <attempt_id> --adapter-mode fake_local --final-confirmation "<local phrase>" --cancel-reason "operator test"
```
