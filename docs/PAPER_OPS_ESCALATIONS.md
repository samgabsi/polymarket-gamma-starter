# Paper Ops Escalation Register

Version: v0.5.2-real

The Paper Ops Escalation Register is a local human-in-the-loop follow-up log for unresolved paper-operations workload. It is designed to sit after the daily briefing, handoffs, reconciliation, and aging review.

It does not execute trades, approve tickets, settle positions, connect wallets, or provide financial advice. It only records operator follow-up state for stale, blocked, repeated, or follow-up paper workflow items.

## UI

```text
/paper-ops-escalations
```

The page shows:

- saved escalation records
- open/resolved/dismissed status counts
- severity counts
- current escalation candidates from the aging review
- per-record update form for status, severity, owner, and note

## API

```text
GET  /api/paper/ops-escalations
GET  /api/paper/ops-escalations/{escalation_id}
GET  /api/paper/ops-escalations.csv
POST /api/paper/ops-escalations
POST /api/paper/ops-escalations/{escalation_id}
```

## CLI

```bash
python3 -m app.cli --paper-ops-escalations
python3 -m app.cli --paper-ops-escalations --ops-escalation-status-filter open
python3 -m app.cli --create-ops-escalation <aging_item_id> --note "needs operator review"
python3 -m app.cli --update-ops-escalation <escalation_id> --ops-escalation-status resolved --note "closed after review"
python3 -m app.cli --ops-escalation-detail <escalation_id>
python3 -m app.cli --export-ops-escalations paper_ops_escalations.csv
```

## Statuses

- `open`
- `investigating`
- `waiting`
- `resolved`
- `dismissed`

## Severities

- `critical`
- `high`
- `medium`
- `low`
- `info`

When creating a record from an aging item, the register maps aging severity to escalation severity:

- `critical` -> `critical`
- `stale` / `followup` -> `high`
- `repeat` / `unknown_age` -> `medium`
- `fresh` -> `low`

## Audit integration

Saved escalation records appear in the paper audit ledger under:

```text
operator_escalation
```

This gives the operator a durable trail showing when a stale workflow item was escalated, who owned it, and how it was resolved or dismissed.


## Escalation review

v0.5.2 adds a read-only reconciliation view for saved escalation records:

```text
/paper-ops-escalation-review
GET /api/paper/ops-escalations/review
GET /api/paper/ops-escalations/{escalation_id}/review
GET /api/paper/ops-escalations/review.csv
```

This review compares saved escalation records to the current aging board and classifies them as `active_followup`, `verify_resolution`, `deescalation_candidate`, `closed_but_reappeared`, or `closed_record`. It does not auto-close or auto-reopen escalation records.
