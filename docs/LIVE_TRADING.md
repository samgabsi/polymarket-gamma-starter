# v1.4.0 UI Safety Update

The mobile UI refresh adds clearer presentation and a global safety banner, but it does not change or bypass backend safety gates. Live trading is dangerous and remains disabled by default.

# Live Trading

Version: 1.0.0-real

Live trading is dangerous. This software is not financial advice. Operators are responsible for credentials, funding, token allowances, risk limits, and every real-money outcome.

## v1.0.0 posture

`v1.0.0-real` implements manual live submit/cancel **inside the CLOB adapter boundary**. It remains fail-closed by default:

- live mode is disabled by default,
- real network is disabled by default,
- submit/cancel are disabled by default,
- the kill switch blocks by default,
- max notional limits default to zero,
- allowlists default empty,
- autonomous live trading remains blocked,
- automated tests do not submit or cancel live orders.

## Manual submit gates

A real submit can be attempted only from the manual record path with `adapter_mode=real_live` and only after all source records and configuration gates pass. Required gates include live mode, real-network permission, submit flags, kill switch off, current SDK dependency, credentials, adapter request, execution packet, authorization, dry-run receipt, market/risk checks, allowlist, and matching final confirmation phrase.

## Manual cancel gates

A real cancel can be attempted only from the manual cancel record path with `adapter_mode=real_live` and an order id. Required gates include live mode, real-network permission, cancel flags, kill switch off, credentials, current SDK dependency, human reason, and matching final confirmation phrase.

## Autonomous trading

Autonomous live trading is not enabled in this milestone. Autonomous paths remain dry-run/fake-adapter oriented and deterministic-signal based. No autonomous background loop starts automatically.

## Validation

Normal validation is no-network and no-real-money. Optional real-live smoke tests must require explicit environment confirmations and are not run by default.


## v1.1.0 live operations hardening

This release adds the live readiness checklist and operator runbook. The checklist is diagnostic only and does not enable live flags. Automated validation remains no-network/no-real-money.
