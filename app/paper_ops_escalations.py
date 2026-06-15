from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR
from .paper_ops_aging import build_ops_aging_detail, build_paper_ops_aging

ESCALATIONS_PATH = DATA_DIR / "paper" / "paper_ops_escalations.json"
ESCALATION_STATUSES = {"open", "investigating", "waiting", "resolved", "dismissed"}
ESCALATION_SEVERITIES = {"critical", "high", "medium", "low", "info"}
OPEN_STATUSES = {"open", "investigating", "waiting"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _severity_from_aging(item: dict[str, Any] | None, requested: str = "") -> str:
    if requested in ESCALATION_SEVERITIES:
        return requested
    aging_severity = _text((item or {}).get("severity"))
    if aging_severity == "critical":
        return "critical"
    if aging_severity in {"stale", "followup"}:
        return "high"
    if aging_severity in {"repeat", "unknown_age"}:
        return "medium"
    if aging_severity == "fresh":
        return "low"
    return "medium"


def _aging_item_snapshot(aging_item_id: str) -> dict[str, Any] | None:
    detail = build_ops_aging_detail(aging_item_id)
    if not detail:
        return None
    item = detail.get("item")
    return item if isinstance(item, dict) else None


def load_ops_escalations() -> list[dict[str, Any]]:
    rows = _read_json(ESCALATIONS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_ops_escalations(rows: list[dict[str, Any]]) -> None:
    _write_json(ESCALATIONS_PATH, rows)


def list_ops_escalations(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    severity: str | None = None,
    owner: str | None = None,
    aging_item_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_ops_escalations()))
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted]
    if severity:
        wanted = _text(severity)
        rows = [row for row in rows if _text(row.get("severity")) == wanted]
    if owner:
        wanted = _text(owner)
        rows = [row for row in rows if _text(row.get("owner")) == wanted]
    if aging_item_id:
        wanted = _text(aging_item_id)
        rows = [row for row in rows if _text(row.get("aging_item_id")) == wanted]
    return rows[: max(0, int(limit))]


def get_ops_escalation(escalation_id: str) -> dict[str, Any] | None:
    wanted = _text(escalation_id)
    for row in load_ops_escalations():
        if _text(row.get("escalation_id")) == wanted:
            return row
    return None


def latest_escalation_by_aging_item(limit: int = 10000) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in list_ops_escalations(limit=limit):
        item_id = _text(row.get("aging_item_id"))
        if item_id and item_id not in index:
            index[item_id] = row
    return index


def create_ops_escalation(
    *,
    aging_item_id: str,
    status: str = "open",
    severity: str = "",
    owner: str = "local",
    note: str = "",
) -> dict[str, Any]:
    aging_item_id = _text(aging_item_id).strip()
    if not aging_item_id:
        raise ValueError("aging_item_id is required")
    aging_item = _aging_item_snapshot(aging_item_id)
    if not aging_item:
        raise ValueError(f"Paper ops aging item not found: {aging_item_id}")
    record_status = status if status in ESCALATION_STATUSES else "open"
    escalation_severity = _severity_from_aging(aging_item, severity)
    created_at = _now()
    record = {
        "escalation_id": f"poe_{uuid4().hex[:12]}",
        "version": "0.5.2-paper-ops-escalation-v1",
        "mode": "paper_ops_escalation_v052",
        "created_at": created_at,
        "updated_at": created_at,
        "aging_item_id": aging_item_id,
        "status": record_status,
        "severity": escalation_severity,
        "owner": _text(owner, "local"),
        "note": _text(note),
        "section": _text(aging_item.get("section")),
        "source_status": _text(aging_item.get("status")),
        "source_severity": _text(aging_item.get("severity")),
        "market_id": _text(aging_item.get("market_id")),
        "ticket_id": _text(aging_item.get("ticket_id")),
        "question": _text(aging_item.get("question") or aging_item.get("title")),
        "title": _text(aging_item.get("title") or aging_item_id),
        "age_hours_at_escalation": aging_item.get("age_hours"),
        "handoff_count_at_escalation": _safe_int(aging_item.get("handoff_count")),
        "recommended_action_at_escalation": _text(aging_item.get("recommended_action")),
        "source_snapshot": aging_item,
        "history": [
            {
                "timestamp": created_at,
                "status": record_status,
                "severity": escalation_severity,
                "owner": _text(owner, "local"),
                "note": _text(note),
                "event": "created",
            }
        ],
        "guardrail": "Local paper-ops escalation record only. It tracks human follow-up and does not approve, execute, or advise trades.",
    }
    rows = load_ops_escalations()
    rows.append(record)
    save_ops_escalations(rows)
    return record


def update_ops_escalation(
    escalation_id: str,
    *,
    status: str | None = None,
    severity: str | None = None,
    owner: str | None = None,
    note: str = "",
) -> dict[str, Any] | None:
    wanted = _text(escalation_id)
    rows = load_ops_escalations()
    updated: dict[str, Any] | None = None
    for row in rows:
        if _text(row.get("escalation_id")) != wanted:
            continue
        previous = {
            "status": row.get("status"),
            "severity": row.get("severity"),
            "owner": row.get("owner"),
        }
        if status:
            row["status"] = status if status in ESCALATION_STATUSES else row.get("status", "open")
        if severity:
            row["severity"] = severity if severity in ESCALATION_SEVERITIES else row.get("severity", "medium")
        if owner is not None and _text(owner):
            row["owner"] = _text(owner)
        row["updated_at"] = _now()
        history = row.get("history") if isinstance(row.get("history"), list) else []
        history.append(
            {
                "timestamp": row["updated_at"],
                "status": row.get("status"),
                "severity": row.get("severity"),
                "owner": row.get("owner"),
                "note": _text(note),
                "event": "updated",
                "previous": previous,
            }
        )
        row["history"] = history
        if note:
            row["note"] = _text(note)
        updated = row
        break
    if updated is not None:
        save_ops_escalations(rows)
    return updated


def summarize_ops_escalations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(_text(row.get("status") or "unknown") for row in rows)
    severities = Counter(_text(row.get("severity") or "unknown") for row in rows)
    sections = Counter(_text(row.get("section") or "unknown") for row in rows)
    owners = Counter(_text(row.get("owner") or "unassigned") for row in rows)
    markets = {_text(row.get("market_id")) for row in rows if row.get("market_id")}
    open_count = sum(statuses.get(status, 0) for status in OPEN_STATUSES)
    return {
        "count": len(rows),
        "open": open_count,
        "resolved": statuses.get("resolved", 0),
        "dismissed": statuses.get("dismissed", 0),
        "critical": severities.get("critical", 0),
        "high": severities.get("high", 0),
        "market_count": len(markets),
        "by_status": dict(sorted(statuses.items())),
        "by_severity": dict(sorted(severities.items())),
        "by_section": dict(sorted(sections.items())),
        "by_owner": dict(sorted(owners.items())),
        "latest_escalation_at": rows[0].get("created_at") if rows else "",
        "guardrail": "Escalation summaries are local operator follow-up records only, not execution authorization or trading advice.",
    }


def build_ops_escalation_board(
    *,
    limit: int = 100,
    status: str | None = None,
    market_id: str | None = None,
    severity: str | None = None,
    owner: str | None = None,
    include_candidates: bool = True,
) -> dict[str, Any]:
    records = list_ops_escalations(limit=limit, status=status, market_id=market_id, severity=severity, owner=owner)
    latest_by_item = latest_escalation_by_aging_item()
    candidates: list[dict[str, Any]] = []
    if include_candidates:
        aging_report = build_paper_ops_aging(limit=1000, market_id=market_id)
        for item in aging_report.get("items") or []:
            sev = _text(item.get("severity"))
            if sev not in {"critical", "stale", "followup", "repeat"}:
                continue
            item_id = _text(item.get("aging_item_id"))
            latest = latest_by_item.get(item_id)
            if latest and _text(latest.get("status")) in OPEN_STATUSES:
                continue
            candidates.append(
                {
                    "aging_item_id": item_id,
                    "recommended_escalation_severity": _severity_from_aging(item),
                    "source_severity": sev,
                    "status": _text(item.get("status")),
                    "section": _text(item.get("section")),
                    "title": _text(item.get("title")),
                    "market_id": _text(item.get("market_id")),
                    "ticket_id": _text(item.get("ticket_id")),
                    "age_hours": item.get("age_hours"),
                    "handoff_count": _safe_int(item.get("handoff_count")),
                    "recommended_action": _text(item.get("recommended_action")),
                    "latest_closed_escalation_id": _text((latest or {}).get("escalation_id")),
                }
            )
        candidates.sort(
            key=lambda row: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(_text(row.get("recommended_escalation_severity")), 0),
                _safe_float(row.get("age_hours")),
                _safe_int(row.get("handoff_count")),
            ),
            reverse=True,
        )
        candidates = candidates[: max(0, int(limit))]
    return {
        "version": "0.5.2-paper-ops-escalation-v1",
        "mode": "paper_ops_escalation_board_v052",
        "generated_at": _now(),
        "summary": summarize_ops_escalations(records),
        "items": records,
        "candidates": candidates,
        "candidate_summary": {
            "count": len(candidates),
            "critical_or_high": sum(1 for row in candidates if row.get("recommended_escalation_severity") in {"critical", "high"}),
        },
        "filters": {"status": status or "", "market_id": market_id or "", "severity": severity or "", "owner": owner or ""},
        "guardrail": "Paper ops escalations are local human follow-up records. They never approve, reject, execute, settle, or advise trades.",
    }


def ops_escalation_alerts(board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_ops_escalation_board(limit=25)
    alerts: list[dict[str, Any]] = []
    for row in board.get("items") or []:
        if _text(row.get("status")) not in OPEN_STATUSES:
            continue
        severity = _text(row.get("severity"))
        level = "warning" if severity in {"critical", "high"} else "info"
        alerts.append(
            {
                "level": level,
                "kind": f"paper_ops_escalation_{severity or 'open'}",
                "title": _text(row.get("title") or "Open paper ops escalation"),
                "detail": f"{row.get('status')} escalation owned by {row.get('owner') or 'unassigned'}: {row.get('note') or row.get('recommended_action_at_escalation')}",
                "market_id": row.get("market_id"),
                "question": row.get("question"),
                "source": "paper_ops_escalation_v052",
                "link": "/paper-ops-escalations",
            }
        )
    for row in board.get("candidates") or []:
        severity = _text(row.get("recommended_escalation_severity"))
        if severity not in {"critical", "high"}:
            continue
        alerts.append(
            {
                "level": "warning",
                "kind": "paper_ops_escalation_candidate",
                "title": _text(row.get("title") or "Paper ops escalation candidate"),
                "detail": f"{row.get('source_severity')} aging item should be escalated or explicitly deferred.",
                "market_id": row.get("market_id"),
                "question": row.get("title"),
                "source": "paper_ops_escalation_v052",
                "link": "/paper-ops-escalations",
            }
        )
    return alerts[:25]


def ops_escalations_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "escalation_id",
        "created_at",
        "updated_at",
        "aging_item_id",
        "status",
        "severity",
        "owner",
        "section",
        "source_status",
        "source_severity",
        "market_id",
        "ticket_id",
        "title",
        "question",
        "age_hours_at_escalation",
        "handoff_count_at_escalation",
        "recommended_action_at_escalation",
        "note",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()
