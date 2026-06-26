# Automated Paper Trading Guide v4.17.0-real

## Architecture

The v4.17 paper trading subsystem consists of:

- paper config reader
- paper strategy runner
- paper risk checks
- simulated paper broker
- local paper account ledger
- local orders/fills/positions/decisions/runs/audit files
- `/v3/paper-trading` UI
- `/api/v3/paper/*` API routes

Runtime files are written under `data/paper_automation/` and are excluded from release ZIPs.

## Candidate decisions

A candidate can become a paper trade only if it passes:

- minimum edge
- minimum confidence
- data freshness
- max spread
- max slippage
- semantic/resolution mismatch checks
- per-order notional
- market exposure
- daily notional
- open position count
- per-run and per-day trade counts

Rejected candidates are still recorded as decisions.

## Simulated fills

The conservative fill model uses ask/top-of-book-like prices when present and applies configured slippage and fees. Positions and P/L are local estimates only.

## API safety flags

Every API envelope exposes paper/live safety fields. Any response from paper automation that claims live execution was used is a bug.
