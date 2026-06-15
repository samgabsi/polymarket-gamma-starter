# v1.4.0 Mobile Data Lab Update

Data Lab pages are now easier to use on mobile. Data ingestion is local-first, network-disabled by default, and does not place trades or cancel orders.

# Data Ingestion

v1.3.0 adds a local-first Data Ingestion layer for Training Lab datasets.

Safety posture:

- Data ingestion does not place trades.
- Data ingestion does not cancel orders.
- Network ingestion is disabled by default.
- Ingestion schedulers are disabled by default.
- Generated raw data, normalized data, labels, manifests, and datasets are runtime state and are excluded from release ZIPs.

Main surfaces:

- UI: `/data`, `/data/sources`, `/data/ingestion`, `/data/snapshots`, `/data/normalized`, `/data/labels`
- API: `/api/data/status`, `/api/data/sources`, `/api/data/ingestion/preview`, `/api/data/ingestion/run`
- CLI: `--data-status`, `--data-sources`, `--preview-data-ingestion`, `--run-data-ingestion`

Network sources are metadata-only by default. They require explicit future opt-in and should be used only for safe read-only collection.

## v1.5.0 Internet ingestion and host training jobs

This release adds an operator-controlled internet ingestion and host training job runner milestone. Internet ingestion is disabled by default, requires approved sources and allowlisted domains, and is limited to public/read-only data fetches. Data ingestion does not trade. Host training jobs are disabled by default, use approved internal job types only, and write artifacts to runtime data directories that are excluded from release ZIPs. Training outputs remain manual-review-only and do not directly live-trade.
