# Emergency and Kill Switch Guide — v2.1.0-real

The emergency posture is conservative by default.

## Default kill switch

```env
POLYMARKET_LIVE_KILL_SWITCH=true
READ_ONLY=true
POLYMARKET_LIVE_ENABLE_SUBMIT=false
POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=false
```

With this posture, live submission is blocked.

## Emergency actions

`POST /api/v2/live/emergency` supports:

- `force_read_only`
- `disable_new_live_orders`
- `record_kill_switch`
- `cancel_all_preview`

These actions are audited. They intentionally do not secretly mutate `.env` or process environment in the background, because hidden mutation could make the operator misunderstand the actual launch state. Persist emergency settings through `/settings/configuration` or by editing local `.env` deliberately.

## Recommended emergency `.env` posture

```env
POLYMARKET_V2_TRADING_MODE=live_read_only
READ_ONLY=true
POLYMARKET_LIVE_KILL_SWITCH=true
POLYMARKET_LIVE_ENABLE_SUBMIT=false
POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED=false
POLYMARKET_LIVE_ENABLE_CANCEL=true
POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED=true
```

This posture blocks new orders while preserving a path for deliberate targeted cancellation if the operator enables cancel gates and confirms each action.

## v2.1.0 Emergency UI

`/v2-live/emergency` presents emergency actions as a dedicated control center. The buttons record audited emergency intent and explain what must be persisted in the environment. Hidden background mutation is intentionally avoided so live trading cannot be armed or disarmed accidentally.
