# Manual QA Checklist - v4.2.0-real

- [ ] `/v3/ai` shows OpenAI safe defaults, prompt governance, AI suggestions, review packets, audit records, and ChatGPT connector blueprint status.
- [ ] `/api/v3/ai/summary`, `/api/v3/ai/prompts`, `/api/v3/ai/schemas`, and `/api/v3/ai/chatgpt-connector` return redacted safe metadata.
- [ ] `/api/v3/ai/copilot/dry-run` returns a draft and does not call the network.
- [ ] AI suggestion acceptance creates a local task only after explicit human acceptance.
- [ ] `/v3/platform` shows router extraction, route registry, API contract, generated manual, schema, migration, plugin, storage, and safety status.
- [ ] `/v3/platform/routes` renders through the extracted platform router.
- [ ] `/api/v3/platform/route-registry` returns route ownership records and no secrets.
- [ ] `/api/v3/ux/status`, `/api/v3/ux/design-system`, and `/api/v3/ux/navigation` remain available through the v3 core router.
- [ ] `/v3/cockpit`, `/v3/workspace`, `/v3/tasks`, `/v3/datasets`, `/v3/freshness`, `/v3/simulation`, `/v3/analytics`, and `/v2-live` still render.
- [ ] Generated manual source opens from `docs/generated/OPERATOR_MANUAL_v4.2.0-real.md`.
- [ ] No UI copy implies automated trading, financial advice, guaranteed edge, trading approval, or execution readiness.
- [ ] Live submit/cancel gates still require backend approval, typed confirmation, warning acknowledgement, live armed state, read-only disabled, kill switch disabled, risk checks, and audit logging.
