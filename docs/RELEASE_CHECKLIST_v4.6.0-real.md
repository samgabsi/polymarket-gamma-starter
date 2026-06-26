# Release Checklist - v4.6.0-real

Release checklist: version consistency, generated docs, route inventory, package identity, no secrets, no runtime records, no screenshots with secrets, no .env, and no live mutation during validation.


## v4.6 Scope

v4.6.0-real adds the Opportunity Review Workbench, Market Detail / Opportunity Review pages, Market Family Comparison pages, AI Edge Packet Lifecycle summaries, operator notes/review records, safe watchlist and paper-review queue states, visual QA hardening, route smoke hardening, and no-live-mutation validation.

## Review-Only Boundary

All opportunity review records, operator notes, watchlist states, paper-review queue states, market-edge recommendations, AI Edge packets, calibration summaries, and evidence reviews are research/review-only. They do not approve trades, place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or bypass backend gates.

## Key Routes

- `/v3/opportunities` and `/opportunities` — Opportunity Review Workbench.
- `/v3/markets/{market_id_or_slug}` and `/market/{market_id_or_slug}` — Market Detail / Opportunity Review.
- `/v3/markets/family/{family_id}` — Market Family Comparison.
- `/v3/ai/edge/packets` — AI Edge packet list and lifecycle context.
- `/api/v3/opportunities/reviews` — review record list.
- `/api/v3/opportunities/review/{market_id_or_slug}/notes` — operator notes update API.
- `/api/v3/opportunities/review/{market_id_or_slug}/status` — review status update API.

## Favorite vs Edge

Favorite means most likely outcome in a detected market family. Edge means possible model-fair versus market-implied price mismatch. A favorite can have no edge, and an underdog can have draft edge. This distinction is displayed in the workbench, detail pages, and family comparison pages.

## Safety Confirmations

- No real order placement.
- No real order cancellation.
- No AI trade approval.
- No automatic live trading arming.
- No hidden autonomous trading.
- No release ZIP runtime ledgers, credentials, AI responses, operator notes, review records, watchlists, paper-review queues, screenshots with secrets, local logs, `.env`, venvs, or node modules.

## Preserved Prior Guidance

# Release Checklist - v4.6.0-real

## Version and Identity

- [ ] `VERSION` is `4.6.0-real`.
- [ ] `APP_VERSION` is `4.6.0-real`.
- [ ] README, CHANGELOG, docs, generated docs, validation, visual QA, manual QA, release checklist, scripts, and UI labels reference v4.6.0-real where current-version references are required.
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
- [ ] Final ZIP is named `polymarket-op-console-v4.6.0-real.zip`.
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
