from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import APP_VERSION, APP_VERSION_SHORT, settings


NAV_SECTIONS: list[dict[str, Any]] = [
    {
        "label": "Overview",
        "items": [
            {"label": "Dashboard", "href": "/", "match": ["/"]},
            {"label": "Workflow map", "href": "/workflow", "match": ["/workflow"]},
            {"label": "Operator brief", "href": "/operator", "match": ["/operator"]},
        ],
    },
    {
        "label": "Research",
        "items": [
            {"label": "Opportunities", "href": "/opportunities", "match": ["/opportunities"]},
            {"label": "Readiness", "href": "/readiness", "match": ["/readiness"]},
            {"label": "Playbooks", "href": "/playbooks", "match": ["/playbooks"]},
            {"label": "Sources", "href": "/research/sources", "match": ["/research/sources"]},
            {"label": "Evidence", "href": "/research/evidence", "match": ["/research/evidence", "/evidence-workbench"]},
        ],
    },
    {
        "label": "Market Data",
        "items": [
            {"label": "Snapshots", "href": "/market-data", "match": ["/market-data", "/market-data/snapshots"]},
            {"label": "Execution quality", "href": "/execution-quality", "match": ["/execution-quality"]},
        ],
    },
    {
        "label": "Paper Workflow",
        "items": [
            {"label": "Tickets", "href": "/trade-tickets", "match": ["/trade-tickets"]},
            {"label": "Approvals", "href": "/approvals", "match": ["/approvals"]},
            {"label": "Preflight", "href": "/preflight", "match": ["/preflight"]},
            {"label": "Execution queue", "href": "/execution-queue", "match": ["/execution-queue"]},
            {"label": "Positions", "href": "/positions", "match": ["/positions"]},
            {"label": "Exit tickets", "href": "/exit-tickets", "match": ["/exit-tickets"]},
            {"label": "Settlements", "href": "/settlements", "match": ["/settlements"]},
        ],
    },
    {
        "label": "Risk / Ops",
        "items": [
            {"label": "Risk budget", "href": "/risk-budget", "match": ["/risk-budget"]},
            {"label": "Runbook", "href": "/runbook", "match": ["/runbook"]},
            {"label": "Briefing", "href": "/paper-ops-briefing", "match": ["/paper-ops-briefing"]},
            {"label": "Aging", "href": "/paper-ops-aging", "match": ["/paper-ops-aging"]},
            {"label": "Handoffs", "href": "/paper-handoffs", "match": ["/paper-handoffs", "/paper-handoff-reconciliation"]},
            {"label": "Escalations", "href": "/paper-ops-escalations", "match": ["/paper-ops-escalations", "/paper-ops-escalation-review"]},
            {"label": "Closeout", "href": "/paper-ops-closeout", "match": ["/paper-ops-closeout"]},
        ],
    },
    {
        "label": "Live Ops",
        "items": [
            {"label": "Live config", "href": "/live-config", "match": ["/live-config"]},
            {"label": "Intents", "href": "/live-order-intents", "match": ["/live-order-intents"]},
            {"label": "Live preflight", "href": "/live-order-intent-preflight", "match": ["/live-order-intent-preflight"]},
            {"label": "Authorizations", "href": "/live-order-authorizations", "match": ["/live-order-authorizations"]},
            {"label": "Packets", "href": "/live-execution-packets", "match": ["/live-execution-packets"]},
            {"label": "Dry-run", "href": "/live-dry-run-adapter", "match": ["/live-dry-run-adapter", "/live-dry-run-review"]},
            {"label": "Adapter", "href": "/live-adapter", "match": ["/live-adapter", "/live-adapter-requests"]},
            {"label": "CLOB boundary", "href": "/live-clob-adapter", "match": ["/live-clob-adapter"]},
        ],
    },
    {
        "label": "Live v2 Console",
        "items": [
            {"label": "Dashboard", "href": "/v2-live", "match": ["/v2-live"]},
            {"label": "Markets", "href": "/v2-live/markets", "match": ["/v2-live/markets", "/v2-live/market-data"]},
            {"label": "Trade Ticket", "href": "/v2-live/trade-ticket", "match": ["/v2-live/trade-ticket"]},
            {"label": "Orders", "href": "/v2-live/orders", "match": ["/v2-live/orders"]},
            {"label": "Positions", "href": "/v2-live/positions", "match": ["/v2-live/positions"]},
            {"label": "Risk", "href": "/v2-live/risk", "match": ["/v2-live/risk", "/v2-live/readiness"]},
            {"label": "Audit", "href": "/v2-live/audit", "match": ["/v2-live/audit"]},
            {"label": "Settings", "href": "/v2-live/settings", "match": ["/v2-live/settings"]},
            {"label": "Emergency", "href": "/v2-live/emergency", "match": ["/v2-live/emergency"]},
            {"label": "Docs", "href": "/v2-live/docs", "match": ["/v2-live/docs"]},
        ],
    },
    {
        "label": "Manual Control",
        "items": [
            {"label": "Manual review", "href": "/manual-execution-boundary", "match": ["/manual-execution-boundary"]},
            {"label": "Manual submit", "href": "/live-manual-execution", "match": ["/live-manual-execution"]},
            {"label": "Attempts", "href": "/live-execution-attempts", "match": ["/live-execution-attempts"]},
            {"label": "Manual cancel", "href": "/live-manual-cancel", "match": ["/live-manual-cancel"]},
            {"label": "Live trading", "href": "/live-trading", "match": ["/live-trading"]},
            {"label": "Live orders", "href": "/live-orders", "match": ["/live-orders"]},
            {"label": "Reconciliation", "href": "/live-reconciliation", "match": ["/live-reconciliation"]},
            {"label": "Operator runbook", "href": "/operator-runbook", "match": ["/operator-runbook"]},
        ],
    },
    {
        "label": "Data System",
        "items": [
            {"label": "Data overview", "href": "/data", "match": ["/data"]},
            {"label": "Sources", "href": "/data/sources", "match": ["/data/sources"]},
            {"label": "Ingestion", "href": "/data/ingestion", "match": ["/data/ingestion"]},
            {"label": "Internet sources", "href": "/data/internet-sources", "match": ["/data/internet-sources"]},
            {"label": "Internet workflow", "href": "/data/internet-workflow", "match": ["/data/internet-workflow"]},
            {"label": "Raw snapshots", "href": "/data/snapshots", "match": ["/data/snapshots"]},
            {"label": "Normalized", "href": "/data/normalized", "match": ["/data/normalized"]},
            {"label": "Labels", "href": "/data/labels", "match": ["/data/labels"]},
        ],
    },
    {
        "label": "Training Lab",
        "items": [
            {"label": "Training overview", "href": "/training", "match": ["/training"]},
            {"label": "Datasets", "href": "/training/datasets", "match": ["/training/datasets"]},
            {"label": "Dataset builder", "href": "/training/dataset-builder", "match": ["/training/dataset-builder"]},
            {"label": "Features", "href": "/training/features", "match": ["/training/features"]},
            {"label": "Training runs", "href": "/training/runs", "match": ["/training/runs"]},
            {"label": "Host jobs", "href": "/training/host-jobs", "match": ["/training/host-jobs"]},
            {"label": "Models", "href": "/training/models", "match": ["/training/models"]},
            {"label": "Backtests", "href": "/training/backtests", "match": ["/training/backtests"]},
            {"label": "Generated signals", "href": "/training/signals", "match": ["/training/signals"]},
        ],
    },
    {
        "label": "Research & Strategy",
        "items": [
            {"label": "Strategy signals", "href": "/strategy-signals", "match": ["/strategy-signals"]},
            {"label": "Autonomous status", "href": "/autonomous-trading", "match": ["/autonomous-trading"]},
            {"label": "Autonomous runs", "href": "/autonomous-runs", "match": ["/autonomous-runs"]},
        ],
    },
    {
        "label": "Audit / Reports",
        "items": [
            {"label": "Audit ledger", "href": "/audit", "match": ["/audit"]},
            {"label": "Review report", "href": "/review-report", "match": ["/review-report"]},
            {"label": "Playbook performance", "href": "/playbook-performance", "match": ["/playbook-performance"]},
            {"label": "UI system", "href": "/ui-system", "match": ["/ui-system"]},
        ],
    },
    {
        "label": "Settings",
        "items": [
            {"label": "Settings hub", "href": "/settings", "match": ["/settings"]},
            {"label": "Configuration console", "href": "/settings/configuration", "match": ["/settings/configuration", "/setup/environment"]},
            {"label": "Setup wizard", "href": "/setup/wizard", "match": ["/setup/wizard"]},
            {"label": "Runtime status", "href": "/setup/status", "match": ["/setup/status"]},
            {"label": "Deployment", "href": "/administration/config", "match": ["/administration/config"]},
            {"label": "Maintenance", "href": "/administration/maintenance", "match": ["/administration/maintenance"]},
            {"label": "Users", "href": "/users", "match": ["/users"]},
        ],
    },
]


STATUS_TONES = {
    "clear": "ok",
    "ok": "ok",
    "ready": "ok",
    "ready_for_review": "info",
    "review": "info",
    "needs_review": "warning",
    "warning": "warning",
    "blocked": "danger",
    "critical": "danger",
    "inactive": "neutral",
    "live_disabled": "neutral",
    "fake_local": "info",
}


def build_global_safety_badges() -> list[dict[str, str]]:
    """Return compact UI-only safety labels. This performs no network or trading work."""
    return [
        {
            "label": "LIVE ENABLED" if settings.polymarket_live_mode else "LIVE DISABLED",
            "tone": "danger" if settings.polymarket_live_mode else "neutral",
            "detail": "Manual live trading config flag",
        },
        {
            "label": "REAL NETWORK ENABLED" if settings.polymarket_live_allow_real_network else "REAL NETWORK DISABLED",
            "tone": "danger" if settings.polymarket_live_allow_real_network else "neutral",
            "detail": "Live adapter network permission",
        },
        {
            "label": "KILL SWITCH ACTIVE" if settings.polymarket_live_kill_switch else "KILL SWITCH OFF",
            "tone": "ok" if settings.polymarket_live_kill_switch else "danger",
            "detail": "Live execution kill switch",
        },
        {
            "label": "SUBMIT ENABLED" if settings.polymarket_live_enable_submit else "SUBMIT DISABLED",
            "tone": "danger" if settings.polymarket_live_enable_submit else "neutral",
            "detail": "Real submit gate",
        },
        {
            "label": "CANCEL ENABLED" if settings.polymarket_live_enable_cancel else "CANCEL DISABLED",
            "tone": "warning" if settings.polymarket_live_enable_cancel else "neutral",
            "detail": "Real cancel gate",
        },
        {
            "label": "AUTONOMOUS ENABLED" if settings.polymarket_live_enable_autonomous else "AUTONOMOUS OFF",
            "tone": "danger" if settings.polymarket_live_enable_autonomous else "neutral",
            "detail": "Autonomous live gate",
        },
        {
            "label": "FAKE ADAPTER ON" if settings.polymarket_live_fake_adapter_enabled else "FAKE ADAPTER OFF",
            "tone": "info" if settings.polymarket_live_fake_adapter_enabled else "neutral",
            "detail": "Local fake adapter simulation",
        },
        {
            "label": "DATA INTERNET ENABLED" if __import__("os").getenv("POLYMARKET_DATA_ALLOW_INTERNET", "false").lower() in {"1", "true", "yes", "on"} else "DATA INGESTION LOCAL ONLY",
            "tone": "warning" if __import__("os").getenv("POLYMARKET_DATA_ALLOW_INTERNET", "false").lower() in {"1", "true", "yes", "on"} else "local",
            "detail": "Data ingestion network permission",
        },
    ]


def build_quick_actions() -> list[dict[str, str]]:
    return [
        {"label": "Dashboard", "href": "/", "tone": "neutral"},
        {"label": "Live v2 Console", "href": "/v2-live", "tone": "danger"},
        {"label": "Kill Switch", "href": "/v2-live/emergency", "tone": "warning"},
        {"label": "Training Lab", "href": "/training", "tone": "info"},
        {"label": "Data Lab", "href": "/data", "tone": "local"},
        {"label": "Runbook", "href": "/operator-runbook", "tone": "ok"},
    ]


def console_globals() -> dict[str, Any]:
    return {
        "app_version": APP_VERSION,
        "app_version_short": APP_VERSION_SHORT,
        "nav_sections": NAV_SECTIONS,
        "app_safety_posture": "Mobile-friendly local-first operator console. v2.1.0 adds a decluttered, faster live-trading operator console with live data reads, trade-ticket preview, approval gates, risk checks, CLOB submit/cancel boundaries, positions, reconciliation, emergency controls, and audit exports while preserving fail-closed defaults and operator-only execution gates.",
        "global_safety_badges": build_global_safety_badges(),
        "quick_actions": build_quick_actions(),
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def status_tone(status: Any) -> str:
    text = str(status or "").lower().replace(" ", "_").replace("-", "_")
    if "kill" in text or "block" in text or "critical" in text or "reject" in text:
        return "danger"
    if "warn" in text or "stale" in text or "needs" in text or "action" in text:
        return "warning"
    if "ready" in text or "clear" in text or "approved" in text or "validated" in text:
        return "ok"
    if "fake" in text or "review" in text:
        return "info"
    return STATUS_TONES.get(text, "neutral")


def compact_id(value: Any, size: int = 12) -> str:
    text = str(value or "")
    if len(text) <= size + 3:
        return text
    return f"{text[:size]}..."


def _stage(
    *,
    group: str,
    title: str,
    description: str,
    href: str,
    mode: str,
    status: str,
    metric: str,
    next_href: str = "",
    api_href: str = "",
    warnings: int = 0,
    blockers: int = 0,
) -> dict[str, Any]:
    return {
        "group": group,
        "title": title,
        "description": description,
        "href": href,
        "mode": mode,
        "status": status,
        "tone": status_tone("blocked" if blockers else "warning" if warnings else status),
        "metric": metric,
        "next_href": next_href,
        "api_href": api_href,
        "warnings": warnings,
        "blockers": blockers,
    }


def build_workflow_map() -> dict[str, Any]:
    from .paper_audit import build_audit_events, summarize_audit
    from .paper_approvals import build_execution_approval_board
    from .paper_execution_queue import build_execution_queue
    from .paper_ops_closeout import build_paper_ops_closeout
    from .paper_playbooks import list_playbook_decisions, summarize_playbook_decisions
    from .paper_preflight import build_preflight_board
    from .trade_tickets import summarize_trade_tickets
    from .live_adapter import build_live_adapter_request_board, build_manual_execution_review_board
    from .live_config import build_live_config_readiness
    from .live_dry_run_adapter import build_live_dry_run_board
    from .live_execution_control import build_live_execution_attempt_board, build_live_execution_control_readiness
    from .live_execution_packets import build_live_execution_packet_board
    from .live_order_authorizations import build_live_order_authorization_board
    from .live_order_intents import build_live_order_intent_board
    from .live_order_preflight import build_live_order_preflight_board
    from .market_data import summarize_execution_quality, summarize_market_data

    ticket_summary = summarize_trade_tickets()
    playbook_summary = summarize_playbook_decisions(list_playbook_decisions(limit=10000))
    preflight_summary = build_preflight_board(limit=200).get("summary", {})
    approval_summary = build_execution_approval_board(limit=200).get("summary", {})
    execution_summary = build_execution_queue(limit=200).get("summary", {})
    closeout_summary = build_paper_ops_closeout(limit=200).get("summary", {})
    audit_summary = summarize_audit(build_audit_events(limit=1000))
    market_data_summary = summarize_market_data()
    execution_quality_summary = summarize_execution_quality()
    live_config_summary = build_live_config_readiness().get("summary", {})
    live_intent_summary = build_live_order_intent_board(limit=200).get("summary", {})
    live_preflight_summary = build_live_order_preflight_board(limit=200).get("summary", {})
    auth_summary = build_live_order_authorization_board(limit=200).get("summary", {})
    packet_summary = build_live_execution_packet_board(limit=200).get("summary", {})
    dry_run_summary = build_live_dry_run_board(limit=200).get("summary", {})
    adapter_request_summary = build_live_adapter_request_board(limit=200).get("summary", {})
    manual_review_summary = build_manual_execution_review_board(limit=200).get("summary", {})
    live_control = build_live_execution_control_readiness()
    attempt_summary = build_live_execution_attempt_board(limit=200).get("summary", {})

    stages = [
        _stage(
            group="Research",
            title="Market Research",
            description="Scan Polymarket markets, gather sources, and save notes before any paper workflow.",
            href="/",
            mode="LOCAL",
            status="ready_for_review",
            metric="Dashboard scan ready",
            next_href="/readiness",
            api_href="/api/markets",
        ),
        _stage(
            group="Research",
            title="Readiness",
            description="Rank market readiness and identify evidence, liquidity, and risk gaps.",
            href="/readiness",
            mode="PAPER ONLY",
            status="ready_for_review",
            metric="Review board",
            next_href="/playbooks",
        ),
        _stage(
            group="Research",
            title="Playbook",
            description="Classify candidate markets with deterministic local playbooks.",
            href="/playbooks",
            mode="PAPER ONLY",
            status="review" if safe_int(playbook_summary.get("count")) else "inactive",
            metric=f"{safe_int(playbook_summary.get('count'))} decisions",
            next_href="/trade-tickets",
            api_href="/api/playbooks/board",
        ),
        _stage(
            group="Market Data",
            title="Market Snapshot",
            description="Record local public/fixture order-book snapshots and compute spread, midpoint, depth, and freshness.",
            href="/market-data",
            mode="LOCAL",
            status="blocked" if safe_int(market_data_summary.get("closed")) or safe_int(market_data_summary.get("not_accepting_orders")) else "warning" if safe_int(market_data_summary.get("stale")) or safe_int(market_data_summary.get("wide_spread")) else "ready_for_review" if safe_int(market_data_summary.get("count")) else "inactive",
            metric=f"{safe_int(market_data_summary.get('count'))} snapshots",
            next_href="/execution-quality",
            api_href="/api/market-data/snapshots",
            warnings=safe_int(market_data_summary.get("stale")) + safe_int(market_data_summary.get("wide_spread")),
            blockers=safe_int(market_data_summary.get("closed")) + safe_int(market_data_summary.get("not_accepting_orders")) + safe_int(market_data_summary.get("invalid_book")),
        ),
        _stage(
            group="Market Data",
            title="Execution Quality",
            description="Estimate fill quantity, average fill, spread, slippage, stale data, and depth blockers before manual review.",
            href="/execution-quality",
            mode="LOCAL SIMULATION",
            status="blocked" if safe_int(execution_quality_summary.get("blocked_total")) else "ready_for_review" if safe_int(execution_quality_summary.get("count")) else "inactive",
            metric=f"{safe_int(execution_quality_summary.get('count'))} simulations",
            next_href="/preflight",
            api_href="/api/execution-quality",
            blockers=safe_int(execution_quality_summary.get("blocked_total")),
        ),
        _stage(
            group="Paper Workflow",
            title="Paper Ticket",
            description="Create human-reviewed paper entry tickets from readiness candidates.",
            href="/trade-tickets",
            mode="PAPER ONLY",
            status="blocked" if safe_int(ticket_summary.get("blocked")) else "ready_for_review" if safe_int(ticket_summary.get("count")) else "inactive",
            metric=f"{safe_int(ticket_summary.get('count'))} tickets",
            next_href="/approvals",
            api_href="/api/trade-tickets",
            blockers=safe_int(ticket_summary.get("blocked")),
        ),
        _stage(
            group="Paper Workflow",
            title="Paper Approval",
            description="Record approve/block/reject decisions before simulated paper execution.",
            href="/approvals",
            mode="PAPER ONLY",
            status="blocked" if safe_int(approval_summary.get("blocked")) else "ready_for_review" if safe_int(approval_summary.get("count")) else "inactive",
            metric=f"{safe_int(approval_summary.get('count'))} approvals",
            next_href="/preflight",
            api_href="/api/paper/approvals",
            blockers=safe_int(approval_summary.get("blocked")),
        ),
        _stage(
            group="Risk / Preflight",
            title="Paper Preflight",
            description="Check paper ticket blockers, risk budget, playbook fit, and live-readiness references.",
            href="/preflight",
            mode="PAPER ONLY",
            status="blocked" if safe_int(preflight_summary.get("blocked")) else "ready_for_review" if safe_int(preflight_summary.get("count")) else "inactive",
            metric=f"{safe_int(preflight_summary.get('count'))} checks",
            next_href="/execution-queue",
            api_href="/api/paper/preflight",
            blockers=safe_int(preflight_summary.get("blocked")),
            warnings=safe_int(preflight_summary.get("warnings")),
        ),
        _stage(
            group="Risk / Preflight",
            title="Execution Queue",
            description="Separate approved-ready simulated paper entries from blocked or approval-needed tickets.",
            href="/execution-queue",
            mode="PAPER ONLY",
            status="ready" if safe_int(execution_summary.get("approved_ready")) else "needs_review" if safe_int(execution_summary.get("needs_approval")) else "inactive",
            metric=f"{safe_int(execution_summary.get('approved_ready'))} ready",
            next_href="/paper-ops-briefing",
            api_href="/api/paper/execution-queue",
            warnings=safe_int(execution_summary.get("needs_approval")),
            blockers=safe_int(execution_summary.get("blocked")),
        ),
        _stage(
            group="Ops / Closeout",
            title="Ops Closeout",
            description="Review unresolved briefing, handoff, aging, and escalation work before ending an operator pass.",
            href="/paper-ops-closeout",
            mode="PAPER ONLY",
            status=str(closeout_summary.get("closeout_status") or "inactive"),
            metric=f"{safe_int(closeout_summary.get('handoff_required'))} handoff required",
            next_href="/audit",
            api_href="/api/paper/ops-closeout",
            warnings=safe_int(closeout_summary.get("handoff_required")),
            blockers=safe_int(closeout_summary.get("briefing_blocked")),
        ),
        _stage(
            group="Live Readiness",
            title="Live Config",
            description="Inspect redacted live-readiness fields and guard switches. This does not enable live trading.",
            href="/live-config",
            mode="LIVE READINESS",
            status=str(live_config_summary.get("readiness_state") or "live_disabled"),
            metric=f"{safe_int(live_config_summary.get('configured'))}/{safe_int(live_config_summary.get('field_count'))} configured",
            next_href="/live-order-intents",
            api_href="/api/live/config/readiness",
            warnings=safe_int(live_config_summary.get("guard_warning_count")),
        ),
        _stage(
            group="Live Readiness",
            title="Live Intent",
            description="Create local, non-executing live order intent previews after paper gates are understood.",
            href="/live-order-intents",
            mode="LIVE READINESS",
            status="ready_for_review" if safe_int(live_intent_summary.get("saved_count") or live_intent_summary.get("count")) else "inactive",
            metric=f"{safe_int(live_intent_summary.get('saved_count') or live_intent_summary.get('count'))} intents",
            next_href="/live-order-intent-preflight",
            api_href="/api/live/order-intents",
        ),
        _stage(
            group="Live Readiness",
            title="Live Preflight",
            description="Check live-intent governance before any operator authorization snapshot.",
            href="/live-order-intent-preflight",
            mode="LIVE READINESS",
            status="blocked" if safe_int(live_preflight_summary.get("blocked")) else "ready_for_review" if safe_int(live_preflight_summary.get("count")) else "inactive",
            metric=f"{safe_int(live_preflight_summary.get('count'))} reviews",
            next_href="/live-order-authorizations",
            api_href="/api/live/order-intents/preflight",
            blockers=safe_int(live_preflight_summary.get("blocked")),
        ),
        _stage(
            group="Live Readiness",
            title="Operator Authorization",
            description="Record human authorization/defer/reject snapshots. These are documentation only.",
            href="/live-order-authorizations",
            mode="LIVE READINESS",
            status="ready_for_review" if safe_int(auth_summary.get("saved_count") or auth_summary.get("count")) else "inactive",
            metric=f"{safe_int(auth_summary.get('saved_count') or auth_summary.get('count'))} authorizations",
            next_href="/live-execution-packets",
            api_href="/api/live/order-intents/authorizations",
        ),
        _stage(
            group="Live Readiness",
            title="Execution Packet",
            description="Assemble unsigned packets for review and dry-run validation only.",
            href="/live-execution-packets",
            mode="LIVE READINESS",
            status="ready_for_review" if safe_int(packet_summary.get("saved_count") or packet_summary.get("count")) else "inactive",
            metric=f"{safe_int(packet_summary.get('saved_count') or packet_summary.get('count'))} packets",
            next_href="/live-dry-run-adapter",
            api_href="/api/live/execution-packets",
        ),
        _stage(
            group="Live Readiness",
            title="Dry-Run Adapter",
            description="Create offline dry-run receipts without signing or network submission.",
            href="/live-dry-run-adapter",
            mode="LIVE READINESS",
            status="ready_for_review" if safe_int(dry_run_summary.get("saved_count") or dry_run_summary.get("count")) else "inactive",
            metric=f"{safe_int(dry_run_summary.get('saved_count') or dry_run_summary.get('count'))} receipts",
            next_href="/live-adapter-requests",
            api_href="/api/live/dry-run-adapter",
        ),
        _stage(
            group="Live Readiness",
            title="Adapter Request",
            description="Validate adapter-shaped requests against packet, auth, dry-run, risk, and kill-switch gates.",
            href="/live-adapter-requests",
            mode="LIVE READINESS",
            status="ready_for_review" if safe_int(adapter_request_summary.get("ready_count") or adapter_request_summary.get("adapter_request_ready")) else "inactive",
            metric=f"{safe_int(adapter_request_summary.get('saved_count') or adapter_request_summary.get('count'))} requests",
            next_href="/manual-execution-boundary",
            api_href="/api/live/adapter/requests",
        ),
        _stage(
            group="Manual Boundary",
            title="Manual Execution Review",
            description="Record final local review of packets before any manual execution-control attempt.",
            href="/manual-execution-boundary",
            mode="LIVE DISABLED",
            status="ready_for_review" if safe_int(manual_review_summary.get("saved_count") or manual_review_summary.get("count")) else "inactive",
            metric=f"{safe_int(manual_review_summary.get('saved_count') or manual_review_summary.get('count'))} reviews",
            next_href="/live-manual-execution",
            api_href="/api/live/manual-execution-reviews",
        ),
        _stage(
            group="Manual Boundary",
            title="Manual Execution Control",
            description="Preview or record blocked/fake-local attempts. Real live submit/cancel are implemented behind hard gates.",
            href="/live-manual-execution",
            mode="LIVE DISABLED",
            status=str(live_control.get("overall_status") or "live_disabled"),
            metric=f"{safe_int(attempt_summary.get('saved_count') or attempt_summary.get('count'))} attempts",
            next_href="/live-execution-attempts",
            api_href="/api/live/execution-control/readiness",
            warnings=len(live_control.get("warnings") or []),
            blockers=len(live_control.get("blockers") or []),
        ),
        _stage(
            group="Audit / Reports",
            title="Audit / Closeout",
            description="Trace paper, ops, and staged-live-readiness records in the local audit ledger.",
            href="/audit",
            mode="LOCAL",
            status="ready_for_review" if safe_int(audit_summary.get("count")) else "inactive",
            metric=f"{safe_int(audit_summary.get('count'))} rows",
            api_href="/api/paper/audit",
        ),
    ]

    groups: list[dict[str, Any]] = []
    for group_name in ["Research", "Market Data", "Paper Workflow", "Risk / Preflight", "Ops / Closeout", "Live Readiness", "Manual Boundary", "Audit / Reports"]:
        group_stages = [stage for stage in stages if stage["group"] == group_name]
        groups.append(
            {
                "name": group_name,
                "stages": group_stages,
                "blockers": sum(safe_int(stage.get("blockers")) for stage in group_stages),
                "warnings": sum(safe_int(stage.get("warnings")) for stage in group_stages),
            }
        )

    return {
        "version": APP_VERSION,
        "generated_at": now_iso(),
        "groups": groups,
        "stages": stages,
        "summary": {
            "stage_count": len(stages),
            "blockers": sum(safe_int(stage.get("blockers")) for stage in stages),
            "warnings": sum(safe_int(stage.get("warnings")) for stage in stages),
            "live_submit_implemented": False,
            "live_cancel_implemented": False,
            "autonomous_trading_enabled": False,
        },
        "guardrail": "Workflow map is read-only. It does not approve, sign, submit, cancel, or automate trading.",
    }


def build_ui_system_reference() -> dict[str, Any]:
    return {
        "version": APP_VERSION,
        "generated_at": now_iso(),
        "badges": [
            {"label": "CLEAR", "tone": "ok"},
            {"label": "WARNING", "tone": "warning"},
            {"label": "BLOCKED", "tone": "danger"},
            {"label": "NEEDS REVIEW", "tone": "warning"},
            {"label": "READY FOR REVIEW", "tone": "info"},
            {"label": "PAPER ONLY", "tone": "paper"},
            {"label": "LIVE DISABLED", "tone": "neutral"},
            {"label": "FAKE LOCAL", "tone": "info"},
            {"label": "NOT SUBMITTED", "tone": "neutral"},
            {"label": "KILL SWITCH ACTIVE", "tone": "danger"},
            {"label": "AUTH REQUIRED", "tone": "warning"},
            {"label": "EXPORT READY", "tone": "ok"},
        ],
        "callouts": [
            {"tone": "info", "title": "Information", "body": "Use blue callouts for context and workflow guidance."},
            {"tone": "warning", "title": "Operator Review", "body": "Use amber callouts for stale records, missing approvals, or manual review."},
            {"tone": "danger", "title": "Blocked", "body": "Use red callouts for blockers, kill switch, and disabled execution controls."},
            {"tone": "ok", "title": "Clear", "body": "Use green callouts when gates are clear or exports are ready."},
        ],
        "guardrail": "Design-system examples are static local UI references. They do not mutate app state.",
    }
