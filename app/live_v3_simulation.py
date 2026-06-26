from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .live_v2 import build_live_v2_readiness, build_live_v2_status, list_audit_records, record_audit, redact_data, redact_text
from .live_strategy import list_theses, list_evidence, list_watchlist, list_scorecards, list_reviews
from .live_research import list_sources, list_queue, list_notes, list_candidates, freshness_summary
from .live_monitoring import list_rules as list_monitoring_rules, list_alerts, list_alert_history
from .live_portfolio import generate_portfolio_snapshot, list_exposure, list_warnings, list_scenarios, planned_trade_impact
from .live_governance import list_journal, list_checklists, list_reviews as list_governance_reviews, list_rules as list_governance_rules, list_near_misses, list_mistake_patterns
from .live_data import health_report_json

SIMULATION_DIR = DATA_DIR / "live_v3" / "simulation"
SIMULATION_EVENTS_PATH = SIMULATION_DIR / "simulation_events.jsonl"
SIMULATION_SESSIONS_PATH = SIMULATION_DIR / "simulation_sessions.jsonl"
SIMULATION_REPORTS_PATH = SIMULATION_DIR / "simulation_reports.jsonl"

SESSION_TYPES = {
    "pre_trade_replay", "thesis_health_replay", "alert_behavior_simulation", "portfolio_risk_simulation",
    "governance_checklist_simulation", "no_trade_simulation", "process_quality_backtest", "what_i_knew_then"
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    SIMULATION_DIR.mkdir(parents=True, exist_ok=True)


def _safe_text(value: Any, default: str = "") -> str:
    text = redact_text(str(value or "").strip())
    return text or default


def _items(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        data = result.get("items", result.get("records", result.get("checks", [])))
    else:
        data = result
    if not isinstance(data, list):
        return []
    return [redact_data(x) for x in data if isinstance(x, dict)]


def _parse_ts(value: Any) -> str:
    return _safe_text(value)


def _record_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
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
            rows.append(redact_data(json.loads(line)))
        except json.JSONDecodeError:
            rows.append({"id": _record_id("invalid"), "created_at": _now(), "status": "invalid_json", "secret_values_returned": False})
    return rows


def _latest_by_id(rows: list[dict[str, Any]], id_key: str = "id") -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get(id_key) or row.get("session_id") or row.get("report_id") or _record_id("row"))
        latest[rid] = row
    return sorted(latest.values(), key=lambda r: str(r.get("updated_at") or r.get("created_at") or r.get("timestamp") or ""), reverse=True)


def _audit(action: str, status: str = "ok", details: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "event_id": _record_id("sim_evt"),
        "timestamp": _now(),
        "app_version": APP_VERSION,
        "action": action,
        "status": status,
        "details": details or {},
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    }
    _write_jsonl(SIMULATION_EVENTS_PATH, event)
    record_audit(f"v3_simulation_{action}", status, details={**(details or {}), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False}, network_attempted=False)
    return redact_data(event)


def list_simulation_events(limit: int = 500) -> dict[str, Any]:
    rows = list(reversed(_read_jsonl(SIMULATION_EVENTS_PATH)))[: max(1, min(int(limit or 500), 5000))]
    return {"version": APP_VERSION, "count": len(rows), "items": redact_data(rows), "secret_values_returned": False}


def _collect_local_data(limit: int = 250) -> dict[str, Any]:
    return redact_data({
        "version": APP_VERSION,
        "generated_at": _now(),
        "status": build_live_v2_status(),
        "readiness": build_live_v2_readiness(),
        "data_health": health_report_json(),
        "strategy": {
            "theses": _items(list_theses(limit=limit)),
            "evidence": _items(list_evidence(limit=limit)),
            "watchlist": _items(list_watchlist(limit=limit)),
            "scorecards": _items(list_scorecards(limit=limit)),
            "reviews": _items(list_reviews(limit=limit)),
        },
        "research": {
            "sources": _items(list_sources(limit=limit)),
            "queue": _items(list_queue(limit=limit)),
            "notes": _items(list_notes(limit=limit)),
            "candidates": _items(list_candidates(limit=limit)),
            "freshness": freshness_summary(),
        },
        "monitoring": {
            "rules": _items(list_monitoring_rules(limit=limit)),
            "alerts": _items(list_alerts(limit=limit)),
            "history": _items(list_alert_history(limit=limit)),
        },
        "portfolio": {
            "snapshot": generate_portfolio_snapshot(record=False),
            "exposure": _items(list_exposure(limit=limit)),
            "warnings": _items(list_warnings(limit=limit)),
            "scenarios": _items(list_scenarios(limit=limit)),
        },
        "governance": {
            "journal": _items(list_journal(limit=limit)),
            "checklists": _items(list_checklists(limit=limit)),
            "reviews": _items(list_governance_reviews(limit=limit)),
            "rules": _items(list_governance_rules(limit=limit)),
            "near_misses": _items(list_near_misses(limit=limit)),
            "mistake_patterns": _items(list_mistake_patterns(limit=limit)),
        },
        "audit": {"events": list_audit_records(limit=limit)},
        "simulation": {
            "sessions": list_sessions(limit=limit).get("items", []),
            "reports": list_reports(limit=limit).get("items", []),
            "events": list_simulation_events(limit=limit).get("items", []),
        },
        "secret_values_returned": False,
    })


def _record_timestamp(row: dict[str, Any]) -> str:
    return str(row.get("updated_at") or row.get("created_at") or row.get("timestamp") or row.get("generated_at") or "")


def _partition_by_replay_time(rows: list[dict[str, Any]], replay_time: str) -> dict[str, Any]:
    if not replay_time:
        return {"known_at_replay_time": rows, "created_after_replay_time": [], "unknown_timestamp_count": 0}
    known: list[dict[str, Any]] = []
    later: list[dict[str, Any]] = []
    unknown = 0
    for row in rows:
        ts = _record_timestamp(row)
        if not ts:
            unknown += 1
            known.append({**row, "replay_label": "unknown timestamp; included cautiously"})
        elif ts <= replay_time:
            known.append({**row, "replay_label": "known at replay time"})
        else:
            later.append({**row, "replay_label": "created after replay time"})
    return {"known_at_replay_time": known, "created_after_replay_time": later, "unknown_timestamp_count": unknown}


def _default_assumptions(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    assumptions = payload.get("assumptions") if isinstance(payload.get("assumptions"), dict) else {}
    defaults = {
        "local_only_replay": True,
        "hypothetical_fill_percentage": payload.get("hypothetical_fill_percentage", assumptions.get("hypothetical_fill_percentage", "unknown")),
        "hypothetical_price": payload.get("hypothetical_price", assumptions.get("hypothetical_price", "unknown")),
        "hypothetical_resolution": payload.get("hypothetical_resolution", assumptions.get("hypothetical_resolution", "unknown")),
        "hypothetical_thesis_outcome": payload.get("hypothetical_thesis_outcome", assumptions.get("hypothetical_thesis_outcome", "unknown")),
        "hypothetical_alert_acknowledgement": payload.get("hypothetical_alert_acknowledgement", assumptions.get("hypothetical_alert_acknowledgement", "unknown")),
        "hypothetical_evidence_freshness": payload.get("hypothetical_evidence_freshness", assumptions.get("hypothetical_evidence_freshness", "unknown")),
        "missing_data_handling_mode": payload.get("missing_data_handling_mode", assumptions.get("missing_data_handling_mode", "mark_unknown")),
    }
    return redact_data({**defaults, **assumptions})


def _safety(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "simulation_only": True,
        "local_replay": True,
        "hypothetical": True,
        "not_financial_advice": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "mutates_live_trading_state": False,
        "secret_values_returned": False,
        "safety_statement": "Simulation and replay outputs are descriptive, local-first, and do not place orders, cancel orders, approve orders, sign orders, arm live trading, or bypass backend gates.",
    }
    if extra:
        base.update(extra)
    return base


def _unknowns(*collections: list[dict[str, Any]]) -> list[str]:
    notes = []
    if not any(collections):
        notes.append("No local records were available for part of this simulation; values are unknown/unavailable, not invented.")
    for idx, collection in enumerate(collections):
        if len(collection) == 0:
            notes.append(f"Input collection {idx + 1} is empty; related simulation output is incomplete.")
    return notes or ["Some fields may be unknown/unavailable unless recorded locally before replay."]


def list_sessions(limit: int = 250) -> dict[str, Any]:
    rows = _latest_by_id(_read_jsonl(SIMULATION_SESSIONS_PATH), "session_id")
    return {"version": APP_VERSION, "count": len(rows), "items": redact_data(rows[: max(1, min(int(limit or 250), 5000))]), **_safety()}


def get_session(session_id: str) -> dict[str, Any] | None:
    for row in list_sessions(limit=5000).get("items", []):
        if row.get("session_id") == session_id or row.get("id") == session_id:
            return redact_data(row)
    return None


def create_session(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    now = _now()
    session = {
        "session_id": _record_id("sim_sess"),
        "id": "",
        "created_at": now,
        "updated_at": now,
        "app_version": APP_VERSION,
        "session_title": _safe_text(payload.get("session_title") or payload.get("title"), "Untitled simulation session"),
        "simulation_type": _safe_text(payload.get("simulation_type") or payload.get("replay_type"), "pre_trade_replay"),
        "target_time": _safe_text(payload.get("target_time") or payload.get("replay_time"), ""),
        "date_range": payload.get("date_range") if isinstance(payload.get("date_range"), dict) else {},
        "selected_market_id": _safe_text(payload.get("market_id") or payload.get("selected_market_id"), ""),
        "selected_thesis_id": _safe_text(payload.get("thesis_id") or payload.get("selected_thesis_id"), ""),
        "included_subsystems": payload.get("included_subsystems") if isinstance(payload.get("included_subsystems"), list) else ["strategy", "research", "monitoring", "portfolio", "governance", "analytics", "data", "audit"],
        "assumption_set": _default_assumptions(payload),
        "notes": _safe_text(payload.get("notes"), ""),
        "status": _safe_text(payload.get("status"), "draft"),
        "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else ["simulation", "local_replay"],
        **_safety(),
    }
    session["id"] = session["session_id"]
    _write_jsonl(SIMULATION_SESSIONS_PATH, session)
    _audit("session_created", "ok", {"session_id": session["session_id"], "simulation_type": session["simulation_type"]})
    return redact_data({"ok": True, "session": session, **_safety()})


def update_session(session_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = get_session(session_id) or create_session({"session_title": f"Recovered {session_id}"})["session"]
    payload = payload or {}
    mutable = {k: v for k, v in payload.items() if k not in {"session_id", "id", "created_at", "order_submitted", "order_cancelled", "live_trading_armed"}}
    updated = redact_data({**existing, **mutable, "updated_at": _now(), **_safety()})
    _write_jsonl(SIMULATION_SESSIONS_PATH, updated)
    _audit("session_updated", "ok", {"session_id": updated.get("session_id")})
    return {"ok": True, "session": updated, **_safety()}


def archive_session(session_id: str) -> dict[str, Any]:
    result = update_session(session_id, {"status": "archived"})
    _audit("session_archived", "ok", {"session_id": session_id})
    return result


def reconstruct_historical_state(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    replay_time = _safe_text(payload.get("replay_time") or payload.get("target_time"), "")
    data = _collect_local_data(limit=int(payload.get("limit", 250) or 250))
    known = {
        "strategy_theses": _partition_by_replay_time(data["strategy"]["theses"], replay_time),
        "strategy_evidence": _partition_by_replay_time(data["strategy"]["evidence"], replay_time),
        "research_sources": _partition_by_replay_time(data["research"]["sources"], replay_time),
        "monitoring_alerts": _partition_by_replay_time(data["monitoring"]["alerts"], replay_time),
        "portfolio_exposure": _partition_by_replay_time(data["portfolio"]["exposure"], replay_time),
        "portfolio_warnings": _partition_by_replay_time(data["portfolio"]["warnings"], replay_time),
        "governance_checklists": _partition_by_replay_time(data["governance"]["checklists"], replay_time),
        "governance_journal": _partition_by_replay_time(data["governance"]["journal"], replay_time),
        "audit_events": _partition_by_replay_time(data["audit"]["events"], replay_time),
    }
    known_count = sum(len(v["known_at_replay_time"]) for v in known.values())
    later_count = sum(len(v["created_after_replay_time"]) for v in known.values())
    return redact_data({
        "version": APP_VERSION,
        "generated_at": _now(),
        "replay_time": replay_time or "current-local-state",
        "known_count": known_count,
        "created_after_replay_time_count": later_count,
        "historical_reconstruction_is_best_effort": True,
        "known_at_replay_time": known,
        "labels": ["known at replay time", "created after replay time", "unknown", "hypothetical assumption"],
        "unknown_unavailable": _unknowns(data["strategy"]["theses"], data["strategy"]["evidence"], data["monitoring"]["alerts"]),
        **_safety(),
    })


def _filter_rows(rows: list[dict[str, Any]], market_id: str = "", thesis_id: str = "") -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if market_id and market_id not in json.dumps(row, default=str):
            continue
        if thesis_id and thesis_id not in json.dumps(row, default=str):
            continue
        out.append(row)
    return out


def simulate_pre_trade(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    data = _collect_local_data()
    replay = reconstruct_historical_state(payload)
    market_id = _safe_text(payload.get("market_id"), "")
    thesis_id = _safe_text(payload.get("thesis_id"), "")
    evidence = _filter_rows(data["strategy"]["evidence"], market_id, thesis_id)
    support = [e for e in evidence if "support" in json.dumps(e).lower()]
    counter = [e for e in evidence if any(word in json.dumps(e).lower() for word in ["contradict", "counter", "against"])]
    stale = [e for e in evidence if "stale" in json.dumps(e).lower() or "expired" in json.dumps(e).lower()]
    alerts = _filter_rows(data["monitoring"]["alerts"], market_id, thesis_id)
    exposure = _filter_rows(data["portfolio"]["exposure"], market_id, thesis_id)
    warnings = _filter_rows(data["portfolio"]["warnings"], market_id, thesis_id)
    checklists = _filter_rows(data["governance"]["checklists"], market_id, thesis_id)
    blockers = []
    if not thesis_id and not _filter_rows(data["strategy"]["theses"], market_id, thesis_id):
        blockers.append("No linked local thesis was found for this simulated packet.")
    if not evidence:
        blockers.append("No local evidence was available for this simulated packet.")
    if not counter:
        blockers.append("No counter-evidence review was found in local data.")
    result = {
        "simulation_id": _record_id("sim_pretrade"),
        "simulation_type": "pre_trade_packet_replay",
        "generated_at": _now(),
        "market_id": market_id,
        "thesis_id": thesis_id,
        "replay_time": replay.get("replay_time"),
        "assumption_set": _default_assumptions(payload),
        "market_context": {"selected_market_id": market_id or "unknown", "selected_outcome": _safe_text(payload.get("outcome"), "unknown")},
        "linked_thesis": _filter_rows(data["strategy"]["theses"], market_id, thesis_id)[:5],
        "evidence_known_then": replay["known_at_replay_time"].get("strategy_evidence", {}).get("known_at_replay_time", [])[:25],
        "evidence_added_later": replay["known_at_replay_time"].get("strategy_evidence", {}).get("created_after_replay_time", [])[:25],
        "supporting_evidence": support[:25],
        "counter_evidence": counter[:25],
        "stale_evidence_warnings": stale[:25],
        "monitoring_alerts": alerts[:25],
        "portfolio_exposure": exposure[:25],
        "concentration_warnings": warnings[:25],
        "governance_checklist_state": checklists[:25],
        "data_health_state": data.get("data_health", {}).get("overall_status", "unknown"),
        "readiness_posture": data.get("readiness", {}),
        "blockers": blockers,
        "warnings": ["Simulation output is not a live ticket or approval.", *(["Stale evidence is present."] if stale else [])],
        "unknown_unavailable": _unknowns(evidence, alerts, exposure, checklists),
        "recommended_operator_review_actions": ["Review blockers and unknowns before creating any real ticket.", "Compare evidence known then against evidence added later.", "Run governance/no-trade simulation if blockers remain."],
        **_safety(),
    }
    _audit("pre_trade_simulation_generated", "ok", {"simulation_id": result["simulation_id"], "blocker_count": len(blockers)})
    return redact_data(result)


def simulate_thesis(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    data = _collect_local_data()
    replay = reconstruct_historical_state(payload)
    thesis_id = _safe_text(payload.get("thesis_id"), "")
    theses = _filter_rows(data["strategy"]["theses"], thesis_id=thesis_id)
    evidence = _filter_rows(data["strategy"]["evidence"], thesis_id=thesis_id)
    counter = [e for e in evidence if any(word in json.dumps(e).lower() for word in ["counter", "contradict", "against"])]
    stale = [e for e in evidence if "stale" in json.dumps(e).lower() or "expired" in json.dumps(e).lower()]
    health = "needs_review" if stale or not counter or not evidence else "strong"
    result = {"simulation_id": _record_id("sim_thesis"), "simulation_type": "thesis_health_replay", "generated_at": _now(), "thesis_id": thesis_id, "replay_time": replay.get("replay_time"), "assumption_set": _default_assumptions(payload), "thesis_state_then": replay["known_at_replay_time"].get("strategy_theses", {}).get("known_at_replay_time", [])[:10], "thesis_state_now": theses[:10], "evidence_coverage_then": replay["known_at_replay_time"].get("strategy_evidence", {}).get("known_at_replay_time", [])[:25], "evidence_coverage_now": evidence[:25], "counter_evidence_count": len(counter), "stale_evidence_count": len(stale), "health_status_then_vs_now": {"then": "unknown" if not replay.get("known_count") else health, "now": health}, "process_quality_lessons": ["Record counter-evidence before confidence upgrades.", "Refresh stale evidence before relying on a thesis."], "unknown_unavailable": _unknowns(theses, evidence), **_safety()}
    _audit("thesis_replay_generated", "ok", {"simulation_id": result["simulation_id"], "health": health})
    return redact_data(result)


def simulate_alerts(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    data = _collect_local_data()
    rule_id = _safe_text(payload.get("rule_id"), "")
    rules = _filter_rows(data["monitoring"]["rules"], _safe_text(payload.get("market_id"), ""), _safe_text(payload.get("thesis_id"), ""))
    alerts = _filter_rows(data["monitoring"]["alerts"], _safe_text(payload.get("market_id"), ""), _safe_text(payload.get("thesis_id"), ""))
    if rule_id:
        rules = [r for r in rules if rule_id in json.dumps(r, default=str)]
    simulated = []
    for rule in rules[:25] or [{"rule_id": rule_id or "hypothetical_rule", "rule_name": "Hypothetical local rule", "severity": "watch"}]:
        triggered = bool(alerts) or _safe_text(payload.get("force_trigger", "")).lower() in {"1", "true", "yes"}
        simulated.append({"rule": rule, "would_trigger": triggered, "severity": rule.get("severity", "watch"), "reason": "Existing local alert context matched." if triggered else "No matching local alert context was found.", "actionability": "unknown" if not alerts else "review", "classification": "useful" if triggered else "unknown"})
    result = {"simulation_id": _record_id("sim_alert"), "simulation_type": "alert_behavior_simulation", "generated_at": _now(), "assumption_set": _default_assumptions(payload), "simulated_alerts": simulated, "linked_review_consequences": ["Acknowledge or tune alert rules in Monitoring; this simulation does not send notifications."], "unknown_unavailable": _unknowns(rules, alerts), **_safety()}
    _audit("alert_simulation_completed", "ok", {"simulation_id": result["simulation_id"], "simulated_count": len(simulated)})
    return redact_data(result)


def simulate_portfolio(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    impact = planned_trade_impact(payload)
    data = _collect_local_data()
    exposure = data["portfolio"]["exposure"]
    warnings = data["portfolio"]["warnings"]
    result = {"simulation_id": _record_id("sim_portfolio"), "simulation_type": "portfolio_risk_simulation", "generated_at": _now(), "assumption_set": _default_assumptions(payload), "exposure_before": exposure[:50], "planned_trade_impact": impact, "simulated_exposure_after": {"status": "hypothetical", "source": "planned_trade_impact_preview", "notional_delta": payload.get("notional") or payload.get("size") or "unknown"}, "concentration_warnings": warnings[:50], "risk_budget_effects": impact.get("warnings", []) if isinstance(impact, dict) else [], "unknown_unavailable": _unknowns(exposure, warnings), **_safety()}
    _audit("portfolio_simulation_completed", "ok", {"simulation_id": result["simulation_id"]})
    return redact_data(result)


def simulate_governance(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    data = _collect_local_data()
    checklists = data["governance"]["checklists"]
    rules = data["governance"]["rules"]
    near_misses = data["governance"]["near_misses"]
    incomplete = [c for c in checklists if str(c.get("status", "")).lower() not in {"completed", "closed"}]
    result = {"simulation_id": _record_id("sim_governance"), "simulation_type": "governance_checklist_simulation", "generated_at": _now(), "assumption_set": _default_assumptions(payload), "checklist_completeness": {"total": len(checklists), "incomplete": len(incomplete), "status": "needs_review" if incomplete else "healthy"}, "missing_items": ["Complete pre-trade checklist before live consideration."] if incomplete else [], "rule_warnings": rules[:25], "near_miss_indicators": near_misses[:25], "suggested_process_review_actions": ["Review incomplete checklists.", "Link near-misses to decision journal entries."], "unknown_unavailable": _unknowns(checklists, rules), **_safety()}
    _audit("governance_simulation_completed", "ok", {"simulation_id": result["simulation_id"], "incomplete": len(incomplete)})
    return redact_data(result)


def simulate_no_trade(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    pre = simulate_pre_trade(payload)
    gov = simulate_governance(payload)
    rationale = []
    for item in pre.get("blockers", []):
        rationale.append(item)
    if gov.get("checklist_completeness", {}).get("incomplete", 0):
        rationale.append("Governance checklist is incomplete.")
    if not rationale:
        rationale.append("No hard blocker was found, but operator may still choose no-trade due to uncertainty or missing context.")
    result = {"simulation_id": _record_id("sim_no_trade"), "simulation_type": "no_trade_simulation", "generated_at": _now(), "assumption_set": _default_assumptions(payload), "no_trade_rationale": rationale, "missing_prerequisites": pre.get("blockers", []), "operator_review_actions": ["Document no-trade rationale in governance journal.", "List what would need to change before reconsideration."], "what_would_need_to_change": ["Evidence coverage improves.", "Counter-evidence is reviewed.", "Stale evidence is refreshed.", "Governance checklist is complete."], "unknown_unavailable": pre.get("unknown_unavailable", []), **_safety()}
    _audit("no_trade_simulation_generated", "ok", {"simulation_id": result["simulation_id"], "rationale_count": len(rationale)})
    return redact_data(result)


def process_quality_backtest(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    data = _collect_local_data()
    decisions = data["governance"]["journal"]
    theses = data["strategy"]["theses"]
    evidence = data["strategy"]["evidence"]
    alerts = data["monitoring"]["alerts"]
    checklists = data["governance"]["checklists"]
    reviews = data["governance"]["reviews"]
    stale_evidence = [e for e in evidence if "stale" in json.dumps(e).lower()]
    completed_checklists = [c for c in checklists if str(c.get("status", "")).lower() in {"completed", "closed"}]
    score = 0
    score += 15 if decisions else 0
    score += 15 if theses else 0
    score += 15 if evidence else 0
    score += 10 if any("counter" in json.dumps(e).lower() or "contradict" in json.dumps(e).lower() for e in evidence) else 0
    score += 15 if completed_checklists else 0
    score += 15 if reviews else 0
    score += 15 if not stale_evidence and evidence else 0
    weaknesses = []
    if not decisions: weaknesses.append("No local decisions were logged for the selected period.")
    if not evidence: weaknesses.append("No local evidence records were available.")
    if stale_evidence: weaknesses.append("Stale evidence was present during the backtest window.")
    if not completed_checklists: weaknesses.append("No completed checklist was found.")
    strengths = []
    if decisions: strengths.append("Decision journal records exist.")
    if evidence: strengths.append("Evidence records exist.")
    if completed_checklists: strengths.append("At least one governance checklist appears completed.")
    result = {"simulation_id": _record_id("sim_process"), "simulation_type": "process_quality_backtest", "generated_at": _now(), "period": payload.get("period", "local_all_time"), "assumption_set": _default_assumptions(payload), "process_scorecard": {"score": score, "max_score": 100, "status": "strong" if score >= 70 else "needs_review"}, "metrics": {"decisions_logged": len(decisions), "theses_available": len(theses), "evidence_available": len(evidence), "alerts_available": len(alerts), "checklists_available": len(checklists), "reviews_available": len(reviews), "stale_evidence_count": len(stale_evidence)}, "strengths": strengths, "weaknesses": weaknesses, "recurring_issues": weaknesses[:5], "suggested_process_improvements": ["Record thesis/evidence/counter-evidence before ticket creation.", "Complete governance checklists before live consideration.", "Refresh stale evidence before relying on replay findings."], "unknown_unavailable": _unknowns(decisions, theses, evidence, checklists), **_safety({"hypothetical": False})}
    _audit("process_backtest_completed", "ok", {"simulation_id": result["simulation_id"], "score": score})
    return redact_data(result)


def compare_then_now(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    replay = reconstruct_historical_state(payload)
    return redact_data({"simulation_id": _record_id("sim_compare"), "simulation_type": "what_i_knew_then_vs_now", "generated_at": _now(), "replay_time": replay.get("replay_time"), "comparison": replay.get("known_at_replay_time"), "lessons_learned": ["Later information is explicitly labeled to reduce hindsight confusion.", "Unknown/unavailable data should be reviewed manually."], **_safety()})


def run_session(session_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    session = get_session(session_id)
    if not session:
        created = create_session({"session_title": f"Auto-created {session_id}", "simulation_type": "process_quality_backtest"})["session"]
        session = created
    payload = {**(session or {}), **(payload or {})}
    stype = str(payload.get("simulation_type") or payload.get("replay_type") or "process_quality_backtest")
    if "pre" in stype:
        output = simulate_pre_trade(payload)
    elif "thesis" in stype:
        output = simulate_thesis(payload)
    elif "alert" in stype:
        output = simulate_alerts(payload)
    elif "portfolio" in stype or "risk" in stype:
        output = simulate_portfolio(payload)
    elif "governance" in stype or "checklist" in stype:
        output = simulate_governance(payload)
    elif "no_trade" in stype or "no-trade" in stype:
        output = simulate_no_trade(payload)
    elif "what" in stype or "compare" in stype:
        output = compare_then_now(payload)
    else:
        output = process_quality_backtest(payload)
    report = {"report_id": _record_id("sim_report"), "session_id": session.get("session_id"), "created_at": _now(), "updated_at": _now(), "app_version": APP_VERSION, "simulation_type": stype, "status": "completed", "output": output, **_safety()}
    _write_jsonl(SIMULATION_REPORTS_PATH, report)
    update_session(session.get("session_id"), {"status": "completed", "last_report_id": report["report_id"]})
    _audit("replay_run_completed", "ok", {"session_id": session.get("session_id"), "report_id": report["report_id"], "simulation_type": stype})
    return {"ok": True, "session": session, "report": redact_data(report), **_safety()}


def list_reports(limit: int = 250) -> dict[str, Any]:
    rows = list(reversed(_read_jsonl(SIMULATION_REPORTS_PATH)))[: max(1, min(int(limit or 250), 5000))]
    return {"version": APP_VERSION, "count": len(rows), "items": redact_data(rows), **_safety()}


def simulation_summary() -> dict[str, Any]:
    sessions = list_sessions(limit=1000).get("items", [])
    reports = list_reports(limit=1000).get("items", [])
    open_sessions = [s for s in sessions if s.get("status") not in {"completed", "archived"}]
    process_reports = [r for r in reports if "process" in str(r.get("simulation_type"))]
    no_trade_reports = [r for r in reports if "no_trade" in json.dumps(r).lower()]
    return redact_data({"version": APP_VERSION, "generated_at": _now(), "session_count": len(sessions), "open_session_count": len(open_sessions), "report_count": len(reports), "process_backtest_count": len(process_reports), "no_trade_simulation_count": len(no_trade_reports), "latest_session": sessions[0] if sessions else None, "latest_report": reports[0] if reports else None, "next_simulation_review_action": "Create a replay session or run a process-quality backtest before relying on historical conclusions.", **_safety({"hypothetical": False})})


def export_simulation_json() -> dict[str, Any]:
    data = {"version": APP_VERSION, "generated_at": _now(), "summary": simulation_summary(), "sessions": list_sessions(limit=1000).get("items", []), "reports": list_reports(limit=1000).get("items", []), "events": list_simulation_events(limit=1000).get("items", []), **_safety()}
    _audit("simulation_export_generated", "ok", {"format": "json", "session_count": data["summary"].get("session_count")})
    return redact_data(data)


def simulation_report_markdown(report: dict[str, Any] | None = None) -> str:
    report = report or {"summary": simulation_summary(), "reports": list_reports(limit=25).get("items", [])}
    lines = [f"# v3.4 Simulation Lab Report — {APP_VERSION}", "", f"Generated: {_now()}", "", "Simulation outputs are local-first, descriptive, educational, and do not place or cancel orders. It does not place orders.", "", "## Summary"]
    summary = report.get("summary") if isinstance(report, dict) else {}
    for key in ("session_count", "open_session_count", "report_count", "process_backtest_count", "no_trade_simulation_count"):
        lines.append(f"- **{key}:** {summary.get(key, 'unknown') if isinstance(summary, dict) else 'unknown'}")
    lines += ["", "## Recent Reports"]
    for item in list_reports(limit=25).get("items", []):
        lines.append(f"- **{item.get('simulation_type', 'simulation')}** — {item.get('status', 'unknown')} — {item.get('created_at', '')}")
    lines += ["", "## Safety Statement", "No simulation output is an order, approval, financial advice, or live-trading authorization. Live order submission still requires existing backend gates."]
    _audit("simulation_report_exported", "ok", {"format": "markdown"})
    return "\n".join(lines) + "\n"


def export_csv(kind: str = "sessions") -> str:
    kind = _safe_text(kind, "sessions")
    rows = list_sessions(limit=1000).get("items", []) if kind == "sessions" else list_reports(limit=1000).get("items", [])
    output = io.StringIO()
    fieldnames = ["id", "session_id", "report_id", "simulation_type", "status", "created_at", "updated_at", "app_version", "order_submitted", "order_cancelled", "live_trading_armed"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    _audit("simulation_report_exported", "ok", {"format": "csv", "kind": kind})
    return output.getvalue()


def simulation_search_items(limit: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for session in list_sessions(limit=limit).get("items", []):
        title = _safe_text(session.get("session_title"), "Simulation session")
        rows.append({"result_id": f"simulation_session:{session.get('session_id')}", "result_type": "simulation_session", "title": title, "summary": _safe_text(session.get("notes") or session.get("simulation_type")), "timestamp": session.get("updated_at", ""), "status": session.get("status", "unknown"), "tags": session.get("tags", ["simulation"]), "quick_link": "/v3/simulation", "search_text": f"{title} {session.get('simulation_type')} simulation replay backtest".lower(), "related": {"session_id": session.get("session_id")}})
    for report in list_reports(limit=limit).get("items", []):
        title = f"{_safe_text(report.get('simulation_type'), 'Simulation report').replace('_', ' ').title()}"
        rows.append({"result_id": f"simulation_report:{report.get('report_id')}", "result_type": "simulation_report", "title": title, "summary": "Local simulation/replay report.", "timestamp": report.get("created_at", ""), "status": report.get("status", "completed"), "tags": ["simulation", "report"], "quick_link": "/v3/simulation/reports", "search_text": f"{title} simulation report replay process backtest no trade".lower(), "related": {"report_id": report.get("report_id"), "session_id": report.get("session_id")}})
    return redact_data(rows[: max(1, min(int(limit or 100), 1000))])


def simulation_graph_nodes_edges() -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for item in simulation_search_items(limit=500):
        nodes.append({"node_id": item["result_id"], "node_type": item["result_type"], "title": item["title"], "status": item.get("status", "unknown"), "timestamp": item.get("timestamp", ""), "tags": item.get("tags", []), "related_object_id": item["result_id"].split(":", 1)[-1], "summary": item.get("summary", ""), "safe_metadata": item.get("related", {})})
        rel = item.get("related", {}) if isinstance(item.get("related"), dict) else {}
        if rel.get("session_id") and item["result_type"] == "simulation_report":
            edges.append({"edge_id": _record_id("edge"), "source_node": item["result_id"], "target_node": f"simulation_session:{rel.get('session_id')}", "relationship_type": "derived_from", "created_at": _now(), "safe_metadata": {}})
    return {"nodes": redact_data(nodes), "edges": redact_data(edges), "secret_values_returned": False}


def simulation_analytics_context() -> dict[str, Any]:
    summary = simulation_summary()
    return {"simulation_sessions": summary.get("session_count", 0), "process_backtests_completed": summary.get("process_backtest_count", 0), "no_trade_simulations": summary.get("no_trade_simulation_count", 0), "recurring_simulated_blockers": "unknown/unavailable until simulation reports exist", "next_simulation_review_action": summary.get("next_simulation_review_action"), "secret_values_returned": False}

# v4.4.0-real dataset integration for Simulation Lab inputs.
_simulation_summary_v34 = simulation_summary

def simulation_summary() -> dict[str, Any]:  # type: ignore[override]
    summary = _simulation_summary_v34()
    try:
        from .live_v3_datasets import dataset_simulation_context
        ds = dataset_simulation_context()
    except Exception as exc:
        ds = {"dataset_selected": False, "error_redacted": redact_text(str(exc)), "secret_values_returned": False}
    summary["dataset_context"] = ds
    summary["replay_dataset_selected"] = ds.get("dataset_selected", False)
    summary["dataset_quality_status"] = ds.get("dataset_quality_status", "unknown")
    summary["secret_values_returned"] = False
    return redact_data(summary)

_export_simulation_json_v34 = export_simulation_json

def export_simulation_json() -> dict[str, Any]:  # type: ignore[override]
    data = _export_simulation_json_v34()
    try:
        from .live_v3_datasets import dataset_simulation_context
        data["dataset_context"] = dataset_simulation_context()
    except Exception as exc:
        data["dataset_context"] = {"dataset_selected": False, "error_redacted": redact_text(str(exc)), "secret_values_returned": False}
    data["secret_values_returned"] = False
    return redact_data(data)


# v4.4.0-real freshness context integration for simulation readiness.
_simulation_summary_v35 = simulation_summary

def simulation_summary() -> dict[str, Any]:  # type: ignore[override]
    summary = _simulation_summary_v35()
    try:
        from .live_v3_freshness import summary as freshness_summary, readiness_report
        summary["freshness_context"] = freshness_summary()
        summary["freshness_readiness"] = readiness_report(write=False)
    except Exception as exc:
        summary.setdefault("warnings", []).append(f"Freshness simulation context unavailable: {redact_text(str(exc))}")
    summary["secret_values_returned"] = False
    return redact_data(summary)
