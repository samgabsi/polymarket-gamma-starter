# Stub Burn-Down Map v4.17.0-real

v4.17 adds paper trading rows to the feature readiness and stub burn-down registries.

## Completed in this pass

- `paper_trading.automation_loop`
- `paper_trading.engine`
- `paper_trading.automation`
- `paper_trading.scheduler`
- `paper_trading.broker_ledger_risk`

## Status semantics

- `working`: paper gates are enabled and the surface can run or report data.
- `disabled`: paper trading or automation gates are off.
- `config_required`: paper engine is enabled but automation is not enabled.

## Remaining future work

- Harden optional background scheduling.
- Connect richer candidate feeds from AI odds/arbitrage/review queue without relying on sample fixtures.
- Add more advanced paper exit/settlement simulation.
- Compare paper decision outcomes over time for calibration.
