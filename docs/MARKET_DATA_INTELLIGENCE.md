# Market Data Intelligence

Version: v0.9.0-real

Market Data Intelligence adds local public/fixture order-book snapshot records. It is a read-only data layer separate from credentials, wallets, signing, live submission, cancellation, and autonomous execution.

## What It Stores

Snapshots are saved in local JSON under `data/market_data/market_snapshots.json` when an operator records them. Release ZIPs must not include generated snapshot data.

Snapshot records include:

- market and token identifiers,
- active/closed/accepting-orders flags,
- best bid and best ask,
- midpoint and spread bps,
- top-of-book depth,
- 1% and 5% depth bands,
- total bid/ask depth,
- warnings and blockers,
- deterministic public-field hash.

Snapshots do not store API keys, CLOB credentials, wallet keys, private user data, or signed payloads.

## Sources

Supported in v0.9.0:

- local fixture JSON,
- manually supplied JSON through API/CLI/UI.

Exposed but not implemented as successful network fetch in v0.9.0:

- optional public fetch boundary.

Public fetch remains disabled by default through `POLYMARKET_MARKET_DATA_PUBLIC_FETCH_ENABLED=false`. The fetch preview/record endpoints report `public_fetch_disabled` or `public_fetch_unimplemented` and do not fake network success.

## Operator Use

Use `/market-data` to inspect snapshot freshness, spread, depth, and market status. Use snapshots as inputs to execution-quality simulation before relying on paper or live-readiness review state.

Market data can be stale, incomplete, or wrong. Operators must manually review all outputs.

## Safety

This layer never submits orders, cancels orders, signs messages, touches wallets, bypasses approvals, or automates trading.
