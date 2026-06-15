from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR

WATCHLIST_PATH = DATA_DIR / "watchlist.json"


def _ensure_parent() -> None:
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_watchlist() -> list[dict[str, Any]]:
    if not WATCHLIST_PATH.exists():
        return []
    try:
        data = json.loads(WATCHLIST_PATH.read_text())
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_watchlist(items: list[dict[str, Any]]) -> None:
    _ensure_parent()
    WATCHLIST_PATH.write_text(json.dumps(items, indent=2, sort_keys=True))


def add_to_watchlist(market: dict[str, Any], note: str = "") -> dict[str, Any]:
    items = load_watchlist()
    market_id = str(market.get("id"))
    now = datetime.now(timezone.utc).isoformat()
    existing = next((item for item in items if str(item.get("market_id")) == market_id), None)
    payload = {
        "market_id": market_id,
        "question": market.get("question", ""),
        "url": market.get("url", ""),
        "category": market.get("category", ""),
        "end_date": market.get("end_date", ""),
        "note": note,
        "updated_at": now,
    }
    if existing:
        existing.update(payload)
        result = existing
    else:
        payload["created_at"] = now
        items.append(payload)
        result = payload
    save_watchlist(items)
    return result


def remove_from_watchlist(market_id: str) -> bool:
    items = load_watchlist()
    kept = [item for item in items if str(item.get("market_id")) != str(market_id)]
    changed = len(kept) != len(items)
    if changed:
        save_watchlist(kept)
    return changed
