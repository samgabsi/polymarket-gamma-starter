from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ai_edge_schemas import AI_EDGE_SAFETY_STATEMENT, base_safety, record_id
from .config import APP_VERSION, DATA_DIR
from .platform_safety import redact_data, redact_text, safety_flags

EDGE_DIR = DATA_DIR / "ai" / "edge"
CALIBRATION_RECORDS_PATH = EDGE_DIR / "calibration_records.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    EDGE_DIR.mkdir(parents=True, exist_ok=True)


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
            rows.append({"calibration_id": record_id("edge_calib_invalid"), "status": "invalid_json", "secret_values_returned": False})
    return rows


def _latest_by_id(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[str(row.get(key) or record_id("edge_calib"))] = row
    return sorted(latest.values(), key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)


def _clamp_probability(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def pending_record_for_packet(packet: dict[str, Any], *, write: bool = True) -> dict[str, Any]:
    probability = packet.get("probability_draft", {}) if isinstance(packet.get("probability_draft"), dict) else {}
    draft_probability = _clamp_probability(probability.get("fair_probability", probability.get("model_probability", 0.5)))
    record = {
        "calibration_id": f"edge_calib_{packet.get('packet_id', record_id('packet'))}",
        "packet_id": str(packet.get("packet_id") or ""),
        "created_at": _now(),
        "updated_at": _now(),
        "app_version": APP_VERSION,
        "provider": str(packet.get("provider") or "mock"),
        "market_id": str(packet.get("market_id") or ""),
        "market_title": str(packet.get("market_title") or ""),
        "status": "pending_outcome",
        "draft_probability": draft_probability,
        "outcome_recorded": False,
        "resolved_outcome": None,
        "brier_score": None,
        "calibration_tracking_is_research_only": True,
        "no_financial_advice": True,
        "no_trade_approval": True,
        "no_live_mutation": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
        "safety_statement": AI_EDGE_SAFETY_STATEMENT,
    }
    if write:
        _write_jsonl(CALIBRATION_RECORDS_PATH, record)
    return safety_flags(record)


def record_outcome(payload: dict[str, Any] | None = None, *, write: bool = True) -> dict[str, Any]:
    payload = payload or {}
    packet_id = redact_text(payload.get("packet_id") or "")
    existing = next((row for row in _latest_by_id(_read_jsonl(CALIBRATION_RECORDS_PATH), "calibration_id") if row.get("packet_id") == packet_id), {})
    draft_probability = _clamp_probability(payload.get("draft_probability", existing.get("draft_probability", 0.5)))
    outcome_raw = payload.get("resolved_outcome", payload.get("outcome", payload.get("actual_outcome")))
    if isinstance(outcome_raw, str):
        outcome = outcome_raw.strip().lower() in {"1", "true", "yes", "win", "resolved_yes"}
    else:
        outcome = bool(outcome_raw)
    brier = (draft_probability - (1.0 if outcome else 0.0)) ** 2
    record = {
        "calibration_id": str(existing.get("calibration_id") or payload.get("calibration_id") or f"edge_calib_{packet_id or record_id('manual')}"),
        "packet_id": packet_id,
        "created_at": existing.get("created_at") or _now(),
        "updated_at": _now(),
        "resolved_at": redact_text(payload.get("resolved_at") or _now()),
        "app_version": APP_VERSION,
        "provider": str(payload.get("provider") or existing.get("provider") or "unknown"),
        "market_id": str(payload.get("market_id") or existing.get("market_id") or ""),
        "market_title": str(payload.get("market_title") or existing.get("market_title") or ""),
        "status": "resolved",
        "draft_probability": draft_probability,
        "outcome_recorded": True,
        "resolved_outcome": outcome,
        "brier_score": round(brier, 6),
        "operator_notes": redact_text(payload.get("operator_notes") or payload.get("notes") or ""),
        "calibration_tracking_is_research_only": True,
        "no_financial_advice": True,
        "no_trade_approval": True,
        "no_live_mutation": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
        "safety_statement": AI_EDGE_SAFETY_STATEMENT,
    }
    if write:
        _write_jsonl(CALIBRATION_RECORDS_PATH, record)
    return safety_flags({"ok": True, "record": record, "write": write, **base_safety()})


def list_records(limit: int = 250, status: str | None = None) -> dict[str, Any]:
    rows = _latest_by_id(_read_jsonl(CALIBRATION_RECORDS_PATH), "calibration_id")
    if status:
        rows = [row for row in rows if row.get("status") == status]
    capped = rows[: max(1, min(int(limit or 250), 5000))]
    return safety_flags({"version": APP_VERSION, "count": len(capped), "total_count": len(rows), "items": capped, **base_safety()})


def calibration_summary() -> dict[str, Any]:
    rows = list_records(limit=5000)["items"]
    resolved = [row for row in rows if row.get("outcome_recorded") is True and row.get("brier_score") is not None]
    avg_brier = round(sum(float(row.get("brier_score") or 0) for row in resolved) / len(resolved), 6) if resolved else None
    by_provider: dict[str, dict[str, Any]] = {}
    for row in rows:
        provider = str(row.get("provider") or "unknown")
        bucket = by_provider.setdefault(provider, {"count": 0, "resolved_count": 0, "avg_brier_score": None, "brier_total": 0.0})
        bucket["count"] += 1
        if row.get("outcome_recorded") is True and row.get("brier_score") is not None:
            bucket["resolved_count"] += 1
            bucket["brier_total"] += float(row.get("brier_score") or 0)
    for bucket in by_provider.values():
        if bucket["resolved_count"]:
            bucket["avg_brier_score"] = round(bucket["brier_total"] / bucket["resolved_count"], 6)
        bucket.pop("brier_total", None)
    return safety_flags({
        "version": APP_VERSION,
        "record_count": len(rows),
        "pending_count": len([row for row in rows if row.get("status") == "pending_outcome"]),
        "resolved_count": len(resolved),
        "avg_brier_score": avg_brier,
        "by_provider": by_provider,
        "calibration_is_research_only": True,
        **base_safety(),
    })


def export_json() -> dict[str, Any]:
    return safety_flags({"version": APP_VERSION, "summary": calibration_summary(), "records": list_records(limit=5000), **base_safety()})


def export_markdown() -> str:
    data = export_json()
    lines = [
        f"# AI Edge Calibration Export - {APP_VERSION}",
        "",
        AI_EDGE_SAFETY_STATEMENT,
        "",
        f"- Records: `{data['summary']['record_count']}`",
        f"- Resolved: `{data['summary']['resolved_count']}`",
        f"- Average Brier score: `{data['summary']['avg_brier_score']}`",
        "",
    ]
    for item in data["records"]["items"]:
        lines.append(f"- `{item.get('calibration_id')}` packet `{item.get('packet_id')}` status `{item.get('status')}` probability `{item.get('draft_probability')}` brier `{item.get('brier_score')}`")
    if not data["records"]["items"]:
        lines.append("- No calibration records yet.")
    return "\n".join(lines) + "\n"


def export_csv() -> str:
    rows = list_records(limit=5000)["items"]
    out = io.StringIO()
    fields = ["calibration_id", "packet_id", "provider", "market_id", "status", "draft_probability", "outcome_recorded", "resolved_outcome", "brier_score", "no_trade_approval", "no_live_mutation"]
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return out.getvalue()
