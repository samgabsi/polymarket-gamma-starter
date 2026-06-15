# Live Execution Packets (v0.5.11-real)

Live Execution Packets are deterministic, unsigned, local-only records created after a saved live-order intent has passed staged preflight and has an acknowledged operator authorization snapshot.

They are intended to make the future live-execution boundary auditable before any execution adapter exists. A packet preserves the exact public order-intent fields that would matter to a future adapter, plus the authorization hash, paper-ticket/approval binding, current preflight state, blockers, warnings, and a deterministic packet hash.

## What packets do

- Re-check the current live-intent preflight at packet creation time.
- Require a saved operator authorization with `authorized_dry_run` or `authorized_with_warnings` status.
- Preserve the source authorization ID and authorization hash.
- Preserve paper workflow binding through `source_ticket_id` and `source_approval_id`.
- Export public, unsigned order fields through `wire_order_preview`.
- Record packet rows in the unified audit ledger under `live_execution_packet`.
- Surface ready/blocked packet counts in dashboard/operator alerts.

## What packets do not do

- They do not derive credentials.
- They do not validate private keys.
- They do not sign orders.
- They do not submit orders.
- They do not cancel orders.
- They do not touch wallets.
- They do not call an authenticated Polymarket/CLOB execution adapter.
- They do not automate trading.

`execution_allowed`, `order_submission_enabled`, `order_cancellation_enabled`, `autonomous_trading_enabled`, `signed_payload_present`, and `exchange_acknowledgement` remain false in this build.

## UI

Open:

```text
/live-execution-packets
```

The page lists saved packets and offers a packaging form for acknowledged authorization snapshots. Packaging still produces a local unsigned record only.

## API

```http
GET  /api/live/execution-packets
GET  /api/live/execution-packets/{packet_id}
GET  /api/live/execution-packets.csv
POST /api/live/order-intents/{intent_id}/execution-packet/preview
POST /api/live/order-intents/{intent_id}/execution-packet
```

Common query fields:

- `status`
- `market_id`
- `operator`
- `intent_id`
- `authorization_id`
- `note`

## CLI

```bash
python3 -m app.cli --live-execution-packets --json
python3 -m app.cli --preview-live-execution-packet --live-execution-packet-intent-id loi_example --live-execution-packet-authorization-id loa_example --json
python3 -m app.cli --record-live-execution-packet --live-execution-packet-intent-id loi_example --live-execution-packet-authorization-id loa_example --json
python3 -m app.cli --live-execution-packet-detail lep_example --json
python3 -m app.cli --export-live-execution-packets live_execution_packets.csv
```

## Packet states

- `packet_ready_dry_run`: packageable for offline/future-adapter review with no blockers.
- `packet_ready_with_warnings`: packageable, but warnings must be reviewed before any future execution-capable build.
- `blocked_by_authorization`: missing, mismatched, unacknowledged, rejected/deferred, or otherwise ineffective authorization.
- `blocked_by_preflight`: current preflight is no longer packageable or has drifted into a blocking state.
- `invalid`: missing source intent or malformed input.

## Safety boundary

A ready packet is not an exchange order, not an execution approval, not a signed payload, and not a Polymarket acknowledgement. It is a local review/export artifact for future adapter design.
