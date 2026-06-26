from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_VERSION, settings
from .feature_status import build_feature_status_map, build_stub_burndown_map
from . import ai_news_odds
from . import cross_market_arbitrage
from . import paper_automation
from .review_queue import list_review_queue_actions, list_review_queue_audit
from .opportunity_review import list_review_records, list_operator_notes


WORKSPACES: list[dict[str, str]] = [
    {
        "id": "command_center",
        "label": "Command Center",
        "route": "/v3",
        "short_label": "Command",
        "purpose": "What needs attention now: safety, readiness, paper automation, reviews, opportunities, and warnings.",
    },
    {
        "id": "opportunities",
        "label": "Opportunities",
        "route": "/v3/opportunities",
        "short_label": "Opportunities",
        "purpose": "Unified entry point for AI odds, edge review, arbitrage candidates, paper strategy signals, and watchlist/review items.",
    },
    {
        "id": "automation",
        "label": "Automation / Paper Trading",
        "route": "/v3/automation",
        "short_label": "Automation",
        "purpose": "Paper-only automation status, run-once controls, simulated fills, paper account, positions, and decision log.",
    },
    {
        "id": "review_audit",
        "label": "Review & Audit",
        "route": "/v3/review-audit",
        "short_label": "Review & Audit",
        "purpose": "Review queue actions, opportunity decisions, paper automation audit rows, settings changes, and safety events.",
    },
    {
        "id": "settings_system",
        "label": "Settings & System",
        "route": "/v3/settings-system",
        "short_label": "Settings",
        "purpose": "Feature readiness, settings, venues, OpenAI/AI status, paper limits, arbitrage config, diagnostics, and advanced links.",
    },
]


COMPATIBILITY_ROUTES: list[dict[str, str]] = [
    {"old_route": "/v3/ai/news-odds", "workspace": "Opportunities", "new_route": "/v3/opportunities", "behavior": "kept as source-specific page and linked from Opportunities"},
    {"old_route": "/v3/arbitrage", "workspace": "Opportunities", "new_route": "/v3/opportunities", "behavior": "kept as source-specific scanner/review page"},
    {"old_route": "/v3/paper-trading", "workspace": "Automation / Paper Trading", "new_route": "/v3/automation", "behavior": "kept as detailed paper trading page and embedded from Automation"},
    {"old_route": "/review-queue", "workspace": "Review & Audit", "new_route": "/v3/review-audit", "behavior": "kept as detailed review queue page"},
    {"old_route": "/v3/feature-readiness", "workspace": "Settings & System", "new_route": "/v3/settings-system", "behavior": "kept as detailed readiness review page"},
    {"old_route": "/v3/settings", "workspace": "Settings & System", "new_route": "/v3/settings-system", "behavior": "kept as detailed settings workflow"},
    {"old_route": "/v3/cockpit", "workspace": "Command Center", "new_route": "/v3", "behavior": "kept as advanced cockpit/direct workflow"},
    {"old_route": "/v3/workspace", "workspace": "Command Center", "new_route": "/v3", "behavior": "kept as advanced guided-workspace/direct workflow"},
    {"old_route": "/v2-live", "workspace": "Settings & System", "new_route": "/v3/settings-system", "behavior": "kept as gated live-control compatibility plane"},
]


ROUTE_SPRAWL_AUDIT: list[dict[str, str]] = [
    {"route_family": "/v3", "classification": "keep as primary workspace", "workspace": "Command Center", "operator_note": "Default landing page now summarizes next action instead of exposing every subsystem equally."},
    {"route_family": "/v3/opportunities, /v3/ai/news-odds, /v3/arbitrage", "classification": "embed/source-specific sections", "workspace": "Opportunities", "operator_note": "AI odds, edge review, and arbitrage remain source-specific, but are discoverable from one workspace."},
    {"route_family": "/v3/paper-trading", "classification": "embed/detail page", "workspace": "Automation / Paper Trading", "operator_note": "Paper-only automation remains detailed but is no longer a peer to every other top-level section."},
    {"route_family": "/review-queue, /audit, paper audit endpoints", "classification": "consolidate", "workspace": "Review & Audit", "operator_note": "Decisions and audit rows are gathered in one accountability workspace."},
    {"route_family": "/v3/settings, /v3/feature-readiness, /v3/platform", "classification": "consolidate with advanced tabs", "workspace": "Settings & System", "operator_note": "Readiness/config/diagnostics live together; low-level routes stay available through Advanced links."},
    {"route_family": "/v3/cockpit, /v3/workspace, /v3/tasks, /v3/datasets, /v3/freshness, /v3/simulation, /v3/analytics", "classification": "advanced/direct workflow", "workspace": "Command Center", "operator_note": "Kept for compatibility and deep work, but not promoted as primary navigation choices."},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tone(status: Any) -> str:
    text = str(status or "").lower()
    if any(token in text for token in ["error", "reject", "disabled", "blocked", "unavailable"]):
        return "danger" if "error" in text or "blocked" in text else "neutral"
    if any(token in text for token in ["partial", "config", "stale", "warning", "sample"]):
        return "warning"
    if any(token in text for token in ["working", "enabled", "ok", "complete", "live"]):
        return "ok"
    return "neutral"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _read_jsonl(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
        except json.JSONDecodeError:
            rows.append({"status": "invalid_json", "source": str(path.name)})
    return list(reversed(rows))[: max(1, min(int(limit or 100), 1000))]


def _feature_rows() -> list[dict[str, Any]]:
    return build_feature_status_map().get("items", [])


def _feature_by_id() -> dict[str, dict[str, Any]]:
    return {str(row.get("feature_id")): row for row in _feature_rows()}


def _feature_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def build_shell_status() -> dict[str, Any]:
    rows = _feature_rows()
    counts = _feature_counts(rows)
    paper_status = paper_automation.build_paper_status()
    last_run = paper_status.get("last_run") or {}
    openai_enabled = bool(getattr(settings, "openai_enable_api", False) or getattr(settings, "ai_enable", False))
    polymarket_enabled = bool(getattr(settings, "polymarket_data_public_fetch_enabled", False) or getattr(settings, "polymarket_live_mode", False) or getattr(settings, "live_trading_enabled", False))
    kalshi_enabled = bool(getattr(settings, "kalshi_enabled", False))
    warnings_count = counts.get("partial", 0) + counts.get("config_required", 0) + counts.get("scaffolded", 0) + counts.get("error", 0)
    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "read_only": bool(getattr(settings, "read_only", True)),
        "live_trading_enabled": bool(getattr(settings, "live_trading_enabled", False)),
        "live_armed": bool(getattr(settings, "polymarket_live_mode", False)),
        "kill_switch": bool(getattr(settings, "polymarket_live_kill_switch", True)),
        "paper_trading_status": paper_status.get("status", "unknown"),
        "paper_automation_status": paper_status.get("automation_status", "unknown"),
        "paper_equity": _safe_float((paper_status.get("account") or {}).get("equity"), 0.0),
        "paper_unrealized_pnl": _safe_float((paper_status.get("account") or {}).get("unrealized_pnl"), 0.0),
        "paper_open_positions": int(paper_status.get("open_position_count") or 0),
        "last_automation_run_id": str(last_run.get("run_id") or "none"),
        "last_automation_status": str(last_run.get("status") or "not_run"),
        "feature_counts": counts,
        "warnings_count": warnings_count,
        "openai_status": "enabled" if openai_enabled else "disabled",
        "polymarket_status": "configured_or_local" if polymarket_enabled else "local_only_or_disabled",
        "kalshi_status": "enabled" if kalshi_enabled else "disabled_or_config_required",
        "arbitrage_status": "enabled" if bool(getattr(settings, "arbitrage_scanner_enabled", False)) else "disabled_review_fixture_mode",
        "safety_posture": "review-first; no real trading enabled by Operator OS consolidation",
        "paper_only": True,
        "live_execution_used": False,
        "order_submitted": False,
        "order_cancelled": False,
        "secret_values_returned": False,
    }


def build_command_center() -> dict[str, Any]:
    shell = build_shell_status()
    ai_summary = ai_news_odds.summarize_news_odds()
    ai_adjustments = ai_news_odds.list_adjustments(limit=20).get("items", [])
    review_actions = list_review_queue_actions(limit=50)
    paper_status = paper_automation.build_paper_status()
    feature_rows = _feature_rows()
    config_required = [row for row in feature_rows if row.get("status") in {"config_required", "partial", "scaffolded", "error"}]
    next_action = "Review system readiness and run a paper strategy cycle only if paper gates are enabled."
    if shell["warnings_count"]:
        next_action = "Open Settings & System to clear config-required, partial, scaffolded, or error statuses."
    if int(paper_status.get("open_position_count") or 0) > 0:
        next_action = "Open Automation to inspect paper positions, decisions, and simulated P/L."
    if review_actions:
        next_action = "Open Review & Audit to inspect the latest local operator decisions."
    return {
        "shell_status": shell,
        "cards": [
            {"label": "Safety posture", "value": "Live disabled" if not shell["live_armed"] else "Live armed", "tone": "ok" if not shell["live_armed"] else "danger", "route": "/v3/settings-system", "detail": "Operator OS consolidation does not enable real order placement."},
            {"label": "Feature warnings", "value": shell["warnings_count"], "tone": "warning" if shell["warnings_count"] else "ok", "route": "/v3/settings-system", "detail": "Partial, config-required, scaffolded, or error statuses."},
            {"label": "Paper automation", "value": shell["paper_automation_status"], "tone": _tone(shell["paper_automation_status"]), "route": "/v3/automation", "detail": f"Last run: {shell['last_automation_status']}"},
            {"label": "Open positions", "value": shell["paper_open_positions"], "tone": "warning" if shell["paper_open_positions"] else "neutral", "route": "/v3/automation", "detail": f"Paper equity: ${shell['paper_equity']:,.2f}"},
            {"label": "Pending review actions", "value": len(review_actions), "tone": "warning" if review_actions else "neutral", "route": "/v3/review-audit", "detail": "Local review queue and decision events."},
            {"label": "AI odds adjustments", "value": len(ai_adjustments), "tone": "info" if ai_adjustments else "neutral", "route": "/v3/opportunities", "detail": str(ai_summary.get("operator_implication") or "AI odds review is source-specific and review-only.")},
        ],
        "next_action": next_action,
        "config_required_rows": config_required[:12],
        "route_audit": ROUTE_SPRAWL_AUDIT,
    }


def _opportunity_from_adjustment(row: dict[str, Any]) -> dict[str, Any]:
    market = row.get("market") if isinstance(row.get("market"), dict) else {}
    recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    return {
        "id": row.get("adjustment_id") or row.get("id") or "ai_news_odds_adjustment",
        "source": "AI Odds",
        "market": row.get("market_title") or market.get("title") or row.get("title") or "AI odds adjustment",
        "side": recommendation.get("recommended_side") or row.get("recommended_side") or "NEEDS REVIEW",
        "price": row.get("market_price") or recommendation.get("market_price") or "unavailable",
        "model_fair_price": row.get("base_fair_yes") or row.get("model_fair_yes") or "unavailable",
        "ai_adjusted_fair_price": row.get("adjusted_fair_yes") or row.get("final_adjusted_fair_yes") or "unavailable",
        "edge": row.get("edge_after_adjustment_pp") or row.get("final_edge_pp") or "unavailable",
        "confidence": row.get("confidence") or row.get("final_confidence") or "unknown",
        "net_margin": "n/a",
        "status": row.get("operator_action") or row.get("status") or "review_only",
        "data_freshness": row.get("data_state") or "cached",
        "recommended_action": "review evidence and cap explanation",
        "posture": "review-only / no order placement",
        "detail_route": f"/v3/ai/news-odds/adjustments/{row.get('adjustment_id')}" if row.get("adjustment_id") else "/v3/ai/news-odds",
    }


def _opportunity_from_paper_decision(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("decision_id") or row.get("signal_id") or "paper_decision",
        "source": "Paper Strategy",
        "market": row.get("market_title") or row.get("market_id") or "Paper strategy decision",
        "side": row.get("side") or "UNKNOWN",
        "price": row.get("price") or row.get("ask_price") or "unavailable",
        "model_fair_price": row.get("model_probability") or "unavailable",
        "ai_adjusted_fair_price": row.get("ai_adjusted_probability") or "unavailable",
        "edge": row.get("edge_pct") or "unavailable",
        "confidence": row.get("confidence") or "unknown",
        "net_margin": "n/a",
        "status": row.get("final_action") or "decision_logged",
        "data_freshness": row.get("data_state") or "cached",
        "recommended_action": row.get("reason") or "inspect paper decision log",
        "posture": "paper-only / live_execution_used=false",
        "detail_route": "/v3/automation",
    }


def _opportunity_from_review_action(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("action_record_id") or row.get("decision_id") or row.get("market_id") or "review_action",
        "source": "Review Queue",
        "market": row.get("market_title") or row.get("market_id") or "Review item",
        "side": "NEEDS REVIEW",
        "price": "unavailable",
        "model_fair_price": "unavailable",
        "ai_adjusted_fair_price": "unavailable",
        "edge": "unavailable",
        "confidence": "operator",
        "net_margin": "n/a",
        "status": row.get("new_state") or row.get("review_status") or row.get("action") or "review_recorded",
        "data_freshness": row.get("data_state") or "cached",
        "recommended_action": row.get("reason") or "continue local review workflow",
        "posture": "review-only / no live mutation",
        "detail_route": "/v3/review-audit",
    }


def build_opportunities() -> dict[str, Any]:
    adjustments = ai_news_odds.list_adjustments(limit=25).get("items", [])
    decisions = paper_automation.list_paper_decisions(limit=25).get("items", [])
    review_actions = list_review_queue_actions(limit=25)
    rows: list[dict[str, Any]] = []
    rows.extend(_opportunity_from_adjustment(row) for row in adjustments[:12])
    rows.extend(_opportunity_from_paper_decision(row) for row in decisions[:12])
    rows.extend(_opportunity_from_review_action(row) for row in review_actions[:12])
    source_sections = [
        {"source": "AI Odds", "count": len(adjustments), "route": "/v3/ai/news-odds", "state": "cached" if adjustments else "empty", "note": "Review-only AI adjustment records with raw/weighted/final probability context when present."},
        {"source": "Cross-Market Arbitrage", "count": 0, "route": "/v3/arbitrage", "state": "source-specific", "note": "Open the source page to run or record a scan; default scans are sample/review unless venues are enabled."},
        {"source": "Paper Strategy", "count": len(decisions), "route": "/v3/automation", "state": "cached" if decisions else "empty", "note": "Automated paper decisions and simulated trades only."},
        {"source": "Review Queue", "count": len(review_actions), "route": "/v3/review-audit", "state": "cached" if review_actions else "empty", "note": "Local review actions and watchlist/paper-review decisions."},
    ]
    return {
        "rows": rows[:50],
        "count": len(rows[:50]),
        "source_sections": source_sections,
        "empty_state": "No unified opportunity rows have been written yet. Use source sections to open AI Odds, Arbitrage, Review Queue, or Paper Automation." if not rows else "",
        "review_only": True,
        "paper_only": True,
        "live_disabled": True,
    }


def build_automation() -> dict[str, Any]:
    status = paper_automation.build_paper_status()
    return {
        "status": status,
        "config": status.get("config") or {},
        "account": status.get("account") or {},
        "positions": status.get("positions") or [],
        "recent_orders": status.get("recent_orders") or [],
        "recent_fills": status.get("recent_fills") or [],
        "recent_decisions": status.get("recent_decisions") or [],
        "last_run": status.get("last_run") or {},
        "api_routes": [
            "/api/v3/paper/status",
            "/api/v3/paper/account",
            "/api/v3/paper/orders",
            "/api/v3/paper/fills",
            "/api/v3/paper/positions",
            "/api/v3/paper/decisions",
            "/api/v3/paper/runs",
        ],
    }


def build_review_audit() -> dict[str, Any]:
    review_actions = list_review_queue_actions(limit=100)
    review_audit = list_review_queue_audit(limit=100)
    paper_audit = paper_automation.list_paper_audit(limit=100).get("items", [])
    paper_decisions = paper_automation.list_paper_decisions(limit=100).get("items", [])
    opportunity_records = list_review_records(limit=100).get("items", [])
    notes = list_operator_notes(limit=50).get("items", [])
    events: list[dict[str, Any]] = []
    for row in review_actions:
        events.append({"source": "Review Queue", "timestamp": row.get("updated_at") or row.get("created_at"), "action": row.get("action"), "target": row.get("market_title") or row.get("market_id"), "status": row.get("new_state"), "detail": row.get("reason"), "posture": "review-only"})
    for row in review_audit:
        events.append({"source": "Review Audit", "timestamp": row.get("at") or row.get("timestamp"), "action": row.get("action"), "target": row.get("target_name") or row.get("target_id"), "status": row.get("new_state"), "detail": row.get("reason"), "posture": "review-only"})
    for row in paper_audit:
        events.append({"source": "Paper Audit", "timestamp": row.get("timestamp"), "action": row.get("action_type") or row.get("action"), "target": row.get("market_title") or row.get("market_id") or row.get("run_id"), "status": row.get("status"), "detail": row.get("reason") or row.get("message"), "posture": "paper-only"})
    for row in opportunity_records[:25]:
        events.append({"source": "Opportunity Review", "timestamp": row.get("updated_at") or row.get("created_at"), "action": row.get("last_action") or row.get("review_status"), "target": row.get("market_title") or row.get("market_id"), "status": row.get("review_status"), "detail": row.get("reason") or row.get("operator_notes"), "posture": "review-only"})
    events.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return {
        "pending_review_count": sum(1 for row in opportunity_records if str(row.get("review_status") or "").upper() in {"UNREVIEWED", "WATCHING", "NEEDS_MORE_EVIDENCE", "PAPER_REVIEW"}),
        "review_action_count": len(review_actions),
        "paper_decision_count": len(paper_decisions),
        "paper_audit_count": len(paper_audit),
        "opportunity_review_count": len(opportunity_records),
        "notes_count": len(notes),
        "events": events[:100],
        "empty_state": "No review or audit events have been written yet." if not events else "",
        "review_only": True,
        "live_disabled": True,
    }


def build_settings_system() -> dict[str, Any]:
    feature_status = build_feature_status_map()
    stub = build_stub_burndown_map()
    rows = feature_status.get("items", [])
    feature_by_id = {str(row.get("feature_id")): row for row in rows}
    important_ids = [
        "paper_trading.engine", "paper_trading.automation", "paper_trading.scheduler", "paper_trading.broker_ledger_risk",
        "ai.news_odds", "ai.edge_research", "arbitrage.scanner", "arbitrage.kalshi_adapter", "venues.kalshi",
        "features.readiness_review_page", "settings.v3_operator_preferences", "live.execution_controls",
    ]
    important = [feature_by_id[key] for key in important_ids if key in feature_by_id]
    return {
        "feature_status": feature_status,
        "stub_burndown": stub,
        "important_rows": important,
        "counts": feature_status.get("counts") or _feature_counts(rows),
        "ai": {
            "enabled": bool(getattr(settings, "ai_enable", False)),
            "provider": getattr(settings, "ai_provider", "mock"),
            "openai_api_enabled": bool(getattr(settings, "openai_enable_api", False)),
            "web_search_enabled": bool(getattr(settings, "openai_enable_web_search", False)),
            "secret_values_returned": False,
        },
        "venues": {
            "polymarket": "local/read-only unless network flags are enabled",
            "kalshi_enabled": bool(getattr(settings, "kalshi_enabled", False)),
            "kalshi_api_key_configured": bool(getattr(settings, "kalshi_api_key_id", None)),
            "secret_values_returned": False,
        },
        "arbitrage": cross_market_arbitrage.arbitrage_settings_summary(),
        "paper": paper_automation.get_paper_config().to_dict(),
        "advanced_links": [
            {"label": "Detailed v3 settings", "href": "/v3/settings"},
            {"label": "Feature readiness review", "href": "/v3/feature-readiness"},
            {"label": "Platform diagnostics", "href": "/v3/platform"},
            {"label": "System route map", "href": "/system-map"},
            {"label": "Legacy configuration console", "href": "/settings/configuration"},
            {"label": "Live v2 gated controls", "href": "/v2-live"},
        ],
    }


def build_workspace_context(workspace: str) -> dict[str, Any]:
    active = workspace if workspace in {row["id"] for row in WORKSPACES} else "command_center"
    context: dict[str, Any] = {
        "version": APP_VERSION,
        "generated_at": _now(),
        "active_workspace": active,
        "workspaces": WORKSPACES,
        "shell_status": build_shell_status(),
        "compatibility_routes": COMPATIBILITY_ROUTES,
        "route_sprawl_audit": ROUTE_SPRAWL_AUDIT,
        "workspace_title": next(row["label"] for row in WORKSPACES if row["id"] == active),
        "paper_only": True,
        "live_execution_used": False,
        "order_submitted": False,
        "order_cancelled": False,
        "secret_values_returned": False,
    }
    context["command_center"] = build_command_center() if active == "command_center" else {}
    context["opportunities_workspace"] = build_opportunities() if active == "opportunities" else {}
    context["automation_workspace"] = build_automation() if active == "automation" else {}
    context["review_audit_workspace"] = build_review_audit() if active == "review_audit" else {}
    context["settings_system_workspace"] = build_settings_system() if active == "settings_system" else {}
    return context
