from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .live_v2 import record_audit, redact_data, redact_text

ANALYTICS_DIR = DATA_DIR / "live_v3" / "analytics"
ANALYTICS_EVENTS_PATH = ANALYTICS_DIR / "analytics_events.jsonl"
ANALYTICS_SNAPSHOTS_PATH = ANALYTICS_DIR / "analytics_snapshots.jsonl"
ANALYTICS_REPORTS_PATH = ANALYTICS_DIR / "learning_reports.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_text(value: Any, default: str = "") -> str:
    text = redact_text(str(value or "").strip())
    return text or default


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("items", value.get("records", value.get("checks", [])))
    if not isinstance(value, list):
        return []
    return [x for x in value if isinstance(x, dict)]


def _event(action: str, status: str = "ok", details: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_dir()
    event = redact_data({
        "event_id": f"analytics_evt_{uuid4().hex[:12]}",
        "timestamp": _now(),
        "app_version": APP_VERSION,
        "action": action,
        "status": status,
        "details": details or {},
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "analytics_are_descriptive": True,
        "secret_values_returned": False,
    })
    with ANALYTICS_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    record_audit(f"v3_analytics_{action}", status, details=event.get("details", {}), network_attempted=False)
    return event


def _collect() -> dict[str, Any]:
    # Imported lazily to avoid a module cycle during application import.
    from . import live_v3

    return live_v3._collect_local_data(limit=500)  # type: ignore[attr-defined]


def _obj_id(item: dict[str, Any]) -> str:
    for key in ("id", "thesis_id", "alert_id", "rule_id", "event_id", "source_id", "scenario_id", "checklist_id", "review_id"):
        if item.get(key):
            return _safe_text(item.get(key))
    return f"obj_{uuid4().hex[:10]}"


def _status(item: dict[str, Any]) -> str:
    return _safe_text(item.get("status") or item.get("state") or item.get("severity") or "unknown").lower()


def _direction(item: dict[str, Any]) -> str:
    return _safe_text(item.get("direction") or item.get("evidence_direction") or "").lower()


def _has_counter_evidence(rows: list[dict[str, Any]]) -> bool:
    return any("contradict" in _direction(x) or "counter" in _direction(x) for x in rows)


def _has_support(rows: list[dict[str, Any]]) -> bool:
    return any("support" in _direction(x) for x in rows)


def _group_by(items: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        value = _safe_text(item.get(key))
        if value:
            grouped.setdefault(value, []).append(item)
    return grouped


def _metric_record(kind: str, source: str, summary: dict[str, Any], related: list[str] | None = None, notes: str = "") -> dict[str, Any]:
    return redact_data({
        "id": f"analytics_{kind}_{uuid4().hex[:10]}",
        "created_at": _now(),
        "updated_at": _now(),
        "app_version": APP_VERSION,
        "analytics_type": kind,
        "source_subsystem": source,
        "related_object_ids": related or [],
        "input_data_summary": summary,
        "computed_metrics": summary,
        "unknown_unavailable_fields": summary.get("unknown_unavailable_fields", []),
        "interpretation_notes": notes,
        "operator_notes": "",
        "tags": ["analytics", kind, source],
        "audit_metadata": {"order_submitted": False, "order_cancelled": False, "live_trading_armed": False},
        "secret_values_returned": False,
    })


def decision_quality_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    journal = data.get("governance", {}).get("journal", [])
    checklists = data.get("governance", {}).get("checklists", [])
    reviews = data.get("governance", {}).get("reviews", [])
    reviewed_statuses = {"reviewed", "closed", "completed", "archived"}
    metrics = {
        "total_decisions": len(journal),
        "decisions_by_type": {},
        "decisions_reviewed": len([x for x in journal if _status(x) in reviewed_statuses]),
        "decisions_not_reviewed": len([x for x in journal if _status(x) not in reviewed_statuses]),
        "decisions_with_follow_up_completed": len([x for x in journal if _safe_text(x.get("follow_up_status")).lower() in {"done", "completed"}]),
        "decisions_with_linked_thesis": len([x for x in journal if x.get("related_thesis_id") or x.get("thesis_id")]),
        "decisions_with_linked_evidence": len([x for x in journal if x.get("related_evidence_id") or x.get("evidence_id")]),
        "decisions_with_counter_evidence_reviewed": len([x for x in journal if "counter" in _safe_text(x.get("decision_summary") or x.get("reasoning")).lower()]),
        "decisions_with_exit_criteria": len([x for x in journal if x.get("exit_criteria")]),
        "decisions_with_invalidation_criteria": len([x for x in journal if x.get("invalidation_criteria")]),
        "decisions_with_governance_checklist_completed": len([x for x in checklists if _status(x) == "completed"]),
        "no_trade_decisions": len([x for x in journal if "no-trade" in _safe_text(x.get("decision_type")).lower() or "no_trade" in _safe_text(x.get("decision_type")).lower()]),
        "emergency_decisions": len([x for x in journal if "emergency" in _safe_text(x.get("decision_type")).lower()]),
        "unresolved_decisions": len([x for x in journal if _status(x) in {"draft", "active", "open", "unresolved"}]),
        "overdue_followups": len([x for x in journal + reviews if _status(x) in {"overdue", "late"}]),
        "quality_indicators": {},
        "unknown_outcome_count": len([x for x in journal if not x.get("actual_outcome") and not x.get("outcome")]),
        "unknown_unavailable_fields": ["actual outcomes", "P&L", "fills"]
    }
    for row in journal:
        kind = _safe_text(row.get("decision_type"), "unknown")
        metrics["decisions_by_type"][kind] = metrics["decisions_by_type"].get(kind, 0) + 1
    total = max(1, metrics["total_decisions"])
    metrics["quality_indicators"] = {
        "evidence_completeness": round(metrics["decisions_with_linked_evidence"] / total, 4),
        "counter_evidence_coverage": round(metrics["decisions_with_counter_evidence_reviewed"] / total, 4),
        "governance_checklist_completeness": round(metrics["decisions_with_governance_checklist_completed"] / max(1, len(checklists)), 4),
        "review_completeness": round(metrics["decisions_reviewed"] / total, 4),
        "follow_through_completeness": round(metrics["decisions_with_follow_up_completed"] / total, 4),
    }
    return {"version": APP_VERSION, "generated_at": _now(), "metrics": redact_data(metrics), "records": [_metric_record("decision_quality", "governance", metrics)], "secret_values_returned": False}


def thesis_quality_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    theses = data.get("strategy", {}).get("theses", [])
    evidence = data.get("strategy", {}).get("evidence", []) + data.get("research", {}).get("candidates", [])
    alerts = data.get("monitoring", {}).get("alerts", [])
    exposure = data.get("portfolio", {}).get("exposure", [])
    reviews = data.get("governance", {}).get("reviews", []) + data.get("strategy", {}).get("reviews", [])
    evidence_by_thesis = _group_by(evidence, "thesis_id")
    metrics = {
        "active_theses": len([x for x in theses if _status(x) not in {"closed", "archived", "invalidated"}]),
        "closed_theses": len([x for x in theses if _status(x) in {"closed", "archived", "invalidated"}]),
        "reviewed_theses": len([x for x in theses if _status(x) in {"reviewed", "closed"}]),
        "stale_theses": len([x for x in theses if "stale" in _status(x)]),
        "theses_with_evidence": 0,
        "theses_without_evidence": 0,
        "theses_with_counter_evidence": 0,
        "theses_without_counter_evidence": 0,
        "theses_with_unresolved_research_questions": len(data.get("research", {}).get("queue", [])),
        "theses_linked_to_active_exposure": len({_safe_text(x.get("thesis_id")) for x in exposure if x.get("thesis_id")}),
        "theses_linked_to_alerts": len({_safe_text(x.get("related_thesis_id") or x.get("thesis_id")) for x in alerts if x.get("related_thesis_id") or x.get("thesis_id")}),
        "theses_linked_to_reviews": len({_safe_text(x.get("related_thesis_id") or x.get("thesis_id")) for x in reviews if x.get("related_thesis_id") or x.get("thesis_id")}),
        "theses_with_invalidation_criteria": len([x for x in theses if x.get("invalidation_criteria")]),
        "theses_without_invalidation_criteria": len([x for x in theses if not x.get("invalidation_criteria")]),
        "theses_with_exit_criteria": len([x for x in theses if x.get("exit_criteria")]),
        "theses_without_exit_criteria": len([x for x in theses if not x.get("exit_criteria")]),
        "thesis_confidence_changes_known": len([x for x in theses if x.get("confidence") or x.get("confidence_level")]),
        "status_counts": {"strong": 0, "needs_review": 0, "stale": 0, "incomplete": 0, "blocked": 0, "unknown": 0},
        "unknown_unavailable_fields": ["resolved outcomes unless operator recorded them"],
    }
    records = []
    for thesis in theses:
        tid = _safe_text(thesis.get("id") or thesis.get("thesis_id"))
        rows = evidence_by_thesis.get(tid, [])
        has_ev = bool(rows)
        has_counter = _has_counter_evidence(rows)
        metrics["theses_with_evidence"] += 1 if has_ev else 0
        metrics["theses_without_evidence"] += 0 if has_ev else 1
        metrics["theses_with_counter_evidence"] += 1 if has_counter else 0
        metrics["theses_without_counter_evidence"] += 0 if has_counter else 1
        quality_status = "strong" if has_ev and has_counter else "incomplete" if not has_ev else "needs_review"
        if "stale" in _status(thesis):
            quality_status = "stale"
        metrics["status_counts"][quality_status] += 1
        records.append(_metric_record("thesis_quality", "strategy", {"thesis_id": tid, "evidence_count": len(rows), "has_counter_evidence": has_counter, "quality_status": quality_status}, [tid]))
    return {"version": APP_VERSION, "generated_at": _now(), "metrics": redact_data(metrics), "records": records, "secret_values_returned": False}


def evidence_usefulness_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    evidence = data.get("strategy", {}).get("evidence", []) + data.get("research", {}).get("candidates", [])
    sources = data.get("research", {}).get("sources", [])
    metrics = {
        "evidence_count": len(evidence),
        "evidence_by_source_type": {},
        "evidence_by_freshness": {},
        "stale_evidence_count": len([x for x in evidence + sources if "stale" in _safe_text(x.get("freshness_status") or x.get("status")).lower()]),
        "expired_evidence_count": len([x for x in evidence + sources if "expired" in _safe_text(x.get("freshness_status") or x.get("status")).lower()]),
        "evidence_used_in_theses": len([x for x in evidence if x.get("thesis_id") or x.get("related_thesis_id")]),
        "evidence_not_linked_to_theses": len([x for x in evidence if not (x.get("thesis_id") or x.get("related_thesis_id"))]),
        "evidence_later_contradicted": len([x for x in evidence if "contradict" in _direction(x)]),
        "sources_requiring_refresh": len([x for x in sources if "stale" in _safe_text(x.get("freshness_status") or x.get("status")).lower()]),
        "usefulness_counts": {"useful": 0, "needs_review": 0, "stale": 0, "contradicted": 0, "unsupported": 0, "unknown": 0},
        "unknown_unavailable_fields": ["true source reliability", "future usefulness", "outcome linkage unless reviewed"],
    }
    records = []
    for item in evidence:
        source_type = _safe_text(item.get("source_type") or item.get("source_kind") or "unknown")
        freshness = _safe_text(item.get("freshness_status") or item.get("status") or "unknown")
        metrics["evidence_by_source_type"][source_type] = metrics["evidence_by_source_type"].get(source_type, 0) + 1
        metrics["evidence_by_freshness"][freshness] = metrics["evidence_by_freshness"].get(freshness, 0) + 1
        status = "contradicted" if "contradict" in _direction(item) else "stale" if "stale" in freshness.lower() else "useful" if item.get("thesis_id") else "needs_review"
        metrics["usefulness_counts"][status] = metrics["usefulness_counts"].get(status, 0) + 1
        records.append(_metric_record("evidence_usefulness", "research", {"evidence_id": _obj_id(item), "freshness": freshness, "usefulness_status": status}, [_obj_id(item)]))
    return {"version": APP_VERSION, "generated_at": _now(), "metrics": redact_data(metrics), "records": records, "secret_values_returned": False}


def alert_usefulness_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    rules = data.get("monitoring", {}).get("rules", [])
    alerts = data.get("monitoring", {}).get("alerts", []) + data.get("monitoring", {}).get("history", [])
    metrics = {
        "alert_rules": len(rules),
        "alerts_triggered": len(alerts),
        "alerts_acknowledged": len([x for x in alerts if _status(x) in {"acknowledged", "resolved"} or x.get("acknowledged_at")]),
        "alerts_snoozed": len([x for x in alerts if _status(x) == "snoozed" or x.get("snoozed_until")]),
        "alerts_ignored_unacknowledged": len([x for x in alerts if _status(x) in {"active", "open", "warning", "critical"} and not x.get("acknowledged_at")]),
        "alerts_linked_to_decisions": len([x for x in alerts if x.get("decision_id") or x.get("related_decision_id")]),
        "alerts_linked_to_reviews": len([x for x in alerts if x.get("review_id") or x.get("related_review_id")]),
        "alerts_linked_to_near_misses": len([x for x in alerts if x.get("near_miss_id") or x.get("related_near_miss_id")]),
        "repeated_alert_types": {},
        "critical_alert_followthrough": len([x for x in alerts if _safe_text(x.get("severity")).lower() == "critical" and (x.get("acknowledged_at") or _status(x) in {"acknowledged", "resolved"})]),
        "stale_evidence_alerts": len([x for x in alerts if "stale" in json.dumps(x, default=str).lower()]),
        "portfolio_concentration_alerts": len([x for x in alerts if "concentration" in json.dumps(x, default=str).lower()]),
        "readiness_safety_posture_alerts": len([x for x in alerts if "readiness" in json.dumps(x, default=str).lower() or "safety" in json.dumps(x, default=str).lower()]),
        "usefulness_counts": {"useful": 0, "noisy": 0, "needs_tuning": 0, "stale": 0, "unresolved": 0, "unknown": 0},
        "recommendations": [],
        "unknown_unavailable_fields": ["operator usefulness unless marked in reviews"],
    }
    for item in alerts:
        atype = _safe_text(item.get("rule_type") or item.get("alert_type") or item.get("severity") or "unknown")
        metrics["repeated_alert_types"][atype] = metrics["repeated_alert_types"].get(atype, 0) + 1
        status = "unresolved" if _status(item) in {"active", "open", "warning", "critical"} else "useful" if _status(item) in {"acknowledged", "resolved"} else "unknown"
        if metrics["repeated_alert_types"][atype] > 3:
            status = "needs_tuning"
        metrics["usefulness_counts"][status] = metrics["usefulness_counts"].get(status, 0) + 1
    if metrics["alerts_ignored_unacknowledged"]:
        metrics["recommendations"].append("Follow up on critical or unacknowledged alerts.")
    if any(count > 3 for count in metrics["repeated_alert_types"].values()):
        metrics["recommendations"].append("Review repeated alert rules for noise or tuning.")
    return {"version": APP_VERSION, "generated_at": _now(), "metrics": redact_data(metrics), "records": [_metric_record("alert_usefulness", "monitoring", metrics)], "secret_values_returned": False}


def governance_discipline_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    gov = data.get("governance", {})
    checklists = gov.get("checklists", [])
    reviews = gov.get("reviews", [])
    near = gov.get("near_misses", [])
    mistakes = gov.get("mistake_patterns", [])
    rules = gov.get("rules", [])
    completed = len([x for x in checklists if _status(x) == "completed"])
    metrics = {
        "checklist_completion_rate": round(completed / max(1, len(checklists)), 4),
        "incomplete_checklist_count": len(checklists) - completed,
        "post_trade_review_completion": len([x for x in reviews if "post" in _safe_text(x.get("review_type")).lower() and _status(x) in {"completed", "closed"}]),
        "daily_review_completion": len([x for x in reviews if "daily" in _safe_text(x.get("review_type")).lower() and _status(x) in {"completed", "closed"}]),
        "weekly_review_completion": len([x for x in reviews if "weekly" in _safe_text(x.get("review_type")).lower() and _status(x) in {"completed", "closed"}]),
        "rule_violations": len([x for x in near if "violation" in _safe_text(x.get("type") or x.get("kind") or x.get("title")).lower()]),
        "near_misses": len(near),
        "repeated_mistake_patterns": len([x for x in mistakes if int(float(x.get("frequency") or 0)) > 1]),
        "resolved_mistake_patterns": len([x for x in mistakes if _status(x) == "resolved"]),
        "process_improvement_items_created": len([x for x in mistakes if x.get("process_improvement_action")]),
        "process_improvement_items_completed": len([x for x in mistakes if _safe_text(x.get("process_improvement_status")).lower() in {"done", "completed"}]),
        "governance_rules_enabled": len([x for x in rules if _status(x) not in {"disabled", "archived"}]),
        "governance_rules_disabled": len([x for x in rules if _status(x) in {"disabled", "archived"}]),
        "follow_up_actions_overdue": len([x for x in reviews + mistakes if _status(x) == "overdue"]),
        "discipline_status": "healthy" if checklists and completed == len(checklists) else "needs_review" if checklists else "unknown",
        "unknown_unavailable_fields": ["unrecorded manual behavior"],
    }
    return {"version": APP_VERSION, "generated_at": _now(), "metrics": redact_data(metrics), "records": [_metric_record("governance_discipline", "governance", metrics)], "secret_values_returned": False}


def portfolio_risk_process_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    portfolio = data.get("portfolio", {})
    audit = data.get("audit", {}).get("events", [])
    exposure = portfolio.get("exposure", [])
    warnings = portfolio.get("warnings", [])
    scenarios = portfolio.get("scenarios", [])
    metrics = {
        "concentration_warnings": len([x for x in warnings if "concentration" in json.dumps(x, default=str).lower()]),
        "exposure_warnings": len(warnings),
        "planned_trade_impacts_evaluated": len([x for x in audit if "planned" in _safe_text(x.get("action")).lower() and "impact" in _safe_text(x.get("action")).lower()]),
        "scenarios_created": len(scenarios),
        "scenarios_evaluated": len([x for x in scenarios if _status(x) in {"evaluated", "completed"}]),
        "risk_blocks": len([x for x in audit if "risk" in _safe_text(x.get("action")).lower() and "block" in json.dumps(x, default=str).lower()]),
        "read_only_blocks": len([x for x in audit if "read_only" in json.dumps(x, default=str).lower() and "block" in json.dumps(x, default=str).lower()]),
        "kill_switch_blocks": len([x for x in audit if "kill" in json.dumps(x, default=str).lower() and "block" in json.dumps(x, default=str).lower()]),
        "exposure_linked_to_stale_evidence": len([x for x in exposure if "stale" in json.dumps(x, default=str).lower()]),
        "exposure_linked_to_unresolved_research": len([x for x in exposure if "unresolved" in json.dumps(x, default=str).lower()]),
        "exposure_linked_to_active_alerts": len([x for x in exposure if x.get("alert_id") or x.get("related_alert_id")]),
        "tickets_blocked_by_risk_controls": len([x for x in audit if "ticket" in json.dumps(x, default=str).lower() and "block" in json.dumps(x, default=str).lower()]),
        "unknown_unavailable_fields": ["actual P&L", "live account exposure unless safe read-only data exists"],
    }
    return {"version": APP_VERSION, "generated_at": _now(), "metrics": redact_data(metrics), "records": [_metric_record("portfolio_risk_process", "portfolio", metrics)], "secret_values_returned": False}


def confidence_calibration_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    rows = data.get("governance", {}).get("journal", []) + data.get("strategy", {}).get("theses", [])
    buckets = {"0-25": {"sample_size": 0, "reviewed_outcomes": 0, "unknown_outcomes": 0}, "26-50": {"sample_size": 0, "reviewed_outcomes": 0, "unknown_outcomes": 0}, "51-75": {"sample_size": 0, "reviewed_outcomes": 0, "unknown_outcomes": 0}, "76-100": {"sample_size": 0, "reviewed_outcomes": 0, "unknown_outcomes": 0}}
    high_no_evidence = 0
    low_with_ticket = 0
    for row in rows:
        raw = row.get("confidence") or row.get("confidence_level") or row.get("probability") or 50
        try:
            conf = float(raw)
            if conf <= 1:
                conf *= 100
        except Exception:
            conf = 50.0
        key = "0-25" if conf <= 25 else "26-50" if conf <= 50 else "51-75" if conf <= 75 else "76-100"
        buckets[key]["sample_size"] += 1
        if row.get("actual_outcome") or row.get("review_outcome"):
            buckets[key]["reviewed_outcomes"] += 1
        else:
            buckets[key]["unknown_outcomes"] += 1
        if conf >= 75 and not (row.get("evidence_id") or row.get("related_evidence_id")):
            high_no_evidence += 1
        if conf <= 40 and (row.get("ticket_id") or row.get("related_ticket_id")):
            low_with_ticket += 1
    metrics = {"confidence_buckets": buckets, "overconfidence_signals": high_no_evidence, "underconfidence_signals": 0, "unreviewed_high_confidence_decisions": buckets["76-100"]["unknown_outcomes"], "high_confidence_decisions_lacking_evidence": high_no_evidence, "low_confidence_decisions_that_led_to_tickets": low_with_ticket, "sample_size": sum(b["sample_size"] for b in buckets.values()), "unknown_count": sum(b["unknown_outcomes"] for b in buckets.values()), "caution": "Calibration is descriptive and needs sufficient sample size before interpretation.", "unknown_unavailable_fields": ["true outcomes unless reviewed"]}
    return {"version": APP_VERSION, "generated_at": _now(), "metrics": redact_data(metrics), "records": [_metric_record("confidence_calibration", "governance", metrics)], "secret_values_returned": False}


def mistake_pattern_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    mistakes = data.get("governance", {}).get("mistake_patterns", [])
    rows = []
    for item in mistakes:
        rows.append({"pattern_id": _obj_id(item), "title": _safe_text(item.get("pattern_title") or item.get("title") or item.get("pattern_type"), "Mistake pattern"), "pattern_type": _safe_text(item.get("pattern_type") or item.get("type") or "unknown"), "frequency": int(float(item.get("frequency") or 1)), "status": _status(item), "corrective_action": _safe_text(item.get("process_improvement_action") or item.get("corrective_action")), "supportive_note": "Use this as process feedback, not blame."})
    return {"version": APP_VERSION, "generated_at": _now(), "count": len(rows), "items": redact_data(rows), "secret_values_returned": False}


def strength_pattern_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    strengths = []
    gov = governance_discipline_metrics(data)["metrics"]
    thesis = thesis_quality_metrics(data)["metrics"]
    alerts = alert_usefulness_metrics(data)["metrics"]
    if gov.get("checklist_completion_rate", 0) > 0:
        strengths.append({"title": "Checklist discipline is being recorded", "pattern_type": "completed_checklists", "frequency": gov.get("decisions_with_governance_checklist_completed", gov.get("checklist_completion_rate", 0)), "status": "active"})
    if thesis.get("theses_with_counter_evidence", 0) > 0:
        strengths.append({"title": "Counter-evidence coverage exists", "pattern_type": "counter_evidence", "frequency": thesis.get("theses_with_counter_evidence", 0), "status": "active"})
    if alerts.get("alerts_acknowledged", 0) > 0:
        strengths.append({"title": "Alerts are being acknowledged", "pattern_type": "alert_followthrough", "frequency": alerts.get("alerts_acknowledged", 0), "status": "active"})
    if not strengths:
        strengths.append({"title": "Analytics baseline established", "pattern_type": "baseline", "frequency": 1, "status": "new", "recommended_operator_action": "Continue recording decisions, evidence, alerts, and reviews to surface more strengths."})
    return {"version": APP_VERSION, "generated_at": _now(), "count": len(strengths), "items": redact_data(strengths), "secret_values_returned": False}


def review_followthrough_metrics(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    reviews = data.get("governance", {}).get("reviews", []) + data.get("strategy", {}).get("reviews", [])
    metrics = {"daily_reviews_created": len([x for x in reviews if "daily" in _safe_text(x.get("review_type")).lower()]), "weekly_reviews_created": len([x for x in reviews if "weekly" in _safe_text(x.get("review_type")).lower()]), "post_trade_reviews_created": len([x for x in reviews if "post" in _safe_text(x.get("review_type")).lower()]), "review_items_completed": len([x for x in reviews if _status(x) in {"completed", "closed"}]), "review_items_overdue": len([x for x in reviews if _status(x) == "overdue"]), "follow_up_dates_met": len([x for x in reviews if _safe_text(x.get("follow_up_status")).lower() in {"done", "completed", "met"}]), "follow_up_dates_missed": len([x for x in reviews if _safe_text(x.get("follow_up_status")).lower() in {"missed", "late", "overdue"}]), "unresolved_review_actions": len([x for x in reviews if _status(x) in {"draft", "active", "open"}]), "improvement_items_completed": len([x for x in reviews if _safe_text(x.get("process_improvement_status")).lower() in {"done", "completed"}]), "unknown_unavailable_fields": ["reviews not yet entered"]}
    return {"version": APP_VERSION, "generated_at": _now(), "metrics": redact_data(metrics), "records": [_metric_record("review_followthrough", "governance", metrics)], "secret_values_returned": False}


def build_analytics_summary(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _collect()
    decision = decision_quality_metrics(data)["metrics"]
    calibration = confidence_calibration_metrics(data)["metrics"]
    review = review_followthrough_metrics(data)["metrics"]
    mistakes = mistake_pattern_metrics(data)
    strengths = strength_pattern_metrics(data)
    evidence = evidence_usefulness_metrics(data)["metrics"]
    alerts = alert_usefulness_metrics(data)["metrics"]
    governance = governance_discipline_metrics(data)["metrics"]
    summary = {
        "version": APP_VERSION,
        "generated_at": _now(),
        "decision_quality_status": "needs_review" if decision.get("decisions_not_reviewed", 0) else "baseline" if decision.get("total_decisions", 0) else "unknown",
        "confidence_calibration_status": "needs_more_data" if calibration.get("sample_size", 0) < 10 else "review_ready",
        "review_followthrough_status": "needs_review" if review.get("unresolved_review_actions", 0) else "unknown" if not sum(v for k, v in review.items() if isinstance(v, int)) else "healthy",
        "recurring_mistake_pattern_count": mistakes.get("count", 0),
        "recurring_strength_pattern_count": strengths.get("count", 0),
        "stale_evidence_trend": evidence.get("stale_evidence_count", 0),
        "alert_usefulness_trend": alerts.get("usefulness_counts", {}),
        "governance_discipline_status": governance.get("discipline_status", "unknown"),
        "latest_learning_report_date": _latest_report_date(),
        "next_recommended_review_action": _next_learning_action(decision, evidence, alerts, governance, review),
        "analytics_are_descriptive": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    }
    return redact_data(summary)


def _next_learning_action(decision: dict[str, Any], evidence: dict[str, Any], alerts: dict[str, Any], governance: dict[str, Any], review: dict[str, Any]) -> str:
    if decision.get("decisions_not_reviewed", 0):
        return "Review unreviewed decision journal entries."
    if evidence.get("stale_evidence_count", 0):
        return "Refresh or archive stale evidence linked to active decisions."
    if alerts.get("alerts_ignored_unacknowledged", 0):
        return "Triage unacknowledged monitoring alerts."
    if governance.get("incomplete_checklist_count", 0):
        return "Complete or archive stale governance checklists."
    if review.get("unresolved_review_actions", 0):
        return "Close or schedule unresolved review follow-up actions."
    return "Continue logging decisions, outcomes, and reviews to improve analytics sample size."


def _latest_report_date() -> str:
    if not ANALYTICS_REPORTS_PATH.exists():
        return "none"
    latest = "none"
    for line in ANALYTICS_REPORTS_PATH.read_text(encoding="utf-8").splitlines():
        try:
            latest = json.loads(line).get("generated_at", latest)
        except Exception:
            continue
    return latest


def generate_analytics_snapshot(write: bool = True) -> dict[str, Any]:
    data = _collect()
    snapshot = redact_data({
        "snapshot_id": f"analytics_snapshot_{uuid4().hex[:12]}",
        "version": APP_VERSION,
        "generated_at": _now(),
        "summary": build_analytics_summary(data),
        "decisions": decision_quality_metrics(data),
        "theses": thesis_quality_metrics(data),
        "evidence": evidence_usefulness_metrics(data),
        "alerts": alert_usefulness_metrics(data),
        "governance": governance_discipline_metrics(data),
        "portfolio": portfolio_risk_process_metrics(data),
        "calibration": confidence_calibration_metrics(data),
        "mistakes": mistake_pattern_metrics(data),
        "strengths": strength_pattern_metrics(data),
        "reviews": review_followthrough_metrics(data),
        "analytics_are_descriptive": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    })
    if write:
        _ensure_dir()
        with ANALYTICS_SNAPSHOTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(snapshot, sort_keys=True, default=str) + "\n")
        _event("snapshot_generated", "ok", {"snapshot_id": snapshot["snapshot_id"]})
    return snapshot


def generate_learning_report(period: str = "weekly", start_date: str = "", end_date: str = "", write: bool = True) -> dict[str, Any]:
    snapshot = generate_analytics_snapshot(write=False)
    report = redact_data({
        "report_id": f"learning_report_{uuid4().hex[:12]}",
        "version": APP_VERSION,
        "generated_at": _now(),
        "period": _safe_text(period, "weekly"),
        "period_covered": {"start_date": _safe_text(start_date, "unknown"), "end_date": _safe_text(end_date, "unknown")},
        "decisions_reviewed": snapshot["decisions"]["metrics"].get("decisions_reviewed", 0),
        "decisions_needing_review": snapshot["decisions"]["metrics"].get("decisions_not_reviewed", 0),
        "thesis_quality_summary": snapshot["theses"]["metrics"].get("status_counts", {}),
        "evidence_usefulness_summary": snapshot["evidence"]["metrics"].get("usefulness_counts", {}),
        "alert_usefulness_summary": snapshot["alerts"]["metrics"].get("usefulness_counts", {}),
        "governance_discipline_summary": snapshot["governance"]["metrics"],
        "portfolio_risk_process_summary": snapshot["portfolio"]["metrics"],
        "confidence_calibration_summary": snapshot["calibration"]["metrics"],
        "recurring_mistake_patterns": snapshot["mistakes"].get("items", []),
        "recurring_strength_patterns": snapshot["strengths"].get("items", []),
        "overdue_followups": snapshot["reviews"]["metrics"].get("review_items_overdue", 0),
        "process_improvement_suggestions": [snapshot["summary"].get("next_recommended_review_action")],
        "unknown_unavailable_data": ["Outcomes, fills, balances, and P&L are unknown unless explicitly recorded or available through safe read-only data."],
        "safety_statement": "Learning reports are descriptive workflow guidance, not financial advice, and this report does not place, cancel, sign, approve, or arm orders.",
        "analytics_are_descriptive": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    })
    if write:
        _ensure_dir()
        with ANALYTICS_REPORTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, sort_keys=True, default=str) + "\n")
        _event("learning_report_generated", "ok", {"report_id": report["report_id"], "period": report["period"]})
    return report


def analytics_context(limit: int = 5) -> dict[str, Any]:
    summary = build_analytics_summary()
    snapshot = generate_analytics_snapshot(write=False)
    return redact_data({"summary": summary, "decision_quality": snapshot["decisions"]["metrics"], "thesis_quality": snapshot["theses"]["metrics"], "evidence_usefulness": snapshot["evidence"]["metrics"], "alert_usefulness": snapshot["alerts"]["metrics"], "governance_discipline": snapshot["governance"]["metrics"], "confidence_calibration": snapshot["calibration"]["metrics"], "mistake_patterns": snapshot["mistakes"].get("items", [])[:limit], "strength_patterns": snapshot["strengths"].get("items", [])[:limit], "secret_values_returned": False})


def analytics_search_items(limit: int = 100) -> list[dict[str, Any]]:
    snapshot = generate_analytics_snapshot(write=False)
    report = generate_learning_report(write=False)
    items = [
        _search_item("analytics_snapshot", snapshot["snapshot_id"], "Analytics Snapshot", snapshot["summary"].get("next_recommended_review_action", "Analytics snapshot"), "current"),
        _search_item("learning_report", report["report_id"], f"Learning Report ({report['period']})", report["process_improvement_suggestions"][0], "draft"),
        _search_item("calibration_summary", "calibration", "Confidence Calibration Summary", f"Sample size {snapshot['calibration']['metrics'].get('sample_size', 0)}; unknown {snapshot['calibration']['metrics'].get('unknown_count', 0)}", "descriptive"),
        _search_item("mistake_pattern_summary", "mistakes", "Mistake Pattern Summary", f"{snapshot['mistakes'].get('count', 0)} patterns recorded", "descriptive"),
        _search_item("strength_pattern_summary", "strengths", "Strength Pattern Summary", f"{snapshot['strengths'].get('count', 0)} strengths recorded", "descriptive"),
        _search_item("evidence_usefulness_summary", "evidence_usefulness", "Evidence Usefulness Summary", json.dumps(snapshot["evidence"]["metrics"].get("usefulness_counts", {})), "descriptive"),
        _search_item("alert_usefulness_summary", "alert_usefulness", "Alert Usefulness Summary", json.dumps(snapshot["alerts"]["metrics"].get("usefulness_counts", {})), "descriptive"),
    ]
    return redact_data(items[:limit])


def _search_item(result_type: str, rid: str, title: str, summary: str, status: str) -> dict[str, Any]:
    haystack = f"{title} {summary} {result_type} analytics learning calibration mistakes strengths"
    return {"result_id": f"{result_type}:{rid}", "result_type": result_type, "title": title, "summary": summary, "timestamp": _now(), "status": status, "tags": ["analytics", "learning"], "related": {"analytics_id": rid}, "quick_link": "/v3/analytics", "search_text": redact_text(haystack.lower()), "secret_values_returned": False}


def analytics_graph_nodes_edges() -> dict[str, Any]:
    items = analytics_search_items()
    nodes = []
    edges = []
    for item in items:
        node_id = item["result_id"]
        nodes.append({"node_id": node_id, "node_type": item["result_type"], "title": item["title"], "status": item["status"], "timestamp": item["timestamp"], "tags": item["tags"], "related_object_id": node_id.split(":", 1)[-1], "summary": item["summary"], "safe_metadata": item["related"]})
        edges.append({"edge_id": f"edge_{uuid4().hex[:12]}", "source_node": node_id, "target_node": "analytics_snapshot:latest", "relationship_type": "summarizes" if item["result_type"] != "analytics_snapshot" else "derived_from", "created_at": _now(), "safe_metadata": {}, "secret_values_returned": False})
    return {"nodes": redact_data(nodes), "edges": redact_data(edges), "secret_values_returned": False}


def export_analytics_json() -> dict[str, Any]:
    snapshot = generate_analytics_snapshot(write=False)
    _event("export_generated", "ok", {"format": "json"})
    return snapshot


def export_learning_report_markdown(period: str = "weekly") -> str:
    report = generate_learning_report(period=period, write=False)
    _event("learning_report_exported", "ok", {"format": "markdown", "period": period})
    return learning_report_to_markdown(report)


def learning_report_to_markdown(report: dict[str, Any]) -> str:
    lines = [f"# v3.2 Learning Report — {APP_VERSION}", "", f"Generated: {report.get('generated_at')}", f"Period: {report.get('period')}", "", "## Decision Review", f"- Decisions reviewed: {report.get('decisions_reviewed')}", f"- Decisions needing review: {report.get('decisions_needing_review')}", "", "## Thesis Quality", f"```json\n{json.dumps(report.get('thesis_quality_summary', {}), indent=2, sort_keys=True)}\n```", "", "## Evidence Usefulness", f"```json\n{json.dumps(report.get('evidence_usefulness_summary', {}), indent=2, sort_keys=True)}\n```", "", "## Alert Usefulness", f"```json\n{json.dumps(report.get('alert_usefulness_summary', {}), indent=2, sort_keys=True)}\n```", "", "## Confidence Calibration", f"Sample size: {report.get('confidence_calibration_summary', {}).get('sample_size', 0)}", f"Unknown outcomes: {report.get('confidence_calibration_summary', {}).get('unknown_count', 0)}", "", "## Recurring Mistake Patterns"]
    for item in report.get("recurring_mistake_patterns", [])[:20]:
        lines.append(f"- {item.get('title')} ({item.get('status')})")
    lines.append("")
    lines.append("## Recurring Strength Patterns")
    for item in report.get("recurring_strength_patterns", [])[:20]:
        lines.append(f"- {item.get('title')} ({item.get('status')})")
    lines.extend(["", "## Process Improvement Suggestions"])
    for suggestion in report.get("process_improvement_suggestions", []):
        lines.append(f"- {suggestion}")
    lines.extend(["", "## Safety", report.get("safety_statement", "Analytics do not place or cancel orders.")])
    return "\n".join(lines) + "\n"


def _csv_from_rows(rows: list[dict[str, Any]], fields: list[str]) -> str:
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        safe = {k: json.dumps(v, sort_keys=True, default=str) if isinstance(v, (dict, list)) else v for k, v in redact_data(row).items()}
        writer.writerow(safe)
    return handle.getvalue()


def export_csv(kind: str) -> str:
    snapshot = generate_analytics_snapshot(write=False)
    fields = ["id", "analytics_type", "source_subsystem", "input_data_summary", "computed_metrics", "interpretation_notes"]
    mapping = {
        "decisions": snapshot["decisions"].get("records", []),
        "theses": snapshot["theses"].get("records", []),
        "evidence": snapshot["evidence"].get("records", []),
        "alerts": snapshot["alerts"].get("records", []),
        "governance": snapshot["governance"].get("records", []),
        "calibration": snapshot["calibration"].get("records", []),
    }
    _event("export_generated", "ok", {"format": "csv", "kind": kind})
    return _csv_from_rows(mapping.get(kind, []), fields)

# v4.4.0-real simulation context integration for analytics summaries.
_analytics_context_v33 = analytics_context


def analytics_context(limit: int = 5) -> dict[str, Any]:  # type: ignore[override]
    context = _analytics_context_v33(limit=limit)
    try:
        from .live_v3_simulation import simulation_analytics_context
        context["simulation"] = simulation_analytics_context()
    except Exception as exc:
        context["simulation"] = {"status": "unknown", "error_redacted": redact_text(str(exc)), "secret_values_returned": False}
    context["secret_values_returned"] = False
    return redact_data(context)


_build_analytics_summary_v33 = build_analytics_summary


def build_analytics_summary(data: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    summary = _build_analytics_summary_v33(data)
    try:
        from .live_v3_simulation import simulation_analytics_context
        sim = simulation_analytics_context()
    except Exception:
        sim = {"simulation_sessions": 0, "process_backtests_completed": 0, "no_trade_simulations": 0, "secret_values_returned": False}
    summary["simulation_sessions"] = sim.get("simulation_sessions", 0)
    summary["process_backtests_completed"] = sim.get("process_backtests_completed", 0)
    summary["no_trade_simulations"] = sim.get("no_trade_simulations", 0)
    summary["simulation_context_available"] = True
    summary["secret_values_returned"] = False
    return redact_data(summary)

# v4.4.0-real dataset context integration for analytics summaries.
_analytics_context_v34 = analytics_context

def analytics_context(limit: int = 5) -> dict[str, Any]:  # type: ignore[override]
    context = _analytics_context_v34(limit=limit)
    try:
        from .live_v3_datasets import dataset_analytics_context
        context["datasets"] = dataset_analytics_context()
    except Exception as exc:
        context["datasets"] = {"status": "unknown", "error_redacted": redact_text(str(exc)), "secret_values_returned": False}
    context["secret_values_returned"] = False
    return redact_data(context)

_build_analytics_summary_v34 = build_analytics_summary

def build_analytics_summary(data: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    summary = _build_analytics_summary_v34(data)
    try:
        from .live_v3_datasets import dataset_analytics_context
        ds = dataset_analytics_context()
    except Exception:
        ds = {"snapshot_count": 0, "dataset_count": 0, "replay_ready_dataset_count": 0, "secret_values_returned": False}
    summary["dataset_snapshot_count"] = ds.get("snapshot_count", 0)
    summary["dataset_count"] = ds.get("dataset_count", 0)
    summary["replay_ready_dataset_count"] = ds.get("replay_ready_dataset_count", 0)
    summary["dataset_quality_status"] = ds.get("dataset_quality_status", "unknown")
    summary["dataset_context_available"] = True
    summary["secret_values_returned"] = False
    return redact_data(summary)


# v4.4.0-real freshness context integration for analytics summaries.
_build_analytics_summary_v35 = build_analytics_summary

def build_analytics_summary(data: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    try:
        summary = _build_analytics_summary_v35(data)  # type: ignore[arg-type]
    except TypeError:
        summary = _build_analytics_summary_v35()
    try:
        from .live_v3_freshness import freshness_analytics_context
        summary["freshness_context"] = freshness_analytics_context()
        summary["stale_dataset_trend"] = summary["freshness_context"].get("stale_dataset_trend", 0)
        summary["notification_resolution_rate"] = summary["freshness_context"].get("notification_resolution_rate", 0)
    except Exception as exc:
        summary.setdefault("warnings", []).append(f"Freshness analytics context unavailable: {redact_text(str(exc))}")
    summary["secret_values_returned"] = False
    return redact_data(summary)
