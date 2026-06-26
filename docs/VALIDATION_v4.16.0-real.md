# v4.17.0-real Validation Notes

## Targeted commands run

```bash
python -m py_compile app/main.py app/live_v3.py app/feature_status.py app/config.py app/paper_automation.py app/ui.py app/platform_version.py app/platform_migrations.py app/platform_diagnostics.py scripts/capture_v3_screenshots.py scripts/generate_operator_manual.py scripts/validate_v3_release.py scripts/validate_v3_ux_release.py
```

Result: passed.

```bash
PYTHONPATH=. pytest -q tests/test_paper_trading_v416.py --maxfail=1
```

Result: 7 passed, 2 warnings.

```bash
PYTHONPATH=. pytest -q tests/test_operator_settings_v415.py tests/test_operator_workflows_v415.py tests/test_feature_readiness_v415.py --maxfail=1
```

Result: 16 passed, 7 warnings.

```bash
PYTHONPATH=. pytest -q tests/test_operator_workflows_v414.py tests/test_operator_workflows_v413.py tests/test_operator_workflows_v412.py tests/test_stub_burndown_v411.py --maxfail=1
```

Result: 17 passed, 13 warnings.

```bash
PYTHONPATH=. pytest -q tests/test_ai_news_odds_v47.py tests/test_cross_market_arbitrage_v48.py --maxfail=1
```

Result: 16 passed, 10 warnings.

```bash
PYTHONPATH=. pytest -q tests/test_api_contracts_v4.py --maxfail=1
```

Result: 9 passed.

```bash
PYTHONPATH=. pytest -q tests/test_operator_workflows_v415_review_queue.py --maxfail=1
```

Result: 4 passed, 2 warnings.

```bash
python scripts/check_versions.py
```

Result: passed with `failed: []`.

```bash
python scripts/validate_v3_release.py --quick
```

Result: overall_status pass.

```bash
python scripts/validate_v3_ux_release.py
```

Result: overall_status pass.

## Full suite attempt

```bash
PYTHONPATH=. pytest -q --maxfail=1
```

Result: timed out after 300 seconds with visible passing progress and no failure output before timeout. Full-suite pass is not claimed.

## Manual verification

1. Launch normally with `python run.py` and confirm `/v3/paper-trading` renders.
2. By default, confirm the page shows paper automation disabled and explains that `PAPER_TRADING_ENABLED=true` and `PAPER_TRADING_AUTOMATION_ENABLED=true` are required.
3. Launch with:

```bash
PAPER_TRADING_ENABLED=true \
PAPER_TRADING_AUTOMATION_ENABLED=true \
python run.py
```

4. Open `/v3/paper-trading`.
5. Click **Run paper strategy once**.
6. Confirm a paper-only decision/order/fill appears if a candidate is available or the paper-only sample fixture is used.
7. Confirm `/api/v3/paper/status` reports `paper_only=true` and `live_execution_used=false`.
8. Confirm no live order routes were called and no real order IDs are present.

## Safety expectations

- No real order placement.
- No real order cancellation.
- No live arming.
- Missing Kalshi credentials do not block paper trading.
- Live trading remains separately gated.
