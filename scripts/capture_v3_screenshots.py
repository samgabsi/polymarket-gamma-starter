from __future__ import annotations

import argparse
import json
from pathlib import Path

ROUTES = [
    "/", "/system-map", "/routes", "/operator-os", "/ai", "/platform", "/cockpit", "/workspace", "/tasks", "/live",
    "/v3", "/v3/command-center", "/v3/search", "/v3/graph", "/v3/workflows",
    "/v3/ai", "/v3/ai/copilot", "/v3/ai/providers", "/v3/ai/openai", "/v3/ai/local-llm", "/v3/ai/model-recommendations", "/v3/ai/suggestions", "/v3/ai/prompts", "/v3/ai/audit", "/v3/ai/settings", "/v3/ai/chatgpt-connector", "/v3/ai/review-packets",
    "/v3/pre-trade-packet", "/v3/market-brief", "/v3/thesis-health", "/v3/portfolio-brief",
    "/v3/operator-review", "/v3/analytics", "/v3/analytics/decisions", "/v3/analytics/theses", "/v3/analytics/evidence", "/v3/analytics/alerts", "/v3/analytics/governance", "/v3/analytics/calibration", "/v3/analytics/learning-report", "/v3/simulation", "/v3/simulation/replay", "/v3/simulation/sessions", "/v3/simulation/scenarios", "/v3/simulation/pre-trade", "/v3/simulation/thesis", "/v3/simulation/alerts", "/v3/simulation/portfolio", "/v3/simulation/governance", "/v3/simulation/no-trade", "/v3/simulation/reports", "/v3/datasets", "/v3/datasets/snapshots", "/v3/datasets/collector", "/v3/datasets/builder", "/v3/datasets/quality", "/v3/datasets/provenance", "/v3/datasets/replay", "/v3/datasets/exports", "/v3/datasets/settings", "/v3/freshness", "/v3/freshness/planner", "/v3/freshness/schedules", "/v3/freshness/jobs", "/v3/freshness/notifications", "/v3/freshness/readiness", "/v3/freshness/history", "/v3/freshness/settings", "/v3/platform", "/v3/platform/health", "/v3/platform/routes", "/v3/platform/schema", "/v3/platform/plugins", "/v3/platform/storage", "/v3/platform/migrations", "/v3/platform/migrations/plan", "/v3/platform/migrations/storage-map", "/v3/platform/diagnostics", "/v3/platform/exports", "/v3/platform/settings", "/v3/cockpit", "/v3/cockpit/layouts", "/v3/cockpit/focus", "/v3/cockpit/review", "/v3/cockpit/tasks", "/v3/cockpit/dependencies", "/v3/cockpit/source", "/v3/cockpit/packets", "/v3/cockpit/command-palette", "/v3/cockpit/shortcuts", "/v3/cockpit/settings", "/v3/workspace", "/v3/workspace/start", "/v3/workspace/daily-review", "/v3/workspace/weekly-review", "/v3/workspace/task-triage", "/v3/workspace/blocked", "/v3/workspace/dependencies", "/v3/workspace/source-preview", "/v3/workspace/review-flows", "/v3/workspace/review-packets", "/v3/workspace/saved-views", "/v3/workspace/settings", "/v3/tasks", "/v3/tasks/board", "/v3/tasks/inbox", "/v3/tasks/today", "/v3/tasks/week", "/v3/tasks/cadence", "/v3/tasks/reviews", "/v3/tasks/templates", "/v3/tasks/exports", "/v3/tasks/settings", "/v3/settings", "/v3/paper-trading", "/v3/docs", "/v2-live", "/v2-live/strategy", "/v2-live/research",
    "/v3/ai/edge",
    "/v3/ai/edge/new",
    "/v3/ai/edge/packets",
    "/v3/ai/edge/evidence",
    "/v3/ai/edge/calibration",
    "/v3/ai/news-odds",
    "/v3/ai/news-odds/run",
    "/v3/ai/news-odds/adjustments",
    "/v3/ai/news-odds/source-weights",
    "/v3/markets",
    "/v3/markets/demo_france_world_cup",
    "/v3/markets/demo_france_world_cup/news-odds",
    "/v3/markets/family/2026_fifa_world_cup_winner",
    "/v3/markets/family/2026_fifa_world_cup_winner/news-odds",
    "/v3/opportunities",
    "/v3/arbitrage",
    "/arbitrage",
    "/opportunities",
    "/edge",
    "/v3/ai/edge/market/example",
    "/markets/example",
    "/v2-live/monitoring", "/v2-live/portfolio", "/v2-live/governance", "/v2-live/data",
]
# v4.17 required visual QA routes include the existing v3/v4 surfaces plus automated paper trading, opportunity review, and arbitrage routes.


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture or plan v3 screenshot QA routes. Dry-run is safe and dependency-free.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="runtime_screenshots/v4.17.0-real")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    plan = {"version": "4.17.0-real", "base_url": args.base_url.rstrip("/"), "out": str(out), "routes": ROUTES, "screenshots_include_secrets": False, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False}
    if args.dry_run:
        print(json.dumps({"dry_run": True, **plan}, indent=2, sort_keys=True))
        return 0
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        print(json.dumps({"ok": False, "reason": "playwright_not_available", "hint": "Run with --dry-run or install browser automation dependencies locally.", **plan}, indent=2, sort_keys=True))
        return 2
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        for route in ROUTES:
            url = args.base_url.rstrip("/") + route
            safe_name = route.strip("/").replace("/", "_") or "v3"
            page.goto(url, wait_until="networkidle")
            page.screenshot(path=str(out / f"{safe_name}.png"), full_page=True)
        browser.close()
    print(json.dumps({"ok": True, **plan}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
