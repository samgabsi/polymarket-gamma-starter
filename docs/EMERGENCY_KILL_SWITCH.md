# Emergency Kill Switch

Version: 1.0.0-real

`POLYMARKET_LIVE_KILL_SWITCH=true` is the safe default and blocks live submit/cancel. Leave it active except during a deliberate operator-controlled live window.

Emergency cancel support remains explicit and gated. Future extensions may allow emergency cancellation while submit remains disabled, but credentials, real-network permission, cancel enablement, operator confirmation, and audit logging are still required.


## v1.1.0 runbook integration

The operator runbook keeps the kill switch active until the final operator-reviewed live window and restores it during closeout.
