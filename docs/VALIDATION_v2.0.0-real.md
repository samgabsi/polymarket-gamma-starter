# Validation Report — v2.1.0-real

Generated: 2026-06-15T20:32:52Z

## Commands run

```text
$ python -m compileall -q app tests
PASS: compileall
$ python -m pytest -q
......                                                                   [100%]
6 passed in 0.47s
$ python - << route/import smoke test
PASS: imported FastAPI app version=2.1.0-real; routes=488; required_v2_routes_present=7
$ python - << package safety scan
NOTE: transient cache dirs may exist during validation: ['.pytest_cache', 'app/__pycache__', 'tests/__pycache__']
PASS: no non-empty secret assignments found in release files
```

## Result

- compileall: PASS
- pytest: PASS (6 tests)
- FastAPI import/routes smoke test: PASS
- Secret assignment scan: PASS
- No real order placement was performed; tests use local mocked/fail-closed paths only.

## Known limitations

- Real submit/cancel still require operator-installed optional dependencies, valid Polymarket credentials, account eligibility, funding/allowances, and all local live gates to pass.
- The legacy py-clob-client adapter is retained for compatibility; current Polymarket docs recommend the newer official SDK family for new integrations.
- Positions/P&L degrade to unknown/unavailable when reliable Data API or account fields are unavailable.
