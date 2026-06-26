# Release Checklist - v4.11.0-real

- [ ] `APP_VERSION` is `4.11.0-real`.
- [ ] `VERSION` is `4.11.0-real`.
- [ ] `/api/v3/features/stub-burndown` returns the required map.
- [ ] `/v3/cockpit` renders Feature Status and Stub Burn-down Map sections.
- [ ] `/v3/workspace` uses POST forms for daily review, weekly review, and task triage.
- [ ] `/v3/ai` uses POST forms for provider dry-run, AI Edge packet generation, evidence normalization preview, and AI review-packet generation.
- [ ] No POST-only v3 Workspace/AI action is presented as a browser href.
- [ ] `python -m pytest` passes.
- [ ] `python scripts/check_versions.py` passes.
- [ ] `python scripts/generate_operator_manual.py` produces v4.11 generated docs.
- [ ] Release ZIP excludes `.env`, runtime data, secrets, virtualenvs, node modules, caches, and local screenshots.
