# Operator Notes v4.17.0-real

Automated paper trading is available as a paper-only workflow.

## Enable paper automation

```bash
PAPER_TRADING_ENABLED=true \
PAPER_TRADING_AUTOMATION_ENABLED=true \
PAPER_TRADING_STARTING_BALANCE=1000 \
PAPER_TRADING_MAX_ORDER_NOTIONAL=25 \
PAPER_TRADING_MIN_EDGE_PCT=2.0 \
PAPER_TRADING_MIN_CONFIDENCE=0.70 \
python run.py
```

Then open `/v3/paper-trading`.

## What happens during run-once

The runner loads candidates, applies edge/confidence/freshness/spread/slippage/mismatch/risk-budget checks, simulates accepted fills, updates the paper account/positions, and writes decisions/audit rows.

## What does not happen

The runner does not submit orders, cancel orders, sign transactions, arm live trading, or bypass kill switches.

## Paper versus dry-run versus live

- Paper trading: local ledger and simulated P/L.
- Dry-run: execution-path rehearsal without live mutation.
- Review-only: operator metadata and decisions only.
- Live trading: separately gated real execution path. v4.17 does not enable it.
