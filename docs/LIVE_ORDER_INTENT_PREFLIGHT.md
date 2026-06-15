# Live Order Intent Preflight (v0.5.7-real)

`v0.5.7-real` adds a read-only live-intent preflight review layer for staged live-trading readiness. It reconciles saved live-order intent previews against the local paper workflow before any future execution adapter can be considered.

## What it checks

For each saved live-order intent, the preflight review verifies:

- The intent preview itself is valid and currently `ready_for_manual_review`.
- `execution_allowed` remains `false`.
- A concrete CLOB `token_id` is present.
- Runtime live guards remain safe: read-only, dry-run, manual approval, pre-trade checks, and audit required.
- No execution adapter, order-placement path, cancellation path, or autonomous-trading path is enabled.
- The intent is explicitly bound to a local paper trade ticket through `source_ticket_id`.
- The intent is explicitly bound to a local paper approval through `source_approval_id`.
- The source ticket and approval match the intent market/outcome and the intent notional does not exceed the approved paper stake.
- The current paper preflight can still be rebuilt and approved.

## Review states

- `ready_for_operator_authorization` — local bindings and guards pass. This still does **not** allow execution in this build.
- `ready_with_warnings` — local bindings pass, but warnings such as price drift or prior approval warnings need review.
- `needs_paper_binding` — the intent is missing an explicit paper ticket or explicit paper approval reference, or the referenced record cannot be found.
- `blocked_by_live_guard` — live readiness guards or the saved intent's guard state block the review.
- `blocked` — non-guard governance/risk/preflight blockers exist.
- `invalid` — the saved intent has invalid required fields.

## UI

Open:

```text
/live-order-intent-preflight
```

Useful API routes:

```text
GET /api/live/order-intents/preflight
GET /api/live/order-intents/preflight.csv
GET /api/live/order-intents/{intent_id}/preflight
```

## CLI

```bash
python3 -m app.cli --live-order-intent-preflight --json
python3 -m app.cli --live-order-intent-preflight --live-preflight-state needs_paper_binding
python3 -m app.cli --live-order-intent-preflight-detail loi_example123 --json
python3 -m app.cli --export-live-order-intent-preflight live_order_intent_preflight.csv
```

Existing live-intent filters can be reused:

```bash
python3 -m app.cli --live-order-intent-preflight --live-intent-market <market_id> --live-intent-operator <operator>
```

## Safety boundary

This feature is intentionally non-executing. It does not derive credentials, validate private keys, sign messages, post orders, cancel orders, connect wallets, alter paper tickets/approvals, or automate trading. A `ready_*` state means the local governance record is ready for human review in a future execution-capable build; it is not an exchange order and not authorization to trade.

## v0.5.11 follow-on: operator authorization snapshots

`v0.5.11-real` adds a separate local authorization ledger for saved preflight rows. Use `/live-order-authorizations` or `python3 -m app.cli --live-order-authorizations --json` to record explicit `authorize`, `reject`, or `defer` snapshots for a preflighted intent.

These authorization records remain documentation-only. They do not submit orders or enable live execution.
