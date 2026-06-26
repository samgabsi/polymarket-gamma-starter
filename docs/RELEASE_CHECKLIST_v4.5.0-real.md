# Release Checklist - v4.5.0-real

## Version and Identity

- [ ] `VERSION` is `4.5.0-real`.
- [ ] `APP_VERSION` is `4.5.0-real`.
- [ ] README, CHANGELOG, docs, generated docs, validation, visual QA, manual QA, release checklist, scripts, and UI labels reference v4.5.0-real where current-version references are required.
- [ ] Package identity is Polymarket OP Console.
- [ ] Package slug is `polymarket-op-console`.

## Feature Checks

- [ ] Duplicate Unified Surface navigation is fixed.
- [ ] Market rows show explicit YES/NO/HOLD recommendation labels.
- [ ] Favorite ranking is separate from edge.
- [ ] Market-family ranking is present where conservatively detected.
- [ ] AI Edge row actions are wired and review-only.
- [ ] System map and route aliases include AI Edge and market recommendation surfaces.

## Validation

- [ ] Unit tests pass.
- [ ] Syntax/import checks pass.
- [ ] Startup smoke passes.
- [ ] Screenshot dry-run route list includes v4.5 AI Edge and market routes.
- [ ] Release package cleanliness check passes.
- [ ] Secret scan finds no packaged secrets.
- [ ] Final ZIP is named `polymarket-op-console-v4.5.0-real.zip`.
- [ ] Final SHA-256 is recorded in the delivery response.

## Safety

- [ ] No real order placement occurred.
- [ ] No real order cancellation occurred.
- [ ] Edge recommendations do not approve trades.
- [ ] AI Edge does not approve trades, place or cancel orders, or arm live trading.
- [ ] OpenAI API and local LLM are disabled by default.
- [ ] No OpenAI API key or local credential is included.
- [ ] Navigation aliases, command palette, keyboard shortcuts, task completion, and guided review completion do not bypass safety gates.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
