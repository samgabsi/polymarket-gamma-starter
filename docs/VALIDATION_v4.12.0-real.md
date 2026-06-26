# Validation Notes - v4.12.0-real

## Automated Coverage Added

- `tests/test_operator_workflows_v412.py`
  - AI odds browser workflow saves a draft adjustment, redirects with feedback, renders market price/raw/weighted/final/recommended-side fields, and persists accept-to-review-context.
  - Arbitrage browser workflow renders review/watchlist/ignore/reject actions, records a watchlist audit row, and confirms no live mutation.
  - Settings/configuration route renders source/restart/masked-secret posture.
  - Stub burn-down endpoint exposes operator acceptance statuses.

## Existing Coverage Preserved

- Cockpit route rendering, layout selection, selected-state persistence, focus-mode navigation, saved layout copy, and feature status honesty.
- AI odds cap behavior, old 2.5 pp warning threshold, hard-cap clamp, weak-evidence conservatism, manual evidence default, and no-network web-search default.
- Arbitrage math for gross/net margin, fees, slippage, liquidity, resolution mismatch, disabled Kalshi posture, and review-only route behavior.

## Manual QA Still Recommended

- Browser screenshot QA across desktop and mobile.
- Manual clickthrough after packaging.
- Live Polymarket/Kalshi read checks only in an explicitly configured safe environment.

## Known Warnings

The test environment may show framework deprecation warnings depending on the local Python/FastAPI/Starlette versions. Treat failures as blockers; do not treat warnings as passed functionality unless the assertions pass.
