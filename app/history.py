from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import settings


def list_snapshots(limit: int = 25) -> list[dict[str, Any]]:
    root = settings.snapshot_dir
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("markets_*.json"), reverse=True)[:limit]:
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        rows.append({
            "path": str(path),
            "filename": path.name,
            "created_at": payload.get("created_at", ""),
            "count": payload.get("count", 0),
            "source": payload.get("source", ""),
        })
    return rows


def load_snapshot_file(path: str | Path) -> dict[str, Any] | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def latest_snapshot_summary() -> dict[str, Any] | None:
    if not settings.latest_path.exists():
        return None
    payload = load_snapshot_file(settings.latest_path)
    if not payload:
        return None
    return {
        "path": str(settings.latest_path),
        "created_at": payload.get("created_at", ""),
        "count": payload.get("count", 0),
        "source": payload.get("source", ""),
    }
