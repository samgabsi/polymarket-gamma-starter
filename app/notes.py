from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import DATA_DIR

NOTES_PATH = DATA_DIR / "market_notes.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent() -> None:
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_notes() -> list[dict[str, Any]]:
    if not NOTES_PATH.exists():
        return []
    try:
        data = json.loads(NOTES_PATH.read_text())
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_notes(items: list[dict[str, Any]]) -> None:
    _ensure_parent()
    NOTES_PATH.write_text(json.dumps(items, indent=2, sort_keys=True))


def add_note(market: dict[str, Any], text: str, tag: str = "research") -> dict[str, Any]:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("Note text cannot be empty.")
    items = load_notes()
    payload = {
        "id": f"note_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "market_id": str(market.get("id")),
        "question": market.get("question", ""),
        "tag": (tag or "research").strip() or "research",
        "text": cleaned,
        "created_at": _now(),
    }
    items.append(payload)
    save_notes(items)
    return payload


def notes_for_market(market_id: str) -> list[dict[str, Any]]:
    return [item for item in load_notes() if str(item.get("market_id")) == str(market_id)]


def delete_note(note_id: str) -> bool:
    items = load_notes()
    kept = [item for item in items if str(item.get("id")) != str(note_id)]
    changed = len(kept) != len(items)
    if changed:
        save_notes(kept)
    return changed


def notes_summary(limit: int = 10) -> dict[str, Any]:
    items = list(reversed(load_notes()))
    by_tag: dict[str, int] = {}
    for item in items:
        tag = str(item.get("tag") or "research")
        by_tag[tag] = by_tag.get(tag, 0) + 1
    return {
        "count": len(items),
        "by_tag": by_tag,
        "recent": items[:limit],
    }
