"""Optional local screenshot helper for v2.5 manual QA.

This script intentionally does not enter secrets, submit forms, cancel orders, or place orders.
It requires Playwright if you choose to use it:

    pip install playwright
    playwright install chromium
    python scripts/capture_v2_6_screenshots.py --base-url http://127.0.0.1:8000

Screenshots are saved under runtime_screenshots/v4.7.0-real/, which is not intended for release ZIP assets unless manually reviewed for secrets.
"""
from __future__ import annotations

import argparse
from pathlib import Path

PAGES = {
    "dashboard": "/v2-live",
    "markets": "/v2-live/markets",
    "trade-ticket": "/v2-live/trade-ticket",
    "strategy": "/v2-live/strategy",
    "research": "/v2-live/research",
    "orders": "/v2-live/orders",
    "positions": "/v2-live/positions",
    "risk": "/v2-live/risk",
    "audit": "/v2-live/audit",
    "settings": "/v2-live/settings",
    "emergency": "/v2-live/emergency",
    "verify": "/v2-live/verify",
    "docs": "/v2-live/docs",
}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="runtime_screenshots/v4.7.0-real")
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        print("Playwright is not installed. Use the manual QA checklist or install playwright explicitly.")
        print(f"Import error: {type(exc).__name__}: {exc}")
        raise SystemExit(2)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        for name, route in PAGES.items():
            page.goto(args.base_url.rstrip("/") + route, wait_until="networkidle")
            page.screenshot(path=str(out / f"{name}.png"), full_page=True)
        browser.close()
    print({"saved_to": str(out), "pages": list(PAGES)})

if __name__ == "__main__":
    main()
