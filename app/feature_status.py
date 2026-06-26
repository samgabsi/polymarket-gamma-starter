from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import APP_VERSION, DATA_DIR, settings
from .platform_safety import safety_flags


DATA_STATE_VALUES = ["live", "cached", "sample", "stale", "unavailable"]
FEATURE_READINESS_RUNTIME_DIR = DATA_DIR / "feature_readiness"
FEATURE_READINESS_AUDIT_PATH = FEATURE_READINESS_RUNTIME_DIR / "readiness_acknowledgements.jsonl"


def _inferred_data_state(feature_id: str, area: str, status: str, reason: str) -> str:
    text = f"{feature_id} {area} {status} {reason}".lower()
    if "fixture" in text or "demo" in text or "sample" in text:
        return "sample"
    if status in {"disabled", "config_required", "scaffolded", "unavailable", "error"}:
        return "unavailable"
    if area in {"cockpit", "settings", "review", "audit", "tasks", "platform", "launch", "data"}:
        return "cached"
    if area in {"market-data", "arbitrage", "venue-registry"}:
        return "cached" if status == "partial" else "live"
    return "unavailable"


def _fallback_operator_implication(status: str, reason: str, operator_action: str) -> str:
    if status == "working":
        return operator_action or reason
    if status in {"disabled", "config_required", "scaffolded", "unavailable", "error"}:
        return reason
    return operator_action or reason


@dataclass(frozen=True)
class FeatureStatus:
    feature_id: str
    title: str
    status: str
    area: str
    visible: bool
    operator_action: str
    reason: str
    route: str = ""
    api_route: str = ""
    requires_restart: bool = False
    review_only: bool = True
    operator_implication: str = ""
    next_action: str = ""
    data_state: str = ""
    safe_review_only: bool = True
    live_disabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["operator_implication"] = self.operator_implication or _fallback_operator_implication(self.status, self.reason, self.operator_action)
        data["next_action"] = self.next_action or self.operator_action
        data["data_state"] = self.data_state or _inferred_data_state(self.feature_id, self.area, self.status, self.reason)
        data["safe_review_only"] = bool(self.safe_review_only and self.review_only)
        data["live_disabled"] = bool(self.live_disabled)
        data["app_version"] = APP_VERSION
        return data


@dataclass(frozen=True)
class StubBurnDownItem:
    feature_id: str
    title: str
    status: str
    area: str
    visible_surface: str
    operator_action: str
    backend_wiring: str
    ui_wiring: str
    test_status: str
    docs_status: str
    reason: str
    route: str = ""
    api_route: str = ""
    review_only: bool = True
    operator_implication: str = ""
    next_action: str = ""
    data_state: str = ""
    safe_review_only: bool = True
    live_disabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["operator_implication"] = self.operator_implication or _fallback_operator_implication(self.status, self.reason, self.operator_action)
        data["next_action"] = self.next_action or self.operator_action
        data["data_state"] = self.data_state or _inferred_data_state(self.feature_id, self.area, self.status, self.reason)
        data["safe_review_only"] = bool(self.safe_review_only and self.review_only)
        data["live_disabled"] = bool(self.live_disabled)
        data["app_version"] = APP_VERSION
        return data


def _status(enabled: bool, configured: bool = True, partial: bool = False) -> str:
    if partial:
        return "partial"
    if enabled and configured:
        return "working"
    if enabled and not configured:
        return "config_required"
    return "disabled"


def _counts(rows: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return counts


def build_stub_burndown_map() -> dict[str, Any]:
    """Return the operator-facing v4.15 stub/dead-control burn-down map.

    The map is intentionally static and local. It does not probe networks or call AI.
    Statuses describe what the package can truthfully do from the visible UI/API.
    """
    kalshi_enabled = bool(getattr(settings, "kalshi_enabled", False))
    kalshi_has_base = bool(getattr(settings, "kalshi_api_base_url", ""))
    arbitrage_enabled = bool(getattr(settings, "arbitrage_scanner_enabled", False))
    ai_adjust_enabled = bool(getattr(settings, "ai_odds_adjustment_enabled", True))
    paper_enabled = bool(getattr(settings, "paper_trading_enabled", False))
    paper_auto_enabled = bool(getattr(settings, "paper_trading_automation_enabled", False))

    rows = [
        StubBurnDownItem(
            "operator_os.five_workspace_shell",
            "Five-workspace Operator OS shell",
            "working",
            "operator-os",
            "Command Center, Opportunities, Automation, Review & Audit, Settings & System",
            "Use the five workspace links for the normal operating flow; use direct legacy routes only for source-specific detail.",
            "New /api/v3/operator-os workspace context returns shell status, compatibility routes, and workspace summaries without live mutation.",
            "New /v3, /v3/automation, /v3/review-audit, and /v3/settings-system pages provide the consolidated shell; /v3/opportunities remains the detailed Opportunity workspace.",
            "working",
            "working",
            "v4.17 reduces primary navigation sprawl without deleting backend routes or enabling trading.",
            "/v3",
            "/api/v3/operator-os",
            operator_implication="Advanced/source-specific pages are still available but no longer dominate the main operating model.",
            next_action="Start from Command Center and drill into the workspace that matches the operator question.",
            data_state="cached",
        ),
        StubBurnDownItem(
            "operator_os.compatibility_routes",
            "Compatibility route map",
            "working",
            "operator-os",
            "Old AI odds, arbitrage, paper trading, review queue, readiness, settings, cockpit, and live-control routes",
            "Use compatibility links when deep source-specific tools are needed; otherwise stay in the five workspace model.",
            "Compatibility routes are documented and exposed through /api/v3/operator-os plus the Operator OS template.",
            "Every primary workspace shows old routes and where they belong; old routes continue to render or link to their workspace.",
            "working",
            "working",
            "No backend route is removed; old bookmarks do not break abruptly.",
            "/v3",
            "/api/v3/operator-os",
            operator_implication="Bookmarked pages remain available, but the user receives a clearer workspace-level path back to the main OS.",
            next_action="Use Settings & System for advanced/debug links and Command Center for daily flow.",
            data_state="cached",
        ),
        StubBurnDownItem(
            "polymarket.discovery_pricing_orderbook",
            "Polymarket discovery / pricing / orderbook",
            "partial",
            "market-data",
            "Market detail, dashboard, orderbook APIs",
            "Use demo/local views by default; configure network/API access before relying on live public reads.",
            "Gamma/CLOB read helpers and orderbook summary routes exist; errors degrade to unavailable data.",
            "Visible market pages link to summaries and never imply live order execution.",
            "needs_tests",
            "needs_docs",
            "Discovery and pricing surfaces are wired for review, but real-time coverage depends on network/API availability and freshness checks.",
            "/v3/markets/{market_id}",
            "/api/v3/markets/{market_id}/summary",
        ),
        StubBurnDownItem(
            "ai.news_odds",
            "AI news odds adjustment",
            _status(ai_adjust_enabled),
            "ai",
            "AI News Odds pages",
            "Review source weights, raw adjustment, weighted adjustment, final risk-controlled draft, explicit YES/NO side, and saved decision feedback before accepting any context.",
            "Manual evidence, planning, adjustment, source weighting, and config APIs are wired.",
            "Browser forms redirect to operator pages with feedback; saved draft adjustments open a detail page with accept/reject/archive actions.",
            "working",
            "working",
            "Manual-evidence review mode is available; web search remains config-gated and disabled by default.",
            "/v3/ai/news-odds",
            "/api/v3/ai/news-odds/config",
        ),
        StubBurnDownItem(
            "ai.edge_research",
            "AI Edge research packets",
            "working",
            "ai",
            "AI Edge dashboard and market links",
            "Generate or inspect draft packets only after human action; treat all outputs as review-only.",
            "Packet, evidence, calibration, provider, dry-run, and export APIs are wired.",
            "v4.11 replaces POST-only API hrefs with working browser POST controls.",
            "working",
            "working",
            "Draft packet workflows work locally without granting trade approval or live mutation.",
            "/v3/ai/edge",
            "/api/v3/ai/edge/packets",
        ),
        StubBurnDownItem(
            "ai.yes_no_recommendation",
            "YES / NO recommendation clarity",
            "working",
            "ai",
            "Market rows, market detail, AI Edge links",
            "Read Recommended Side as YES, NO, HOLD, NEEDS REVIEW, or INSUFFICIENT DATA; do not treat favorite rank as edge.",
            "Deterministic market-edge helpers expose side, fair YES/NO, favorite-vs-edge explanation, and draft packet context.",
            "Market detail and workbench surfaces label review-only side guidance.",
            "working",
            "working",
            "The recommendation label is explanatory context, not a trade signal or approval.",
            "/v3/markets/{market_id}",
            "/api/v3/ai/edge/market/{market_id}/summary",
        ),
        StubBurnDownItem(
            "arbitrage.scanner_review",
            "Cross-market arbitrage scanner and review",
            "partial" if not arbitrage_enabled else "working",
            "arbitrage",
            "Arbitrage page and review APIs",
            "Use demo scans unless the scanner is explicitly enabled; record snapshots only when you want a local audit trail.",
            "Candidate generation, equivalence scoring, persisted scan snapshots, review records, data-state labels, and audit payloads are wired.",
            "Refresh, record snapshot, review, watchlist, ignore, and reject controls are browser-safe forms with redirect feedback; informational GET compatibility routes do not record decisions.",
            "working",
            "working",
            "The engine is review-first. Live scan breadth depends on enabled venues and configured read access; default package scans use sample fixtures.",
            "/v3/arbitrage",
            "/api/v3/arbitrage/scan",
            data_state="sample" if not arbitrage_enabled else "live",
            operator_implication="Default arbitrage scans are workflow/sample data unless the scanner and venues are explicitly enabled.",
            next_action="Use Record scan snapshot for local audit evidence, or configure live read-only venues before interpreting candidates as current market data.",
        ),
        StubBurnDownItem(
            "venues.kalshi",
            "Kalshi venue adapter",
            "config_required" if kalshi_enabled and kalshi_has_base else ("disabled" if not kalshi_enabled else "partial"),
            "venue-registry",
            "Arbitrage readiness and feature status",
            "Set KALSHI_ENABLED=true and review credentials only when public Kalshi reads are intended.",
            "Adapter and registry entries exist; credentials are optional/redacted; missing config does not block startup.",
            "Shown as disabled/config-required instead of complete.",
            "working",
            "working",
            "Kalshi remains safe-default disabled unless deliberately configured.",
            "/v3/arbitrage",
            "/api/v3/arbitrage/config",
        ),
        StubBurnDownItem(
            "venues.registry",
            "Venue registry",
            "partial",
            "venue-registry",
            "Arbitrage config/status",
            "Confirm each venue status before interpreting any cross-market candidate.",
            "Polymarket and Kalshi adapters are registered; competitor/future venues stay disabled scaffolds.",
            "Feature status distinguishes working, disabled, and config-required venue entries.",
            "needs_tests",
            "working",
            "The registry is truthful but not all venues are live-read capable in the default package.",
            "/v3/arbitrage",
            "/api/v3/arbitrage/config",
        ),
        StubBurnDownItem(
            "review.queue_actions",
            "Review queue and operator decisions",
            "working",
            "review",
            "Review Queue, opportunity, paper review, audit, task/workspace surfaces",
            "Approve/reject/dismiss/mark-reviewed style actions create local review records only where exposed, with source metadata where available.",
            "Opportunity, paper review, escalation, workspace, and task review APIs write local JSONL records; v4.15 adds Review Queue POST actions with persisted state, data-state, source route/component, previous/new state, and live-disabled audit fields.",
            "High-traffic review actions use POST forms or explicit JSON links; Review Queue rows now expose real action forms with feedback redirects instead of static action labels.",
            "working",
            "working",
            "Review records do not approve trades, place orders, or arm live trading.",
            "/review-queue",
            "/api/review-queue/{market_id}/action",
            data_state="cached",
            operator_implication="Review Queue and Opportunity decisions persist local audit evidence only and carry source/data-state context for operator traceability.",
            next_action="Use Review Queue row forms for mark-reviewed/watchlist/paper-review/dismiss, or use the Opportunity workbench data-mode selector for notes/status decisions.",
        ),
        StubBurnDownItem(
            "audit.operator_log",
            "Operator audit log",
            "working",
            "audit",
            "Audit pages, v2/v3 subsystem audit calls",
            "Use audit/export routes for local review; do not store secrets in runtime notes.",
            "Cockpit, task, workspace, AI, opportunity, and live-control-adjacent actions record local audit metadata where supported.",
            "Audit/export links are GET routes; write actions are POST-backed.",
            "working",
            "working",
            "Audit is local-first and redacted; it is not immutable external compliance storage.",
            "/audit",
            "/api/paper/audit",
        ),
        StubBurnDownItem(
            "cockpit.layouts_focus",
            "Cockpit layouts and focus modes",
            "working",
            "cockpit",
            "Operator Cockpit",
            "Select a layout, save a copy, or start a focus mode from the cockpit page.",
            "Layout selection, saved layouts, focus session snapshots, command palette safety, and exports are wired.",
            "Cards are real POST controls with selected/active state.",
            "working",
            "working",
            "Cockpit actions are workflow aids only.",
            "/v3/cockpit",
            "/api/v3/cockpit/layouts",
        ),
        StubBurnDownItem(
            "tasks.triage_blockers",
            "Task triage, blocked/dependency/source/dataset review",
            "working",
            "tasks",
            "Tasks and Guided Workspace",
            "Start daily/weekly/triage reviews and mark tasks blocked/unblocked through task APIs.",
            "Tasks, inbox, cadence, dependencies, blocked review, source previews, saved views, and review packets are wired.",
            "Workspace review flows start through browser POST forms instead of POST-only hrefs.",
            "working",
            "working",
            "Task completion and guided review completion never approve trades.",
            "/v3/workspace",
            "/api/v3/workspace/task-triage/start",
        ),
        StubBurnDownItem(
            "paper_trading.automation_loop",
            "Automated paper trading strategy loop",
            "working" if paper_enabled and paper_auto_enabled else ("disabled" if not paper_enabled else "config_required"),
            "paper-trading",
            "Automated Paper Trading page, API, local paper ledger, and feature readiness",
            "Enable PAPER_TRADING_ENABLED and PAPER_TRADING_AUTOMATION_ENABLED to run simulated strategy cycles; keep live trading separately disabled.",
            "v4.17 adds a paper-only broker, strategy runner, ledger, risk checks, API routes, audit rows, and reset/run-once controls that never call real execution endpoints.",
            "The /v3/paper-trading page shows status cards, run/reset forms, recent orders/fills/positions, decisions, and explicit paper-only safety banners.",
            "working",
            "working",
            "Automation is implemented as local simulated execution only. Sample candidates are clearly marked sample/paper-only when no live/local candidate feed is supplied.",
            "/v3/paper-trading",
            "/api/v3/paper/status",
            review_only=False,
            operator_implication="Operators can run an automated paper cycle and inspect decisions, fills, P/L, and audit evidence without placing or cancelling real orders.",
            next_action="Set PAPER_TRADING_ENABLED=true and PAPER_TRADING_AUTOMATION_ENABLED=true, then use Run paper strategy once from /v3/paper-trading.",
            data_state="cached" if paper_enabled else "unavailable",
            safe_review_only=True,
            live_disabled=True,
        ),
        StubBurnDownItem(
            "settings.config",
            "Settings and configuration",
            "working",
            "settings",
            "Settings hub, v3 settings page, and configuration console",
            "Edit UI-safe preferences on /v3/settings; use /settings/configuration for process/env preview and explicit save confirmation.",
            "Schema, status, diff, save, presets, audit history, setup status, masked config routes, and v3 settings persistence/local preference persistence are wired.",
            "v4.15 replaces the raw-only v3 settings JSON card with validated POST-backed controls, source/restart labels, and recent settings audit feedback.",
            "working",
            "working",
            "Process-level env changes still require restart; UI preference changes save locally and secrets remain masked.",
            "/v3/settings",
            "/api/v3/settings",
            data_state="cached",
            operator_implication="Operators can save local UI preferences without touching secrets, enabling scanners, or changing live execution posture.",
            next_action="Use the v3 settings form for local preferences; use the configuration console for .env/process changes that require restart.",
        ),
        StubBurnDownItem(
            "features.readiness_registry",
            "Feature readiness and stub burn-down registry",
            "working",
            "platform",
            "Cockpit and platform readiness sections",
            "Use status maps before trusting a visible feature as complete.",
            "Feature status and stub burn-down endpoints are wired.",
            "Cockpit readiness table links both maps.",
            "working",
            "working",
            "The map is static/local and intentionally avoids live probes.",
            "/v3/cockpit",
            "/api/v3/features/stub-burndown",
        ),
        StubBurnDownItem(
            "features.readiness_page",
            "Feature readiness review workflow",
            "working",
            "platform",
            "Feature Readiness page",
            "Open the readiness page, filter status rows, review operator implications, and record a local acknowledgement when the current state has been reviewed.",
            "Feature status, stub burn-down, acknowledgement listing, and acknowledgement POST routes are wired without live probes.",
            "The page renders working/partial/config-required/scaffolded/disabled states with data-state badges and POST-backed acknowledgement feedback.",
            "working",
            "working",
            "Readiness acknowledgements are local audit evidence only; they do not enable disabled features or live execution.",
            "/v3/feature-readiness",
            "/api/v3/features/readiness/acknowledgements",
            data_state="cached",
            operator_implication="The operator can verify what is real, what is disabled, and what needs config before using visible surfaces.",
            next_action="Use the filters and Record readiness review after checking the relevant statuses.",
        ),
        StubBurnDownItem(
            "data.export_import",
            "Export / import / backup workflows",
            "partial",
            "data",
            "Data, platform, cockpit, workspace, tasks exports",
            "Use exports freely; use import/restore preview/apply paths only after reviewing local runtime data.",
            "Many JSON/Markdown/CSV exports are wired; import/restore paths remain deliberately gated.",
            "Export links are GET routes; restore is not exposed as an accidental one-click web action.",
            "needs_tests",
            "working",
            "Export coverage is broad, while destructive restore/import is intentionally constrained.",
            "/v2-live/data",
            "/api/v2/live/data/export.json",
        ),
        StubBurnDownItem(
            "launch.helpers",
            "Launch helpers",
            "working",
            "launch",
            "run.py, scripts, docs, validation",
            "Launch with the documented run command and validate routes/tests before operating.",
            "CLI/run helpers and validation scripts are package-local.",
            "Docs and release notes include launch and validation guidance.",
            "working",
            "working",
            "Launch helpers do not enable live trading or network-heavy jobs by themselves.",
            "/setup/status",
            "/api/setup/status",
        ),
        StubBurnDownItem(
            "live.execution_controls",
            "Live execution controls",
            "disabled",
            "live-controls",
            "v2 live controls and execution readiness",
            "Keep live submit/cancel disabled unless every backend gate, approval, warning acknowledgement, and typed confirmation passes.",
            "Preview, preflight, authorization, dry-run, adapter, manual submit/cancel, and audit boundaries are wired behind gates.",
            "Dangerous controls remain visually distinct and disabled/gated by backend state.",
            "working",
            "working",
            "This package is not autonomous trading software. Live mutation remains fail-closed by default.",
            "/v2-live",
            "/api/live/execution-control/readiness",
        ),
    ]

    counts = _counts(rows)
    categories = {
        "broken_visible_ui": [
            "v4.15 adds a first-class feature readiness review page with filters and local acknowledgement audit records.",
            "v4.15 continues the burn-down by making v3 settings preferences browser-editable, validated, persisted, audited, and reflected in readiness.",
            "v4.15 made opportunity review data mode explicit and preserved source/data-state metadata in browser POST actions.",
            "v4.13 made arbitrage scan persistence a visible POST action with redirect feedback instead of a hidden GET query flag.",
        ],
        "partially_wired_systems": [
            "Polymarket live-read freshness depends on network/API state.",
            "Venue registry includes disabled/config-required venues by design.",
            "Export/import coverage is broad but restore/import remains gated.",
        ],
        "misleading_scaffolds": [
            "Kalshi and future venues are labeled disabled/config-required instead of complete.",
            "Live execution controls stay disabled/gated by default.",
        ],
        "missing_operator_feedback": [
            "v4.15 adds feedback for feature readiness acknowledgements and lists recent local records on the readiness page.",
            "v4.15 adds settings preference save/reject feedback and local audit events for validated UI-safe preference changes.",
            "v4.15 kept opportunity review notes/status feedback and enriched the resulting local audit rows.",
            "v4.13 added feedback for recorded arbitrage scan snapshots and kept review-decision feedback.",
        ],
        "missing_tests": [
            "v4.15 adds feature readiness page, acknowledgement persistence, API contract, and no-live-mutation regression tests.",
            "v4.15 adds workflow tests for settings preferences, validation rejection, audit events, and readiness truthfulness.",
            "v4.15 added workflow tests for opportunity data-mode controls, source metadata, enriched audit fields, and readiness truthfulness.",
            "v4.13 added workflow tests for arbitrage scan recording, data-state surfacing, enriched audit fields, and readiness schema fields.",
            "Broader browser screenshot/manual QA remains outside automated pytest coverage.",
        ],
    }
    acceptance = {
        "cockpit_layout_focus": "working",
        "ai_odds_review": "working",
        "arbitrage_review": "working",
        "settings_config": "working",
        "feature_readiness": "working",
        "feature_readiness_review": "working",
        "paper_trading": "working" if paper_enabled and paper_auto_enabled else ("disabled" if not paper_enabled else "config_required"),
        "live_execution": "disabled",
        "kalshi": "disabled" if not kalshi_enabled else "config_required",
    }
    return {
        "app_version": APP_VERSION,
        "items": [row.to_dict() for row in rows],
        "count": len(rows),
        "counts": counts,
        "status_values": [
            "working",
            "partial",
            "config_required",
            "scaffolded",
            "disabled",
            "unavailable",
            "needs_tests",
            "needs_ui_wiring",
            "needs_backend_wiring",
            "needs_docs",
            "error",
        ],
        "data_state_values": DATA_STATE_VALUES,
        "audit_categories": categories,
        "operator_acceptance": acceptance,
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "map_is_static_no_live_probe": True,
        **safety_flags(),
    }


def build_feature_status_map() -> dict[str, Any]:
    """Return the UI honesty/readiness registry used by v4.15.0 surfaces.

    This intentionally avoids live network calls. It reports whether a surface is wired,
    disabled, scaffolded, or config-required so visible UI does not imply fake capability.
    """
    kalshi_enabled = bool(getattr(settings, "kalshi_enabled", False))
    kalshi_has_base = bool(getattr(settings, "kalshi_api_base_url", ""))
    kalshi_credentials_configured = bool(getattr(settings, "kalshi_api_key_id", ""))
    arbitrage_enabled = bool(getattr(settings, "arbitrage_scanner_enabled", False))
    ai_adjust_enabled = bool(getattr(settings, "ai_odds_adjustment_enabled", True))
    paper_enabled = bool(getattr(settings, "paper_trading_enabled", False))
    paper_auto_enabled = bool(getattr(settings, "paper_trading_automation_enabled", False))

    rows = [
        FeatureStatus(
            "operator_os.command_center",
            "Operator OS Command Center",
            "working",
            "operator-os",
            True,
            "Use /v3 as the default landing page for safety posture, readiness warnings, paper automation status, reviews, and next operator action.",
            "v4.17 consolidates the default UI into a five-workspace Operator OS without enabling live execution.",
            "/v3",
            "/api/v3/operator-os/command_center",
            operator_implication="Command Center summarizes existing systems; it does not mutate trading state or hide source-specific detail pages.",
            next_action="Start from /v3, then drill into Opportunities, Automation, Review & Audit, or Settings & System.",
            data_state="cached",
        ),
        FeatureStatus(
            "operator_os.opportunities_workspace",
            "Operator OS Opportunities workspace",
            "working",
            "operator-os",
            True,
            "Use /v3/opportunities as the consolidated entry point for AI odds, edge review, arbitrage, paper signals, and review queue items.",
            "The existing opportunity workbench remains the detail surface; v4.17 adds a source-aware consolidated workspace model.",
            "/v3/opportunities",
            "/api/v3/operator-os/opportunities",
            operator_implication="Rows are shown only when local records exist; source-specific pages stay linked and honest about sample/cached/live state.",
            next_action="Open source sections for AI odds, arbitrage, or paper automation when the unified table is empty.",
            data_state="cached",
        ),
        FeatureStatus(
            "operator_os.automation_workspace",
            "Operator OS Automation / Paper Trading workspace",
            "working",
            "operator-os",
            True,
            "Use /v3/automation for paper-only automation status, run-once controls, paper account, decisions, orders, fills, positions, and P/L.",
            "Automation remains paper-only and delegates detailed tables to the v4.16 paper trading subsystem.",
            "/v3/automation",
            "/api/v3/operator-os/automation",
            review_only=False,
            operator_implication="No real orders are placed; API responses remain paper_only=true and live_execution_used=false.",
            next_action="Enable paper gates deliberately and use run-once to validate the simulated workflow.",
            data_state="cached",
            safe_review_only=True,
            live_disabled=True,
        ),
        FeatureStatus(
            "operator_os.review_audit_workspace",
            "Operator OS Review & Audit workspace",
            "working",
            "operator-os",
            True,
            "Use /v3/review-audit to inspect review queue actions, opportunity review records, paper decisions, and paper audit rows.",
            "v4.17 collects accountability surfaces without changing their persistence/audit semantics.",
            "/v3/review-audit",
            "/api/v3/operator-os/review_audit",
            operator_implication="Review actions are local decisions only and cannot approve, submit, cancel, or arm live orders.",
            next_action="Inspect recent events or open the detailed Review Queue for row-level actions.",
            data_state="cached",
        ),
        FeatureStatus(
            "operator_os.settings_system_workspace",
            "Operator OS Settings & System workspace",
            "working",
            "operator-os",
            True,
            "Use /v3/settings-system for readiness, settings, venues, AI/OpenAI status, paper limits, arbitrage config, diagnostics, and advanced links.",
            "v4.17 demotes low-level diagnostics and compatibility routes behind a single settings/system workspace.",
            "/v3/settings-system",
            "/api/v3/operator-os/settings_system",
            operator_implication="Settings & System surfaces truthfulness and config sources without exposing secrets or mutating .env from the consolidated page.",
            next_action="Use detailed settings or feature readiness pages when a row needs deeper review.",
            data_state="cached",
        ),
        FeatureStatus(
            "cockpit.layout_selector",
            "Cockpit layout selector",
            "working",
            "cockpit",
            True,
            "Select a layout card to persist the active cockpit layout.",
            "Cockpit layout cards are POST actions with selected state, panel changes, and audit records.",
            "/v3/cockpit",
            "/api/v3/cockpit/layouts/{layout_id}/select",
        ),
        FeatureStatus(
            "cockpit.saved_layouts",
            "Saved cockpit layouts",
            "working",
            "cockpit",
            True,
            "Use Save current layout copy to create an operator-owned saved layout.",
            "Default layouts remain available; saved copies are stored locally in the cockpit layout JSONL store.",
            "/v3/cockpit",
            "/api/v3/cockpit/layouts",
        ),
        FeatureStatus(
            "cockpit.focus_modes",
            "Focused review modes",
            "working",
            "cockpit",
            True,
            "Start a focus mode to switch the layout and navigate to the relevant review surface.",
            "Focus mode cards are POST-backed and create a local session snapshot; they do not mutate live trading state.",
            "/v3/cockpit",
            "/api/v3/cockpit/focus-modes/{focus_mode_id}/start",
        ),
        FeatureStatus(
            "ai.odds_adjustment",
            "AI odds adjustment surfacing",
            _status(ai_adjust_enabled),
            "ai",
            True,
            "Review raw, evidence-weighted, and final risk-controlled adjustments before accepting any context update.",
            "The 2.5 percentage-point value is a legacy warning threshold, not an absolute hidden cap.",
            "/v3/ai/news-odds",
            "/api/v3/ai/news-odds/config",
        ),
        FeatureStatus(
            "ai.odds_page_actions",
            "AI odds page actions",
            "working",
            "ai",
            True,
            "Use page POST controls for search planning, gated web-search preview, manual evidence, and draft adjustment generation.",
            "Browser actions submit to page POST wrappers; JSON APIs remain available for programmatic clients.",
            "/v3/markets/{market_id}/news-odds",
            "/api/v3/ai/news-odds/market/{market_id}/adjust",
        ),
        FeatureStatus(
            "arbitrage.scanner",
            "Cross-market arbitrage scanner",
            _status(arbitrage_enabled),
            "arbitrage",
            True,
            "Use demo fixtures or enable the scanner explicitly; record a scan snapshot only when local audit evidence is useful.",
            "Candidates include fees, slippage, liquidity, net margin, equivalence score, mismatch risk, scanner status, venue status, and data-state labels.",
            "/v3/arbitrage",
            "/api/v3/arbitrage/scan",
            operator_implication="Default output is sample/review-only unless live read-only scanning is enabled and venues return data.",
            next_action="Review the page data-state and venue rows, then use Record scan snapshot if the scan should be persisted.",
            data_state="sample" if not arbitrage_enabled else "live",
        ),
        FeatureStatus(
            "arbitrage.review_actions",
            "Arbitrage review actions",
            "working",
            "arbitrage",
            True,
            "Submit candidate review decisions through POST-backed page forms or the POST JSON API.",
            "The compatibility GET route is informational and does not record a review action; audit records include target, state transition, source route, and data state.",
            "/v3/arbitrage",
            "/api/v3/arbitrage/opportunity/{opportunity_id}/review",
            operator_implication="Review actions persist local decisions only and do not approve or execute trades.",
            next_action="Use review/watchlist/ignore/reject from the page and inspect the local audit log when needed.",
            data_state="cached",
        ),
        FeatureStatus(
            "arbitrage.polymarket_adapter",
            "Polymarket venue adapter",
            "working",
            "arbitrage",
            True,
            "Polymarket remains the primary venue adapter and degrades to explicit unavailable status on fetch errors.",
            "Live read paths are controlled by scanner configuration; demo mode uses deterministic fixtures.",
            "/v3/arbitrage",
            "/api/v3/arbitrage/scan",
        ),
        FeatureStatus(
            "arbitrage.kalshi_adapter",
            "Kalshi venue adapter",
            "config_required" if kalshi_enabled and kalshi_has_base else ("disabled" if not kalshi_enabled else "partial"),
            "arbitrage",
            True,
            "Set KALSHI_ENABLED=true only when you want public Kalshi reads; private credentials remain optional and redacted.",
            "Kalshi does not block app startup. Credentials configured: " + str(kalshi_credentials_configured),
            "/v3/arbitrage",
            "/api/v3/arbitrage/config",
        ),
        FeatureStatus(
            "review.queue_actions",
            "Review Queue operator actions",
            "working",
            "review",
            True,
            "Use row-level POST forms on /review-queue to mark reviewed, watchlist, needs-evidence, paper-review, reject, or archive candidates.",
            "v4.15 Review Queue actions persist local JSONL decisions with data state, source route/component, previous/new state, and live-disabled audit metadata.",
            "/review-queue",
            "/api/review-queue/{market_id}/action",
            operator_implication="Review Queue decisions are local operator metadata only and cannot approve, place, cancel, or arm live orders.",
            next_action="Open /review-queue?demo=true to verify the workflow, then use configured source mode when market/evidence inputs are available.",
            data_state="cached",
        ),
        FeatureStatus(
            "opportunity.review_actions",
            "Opportunity review actions",
            "working",
            "review",
            True,
            "Use POST-backed notes, watchlist, paper-review, reject, and archive controls from the workbench or market detail page.",
            "Review records are local runtime JSONL records and remain review-only; API hrefs are no longer presented as browser action links, and v4.14/v4.15 actions persist source metadata plus previous/new state.",
            "/v3/opportunities",
            "/api/v3/opportunities/review/{market_id}/status",
            operator_implication="Opportunity decisions are local review metadata only; data-state and source fields make demo/local/live context visible in the audit trail.",
            next_action="Select Demo fixtures or Configured local/live source, then save notes or status decisions with route/component metadata.",
            data_state="cached",
        ),
        FeatureStatus(
            "paper_trading.engine",
            "Automated paper trading engine",
            "working" if paper_enabled else "disabled",
            "paper-trading",
            True,
            "Enable PAPER_TRADING_ENABLED=true to initialize the paper broker, ledger, and account surfaces.",
            "The v4.17 subsystem is paper-only and does not call real submit/cancel APIs.",
            "/v3/paper-trading",
            "/api/v3/paper/status",
            review_only=False,
            operator_implication="Paper trading can track simulated orders, fills, positions, and P/L while live execution remains separate and disabled by default.",
            next_action="Open /v3/paper-trading to inspect status or set PAPER_TRADING_ENABLED=true before running automation.",
            data_state="cached" if paper_enabled else "unavailable",
            safe_review_only=True,
            live_disabled=True,
        ),
        FeatureStatus(
            "paper_trading.automation",
            "Paper strategy automation runner",
            "working" if paper_enabled and paper_auto_enabled else ("disabled" if not paper_enabled else "config_required"),
            "paper-trading",
            True,
            "Use Run paper strategy once after PAPER_TRADING_AUTOMATION_ENABLED=true is set.",
            "The runner considers candidates, applies edge/confidence/freshness/risk checks, and creates simulated fills only.",
            "/v3/paper-trading",
            "/api/v3/paper/run-once",
            review_only=False,
            operator_implication="Automation is available for paper trading only; every decision reports paper_only=true and live_execution_used=false.",
            next_action="Run a cycle from the UI/API after enabling the paper gates.",
            data_state="cached" if paper_enabled and paper_auto_enabled else "unavailable",
            safe_review_only=True,
            live_disabled=True,
        ),
        FeatureStatus(
            "paper_trading.scheduler",
            "Paper trading scheduler",
            "disabled" if not bool(getattr(settings, "paper_trading_scheduler_enabled", False)) else "working",
            "paper-trading",
            True,
            "Keep scheduler disabled unless explicitly configured; run-once remains the primary operator control.",
            "v4.17 exposes scheduler status but does not auto-start background jobs on import.",
            "/v3/paper-trading",
            "/api/v3/paper/status",
            review_only=False,
            operator_implication="No background paper loop starts just because the app imports modules.",
            next_action="Use run-once for deterministic QA; scheduler work can be hardened in a future iteration.",
            data_state="unavailable",
            safe_review_only=True,
            live_disabled=True,
        ),
        FeatureStatus(
            "paper_trading.broker_ledger_risk",
            "Paper broker, ledger, and risk controls",
            "working" if paper_enabled else "disabled",
            "paper-trading",
            True,
            "Inspect account, orders, fills, positions, decisions, and risk rejections from the paper API/UI.",
            "The broker applies notional, confidence, edge, spread, slippage, freshness, daily limit, position, and mismatch-risk gates before simulating fills.",
            "/v3/paper-trading",
            "/api/v3/paper/account",
            review_only=False,
            operator_implication="Risk checks can block simulated trades, and blocked decisions are still logged for review.",
            next_action="Run a paper cycle and inspect /api/v3/paper/decisions plus /api/v3/paper/audit.",
            data_state="cached" if paper_enabled else "unavailable",
            safe_review_only=True,
            live_disabled=True,
        ),
        FeatureStatus(
            "settings.ui_preferences",
            "v3 settings UI preferences",
            "working",
            "settings",
            True,
            "Use /v3/settings to edit local UI-safe preferences with validation, feedback, persistence, and local audit events.",
            "v4.15 settings controls save only non-secret UI preferences; process-level env changes still require the configuration console and restart.",
            "/v3/settings",
            "/api/v3/settings",
            operator_implication="Local preference changes are persisted and audited, but they cannot enable trading, scanners, AI network calls, or credential exposure.",
            next_action="Save a preference, verify redirect feedback, and inspect recent settings audit rows or /api/v3/settings.",
            data_state="cached",
        ),
        FeatureStatus(
            "settings.ai_arbitrage_config",
            "AI and arbitrage settings surfacing",
            "working",
            "settings",
            True,
            "Review AI odds, arbitrage, and Kalshi settings in /v3/settings or the admin configuration console.",
            "Secrets stay masked; v3 preferences persist locally while process-level .env changes require restart and explicit admin preview/save confirmation.",
            "/v3/settings",
            "/api/v3/settings",
            requires_restart=True,
        ),
        FeatureStatus(
            "features.readiness_review_page",
            "Feature readiness review page",
            "working",
            "platform",
            True,
            "Open the readiness page, filter real statuses, and record a local acknowledgement after review.",
            "The page uses the same status registry as the cockpit and adds POST-backed local audit evidence without live probes.",
            "/v3/feature-readiness",
            "/api/v3/features/readiness/acknowledgements",
            operator_implication="Use this before trusting a visible feature as complete; acknowledgements do not enable disabled features.",
            next_action="Review filtered rows and submit the acknowledgement form when the current status has been checked.",
            data_state="cached",
        ),
        FeatureStatus(
            "settings.v3_operator_preferences",
            "v3 operator settings preferences",
            "working",
            "settings",
            True,
            "Use /v3/settings to review runtime values, save UI-safe preference overlays, validate numeric controls, and see restart-required indicators.",
            "The v3 settings workflow persists non-secret preferences locally, rejects invalid numeric values, masks secrets, and writes audit events; it does not mutate process env or live trading state.",
            "/v3/settings",
            "/api/v3/settings",
            requires_restart=True,
            operator_implication="Saved v3 preferences are operator UI context until env/config changes are applied and the app restarts; they are not live execution permissions.",
            next_action="Open /v3/settings, edit AI/arbitrage/Kalshi preference fields, save, and inspect the settings_preferences_saved audit event.",
            data_state="cached",
        ),
        FeatureStatus(
            "operator.audit_log",
            "Operator audit trail",
            "working",
            "audit",
            True,
            "Layout selections, focus starts, exports, and review actions are recorded locally where their subsystem has audit support.",
            "Audit records are local-first and secret-redacted.",
            "/v3/cockpit",
            "/api/v3/cockpit/export.json",
        ),
    ]

    counts = _counts(rows)
    stub_burndown = build_stub_burndown_map()
    return {
        "app_version": APP_VERSION,
        "items": [row.to_dict() for row in rows],
        "count": len(rows),
        "counts": counts,
        "status_values": ["working", "partial", "config_required", "scaffolded", "disabled", "unavailable", "error"],
        "data_state_values": DATA_STATE_VALUES,
        "stub_burndown": stub_burndown,
        "visible_feature_count": sum(1 for row in rows if row.visible),
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        **safety_flags(),
    }

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"timestamp": "", "error": "Unreadable feature readiness acknowledgement row."})
        if len(rows) >= max(1, min(int(limit or 50), 500)):
            break
    return rows


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def list_feature_readiness_acknowledgements(limit: int = 50) -> dict[str, Any]:
    rows = _read_jsonl(FEATURE_READINESS_AUDIT_PATH, limit=limit)
    return {
        "app_version": APP_VERSION,
        "items": rows,
        "count": len(rows),
        "audit_path": str(FEATURE_READINESS_AUDIT_PATH),
        "manual_review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "secret_values_returned": False,
        **safety_flags(),
    }


def record_feature_readiness_acknowledgement(
    *,
    operator: str = "local",
    status_filter: str = "",
    area_filter: str = "",
    note: str = "",
    source_route: str = "/v3/feature-readiness",
    source_component: str = "feature_readiness.acknowledgement_form",
) -> dict[str, Any]:
    status_map = build_feature_status_map()
    stub_map = status_map.get("stub_burndown", {})
    feature_items = list(status_map.get("items", []))
    stub_items = list(stub_map.get("items", []))
    combined = feature_items + stub_items
    status_filter = str(status_filter or "").strip()
    area_filter = str(area_filter or "").strip()
    matching = [
        row
        for row in combined
        if (not status_filter or row.get("status") == status_filter)
        and (not area_filter or row.get("area") == area_filter)
    ]
    ack_id = f"readiness_ack_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    row = {
        "acknowledgement_id": ack_id,
        "timestamp": _now_iso(),
        "app_version": APP_VERSION,
        "feature_area": "feature_readiness",
        "action_type": "readiness_review_acknowledgement",
        "action": "acknowledge_status_review",
        "operator": operator or "local",
        "target_id": "feature_readiness_registry",
        "target_name": "Feature readiness and stub burn-down status registry",
        "previous_state": "status_visible",
        "new_state": "review_acknowledged",
        "reason": note or "Operator acknowledged current feature readiness statuses.",
        "status_filter": status_filter,
        "area_filter": area_filter,
        "feature_rows_considered": len(feature_items),
        "stub_rows_considered": len(stub_items),
        "matching_rows_considered": len(matching),
        "status_counts": status_map.get("counts", {}),
        "stub_status_counts": stub_map.get("counts", {}),
        "source_route": source_route,
        "source_component": source_component,
        "data_state": "cached",
        "data_freshness": "local_static_registry",
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    }
    _write_jsonl(FEATURE_READINESS_AUDIT_PATH, row)
    return {"ok": True, "item": row, "recorded": True, **safety_flags()}


def build_feature_readiness_context(status_filter: str = "", area_filter: str = "", limit: int = 50) -> dict[str, Any]:
    status_map = build_feature_status_map()
    stub_map = status_map.get("stub_burndown", {})
    status_filter = str(status_filter or "").strip()
    area_filter = str(area_filter or "").strip()

    def _filtered(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            row
            for row in rows
            if (not status_filter or row.get("status") == status_filter)
            and (not area_filter or row.get("area") == area_filter)
        ]

    feature_rows = list(status_map.get("items", []))
    stub_rows = list(stub_map.get("items", []))
    areas = sorted({str(row.get("area", "")) for row in feature_rows + stub_rows if row.get("area")})
    statuses = list(dict.fromkeys(list(status_map.get("status_values", [])) + list(stub_map.get("status_values", []))))
    acknowledgements = list_feature_readiness_acknowledgements(limit=limit)
    return {
        "app_version": APP_VERSION,
        "status_map": status_map,
        "stub_burndown": stub_map,
        "feature_rows": _filtered(feature_rows),
        "stub_rows": _filtered(stub_rows),
        "all_feature_count": len(feature_rows),
        "all_stub_count": len(stub_rows),
        "status_filter": status_filter,
        "area_filter": area_filter,
        "status_values": statuses,
        "area_values": areas,
        "data_state_values": DATA_STATE_VALUES,
        "acknowledgements": acknowledgements,
        "manual_review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "data_state": "cached",
        "data_state_reason": "Feature readiness is a local/static registry plus local acknowledgement audit rows. It performs no live probes.",
        "operator_implication": "Use this page to verify visible features before relying on them; acknowledgement records do not enable disabled/config-required/scaffolded features.",
        "secret_values_returned": False,
        **safety_flags(),
    }

