# Order Lifecycle Guide — v2.1.0-real

The v2 order lifecycle is:

```text
Market Discovery / Gamma Data
  -> Market Selection
  -> Order Book / Pricing
  -> Trade Ticket Draft
  -> Risk Pre-Check
  -> Operator Preview
  -> Human Approval
  -> Signed Order Creation
  -> Order Submission
  -> Order Status Monitor
  -> Fill / Cancel / Error Handling
  -> Audit Ledger + Position Update
```

## Draft and preview

`POST /api/v2/live/ticket/preview` accepts a JSON ticket, computes notional/max-loss estimates, runs risk checks, and writes a preview audit record. It does not sign or submit.

## Approval

For live submission, include:

```json
{
  "human_approval": true,
  "acknowledge_warnings": true,
  "confirmation_phrase": "LIVE ORDER APPROVED"
}
```

The confirmation phrase must exactly match the configured phrase.

## Submit

`POST /api/v2/live/order/submit` re-builds the ticket, re-runs risk checks, validates confirmation, then calls the isolated CLOB adapter. The adapter is responsible for SDK initialization, order creation/signing, post-order submission, response parsing, and secret redaction.

## Monitor and reconcile

Use:

- `GET /api/v2/live/orders/open`
- `GET /api/v2/live/positions`
- `POST /api/v2/live/reconcile`
- `/v2-live/audit`

When remote state is unavailable, the app reports unknown/unavailable instead of inventing fills, balances, or P&L.

## Cancel

`POST /api/v2/live/order/cancel` requires an order id, cancel reason, cancel gates, real-network permission, and typed confirmation. Every cancel attempt is audited.
