# Release Notes - v4.12.0-real

Starting version detected: `4.11.0-real`.
Target version: `4.12.0-real`.

## Summary

v4.12.0-real is an operator workflow completion and acceptance-test pass. It keeps the v4.11 stub burn-down work and focuses on making visible AI odds and arbitrage review actions complete from the browser: action, feedback, persistence where appropriate, and review-only safety language.

## Completed Workflows

- Cockpit layout/focus workflow remains functional and covered by existing tests.
- AI odds review workflow now supports plan feedback, manual-evidence preview feedback, saved draft adjustment creation, adjustment detail review, accept/reject/archive review actions, and latest persisted decision lookup.
- Arbitrage review workflow now exposes review, watchlist, ignore, and reject actions with local audit persistence and redirect feedback.
- Settings/configuration workflow remains schema-backed with sources, restart labels, masked secrets, validation preview, and confirmation-gated saves.
- Feature readiness workflow now reports an `operator_acceptance` summary in the stub burn-down endpoint.

## Honest Disabled or Config-Required States

- Kalshi remains disabled/config-required unless `KALSHI_ENABLED=true` and operator-provided configuration are present.
- Arbitrage live scanning remains disabled by default and review-only when enabled.
- OpenAI web search remains disabled by default unless every provider gate is configured.
- Live execution controls remain disabled/gated by default.

## Safety

No autonomous trading, order placement, cancellation, trade approval, live arming, signing, or safety-gate bypass was added. AI odds output is advisory review context. Arbitrage candidates are not guaranteed profits.

## Verification

Run:

```bash
python -m pytest tests/test_operator_workflows_v412.py -q
python -m pytest -q
python scripts/check_versions.py
python scripts/generate_operator_manual.py
```

Review `docs/OPERATOR_ACCEPTANCE_CHECKLIST.md` for the manual operator acceptance path.
