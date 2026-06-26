# Operator Notes - v4.15.0-real

## Launch

```bash
python run.py
```

Open `http://127.0.0.1:8000`, sign in, then use `/v3/settings`, `/v3/feature-readiness`, `/review-queue`, `/v3/ai/news-odds`, and `/v3/arbitrage` for the v4 operator workflows.

## Settings workflow

Open `/v3/settings` to review UI-safe operator preferences for AI odds adjustment, arbitrage scanner thresholds, and Kalshi posture. Each row shows the runtime value, any saved UI preference, the source of the value, and whether a restart is required for runtime/environment changes.

Use **Save UI-safe preferences** to persist local operator preferences. These preferences are local review context; they do not edit `.env`, mutate process environment variables, expose secrets, place orders, cancel orders, approve trades, or arm live trading.

Invalid numeric values are rejected and shown as validation errors. The previous saved preference remains intact.

## Review Queue and Feature Readiness

- `/review-queue` records local operator decisions such as Mark Reviewed, Watchlist, Send to Paper Review, Reject, and Archive.
- `/v3/feature-readiness` lets the operator inspect working/partial/config-required/scaffolded/disabled/unavailable/error surfaces and record a local acknowledgement.

## Safety posture

The app remains review-only and human-in-the-loop. AI odds adjustments are advisory drafts. Arbitrage candidates are review candidates, not guaranteed profits. Kalshi remains honest about disabled/config-required/scaffolded state unless explicitly configured. No uncontrolled autonomous execution was added.
