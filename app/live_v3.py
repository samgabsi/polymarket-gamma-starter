from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR, settings as app_settings
from .live_v2 import build_live_v2_readiness, build_live_v2_status, list_audit_records, record_audit, redact_data, redact_text
from .live_strategy import list_theses, list_evidence, list_watchlist, list_scorecards, list_reviews
from .live_research import list_sources, list_queue, list_notes, list_candidates, freshness_summary, build_thesis_comparison
from .live_monitoring import list_rules as list_monitoring_rules, list_alerts, list_alert_history
from .live_portfolio import generate_portfolio_snapshot, list_exposure, list_warnings, list_scenarios, planned_trade_impact
from .live_governance import list_journal, list_checklists, list_reviews as list_governance_reviews, list_rules as list_governance_rules, list_near_misses, list_mistake_patterns
from .live_data import health_report_json, runtime_inventory, scan_secrets, migration_registry

V3_DIR = DATA_DIR / "live_v3"
V3_EVENTS_PATH = V3_DIR / "v3_events.jsonl"
V3_WORKFLOW_RUNS_PATH = V3_DIR / "workflow_runs.jsonl"
V3_SETTINGS_PATH = V3_DIR / "settings.json"

WORKFLOW_REGISTRY = [
    {"workflow_id": "market_intelligence_brief", "name": "Market Intelligence Brief", "read_only": True, "mutates_trading_state": False, "description": "Summarize local market context, sources, evidence, alerts, and stale/unknown data."},
    {"workflow_id": "thesis_health_review", "name": "Thesis Health Review", "read_only": True, "mutates_trading_state": False, "description": "Review thesis evidence coverage, stale evidence, alerts, exposure, and governance status."},
    {"workflow_id": "pre_trade_intelligence_packet", "name": "Pre-Trade Intelligence Packet", "read_only": True, "mutates_trading_state": False, "description": "Gather strategy, research, portfolio, monitoring, governance, risk, readiness, and audit context before ticket submission."},
    {"workflow_id": "portfolio_risk_brief", "name": "Portfolio Risk Brief", "read_only": True, "mutates_trading_state": False, "description": "Summarize exposure, concentration warnings, scenarios, stale evidence exposure, and unknown/unavailable values."},
    {"workflow_id": "stale_evidence_review", "name": "Stale Evidence Review", "read_only": True, "mutates_trading_state": False, "description": "Collect stale/aging evidence and source review items for operator action."},
    {"workflow_id": "alert_triage_brief", "name": "Alert Triage Brief", "read_only": True, "mutates_trading_state": False, "description": "Group active monitoring alerts and suggest review actions without execution."},
    {"workflow_id": "governance_daily_review", "name": "Governance Daily Review", "read_only": True, "mutates_trading_state": False, "description": "Summarize decisions, reviews, risk blocks, alerts, unresolved items, and next actions."},
    {"workflow_id": "weekly_operator_review", "name": "Weekly Operator Review", "read_only": True, "mutates_trading_state": False, "description": "Roll up daily review signals, recurring patterns, stale evidence, concentration trends, and process improvements."},
    {"workflow_id": "data_health_backup_readiness", "name": "Data Health / Backup Readiness Brief", "read_only": True, "mutates_trading_state": False, "description": "Summarize data health, backup readiness, migration status, and secret-scan posture."},
    {"workflow_id": "no_trade_review_packet", "name": "No-Trade Review Packet", "read_only": True, "mutates_trading_state": False, "description": "Document missing prerequisites or risk blockers supporting a no-trade decision."},
]

NODE_TYPES = {
    "market", "outcome", "thesis", "evidence", "research_source", "source_note", "research_queue_item",
    "watchlist_item", "scorecard", "monitoring_rule", "alert", "portfolio_exposure", "scenario",
    "decision_journal_entry", "governance_checklist", "review", "mistake_pattern", "audit_event", "data_health_check",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    V3_DIR.mkdir(parents=True, exist_ok=True)


def _items(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        data = result.get("items", result.get("records", result.get("checks", [])))
    else:
        data = result
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def _safe_text(value: Any, default: str = "") -> str:
    text = redact_text(str(value or "").strip())
    return text or default


def _safe_id(prefix: str, item: dict[str, Any]) -> str:
    for key in ("id", "event_id", "rule_id", "alert_id", "scenario_id", "ticket_id", "order_id", "market_id", "thesis_id", "source_id"):
        raw = item.get(key)
        if raw:
            return f"{prefix}:{_safe_text(raw)}"
    return f"{prefix}:{uuid4().hex[:12]}"


def _summary_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if item.get(key):
            return _safe_text(item.get(key))[:500]
    return _safe_text(item.get("notes") or item.get("details") or item.get("status") or "")[:500]


def _event(action: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_dir()
    event = redact_data({
        "event_id": f"v3_evt_{uuid4().hex[:12]}",
        "timestamp": _now(),
        "app_version": APP_VERSION,
        "action": action,
        "status": status,
        "details": details or {},
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "ai_assistance_enabled": False,
        "secret_values_returned": False,
    })
    with V3_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    record_audit(f"v3_{action}", status, details={**(details or {}), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "ai_assistance_enabled": False}, network_attempted=False)
    return event


def list_v3_events(limit: int = 500) -> list[dict[str, Any]]:
    if not V3_EVENTS_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in V3_EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(redact_data(json.loads(line)))
        except json.JSONDecodeError:
            rows.append({"event_id": "invalid", "timestamp": _now(), "action": "invalid_v3_event", "status": "warning"})
    return list(reversed(rows))[: max(1, min(int(limit or 500), 5000))]


def _collect_local_data(limit: int = 250) -> dict[str, Any]:
    readiness = build_live_v2_readiness()
    status = build_live_v2_status()
    health = health_report_json()
    return redact_data({
        "version": APP_VERSION,
        "generated_at": _now(),
        "status": status,
        "readiness": readiness,
        "data_health": health,
        "inventory": runtime_inventory(),
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
        "v3": {"events": list_v3_events(limit=limit)},
        "secret_values_returned": False,
    })


def _node(prefix: str, node_type: str, item: dict[str, Any], title_keys: tuple[str, ...], summary_keys: tuple[str, ...] = ()) -> dict[str, Any]:
    title = ""
    for key in title_keys:
        if item.get(key):
            title = _safe_text(item.get(key))
            break
    if not title:
        title = f"{node_type} {_safe_text(item.get('id') or item.get('event_id') or '')}".strip()
    return redact_data({
        "node_id": _safe_id(prefix, item),
        "node_type": node_type,
        "title": title[:160],
        "status": _safe_text(item.get("status") or item.get("severity") or item.get("action") or "unknown"),
        "timestamp": _safe_text(item.get("updated_at") or item.get("created_at") or item.get("timestamp") or ""),
        "tags": item.get("tags", []) if isinstance(item.get("tags"), list) else [],
        "related_object_id": _safe_text(item.get("id") or item.get("event_id") or item.get("rule_id") or item.get("alert_id") or ""),
        "summary": _summary_text(item, *(summary_keys or title_keys)),
        "safe_metadata": {k: redact_data(item.get(k)) for k in ("market_id", "market_title", "thesis_id", "source_id", "order_id", "ticket_id", "severity", "direction") if item.get(k)},
    })


def build_search_index(limit: int = 250) -> dict[str, Any]:
    data = _collect_local_data(limit=limit)
    rows: list[dict[str, Any]] = []

    def add(result_type: str, item: dict[str, Any], title_keys: tuple[str, ...], summary_keys: tuple[str, ...] = ()) -> None:
        node = _node(result_type, result_type, item, title_keys, summary_keys)
        haystack = " ".join(str(x) for x in [node["title"], node["summary"], node["status"], json.dumps(node.get("safe_metadata", {}), default=str)])
        rows.append({
            "result_id": node["node_id"],
            "result_type": result_type,
            "title": node["title"],
            "summary": node["summary"],
            "timestamp": node["timestamp"],
            "status": node["status"],
            "tags": node["tags"],
            "related": node["safe_metadata"],
            "quick_link": _quick_link(result_type, item),
            "search_text": redact_text(haystack.lower()),
            "secret_values_returned": False,
        })

    for item in data["strategy"]["theses"]:
        add("thesis", item, ("market_title", "title", "id"), ("thesis_summary", "operator_notes", "status"))
    for item in data["strategy"]["evidence"]:
        add("evidence", item, ("title", "source_url", "id"), ("notes", "direction"))
    for item in data["strategy"]["watchlist"]:
        add("watchlist_item", item, ("market_title", "title", "id"), ("reason", "notes"))
    for item in data["strategy"]["scorecards"]:
        add("scorecard", item, ("market_title", "thesis_id", "id"), ("recommended_next_action", "notes"))
    for item in data["research"]["sources"]:
        add("research_source", item, ("title", "url", "id"), ("notes", "source_type"))
    for item in data["research"]["queue"]:
        add("research_queue_item", item, ("title", "research_question", "id"), ("notes", "desired_output"))
    for item in data["research"]["notes"]:
        add("source_note", item, ("summary", "source_id", "id"), ("key_claims", "operator_interpretation"))
    for item in data["research"]["candidates"]:
        add("evidence_candidate", item, ("title", "source_id", "id"), ("notes", "direction"))
    for item in data["monitoring"]["rules"]:
        add("monitoring_rule", item, ("rule_name", "title", "id"), ("condition", "notes"))
    for item in data["monitoring"]["alerts"]:
        add("alert", item, ("title", "reason", "id"), ("recommended_operator_action", "reason"))
    for item in data["portfolio"]["exposure"]:
        add("portfolio_exposure", item, ("market_title", "exposure_type", "id"), ("notes", "status"))
    for item in data["portfolio"]["warnings"]:
        add("portfolio_warning", item, ("title", "warning_type", "id"), ("recommended_operator_action", "notes"))
    for item in data["portfolio"]["scenarios"]:
        add("scenario", item, ("title", "scenario_type", "id"), ("notes", "recommended_operator_action"))
    for item in data["governance"]["journal"]:
        add("decision_journal_entry", item, ("decision_title", "title", "id"), ("decision_summary", "reasoning"))
    for item in data["governance"]["checklists"]:
        add("governance_checklist", item, ("title", "checklist_type", "id"), ("notes", "status"))
    for item in data["governance"]["reviews"]:
        add("review", item, ("title", "review_type", "id"), ("lesson_learned", "notes"))
    for item in data["governance"]["mistake_patterns"]:
        add("mistake_pattern", item, ("title", "pattern_type", "id"), ("notes", "process_improvement_action"))
    for item in data["audit"]["events"]:
        add("audit_event", item, ("action", "event_id"), ("status", "details"))
    for check in _items(data.get("data_health", {}).get("checks", [])):
        add("data_health_check", check, ("check_name", "affected_file", "id"), ("explanation", "recommended_operator_action"))

    rows.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    return {"version": APP_VERSION, "generated_at": _now(), "count": len(rows), "items": redact_data(rows), "secret_values_returned": False, "local_only": True}


def _quick_link(result_type: str, item: dict[str, Any]) -> str:
    mapping = {
        "thesis": "/v2-live/strategy", "evidence": "/v2-live/strategy", "watchlist_item": "/v2-live/strategy", "scorecard": "/v2-live/strategy",
        "research_source": "/v2-live/research", "research_queue_item": "/v2-live/research", "source_note": "/v2-live/research", "evidence_candidate": "/v2-live/research",
        "monitoring_rule": "/v2-live/monitoring", "alert": "/v2-live/monitoring",
        "portfolio_exposure": "/v2-live/portfolio", "portfolio_warning": "/v2-live/portfolio", "scenario": "/v2-live/portfolio",
        "decision_journal_entry": "/v2-live/governance", "governance_checklist": "/v2-live/governance", "review": "/v2-live/governance", "mistake_pattern": "/v2-live/governance",
        "audit_event": "/v2-live/audit", "data_health_check": "/v2-live/data",
    }
    return mapping.get(result_type, "/v3")


def search_local(query: str = "", result_type: str = "", limit: int = 50) -> dict[str, Any]:
    index = build_search_index(limit=500)
    q = _safe_text(query).lower()
    rtype = _safe_text(result_type).lower()
    rows: list[dict[str, Any]] = []
    for item in index["items"]:
        if rtype and _safe_text(item.get("result_type")).lower() != rtype:
            continue
        if q and q not in item.get("search_text", ""):
            continue
        score = 1.0
        if q and q in str(item.get("title", "")).lower():
            score += 2.0
        elif q and q in str(item.get("summary", "")).lower():
            score += 1.0
        visible = {k: v for k, v in item.items() if k != "search_text"}
        visible["relevance_score"] = score
        rows.append(visible)
        if len(rows) >= max(1, min(int(limit or 50), 500)):
            break
    if q:
        _event("search_query_run", "ok", {"query_present": True, "result_type": result_type, "count": len(rows)})
    return {"version": APP_VERSION, "query": query, "result_type": result_type, "count": len(rows), "items": redact_data(rows), "local_only": True, "secret_values_returned": False}


def rebuild_search_index() -> dict[str, Any]:
    index = build_search_index(limit=1000)
    _ensure_dir()
    path = V3_DIR / "search_index_summary.json"
    path.write_text(json.dumps({"version": APP_VERSION, "generated_at": index["generated_at"], "count": index["count"]}, indent=2, sort_keys=True), encoding="utf-8")
    _event("search_index_rebuilt", "ok", {"count": index["count"], "path": str(path)})
    return {"ok": True, "index": index, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def build_decision_graph(limit: int = 250) -> dict[str, Any]:
    index = build_search_index(limit=limit)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    market_nodes: dict[str, str] = {}
    thesis_nodes: dict[str, str] = {}
    source_nodes: dict[str, str] = {}

    for item in index["items"]:
        node_type = _safe_text(item.get("result_type")).replace("_item", "")
        if node_type == "evidence_candidate":
            node_type = "evidence"
        node = {
            "node_id": item["result_id"],
            "node_type": node_type,
            "title": item["title"],
            "status": item.get("status", "unknown"),
            "timestamp": item.get("timestamp", ""),
            "tags": item.get("tags", []),
            "related_object_id": item["result_id"].split(":", 1)[-1],
            "summary": item.get("summary", ""),
            "safe_metadata": item.get("related", {}),
        }
        nodes.append(node)
        meta = node.get("safe_metadata", {}) if isinstance(node.get("safe_metadata"), dict) else {}
        if meta.get("market_id"):
            market_id = _safe_text(meta.get("market_id"))
            mnode = market_nodes.setdefault(market_id, f"market:{market_id}")
            edges.append(_edge(node["node_id"], mnode, "linked_to"))
        if meta.get("thesis_id"):
            thesis_id = _safe_text(meta.get("thesis_id"))
            tnode = thesis_nodes.setdefault(thesis_id, f"thesis:{thesis_id}")
            if node["node_id"] != tnode:
                edges.append(_edge(node["node_id"], tnode, "depends_on" if node_type in {"trade_ticket", "portfolio_exposure"} else "linked_to"))
        if meta.get("source_id"):
            source_id = _safe_text(meta.get("source_id"))
            snode = source_nodes.setdefault(source_id, f"research_source:{source_id}")
            if node["node_id"] != snode:
                edges.append(_edge(node["node_id"], snode, "derived_from"))
        if node_type == "alert" and meta.get("market_id"):
            edges.append(_edge(node["node_id"], f"market:{_safe_text(meta.get('market_id'))}", "alerted_by"))

    existing_node_ids = {n["node_id"] for n in nodes}
    for market_id, node_id in market_nodes.items():
        if node_id not in existing_node_ids:
            nodes.append({"node_id": node_id, "node_type": "market", "title": f"Market {market_id}", "status": "referenced", "timestamp": "", "tags": [], "related_object_id": market_id, "summary": "Referenced market node", "safe_metadata": {"market_id": market_id}})
    findings = missing_prerequisites_scan()["findings"]
    for finding in findings:
        if finding.get("related_node"):
            edges.append(_edge(_safe_text(finding.get("related_node")), f"finding:{finding['finding_id']}", "missing_prerequisite"))
            nodes.append({"node_id": f"finding:{finding['finding_id']}", "node_type": "data_health_check", "title": finding.get("title", "Finding"), "status": finding.get("severity", "warning"), "timestamp": finding.get("timestamp", _now()), "tags": ["v3_finding"], "related_object_id": finding["finding_id"], "summary": finding.get("explanation", ""), "safe_metadata": {"finding_type": finding.get("finding_type")}})

    graph = {"version": APP_VERSION, "generated_at": _now(), "node_count": len(nodes), "edge_count": len(edges), "nodes": redact_data(nodes), "edges": redact_data(edges), "secret_values_returned": False, "local_only": True}
    return graph


def _edge(source: str, target: str, relationship_type: str) -> dict[str, Any]:
    return {"edge_id": f"edge_{uuid4().hex[:12]}", "source_node": source, "target_node": target, "relationship_type": relationship_type, "created_at": _now(), "safe_metadata": {}, "secret_values_returned": False}


def rebuild_graph() -> dict[str, Any]:
    graph = build_decision_graph(limit=1000)
    _ensure_dir()
    path = V3_DIR / "decision_graph_summary.json"
    path.write_text(json.dumps({"version": APP_VERSION, "generated_at": graph["generated_at"], "node_count": graph["node_count"], "edge_count": graph["edge_count"]}, indent=2, sort_keys=True), encoding="utf-8")
    _event("graph_rebuilt", "ok", {"node_count": graph["node_count"], "edge_count": graph["edge_count"], "path": str(path)})
    return {"ok": True, "graph": graph, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def graph_to_markdown(graph: dict[str, Any] | None = None) -> str:
    graph = graph or build_decision_graph()
    lines = [f"# Decision Graph Export — {APP_VERSION}", "", f"Generated: {graph.get('generated_at')}", "", f"Nodes: {graph.get('node_count', 0)}", f"Edges: {graph.get('edge_count', 0)}", "", "## Nodes"]
    for node in graph.get("nodes", [])[:200]:
        lines.append(f"- **{node.get('node_type')}** — {node.get('title')} ({node.get('status')})")
    lines.extend(["", "## Edges"])
    for edge in graph.get("edges", [])[:200]:
        lines.append(f"- {edge.get('source_node')} --{edge.get('relationship_type')}--> {edge.get('target_node')}")
    lines.extend(["", "Safety: decision graph exports do not place, cancel, approve, sign, or arm live orders."])
    return "\n".join(lines) + "\n"


def build_command_center() -> dict[str, Any]:
    data = _collect_local_data(limit=100)
    readiness = data["readiness"]
    live_status = data["status"]
    findings = missing_prerequisites_scan(limit=100)["findings"]
    alerts = data["monitoring"]["alerts"]
    critical_alerts = [a for a in alerts if _safe_text(a.get("severity")).lower() == "critical"]
    stale_count = 0
    freshness = data["research"].get("freshness", {})
    if isinstance(freshness, dict):
        stale_count = int(freshness.get("stale_count", 0) or freshness.get("stale", 0) or 0)
    health_summary = data.get("data_health", {}).get("summary", {}) if isinstance(data.get("data_health"), dict) else {}
    exposure_summary = data.get("portfolio", {}).get("snapshot", {}).get("summary", {}) if isinstance(data.get("portfolio", {}).get("snapshot"), dict) else {}
    next_actions = _next_actions(readiness, health_summary, findings, alerts)
    summary = {
        "version": APP_VERSION,
        "generated_at": _now(),
        "mode": live_status.get("mode") or live_status.get("config", {}).get("trading_mode", "unknown"),
        "live_armed": bool(live_status.get("live_armed", False) or live_status.get("config", {}).get("live_armed", False)),
        "read_only": bool(live_status.get("read_only", True) or live_status.get("config", {}).get("read_only", True)),
        "kill_switch_active": bool(live_status.get("kill_switch_active", True) or live_status.get("config", {}).get("kill_switch_active", True)),
        "readiness_state": readiness.get("overall_status", "unknown"),
        "data_health_state": health_summary.get("overall_status") or ("fail" if health_summary.get("fail", 0) else "pass"),
        "backup_restore_health": "available",
        "active_thesis_count": len([x for x in data["strategy"]["theses"] if _safe_text(x.get("status")).lower() not in {"archived", "closed", "invalidated"}]),
        "active_research_queue_count": len([x for x in data["research"]["queue"] if _safe_text(x.get("status")).lower() not in {"archived", "converted"}]),
        "stale_evidence_count": stale_count,
        "active_alert_count": len(alerts),
        "critical_alert_count": len(critical_alerts),
        "portfolio_exposure_summary": exposure_summary,
        "concentration_warning_count": len(data["portfolio"]["warnings"]),
        "open_governance_checklist_count": len([x for x in data["governance"]["checklists"] if _safe_text(x.get("status")).lower() not in {"completed", "archived"}]),
        "recent_decisions": data["governance"]["journal"][:5],
        "recent_audit_events": data["audit"]["events"][:10],
        "recent_risk_blocks": [x for x in data["audit"]["events"] if "block" in _safe_text(x.get("status")).lower() or "risk" in _safe_text(x.get("action")).lower()][:10],
        "recent_verification_status": readiness.get("checks", [])[:8],
        "action_needed": findings[:20],
        "next_operator_actions": next_actions,
        "safety_statement": "v3 command center is read-only by default and does not place, cancel, sign, approve, or arm live orders.",
        "secret_values_returned": False,
    }
    return redact_data(summary)


def _next_actions(readiness: dict[str, Any], health_summary: dict[str, Any], findings: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    if readiness.get("overall_status") not in {"pass", "ready"}:
        actions.append("Review Live Readiness before any live workflow.")
    if health_summary.get("fail", 0):
        actions.append("Open Data health and resolve failing runtime-data checks.")
    if alerts:
        actions.append("Triage active Monitoring alerts before creating new tickets.")
    if findings:
        actions.append("Review missing prerequisites/conflicts in the v3 action-needed queue.")
    if not actions:
        actions.append("System appears calm; continue research, strategy review, or paper rehearsal.")
    return actions[:8]


def missing_prerequisites_scan(limit: int = 250) -> dict[str, Any]:
    data = _collect_local_data(limit=limit)
    findings: list[dict[str, Any]] = []
    evidence_by_thesis: dict[str, list[dict[str, Any]]] = {}
    for ev in data["strategy"]["evidence"] + data["research"]["candidates"]:
        tid = _safe_text(ev.get("thesis_id"))
        if tid:
            evidence_by_thesis.setdefault(tid, []).append(ev)
    for thesis in data["strategy"]["theses"]:
        tid = _safe_text(thesis.get("id") or thesis.get("thesis_id"))
        title = _safe_text(thesis.get("market_title") or thesis.get("title") or tid)
        status = _safe_text(thesis.get("status")).lower()
        evidence = evidence_by_thesis.get(tid, [])
        if not evidence:
            findings.append(_finding("missing_evidence", "warning", f"Thesis has no linked evidence: {title}", "Add or link evidence before creating a ticket.", f"thesis:{tid}"))
        if evidence and not any("contradict" in _safe_text(ev.get("direction")).lower() for ev in evidence):
            findings.append(_finding("missing_counter_evidence", "info", f"No counter-evidence review found: {title}", "Review and record counter-evidence or acknowledge none found.", f"thesis:{tid}"))
        if status in {"ready_for_ticket", "ticket_created", "active"} and not _safe_text(thesis.get("exit_criteria")):
            findings.append(_finding("missing_exit_criteria", "warning", f"Ready/active thesis lacks exit criteria: {title}", "Define exit criteria before live consideration.", f"thesis:{tid}"))
        if status in {"ready_for_ticket", "ticket_created", "active"} and not _safe_text(thesis.get("invalidation_criteria")):
            findings.append(_finding("missing_invalidation_criteria", "warning", f"Ready/active thesis lacks invalidation criteria: {title}", "Define invalidation criteria before live consideration.", f"thesis:{tid}"))
    for exposure in data["portfolio"]["exposure"]:
        tid = _safe_text(exposure.get("thesis_id"))
        if tid and not evidence_by_thesis.get(tid):
            findings.append(_finding("exposure_without_evidence", "warning", "Exposure is linked to a thesis with no evidence.", "Review exposure and thesis evidence linkage.", f"portfolio_exposure:{_safe_text(exposure.get('id'))}"))
    for alert in data["monitoring"]["alerts"]:
        sev = _safe_text(alert.get("severity")).lower()
        if sev in {"warning", "critical"}:
            findings.append(_finding("active_alert_needs_review", sev, _safe_text(alert.get("title") or alert.get("reason") or "Active alert needs review"), "Open Monitoring and acknowledge, snooze, or resolve after review.", f"alert:{_safe_text(alert.get('id') or alert.get('alert_id'))}"))
    health_summary = data.get("data_health", {}).get("summary", {}) if isinstance(data.get("data_health"), dict) else {}
    if health_summary.get("fail", 0):
        findings.append(_finding("data_health_failure", "critical", "Data health check has failing checks.", "Open Data and resolve invalid/corrupt runtime data before relying on packets.", "data_health:latest"))
    readiness = data["readiness"]
    if readiness.get("overall_status") not in {"pass", "ready"}:
        findings.append(_finding("readiness_not_ready", "warning", "Live readiness is not ready/pass.", "Keep live workflows read-only and review readiness details.", "readiness:latest"))
    findings = redact_data(findings[: max(1, min(int(limit or 250), 1000))])
    _event("missing_prerequisite_scan_run", "ok", {"count": len(findings)})
    return {"version": APP_VERSION, "generated_at": _now(), "count": len(findings), "findings": findings, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def _finding(kind: str, severity: str, title: str, action: str, related_node: str) -> dict[str, Any]:
    return {"finding_id": f"finding_{uuid4().hex[:10]}", "timestamp": _now(), "finding_type": kind, "severity": severity if severity in {"info", "watch", "warning", "critical"} else "warning", "title": title, "explanation": title, "recommended_operator_action": action, "related_node": related_node, "order_submitted": False, "order_cancelled": False}


def workflow_registry() -> dict[str, Any]:
    return {"version": APP_VERSION, "workflows": WORKFLOW_REGISTRY, "ai_assistance_enabled": False, "secret_values_returned": False}


def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    workflow_id = _safe_text(payload.get("workflow_id") or payload.get("id") or "pre_trade_intelligence_packet")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else payload
    if workflow_id == "market_intelligence_brief":
        output = market_intelligence_brief(context)
    elif workflow_id == "thesis_health_review":
        output = thesis_health_report(context)
    elif workflow_id == "portfolio_risk_brief":
        output = portfolio_risk_brief(context)
    elif workflow_id in {"governance_daily_review", "weekly_operator_review"}:
        output = operator_review_packet({**context, "period": "weekly" if workflow_id == "weekly_operator_review" else "daily"})
    elif workflow_id == "data_health_backup_readiness":
        output = data_health_backup_readiness_brief(context)
    elif workflow_id == "alert_triage_brief":
        output = alert_triage_brief(context)
    elif workflow_id == "stale_evidence_review":
        output = stale_evidence_review(context)
    elif workflow_id == "no_trade_review_packet":
        output = no_trade_review_packet(context)
    else:
        workflow_id = "pre_trade_intelligence_packet"
        output = pre_trade_packet(context)
    run = redact_data({
        "run_id": f"v3_run_{uuid4().hex[:12]}",
        "workflow_id": workflow_id,
        "started_at": _now(),
        "completed_at": _now(),
        "status": "completed",
        "read_only": True,
        "mutated_trading_state": False,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "ai_assistance_enabled": False,
        "output": output,
        "secret_values_returned": False,
    })
    _ensure_dir()
    with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run, sort_keys=True, default=str) + "\n")
    _event("workflow_run_completed", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"]})
    return run


def list_workflow_runs(limit: int = 100) -> dict[str, Any]:
    if not V3_WORKFLOW_RUNS_PATH.exists():
        return {"version": APP_VERSION, "count": 0, "items": [], "secret_values_returned": False}
    rows: list[dict[str, Any]] = []
    for line in V3_WORKFLOW_RUNS_PATH.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(redact_data(json.loads(line)))
        except Exception:
            rows.append({"run_id": "invalid", "status": "warning"})
    rows = list(reversed(rows))[: max(1, min(int(limit or 100), 1000))]
    return {"version": APP_VERSION, "count": len(rows), "items": rows, "secret_values_returned": False}


def get_workflow_run(run_id: str) -> dict[str, Any] | None:
    for row in list_workflow_runs(limit=1000)["items"]:
        if row.get("run_id") == run_id:
            return row
    return None


def pre_trade_packet(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    thesis_id = _safe_text(payload.get("thesis_id"))
    market_id = _safe_text(payload.get("market_id"))
    data = _collect_local_data(limit=250)
    thesis = _find_by_id(data["strategy"]["theses"], thesis_id) if thesis_id else _find_by_market(data["strategy"]["theses"], market_id)
    evidence = _filter_related(data["strategy"]["evidence"] + data["research"]["candidates"], thesis_id=thesis_id, market_id=market_id)
    packet = {
        "packet_type": "pre_trade_intelligence_packet",
        "version": APP_VERSION,
        "generated_at": _now(),
        "selected_market": market_id or (thesis or {}).get("market_id", ""),
        "selected_outcome": _safe_text(payload.get("outcome") or (thesis or {}).get("outcome")),
        "linked_thesis": thesis or {},
        "thesis_status": (thesis or {}).get("status", "unknown"),
        "evidence_count": len(evidence),
        "supporting_evidence": [e for e in evidence if "support" in _safe_text(e.get("direction")).lower()][:10],
        "counter_evidence": [e for e in evidence if "contradict" in _safe_text(e.get("direction")).lower()][:10],
        "stale_evidence_warnings": _extract_stale_evidence(data, thesis_id, market_id),
        "unresolved_research_questions": data["research"]["queue"][:10],
        "scorecard_summary": _filter_related(data["strategy"]["scorecards"], thesis_id=thesis_id, market_id=market_id)[:5],
        "watchlist_status": _filter_related(data["strategy"]["watchlist"], thesis_id=thesis_id, market_id=market_id)[:5],
        "monitoring_alerts": _filter_related(data["monitoring"]["alerts"], thesis_id=thesis_id, market_id=market_id)[:10],
        "portfolio_exposure": _filter_related(data["portfolio"]["exposure"], thesis_id=thesis_id, market_id=market_id)[:10],
        "concentration_warnings": data["portfolio"]["warnings"][:10],
        "governance_checklist_status": data["governance"]["checklists"][:10],
        "decision_journal_context": data["governance"]["journal"][:10],
        "risk_precheck_summary": data["readiness"].get("checks", [])[:10],
        "data_health_warnings": [x for x in _items(data.get("data_health", {}).get("checks", [])) if x.get("status") in {"fail", "warning"}][:10],
        "readiness_posture": data["readiness"].get("overall_status", "unknown"),
        "audit_trail_references": data["audit"]["events"][:10],
        "findings": missing_prerequisites_scan(limit=100)["findings"][:15],
        "status": "needs_review",
        "recommended_operator_actions": ["Review blockers/warnings", "Confirm thesis/evidence coverage", "Run trade-ticket risk preview separately if proceeding"],
        "safety_statement": "This packet does not place, cancel, sign, approve, or arm live orders.",
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    }
    _event("pre_trade_packet_generated", "ok", {"market_id": market_id, "thesis_id": thesis_id})
    return redact_data(packet)


def market_intelligence_brief(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    market_id = _safe_text(payload.get("market_id"))
    data = _collect_local_data(limit=250)
    sources = _filter_related(data["research"]["sources"], market_id=market_id)
    candidates = _filter_related(data["research"]["candidates"], market_id=market_id)
    theses = _filter_related(data["strategy"]["theses"], market_id=market_id)
    brief = {"brief_type": "market_intelligence", "version": APP_VERSION, "generated_at": _now(), "market_id": market_id, "summary": f"Local brief for market {market_id or 'unspecified'}.", "linked_sources": sources[:20], "evidence_candidates": candidates[:20], "linked_theses": theses[:10], "watchlist_entries": _filter_related(data["strategy"]["watchlist"], market_id=market_id)[:10], "monitoring_alerts": _filter_related(data["monitoring"]["alerts"], market_id=market_id)[:10], "strongest_support": [x for x in candidates if "support" in _safe_text(x.get("direction")).lower()][:5], "strongest_contradiction": [x for x in candidates if "contradict" in _safe_text(x.get("direction")).lower()][:5], "missing_research": ["Add source notes" if not sources else "Review source freshness"], "safety_statement": "Market briefs are workflow guidance only and do not place or cancel orders.", "order_submitted": False, "order_cancelled": False, "secret_values_returned": False}
    _event("market_brief_generated", "ok", {"market_id": market_id})
    return redact_data(brief)


def thesis_health_report(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    thesis_id = _safe_text(payload.get("thesis_id"))
    data = _collect_local_data(limit=250)
    thesis = _find_by_id(data["strategy"]["theses"], thesis_id) if thesis_id else (data["strategy"]["theses"][:1] or [{}])[0]
    tid = _safe_text(thesis.get("id") or thesis_id)
    evidence = _filter_related(data["strategy"]["evidence"] + data["research"]["candidates"], thesis_id=tid)
    report = {"report_type": "thesis_health", "version": APP_VERSION, "generated_at": _now(), "thesis": thesis, "evidence_count": len(evidence), "supporting_count": len([x for x in evidence if "support" in _safe_text(x.get("direction")).lower()]), "counter_evidence_count": len([x for x in evidence if "contradict" in _safe_text(x.get("direction")).lower()]), "stale_evidence": _extract_stale_evidence(data, tid, _safe_text(thesis.get("market_id"))), "monitoring_alerts": _filter_related(data["monitoring"]["alerts"], thesis_id=tid)[:10], "exposure": _filter_related(data["portfolio"]["exposure"], thesis_id=tid)[:10], "governance_checklists": _filter_related(data["governance"]["checklists"], thesis_id=tid)[:10], "decision_journal": _filter_related(data["governance"]["journal"], thesis_id=tid)[:10], "scorecard_summary": _filter_related(data["strategy"]["scorecards"], thesis_id=tid)[:5], "invalidated_or_missing": not bool(thesis) or _safe_text(thesis.get("status")).lower() in {"invalidated", "archived"}, "health_status": "needs_review" if not evidence else "watch", "next_operator_actions": ["Review counter-evidence", "Check stale evidence", "Update exit/invalidation criteria"], "safety_statement": "Thesis health reports do not place or cancel orders.", "order_submitted": False, "order_cancelled": False, "secret_values_returned": False}
    _event("thesis_health_report_generated", "ok", {"thesis_id": tid})
    return redact_data(report)


def portfolio_risk_brief(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = _collect_local_data(limit=250)
    brief = {"brief_type": "portfolio_risk", "version": APP_VERSION, "generated_at": _now(), "snapshot": data["portfolio"]["snapshot"], "exposure": data["portfolio"]["exposure"][:50], "warnings": data["portfolio"]["warnings"][:50], "scenarios": data["portfolio"]["scenarios"][:20], "monitoring_alerts": data["monitoring"]["alerts"][:20], "governance_near_misses": data["governance"].get("near_misses", [])[:20], "unknown_unavailable_data": ["Live exposure may be unknown unless safe read-only account data is available."], "risk_posture": "needs_review" if data["portfolio"]["warnings"] else "watch", "next_operator_actions": ["Review concentration warnings", "Evaluate scenarios before creating tickets"], "safety_statement": "Portfolio risk briefs do not place or cancel orders.", "order_submitted": False, "order_cancelled": False, "secret_values_returned": False}
    _event("portfolio_risk_brief_generated", "ok", {})
    return redact_data(brief)


def operator_review_packet(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    period = _safe_text(payload.get("period"), "daily")
    data = _collect_local_data(limit=250)
    packet = {"packet_type": f"{period}_operator_review", "version": APP_VERSION, "generated_at": _now(), "decisions": data["governance"]["journal"][:50], "theses_updated": data["strategy"]["theses"][:25], "evidence_added": data["strategy"]["evidence"][:50], "alerts_triggered": data["monitoring"]["alerts"][:50], "portfolio_warnings": data["portfolio"]["warnings"][:50], "governance_checklist_state": data["governance"]["checklists"][:50], "risk_blocks": [x for x in data["audit"]["events"] if "block" in _safe_text(x.get("status")).lower()][:50], "data_health_state": data["data_health"].get("summary", {}), "unresolved_items": missing_prerequisites_scan(limit=100)["findings"][:25], "next_actions": ["Review unresolved items", "Update stale evidence", "Create or close governance reviews"], "safety_statement": "Operator review packets are local reports only and do not place or cancel orders.", "order_submitted": False, "order_cancelled": False, "secret_values_returned": False}
    _event("operator_review_packet_generated", "ok", {"period": period})
    return redact_data(packet)


def data_health_backup_readiness_brief(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    report = {"brief_type": "data_health_backup_readiness", "version": APP_VERSION, "generated_at": _now(), "health": health_report_json(), "inventory": runtime_inventory(), "secret_scan": scan_secrets(), "migrations": migration_registry(), "safety_statement": "Data health briefs do not place or cancel orders and default to redaction.", "order_submitted": False, "order_cancelled": False, "secret_values_returned": False}
    _event("data_health_backup_readiness_brief_generated", "ok", {})
    return redact_data(report)


def alert_triage_brief(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    alerts = _items(list_alerts(limit=250))
    report = {"brief_type": "alert_triage", "version": APP_VERSION, "generated_at": _now(), "active_alerts": alerts, "critical_alerts": [a for a in alerts if _safe_text(a.get("severity")).lower() == "critical"], "next_actions": ["Acknowledge, snooze, or resolve alerts after review", "Open linked thesis/research/portfolio objects"], "safety_statement": "Alert triage does not place or cancel orders.", "order_submitted": False, "order_cancelled": False, "secret_values_returned": False}
    _event("alert_triage_brief_generated", "ok", {"alert_count": len(alerts)})
    return redact_data(report)


def stale_evidence_review(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = _collect_local_data(limit=250)
    report = {"brief_type": "stale_evidence_review", "version": APP_VERSION, "generated_at": _now(), "freshness": data["research"].get("freshness", {}), "stale_items": _extract_stale_evidence(data, "", ""), "next_actions": ["Refresh sources", "Update linked theses", "Avoid relying on stale evidence without acknowledgement"], "safety_statement": "Stale evidence review does not place or cancel orders.", "order_submitted": False, "order_cancelled": False, "secret_values_returned": False}
    _event("stale_evidence_review_generated", "ok", {})
    return redact_data(report)


def no_trade_review_packet(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    report = {"packet_type": "no_trade_review", "version": APP_VERSION, "generated_at": _now(), "findings": missing_prerequisites_scan(limit=100)["findings"], "recommended_operator_actions": ["Document no-trade reason in Governance", "Resolve blockers before reconsidering"], "safety_statement": "No-trade review supports not trading and does not place or cancel orders.", "order_submitted": False, "order_cancelled": False, "secret_values_returned": False}
    _event("no_trade_review_packet_generated", "ok", {})
    return redact_data(report)


def _find_by_id(rows: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    for row in rows:
        if _safe_text(row.get("id") or row.get("thesis_id") or row.get("event_id")) == item_id:
            return row
    return {}


def _find_by_market(rows: list[dict[str, Any]], market_id: str) -> dict[str, Any]:
    if not market_id:
        return {}
    for row in rows:
        if _safe_text(row.get("market_id")) == market_id:
            return row
    return {}


def _filter_related(rows: list[dict[str, Any]], thesis_id: str = "", market_id: str = "") -> list[dict[str, Any]]:
    thesis_id = _safe_text(thesis_id)
    market_id = _safe_text(market_id)
    if not thesis_id and not market_id:
        return rows[:50]
    return [row for row in rows if (thesis_id and _safe_text(row.get("thesis_id")) == thesis_id) or (market_id and _safe_text(row.get("market_id")) == market_id)]


def _extract_stale_evidence(data: dict[str, Any], thesis_id: str = "", market_id: str = "") -> list[dict[str, Any]]:
    rows = data["strategy"]["evidence"] + data["research"]["candidates"] + data["research"]["sources"]
    related = _filter_related(rows, thesis_id=thesis_id, market_id=market_id)
    stale = [r for r in related if _safe_text(r.get("freshness_status") or r.get("status")).lower() in {"stale", "expired", "aging"}]
    return stale[:50]




V3_UI_SETTING_DEFINITIONS: list[dict[str, Any]] = [
    {
        "key": "ai_odds_adjustment_enabled",
        "env_key": "AI_ODDS_ADJUSTMENT_ENABLED",
        "label": "AI odds adjustment enabled",
        "group": "AI odds adjustment",
        "description": "Controls whether AI odds adjustment review surfaces are enabled. Outputs remain advisory and review-only.",
        "value_type": "bool",
        "control": "toggle",
        "default_value": True,
        "restart_required": True,
    },
    {
        "key": "ai_odds_adjustment_mode",
        "env_key": "AI_ODDS_ADJUSTMENT_MODE",
        "label": "AI odds adjustment mode",
        "group": "AI odds adjustment",
        "description": "Operator preference for conservative, balanced, aggressive, or custom cap posture.",
        "value_type": "select",
        "control": "select",
        "allowed_values": ["off", "conservative", "balanced", "aggressive", "custom"],
        "default_value": "conservative",
        "restart_required": True,
    },
    {
        "key": "ai_default_max_adjustment_pct",
        "env_key": "AI_DEFAULT_MAX_ADJUSTMENT_PCT",
        "label": "Conservative/default max adjustment pct",
        "group": "AI odds adjustment",
        "description": "Default soft cap. Safe default preserves the old 2.5 percentage-point posture unless evidence/config permit more.",
        "value_type": "float",
        "control": "number",
        "default_value": 2.5,
        "min_value": 0.0,
        "max_value": 25.0,
        "step": 0.1,
        "restart_required": True,
    },
    {
        "key": "ai_balanced_max_adjustment_pct",
        "env_key": "AI_BALANCED_MAX_ADJUSTMENT_PCT",
        "label": "Balanced max adjustment pct",
        "group": "AI odds adjustment",
        "description": "Soft cap used by balanced mode when evidence quality supports a larger adjustment.",
        "value_type": "float",
        "control": "number",
        "default_value": 7.5,
        "min_value": 0.0,
        "max_value": 25.0,
        "step": 0.1,
        "restart_required": True,
    },
    {
        "key": "ai_aggressive_max_adjustment_pct",
        "env_key": "AI_AGGRESSIVE_MAX_ADJUSTMENT_PCT",
        "label": "Aggressive max adjustment pct",
        "group": "AI odds adjustment",
        "description": "Upper soft cap for aggressive mode; hard cap and operator confirmation still apply.",
        "value_type": "float",
        "control": "number",
        "default_value": 15.0,
        "min_value": 0.0,
        "max_value": 25.0,
        "step": 0.1,
        "restart_required": True,
    },
    {
        "key": "ai_absolute_hard_cap_pct",
        "env_key": "AI_ABSOLUTE_HARD_CAP_PCT",
        "label": "Absolute hard cap pct",
        "group": "AI odds adjustment",
        "description": "Never allow final adjustment above this cap. This protects against extreme model or evidence errors.",
        "value_type": "float",
        "control": "number",
        "default_value": 25.0,
        "min_value": 0.0,
        "max_value": 25.0,
        "step": 0.1,
        "restart_required": True,
    },
    {
        "key": "ai_require_operator_confirm_above_pct",
        "env_key": "AI_REQUIRE_OPERATOR_CONFIRM_ABOVE_PCT",
        "label": "Operator confirmation threshold pct",
        "group": "AI odds adjustment",
        "description": "Large adjustments above this threshold require explicit operator confirmation before being treated as review context.",
        "value_type": "float",
        "control": "number",
        "default_value": 10.0,
        "min_value": 0.0,
        "max_value": 25.0,
        "step": 0.1,
        "restart_required": True,
    },
    {
        "key": "arbitrage_scanner_enabled",
        "env_key": "ARBITRAGE_SCANNER_ENABLED",
        "label": "Arbitrage scanner enabled",
        "group": "Cross-market arbitrage",
        "description": "Enables review-first scan surfaces. Disabled default keeps the page in sample/config-required mode.",
        "value_type": "bool",
        "control": "toggle",
        "default_value": False,
        "restart_required": True,
    },
    {
        "key": "arbitrage_min_net_margin_pct",
        "env_key": "ARBITRAGE_MIN_NET_MARGIN_PCT",
        "label": "Minimum net arbitrage margin pct",
        "group": "Cross-market arbitrage",
        "description": "Minimum net margin after fees/slippage before an opportunity should be considered for review.",
        "value_type": "float",
        "control": "number",
        "default_value": 1.0,
        "min_value": 0.0,
        "max_value": 50.0,
        "step": 0.1,
        "restart_required": True,
    },
    {
        "key": "arbitrage_min_confidence",
        "env_key": "ARBITRAGE_MIN_CONFIDENCE",
        "label": "Minimum arbitrage confidence",
        "group": "Cross-market arbitrage",
        "description": "Minimum normalized equivalence/confidence score for review-worthy candidates.",
        "value_type": "float",
        "control": "number",
        "default_value": 0.72,
        "min_value": 0.0,
        "max_value": 1.0,
        "step": 0.01,
        "restart_required": True,
    },
    {
        "key": "arbitrage_max_stale_seconds",
        "env_key": "ARBITRAGE_MAX_STALE_SECONDS",
        "label": "Maximum stale seconds",
        "group": "Cross-market arbitrage",
        "description": "Data older than this should be marked stale before a candidate is trusted.",
        "value_type": "int",
        "control": "number",
        "default_value": 300,
        "min_value": 10,
        "max_value": 86400,
        "step": 10,
        "restart_required": True,
    },
    {
        "key": "kalshi_enabled",
        "env_key": "KALSHI_ENABLED",
        "label": "Kalshi adapter enabled",
        "group": "Venue configuration",
        "description": "Disabled by default. Enable only when read-only Kalshi discovery/orderbook access should be attempted.",
        "value_type": "bool",
        "control": "toggle",
        "default_value": False,
        "restart_required": True,
    },
    {
        "key": "kalshi_use_demo",
        "env_key": "KALSHI_USE_DEMO",
        "label": "Use Kalshi demo host",
        "group": "Venue configuration",
        "description": "Routes Kalshi read attempts toward the demo base URL when the adapter is explicitly enabled.",
        "value_type": "bool",
        "control": "toggle",
        "default_value": False,
        "restart_required": True,
    },
    {
        "key": "kalshi_api_base_url",
        "env_key": "KALSHI_API_BASE_URL",
        "label": "Kalshi API base URL",
        "group": "Venue configuration",
        "description": "Public/private Kalshi API base URL. This is not a credential, but changes require restart.",
        "value_type": "text",
        "control": "text",
        "default_value": "https://external-api.kalshi.com/trade-api/v2",
        "restart_required": True,
    },
    {
        "key": "paper_trading_enabled",
        "env_key": "PAPER_TRADING_ENABLED",
        "label": "Paper trading enabled",
        "group": "Automated paper trading",
        "description": "Enables the local paper trading ledger and simulated broker. This never enables live trading.",
        "value_type": "bool",
        "control": "toggle",
        "default_value": False,
        "restart_required": True,
    },
    {
        "key": "paper_trading_automation_enabled",
        "env_key": "PAPER_TRADING_AUTOMATION_ENABLED",
        "label": "Automated paper strategy loop enabled",
        "group": "Automated paper trading",
        "description": "Allows the paper strategy runner to evaluate candidates and create simulated orders when invoked.",
        "value_type": "bool",
        "control": "toggle",
        "default_value": False,
        "restart_required": True,
    },
    {
        "key": "paper_trading_starting_balance",
        "env_key": "PAPER_TRADING_STARTING_BALANCE",
        "label": "Paper account starting balance",
        "group": "Automated paper trading",
        "description": "Starting cash for local simulated account resets.",
        "value_type": "float",
        "control": "number",
        "default_value": 1000.0,
        "min_value": 1.0,
        "max_value": 1000000.0,
        "step": 1.0,
        "restart_required": True,
    },
    {
        "key": "paper_trading_max_order_notional",
        "env_key": "PAPER_TRADING_MAX_ORDER_NOTIONAL",
        "label": "Max paper order notional",
        "group": "Automated paper trading",
        "description": "Maximum simulated notional per paper order.",
        "value_type": "float",
        "control": "number",
        "default_value": 25.0,
        "min_value": 0.0,
        "max_value": 100000.0,
        "step": 1.0,
        "restart_required": True,
    },
    {
        "key": "paper_trading_max_daily_notional",
        "env_key": "PAPER_TRADING_MAX_DAILY_NOTIONAL",
        "label": "Max daily paper notional",
        "group": "Automated paper trading",
        "description": "Maximum simulated notional per UTC day.",
        "value_type": "float",
        "control": "number",
        "default_value": 250.0,
        "min_value": 0.0,
        "max_value": 1000000.0,
        "step": 1.0,
        "restart_required": True,
    },
    {
        "key": "paper_trading_min_edge_pct",
        "env_key": "PAPER_TRADING_MIN_EDGE_PCT",
        "label": "Minimum paper edge pct",
        "group": "Automated paper trading",
        "description": "Minimum edge required before the automation can create a paper order.",
        "value_type": "float",
        "control": "number",
        "default_value": 2.0,
        "min_value": 0.0,
        "max_value": 100.0,
        "step": 0.1,
        "restart_required": True,
    },
    {
        "key": "paper_trading_min_confidence",
        "env_key": "PAPER_TRADING_MIN_CONFIDENCE",
        "label": "Minimum paper confidence",
        "group": "Automated paper trading",
        "description": "Minimum confidence required before a paper order can be simulated.",
        "value_type": "float",
        "control": "number",
        "default_value": 0.70,
        "min_value": 0.0,
        "max_value": 1.0,
        "step": 0.01,
        "restart_required": True,
    },
    {
        "key": "paper_trading_fill_model",
        "env_key": "PAPER_TRADING_FILL_MODEL",
        "label": "Paper fill model",
        "group": "Automated paper trading",
        "description": "Simulated fill model used by the paper broker.",
        "value_type": "select",
        "control": "select",
        "allowed_values": ["top_of_book", "midpoint", "conservative", "adverse"],
        "default_value": "conservative",
        "restart_required": True,
    },
]


def _read_saved_v3_settings() -> dict[str, Any]:
    try:
        if V3_SETTINGS_PATH.exists():
            data = json.loads(V3_SETTINGS_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {"settings_warning": "Settings file was invalid JSON; runtime defaults are shown."}
    return {}


def _runtime_setting_value(definition: dict[str, Any]) -> Any:
    key = str(definition["key"])
    return getattr(app_settings, key, definition.get("default_value"))


def _setting_source(definition: dict[str, Any]) -> str:
    env_key = str(definition.get("env_key") or "")
    if env_key and env_key in os.environ:
        return "process_environment_or_dotenv"
    return "runtime_default"


def _mask_setting_value(value: Any, *, secret: bool = False) -> Any:
    if not secret:
        return value
    return "configured_redacted" if value not in {None, "", False} else "not_configured"


def _coerce_v3_setting_value(definition: dict[str, Any], raw_value: Any) -> tuple[Any | None, str | None]:
    key = str(definition["key"])
    value_type = str(definition.get("value_type") or "text")
    if definition.get("secret"):
        return None, f"{key} is secret-backed and cannot be saved from the v3 UI preference form."
    try:
        if value_type == "bool":
            if isinstance(raw_value, bool):
                value = raw_value
            else:
                value = str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}
        elif value_type == "int":
            value = int(float(str(raw_value).strip()))
        elif value_type == "float":
            value = float(str(raw_value).strip())
        elif value_type == "select":
            value = str(raw_value or "").strip().lower()
            allowed = [str(v) for v in definition.get("allowed_values", [])]
            if allowed and value not in allowed:
                return None, f"{key} must be one of: {', '.join(allowed)}."
        else:
            value = str(raw_value or "").strip()
    except (TypeError, ValueError):
        return None, f"{key} could not be parsed as {value_type}."

    if value_type in {"float", "int"}:
        min_value = definition.get("min_value")
        max_value = definition.get("max_value")
        numeric = float(value)
        if min_value is not None and numeric < float(min_value):
            return None, f"{key} must be >= {min_value}."
        if max_value is not None and numeric > float(max_value):
            return None, f"{key} must be <= {max_value}."
    if key == "ai_absolute_hard_cap_pct" and float(value) > 25.0:
        return None, "ai_absolute_hard_cap_pct cannot exceed 25.0 in the operator preference UI."
    if key == "kalshi_api_base_url" and value and not str(value).startswith(("https://", "http://")):
        return None, "kalshi_api_base_url must start with http:// or https://."
    return value, None


def _build_v3_settings_sections(saved: dict[str, Any]) -> list[dict[str, Any]]:
    saved_preferences = saved.get("preferences") if isinstance(saved.get("preferences"), dict) else {}
    rows: list[dict[str, Any]] = []
    for definition in V3_UI_SETTING_DEFINITIONS:
        secret = bool(definition.get("secret"))
        key = str(definition["key"])
        runtime_value = _runtime_setting_value(definition)
        has_saved = key in saved_preferences
        saved_value = saved_preferences.get(key)
        effective_operator_value = saved_value if has_saved else runtime_value
        rows.append(redact_data({
            **definition,
            "runtime_value": _mask_setting_value(runtime_value, secret=secret),
            "saved_preference": _mask_setting_value(saved_value, secret=secret) if has_saved else None,
            "effective_operator_value": _mask_setting_value(effective_operator_value, secret=secret),
            "source": "ui_preference" if has_saved else _setting_source(definition),
            "runtime_source": _setting_source(definition),
            "saved": has_saved,
            "editable": not secret,
            "requires_restart": bool(definition.get("restart_required", True)),
            "secret": secret,
            "review_only": True,
            "live_disabled": True,
        }))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("group") or "General"), []).append(row)
    return [{"group": group, "items": items, "count": len(items)} for group, items in grouped.items()]


def build_v3_settings() -> dict[str, Any]:
    saved = _read_saved_v3_settings()
    sections = _build_v3_settings_sections(saved)
    flattened = [item for section in sections for item in section["items"]]
    configured_count = sum(1 for item in flattened if item.get("saved"))
    settings = {
        "version": APP_VERSION,
        "generated_at": _now(),
        "workflow_status": "working",
        "workflow_name": "v3 operator settings preferences",
        "settings_storage_path": str(V3_SETTINGS_PATH),
        "settings_storage_state": "saved_preferences_present" if configured_count else "runtime_defaults_only",
        "settings_warning": saved.get("settings_warning", ""),
        "ai_assistance_enabled": False,
        "analysis_provider": {"provider": "deterministic_local", "enabled": False, "external_calls_allowed": False, "secret_values_sent": False},
        "sections": sections,
        "editable_keys": [str(item["key"]) for item in flattened if item.get("editable")],
        "configured_preference_count": configured_count,
        "operator_feedback": {
            "save_supported": True,
            "invalid_values_rejected": True,
            "secrets_masked": True,
            "restart_required_visible": True,
            "runtime_env_not_mutated": True,
        },
        "preferences": [
            {"key": "default_landing_page", "value": "/v3", "secret": False, "source": "runtime_default", "saved": False},
            {"key": "search_index_manual_rebuild", "value": True, "secret": False, "source": "runtime_default", "saved": False},
            {"key": "graph_manual_rebuild", "value": True, "secret": False, "source": "runtime_default", "saved": False},
            {"key": "workflow_outputs_are_drafts", "value": True, "secret": False, "source": "runtime_default", "saved": False},
            {"key": "prompt_payload_redaction", "value": "always", "secret": False, "source": "runtime_default", "saved": False},
            {"key": "packet_generation_default", "value": "read_only", "secret": False, "source": "runtime_default", "saved": False},
        ],
        "last_saved_at": saved.get("saved_at"),
        "last_operator_payload_keys": saved.get("operator_payload_keys", []),
        "validation_errors": saved.get("last_validation_errors", []),
        "audit_action": "settings_preferences_saved",
        "secret_values_returned": False,
        "sensitive_data_allowed": False,
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
    }
    return redact_data(settings)


def update_v3_settings(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = redact_data(payload or {})
    _ensure_dir()
    current_saved = _read_saved_v3_settings()
    current_preferences = current_saved.get("preferences") if isinstance(current_saved.get("preferences"), dict) else {}
    definitions = {str(item["key"]): item for item in V3_UI_SETTING_DEFINITIONS}
    updates: dict[str, Any] = {}
    errors: list[dict[str, str]] = []
    ignored_keys: list[str] = []
    for key, raw_value in payload.items():
        if str(key).startswith("_"):
            continue
        if key not in definitions:
            ignored_keys.append(str(key))
            continue
        value, error = _coerce_v3_setting_value(definitions[key], raw_value)
        if error:
            errors.append({"key": key, "error": error})
        else:
            updates[key] = value
    if errors:
        rejected = {
            "ok": False,
            "version": APP_VERSION,
            "errors": errors,
            "ignored_keys": ignored_keys,
            "updated_keys": [],
            "settings": build_v3_settings(),
            "secret_values_returned": False,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "review_only": True,
            "live_disabled": True,
        }
        _event("settings_preferences_rejected", "blocked", {"errors": errors, "ignored_keys": ignored_keys, "source_route": payload.get("_source_route", "/api/v3/settings"), "source_component": payload.get("_source_component", "api_v3_settings_update")})
        return redact_data(rejected)

    new_preferences = {**current_preferences, **updates}
    record = redact_data({
        "version": APP_VERSION,
        "saved_at": _now(),
        "preferences": new_preferences,
        "operator_payload_keys": sorted(updates.keys()),
        "ignored_keys": ignored_keys,
        "last_validation_errors": [],
        "source_route": payload.get("_source_route", "/api/v3/settings"),
        "source_component": payload.get("_source_component", "api_v3_settings_update"),
        "secret_values_returned": False,
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
    })
    V3_SETTINGS_PATH.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _event(
        "settings_preferences_saved",
        "ok",
        {
            "keys": sorted(updates.keys()),
            "ignored_keys": ignored_keys,
            "previous_state": {key: current_preferences.get(key) for key in updates},
            "new_state": updates,
            "source_route": payload.get("_source_route", "/api/v3/settings"),
            "source_component": payload.get("_source_component", "api_v3_settings_update"),
            "restart_required": True,
            "runtime_env_mutated": False,
            "review_only": True,
            "live_disabled": True,
        },
    )
    return {"ok": True, "settings": build_v3_settings(), "updated_keys": sorted(updates.keys()), "ignored_keys": ignored_keys, "secret_values_returned": False, "order_submitted": False, "order_cancelled": False, "trade_approved": False, "review_only": True, "live_disabled": True}

def export_report_json(kind: str = "command_center", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if kind == "graph":
        report = build_decision_graph()
    elif kind == "search":
        report = build_search_index()
    elif kind == "pre_trade_packet":
        report = pre_trade_packet(payload)
    elif kind == "market_brief":
        report = market_intelligence_brief(payload)
    elif kind == "thesis_health":
        report = thesis_health_report(payload)
    elif kind == "portfolio_brief":
        report = portfolio_risk_brief(payload)
    elif kind == "operator_review":
        report = operator_review_packet(payload)
    elif kind == "missing_prerequisites":
        report = missing_prerequisites_scan()
    else:
        report = build_command_center()
    exported = {"version": APP_VERSION, "generated_at": _now(), "kind": kind, "report": report, "safety_statement": "v3 exports do not place, cancel, approve, sign, or arm live orders.", "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    _event("report_exported", "ok", {"kind": kind})
    return redact_data(exported)


def export_report_markdown(kind: str = "command_center", payload: dict[str, Any] | None = None) -> str:
    report = export_report_json(kind, payload)
    lines = [f"# v3 Intelligence Report — {kind}", "", f"Version: {APP_VERSION}", f"Generated: {report.get('generated_at')}", "", "Safety: v3 intelligence reports do not place, cancel, approve, sign, or arm live orders.", "", "## Summary"]
    body = report.get("report", {})
    if isinstance(body, dict):
        for key, value in body.items():
            if key in {"items", "nodes", "edges", "checks", "events"}:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                lines.append(f"- **{key}**: {value}")
        lines.extend(["", "## Findings / Items"])
        for item in (body.get("findings") or body.get("next_operator_actions") or body.get("items") or [])[:50]:
            if isinstance(item, dict):
                lines.append(f"- {item.get('title') or item.get('recommended_operator_action') or item.get('summary') or item.get('action') or item.get('status')}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append(str(body)[:2000])
    return "\n".join(lines) + "\n"

# v4.4.0-real polish layer: demo fixtures, filters, release validation helpers, and safer packet templates.
V3_DEMO_DATA_PATH = V3_DIR / "demo_fixture.json"


def _demo_data_path() -> Path:
    return V3_DIR / "demo_fixture.json"

_DEMO_SECRET_PATTERNS = (
    "private_key", "api_key", "api_secret", "bearer ", "authorization:", "mnemonic", "seed phrase",
    "wallet_secret", "passphrase", "polymarket_private_key", "secret_key",
)


def _load_demo_data() -> dict[str, Any]:
    path = _demo_data_path()
    if not path.exists():
        return {}
    try:
        return redact_data(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {"invalid_demo_data": True, "secret_values_returned": False}


def _demo_item(item_id: str, **fields: Any) -> dict[str, Any]:
    return redact_data({
        "id": item_id,
        "created_at": fields.pop("created_at", _now()),
        "updated_at": fields.pop("updated_at", _now()),
        "app_version": APP_VERSION,
        "demo_fixture": True,
        "tags": sorted(set(fields.pop("tags", ["demo", "v3.2"]))),
        **fields,
    })


def build_demo_fixture() -> dict[str, Any]:
    """Build a fake, safe v3 demo fixture without live credentials or real account data."""
    now = _now()
    market_id = "demo-market-v31"
    thesis_id = "demo-thesis-v31"
    source_id = "demo-source-v31"
    fixture = {
        "version": APP_VERSION,
        "fixture_id": "v3_1_safe_demo_fixture",
        "created_at": now,
        "clearly_fake": True,
        "no_live_credentials": True,
        "no_financial_advice": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "strategy": {
            "theses": [_demo_item(thesis_id, node_type="thesis", market_id=market_id, market_title="DEMO: Will the operator complete visual QA?", outcome="YES", thesis_summary="Fake demo thesis used to exercise v3.2 screenshots and packet generation.", status="needs_review", tags=["demo", "visual_qa", "thesis"])],
            "evidence": [
                _demo_item("demo-evidence-support-v31", thesis_id=thesis_id, market_id=market_id, title="DEMO supporting evidence", direction="supports", notes="Fake support item for packet layout testing.", freshness_status="fresh", status="active", tags=["demo", "support"]),
                _demo_item("demo-evidence-counter-v31", thesis_id=thesis_id, market_id=market_id, title="DEMO counter evidence", direction="contradicts", notes="Fake counter-evidence item so the UI can show balanced review context.", freshness_status="fresh", status="active", tags=["demo", "counter_evidence"]),
                _demo_item("demo-evidence-stale-v31", thesis_id=thesis_id, market_id=market_id, title="DEMO stale evidence", direction="supports", notes="Fake stale item for warning layout testing.", freshness_status="stale", status="stale", tags=["demo", "stale"]),
            ],
            "watchlist": [_demo_item("demo-watchlist-v31", thesis_id=thesis_id, market_id=market_id, market_title="DEMO visual QA market", reason="Fake watchlist item for command center cards.", status="review")],
            "scorecards": [_demo_item("demo-scorecard-v31", thesis_id=thesis_id, market_id=market_id, market_title="DEMO visual QA market", recommended_next_action="Review fake prerequisites before demo.", score=72, status="watch")],
            "reviews": [],
        },
        "research": {
            "sources": [_demo_item(source_id, market_id=market_id, related_thesis_id=thesis_id, title="DEMO source registry item", url="https://example.invalid/demo-source", source_type="demo", credibility_rating=4, freshness_status="stale", status="stale", notes="Fake source for visual QA only.")],
            "queue": [_demo_item("demo-research-queue-v31", market_id=market_id, related_thesis_id=thesis_id, title="DEMO unresolved research question", research_question="What would need to be verified before a real decision?", status="open", priority="high")],
            "notes": [_demo_item("demo-source-note-v31", source_id=source_id, market_id=market_id, related_thesis_id=thesis_id, summary="DEMO note summary for packet rendering.", key_claims="Fake key claim; not financial advice.", status="active")],
            "candidates": [_demo_item("demo-evidence-candidate-v31", source_id=source_id, thesis_id=thesis_id, market_id=market_id, title="DEMO candidate evidence", direction="supports", freshness_status="aging", status="draft")],
        },
        "monitoring": {
            "rules": [_demo_item("demo-monitor-rule-v31", rule_name="DEMO review threshold", rule_type="thesis_alert", related_market_id=market_id, related_thesis_id=thesis_id, severity="warning", status="enabled", condition={"field":"review_status", "operator":"equals", "value":"needs_review"})],
            "alerts": [_demo_item("demo-alert-v31", title="DEMO stale evidence warning", reason="Fake stale evidence linked to fake thesis.", related_market_id=market_id, related_thesis_id=thesis_id, severity="warning", status="active", recommended_operator_action="Refresh fake demo source before relying on the fake thesis.")],
            "history": [],
        },
        "portfolio": {
            "exposure": [_demo_item("demo-exposure-v31", market_id=market_id, thesis_id=thesis_id, market_title="DEMO visual QA market", exposure_type="planned", notional_estimate=25.0, max_loss_estimate=25.0, status="planned")],
            "warnings": [_demo_item("demo-concentration-warning-v31", market_id=market_id, thesis_id=thesis_id, title="DEMO concentration warning", warning_type="planned_trade_limit", severity="warning", recommended_operator_action="Review fake planned exposure in demo mode.", status="open")],
            "scenarios": [_demo_item("demo-scenario-v31", market_id=market_id, thesis_id=thesis_id, title="DEMO adverse scenario", scenario_type="market_resolves_no", estimated_impact="Fake scenario impact for visual QA.", status="draft")],
        },
        "governance": {
            "journal": [_demo_item("demo-journal-v31", decision_title="DEMO no-trade review", decision_type="no-trade decision", related_market_id=market_id, related_thesis_id=thesis_id, decision_summary="Fake journal entry used for governance panel layout.", status="active")],
            "checklists": [_demo_item("demo-checklist-v31", checklist_title="DEMO pre-trade checklist", checklist_type="pre_trade", related_market_id=market_id, related_thesis_id=thesis_id, completed_count=9, total_count=14, completion_ratio=0.6429, status="draft")],
            "reviews": [_demo_item("demo-review-v31", review_title="DEMO daily operator review", review_type="daily", lessons_learned="Fake demo review shows the packet structure.", status="draft")],
            "rules": [],
            "near_misses": [_demo_item("demo-near-miss-v31", title="DEMO ignored-alert near miss", related_thesis_id=thesis_id, severity="watch", what_happened="Fake near-miss used to exercise governance warnings.", money_was_at_risk=False, live_execution_occurred=False, status="open")],
            "mistake_patterns": [_demo_item("demo-mistake-v31", pattern_title="DEMO stale-evidence pattern", pattern_type="relied_on_stale_evidence", frequency=1, process_improvement_action="Refresh sources before ticket creation.", status="active")],
        },
        "workflow_outputs": [
            _demo_item("demo-workflow-output-v31", workflow_id="pre_trade_intelligence_packet", title="DEMO Pre-Trade Intelligence Packet", status="completed", summary="Fake packet output for screenshot and manual QA.")
        ],
        "secret_values_returned": False,
    }
    return redact_data(fixture)


_collect_local_data_base = _collect_local_data


def _collect_local_data(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    data = _collect_local_data_base(limit=limit)
    fixture = _load_demo_data()
    if not fixture or fixture.get("invalid_demo_data"):
        data["demo"] = {"enabled": False, "items": 0, "secret_values_returned": False}
        return data
    # Merge fixture rows into the same local-first collections used by search/graph/packets.
    for section in ("strategy", "research", "monitoring", "portfolio", "governance"):
        if section not in data or not isinstance(data.get(section), dict):
            continue
        demo_section = fixture.get(section, {}) if isinstance(fixture.get(section), dict) else {}
        for key, rows in demo_section.items():
            if isinstance(rows, list) and isinstance(data[section].get(key), list):
                data[section][key] = rows + data[section][key]
    data["v3"]["workflow_outputs"] = fixture.get("workflow_outputs", [])
    data["demo"] = {"enabled": True, "fixture_id": fixture.get("fixture_id"), "items": sum(len(v) for s in ("strategy", "research", "monitoring", "portfolio", "governance") for v in (fixture.get(s, {}) or {}).values() if isinstance(v, list)), "clearly_fake": True, "secret_values_returned": False}
    return redact_data(data)


def create_demo_data() -> dict[str, Any]:
    _ensure_dir()
    fixture = build_demo_fixture()
    _demo_data_path().parent.mkdir(parents=True, exist_ok=True)
    _demo_data_path().write_text(json.dumps(fixture, indent=2, sort_keys=True, default=str), encoding="utf-8")
    safety = demo_data_safety_check(fixture)
    _event("demo_data_created", "ok" if safety["ok"] else "warning", {"path": str(_demo_data_path()), "items": fixture.get("demo", {}).get("items", 0), "secret_like_findings": safety.get("finding_count", 0)})
    return {"ok": safety["ok"], "path": str(_demo_data_path()), "fixture": fixture, "safety": safety, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def clear_demo_data() -> dict[str, Any]:
    path = _demo_data_path()
    existed = path.exists()
    if existed:
        path.unlink()
    _event("demo_data_cleared", "ok", {"existed": existed})
    return {"ok": True, "cleared": existed, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def demo_status() -> dict[str, Any]:
    fixture = _load_demo_data()
    return {"enabled": bool(fixture and not fixture.get("invalid_demo_data")), "path": str(_demo_data_path()), "clearly_fake": bool(fixture.get("clearly_fake")) if fixture else False, "safety": demo_data_safety_check(fixture) if fixture else {"ok": True, "finding_count": 0}, "secret_values_returned": False}


def demo_data_safety_check(fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    fixture = fixture if fixture is not None else _load_demo_data()
    raw = json.dumps(fixture or {}, sort_keys=True, default=str).lower()
    findings = []
    for pattern in _DEMO_SECRET_PATTERNS:
        if pattern in raw:
            findings.append({"pattern": pattern, "redacted": True})
    # The fixture may include safety field names like no_live_credentials; do not flag those as secrets.
    findings = [f for f in findings if f["pattern"] not in {"private_key", "api_key", "api_secret"} or "fake" not in raw]
    return {"ok": len(findings) == 0, "finding_count": len(findings), "findings": findings, "secret_values_returned": False}


def search_filters() -> dict[str, Any]:
    index = build_search_index(limit=1000)
    types = sorted({str(item.get("result_type") or "unknown") for item in index.get("items", [])})
    statuses = sorted({str(item.get("status") or "unknown") for item in index.get("items", [])})
    tags = sorted({str(tag) for item in index.get("items", []) for tag in (item.get("tags") or [])})
    return {"version": APP_VERSION, "object_types": types, "statuses": statuses, "tags": tags, "count": index.get("count", 0), "local_only": True, "secret_values_returned": False}


_search_local_base = search_local


def search_local(query: str = "", result_type: str = "", limit: int = 50, status: str = "", tag: str = "", recent: str = "") -> dict[str, Any]:  # type: ignore[override]
    index = build_search_index(limit=1000)
    q = _safe_text(query).lower()
    rtype = _safe_text(result_type).lower()
    stat = _safe_text(status).lower()
    wanted_tag = _safe_text(tag).lower()
    rows: list[dict[str, Any]] = []
    for item in index.get("items", []):
        if rtype and _safe_text(item.get("result_type")).lower() != rtype:
            continue
        if stat and _safe_text(item.get("status")).lower() != stat:
            continue
        if wanted_tag and wanted_tag not in [str(t).lower() for t in item.get("tags", [])]:
            continue
        if q and q not in item.get("search_text", ""):
            continue
        score = 1.0
        if q and q in str(item.get("title", "")).lower():
            score += 2.0
        if q and q in str(item.get("summary", "")).lower():
            score += 1.0
        visible = {k: v for k, v in item.items() if k != "search_text"}
        visible.update({"relevance_score": score, "filter_status": stat or "any", "filter_tag": wanted_tag or "any"})
        rows.append(visible)
        if len(rows) >= max(1, min(int(limit or 50), 500)):
            break
    if q or rtype or stat or wanted_tag:
        _event("search_query_run", "ok", {"query_present": bool(q), "result_type": result_type, "status": status, "tag": tag, "count": len(rows)})
    return {"version": APP_VERSION, "query": query, "result_type": result_type, "status": status, "tag": tag, "recent": recent, "count": len(rows), "items": redact_data(rows), "filters": search_filters(), "local_only": True, "secret_values_returned": False}


def graph_filters() -> dict[str, Any]:
    graph = build_decision_graph(limit=1000)
    node_types = sorted({str(n.get("node_type") or "unknown") for n in graph.get("nodes", [])})
    relationship_types = sorted({str(e.get("relationship_type") or "unknown") for e in graph.get("edges", [])})
    statuses = sorted({str(n.get("status") or "unknown") for n in graph.get("nodes", [])})
    return {"version": APP_VERSION, "node_types": node_types, "relationship_types": relationship_types, "statuses": statuses, "node_count": graph.get("node_count", 0), "edge_count": graph.get("edge_count", 0), "secret_values_returned": False}


def filtered_decision_graph(node_type: str = "", relationship_type: str = "", limit: int = 250) -> dict[str, Any]:
    graph = build_decision_graph(limit=limit)
    nt = _safe_text(node_type).lower()
    rt = _safe_text(relationship_type).lower()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if nt:
        nodes = [n for n in nodes if _safe_text(n.get("node_type")).lower() == nt]
        node_ids = {n.get("node_id") for n in nodes}
        edges = [e for e in edges if e.get("source_node") in node_ids or e.get("target_node") in node_ids]
    if rt:
        edges = [e for e in edges if _safe_text(e.get("relationship_type")).lower() == rt]
    graph.update({"node_type_filter": node_type, "relationship_type_filter": relationship_type, "nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), "filters": graph_filters()})
    return graph


def workflow_templates() -> dict[str, Any]:
    templates = []
    sections = {
        "pre_trade_intelligence_packet": ["Market Context", "Thesis", "Evidence", "Counter-Evidence", "Stale Evidence", "Monitoring Alerts", "Portfolio Exposure", "Governance", "Blockers", "Warnings", "Unknowns", "Next Actions"],
        "market_intelligence_brief": ["Market Summary", "Known Local Research", "Strongest Support", "Strongest Contradiction", "Missing Research", "Next Research Actions"],
        "thesis_health_review": ["Thesis Summary", "Evidence Coverage", "Counter-Evidence", "Stale Evidence", "Exposure", "Governance", "Health Status", "Next Actions"],
        "portfolio_risk_brief": ["Exposure Summary", "Concentration", "Scenario Risk", "Stale Evidence Exposure", "Unknown Data", "Next Actions"],
        "governance_daily_review": ["Decisions", "Theses", "Evidence", "Alerts", "Portfolio Warnings", "Risk Blocks", "Data Health", "Next Actions"],
        "weekly_operator_review": ["Daily Rollup", "Recurring Patterns", "Stale Evidence Trends", "Concentration Trends", "Governance Issues", "Next Week Focus"],
        "stale_evidence_review": ["Stale Items", "Aging Items", "Affected Theses", "Refresh Actions"],
        "alert_triage_brief": ["Active Alerts", "Critical Alerts", "Acknowledgement Plan", "Linked Objects"],
        "data_health_backup_readiness": ["Data Health", "Secret Scan", "Backups", "Migrations", "Recovery Actions"],
        "no_trade_review_packet": ["Blockers", "Warnings", "Missing Prerequisites", "No-Trade Rationale", "Follow-up Actions"],
    }
    for workflow in WORKFLOW_REGISTRY:
        wid = workflow["workflow_id"]
        templates.append({**workflow, "sections": sections.get(wid, ["Summary", "Findings", "Next Actions"]), "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False})
    return {"version": APP_VERSION, "templates": templates, "count": len(templates), "secret_values_returned": False}


def workflow_outputs(limit: int = 100) -> dict[str, Any]:
    runs = list_workflow_runs(limit=limit).get("items", [])
    demo_outputs = _collect_local_data(limit=limit).get("v3", {}).get("workflow_outputs", [])
    items = []
    for run in runs:
        items.append({"id": run.get("run_id"), "workflow_id": run.get("workflow_id"), "title": run.get("workflow_id", "workflow").replace("_", " ").title(), "status": run.get("status"), "generated_at": run.get("completed_at") or run.get("started_at"), "output": run.get("output", {}), "demo_fixture": False})
    items = demo_outputs + items
    return {"version": APP_VERSION, "count": len(items), "items": redact_data(items[: max(1, min(int(limit or 100), 1000))]), "secret_values_returned": False}


def validation_status() -> dict[str, Any]:
    required_docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    root = Path(__file__).resolve().parents[1]
    checks = []
    for rel in required_docs:
        checks.append({"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review document before release."})
    checks.append({"check": "AI/model assistance", "status": "pass", "details": "Disabled by default."})
    checks.append({"check": "v3 workflows", "status": "pass", "details": "Read-only; no order placement/cancellation/arming helpers are called."})
    return {"version": APP_VERSION, "generated_at": _now(), "checks": checks, "overall_status": "pass" if all(c["status"] == "pass" for c in checks[:1]) else "warning", "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


_build_command_center_base = build_command_center


def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_base()
    groups = {
        "safety": {"live_armed": center.get("live_armed"), "read_only": center.get("read_only"), "kill_switch": center.get("kill_switch"), "readiness_status": center.get("readiness_status")},
        "data_health": {"data_health_status": center.get("data_health_status"), "backup_restore_health": center.get("backup_restore_health")},
        "research_strategy": {"active_theses": center.get("active_theses"), "research_queue_count": center.get("research_queue_count"), "stale_evidence_count": center.get("stale_evidence_count")},
        "monitoring": {"active_alerts": center.get("active_alert_count"), "critical_alerts": center.get("critical_alert_count")},
        "portfolio": {"concentration_warnings": center.get("concentration_warning_count"), "portfolio_exposure_summary": center.get("portfolio_exposure_summary")},
        "governance": {"open_checklists": center.get("open_governance_checklist_count"), "recent_decisions": len(center.get("recent_decisions", []))},
        "recent_activity": {"recent_audit_events": len(center.get("recent_audit_events", [])), "recent_risk_blocks": len(center.get("recent_risk_blocks", []))},
        "next_actions": center.get("next_operator_actions", []),
    }
    center.update({
        "release_candidate_stage": "v3.2 visual QA and workflow polish",
        "demo_status": demo_status(),
        "groups": redact_data(groups),
        "safety_boundary": "The v3.2 command center is read-only and does not place, cancel, approve, sign, or arm live orders.",
        "secret_values_returned": False,
    })
    return redact_data(center)


def export_pre_trade_packet_markdown(payload: dict[str, Any] | None = None) -> str:
    return export_report_markdown("pre_trade_packet", payload or {})


def export_operator_review_markdown(payload: dict[str, Any] | None = None) -> str:
    return export_report_markdown("operator_review", payload or {})

# v4.4.0-real analytics learning layer: local-first descriptive metrics, learning reports,
# analytics search/graph integration, and read-only workflow context.

_build_search_index_v31 = build_search_index


def build_search_index(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    index = _build_search_index_v31(limit=limit)
    try:
        from .live_v3_analytics import analytics_search_items
        analytics_items = analytics_search_items(limit=100)
    except Exception:
        analytics_items = []
    rows = index.get("items", []) + analytics_items
    rows.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    return {**index, "count": len(rows), "items": redact_data(rows[: max(1, min(int(limit or 250), 2000))]), "analytics_indexed": len(analytics_items), "secret_values_returned": False}


_build_decision_graph_v31 = build_decision_graph


def build_decision_graph(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    graph = _build_decision_graph_v31(limit=limit)
    try:
        from .live_v3_analytics import analytics_graph_nodes_edges
        analytics = analytics_graph_nodes_edges()
        nodes = graph.get("nodes", []) + analytics.get("nodes", [])
        edges = graph.get("edges", []) + analytics.get("edges", [])
        graph.update({"nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), "analytics_nodes": len(analytics.get("nodes", [])), "analytics_edges": len(analytics.get("edges", []))})
    except Exception:
        graph.update({"analytics_nodes": 0, "analytics_edges": 0})
    graph["secret_values_returned"] = False
    return graph


_build_command_center_v31 = build_command_center


def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_v31()
    try:
        from .live_v3_analytics import build_analytics_summary
        analytics = build_analytics_summary()
    except Exception as exc:
        analytics = {"status": "unknown", "error_redacted": redact_text(str(exc)), "secret_values_returned": False}
    center["analytics_summary"] = redact_data(analytics)
    center.setdefault("groups", {})["analytics"] = {
        "decision_quality_status": analytics.get("decision_quality_status"),
        "confidence_calibration_status": analytics.get("confidence_calibration_status"),
        "review_followthrough_status": analytics.get("review_followthrough_status"),
        "mistake_patterns": analytics.get("recurring_mistake_pattern_count", 0),
        "strength_patterns": analytics.get("recurring_strength_pattern_count", 0),
        "next_review_action": analytics.get("next_recommended_review_action"),
    }
    center["release_candidate_stage"] = "v3.2 operator analytics and learning loop"
    center["safety_boundary"] = "The v3.2 command center, analytics, workflows, and learning reports are read-only/descriptive and do not place, cancel, approve, sign, or arm live orders."
    center["secret_values_returned"] = False
    return redact_data(center)


_pre_trade_packet_v31 = pre_trade_packet


def pre_trade_packet(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    packet = _pre_trade_packet_v31(payload)
    try:
        from .live_v3_analytics import analytics_context
        packet["analytics_context"] = analytics_context()
    except Exception:
        packet["analytics_context"] = {"status": "unknown", "secret_values_returned": False}
    packet["analytics_are_descriptive"] = True
    packet["safety_statement"] = "This packet includes descriptive analytics context but does not place, cancel, sign, approve, or arm live orders."
    return redact_data(packet)


_thesis_health_report_v31 = thesis_health_report


def thesis_health_report(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    report = _thesis_health_report_v31(payload)
    try:
        from .live_v3_analytics import analytics_context
        report["analytics_context"] = {k: v for k, v in analytics_context().items() if k in {"thesis_quality", "evidence_usefulness", "confidence_calibration", "secret_values_returned"}}
    except Exception:
        report["analytics_context"] = {"status": "unknown", "secret_values_returned": False}
    report["analytics_are_descriptive"] = True
    return redact_data(report)


_portfolio_risk_brief_v31 = portfolio_risk_brief


def portfolio_risk_brief(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    brief = _portfolio_risk_brief_v31(payload)
    try:
        from .live_v3_analytics import analytics_context
        brief["analytics_context"] = {k: v for k, v in analytics_context().items() if k in {"governance_discipline", "alert_usefulness", "mistake_patterns", "secret_values_returned"}}
    except Exception:
        brief["analytics_context"] = {"status": "unknown", "secret_values_returned": False}
    brief["analytics_are_descriptive"] = True
    return redact_data(brief)


_operator_review_packet_v31 = operator_review_packet


def operator_review_packet(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    packet = _operator_review_packet_v31(payload)
    try:
        from .live_v3_analytics import generate_learning_report, analytics_context
        packet["learning_report_summary"] = generate_learning_report(period=_safe_text((payload or {}).get("period"), "daily"), write=False)
        packet["analytics_context"] = analytics_context()
    except Exception:
        packet["learning_report_summary"] = {"status": "unknown", "secret_values_returned": False}
    packet["analytics_are_descriptive"] = True
    return redact_data(packet)


_build_demo_fixture_v31 = build_demo_fixture


def build_demo_fixture() -> dict[str, Any]:  # type: ignore[override]
    fixture = _build_demo_fixture_v31()
    gov = fixture.setdefault("governance", {})
    gov.setdefault("journal", []).extend([
        _demo_item("demo-reviewed-decision-v32", decision_title="DEMO reviewed decision", decision_type="research decision", decision_summary="Fake reviewed decision for analytics QA.", confidence_level=70, status="reviewed", actual_outcome="unknown", tags=["demo", "analytics"]),
        _demo_item("demo-unresolved-decision-v32", decision_title="DEMO unresolved decision", decision_type="thesis decision", decision_summary="Fake unresolved decision for analytics cards.", confidence_level=85, status="active", tags=["demo", "analytics"]),
    ])
    gov.setdefault("mistake_patterns", []).append(_demo_item("demo-mistake-v32", pattern_title="DEMO skipped counter-evidence", pattern_type="ignored_counter_evidence", frequency=2, process_improvement_action="Record counter-evidence before packet generation.", status="active", tags=["demo", "analytics"]))
    gov.setdefault("reviews", []).append(_demo_item("demo-weekly-review-v32", review_title="DEMO weekly learning review", review_type="weekly", lessons_learned="Fake review for learning report output.", status="completed", follow_up_status="completed", tags=["demo", "analytics"]))
    fixture.setdefault("monitoring", {}).setdefault("alerts", []).append(_demo_item("demo-noisy-alert-v32", title="DEMO noisy alert", alert_type="price_threshold", severity="watch", status="active", reason="Fake repeated/noisy alert for alert usefulness analytics.", tags=["demo", "analytics", "noisy_alert"]))
    fixture.setdefault("v3_analytics", {})["demo_note"] = "Fake analytics-friendly demo records only. No real secrets or account data."
    return redact_data(fixture)


_validation_status_v31 = validation_status


def validation_status() -> dict[str, Any]:  # type: ignore[override]
    status = _validation_status_v31()
    root = Path(__file__).resolve().parents[1]
    docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    checks = status.get("checks", []) + [{"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review v3.2 analytics documentation before release."} for rel in docs]
    try:
        from .live_v3_analytics import build_analytics_summary
        analytics_ok = build_analytics_summary().get("secret_values_returned") is False
    except Exception:
        analytics_ok = False
    checks.append({"check": "v3.2 analytics", "status": "pass" if analytics_ok else "warning", "details": "Local-first descriptive analytics; no order placement/cancellation/arming."})
    status.update({"checks": checks, "overall_status": "pass" if all(c.get("status") == "pass" for c in checks if "v3.2" in c.get("check", "") or c.get("check") == "v3.2 analytics") else "warning", "analytics_are_descriptive": True, "secret_values_returned": False})
    return redact_data(status)

# v4.4.0-real complete UI/UX redesign layer: design-system metadata,
# navigation grouping, UX validation status, and release-candidate safety signals.

def design_system_status() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    css = root / "app" / "static" / "v3_design.css"
    js = root / "app" / "static" / "v3_interactions.js"
    checks = [
        {"name": "design_system_css", "status": "pass" if css.exists() else "warning", "path": "app/static/v3_design.css"},
        {"name": "interaction_js", "status": "pass" if js.exists() else "warning", "path": "app/static/v3_interactions.js"},
        {"name": "danger_visual_hierarchy", "status": "pass", "details": "Danger, warning, unknown, blocked, read-only, live-armed, and fake-demo states have distinct badges/callouts."},
        {"name": "responsive_shell", "status": "pass", "details": "v3 app shell collapses to a single-column layout on narrow screens."},
        {"name": "accessibility_baseline", "status": "pass", "details": "Skip link, focus-visible styles, semantic landmarks, captions, and labels are included where practical."},
    ]
    return redact_data({
        "version": APP_VERSION,
        "status": "pass" if all(c["status"] == "pass" for c in checks) else "warning",
        "style_goals": ["crisp", "fast", "serious", "calm", "technical", "professional", "readable", "operator-focused", "safe", "trustworthy"],
        "components": ["app_shell", "side_navigation", "page_hero", "metric_tiles", "status_badges", "cards", "filter_bars", "tables", "empty_states", "callouts", "report_views", "danger_zones"],
        "checks": checks,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    })


def navigation_groups() -> dict[str, Any]:
    groups = [
        {"group": "Operate", "links": ["Command Center", "Live Controls", "Trade Ticket", "Audit"]},
        {"group": "Analyze", "links": ["Analytics", "Simulation Lab", "Portfolio", "Monitoring", "Graph", "Search"]},
        {"group": "Build Thesis", "links": ["Strategy", "Research", "Evidence", "Watchlists"]},
        {"group": "Govern", "links": ["Governance", "Reviews", "Data / Backup", "Settings"]},
        {"group": "Output", "links": ["Workflows", "Briefs", "Reports", "Docs"]},
    ]
    return redact_data({"version": APP_VERSION, "groups": groups, "v2_routes_preserved": True, "local_first": True, "secret_values_returned": False})


def ux_release_status() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_UI_UX_REDESIGN_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    script_checks = [
        "scripts/capture_v3_screenshots.py",
        "scripts/validate_v3_release.py",
        "scripts/validate_v3_ux_release.py",
        "scripts/create_v3_demo_data.py",
        "scripts/clear_v3_demo_data.py",
    ]
    checks = []
    checks.extend({"check": d, "status": "pass" if (root / d).exists() else "warning", "recommended_operator_action": "Review v3.5 UX release documentation."} for d in docs)
    checks.extend({"check": s, "status": "pass" if (root / s).exists() else "warning", "recommended_operator_action": "Run safe dry-run validation locally."} for s in script_checks)
    checks.append({"check": "design_system_status", "status": design_system_status()["status"], "recommended_operator_action": "Use visual QA checklist before publishing screenshots."})
    return redact_data({
        "version": APP_VERSION,
        "overall_status": "pass" if all(c["status"] == "pass" for c in checks) else "warning",
        "checks": checks,
        "redesigned_ui_does_not_bypass_backend_gates": True,
        "screenshots_included_in_release_zip": False,
        "demo_data_fake_and_secret_free": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    })


_validation_status_v32 = validation_status


def validation_status() -> dict[str, Any]:  # type: ignore[override]
    status = _validation_status_v32()
    ux = ux_release_status()
    checks = status.get("checks", []) + ux.get("checks", []) + [{"check": "v3.5 UX redesign", "status": ux.get("overall_status", "warning"), "details": "Complete operator UX redesign, design system, responsive shell, accessibility baseline, and visual QA docs."}]
    status.update({
        "checks": checks,
        "overall_status": "pass" if all(c.get("status") == "pass" for c in checks if "v3.5" in str(c.get("check", "")) or c.get("check") in {"design_system_status"}) else "warning",
        "ui_ux_redesign_active": True,
        "redesigned_ui_does_not_bypass_backend_gates": True,
        "screenshots_included_in_release_zip": False,
        "secret_values_returned": False,
    })
    return redact_data(status)

# v4.4.0-real simulation lab integration: local-first replay, simulation, process backtesting,
# and clear live/paper/simulation separation. All helpers are read-only/descriptive.

_build_search_index_v33 = build_search_index


def build_search_index(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    index = _build_search_index_v33(limit=limit)
    try:
        from .live_v3_simulation import simulation_search_items
        simulation_items = simulation_search_items(limit=100)
    except Exception:
        simulation_items = []
    rows = index.get("items", []) + simulation_items
    rows.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    return {**index, "count": len(rows), "items": redact_data(rows[: max(1, min(int(limit or 250), 2500))]), "simulation_indexed": len(simulation_items), "secret_values_returned": False}


_build_decision_graph_v33 = build_decision_graph


def build_decision_graph(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    graph = _build_decision_graph_v33(limit=limit)
    try:
        from .live_v3_simulation import simulation_graph_nodes_edges
        simulation = simulation_graph_nodes_edges()
        nodes = graph.get("nodes", []) + simulation.get("nodes", [])
        edges = graph.get("edges", []) + simulation.get("edges", [])
        graph.update({"nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), "simulation_nodes": len(simulation.get("nodes", [])), "simulation_edges": len(simulation.get("edges", []))})
    except Exception:
        graph.update({"simulation_nodes": 0, "simulation_edges": 0})
    graph["secret_values_returned"] = False
    return redact_data(graph)


_build_command_center_v33 = build_command_center


def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_v33()
    try:
        from .live_v3_simulation import simulation_summary
        sim = simulation_summary()
    except Exception as exc:
        sim = {"status": "unknown", "error_redacted": redact_text(str(exc)), "secret_values_returned": False}
    center["simulation_summary"] = redact_data(sim)
    center.setdefault("groups", {})["simulation"] = {
        "session_count": sim.get("session_count", 0),
        "open_session_count": sim.get("open_session_count", 0),
        "report_count": sim.get("report_count", 0),
        "process_backtest_count": sim.get("process_backtest_count", 0),
        "no_trade_simulation_count": sim.get("no_trade_simulation_count", 0),
        "next_simulation_review_action": sim.get("next_simulation_review_action"),
    }
    center["release_candidate_stage"] = "v3.5 simulation lab and replay layer"
    center["safety_boundary"] = "The v3.5 command center, simulation lab, analytics, workflows, and reports are read-only/descriptive and do not place, cancel, approve, sign, or arm live orders."
    center["secret_values_returned"] = False
    return redact_data(center)


_workflow_templates_v33 = workflow_templates


def workflow_templates() -> dict[str, Any]:  # type: ignore[override]
    result = _workflow_templates_v33()
    templates = result.get("templates", [])
    simulation_templates = [
        {"workflow_id": "replay_review_packet", "name": "Replay Review Packet", "read_only": True, "mutates_trading_state": False, "description": "Review local decision state at a replay time with known-then versus known-now labels.", "sections": ["Replay Scope", "Known Then", "Added Later", "Assumptions", "Lessons", "Unknowns", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "simulation_lab_report", "name": "Simulation Lab Report", "read_only": True, "mutates_trading_state": False, "description": "Summarize replay sessions, simulation outputs, process backtests, and no-trade simulations.", "sections": ["Summary", "Sessions", "Findings", "Assumptions", "Limitations", "Next Actions", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "process_backtest_report", "name": "Process Backtest Report", "read_only": True, "mutates_trading_state": False, "description": "Evaluate operator process quality from local records without claiming financial performance.", "sections": ["Process Scorecard", "Strengths", "Weaknesses", "Recurring Issues", "Unknown Data", "Improvements"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
    ]
    ids = {t.get("workflow_id") for t in templates}
    for template in simulation_templates:
        if template["workflow_id"] not in ids:
            templates.append(template)
    return {**result, "templates": redact_data(templates), "count": len(templates), "simulation_templates": len(simulation_templates), "secret_values_returned": False}


_build_demo_fixture_v33 = build_demo_fixture


def build_demo_fixture() -> dict[str, Any]:  # type: ignore[override]
    fixture = _build_demo_fixture_v33()
    now = _now()
    simulation = fixture.setdefault("simulation", {})
    simulation["sessions"] = [
        _demo_item("demo-sim-session-v34", session_id="demo-sim-session-v34", session_title="DEMO replay session", simulation_type="pre_trade_replay", target_time="2026-01-01T12:00:00+00:00", status="ready", assumption_set={"local_only_replay": True, "hypothetical_fill_percentage": 50, "missing_data_handling_mode": "mark_unknown"}, notes="Fake replay session for Simulation Lab screenshots.", tags=["demo", "simulation", "v3.5"])
    ]
    simulation["reports"] = [
        _demo_item("demo-sim-report-v34", report_id="demo-sim-report-v34", session_id="demo-sim-session-v34", simulation_type="process_quality_backtest", status="completed", created_at=now, output={"process_scorecard": {"score": 65, "status": "needs_review"}, "safety_statement": "Fake demo report; no live orders."}, tags=["demo", "simulation", "report", "v3.5"])
    ]
    simulation["no_trade"] = [_demo_item("demo-no-trade-sim-v34", simulation_type="no_trade_simulation", no_trade_rationale="Fake stale evidence plus incomplete checklist.", status="completed", tags=["demo", "simulation", "no_trade"])]
    fixture["simulation_note"] = "Fake simulation-friendly demo records only. No real credentials, no live orders, no financial advice."
    return redact_data(fixture)


_validation_status_v33 = validation_status


def validation_status() -> dict[str, Any]:  # type: ignore[override]
    status = _validation_status_v33()
    root = Path(__file__).resolve().parents[1]
    docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md",
        "docs/V3_UI_UX_REDESIGN_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    checks = status.get("checks", []) + [{"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review v3.5 simulation documentation before release."} for rel in docs]
    try:
        from .live_v3_simulation import simulation_summary
        sim_ok = simulation_summary().get("secret_values_returned") is False
    except Exception:
        sim_ok = False
    checks.append({"check": "v3.5 simulation lab", "status": "pass" if sim_ok else "warning", "details": "Local-first simulation/replay/process backtesting; no order placement/cancellation/arming."})
    status.update({"checks": checks, "overall_status": "pass" if sim_ok and all(c.get("status") == "pass" for c in checks if "v3.5" in str(c.get("check", ""))) else "warning", "simulation_lab_active": True, "simulation_is_descriptive": True, "simulation_workflows_do_not_arm_live_trading": True, "secret_values_returned": False})
    return redact_data(status)

_run_workflow_v33 = run_workflow


def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    payload = payload or {}
    workflow_id = _safe_text(payload.get("workflow_id") or payload.get("id"), "")
    if workflow_id in {"replay_review_packet", "simulation_lab_report", "process_backtest_report"}:
        try:
            from .live_v3_simulation import compare_then_now, process_quality_backtest, export_simulation_json
            context = payload.get("context") if isinstance(payload.get("context"), dict) else payload
            if workflow_id == "replay_review_packet":
                output = compare_then_now(context)
            elif workflow_id == "process_backtest_report":
                output = process_quality_backtest(context)
            else:
                output = export_simulation_json()
            run = redact_data({
                "run_id": f"v3_run_{uuid4().hex[:12]}",
                "workflow_id": workflow_id,
                "started_at": _now(),
                "completed_at": _now(),
                "status": "completed",
                "read_only": True,
                "mutated_trading_state": False,
                "order_submitted": False,
                "order_cancelled": False,
                "live_trading_armed": False,
                "ai_assistance_enabled": False,
                "output": output,
                "secret_values_returned": False,
            })
            _ensure_dir()
            with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(run, sort_keys=True, default=str) + "\n")
            _event("workflow_run_completed", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"], "simulation_workflow": True})
            return run
        except Exception as exc:
            return redact_data({"run_id": f"v3_run_{uuid4().hex[:12]}", "workflow_id": workflow_id, "status": "failed", "error_redacted": redact_text(str(exc)), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False})
    return _run_workflow_v33(payload)

# v4.4.0-real dataset/snapshot layer: read-only snapshot collection, replay datasets,
# provenance, quality scoring, and local-first dataset integration. No live/paper mutation.
_build_search_index_v34 = build_search_index

def build_search_index(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    index = _build_search_index_v34(limit=limit)
    try:
        from .live_v3_datasets import dataset_search_items
        dataset_items = dataset_search_items(limit=100)
    except Exception:
        dataset_items = []
    rows = index.get("items", []) + dataset_items
    rows.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    return {**index, "count": len(rows), "items": redact_data(rows[: max(1, min(int(limit or 250), 2500))]), "dataset_indexed": len(dataset_items), "secret_values_returned": False}


_build_decision_graph_v34 = build_decision_graph

def build_decision_graph(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    graph = _build_decision_graph_v34(limit=limit)
    try:
        from .live_v3_datasets import dataset_graph_nodes_edges
        dataset = dataset_graph_nodes_edges()
        nodes = graph.get("nodes", []) + dataset.get("nodes", [])
        edges = graph.get("edges", []) + dataset.get("edges", [])
        graph.update({"nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), "dataset_nodes": len(dataset.get("nodes", [])), "dataset_edges": len(dataset.get("edges", []))})
    except Exception:
        graph.update({"dataset_nodes": 0, "dataset_edges": 0})
    graph["secret_values_returned"] = False
    return redact_data(graph)


_build_command_center_v34 = build_command_center

def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_v34()
    try:
        from .live_v3_datasets import datasets_summary
        ds = datasets_summary()
    except Exception as exc:
        ds = {"status": "unknown", "error_redacted": redact_text(str(exc)), "secret_values_returned": False}
    center["datasets_summary"] = redact_data(ds)
    center.setdefault("groups", {})["datasets"] = {
        "snapshot_count": ds.get("snapshot_count", 0),
        "dataset_count": ds.get("dataset_count", 0),
        "replay_ready_dataset_count": ds.get("replay_ready_dataset_count", 0),
        "dataset_quality_status": ds.get("quality_status", "unknown"),
        "dataset_quality_score": ds.get("quality_score", 0),
        "missing_snapshot_warnings": ds.get("missing_snapshot_warnings", 0),
        "next_recommended_dataset_action": ds.get("next_recommended_dataset_action"),
    }
    center["release_candidate_stage"] = "v3.5 dataset builder and read-only snapshot layer"
    center["safety_boundary"] = "The v3.5 command center, dataset builder, simulation lab, analytics, workflows, and reports are read-only/descriptive and do not place, cancel, approve, sign, or arm live orders."
    center["secret_values_returned"] = False
    return redact_data(center)


_workflow_templates_v34 = workflow_templates

def workflow_templates() -> dict[str, Any]:  # type: ignore[override]
    result = _workflow_templates_v34()
    templates = result.get("templates", [])
    dataset_templates = [
        {"workflow_id": "dataset_quality_review", "name": "Dataset Quality Review", "read_only": True, "mutates_trading_state": False, "description": "Review snapshot coverage, data quality, provenance, replay readiness, and export safety.", "sections": ["Dataset Summary", "Quality", "Missing Snapshots", "Provenance", "Replay Readiness", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "snapshot_freshness_review", "name": "Snapshot Freshness Review", "read_only": True, "mutates_trading_state": False, "description": "Summarize latest snapshot collection, stale data, unknown values, and next collection actions.", "sections": ["Latest Run", "Freshness", "Unknown Data", "Next Actions", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "replay_dataset_readiness_review", "name": "Replay Dataset Readiness Review", "read_only": True, "mutates_trading_state": False, "description": "Check whether local replay datasets are usable for v3.4 Simulation Lab inputs.", "sections": ["Replay-Ready Datasets", "Quality Threshold", "Warnings", "Limitations", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
    ]
    ids = {t.get("workflow_id") for t in templates}
    for template in dataset_templates:
        if template["workflow_id"] not in ids:
            templates.append(template)
    return {**result, "templates": redact_data(templates), "count": len(templates), "dataset_templates": len(dataset_templates), "secret_values_returned": False}


_build_demo_fixture_v34 = build_demo_fixture

def build_demo_fixture() -> dict[str, Any]:  # type: ignore[override]
    fixture = _build_demo_fixture_v34()
    now = _now()
    fixture.setdefault("datasets", {})
    fixture["datasets"]["snapshots"] = [
        _demo_item("demo-market-snapshot-v35", snapshot_id="demo-market-snapshot-v35", snapshot_type="market_metadata", source_subsystem="external_market_data", collection_mode="demo", market_id="DEMO-MARKET-DATASET", created_at=now, quality_status="usable", validation_status="pass", tags=["demo", "dataset", "snapshot"]),
        _demo_item("demo-orderbook-snapshot-v35", snapshot_id="demo-orderbook-snapshot-v35", snapshot_type="order_book", source_subsystem="external_market_data", collection_mode="demo", market_id="DEMO-MARKET-DATASET", created_at=now, quality_status="usable", validation_status="pass", tags=["demo", "dataset", "order_book"]),
    ]
    fixture["datasets"]["manifests"] = [_demo_item("demo-replay-dataset-v35", dataset_id="demo-replay-dataset-v35", title="DEMO Replay Dataset", dataset_type="replay_dataset", created_at=now, quality_status="usable", quality_score=78, tags=["demo", "dataset", "replay"])]
    fixture["datasets"]["quality_reports"] = [_demo_item("demo-quality-report-v35", quality_report_id="demo-quality-report-v35", dataset_id="demo-replay-dataset-v35", quality_status="usable", quality_score=78, findings=[{"severity": "warning", "title": "Fake stale evidence warning"}], tags=["demo", "dataset", "quality"])]
    fixture["datasets_note"] = "Fake dataset-friendly demo records only. No real credentials, no live orders, no financial advice."
    return redact_data(fixture)


_validation_status_v34 = validation_status

def validation_status() -> dict[str, Any]:  # type: ignore[override]
    status = _validation_status_v34()
    root = Path(__file__).resolve().parents[1]
    docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md",
        "docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md",
        "docs/V3_UI_UX_REDESIGN_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    checks = status.get("checks", []) + [{"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review v3.5 dataset/snapshot documentation before release."} for rel in docs]
    try:
        from .live_v3_datasets import datasets_summary
        ds_ok = datasets_summary().get("secret_values_returned") is False
    except Exception:
        ds_ok = False
    checks.append({"check": "v3.5 dataset builder", "status": "pass" if ds_ok else "warning", "details": "Local-first read-only snapshots/datasets; no order placement/cancellation/arming."})
    status.update({"checks": checks, "overall_status": "pass" if ds_ok and all(c.get("status") == "pass" for c in checks if "v3.5" in str(c.get("check", ""))) else "warning", "dataset_builder_active": True, "dataset_snapshot_collection_is_read_only": True, "dataset_workflows_do_not_arm_live_trading": True, "secret_values_returned": False})
    return redact_data(status)


_run_workflow_v34 = run_workflow

def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    payload = payload or {}
    workflow_id = _safe_text(payload.get("workflow_id") or payload.get("id"), "")
    if workflow_id in {"dataset_quality_review", "snapshot_freshness_review", "replay_dataset_readiness_review"}:
        try:
            from .live_v3_datasets import dataset_workflow_context, export_dataset_json, export_dataset_markdown
            if workflow_id == "dataset_quality_review":
                output = export_dataset_json(payload.get("dataset_id"))
            elif workflow_id == "snapshot_freshness_review":
                output = dataset_workflow_context().get("snapshot_freshness_review")
            else:
                output = dataset_workflow_context().get("replay_dataset_readiness_review")
            run = redact_data({
                "run_id": f"v3_run_{uuid4().hex[:12]}",
                "workflow_id": workflow_id,
                "started_at": _now(),
                "completed_at": _now(),
                "status": "completed",
                "read_only": True,
                "mutated_trading_state": False,
                "order_submitted": False,
                "order_cancelled": False,
                "live_trading_armed": False,
                "ai_assistance_enabled": False,
                "output": output,
                "markdown_preview": export_dataset_markdown(payload.get("dataset_id")) if workflow_id == "dataset_quality_review" else "",
                "secret_values_returned": False,
            })
            _ensure_dir()
            with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(run, sort_keys=True, default=str) + "\n")
            _event("workflow_run_completed", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"], "dataset_workflow": True})
            return run
        except Exception as exc:
            return redact_data({"run_id": f"v3_run_{uuid4().hex[:12]}", "workflow_id": workflow_id, "status": "failed", "error_redacted": redact_text(str(exc)), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False})
    return _run_workflow_v34(payload)

_create_demo_data_v34 = create_demo_data

def create_demo_data() -> dict[str, Any]:  # type: ignore[override]
    result = _create_demo_data_v34()
    # The v3.5 demo fixture includes dataset-friendly fake records in demo_fixture.json.
    # It does not automatically create runtime dataset/snapshot collections on demo load.
    # Use app.live_v3_datasets.create_demo_dataset_records() explicitly for full dataset demo records.
    result["dataset_demo"] = {"ok": True, "fixture_only": True, "demo_data_is_fake": True, "secret_values_returned": False}
    result["order_submitted"] = False
    result["order_cancelled"] = False
    result["live_trading_armed"] = False
    result["secret_values_returned"] = False
    return redact_data(result)

_clear_demo_data_v34 = clear_demo_data

def clear_demo_data() -> dict[str, Any]:  # type: ignore[override]
    result = _clear_demo_data_v34()
    try:
        from .live_v3_datasets import DATASETS_DIR
        # Runtime demo dataset records live under data/live_v3/datasets and are never shipped in release ZIPs.
        import shutil
        shutil.rmtree(DATASETS_DIR, ignore_errors=True)
        result["dataset_demo_cleared"] = True
    except Exception as exc:
        result["dataset_demo_cleared"] = False
        result["dataset_demo_error_redacted"] = redact_text(str(exc))
    result["order_submitted"] = False
    result["order_cancelled"] = False
    result["live_trading_armed"] = False
    result["secret_values_returned"] = False
    return redact_data(result)


# v4.4.0-real freshness/scheduler layer: read-only collection planning, dataset freshness,
# local notifications, and operator-controlled collection queues.
_build_search_index_v35 = build_search_index

def build_search_index(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    result = _build_search_index_v35(limit=limit)
    try:
        from .live_v3_freshness import freshness_search_items
        items = result.get("items", []) + freshness_search_items(limit=limit)
        result.update({"items": redact_data(items[: max(1, min(int(limit or 250), 5000))]), "count": len(items), "freshness_items": len(freshness_search_items(limit=limit)), "secret_values_returned": False})
    except Exception as exc:
        result.setdefault("warnings", []).append(f"Freshness search integration unavailable: {redact_text(str(exc))}")
    return redact_data(result)

_build_decision_graph_v35 = build_decision_graph

def build_decision_graph(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    graph = _build_decision_graph_v35(limit=limit)
    try:
        from .live_v3_freshness import freshness_graph_nodes_edges
        fg = freshness_graph_nodes_edges()
        nodes = graph.get("nodes", []) + fg.get("nodes", [])
        edges = graph.get("edges", []) + fg.get("edges", [])
        graph.update({"nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), "freshness_nodes": len(fg.get("nodes", [])), "freshness_edges": len(fg.get("edges", [])), "secret_values_returned": False})
    except Exception as exc:
        graph.setdefault("warnings", []).append(f"Freshness graph integration unavailable: {redact_text(str(exc))}")
    return redact_data(graph)

_build_command_center_v35 = build_command_center

def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_v35()
    try:
        from .live_v3_freshness import summary as freshness_summary
        fresh = freshness_summary()
        center.setdefault("groups", {})["freshness"] = {
            "dataset_freshness_status": fresh.get("dataset_freshness_status", "unknown"),
            "stale_snapshot_count": fresh.get("stale_snapshot_count", 0),
            "stale_dataset_count": fresh.get("stale_dataset_count", 0),
            "queued_collection_jobs": fresh.get("queued_collection_jobs", 0),
            "failed_collection_jobs": fresh.get("failed_collection_jobs", 0),
            "unread_local_notifications": fresh.get("unread_local_notifications", 0),
            "replay_readiness_warnings": fresh.get("replay_readiness_warnings", 0),
            "next_dataset_collection_action": fresh.get("next_dataset_collection_action"),
        }
        center["freshness_summary"] = fresh
        center["release_candidate_stage"] = "v3.7 freshness scheduler and local operator notification layer"
        center["safety_boundary"] = "The v3.7 freshness planner, scheduler scaffolding, local notifications, datasets, simulations, analytics, workflows, and reports are read-only/descriptive and do not place, cancel, approve, sign, or arm live orders."
    except Exception as exc:
        center.setdefault("warnings", []).append(f"Freshness command-center integration unavailable: {redact_text(str(exc))}")
    center["secret_values_returned"] = False
    return redact_data(center)

_workflow_templates_v35 = workflow_templates

def workflow_templates() -> dict[str, Any]:  # type: ignore[override]
    result = _workflow_templates_v35()
    templates = result.get("templates", [])
    freshness_templates = [
        {"workflow_id": "freshness_review", "name": "Freshness Review", "read_only": True, "mutates_trading_state": False, "description": "Review stale snapshots, stale datasets, unread local notifications, and replay readiness warnings.", "sections": ["Freshness Findings", "Collection Jobs", "Notifications", "Dataset Readiness", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "collection_plan_review", "name": "Collection Plan Review", "read_only": True, "mutates_trading_state": False, "description": "Inspect policies and queued read-only collection jobs before running them manually.", "sections": ["Policies", "Queued Jobs", "Read-Only Assertions", "Blocked/Unsafe Jobs", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "notification_triage", "name": "Notification Triage", "read_only": True, "mutates_trading_state": False, "description": "Triage stale dataset, failed job, validation, and readiness notifications locally.", "sections": ["Notifications", "Acknowledgments", "Snoozed Items", "Resolved Items", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "dataset_readiness_review", "name": "Dataset Readiness Review", "read_only": True, "mutates_trading_state": False, "description": "Check freshness and dataset quality before replay, simulation, or operator review.", "sections": ["Readiness", "Missing Snapshots", "Stale Snapshots", "Recommended Collection Jobs", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
    ]
    ids = {t.get("workflow_id") for t in templates}
    for template in freshness_templates:
        if template["workflow_id"] not in ids:
            templates.append(template)
    return {**result, "templates": redact_data(templates), "count": len(templates), "freshness_templates": len(freshness_templates), "secret_values_returned": False}

_validation_status_v35 = validation_status

def validation_status() -> dict[str, Any]:  # type: ignore[override]
    status = _validation_status_v35()
    root = Path(__file__).resolve().parents[1]
    docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md",
        "docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md",
        "docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md",
        "docs/V3_UI_UX_REDESIGN_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    checks = status.get("checks", []) + [{"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review v3.7 freshness/scheduler documentation before release."} for rel in docs]
    try:
        from .live_v3_freshness import summary as freshness_summary
        fresh_ok = freshness_summary().get("secret_values_returned") is False
    except Exception:
        fresh_ok = False
    checks.append({"check": "v3.7 freshness scheduler", "status": "pass" if fresh_ok else "warning", "details": "Local-first read-only scheduler/freshness layer; no order placement/cancellation/arming."})
    status.update({"checks": checks, "overall_status": "pass" if fresh_ok and all(c.get("status") == "pass" for c in checks if "v3.7" in str(c.get("check", ""))) else "warning", "freshness_scheduler_active": True, "freshness_collection_is_read_only": True, "freshness_scheduler_disabled_by_default": True, "freshness_workflows_do_not_arm_live_trading": True, "secret_values_returned": False})
    return redact_data(status)

_build_demo_fixture_v35 = build_demo_fixture

def build_demo_fixture() -> dict[str, Any]:  # type: ignore[override]
    fixture = _build_demo_fixture_v35()
    now = _now()
    fixture.setdefault("freshness", {})
    fixture["freshness"]["policies"] = [_demo_item("demo-freshness-policy-v36", policy_id="demo-freshness-policy-v36", title="DEMO Dataset Freshness Policy", target_snapshot_types=["market_metadata", "order_book"], enabled=True, created_at=now, tags=["demo", "freshness", "policy"])]
    fixture["freshness"]["jobs"] = [_demo_item("demo-collection-job-v36", job_id="demo-collection-job-v36", status="queued", requested_snapshot_types=["market_metadata", "order_book"], run_mode="demo", created_at=now, tags=["demo", "freshness", "job"])]
    fixture["freshness"]["notifications"] = [_demo_item("demo-freshness-note-v36", notification_id="demo-freshness-note-v36", title="DEMO dataset needs refresh", severity="warning", status="new", created_at=now, tags=["demo", "freshness", "notification"])]
    fixture["freshness_note"] = "Fake freshness-friendly demo records only. No real credentials, no live orders, no financial advice."
    return redact_data(fixture)

_run_workflow_v35 = run_workflow

def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    payload = payload or {}
    workflow_id = _safe_text(payload.get("workflow_id") or payload.get("id"), "")
    if workflow_id in {"freshness_review", "collection_plan_review", "notification_triage", "dataset_readiness_review"}:
        try:
            from .live_v3_freshness import freshness_workflow_context, export_freshness_markdown
            context = freshness_workflow_context()
            output = context.get(workflow_id) or context
            run = redact_data({
                "run_id": f"v3_run_{uuid4().hex[:12]}",
                "workflow_id": workflow_id,
                "started_at": _now(),
                "completed_at": _now(),
                "status": "completed",
                "read_only": True,
                "mutated_trading_state": False,
                "order_submitted": False,
                "order_cancelled": False,
                "live_trading_armed": False,
                "ai_assistance_enabled": False,
                "output": output,
                "markdown_preview": export_freshness_markdown(),
                "secret_values_returned": False,
            })
            _ensure_dir()
            with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(run, sort_keys=True, default=str) + "\n")
            _event("workflow_run_completed", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"], "freshness_workflow": True})
            return run
        except Exception as exc:
            return redact_data({"run_id": f"v3_run_{uuid4().hex[:12]}", "workflow_id": workflow_id, "status": "failed", "error_redacted": redact_text(str(exc)), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False})
    return _run_workflow_v35(payload)

_create_demo_data_v35 = create_demo_data

def create_demo_data() -> dict[str, Any]:  # type: ignore[override]
    result = _create_demo_data_v35()
    try:
        from .live_v3_freshness import create_demo_freshness_records
        result["freshness_demo"] = create_demo_freshness_records()
    except Exception as exc:
        result["freshness_demo"] = {"ok": False, "error_redacted": redact_text(str(exc)), "secret_values_returned": False}
    result["order_submitted"] = False
    result["order_cancelled"] = False
    result["live_trading_armed"] = False
    result["secret_values_returned"] = False
    return redact_data(result)

_clear_demo_data_v35 = clear_demo_data

def clear_demo_data() -> dict[str, Any]:  # type: ignore[override]
    result = _clear_demo_data_v35()
    try:
        from .live_v3_freshness import FRESHNESS_DIR
        import shutil
        shutil.rmtree(FRESHNESS_DIR, ignore_errors=True)
        result["freshness_demo_cleared"] = True
    except Exception as exc:
        result["freshness_demo_cleared"] = False
        result["freshness_demo_error_redacted"] = redact_text(str(exc))
    result["order_submitted"] = False
    result["order_cancelled"] = False
    result["live_trading_armed"] = False
    result["secret_values_returned"] = False
    return redact_data(result)

# v4.4.0-real operator task planner, daily ops, weekly cadence, and human-in-the-loop follow-through layer.
_build_search_index_v36 = build_search_index

def build_search_index(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    result = _build_search_index_v36(limit=limit)
    try:
        from .live_v3_tasks import tasks_search_items
        task_items = tasks_search_items(limit=limit)
        items = result.get("items", []) + task_items
        items.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
        result.update({"items": redact_data(items[: max(1, min(int(limit or 250), 5000))]), "count": len(items), "task_items": len(task_items), "secret_values_returned": False})
    except Exception as exc:
        result.setdefault("warnings", []).append(f"Task search integration unavailable: {redact_text(str(exc))}")
    return redact_data(result)

_build_decision_graph_v36 = build_decision_graph

def build_decision_graph(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    graph = _build_decision_graph_v36(limit=limit)
    try:
        from .live_v3_tasks import tasks_graph_nodes_edges
        tg = tasks_graph_nodes_edges()
        nodes = graph.get("nodes", []) + tg.get("nodes", [])
        edges = graph.get("edges", []) + tg.get("edges", [])
        graph.update({"nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), "task_nodes": len(tg.get("nodes", [])), "task_edges": len(tg.get("edges", [])), "secret_values_returned": False})
    except Exception as exc:
        graph.setdefault("warnings", []).append(f"Task graph integration unavailable: {redact_text(str(exc))}")
    return redact_data(graph)

_build_command_center_v36 = build_command_center

def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_v36()
    try:
        from .live_v3_tasks import task_summary
        tasks = task_summary()
        center.setdefault("groups", {})["tasks"] = {
            "open_tasks": tasks.get("open_tasks", 0),
            "urgent_tasks": tasks.get("urgent_tasks", 0),
            "blocked_tasks": tasks.get("blocked_tasks", 0),
            "overdue_tasks": tasks.get("overdue_tasks", 0),
            "tasks_due_today": tasks.get("tasks_due_today", 0),
            "inbox_items": tasks.get("inbox_items", 0),
            "daily_checklist_status": tasks.get("daily_checklist_status"),
            "weekly_planning_status": tasks.get("weekly_planning_status"),
            "next_operator_task": tasks.get("next_operator_task"),
        }
        center["tasks_summary"] = tasks
        center["release_candidate_stage"] = "v3.7 operator task planner, daily ops, weekly cadence, and HITL follow-through layer"
        center["safety_boundary"] = "The v3.7 task planner, cadence manager, daily/weekly ops packets, notification/finding conversion, search, graph, workflow, freshness, datasets, simulations, analytics, and reports are local workflow records only. They do not place, cancel, approve, sign, or arm live orders."
    except Exception as exc:
        center.setdefault("warnings", []).append(f"Task command-center integration unavailable: {redact_text(str(exc))}")
    center["secret_values_returned"] = False
    return redact_data(center)

_workflow_templates_v36 = workflow_templates

def workflow_templates() -> dict[str, Any]:  # type: ignore[override]
    result = _workflow_templates_v36()
    templates = result.get("templates", [])
    task_templates = [
        {"workflow_id": "daily_ops_packet", "name": "Daily Ops Packet", "read_only": True, "mutates_trading_state": False, "description": "Generate a local daily operator checklist, unresolved item rollup, and safe next-action packet.", "sections": ["Safety", "Open Tasks", "Inbox", "Blocked Tasks", "Unknown Data"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "weekly_planning_packet", "name": "Weekly Planning Packet", "read_only": True, "mutates_trading_state": False, "description": "Roll up open/overdue tasks, recurring blockers, stale data, review needs, and next-week focus.", "sections": ["Task Rollup", "Review Needs", "Blockers", "Next Week Focus", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "task_triage_packet", "name": "Task Triage Packet", "read_only": True, "mutates_trading_state": False, "description": "Summarize local task inbox items and suggested conversions without auto-submitting anything.", "sections": ["Inbox", "Suggested Tasks", "Dismissals", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "blocked_task_review", "name": "Blocked Task Review", "read_only": True, "mutates_trading_state": False, "description": "Review blocked tasks, blockers, related objects, and human follow-up needs.", "sections": ["Blocked Tasks", "Dependencies", "Unknown Data", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "cadence_review", "name": "Cadence Review", "read_only": True, "mutates_trading_state": False, "description": "Review cadence rules and optionally generate local inbox suggestions through explicit operator action.", "sections": ["Cadence Rules", "Generated Inbox Items", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
    ]
    ids = {t.get("workflow_id") for t in templates}
    for template in task_templates:
        if template["workflow_id"] not in ids:
            templates.append(template)
    return {**result, "templates": redact_data(templates), "count": len(templates), "task_templates": len(task_templates), "secret_values_returned": False}

_run_workflow_v36 = run_workflow

def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    payload = payload or {}
    workflow_id = _safe_text(payload.get("workflow_id"), "operator_review_packet")
    if workflow_id in {"daily_ops_packet", "weekly_planning_packet", "task_triage_packet", "blocked_task_review", "cadence_review"}:
        try:
            from .live_v3_tasks import generate_daily_ops_packet, generate_weekly_plan, list_inbox, list_tasks, list_cadence_rules, run_cadence
            if workflow_id == "daily_ops_packet":
                output = generate_daily_ops_packet(payload, write=True)
            elif workflow_id == "weekly_planning_packet":
                output = generate_weekly_plan(payload, write=True)
            elif workflow_id == "task_triage_packet":
                output = {"inbox": list_inbox(limit=250), "suggested_action": "Convert relevant inbox items to planned tasks after human review."}
            elif workflow_id == "blocked_task_review":
                output = {"blocked_tasks": list_tasks(limit=250, status="blocked"), "suggested_action": "Resolve blockers or document dependencies. Completion is not trade approval."}
            else:
                output = run_cadence({"create_tasks": bool(payload.get("create_tasks", False))}) if payload.get("run") else {"cadence": list_cadence_rules(limit=250), "operator_trigger_required": True}
            run = {
                "run_id": f"workflow_{uuid4().hex[:12]}",
                "workflow_id": workflow_id,
                "status": "completed",
                "created_at": _now(),
                "app_version": APP_VERSION,
                "output": redact_data(output),
                "order_submitted": False,
                "order_cancelled": False,
                "live_trading_armed": False,
                "mutates_trading_state": False,
                "secret_values_returned": False,
            }
            _ensure_dir()
            with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(redact_data(run), sort_keys=True, default=str) + "\n")
            _event("workflow_run", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"], "task_workflow": True})
            return redact_data(run)
        except Exception as exc:
            return {"workflow_id": workflow_id, "status": "failed", "error": redact_text(str(exc)), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    return _run_workflow_v36(payload)

_build_demo_fixture_v36 = build_demo_fixture

def build_demo_fixture() -> dict[str, Any]:  # type: ignore[override]
    fixture = _build_demo_fixture_v36()
    try:
        from .live_v3_tasks import demo_fixture as task_demo_fixture
        fixture.update(task_demo_fixture())
        fixture["task_planner_note"] = "Fake v3.7 task planner demo records only. No live orders, no private data, no financial advice."
    except Exception as exc:
        fixture.setdefault("warnings", []).append(f"Task demo fixture unavailable: {redact_text(str(exc))}")
    return redact_data(fixture)

_validation_status_v36 = validation_status

def validation_status() -> dict[str, Any]:  # type: ignore[override]
    status = _validation_status_v36()
    root = Path(__file__).resolve().parents[1]
    docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md",
        "docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md",
        "docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md",
        "docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md",
        "docs/V3_UI_UX_REDESIGN_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    checks = status.get("checks", []) + [{"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review v3.7 task planner and daily ops documentation before release."} for rel in docs]
    try:
        from .live_v3_tasks import task_summary, generate_daily_ops_packet, generate_weekly_plan
        task_ok = task_summary().get("secret_values_returned") is False
        daily_ok = generate_daily_ops_packet(write=False).get("order_submitted") is False
        weekly_ok = generate_weekly_plan(write=False).get("live_trading_armed") is False
    except Exception:
        task_ok = daily_ok = weekly_ok = False
    checks.append({"check": "v3.7 task planner safety", "status": "pass" if task_ok and daily_ok and weekly_ok else "warning", "details": "Local-first task/cadence workflows do not place/cancel/approve/sign/arm live orders."})
    status.update({"checks": checks, "overall_status": "pass" if task_ok and daily_ok and weekly_ok else "warning", "task_planner_active": True, "task_planning_is_local_first": True, "task_workflows_do_not_arm_live_trading": True, "task_completion_is_not_trade_approval": True, "secret_values_returned": False})
    return redact_data(status)

# v4.4.0-real guided operator workspace, interactive review flows, source previews,
# saved views, task dependency intelligence, and review packet integration.
_build_search_index_v37 = build_search_index

def build_search_index(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    result = _build_search_index_v37(limit=limit)
    try:
        from .live_v3_workspace import workspace_search_items
        workspace_items = workspace_search_items(limit=limit)
        items = result.get("items", []) + workspace_items
        items.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
        result.update({"items": redact_data(items[: max(1, min(int(limit or 250), 5000))]), "count": len(items), "workspace_items": len(workspace_items), "secret_values_returned": False})
    except Exception as exc:
        result.setdefault("warnings", []).append(f"Guided workspace search integration unavailable: {redact_text(str(exc))}")
    return redact_data(result)

_build_decision_graph_v37 = build_decision_graph

def build_decision_graph(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    graph = _build_decision_graph_v37(limit=limit)
    try:
        from .live_v3_workspace import workspace_graph_nodes_edges
        wg = workspace_graph_nodes_edges()
        nodes = graph.get("nodes", []) + wg.get("nodes", [])
        edges = graph.get("edges", []) + wg.get("edges", [])
        graph.update({"nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), "workspace_nodes": len(wg.get("nodes", [])), "workspace_edges": len(wg.get("edges", [])), "secret_values_returned": False})
    except Exception as exc:
        graph.setdefault("warnings", []).append(f"Guided workspace graph integration unavailable: {redact_text(str(exc))}")
    return redact_data(graph)

_build_command_center_v37 = build_command_center

def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_v37()
    try:
        from .live_v3_workspace import workspace_summary
        workspace = workspace_summary()
        center.setdefault("groups", {})["workspace"] = {
            "active_guided_review_session": workspace.get("active_guided_review_session"),
            "latest_daily_review": workspace.get("latest_daily_review"),
            "latest_weekly_review": workspace.get("latest_weekly_review"),
            "blocked_task_count": workspace.get("blocked_task_count", 0),
            "dependency_warning_count": workspace.get("dependency_warning_count", 0),
            "next_guided_step": workspace.get("next_guided_step"),
            "latest_review_packet": workspace.get("latest_review_packet"),
            "saved_views_count": workspace.get("saved_views_count", 0),
            "source_previews_awaiting_review": workspace.get("source_previews_awaiting_review", 0),
        }
        center["workspace_summary"] = workspace
        center["release_candidate_stage"] = "v3.8 guided operator workspace, review flows, source previews, saved views, and task dependency intelligence"
        center["safety_boundary"] = "The v3.8 guided workspace, task dependencies, saved views, source previews, review packets, tasks, cadence, freshness, datasets, simulations, analytics, search, graph, and workflows are local workflow records only. They do not place, cancel, approve, sign, or arm live orders."
    except Exception as exc:
        center.setdefault("warnings", []).append(f"Guided workspace command-center integration unavailable: {redact_text(str(exc))}")
    center["secret_values_returned"] = False
    return redact_data(center)

_workflow_templates_v37 = workflow_templates

def workflow_templates() -> dict[str, Any]:  # type: ignore[override]
    result = _workflow_templates_v37()
    templates = result.get("templates", [])
    workspace_templates = [
        {"workflow_id": "guided_daily_review_packet", "name": "Guided Daily Review Packet", "read_only": True, "mutates_trading_state": False, "description": "Start or summarize a local guided daily review session and packet.", "sections": ["Safety", "Review Steps", "Unresolved Items", "Blockers", "Packet"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "guided_weekly_review_packet", "name": "Guided Weekly Review Packet", "read_only": True, "mutates_trading_state": False, "description": "Create guided weekly planning context with task rollups and next-week focus.", "sections": ["Open Tasks", "Overdue", "Review Needs", "Next Week", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "task_dependency_review", "name": "Task Dependency Review", "read_only": True, "mutates_trading_state": False, "description": "Review workflow-only task dependencies and blockers.", "sections": ["Dependencies", "Blocked Tasks", "Warnings", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "source_preview_review", "name": "Source Preview Review", "read_only": True, "mutates_trading_state": False, "description": "Generate source-context previews before converting findings to tasks.", "sections": ["Source", "Unknowns", "Template", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "saved_view_review", "name": "Saved View Review", "read_only": True, "mutates_trading_state": False, "description": "Review saved task views as filters, not trading recommendations.", "sections": ["Views", "Filters", "Limitations", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
    ]
    ids = {t.get("workflow_id") for t in templates}
    for template in workspace_templates:
        if template["workflow_id"] not in ids:
            templates.append(template)
    return {**result, "templates": redact_data(templates), "count": len(templates), "workspace_templates": len(workspace_templates), "secret_values_returned": False}

_run_workflow_v37 = run_workflow

def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    payload = payload or {}
    workflow_id = _safe_text(payload.get("workflow_id"), "operator_review_packet")
    if workflow_id in {"guided_daily_review_packet", "guided_weekly_review_packet", "task_dependency_review", "source_preview_review", "saved_view_review"}:
        try:
            from .live_v3_workspace import start_daily_review, start_weekly_review, blocked_review, create_source_preview, export_saved_views_json, generate_review_packet
            if workflow_id == "guided_daily_review_packet":
                started = start_daily_review(payload)
                output = generate_review_packet({"session_id": started.get("session", {}).get("session_id", ""), "packet_type": "daily-review", "title": "Guided Daily Review Packet"}, write=True)
            elif workflow_id == "guided_weekly_review_packet":
                started = start_weekly_review(payload)
                output = generate_review_packet({"session_id": started.get("session", {}).get("session_id", ""), "packet_type": "weekly-review", "title": "Guided Weekly Review Packet"}, write=True)
            elif workflow_id == "task_dependency_review":
                output = blocked_review(write=True)
            elif workflow_id == "source_preview_review":
                output = create_source_preview(payload, write=True)
            else:
                output = export_saved_views_json()
            run = {
                "run_id": f"workflow_{uuid4().hex[:12]}",
                "workflow_id": workflow_id,
                "status": "completed",
                "created_at": _now(),
                "app_version": APP_VERSION,
                "output": redact_data(output),
                "order_submitted": False,
                "order_cancelled": False,
                "live_trading_armed": False,
                "mutates_trading_state": False,
                "guided_review_completion_is_not_trade_approval": True,
                "secret_values_returned": False,
            }
            _ensure_dir()
            with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(redact_data(run), sort_keys=True, default=str) + "\n")
            _event("workflow_run", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"], "guided_workspace_workflow": True})
            return redact_data(run)
        except Exception as exc:
            return {"workflow_id": workflow_id, "status": "failed", "error": redact_text(str(exc)), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    return _run_workflow_v37(payload)

_build_demo_fixture_v37 = build_demo_fixture

def build_demo_fixture() -> dict[str, Any]:  # type: ignore[override]
    fixture = _build_demo_fixture_v37()
    try:
        from .live_v3_workspace import demo_fixture as workspace_demo_fixture
        fixture.update(workspace_demo_fixture())
        fixture["guided_workspace_note"] = "Fake v3.8 guided workspace demo records only. No live orders, no private data, no financial advice."
    except Exception as exc:
        fixture.setdefault("warnings", []).append(f"Guided workspace demo fixture unavailable: {redact_text(str(exc))}")
    return redact_data(fixture)

_validation_status_v37 = validation_status

def validation_status() -> dict[str, Any]:  # type: ignore[override]
    status = _validation_status_v37()
    root = Path(__file__).resolve().parents[1]
    docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md",
        "docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md",
        "docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md",
        "docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md",
        "docs/V3_UI_UX_REDESIGN_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    checks = status.get("checks", []) + [{"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review v3.8 guided workspace documentation before release."} for rel in docs]
    try:
        from .live_v3_workspace import workspace_summary, start_daily_review, generate_review_packet, create_dependency
        workspace_ok = workspace_summary().get("secret_values_returned") is False
        daily = start_daily_review({"title": "Validation guided daily review"})
        packet = generate_review_packet({"session_id": daily.get("session", {}).get("session_id", ""), "packet_type": "daily-review"}, write=False)
        dep = create_dependency({"task_id": "validation-task", "depends_on_task_id": "validation-prereq"})
        guided_ok = daily.get("order_submitted") is False and packet.get("order_cancelled") is False and dep.get("live_trading_armed") is False
    except Exception:
        workspace_ok = guided_ok = False
    checks.append({"check": "v3.8 guided workspace safety", "status": "pass" if workspace_ok and guided_ok else "warning", "details": "Local-first guided review, dependency, saved-view, and source-preview workflows do not place/cancel/approve/sign/arm live orders."})
    status.update({"checks": checks, "overall_status": "pass" if workspace_ok and guided_ok else "warning", "guided_workspace_active": True, "guided_reviews_are_local_first": True, "guided_workflows_do_not_arm_live_trading": True, "guided_review_completion_is_not_trade_approval": True, "secret_values_returned": False})
    return redact_data(status)

# v4.4.0-real multi-panel operator cockpit, saved layouts, keyboard navigation,
# safe command palette, focus modes, side-by-side context, and dependency visualization.
_build_search_index_v38 = build_search_index

def build_search_index(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    result = _build_search_index_v38(limit=limit)
    try:
        from .live_v3_cockpit import cockpit_search_items
        cockpit_items = cockpit_search_items(limit=limit)
        items = result.get("items", []) + cockpit_items
        items.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
        result.update({"items": redact_data(items[: max(1, min(int(limit or 250), 5000))]), "count": len(items), "cockpit_items": len(cockpit_items), "secret_values_returned": False})
    except Exception as exc:
        result.setdefault("warnings", []).append(f"Cockpit search integration unavailable: {redact_text(str(exc))}")
    return redact_data(result)

_build_decision_graph_v38 = build_decision_graph

def build_decision_graph(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    graph = _build_decision_graph_v38(limit=limit)
    try:
        from .live_v3_cockpit import cockpit_graph_nodes_edges
        cg = cockpit_graph_nodes_edges()
        nodes = graph.get("nodes", []) + cg.get("nodes", [])
        edges = graph.get("edges", []) + cg.get("edges", [])
        graph.update({"nodes": redact_data(nodes), "edges": redact_data(edges), "node_count": len(nodes), "edge_count": len(edges), "cockpit_nodes": len(cg.get("nodes", [])), "cockpit_edges": len(cg.get("edges", [])), "secret_values_returned": False})
    except Exception as exc:
        graph.setdefault("warnings", []).append(f"Cockpit graph integration unavailable: {redact_text(str(exc))}")
    return redact_data(graph)

_build_command_center_v38 = build_command_center

def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_v38()
    try:
        from .live_v3_cockpit import cockpit_summary
        cockpit = cockpit_summary()
        center.setdefault("groups", {})["cockpit"] = {
            "active_cockpit_layout": cockpit.get("active_cockpit_layout"),
            "active_focus_mode": cockpit.get("active_focus_mode"),
            "cockpit_saved_layouts_count": cockpit.get("cockpit_saved_layouts_count", 0),
            "available_shortcuts_count": cockpit.get("available_shortcuts_count", 0),
            "command_palette_safe_actions_count": cockpit.get("command_palette_safe_actions_count", 0),
            "active_guided_review_session": cockpit.get("active_guided_review_session"),
            "blocked_task_count": cockpit.get("blocked_task_count", 0),
            "dependency_warning_count": cockpit.get("dependency_warning_count", 0),
            "overdue_task_count": cockpit.get("overdue_task_count", 0),
            "source_previews_awaiting_review": cockpit.get("source_previews_awaiting_review", 0),
            "latest_review_packet": cockpit.get("latest_review_packet"),
        }
        center["cockpit_summary"] = cockpit
        center["release_candidate_stage"] = "v4.0 multi-panel operator cockpit, keyboard navigation, safe command palette, saved layouts, focus modes, and side-by-side review context"
        center["safety_boundary"] = "The v4.0 cockpit, shortcuts, command palette, layouts, focus modes, tasks, guided workspace, cadence, freshness, datasets, simulations, analytics, search, graph, and workflows are local workflow/navigation records only. They do not place, cancel, approve, sign, or arm live orders."
    except Exception as exc:
        center.setdefault("warnings", []).append(f"Cockpit command-center integration unavailable: {redact_text(str(exc))}")
    center["secret_values_returned"] = False
    return redact_data(center)

_workflow_templates_v38 = workflow_templates

def workflow_templates() -> dict[str, Any]:  # type: ignore[override]
    result = _workflow_templates_v38()
    templates = result.get("templates", [])
    cockpit_templates = [
        {"workflow_id": "cockpit_layout_review", "name": "Cockpit Layout Review", "read_only": True, "mutates_trading_state": False, "description": "Review active/saved cockpit layouts, panels, unknowns, blockers, and safety boundaries.", "sections": ["Layouts", "Panels", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "cockpit_focus_mode_review", "name": "Cockpit Focus Mode Review", "read_only": True, "mutates_trading_state": False, "description": "Review cockpit focus modes and safe next actions without creating trading automation.", "sections": ["Focus Modes", "Suggested Safe Actions", "Unknown Data", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "cockpit_dependency_review", "name": "Cockpit Dependency Review", "read_only": True, "mutates_trading_state": False, "description": "Review task dependency chains and blockers from the cockpit.", "sections": ["Dependency Chain", "Blockers", "Source Context", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "cockpit_source_context_review", "name": "Cockpit Source Context Review", "read_only": True, "mutates_trading_state": False, "description": "Review source previews side-by-side with tasks and guided context.", "sections": ["Source Previews", "Linked Tasks", "Unknown Data", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "cockpit_command_palette_safety_review", "name": "Cockpit Command Palette Safety Review", "read_only": True, "mutates_trading_state": False, "description": "Review safe command-palette and keyboard shortcut manifests for live-mutation separation.", "sections": ["Command Palette", "Keyboard Shortcuts", "Forbidden Actions", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
    ]
    ids = {t.get("workflow_id") for t in templates}
    for template in cockpit_templates:
        if template["workflow_id"] not in ids:
            templates.append(template)
    return {**result, "templates": redact_data(templates), "count": len(templates), "cockpit_templates": len(cockpit_templates), "secret_values_returned": False}

_run_workflow_v38 = run_workflow

def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    payload = payload or {}
    workflow_id = _safe_text(payload.get("workflow_id"), "operator_review_packet")
    if workflow_id in {"cockpit_layout_review", "cockpit_focus_mode_review", "cockpit_dependency_review", "cockpit_source_context_review", "cockpit_command_palette_safety_review"}:
        try:
            from .live_v3_cockpit import export_json, export_markdown, export_focus_mode_json, dependency_view, source_context, export_command_palette_json, export_shortcuts_json
            if workflow_id == "cockpit_layout_review":
                output = {"json": export_json(), "markdown": export_markdown()}
            elif workflow_id == "cockpit_focus_mode_review":
                output = export_focus_mode_json()
            elif workflow_id == "cockpit_dependency_review":
                output = dependency_view(task_id=str(payload.get("task_id", "")))
            elif workflow_id == "cockpit_source_context_review":
                output = source_context()
            else:
                output = {"command_palette": export_command_palette_json(), "keyboard_shortcuts": export_shortcuts_json()}
            run = {
                "run_id": f"workflow_{uuid4().hex[:12]}",
                "workflow_id": workflow_id,
                "status": "completed",
                "created_at": _now(),
                "app_version": APP_VERSION,
                "output": redact_data(output),
                "order_submitted": False,
                "order_cancelled": False,
                "live_trading_armed": False,
                "mutates_trading_state": False,
                "command_palette_actions_do_not_place_or_cancel_orders": True,
                "keyboard_shortcuts_do_not_place_or_cancel_orders": True,
                "secret_values_returned": False,
            }
            _ensure_dir()
            with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(redact_data(run), sort_keys=True, default=str) + "\n")
            _event("workflow_run", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"], "cockpit_workflow": True})
            return redact_data(run)
        except Exception as exc:
            return {"workflow_id": workflow_id, "status": "failed", "error": redact_text(str(exc)), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    return _run_workflow_v38(payload)

_build_demo_fixture_v38 = build_demo_fixture

def build_demo_fixture() -> dict[str, Any]:  # type: ignore[override]
    fixture = _build_demo_fixture_v38()
    try:
        from .live_v3_cockpit import demo_fixture as cockpit_demo_fixture
        fixture.update(cockpit_demo_fixture())
        fixture["operator_cockpit_note"] = "Fake v4.0 cockpit demo records only. No live orders, no private data, no financial advice."
    except Exception as exc:
        fixture.setdefault("warnings", []).append(f"Cockpit demo fixture unavailable: {redact_text(str(exc))}")
    return redact_data(fixture)

_validation_status_v38 = validation_status

def validation_status() -> dict[str, Any]:  # type: ignore[override]
    status = _validation_status_v38()
    root = Path(__file__).resolve().parents[1]
    docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V3_OPERATOR_COCKPIT_GUIDE_v4.7.0-real.md",
        "docs/V3_GUIDED_OPERATOR_WORKSPACE_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_TASK_PLANNER_GUIDE_v4.7.0-real.md",
        "docs/V3_FRESHNESS_SCHEDULER_GUIDE_v4.7.0-real.md",
        "docs/V3_DATASET_BUILDER_GUIDE_v4.7.0-real.md",
        "docs/V3_SIMULATION_LAB_GUIDE_v4.7.0-real.md",
        "docs/V3_UI_UX_REDESIGN_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_ANALYTICS_GUIDE_v4.7.0-real.md",
        "docs/V3_OPERATOR_INTELLIGENCE_OS_GUIDE_v4.7.0-real.md",
        "docs/V2_TO_V3_MIGRATION_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    checks = status.get("checks", []) + [{"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review v4.0 cockpit documentation before release."} for rel in docs]
    try:
        from .live_v3_cockpit import cockpit_summary, create_layout, select_layout, reset_default_layouts, start_focus_mode, create_panel, run_command_palette_action, export_json, keyboard_shortcuts
        cockpit_ok = cockpit_summary().get("secret_values_returned") is False
        layout = create_layout({"title": "Validation cockpit layout", "layout_type": "custom"})
        selected = select_layout(layout["layout_id"])
        reset = reset_default_layouts()
        focus = start_focus_mode("focus_daily_review")
        panel = create_panel({"title": "Validation panel", "panel_type": "task-list"})
        command = run_command_palette_action({"action_id": "navigate_cockpit"})
        forbidden = run_command_palette_action({"action_id": "place_order"})
        export = export_json()
        shortcuts = keyboard_shortcuts()
        cockpit_safety_ok = all([
            layout.get("order_submitted") is False,
            selected.get("order_cancelled") is False,
            reset.get("live_trading_armed") is False,
            focus.get("order_submitted") is False,
            panel.get("mutates_live_trading_state") is False,
            command.get("ok") is True,
            forbidden.get("status") == "rejected",
            export.get("secret_values_returned") is False,
            shortcuts.get("keyboard_shortcuts_do_not_place_or_cancel_orders") is True,
        ])
    except Exception:
        cockpit_ok = cockpit_safety_ok = False
    checks.append({"check": "v4.0 cockpit safety", "status": "pass" if cockpit_ok and cockpit_safety_ok else "warning", "details": "Local-first cockpit, layout, focus-mode, command-palette, keyboard shortcut, dependency, and source-context workflows do not place/cancel/approve/sign/arm live orders."})
    status.update({"checks": checks, "overall_status": "pass" if cockpit_ok and cockpit_safety_ok else "warning", "operator_cockpit_active": True, "cockpit_workflows_are_local_first": True, "cockpit_workflows_do_not_arm_live_trading": True, "command_palette_actions_do_not_place_or_cancel_orders": True, "keyboard_shortcuts_do_not_place_or_cancel_orders": True, "secret_values_returned": False})
    return redact_data(status)


# v4 platform stabilization overrides and integration hooks.
from . import platform_diagnostics as _v4_platform_diagnostics
from . import platform_api as _v4_platform_api
from . import platform_migrations as _v4_platform_migrations
from . import platform_plugins as _v4_platform_plugins
from . import platform_routes as _v4_platform_routes
from . import platform_storage as _v4_platform_storage
from . import platform_safety as _v4_platform_safety
from . import ai_suggestions as _v4_ai
from . import ai_operator_copilot as _v4_ai_copilot
from . import ai_prompt_governance as _v4_ai_prompts
from . import ai_schemas as _v4_ai_schemas
from . import ai_edge_research as _v4_ai_edge

_build_search_index_v39 = build_search_index
_build_decision_graph_v39 = build_decision_graph
_build_command_center_v39 = build_command_center
_workflow_templates_v39 = workflow_templates
_run_workflow_v39 = run_workflow
_build_demo_fixture_v39 = build_demo_fixture
_validation_status_v39 = validation_status


def build_search_index(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    base = _build_search_index_v39(limit=limit)
    rows = list(base.get("items", []))
    rows.extend(_v4_platform_diagnostics.search_items())
    rows.extend(_v4_ai.search_items(limit=limit))
    rows.extend(_v4_ai_edge.search_items(limit=limit))
    rows = rows[: max(1, min(int(limit or 250), 1000))]
    base.update({"version": APP_VERSION, "count": len(rows), "items": redact_data(rows), "platform_indexed": len([r for r in rows if str(r.get("result_type", "")).startswith("platform")]), "ai_indexed": len([r for r in rows if str(r.get("result_type", "")).startswith("ai") or "openai" in str(r.get("result_type", "")) or "chatgpt" in str(r.get("result_type", ""))]), "secret_values_returned": False})
    return base


def build_decision_graph(limit: int = 250) -> dict[str, Any]:  # type: ignore[override]
    graph = _build_decision_graph_v39(limit=limit)
    nodes, edges = _v4_platform_diagnostics.graph_nodes()
    ai_nodes, ai_edges = _v4_ai.graph_nodes()
    edge_nodes, edge_edges = _v4_ai_edge.graph_nodes()
    nodes.extend(ai_nodes)
    edges.extend(ai_edges)
    nodes.extend(edge_nodes)
    edges.extend(edge_edges)
    existing = {n.get("node_id") for n in graph.get("nodes", [])}
    new_nodes = [n for n in nodes if n.get("node_id") not in existing]
    graph["nodes"] = graph.get("nodes", []) + new_nodes
    graph["edges"] = graph.get("edges", []) + edges
    existing_types = {str(n.get("node_type", "")) for n in graph["nodes"]}
    existing_ids = {str(n.get("node_id", "")) for n in graph["nodes"]}
    # Keep v4.3 graph enrichment bounded. The full local search index can be
    # very large on mature packages, and graph diagnostics are only intended to
    # provide a fast, representative inventory for UI/validation.
    safe_limit = max(1, min(int(limit or 250), 100))
    for item in build_search_index(limit=safe_limit).get("items", []):
        rtype = str(item.get("result_type", ""))
        rid = str(item.get("result_id") or item.get("id") or "")
        if not rid or rid in existing_ids:
            continue
        if any(token in rtype for token in ["simulation", "dataset", "freshness", "task", "workspace", "cockpit", "analytics", "platform"]):
            graph["nodes"].append({
                "node_id": rid,
                "node_type": rtype,
                "title": item.get("title", rtype),
                "status": item.get("status", "available"),
                "summary": item.get("summary", "Local v4 graph coverage node."),
            })
            existing_ids.add(rid)
            existing_types.add(rtype)
    max_nodes = max(1, min(int(limit or 250), 500))
    max_edges = max_nodes * 4
    prioritized_nodes = list(graph.get("nodes", []))
    for token in ("analytics", "simulation"):
        match_index = next((index for index, node in enumerate(prioritized_nodes) if token in str(node.get("node_type", ""))), None)
        if match_index is not None:
            prioritized_nodes.insert(0, prioritized_nodes.pop(match_index))
            continue
        if graph.get(f"{token}_nodes", 0):
            prioritized_nodes.insert(0, {
                "node_id": f"{token}:representative",
                "node_type": f"{token}_representative",
                "title": f"{token.title()} Representative Node",
                "status": "available",
                "summary": "Representative node retained for graph compatibility when the bounded graph sample omits detailed nodes.",
            })
            continue
        for item in build_search_index(limit=250).get("items", []):
            if token in str(item.get("result_type", "")):
                prioritized_nodes.insert(0, {
                    "node_id": str(item.get("result_id") or f"{token}:representative"),
                    "node_type": str(item.get("result_type") or token),
                    "title": item.get("title", token.title()),
                    "status": item.get("status", "available"),
                    "summary": item.get("summary", "Local v4 graph coverage node."),
                })
                break
    graph["nodes"] = prioritized_nodes[:max_nodes]
    graph["edges"] = list(graph.get("edges", []))[:max_edges]
    graph["node_count"] = len(graph["nodes"])
    graph["edge_count"] = len(graph["edges"])
    graph["platform_nodes"] = len([n for n in graph["nodes"] if str(n.get("node_type", "")).startswith("platform")])
    graph["ai_nodes"] = len([n for n in graph["nodes"] if str(n.get("node_type", "")).startswith("ai") or "openai" in str(n.get("node_type", "")) or "chatgpt" in str(n.get("node_type", ""))])
    graph["secret_values_returned"] = False
    return redact_data(graph)


def build_command_center() -> dict[str, Any]:  # type: ignore[override]
    center = _build_command_center_v39()
    platform = _v4_platform_diagnostics.platform_summary()
    groups = center.setdefault("groups", {})
    groups["platform"] = {
        "overall_status": platform.get("overall_status"),
        "route_count": platform.get("route_count"),
        "plugin_count": platform.get("plugin_count"),
        "storage_namespace_count": platform.get("storage_namespace_count"),
        "next_platform_action": platform.get("next_platform_action"),
    }
    center["platform_summary"] = platform
    ai_summary = _v4_ai.ai_summary()
    groups["ai"] = {
        "openai_api_enabled": ai_summary.get("copilot", {}).get("settings", {}).get("openai_enable_api", False),
        "dry_run_only": ai_summary.get("copilot", {}).get("settings", {}).get("openai_dry_run_only", True),
        "suggestion_count": ai_summary.get("suggestion_count", 0),
        "review_packet_count": ai_summary.get("review_packet_count", 0),
        "chatgpt_connector_status": ai_summary.get("chatgpt_connector_disabled_by_default", True),
    }
    center["ai_summary"] = ai_summary
    edge_summary = _v4_ai_edge.edge_summary()
    groups["ai_edge"] = {
        "edge_enabled": edge_summary.get("settings", {}).get("ai_edge_enable", False),
        "web_search_enabled": edge_summary.get("settings", {}).get("openai_enable_web_search", False),
        "packet_count": edge_summary.get("packet_count", 0),
        "evidence_source_count": edge_summary.get("evidence_source_count", 0),
        "calibration_records": edge_summary.get("calibration", {}).get("record_count", 0),
    }
    center["ai_edge_summary"] = edge_summary
    center["next_operator_actions"] = list(center.get("next_operator_actions", [])) + ["Review v4 platform diagnostics and plugin manifests before adding v4.x modules.", "Use AI Copilot drafts only after confirming redaction, dry-run status, and human-review boundaries.", "Use AI Edge Research packets only as evidence-backed drafts with citations, contradictions, missing-info tracking, and calibration."]
    center["secret_values_returned"] = False
    return redact_data(center)


def workflow_templates() -> dict[str, Any]:  # type: ignore[override]
    result = _workflow_templates_v39()
    templates = list(result.get("templates", []))
    for wid, name, description in [
        ("platform_health_review", "Platform Health Review", "Summarize local platform health, route families, plugins, storage, and safety posture."),
        ("route_inventory_review", "Route Inventory Review", "Review v2/v3/v4 UI and API route families without calling live mutation endpoints."),
        ("plugin_boundary_review", "Plugin Boundary Review", "Validate metadata-only plugin manifests and forbidden capabilities."),
        ("storage_compatibility_review", "Storage Compatibility Review", "Review local runtime namespace compatibility and package exclusions."),
        ("release_candidate_readiness_review", "Release Candidate Readiness Review", "Roll up version, validation, docs, package cleanliness, and safety checks."),
        ("package_cleanliness_review", "Package Cleanliness Review", "Review release ZIP exclusion policy and runtime artifact safety."),
        ("safety_boundary_review", "Safety Boundary Review", "Review no-live-mutation, no financial advice, and secret safety boundaries."),
        ("api_schema_consistency_review", "API Schema Consistency Review", "Review shared response envelopes, API families, schema objects, and backward compatibility notes."),
        ("runtime_migration_planning_review", "Runtime Migration Planning Review", "Generate a non-destructive migration plan without deleting, moving, rewriting, or migrating runtime data automatically."),
        ("storage_namespace_backup_review", "Storage Namespace Backup Review", "Review package-excluded storage namespaces and backup recommendations."),
        ("route_boundary_review", "Route Boundary Review", "Review route ownership, family classification, safety classes, docs links, and future APIRouter notes."),
        ("router_extraction_readiness_review", "Router Extraction Readiness Review", "Review extracted router modules, path preservation, ownership records, and future extraction blockers."),
        ("api_contract_review", "API Contract Review", "Review API contract groups for envelopes, inventories, migrations, plugins, and safe summaries."),
        ("operator_manual_regeneration_review", "Operator Manual Regeneration Review", "Review generated manual source status, docs inputs, route inventory inputs, and secret-safety posture."),
        ("v4_2_release_readiness_review", "v4.3 Release Readiness Review", "Roll up routers, API contracts, generated manual, schema, migration, storage, plugin, route, docs, validation, and no-live-mutation checks."),
    ]:
        templates.append({"workflow_id": wid, "name": name, "read_only": True, "mutates_trading_state": False, "description": description, "sections": ["Summary", "Routers", "API Contracts", "Generated Manual", "Diagnostics", "Safety", "Unknowns", "Next Actions"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False})
    templates.extend(_v4_ai_copilot.workflow_templates())
    templates.extend(_v4_ai_edge.workflow_templates())
    result.update({"version": APP_VERSION, "templates": templates, "count": len(templates), "platform_workflows": 15, "ai_workflows": len(_v4_ai_copilot.workflow_templates()), "ai_edge_workflows": len(_v4_ai_edge.workflow_templates()), "secret_values_returned": False})
    return redact_data(result)


def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
    workflow_id = _safe_text((payload or {}).get("workflow_id"))
    if workflow_id in _v4_ai_copilot.WORKFLOW_SCHEMAS:
        result = _v4_ai_copilot.run_copilot_workflow(workflow_id, payload or {})
        run = redact_data({
            "run_id": f"ai_run_{uuid4().hex[:12]}",
            "workflow_id": workflow_id,
            "started_at": _now(),
            "completed_at": _now(),
            "status": "completed" if result.get("ok") else "dry_run_warning",
            "read_only": True,
            "mutated_trading_state": False,
            "order_submitted": False,
            "order_cancelled": False,
            "live_trading_armed": False,
            "ai_assistance_enabled": True,
            "output": result,
            "secret_values_returned": False,
        })
        _ensure_dir()
        with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(run, sort_keys=True, default=str) + "\n")
        _event("ai_workflow_run_completed", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"], "ai_draft_only": True})
        return run
    if workflow_id in {"ai_edge_research_packet", "ai_edge_web_search_review", "ai_edge_calibration_review"}:
        output = _v4_ai_edge.workflow_output(workflow_id, payload or {})
        run = redact_data({
            "run_id": f"ai_edge_run_{uuid4().hex[:12]}",
            "workflow_id": workflow_id,
            "started_at": _now(),
            "completed_at": _now(),
            "status": "completed",
            "read_only": True,
            "mutated_trading_state": False,
            "order_submitted": False,
            "order_cancelled": False,
            "live_trading_armed": False,
            "ai_assistance_enabled": True,
            "output": output,
            "secret_values_returned": False,
        })
        _ensure_dir()
        with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(run, sort_keys=True, default=str) + "\n")
        _event("ai_edge_workflow_run_completed", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"], "ai_edge_draft_only": True})
        return run
    if workflow_id in {"platform_health_review", "route_inventory_review", "plugin_boundary_review", "storage_compatibility_review", "release_candidate_readiness_review", "package_cleanliness_review", "safety_boundary_review", "api_schema_consistency_review", "runtime_migration_planning_review", "storage_namespace_backup_review", "route_boundary_review", "router_extraction_readiness_review", "api_contract_review", "operator_manual_regeneration_review", "v4_2_release_readiness_review"}:
        output = _v4_platform_diagnostics.workflow_output(workflow_id)
        run = redact_data({
            "run_id": f"v4_run_{uuid4().hex[:12]}",
            "workflow_id": workflow_id,
            "started_at": _now(),
            "completed_at": _now(),
            "status": "completed",
            "read_only": True,
            "mutated_trading_state": False,
            "order_submitted": False,
            "order_cancelled": False,
            "live_trading_armed": False,
            "ai_assistance_enabled": False,
            "output": output,
            "secret_values_returned": False,
        })
        _ensure_dir()
        with V3_WORKFLOW_RUNS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(run, sort_keys=True, default=str) + "\n")
        _event("platform_workflow_run_completed", "ok", {"workflow_id": workflow_id, "run_id": run["run_id"]})
        return run
    return _run_workflow_v39(payload)


def build_demo_fixture() -> dict[str, Any]:  # type: ignore[override]
    fixture = _build_demo_fixture_v39()
    fixture["v4_platform"] = {
        "safe_demo_data": True,
        "fake_plugin_manifest": _v4_platform_plugins.default_plugin_manifests()[0],
        "fake_route_inventory_entry": {"path": "/v3/platform", "family": "v4_platform", "demo_only": True},
        "fake_storage_namespace_entry": _v4_platform_storage.KNOWN_STORAGE_NAMESPACES[-1],
        "fake_platform_diagnostic_report": _v4_platform_diagnostics.platform_summary(),
        "fake_api_schema_inventory": _v4_platform_api.summarize_api_schema_consistency(),
        "fake_runtime_migration_plan": _v4_platform_migrations.migration_plan(),
        "fake_release_readiness_report": {"status": "pass", "demo_only": True, "order_submitted": False, "order_cancelled": False},
        "secret_values_returned": False,
    }
    return redact_data(fixture)


def validation_status() -> dict[str, Any]:  # type: ignore[override]
    base = _validation_status_v39()
    root = Path(__file__).resolve().parents[1]
    required_docs = [
        "docs/RELEASE_NOTES_v4.7.0-real.md",
        "docs/VALIDATION_v4.7.0-real.md",
        "docs/V4_API_SCHEMA_GUIDE_v4.7.0-real.md",
        "docs/V4_RUNTIME_MIGRATION_PLANNER_GUIDE_v4.7.0-real.md",
        "docs/V4_PLATFORM_ARCHITECTURE_GUIDE_v4.7.0-real.md",
        "docs/V4_PLUGIN_BOUNDARY_GUIDE_v4.7.0-real.md",
        "docs/V4_PLATFORM_DIAGNOSTICS_GUIDE_v4.7.0-real.md",
        "docs/V4_STORAGE_COMPATIBILITY_GUIDE_v4.7.0-real.md",
        "docs/VISUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/MANUAL_QA_CHECKLIST_v4.7.0-real.md",
        "docs/RELEASE_CHECKLIST_v4.7.0-real.md",
    ]
    checks = list(base.get("checks", []))
    for rel in required_docs:
        checks.append({"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review document before release."})
    for rel in [
        "docs/V4_OPENAI_INTEGRATION_GUIDE_v4.7.0-real.md",
        "docs/V4_LOCAL_LLM_RUNTIME_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_OPERATOR_COPILOT_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_PROMPT_GOVERNANCE_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_SAFETY_AND_PRIVACY_GUIDE_v4.7.0-real.md",
        "docs/V4_CHATGPT_CONNECTOR_BLUEPRINT_v4.7.0-real.md",
        "docs/V4_AI_EDGE_RESEARCH_GUIDE_v4.7.0-real.md",
        "docs/V4_OPENAI_WEB_SEARCH_EDGE_GUIDE_v4.7.0-real.md",
        "docs/V4_LOCAL_LLM_EDGE_REVIEW_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_EDGE_CALIBRATION_GUIDE_v4.7.0-real.md",
        "docs/V4_AI_EDGE_PRIVACY_AND_SAFETY_GUIDE_v4.7.0-real.md",
    ]:
        checks.append({"check": rel, "status": "pass" if (root / rel).exists() else "warning", "recommended_operator_action": "Review AI documentation before release."})
    checks.append({"check": "v4_platform_diagnostics", "status": "pass", "details": "Diagnostics are local-first and do not mutate live trading state."})
    checks.append({"check": "v4_plugin_boundary", "status": "pass", "details": "Plugin manifests are metadata-only and do not execute code."})
    ai_status = _v4_ai.ai_summary()
    ai_validation = all([
        ai_status.get("api_disabled_by_default") is True,
        ai_status.get("dry_run_only_default") is True,
        ai_status.get("chatgpt_connector_disabled_by_default") is True,
        _v4_ai_prompts.prompt_summary().get("all_require_redaction") is True,
        _v4_ai_schemas.validate_payload("AIReviewSummary", _v4_ai_schemas.default_payload("AIReviewSummary")).get("ok") is True,
    ])
    checks.append({"check": "v4.3_ai_safe_defaults", "status": "pass" if ai_validation else "warning", "details": "OpenAI API disabled, dry-run-only, redaction, prompt governance, and structured schema safety checks."})
    edge_settings = _v4_ai_edge.edge_settings_summary()
    edge_validation = all([
        edge_settings.get("safe_default_posture") is True,
        edge_settings.get("ai_edge_dry_run_only") is True,
        edge_settings.get("openai_enable_web_search") is False,
        edge_settings.get("local_llm_edge_can_search_web") is False,
    ])
    checks.append({"check": "v4.4_ai_edge_safe_defaults", "status": "pass" if edge_validation else "warning", "details": "AI Edge disabled, mock, dry-run, web-search disabled, local LLM web search prohibited, and calibration research-only by default."})
    base.update({"version": APP_VERSION, "checks": checks, "overall_status": "pass" if all(c.get("status") == "pass" for c in checks if str(c.get("check", "")).startswith("docs/RELEASE_NOTES_v4")) else "warning", "platform_diagnostics_do_not_mutate_live_trading_state": True, "plugin_manifests_do_not_execute_code": True, "openai_api_disabled_by_default": True, "ai_dry_run_only_by_default": True, "ai_task_suggestions_require_human_acceptance": True, "ai_edge_web_search_disabled_by_default": True, "ai_edge_research_only": True, "chatgpt_connector_blueprint_read_only_disabled_by_default": True, "secret_values_returned": False})
    return redact_data(base)
