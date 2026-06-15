# Autonomous Trading

Version: 1.0.0-real

Autonomous live trading is **not enabled** in this milestone. Manual live submit/cancel are the priority and are implemented only through the guarded manual control plane.

Autonomous paths remain off by default and deterministic-signal based. Dry-run and fake-adapter modes may be used for local workflow validation. No background scheduler starts automatically. Autonomous live trading must not run unless a future release explicitly proves all strategy, market, token, budget, kill-switch, execution-quality, and audit gates.


## v1.1.0 controlled readiness

Autonomous live trading remains blocked by default. Dry-run and fake-adapter modes can queue deterministic signals for manual review, but the scheduler must remain disabled unless explicitly reviewed in a future milestone.

## v1.2.0 Training Lab relationship

Training-generated signals do not enable autonomous live trading. They are queued for manual review and must pass the existing autonomous and live guardrails. Autonomous live mode remains disabled by default.
