
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json
import re
import uuid


DATA_DIR = Path("data")
PACKET_DIR = DATA_DIR / "evidence_packets"
THESIS_FILE = DATA_DIR / "theses.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_slug(text: str, fallback: str = "market") -> str:
    text = (text or fallback).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:80] or fallback


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def market_title(market: Dict[str, Any]) -> str:
    return str(
        market.get("title")
        or market.get("question")
        or market.get("name")
        or market.get("slug")
        or market.get("id")
        or "Untitled market"
    )


def market_id(market: Dict[str, Any]) -> str:
    return str(market.get("market_id") or market.get("id") or market.get("conditionId") or market.get("slug") or "")


def default_queries_for_market(market: Dict[str, Any]) -> List[str]:
    title = market_title(market)
    category = str(market.get("category") or market.get("categorySlug") or "").strip()
    tags = market.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    queries = [title]
    if category:
        queries.append(f"{title} {category}")
    for tag in tags[:3]:
        tag = str(tag).strip()
        if tag:
            queries.append(f"{title} {tag}")

    seen = set()
    clean = []
    for q in queries:
        q = re.sub(r"\s+", " ", str(q)).strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            clean.append(q)
    return clean[:5]


def default_sources_for_market(market: Dict[str, Any]) -> List[Dict[str, str]]:
    title = market_title(market)
    q = "+".join(title.split())
    return [
        {"name": "Polymarket", "type": "market", "url": str(market.get("polymarket_url") or market.get("url") or "")},
        {"name": "Google News Search", "type": "search", "url": f"https://www.google.com/search?tbm=nws&q={q}"},
        {"name": "Reuters Search", "type": "search", "url": f"https://www.reuters.com/site-search/?query={q}"},
        {"name": "AP News Search", "type": "search", "url": f"https://apnews.com/search?q={q}"},
    ]


@dataclass
class EvidenceTask:
    id: str
    market_id: str
    market_title: str
    task_type: str
    priority: str
    status: str
    query: str
    source_hint: str
    created_at: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_evidence_packet(market: Dict[str, Any], reason: str = "Automated evidence packet") -> Dict[str, Any]:
    mid = market_id(market)
    title = market_title(market)
    packet_id = f"ev_{safe_slug(mid or title)}_{uuid.uuid4().hex[:8]}"
    packet = {
        "packet_id": packet_id,
        "market_id": mid,
        "market_title": title,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "reason": reason,
        "status": "open",
        "queries": default_queries_for_market(market),
        "sources": default_sources_for_market(market),
        "claims": [],
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "open_questions": [
            "What would resolve this market?",
            "What primary sources or official data determine the outcome?",
            "What evidence would invalidate the current thesis?",
        ],
        "operator_notes": "",
    }
    PACKET_DIR.mkdir(parents=True, exist_ok=True)
    save_json(PACKET_DIR / f"{packet_id}.json", packet)
    return packet


def list_evidence_packets() -> List[Dict[str, Any]]:
    PACKET_DIR.mkdir(parents=True, exist_ok=True)
    packets = []
    for p in sorted(PACKET_DIR.glob("*.json"), reverse=True):
        packet = load_json(p, None)
        if isinstance(packet, dict):
            packets.append(packet)
    return packets


def find_packets_for_market(mid: str) -> List[Dict[str, Any]]:
    return [p for p in list_evidence_packets() if str(p.get("market_id")) == str(mid)]


def build_evidence_tasks_for_market(market: Dict[str, Any]) -> List[Dict[str, Any]]:
    mid = market_id(market)
    title = market_title(market)
    packets = find_packets_for_market(mid)
    tasks: List[EvidenceTask] = []

    if not packets:
        tasks.append(EvidenceTask(
            id=f"task_{uuid.uuid4().hex[:8]}",
            market_id=mid,
            market_title=title,
            task_type="create_packet",
            priority="high",
            status="open",
            query=title,
            source_hint="Create an evidence packet before acting on this market.",
            created_at=now_iso(),
        ))

    latest = packets[0] if packets else None
    if latest:
        if not latest.get("supporting_evidence"):
            tasks.append(EvidenceTask(
                id=f"task_{uuid.uuid4().hex[:8]}",
                market_id=mid,
                market_title=title,
                task_type="supporting_evidence",
                priority="high",
                status="open",
                query=(latest.get("queries") or [title])[0],
                source_hint="Find at least two credible supporting sources.",
                created_at=now_iso(),
            ))
        if not latest.get("contradicting_evidence"):
            tasks.append(EvidenceTask(
                id=f"task_{uuid.uuid4().hex[:8]}",
                market_id=mid,
                market_title=title,
                task_type="contradicting_evidence",
                priority="medium",
                status="open",
                query=(latest.get("queries") or [title])[0],
                source_hint="Find disconfirming evidence or reasons this market may be misread.",
                created_at=now_iso(),
            ))
        if not latest.get("claims"):
            tasks.append(EvidenceTask(
                id=f"task_{uuid.uuid4().hex[:8]}",
                market_id=mid,
                market_title=title,
                task_type="extract_claims",
                priority="medium",
                status="open",
                query=title,
                source_hint="Extract key claims from collected sources.",
                created_at=now_iso(),
            ))

    return [t.to_dict() for t in tasks]


def build_evidence_workbench(markets: List[Dict[str, Any]], limit: int = 25) -> Dict[str, Any]:
    items = []
    for market in markets[:limit]:
        mid = market_id(market)
        packets = find_packets_for_market(mid)
        tasks = build_evidence_tasks_for_market(market)
        items.append({
            "market_id": mid,
            "market_title": market_title(market),
            "packet_count": len(packets),
            "latest_packet_id": packets[0].get("packet_id") if packets else None,
            "open_task_count": len(tasks),
            "tasks": tasks,
            "recommended_queries": default_queries_for_market(market),
            "recommended_sources": default_sources_for_market(market),
        })
    items.sort(key=lambda x: (x["open_task_count"], -x["packet_count"]), reverse=True)
    return {"generated_at": now_iso(), "items": items}
