# Validation - v4.10.0-real

Validation target: v4.10.0-real route/action honesty, cockpit persistence, feature status, AI odds surfacing, and arbitrage review hardening.

Recommended manual checks:

1. Start the app with `python run.py`.
2. Open `/v3/cockpit`, select a layout, refresh, and confirm the selected layout persists.
3. Start Task Triage Focus and confirm it routes to `/v3/cockpit/tasks` while selecting the task-triage layout.
4. Open `/api/v3/features/status` and confirm opportunity review actions, AI odds page actions, arbitrage review actions, and settings surfacing are `working`.
5. Open `/v3/opportunities?demo=true` and confirm watchlist, paper-review, reject, archive, and notes controls are POST forms, not API links.
6. Open `/v3/markets/demo_france_world_cup` and confirm operator notes/status controls are POST forms and AI Edge opens a real page route.
7. Open `/v3/markets/demo_france_world_cup/news-odds` and confirm plan/search/manual-evidence/adjust controls submit to `/v3/ai/news-odds/market/...` POST routes.
8. Open `/v3/arbitrage?demo=true` and confirm review decisions submit to `/v3/arbitrage/opportunity/.../review` POST routes.
9. Open `/api/v3/arbitrage/opportunity/example/review?action=review_requested` and confirm it reports `method_required: POST` without order/live mutation flags.

Automated checks used for this package:

- `python3 -m compileall -q app`
- `PYTHONPATH=. /Users/sam/Documents/Codex/2026-06-23/fol/work/.test-venv311/bin/pytest -q tests/test_opportunity_review_v46.py tests/test_ai_news_odds_v47.py tests/test_cross_market_arbitrage_v48.py tests/test_live_v3_cockpit.py`
- `PYTHONPATH=. /Users/sam/Documents/Codex/2026-06-23/fol/work/.test-venv311/bin/pytest -q`
- `PYTHONPATH=. /Users/sam/Documents/Codex/2026-06-23/fol/work/.test-venv311/bin/python scripts/check_versions.py`
- `PYTHONPATH=. /Users/sam/Documents/Codex/2026-06-23/fol/work/.test-venv311/bin/python scripts/validate_v3_release.py`
- `PYTHONPATH=. /Users/sam/Documents/Codex/2026-06-23/fol/work/.test-venv311/bin/python scripts/validate_v3_ux_release.py`

Observed result: 178 passed. Existing Starlette template deprecation warnings are non-blocking.
