from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .ai_edge_schemas import AI_EDGE_SAFETY_STATEMENT, base_safety, default_evidence_source, record_id
from .config import APP_VERSION, DATA_DIR, settings
from .platform_safety import redact_data, redact_text, safety_flags

EDGE_DIR = DATA_DIR / "ai" / "edge"
EVIDENCE_SOURCES_PATH = EDGE_DIR / "evidence_sources.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    EDGE_DIR.mkdir(parents=True, exist_ok=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_dir()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact_data(row), sort_keys=True, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(redact_data(parsed))
        except json.JSONDecodeError:
            rows.append({"source_id": record_id("edge_src_invalid"), "status": "invalid_json", "retrieved_at": _now(), "secret_values_returned": False})
    return rows


def _latest_by_id(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[str(row.get(key) or record_id("edge_src"))] = row
    return sorted(latest.values(), key=lambda row: str(row.get("updated_at") or row.get("retrieved_at") or ""), reverse=True)


def _stance(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"supports", "contradicts", "mixed", "unknown"}:
        return text
    if any(token in text for token in ["not", "decline", "against", "fail", "false"]):
        return "contradicts"
    if any(token in text for token in ["support", "increase", "for", "true", "confirm"]):
        return "supports"
    return "unknown"


def _source_from_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    safe_record = redact_data(record)
    url = redact_text(safe_record.get("url") or safe_record.get("source_url") or "")
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    title = redact_text(safe_record.get("title") or safe_record.get("name") or domain or f"Evidence source {index}")
    snippet = redact_text(safe_record.get("snippet") or safe_record.get("summary") or safe_record.get("text") or "No snippet supplied.")
    if not settings.ai_edge_allow_source_urls:
        url = ""
    source = {
        "source_id": redact_text(safe_record.get("source_id") or record_id("edge_src")),
        "created_at": safe_record.get("created_at") or _now(),
        "updated_at": _now(),
        "app_version": APP_VERSION,
        "title": title[:220],
        "url": url,
        "domain": domain,
        "citation_label": str(safe_record.get("citation_label") or f"S{index}"),
        "claim_stance": _stance(safe_record.get("claim_stance") or safe_record.get("stance") or snippet),
        "snippet": snippet[:1200],
        "retrieved_at": redact_text(safe_record.get("retrieved_at") or _now()),
        "published_at": redact_text(safe_record.get("published_at") or safe_record.get("date") or ""),
        "recency_status": redact_text(safe_record.get("recency_status") or "operator_supplied_unknown"),
        "quality_score": float(safe_record.get("quality_score", 0.65) or 0.65),
        "relevance_score": float(safe_record.get("relevance_score", 0.7) or 0.7),
        "operator_provided": bool(safe_record.get("operator_provided", True)),
        "source_hash": _hash({"url": url, "title": title, "snippet": snippet}),
        "secret_values_returned": False,
        "safety_statement": AI_EDGE_SAFETY_STATEMENT,
    }
    return redact_data(source)


def _sources_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key in ("evidence_sources", "sources"):
        raw = payload.get(key)
        if isinstance(raw, list):
            records.extend([item for item in raw if isinstance(item, dict)])
    urls = payload.get("evidence_urls") or payload.get("source_urls") or []
    snippets = payload.get("evidence_snippets") or payload.get("snippets") or []
    if isinstance(urls, str):
        urls = [urls]
    if isinstance(snippets, str):
        snippets = [snippets]
    if isinstance(urls, list):
        for index, url in enumerate(urls):
            if isinstance(url, str) and url.strip():
                snippet = snippets[index] if isinstance(snippets, list) and index < len(snippets) else ""
                records.append({"url": url, "snippet": snippet, "title": urlparse(url).netloc or f"Evidence URL {index + 1}"})
    if isinstance(snippets, list):
        for index, snippet in enumerate(snippets):
            if isinstance(snippet, str) and snippet.strip() and index >= len(urls):
                records.append({"snippet": snippet, "title": f"Operator evidence snippet {index + 1}", "url": ""})
    return records


def normalize_evidence(payload: dict[str, Any] | None = None, *, write: bool = False, include_demo_when_empty: bool = False) -> dict[str, Any]:
    payload = payload or {}
    records = _sources_from_payload(payload)
    sources = [_source_from_record(record, index + 1) for index, record in enumerate(records)]
    if not sources and include_demo_when_empty:
        sources = [default_evidence_source()]
    if write:
        for source in sources:
            _write_jsonl(EVIDENCE_SOURCES_PATH, source)
    return safety_flags({
        "version": APP_VERSION,
        "count": len(sources),
        "items": sources,
        "write": write,
        "normalization_does_not_fetch_urls": True,
        "external_network_called": False,
        "source_urls_included": settings.ai_edge_allow_source_urls,
        **base_safety(),
    })


def list_evidence_sources(limit: int = 250, stance: str | None = None) -> dict[str, Any]:
    rows = _latest_by_id(_read_jsonl(EVIDENCE_SOURCES_PATH), "source_id")
    if stance:
        rows = [row for row in rows if row.get("claim_stance") == stance]
    capped = rows[: max(1, min(int(limit or 250), 5000))]
    return safety_flags({"version": APP_VERSION, "count": len(capped), "total_count": len(rows), "items": capped, **base_safety()})


def evidence_summary() -> dict[str, Any]:
    rows = list_evidence_sources(limit=5000)["items"]
    stances: dict[str, int] = {}
    for row in rows:
        stance = str(row.get("claim_stance") or "unknown")
        stances[stance] = stances.get(stance, 0) + 1
    return safety_flags({
        "version": APP_VERSION,
        "evidence_source_count": len(rows),
        "stance_counts": stances,
        "source_urls_allowed": settings.ai_edge_allow_source_urls,
        "external_network_called": False,
        **base_safety(),
    })


def export_evidence_json() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "summary": evidence_summary(),
        "evidence_sources": list_evidence_sources(limit=5000),
        "raw_private_data_included": False,
        **base_safety(),
    })


def export_evidence_markdown() -> str:
    data = export_evidence_json()
    lines = [f"# AI Edge Evidence Export - {APP_VERSION}", "", AI_EDGE_SAFETY_STATEMENT, ""]
    for item in data["evidence_sources"]["items"]:
        url = f" - {item.get('url')}" if item.get("url") else ""
        lines.append(f"- `{item.get('citation_label')}` {item.get('title')}{url}")
        lines.append(f"  - Stance: `{item.get('claim_stance')}`")
        lines.append(f"  - Snippet: {item.get('snippet')}")
    if not data["evidence_sources"]["items"]:
        lines.append("- No evidence sources recorded.")
    return "\n".join(lines) + "\n"


def cleanup_runtime_records(root: Path | None = None) -> dict[str, Any]:
    root = root or EDGE_DIR
    removed = []
    if root.exists():
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
                removed.append(str(path))
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            root.rmdir()
        except OSError:
            pass
    return safety_flags({"removed_count": len(removed), "removed_paths": removed[:100], **base_safety()})
