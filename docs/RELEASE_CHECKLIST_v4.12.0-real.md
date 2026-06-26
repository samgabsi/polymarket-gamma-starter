# Release Checklist - v4.12.0-real

- [ ] Version metadata reads `4.12.0-real`.
- [ ] README and CHANGELOG include v4.12.
- [ ] `docs/OPERATOR_ACCEPTANCE_CHECKLIST.md` reflects actual current behavior.
- [ ] AI odds browser actions redirect with feedback.
- [ ] Saved AI odds draft adjustment opens a detail page.
- [ ] AI odds accept/reject/archive actions persist local decision state.
- [ ] Arbitrage review/watchlist/ignore/reject actions persist local audit rows.
- [ ] Settings/configuration renders without exposing secrets.
- [ ] Feature readiness and stub burn-down endpoints render and include operator acceptance status.
- [ ] Kalshi remains disabled/config-required unless configured.
- [ ] Live execution remains disabled/gated by default.
- [ ] Targeted workflow tests pass.
- [ ] Full pytest suite passes or any skipped/unrun tests are documented.
- [ ] Generated operator manual and inventories are regenerated.
- [ ] Release package excludes runtime data, caches, virtualenvs, `.env`, logs, and secrets.
