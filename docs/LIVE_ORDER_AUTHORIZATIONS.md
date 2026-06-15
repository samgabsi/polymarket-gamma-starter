# Live Operator Authorization Ledger (v0.5.11-real)

`v0.5.11-real` adds a local authorization ledger for staged live-readiness work. It lets an operator record an explicit `authorize`, `reject`, or `defer` decision against a saved live-order intent preflight snapshot.

This feature is intentionally documentation-only. It does not sign messages, place orders, cancel orders, derive credentials, touch wallets, automate trading, or override any paper preflight, approval, risk, or audit control.

## Workflow

1. Populate live config fields locally through `.env`; values remain redacted in app reports.
2. Record a live order intent preview with `/live-order-intents` or `--record-live-order-intent`.
3. Review the intent through `/live-order-intent-preflight` or `--live-order-intent-preflight`.
4. Record an authorization decision through `/live-order-authorizations` or `--record-live-order-authorization <intent_id>`.

Only preflight states `ready_for_operator_authorization` and `ready_with_warnings` can produce an authorization snapshot. Other states are recorded as `blocked_by_preflight` unless the operator records `reject` or `defer`.

## UI

Open:

```bash
/live-order-authorizations
```

The page shows current preflight rows and saved authorization snapshots. Each saved record includes an authorization hash over the intent/preflight fields and decision metadata so the reviewed snapshot can be identified later.

## API

```http
GET  /api/live/order-intents/authorizations
GET  /api/live/order-intents/authorizations.csv
GET  /api/live/order-intents/authorizations/{authorization_id}
POST /api/live/order-intents/{intent_id}/authorization?decision=authorize&acknowledged=true
```

Supported decisions:

- `authorize`
- `reject`
- `defer`

Supported authorization statuses:

- `authorized_dry_run`
- `authorized_with_warnings`
- `rejected`
- `deferred`
- `blocked_by_preflight`
- `invalid`

## CLI

```bash
python3 -m app.cli --live-order-authorizations --json
python3 -m app.cli --record-live-order-authorization loi_example --live-authorization-decision authorize --live-authorization-ack --live-intent-operator local --json
python3 -m app.cli --live-order-authorization-detail loa_example --json
python3 -m app.cli --export-live-order-authorizations live_order_authorizations.csv
```

Useful filters:

```bash
python3 -m app.cli --live-order-authorizations --live-authorization-status authorized_dry_run --json
python3 -m app.cli --live-order-authorizations --live-authorization-decision-filter reject --json
python3 -m app.cli --live-order-authorizations --live-authorization-intent-id loi_example --json
```

## Audit and alerts

Saved authorization records appear in the unified audit ledger under category `live_order_authorization`. Dashboard and operator alerts surface blocked, authorized, and deferred authorization records.

## Safety boundary

`authorization_effective=true` means only that a local operator authorization snapshot was recorded for future staged review. It does not mean a live order is approved for this build, executable, submitted, acknowledged by Polymarket, or safe to trade.
