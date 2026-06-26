from __future__ import annotations

from pathlib import Path
import sys

EXPECTED = "4.17.0-real"
ROOT = Path(__file__).resolve().parents[1]
checks = {
    "VERSION": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    "README": "present" if EXPECTED in (ROOT / "README.md").read_text(encoding="utf-8") else "missing",
    "config": "present" if f'APP_VERSION = "{EXPECTED}"' in (ROOT / "app" / "config.py").read_text(encoding="utf-8") else "missing",
}
failed = [key for key, value in checks.items() if value not in {EXPECTED, "present"}]
print({"expected": EXPECTED, "checks": checks, "failed": failed})
if failed:
    sys.exit(1)
