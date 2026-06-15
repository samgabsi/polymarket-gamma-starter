# Release Notes — v2.1.0-real

## Summary

`v2.1.0-real` introduces the first full live-trading build: live data discovery, live order-book inspection, trade-ticket preview, strict pre-trade risk checks, human approval, typed confirmation, isolated CLOB submit/cancel adapter calls, open-order/position read paths, reconciliation, emergency controls, and JSONL/CSV audit exports.

## Added

- `app/live_v2.py` live control-plane module.
- `/v2-live` dashboard and subpages.
- `/api/v2/live/*` JSON and CSV endpoints.
- v2 configuration keys in `.env.example` and the GUI configuration schema.
- Optional unified SDK dependency notes in `requirements-live-optional.txt`.
- v2 docs for setup, env vars, risk, order lifecycle, emergency controls, troubleshooting, and release notes.

## Preserved

- v1.9 GUI-first settings/configuration workflow.
- Paper workflow, research, data ingestion, training, audit, and manual control routes.
- Existing isolated live CLOB adapter boundary.
- Fail-closed defaults.

## Known limitations

- Real live submit/cancel requires operator-installed optional dependencies, valid credentials, funding/allowances, Polymarket availability, jurisdiction/account eligibility, and all local gates to pass.
- The old `py-clob-client` path is retained only as a compatibility fallback. Prefer the current official Polymarket unified Python SDK in environments where it is stable and supported.
- P&L is not invented. If Polymarket Data API or account data does not provide reliable fields, the app reports unknown/unavailable.
