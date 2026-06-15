from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR
from .sources import build_market_collection_targets, build_market_source_pack, extract_market_query

EVIDENCE_DIR = DATA_DIR / "evidence_packets"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(value: str) -> str:
    value = _SAFE.sub("-", value).strip("-._")
    return value[:80] or "market"


def evidence_file_for(packet_id: str) -> Path:
    name = Path(packet_id).name
    if not name.endswith(".json"):
        name += ".json"
    path = (EVIDENCE_DIR / name).resolve()
    if EVIDENCE_DIR.resolve() not in path.parents and path != EVIDENCE_DIR.resolve():
        raise ValueError("Invalid evidence packet path")
    return path


def list_evidence_packets(limit: int = 50) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(EVIDENCE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows.append({
                "packet_id": path.name,
                "created_at": data.get("created_at") or data.get("generated_at") or "",
                "market_id": data.get("market", {}).get("id") or data.get("market_id") or "",
                "question": data.get("market", {}).get("question") or data.get("question") or "",
                "query": data.get("query") or "",
                "status": data.get("status") or "unknown",
                "source_count": len(data.get("evidence_items", [])),
                "path": str(path),
            })
        except Exception:
            rows.append({"packet_id": path.name, "status": "unreadable", "source_count": 0, "path": str(path)})
    return rows


def load_evidence_packet(packet_id: str) -> dict[str, Any]:
    path = evidence_file_for(packet_id)
    if not path.exists():
        raise FileNotFoundError(packet_id)
    return json.loads(path.read_text(encoding="utf-8"))


def delete_evidence_packet(packet_id: str) -> bool:
    path = evidence_file_for(packet_id)
    if path.exists():
        path.unlink()
        return True
    return False


def create_evidence_packet(market: dict[str, Any], *, created_by: str = "local", note: str = "", include_weak_sources: bool = False) -> dict[str, Any]:
    market_id = str(market.get("id") or "")
    question = str(market.get("question") or market.get("title") or "")
    query = extract_market_query(market)
    targets = build_market_collection_targets(market)
    source_pack = build_market_source_pack(market)
    target_groups = [
        ("primary", targets.get("primary_targets", [])),
        ("secondary", targets.get("secondary_targets", [])),
    ]
    if include_weak_sources:
        target_groups.append(("weak_signal", targets.get("weak_signal_targets", [])))

    evidence_items: list[dict[str, Any]] = []
    for priority, links in target_groups:
        for link in links:
            evidence_items.append({
                "source_id": link.get("id"),
                "source_name": link.get("name"),
                "category": link.get("category"),
                "priority": priority,
                "url": link.get("url"),
                "requires_key": bool(link.get("requires_key", False)),
                "collection_status": "pending_manual_review",
                "evidence_strength": "unknown",
                "fact_summary": "",
                "collected_at": None,
                "notes": "Open the URL, verify facts, then record conclusions in market notes or future AI evidence extraction.",
            })

    created_at = _now()
    filename = f"{created_at.replace(':','').replace('+','Z')}_{_safe_filename(market_id or question)}.json"
    packet = {
        "packet_version": "0.2.4-evidence-packet-v1",
        "status": "pending_manual_review",
        "created_at": created_at,
        "created_by": created_by,
        "note": note,
        "market": {
            "id": market_id,
            "question": question,
            "slug": market.get("slug"),
            "category": market.get("category"),
            "volume_24hr": market.get("volume_24hr"),
            "liquidity": market.get("liquidity"),
            "polymarket_url": market.get("polymarket_url"),
            "polymarket_search_url": market.get("polymarket_search_url"),
        },
        "query": query,
        "topics": targets.get("topics", []),
        "source_pack": source_pack,
        "collection_targets": targets,
        "evidence_items": evidence_items,
        "analysis_template": {
            "verified_facts": [],
            "contradictory_facts": [],
            "open_questions": [],
            "probability_implications": "",
            "paper_trade_implications": "",
        },
        "guardrails": [
            "No live trading or wallet signing is performed by this packet.",
            "Social sources are weak signals unless independently confirmed.",
            "Record exact dates and source URLs for any facts used in probability updates.",
        ],
    }
    path = EVIDENCE_DIR / filename
    path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    packet["packet_id"] = filename
    packet["path"] = str(path)
    return packet


def evidence_summary(limit: int = 10) -> dict[str, Any]:
    items = list_evidence_packets(limit=limit)
    by_status: dict[str, int] = {}
    for item in list_evidence_packets(limit=1000):
        status = str(item.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
    return {"count": sum(by_status.values()), "by_status": by_status, "recent": items}
