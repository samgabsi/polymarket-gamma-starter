# Paper Ops Aging Review

Version: v0.5.0-real

Paper Ops Aging Review is a read-only workflow hygiene layer. It reviews unresolved daily paper ops briefing items and saved operator handoff history to identify work that may be stale, repeated across handoffs, or missing useful source timestamps.

It does not change any trade ticket, approval, preflight, runbook, handoff, position, settlement, paper trade, or live-trading state.

## Browser view

```text
/paper-ops-aging
```

Useful filters:

- `section`: briefing section such as `entry_execution`, `risk_budget`, or `post_trade_review`
- `status`: current briefing status such as `ready`, `action_required`, `blocked`, `review`, or `watch`
- `severity`: `critical`, `stale`, `followup`, `repeat`, `fresh`, or `unknown_age`
- `market_id`: focus on one market
- `min_age_hours`: only show rows at or above a selected age

## API

```http
GET /api/paper/ops-aging
GET /api/paper/ops-aging/{item_id}
GET /api/paper/ops-aging.csv
```

## CLI

```bash
python3 -m app.cli --paper-ops-aging
python3 -m app.cli --paper-ops-aging --ops-aging-severity stale
python3 -m app.cli --paper-ops-aging --ops-aging-min-hours 24
python3 -m app.cli --ops-aging-detail <aging_item_id>
python3 -m app.cli --export-ops-aging paper_ops_aging.csv
```

## Severity model

Default stale thresholds:

| Status | Threshold |
|---|---:|
| `ready` | 12 hours |
| `action_required` | 12 hours |
| `blocked` | 24 hours |
| `review` | 48 hours |
| `watch` | 72 hours |

Severity values:

- `critical`: blocked/stale work is beyond the critical threshold.
- `stale`: unresolved work is older than the configured status threshold.
- `followup`: saved handoff history marked the item as needing follow-up.
- `repeat`: the item appeared across multiple saved handoff packets.
- `fresh`: the item is unresolved but still within the expected review window.
- `unknown_age`: the item lacks source timestamps and has not repeated across handoffs.

## Guardrail

This report is local workflow context only. It does not approve entries, execute exits, settle markets, or provide investment advice.
