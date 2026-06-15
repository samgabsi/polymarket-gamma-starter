# Paper Ops Closeout Signoffs

Version: v0.5.4-real

Paper Ops Closeout Signoffs are explicit local operator records for the end-of-shift closeout workflow. A signoff snapshots the current Paper Ops Closeout board after human review so an operator can preserve what was completed, handed off, skipped, or blocked.

## Boundaries

- Local paper-workflow record only.
- Does not close handoffs, escalations, tickets, approvals, positions, settlements, or trades.
- Does not place live orders, connect wallets, sign messages, or provide investment advice.
- Does not bypass preflight, approval, risk-budget, audit, handoff, escalation, or review controls.

## UI

- `/paper-ops-closeout-signoffs` lists saved signoffs, shows the current recommended signoff status, and provides the explicit signoff form.
- `/paper-ops-closeout` links to the signoff page after the read-only closeout checklist has been reviewed.

## API

```http
GET  /api/paper/ops-closeout/signoffs
GET  /api/paper/ops-closeout/signoffs/{signoff_id}
GET  /api/paper/ops-closeout/signoffs.csv
POST /api/paper/ops-closeout/signoffs
```

Create parameters are query parameters for the API:

- `status`: optional `completed`, `handed_off`, `needs_followup`, `blocked`, or `skipped`. If omitted, the app derives a conservative status from the current closeout summary.
- `operator`: local operator label.
- `note`: operator note.
- `limit`: number of current closeout rows to snapshot.
- `source`, `item_status`, `market_id`, `handoff_required`: optional closeout filters.

## CLI

```bash
python -m app.cli --paper-ops-closeout-signoffs
python -m app.cli --record-ops-closeout-signoff --ops-closeout-signoff-status handed_off --note "Handoff recorded separately"
python -m app.cli --ops-closeout-signoff-detail pocs_...
python -m app.cli --export-ops-closeout-signoffs paper_ops_closeout_signoffs.csv
```

## Signoff statuses

- `completed`: operator reviewed a clear closeout or completed the closeout review.
- `handed_off`: unresolved items were explicitly handed to the next operator or workflow.
- `needs_followup`: work remains and requires follow-up before the next operator pass.
- `blocked`: closeout is blocked by critical/reappeared/stale work and should not be treated as complete.
- `skipped`: operator explicitly skipped signoff recording or closeout completion for a documented reason.

## Audit

Saved signoffs are added to the unified paper audit ledger with category `ops_closeout_signoff` and event type `OPS_CLOSEOUT_SIGNOFF`.
