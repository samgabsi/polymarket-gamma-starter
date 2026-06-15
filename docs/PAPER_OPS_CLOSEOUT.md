# Paper Ops Closeout

Introduced: v0.5.3-real
Package note: v0.5.4-real adds separate closeout signoff records; this checklist remains read-only.

Paper Ops Closeout is a read-only end-of-shift checklist for the local Polymarket paper-ops workflow. It consolidates the current Daily Paper Ops Briefing, Paper Ops Aging Review, Handoff Reconciliation, Escalation Register, and Escalation Review so an operator can see what must be resolved, explicitly handed off, or summarized before ending an operator pass.

It does not record handoffs or signoffs by itself, close escalation records, approve or reject tickets, execute simulated trades, settle positions, connect wallets, sign messages, place live orders, or provide investment advice.

## UI

```text
/paper-ops-closeout
```

The page shows:

- a closeout status of `blocked`, `attention`, or `clear`
- prioritized checklist rows from briefing, aging, handoff reconciliation, escalations, escalation candidates, and escalation review
- whether each row requires handoff/follow-up
- a closure gate for each row
- component summaries from the underlying paper-ops reports
- links back to the workflow page where the operator can review or manually act
- a link to `/paper-ops-closeout-signoffs` for explicit local signoff snapshots after review

## API

```text
GET /api/paper/ops-closeout
GET /api/paper/ops-closeout.csv
```

Supported filters:

- `limit`
- `source`
- `status`
- `market_id`
- `handoff_required`

Example:

```bash
curl 'http://127.0.0.1:8000/api/paper/ops-closeout?handoff_required=true'
```

## CLI

```bash
python3 -m app.cli --paper-ops-closeout
python3 -m app.cli --paper-ops-closeout --ops-closeout-handoff-required
python3 -m app.cli --paper-ops-closeout --ops-closeout-source escalation_review
python3 -m app.cli --paper-ops-closeout --ops-closeout-status active_followup
python3 -m app.cli --export-ops-closeout paper_ops_closeout.csv
```

## Closeout statuses

- `blocked` — blocked briefing work, critical aging, or closed escalation records that reappeared need explicit review before closeout.
- `attention` — unresolved but less severe follow-up exists and should be handed off or checkpointed.
- `clear` — no high-priority unresolved closeout rows matched the current filters.

## Operator guardrail

Use closeout as a read-only checklist. It intentionally does not auto-record a handoff, auto-resolve an escalation, or mutate any trade/review state because those remain human-in-the-loop workflow decisions.
