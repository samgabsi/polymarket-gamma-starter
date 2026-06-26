# Operator Notes - v4.13.0-real

## Completed Workflow

The completed workflow is Cross-Market Arbitrage scan recording and readiness truthfulness.

Operators can now:

- Open `/v3/arbitrage`.
- See whether scan data is sample, live, cached, stale, or unavailable.
- See scanner, venue, Kalshi, and feature-readiness implications.
- Record the current scan snapshot through a visible POST action.
- Receive feedback after recording.
- Inspect local scan and audit JSONL rows.
- Submit candidate review decisions with data-state metadata preserved in the audit row.

## Operator Boundary

Recorded scan snapshots are local evidence, not execution instructions. Review decisions are local workflow state, not trade approval. Live execution remains governed by separate fail-closed backend gates.

