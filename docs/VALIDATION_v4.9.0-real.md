# Validation - v4.9.0-real

Validation target: v4.9.0-real functional completion and surfaced-status pass.

Recommended checks:

1. Start the app with `python run.py`.
2. Open `/v3/cockpit`.
3. Select Weekly Review Cockpit from Layout Selector.
4. Refresh the page and confirm Weekly Review remains selected.
5. Start Task Triage Focus and confirm it routes to `/v3/cockpit/tasks` while selecting the task-triage layout.
6. Save a current layout copy and confirm the layout count increases.
7. Open `/api/v3/features/status` and confirm cockpit layout/focus features are working while Kalshi status is honest.
8. Open `/v3/ai/news-odds` and confirm raw/evidence/final adjustment language remains visible.
9. Open `/v3/arbitrage?demo=true` and confirm review-only arbitrage posture remains visible.

Automated tests added/updated:

- Layout selector cards render as functional controls.
- Layout selection persists through settings.
- Focus mode starts and redirects to a real cockpit route.
- Feature status endpoint returns honest statuses.
- Existing odds-adjustment and arbitrage review-only tests remain in place.
