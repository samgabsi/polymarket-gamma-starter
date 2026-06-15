# Internet Data Ingestion

v1.5.0 adds controlled internet data ingestion for public/read-only research data.

Safety defaults:

- `POLYMARKET_DATA_ALLOW_INTERNET=false`
- allowed domains are required
- network ingestion is explicit, never automatic
- ingestion does not place, sign, submit, or cancel orders
- ingestion never enables autonomous trading
- raw responses and snapshots are runtime data and are excluded from release ZIPs

A real internet ingestion run requires a registered source, enabled source metadata, an allowlisted domain, safe GET-only endpoint shape, configured timeout/rate limits, and the operator confirmation phrase.

## v1.6.0 scoped/category workflow note

For medium-large local training, prefer scoped/category backfills over broad ingest-everything jobs. Use `/data/scopes`, `/data/backfills`, and `/training/category-datasets` to cap records, preview pagination/storage/RAM risk, and keep dataset builds reproducible. Network ingestion remains disabled by default and no data/training workflow trades.
