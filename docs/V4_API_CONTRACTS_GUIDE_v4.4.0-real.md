# V4 API Contracts Guide - v4.4.0-real

## Purpose

v4.4.0-real adds local API contract tests for high-level response expectations without requiring credentials, network access, live market data, or live mutation endpoints.

## Shared Envelopes

Platform schema helpers use the shared response envelope from `app/platform_api.py`. Required fields include `success`, `app_version`, `generated_at`, `module`, `action`, `warnings`, `blockers`, `unknown_unavailable_data`, `limitations`, and `safety_statement`.

## Backward Compatibility

Existing v2, v3, cockpit, workspace, task, dataset, freshness, simulation, analytics, and live-control responses are not force-normalized in v4.4. API contract tests validate that platform envelopes exist and that legacy summary responses remain safe and available.

## Unknown Data, Warnings, And Blockers

Contracts must preserve visibility for warnings, blockers, stale data, unknown data, unavailable data, disabled gates, and kill-switch state. Tests must not hide these fields or treat missing runtime data as real data.

## Contract Groups

- Platform summary envelope and safety flags
- Route inventory and route ownership registry
- API schema inventory and envelope adoption summary
- Runtime migration planner and storage map
- Plugin manifest metadata-only boundary
- Cockpit, workspace, task, dataset, freshness, simulation, and analytics summaries where safe
- Live-control status/readiness routes as fail-closed or authentication-protected surfaces
- Forbidden command-palette actions

## No-Live-Mutation Expectations

Contract tests must not place orders, cancel orders, arm live trading, approve trades, sign transactions, call live mutation endpoints, call network-heavy workflows, or require real credentials. They use FastAPI TestClient, local fakes, and safe helper calls.

## Future Endpoint Guidance

New platform endpoints should adopt the shared envelope. Existing endpoints should adopt it only additively, after templates and clients have compatibility tests.
