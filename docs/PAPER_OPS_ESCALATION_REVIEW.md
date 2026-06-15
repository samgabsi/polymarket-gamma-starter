# Paper Ops Escalation Review

Version: v0.5.2-real

The Paper Ops Escalation Review is a read-only reconciliation layer for saved Paper Ops Escalation Register records. It compares each saved escalation to the current Paper Ops Aging Review so an operator can decide whether follow-up is still active, should be verified as resolved, can be de-escalated, or needs to be reopened.

It does not mutate escalation records, approve or reject tickets, execute simulated trades, settle positions, connect wallets, sign orders, or provide investment advice.

## UI

```text
/paper-ops-escalation-review
```

The page shows:

- saved escalation records reconciled against the current aging board
- review-required counts
- active follow-up counts
- verify-resolution rows where the original aging item is no longer visible
- de-escalation candidates where the current item is visible but no longer critical/stale/follow-up/repeated
- closed escalations whose source aging item reappeared
- a detail view that links back to the editable escalation record

## API

```text
GET /api/paper/ops-escalations/review
GET /api/paper/ops-escalations/{escalation_id}/review
GET /api/paper/ops-escalations/review.csv
```

## CLI

```bash
python3 -m app.cli --paper-ops-escalation-review
python3 -m app.cli --paper-ops-escalation-review --ops-escalation-review-state active_followup
python3 -m app.cli --paper-ops-escalation-review --ops-escalation-owner-filter local
python3 -m app.cli --ops-escalation-review-detail <escalation_id>
python3 -m app.cli --export-ops-escalation-review paper_ops_escalation_review.csv
```

## Review states

- `active_followup` — the escalation is open/investigating/waiting and the source aging item is still actionable.
- `verify_resolution` — the escalation is still open, but the source aging item is no longer visible in the current aging board.
- `deescalation_candidate` — the source item is still visible, but its current aging severity has softened below the actionable aging severities.
- `closed_but_reappeared` — the saved escalation is resolved/dismissed, but the current aging board shows the source item as actionable again.
- `closed_record` — the escalation is resolved/dismissed and no actionable aging item is currently visible.

## Operator guardrail

Use this report as a reconciliation checklist before changing escalation status manually in the escalation register. The review intentionally does not auto-close or auto-reopen anything because those are human-in-the-loop workflow decisions.
