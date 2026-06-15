from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .paper_briefing import build_paper_ops_briefing
from .paper_handoff import build_operator_handoff_reconciliation_board
from .paper_ops_aging import build_paper_ops_aging
from .paper_ops_escalations import build_ops_escalation_board
from .paper_ops_escalation_review import build_ops_escalation_review

FOLLOWUP_BRIEFING_STATUSES = {"ready", "action_required", "blocked", "review", "watch"}
ACTIONABLE_AGING_SEVERITIES = {"critical", "stale", "followup", "repeat", "unknown_age"}
ACTIONABLE_ESCALATION_STATES = {"active_followup", "verify_resolution", "deescalation_candidate", "closed_but_reappeared"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _row(
    *,
    source: str,
    source_id: str,
    title: str,
    status: str,
    severity: str,
    priority: int,
    recommended_action: str,
    detail: str = "",
    market_id: str = "",
    ticket_id: str = "",
    owner: str = "",
    link: str = "",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handoff_required = status in {"blocked", "action_required", "active_followup", "verify_resolution", "closed_but_reappeared", "followup_required", "open", "investigating", "waiting", "candidate"} or severity in {"critical", "high", "stale", "followup", "repeat"}
    return {
        "version": "0.5.3-paper-ops-closeout-v1",
        "mode": "paper_ops_closeout_item_v053",
        "source": source,
        "source_id": _text(source_id),
        "title": _text(title or source_id or source),
        "status": _text(status or "review"),
        "severity": _text(severity or "info"),
        "priority": int(priority),
        "recommended_action": _text(recommended_action or "review_before_closeout"),
        "detail": _text(detail),
        "market_id": _text(market_id),
        "ticket_id": _text(ticket_id),
        "owner": _text(owner or "unassigned"),
        "link": _text(link),
        "handoff_required": bool(handoff_required),
        "closure_gate": "requires_operator_followup" if handoff_required else "can_be_summarized_in_closeout",
        "data": data or {},
        "guardrail": "Paper ops closeout rows are read-only local workflow checklist items and do not approve, execute, settle, or advise trades.",
    }


def _briefing_rows(report: dict[str, Any], *, max_items: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in report.get("items") or []:
        status = _text(item.get("status"))
        if status not in FOLLOWUP_BRIEFING_STATUSES:
            continue
        priority = _safe_int(item.get("priority"), 50)
        if status == "blocked":
            priority += 30
        elif status == "action_required":
            priority += 20
        elif status == "ready":
            priority += 10
        source_id = _text(item.get("briefing_item_id"))
        rows.append(
            _row(
                source="briefing",
                source_id=source_id,
                title=_text(item.get("title") or source_id),
                status=status,
                severity="warning" if status in {"blocked", "action_required"} else "info",
                priority=priority,
                recommended_action=_text(item.get("recommended_action") or "review_briefing_item"),
                detail=_text(item.get("detail")),
                market_id=_text(item.get("market_id")),
                ticket_id=_text(item.get("ticket_id")),
                link="/paper-ops-briefing",
                data=item,
            )
        )
    return rows[:max_items]


def _aging_rows(report: dict[str, Any], *, max_items: int) -> list[dict[str, Any]]:
    priority_map = {"critical": 110, "stale": 95, "followup": 90, "repeat": 85, "unknown_age": 70, "fresh": 30}
    rows: list[dict[str, Any]] = []
    for item in report.get("items") or []:
        severity = _text(item.get("severity"))
        if severity not in ACTIONABLE_AGING_SEVERITIES:
            continue
        age_bonus = min(20, int(_safe_float(item.get("age_hours")) // 12)) if item.get("age_hours") is not None else 0
        handoff_bonus = min(15, _safe_int(item.get("handoff_count")) * 3)
        source_id = _text(item.get("aging_item_id"))
        rows.append(
            _row(
                source="aging",
                source_id=source_id,
                title=_text(item.get("title") or source_id),
                status=_text(item.get("status") or "review"),
                severity=severity,
                priority=priority_map.get(severity, 50) + age_bonus + handoff_bonus,
                recommended_action=_text(item.get("recommended_action") or "review_aging_item"),
                detail=_text(item.get("detail")),
                market_id=_text(item.get("market_id")),
                ticket_id=_text(item.get("ticket_id")),
                link=f"/paper-ops-aging?item_id={source_id}",
                data=item,
            )
        )
    return rows[:max_items]


def _handoff_reconciliation_rows(report: dict[str, Any], *, max_items: int) -> list[dict[str, Any]]:
    priority_map = {"followup_required": 88, "verify_clearance": 70, "cleared_review": 30, "no_saved_items": 10}
    rows: list[dict[str, Any]] = []
    for item in report.get("items") or []:
        status = _text(item.get("reconciliation_state") or item.get("reconciliation_status") or item.get("status"))
        followup_count = _safe_int(item.get("followup_required"))
        followup_required = followup_count > 0 or status in {"followup_required", "still_open", "changed_open"}
        verify_clearance = _safe_int(item.get("not_visible")) > 0 or status == "verify_clearance"
        if not followup_required and not verify_clearance:
            continue
        source_id = _text(item.get("handoff_id") or item.get("source_id"))
        detail = f"saved={item.get('saved_item_count', 0)} still_open={item.get('still_open', 0)} changed={item.get('changed_open', 0)} not_visible={item.get('not_visible', 0)}"
        rows.append(
            _row(
                source="handoff_reconciliation",
                source_id=source_id,
                title=f"Handoff reconciliation: {source_id}",
                status=status or "review",
                severity="warning" if followup_required else "info",
                priority=priority_map.get(status, 55) + min(10, followup_count * 2),
                recommended_action=_text(item.get("recommended_action") or "review_handoff_reconciliation"),
                detail=detail,
                market_id=_text(item.get("market_id")),
                ticket_id=_text(item.get("ticket_id")),
                link=f"/paper-handoff-reconciliation?handoff_id={source_id}",
                data=item,
            )
        )
    return rows[:max_items]


def _escalation_rows(board: dict[str, Any], *, max_items: int) -> list[dict[str, Any]]:
    priority_map = {"critical": 115, "high": 100, "medium": 80, "low": 55, "info": 35}
    rows: list[dict[str, Any]] = []
    for item in board.get("items") or []:
        status = _text(item.get("status"))
        if status not in {"open", "investigating", "waiting"}:
            continue
        severity = _text(item.get("severity"))
        source_id = _text(item.get("escalation_id"))
        rows.append(
            _row(
                source="escalation",
                source_id=source_id,
                title=_text(item.get("title") or item.get("question") or source_id),
                status=status,
                severity=severity,
                priority=priority_map.get(severity, 65),
                recommended_action=_text(item.get("recommended_action_at_escalation") or item.get("note") or "continue_escalation_followup"),
                detail=_text(item.get("note")),
                market_id=_text(item.get("market_id")),
                ticket_id=_text(item.get("ticket_id")),
                owner=_text(item.get("owner")),
                link=f"/paper-ops-escalations?escalation_id={source_id}",
                data=item,
            )
        )
    for candidate in board.get("candidates") or []:
        severity = _text(candidate.get("recommended_escalation_severity"))
        if severity not in {"critical", "high"}:
            continue
        source_id = _text(candidate.get("aging_item_id"))
        rows.append(
            _row(
                source="escalation_candidate",
                source_id=source_id,
                title=_text(candidate.get("title") or source_id),
                status="candidate",
                severity=severity,
                priority=priority_map.get(severity, 70) - 5,
                recommended_action=_text(candidate.get("recommended_action") or "escalate_or_explicitly_defer"),
                detail=f"Aging severity {candidate.get('source_severity')}; handoffs {candidate.get('handoff_count')}",
                market_id=_text(candidate.get("market_id")),
                ticket_id=_text(candidate.get("ticket_id")),
                link=f"/paper-ops-aging?item_id={source_id}",
                data=candidate,
            )
        )
    return rows[:max_items]


def _escalation_review_rows(report: dict[str, Any], *, max_items: int) -> list[dict[str, Any]]:
    priority_map = {"closed_but_reappeared": 120, "active_followup": 105, "verify_resolution": 80, "deescalation_candidate": 60, "closed_record": 15}
    rows: list[dict[str, Any]] = []
    for item in report.get("items") or []:
        state = _text(item.get("review_state"))
        if state not in ACTIONABLE_ESCALATION_STATES:
            continue
        source_id = _text(item.get("escalation_id"))
        rows.append(
            _row(
                source="escalation_review",
                source_id=source_id,
                title=_text(item.get("title") or source_id),
                status=state,
                severity=_text(item.get("escalation_severity") or "info"),
                priority=priority_map.get(state, 50),
                recommended_action=_text(item.get("recommended_action") or "review_escalation_reconciliation"),
                detail=f"Escalation {item.get('escalation_status')} / current aging {item.get('current_severity') or 'not visible'}",
                market_id=_text(item.get("market_id")),
                ticket_id=_text(item.get("ticket_id")),
                owner=_text(item.get("owner")),
                link=f"/paper-ops-escalation-review?escalation_id={source_id}",
                data=item,
            )
        )
    return rows[:max_items]


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    source: str | None = None,
    status: str | None = None,
    market_id: str | None = None,
    handoff_required: bool | None = None,
) -> list[dict[str, Any]]:
    if source:
        wanted = _text(source)
        rows = [row for row in rows if _text(row.get("source")) == wanted]
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted]
    if handoff_required is not None:
        rows = [row for row in rows if bool(row.get("handoff_required")) is handoff_required]
    return rows


def summarize_ops_closeout(
    rows: list[dict[str, Any]],
    *,
    briefing: dict[str, Any],
    aging: dict[str, Any],
    handoff_reconciliation: dict[str, Any],
    escalations: dict[str, Any],
    escalation_review: dict[str, Any],
) -> dict[str, Any]:
    sources = Counter(_text(row.get("source") or "unknown") for row in rows)
    statuses = Counter(_text(row.get("status") or "unknown") for row in rows)
    severities = Counter(_text(row.get("severity") or "unknown") for row in rows)
    markets = {_text(row.get("market_id")) for row in rows if row.get("market_id")}
    handoff_required_count = sum(1 for row in rows if row.get("handoff_required"))

    briefing_summary = briefing.get("summary", {}) if isinstance(briefing, dict) else {}
    aging_summary = aging.get("summary", {}) if isinstance(aging, dict) else {}
    handoff_summary = handoff_reconciliation.get("summary", {}) if isinstance(handoff_reconciliation, dict) else {}
    escalation_summary = escalations.get("summary", {}) if isinstance(escalations, dict) else {}
    escalation_candidate_summary = escalations.get("candidate_summary", {}) if isinstance(escalations, dict) else {}
    escalation_review_summary = escalation_review.get("summary", {}) if isinstance(escalation_review, dict) else {}

    blocked = _safe_int(briefing_summary.get("blocked"))
    action_required = _safe_int(briefing_summary.get("action_required"))
    critical_aging = _safe_int(aging_summary.get("critical"))
    stale_aging = _safe_int(aging_summary.get("stale"))
    open_escalations = _safe_int(escalation_summary.get("open"))
    closed_but_reappeared = _safe_int(escalation_review_summary.get("closed_but_reappeared"))

    if blocked or critical_aging or closed_but_reappeared:
        closeout_status = "blocked"
        closeout_message = "Resolve or explicitly hand off blocked, critical, or reappeared items before ending the operator pass."
    elif action_required or stale_aging or open_escalations or handoff_required_count:
        closeout_status = "attention"
        closeout_message = "Prepare a handoff/checkpoint for unresolved paper-ops follow-up before closeout."
    else:
        closeout_status = "clear"
        closeout_message = "No high-priority unresolved paper-ops closeout items matched the current filters."

    return {
        "count": len(rows),
        "closeout_status": closeout_status,
        "closeout_message": closeout_message,
        "handoff_required": handoff_required_count,
        "can_summarize": len(rows) - handoff_required_count,
        "market_count": len(markets),
        "by_source": dict(sorted(sources.items())),
        "by_status": dict(sorted(statuses.items())),
        "by_severity": dict(sorted(severities.items())),
        "briefing_blocked": blocked,
        "briefing_action_required": action_required,
        "aging_critical": critical_aging,
        "aging_stale": stale_aging,
        "handoff_reconciliation_followup": _safe_int(handoff_summary.get("followup_required_count")),
        "open_escalations": open_escalations,
        "escalation_candidates": _safe_int(escalation_candidate_summary.get("count")),
        "escalation_review_required": _safe_int(escalation_review_summary.get("review_required")),
        "closed_but_reappeared": closed_but_reappeared,
        "guardrail": "Closeout summary is workflow hygiene only. It does not close records, approve tickets, execute paper trades, or provide investment advice.",
    }


def build_paper_ops_closeout(
    *,
    limit: int = 100,
    source: str | None = None,
    status: str | None = None,
    market_id: str | None = None,
    handoff_required: bool | None = None,
) -> dict[str, Any]:
    scan_limit = max(100, min(10000, int(limit) * 5))
    briefing = build_paper_ops_briefing(limit=scan_limit, market_id=market_id)
    aging = build_paper_ops_aging(limit=scan_limit, market_id=market_id)
    handoff_reconciliation = build_operator_handoff_reconciliation_board(limit=scan_limit, market_id=market_id)
    escalations = build_ops_escalation_board(limit=scan_limit, market_id=market_id, include_candidates=True)
    escalation_review = build_ops_escalation_review(limit=scan_limit, market_id=market_id)

    rows: list[dict[str, Any]] = []
    rows.extend(_briefing_rows(briefing, max_items=scan_limit))
    rows.extend(_aging_rows(aging, max_items=scan_limit))
    rows.extend(_handoff_reconciliation_rows(handoff_reconciliation, max_items=scan_limit))
    rows.extend(_escalation_rows(escalations, max_items=scan_limit))
    rows.extend(_escalation_review_rows(escalation_review, max_items=scan_limit))

    rows = _filter_rows(rows, source=source, status=status, market_id=market_id, handoff_required=handoff_required)
    rows.sort(key=lambda row: (_safe_int(row.get("priority")), _text(row.get("source")), _text(row.get("source_id"))), reverse=True)
    rows = rows[: max(0, int(limit))]

    return {
        "version": "0.5.3-paper-ops-closeout-v1",
        "mode": "paper_ops_closeout_board_v053",
        "generated_at": _now(),
        "summary": summarize_ops_closeout(rows, briefing=briefing, aging=aging, handoff_reconciliation=handoff_reconciliation, escalations=escalations, escalation_review=escalation_review),
        "items": rows,
        "filters": {"source": source or "", "status": status or "", "market_id": market_id or "", "handoff_required": "" if handoff_required is None else bool(handoff_required)},
        "component_summaries": {
            "briefing": briefing.get("summary", {}),
            "aging": aging.get("summary", {}),
            "handoff_reconciliation": handoff_reconciliation.get("summary", {}),
            "escalations": escalations.get("summary", {}),
            "escalation_candidates": escalations.get("candidate_summary", {}),
            "escalation_review": escalation_review.get("summary", {}),
        },
        "guardrail": "Paper ops closeout is a read-only local end-of-shift checklist. It never creates handoffs, closes escalations, approves tickets, settles positions, connects wallets, signs messages, or places live orders.",
    }


def paper_ops_closeout_alerts(report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    report = report or build_paper_ops_closeout(limit=25)
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    alerts: list[dict[str, Any]] = []
    status = _text(summary.get("closeout_status"))
    if status in {"blocked", "attention"}:
        alerts.append(
            {
                "level": "warning" if status == "blocked" else "info",
                "kind": f"paper_ops_closeout_{status}",
                "title": "Paper ops closeout needs review",
                "detail": _text(summary.get("closeout_message")),
                "market_id": None,
                "question": None,
                "source": "paper_ops_closeout_v053",
                "link": "/paper-ops-closeout",
            }
        )
    for row in report.get("items", [])[:10]:
        if not row.get("handoff_required"):
            continue
        alerts.append(
            {
                "level": "warning" if _text(row.get("severity")) in {"critical", "stale", "high"} or _text(row.get("status")) == "blocked" else "info",
                "kind": f"paper_ops_closeout_{row.get('source')}",
                "title": _text(row.get("title") or "Paper ops closeout item"),
                "detail": _text(row.get("recommended_action")),
                "market_id": row.get("market_id"),
                "question": row.get("title"),
                "source": "paper_ops_closeout_v053",
                "link": row.get("link") or "/paper-ops-closeout",
            }
        )
    return alerts[:25]


def paper_ops_closeout_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "source",
        "source_id",
        "title",
        "status",
        "severity",
        "priority",
        "recommended_action",
        "detail",
        "market_id",
        "ticket_id",
        "owner",
        "handoff_required",
        "closure_gate",
        "link",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()
