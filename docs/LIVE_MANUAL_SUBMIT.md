# Live Manual Submit

Version: v0.9.0-real

Manual submit attempts start from a saved live adapter request validation record.

Required gates:

- Kill switch clear.
- `POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=true`.
- `POLYMARKET_LIVE_ENABLE_SUBMIT=true`.
- `POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH=true`.
- Adapter request status is `adapter_request_ready` or `adapter_request_ready_with_warnings`.
- Bound unsigned execution packet still exists and hash matches.
- Bound operator authorization is acknowledged, authorized, current, and hash-matched.
- Bound offline dry-run receipt is validated, current, hash-matched, no-network, and unsigned.
- `LIVE_MAX_ORDER_NOTIONAL` and `LIVE_ALLOWED_MARKET_IDS` pass.
- `POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE` is configured and the operator provides the exact phrase for the attempt.

Adapter modes:

- `blocked`: records a safe blocked attempt.
- `fake_local`: can create a deterministic fake-local receipt when all gates pass and `POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED=true`.
- `real_live`: calls the SDK submit path only after every explicit live/submit gate passes; otherwise it records `submit_blocked`.

Fake-local submit receipts are not exchange orders and must not be treated as exchange acknowledgements.

CLI:

```text
python3 -m app.cli --live-execution-control-readiness --json
python3 -m app.cli --preview-live-manual-submit --adapter-request-id <request_id> --adapter-mode fake_local
python3 -m app.cli --record-live-manual-submit --adapter-request-id <request_id> --adapter-mode fake_local --final-confirmation "<local phrase>"
python3 -m app.cli --live-execution-attempts --json
```
