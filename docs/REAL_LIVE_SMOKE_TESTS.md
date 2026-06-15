# Real Live Smoke Tests

Real-live smoke tests are opt-in only and may trade real money if executed incorrectly. Normal validation must never run them.

## Required guards

All real-live smoke tests require local operator review and all of the following environment controls:

- `POLYMARKET_RUN_REAL_LIVE_TESTS=true`
- `POLYMARKET_REAL_LIVE_TEST_CONFIRMATION=I_UNDERSTAND_THIS_MAY_TRADE_REAL_MONEY`
- `POLYMARKET_LIVE_MODE=true`
- `POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true`
- operation-specific submit/cancel confirmation
- explicit market allowlist
- explicit token allowlist
- positive but tiny max order notional
- kill switch deliberately off for the live window
- final operator confirmation phrase

## Recommended order

1. Offline adapter verification.
2. Dependency and credential presence checks.
3. Fake-local submit/cancel test.
4. Read-only reconciliation.
5. Optional read-only network check.
6. Manual live submit with minimum notional.
7. Manual live cancel only when a known exchange order ID exists.
8. Restore kill switch and disable live flags.

This release provides verification and runbook surfaces. It does not run real smoke tests during automated validation.
