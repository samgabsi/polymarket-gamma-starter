from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .paper_briefing import build_paper_ops_briefing
from .paper_handoff import list_operator_handoffs

UNRESOLVED_STATUSES = {"ready", "action_required", "blocked", "review", "watch"}
AGING_THRESHOLDS_HOURS = {
    "ready": 12.0,
    "action_required": 12.0,
    "blocked": 24.0,
    "review": 48.0,
    "watch": 72.0,
}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = _text(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _candidate_times(row: dict[str, Any]) -> list[tuple[str, datetime]]:
    candidates: list[tuple[str, datetime]] = []

    def add(label: str, value: Any) -> None:
        parsed = _parse_dt(value)
        if parsed:
            candidates.append((label, parsed))

    add("briefing_item.created_at", row.get("created_at"))
    add("briefing_item.updated_at", row.get("updated_at"))
    add("metrics.latest_approval_at", (row.get("metrics") or {}).get("latest_approval_at"))

    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    for key in ("created_at", "updated_at", "latest_approval_at", "last_trade_at", "settled_at"):
        add(f"data.{key}", data.get(key))

    ticket = data.get("ticket_snapshot") if isinstance(data.get("ticket_snapshot"), dict) else {}
    for key in ("created_at", "updated_at"):
        add(f"ticket_snapshot.{key}", ticket.get(key))

    approval = data.get("latest_approval") if isinstance(data.get("latest_approval"), dict) else {}
    add("latest_approval.created_at", approval.get("created_at"))

    ack = data.get("latest_acknowledgement") if isinstance(data.get("latest_acknowledgement"), dict) else {}
    add("latest_acknowledgement.created_at", ack.get("created_at"))

    # Some nested rows carry the original payload one level deeper.
    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
    for key in ("created_at", "updated_at", "latest_approval_at", "last_trade_at"):
        add(f"data.data.{key}", nested.get(key))
    nested_ticket = nested.get("ticket_snapshot") if isinstance(nested.get("ticket_snapshot"), dict) else {}
    for key in ("created_at", "updated_at"):
        add(f"data.data.ticket_snapshot.{key}", nested_ticket.get(key))

    return candidates


def _age_hours(origin: datetime | None, now: datetime) -> float | None:
    if not origin:
        return None
    return max(0.0, round((now - origin).total_seconds() / 3600.0, 2))


def _handoff_index(*, limit: int = 10000) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for handoff in list_operator_handoffs(limit=limit):
        created_at = _text(handoff.get("created_at"))
        created_dt = _parse_dt(created_at)
        status = _text(handoff.get("status"))
        handoff_id = _text(handoff.get("handoff_id"))
        for item in handoff.get("handoff_items") or []:
            item_id = _text(item.get("briefing_item_id"))
            if not item_id:
                continue
            entry = index.setdefault(
                item_id,
                {
                    "handoff_count": 0,
                    "first_handoff_at": "",
                    "last_handoff_at": "",
                    "first_handoff_dt": None,
                    "last_handoff_dt": None,
                    "last_handoff_id": "",
                    "last_handoff_status": "",
                    "open_handoff_count": 0,
                    "needs_followup_handoff_count": 0,
                },
            )
            entry["handoff_count"] += 1
            if status == "open":
                entry["open_handoff_count"] += 1
            if status == "needs_followup":
                entry["needs_followup_handoff_count"] += 1
            if created_dt and (entry["first_handoff_dt"] is None or created_dt < entry["first_handoff_dt"]):
                entry["first_handoff_dt"] = created_dt
                entry["first_handoff_at"] = created_at
            if created_dt and (entry["last_handoff_dt"] is None or created_dt > entry["last_handoff_dt"]):
                entry["last_handoff_dt"] = created_dt
                entry["last_handoff_at"] = created_at
                entry["last_handoff_id"] = handoff_id
                entry["last_handoff_status"] = status
    return index


def _severity_for(*, status: str, age_hours: float | None, handoff_count: int, needs_followup_count: int) -> str:
    threshold = AGING_THRESHOLDS_HOURS.get(status, 48.0)
    if needs_followup_count:
        return "followup"
    if age_hours is None:
        return "repeat" if handoff_count >= 2 else "unknown_age"
    if status == "blocked" and age_hours >= threshold:
        return "critical"
    if age_hours >= threshold * 2:
        return "critical"
    if age_hours >= threshold:
        return "stale"
    if handoff_count >= 2:
        return "repeat"
    return "fresh"


def _recommended_action(row: dict[str, Any], severity: str) -> str:
    status = _text(row.get("status"))
    section = _text(row.get("section"))
    if severity in {"critical", "stale", "followup", "repeat"}:
        if status == "blocked":
            return "clear_or_escalate_blocker_before_next_operator_pass"
        if status == "action_required":
            return "complete_operator_action_or_record_followup_reason"
        if status == "ready":
            return "execute_or_hold_with_explicit_operator_note"
        if section == "post_trade_review":
            return "write_or_close_review_lesson"
        if section == "risk_budget":
            return "resolve_budget_flag_or_reduce_pending_exposure"
        if section == "playbook_performance":
            return "review_playbook_noise_and_update_process_if_needed"
        return "review_and_acknowledge_aging_work_item"
    if severity == "unknown_age":
        return "verify_source_timestamp_or_capture_handoff_checkpoint"
    return _text(row.get("recommended_action") or "monitor_current_paper_ops_item")


def _aging_item(row: dict[str, Any], handoff: dict[str, Any], now: datetime) -> dict[str, Any]:
    status = _text(row.get("status"))
    candidates = _candidate_times(row)
    source_label = ""
    origin = None
    if candidates:
        source_label, origin = min(candidates, key=lambda pair: pair[1])
    handoff_origin = handoff.get("first_handoff_dt")
    if handoff_origin and (origin is None or handoff_origin < origin):
        source_label = "first_handoff_at"
        origin = handoff_origin
    age = _age_hours(origin, now)
    handoff_count = _safe_int(handoff.get("handoff_count"))
    needs_followup_count = _safe_int(handoff.get("needs_followup_handoff_count"))
    severity = _severity_for(status=status, age_hours=age, handoff_count=handoff_count, needs_followup_count=needs_followup_count)
    threshold = AGING_THRESHOLDS_HOURS.get(status, 48.0)
    return {
        "aging_item_id": _text(row.get("briefing_item_id")),
        "version": "0.5.0-paper-ops-aging-v1",
        "mode": "paper_ops_aging_v050",
        "section": _text(row.get("section")),
        "status": status,
        "severity": severity,
        "priority": _safe_int(row.get("priority")),
        "age_hours": age,
        "age_days": None if age is None else round(age / 24.0, 2),
        "threshold_hours": threshold,
        "origin_at": origin.isoformat() if origin else "",
        "origin_source": source_label,
        "title": _text(row.get("title") or row.get("briefing_item_id")),
        "recommended_action": _recommended_action(row, severity),
        "current_recommended_action": _text(row.get("recommended_action")),
        "detail": _text(row.get("detail")),
        "market_id": _text(row.get("market_id")),
        "ticket_id": _text(row.get("ticket_id")),
        "source_id": _text(row.get("source_id")),
        "question": _text(row.get("question") or row.get("title")),
        "handoff_count": handoff_count,
        "open_handoff_count": _safe_int(handoff.get("open_handoff_count")),
        "needs_followup_handoff_count": needs_followup_count,
        "first_handoff_at": _text(handoff.get("first_handoff_at")),
        "last_handoff_at": _text(handoff.get("last_handoff_at")),
        "last_handoff_id": _text(handoff.get("last_handoff_id")),
        "last_handoff_status": _text(handoff.get("last_handoff_status")),
        "links": row.get("links") or {},
        "metrics": row.get("metrics") or {},
        "briefing_item": row,
        "guardrail": "Paper ops aging rows are read-only local workflow diagnostics. They do not approve, execute, or advise trades.",
    }


def summarize_ops_aging(items: list[dict[str, Any]], *, source_count: int) -> dict[str, Any]:
    statuses = Counter(_text(row.get("status") or "unknown") for row in items)
    severities = Counter(_text(row.get("severity") or "unknown") for row in items)
    sections = Counter(_text(row.get("section") or "unknown") for row in items)
    markets = {_text(row.get("market_id")) for row in items if row.get("market_id")}
    max_age = max([_safe_float(row.get("age_hours")) for row in items if row.get("age_hours") is not None], default=0.0)
    stale_or_worse = sum(severities.get(key, 0) for key in ("stale", "critical", "followup", "repeat"))
    return {
        "count": len(items),
        "source_unresolved_count": source_count,
        "market_count": len(markets),
        "by_status": dict(sorted(statuses.items())),
        "by_severity": dict(sorted(severities.items())),
        "by_section": dict(sorted(sections.items())),
        "critical": severities.get("critical", 0),
        "stale": severities.get("stale", 0),
        "followup": severities.get("followup", 0),
        "repeat": severities.get("repeat", 0),
        "fresh": severities.get("fresh", 0),
        "unknown_age": severities.get("unknown_age", 0),
        "stale_or_worse": stale_or_worse,
        "max_age_hours": round(max_age, 2),
        "guardrail": "Aging summary is a local workflow hygiene report only, not a trading signal or execution authorization.",
    }


def build_paper_ops_aging(
    *,
    limit: int = 100,
    section: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    market_id: str | None = None,
    min_age_hours: float | None = None,
) -> dict[str, Any]:
    now = _now_dt()
    briefing = build_paper_ops_briefing(limit=1000, section=section, status=status, market_id=market_id)
    source_items = [row for row in (briefing.get("items") or []) if _text(row.get("status")) in UNRESOLVED_STATUSES]
    handoffs = _handoff_index()
    items = [_aging_item(row, handoffs.get(_text(row.get("briefing_item_id")), {}), now) for row in source_items]
    if severity:
        wanted = _text(severity)
        items = [row for row in items if _text(row.get("severity")) == wanted]
    if min_age_hours is not None:
        minimum = _safe_float(min_age_hours)
        items = [row for row in items if row.get("age_hours") is not None and _safe_float(row.get("age_hours")) >= minimum]
    items.sort(
        key=lambda row: (
            {"critical": 5, "followup": 4, "stale": 3, "repeat": 2, "unknown_age": 1, "fresh": 0}.get(_text(row.get("severity")), 0),
            _safe_float(row.get("age_hours")),
            _safe_int(row.get("priority")),
            _text(row.get("aging_item_id")),
        ),
        reverse=True,
    )
    items = items[: max(0, int(limit))]
    return {
        "version": "0.5.0-paper-ops-aging-v1",
        "mode": "paper_ops_aging_v050",
        "generated_at": _now(),
        "summary": summarize_ops_aging(items, source_count=len(source_items)),
        "items": items,
        "filters": {
            "section": section or "",
            "status": status or "",
            "severity": severity or "",
            "market_id": market_id or "",
            "min_age_hours": min_age_hours,
        },
        "thresholds_hours": dict(AGING_THRESHOLDS_HOURS),
        "briefing_summary": briefing.get("summary", {}),
        "guardrail": "Paper ops aging is a read-only local workflow hygiene report. It never changes approvals, tickets, positions, handoffs, paper trades, or live trading state.",
    }


def build_ops_aging_detail(item_id: str) -> dict[str, Any] | None:
    report = build_paper_ops_aging(limit=10000)
    wanted = _text(item_id)
    for row in report.get("items") or []:
        if _text(row.get("aging_item_id")) == wanted:
            return {
                "version": "0.5.0-paper-ops-aging-v1",
                "mode": "paper_ops_aging_detail_v050",
                "generated_at": _now(),
                "item": row,
                "thresholds_hours": dict(AGING_THRESHOLDS_HOURS),
                "guardrail": "Paper ops aging detail is read-only workflow context only.",
            }
    return None


def ops_aging_alerts(report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    report = report or build_paper_ops_aging(limit=50)
    alerts: list[dict[str, Any]] = []
    for row in report.get("items") or []:
        severity = _text(row.get("severity"))
        if severity not in {"critical", "stale", "followup", "repeat"}:
            continue
        level = "warning" if severity in {"critical", "stale", "followup"} else "info"
        alerts.append(
            {
                "level": level,
                "kind": f"paper_ops_aging_{severity}",
                "title": _text(row.get("title") or "Aging paper ops item"),
                "detail": f"{severity}: age={row.get('age_hours') if row.get('age_hours') is not None else 'unknown'}h; action={row.get('recommended_action')}",
                "market_id": row.get("market_id"),
                "question": row.get("question"),
                "source": "paper_ops_aging_v050",
                "link": "/paper-ops-aging",
            }
        )
    return alerts[:25]


def ops_aging_to_csv(items: list[dict[str, Any]]) -> str:
    fields = [
        "aging_item_id",
        "section",
        "status",
        "severity",
        "priority",
        "age_hours",
        "age_days",
        "threshold_hours",
        "origin_at",
        "origin_source",
        "title",
        "recommended_action",
        "market_id",
        "ticket_id",
        "handoff_count",
        "open_handoff_count",
        "needs_followup_handoff_count",
        "first_handoff_at",
        "last_handoff_at",
        "last_handoff_id",
        "last_handoff_status",
        "detail",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in items:
        writer.writerow(row)
    return buf.getvalue()
