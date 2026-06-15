# Troubleshooting Guide — v2.1.0-real

## Readiness says credentials are missing

Confirm that credentials are in local `.env` or process environment, not in `.env.example` or the release ZIP. Use `/settings/configuration` to verify presence; values remain masked.

## Wallet address is not derivable

Set `POLYMARKET_WALLET_ADDRESS` explicitly, or install optional dependencies from `requirements-live-optional.txt` so the app can derive the address from a private key for readiness display.

## SDK unavailable

Install optional dependencies in a dedicated venv after reviewing current official Polymarket docs:

```bash
pip install -r requirements-live-optional.txt
```

The app will still run without optional live dependencies, but live submit/cancel will remain blocked.

## Order submit is blocked by risk

Open `/v2-live/risk` and inspect `POST /api/v2/live/ticket/preview`. Typical causes are zero risk caps, kill switch active, read-only mode, missing approval, wrong trading mode, missing allowlist entry, or submit gates disabled.

## Market data fails

Check `GAMMA_BASE_URL`, `CLOB_BASE_URL`, network connectivity, request timeouts, and whether Polymarket API availability or local firewall/DNS is affecting the request.

## Positions are unavailable

Positions require a configured wallet address and read-only network permission:

```env
POLYMARKET_LIVE_NETWORK_READONLY=true
POLYMARKET_LIVE_ALLOW_REAL_NETWORK=true
POLYMARKET_WALLET_ADDRESS=0x...
```

If the Data API does not return a field needed for P&L, the app shows unknown/unavailable instead of inventing a value.

## Reconciliation flags local-only records

A local-only record can mean the order was blocked before submission, the exchange did not acknowledge it, the order is no longer open, remote open-order reads are disabled, or API credentials are missing. Review the corresponding audit record details.

## v2.1.0 UI troubleshooting

- If a Live v2 panel looks empty, use its explicit Refresh/Search/Preview button. v2.1 avoids noisy automatic fetching.
- If a button is disabled, read the nearby status badge and run `/v2-live/risk` to see backend blockers.
- If raw API output is needed, expand the details panel in the result area or use the matching `/api/v2/live/*` route.
- If settings look wrong, open `/v2-live/settings` for grouped review and `/settings/configuration` for the audited configuration editor.
