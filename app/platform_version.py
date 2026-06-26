from __future__ import annotations

from typing import Any

from .config import APP_VERSION, APP_VERSION_SHORT
from .platform_safety import safety_flags

RELEASE_TITLE = "Automated Paper Trading Strategy Loop and Simulated Execution"
RELEASE_FAMILY = "v4-operator-workflow-truthfulness"
RELEASE_STAGE = "paper-trading automation release; live execution remains separately gated"
COMPATIBILITY_NOTES = [
    "Preserves v2 live/paper controls and all v3 command center, analytics, simulation, dataset, freshness, task, workspace, and cockpit routes.",
    "Local JSON/JSONL runtime data remains lazily created and excluded from release ZIPs.",
    "Plugin manifests remain metadata-only and do not execute arbitrary code.",
    "Runtime migration planner is non-destructive and does not delete, move, rewrite, or migrate user data automatically.",
    "API schema inventory and response envelope helpers are additive and backward-compatible.",
    "v4 platform and low-risk v3 UX API routes are registered through modular APIRouter modules without changing public paths.",
    "Route ownership registry marks higher-risk families metadata-only or do-not-move-yet until dedicated safety coverage is broader.",
    "Generated manual and inventory artifacts are deterministic, secret-free, and exclude runtime data.",
    "Multi-provider AI Copilot workflows are disabled/mock/dry-run-only by default, redacted, structured-output-oriented, audited by hashes, and draft-only.",
    "Local LLM/Ollama/Gemma/Qwen support is disabled by default, localhost-required, redacted, and governed by the same no-live-mutation boundary.",
    "AI task suggestions require explicit human acceptance before becoming local tasks and never approve trades or mutate live trading state.",
    "ChatGPT connector artifacts are blueprint-only, read-only, disabled by default, auth-required, and forbid live mutation or secret export tools.",
    "AI Edge Research is disabled/mock/dry-run-only by default and creates evidence-backed draft packets with citations, contradictions, missing information, probability drafts, and calibration records.",
    "OpenAI web-search review packets are dry-run and blocked by default unless every explicit web-search gate is enabled.",
    "Local LLM edge review requires app-provided evidence and cannot claim web search.",
    "v4.17 adds automated paper trading with a paper-only strategy runner, simulated broker, local ledger, risk gates, and audit rows.",
    "v4.17 paper automation never calls real submit/cancel APIs and reports paper_only=true plus live_execution_used=false in paper responses.",
    "v4.15 completes the legacy Review Queue page with POST-backed browser/API actions, local JSONL decisions/actions/audit persistence, persisted status refresh, and review-only/live-disabled metadata.",
    "v4.15 hardens v3 Settings with validated UI-safe preference controls, local settings persistence, restart/source labels, no-secret echoing, and audit feedback.",
    "v4.15 hardens Feature Readiness with a browser review page, filtered acknowledgements, local JSONL audit rows, and truthful working/partial/config-required/scaffolded/disabled labels.",
    "v4.14 adds a first-class Feature Readiness page backed by the feature-status and stub burn-down registries.",
    "v4.14 adds local readiness acknowledgement records with filters, counts, source metadata, review-only/live-disabled flags, and no-live-mutation evidence.",
    "v4.14 makes opportunity review data mode explicit, labels row data state, and persists source metadata in notes/status audit rows.",
    "v4.13 makes arbitrage scan snapshot persistence a visible POST workflow with feedback, enriched audit rows, and data-state labels.",
    "v4.13 extends feature-readiness and stub burn-down rows with operator implication, next action, data state, safe review-only, live-disabled, and error-status fields.",
    "v4.12 completes browser-visible AI odds adjustment actions with redirect feedback, saved draft records, review decision forms, and latest-record lookup.",
    "v4.12 expands arbitrage review actions to review, watchlist, ignore, and reject decisions with local audit persistence and feedback.",
    "v4.11 adds a first-class stub burn-down map for working, partial, disabled, config-required, unavailable, needs-tests, needs-UI-wiring, needs-backend-wiring, and needs-docs surfaces.",
    "v4.11 replaces remaining visible Workspace and AI POST-only API links with browser-safe POST-backed page forms and feedback redirects.",
    "v4.10 replaces visible POST-only API links in review surfaces with browser-safe POST-backed page forms.",
    "v4.10 hardens arbitrage review actions so GET is informational and POST records local review decisions.",
    "v4.10 expands feature-status surfacing for opportunity review actions, AI odds page actions, arbitrage review actions, and AI/arbitrage configuration.",
    "v4.8 replaces the hidden 2.5 pp odds-adjustment ceiling with configurable raw, evidence-weighted, and final risk-controlled adjustment fields.",
    "v4.8 adds cross-market arbitrage candidate detection across Polymarket, Kalshi, and disabled future venue scaffolds without autonomous execution.",
    "v4.7 adds the AI News Odds Adjustment Engine for source-weighted draft fair-probability updates from web-search or manual evidence.",
    "v4.6 adds the Opportunity Review Workbench for review statuses, operator notes, watchlist state, paper-review draft queues, and AI Edge packet lifecycle visibility.",
    "Market Detail / Opportunity Review pages label Recommended Side explicitly as YES, NO, HOLD, NEEDS REVIEW, or INSUFFICIENT DATA.",
    "Favorite ranking is separated from draft wager edge; group favorite does not imply positive edge.",
    "Market Family Comparison pages compare mutually exclusive outcomes by market price, model fair, and draft edge without implying trade approval.",
    "AI Edge packet lifecycle states remain draft/review-only and never submit, cancel, approve, or arm live trading.",
    "The Unified Surface sidebar renders one desktop Unified Surface heading; mobile headings are distinct to avoid duplicate sidebar groups.",
    "Software identity remains Polymarket OP Console and package slug remains polymarket-op-console.",
    "GitHub repository identity is https://github.com/samgabsi/polymarket-op-console.",
]
DOCS_INDEX = [
    "docs/RELEASE_NOTES_v4.17.0-real.md",
    "docs/VALIDATION_v4.17.0-real.md",
    "docs/OPERATOR_NOTES_v4.17.0-real.md",
    "docs/PAPER_TRADING_v4.17.0-real.md",
    "docs/STUB_BURNDOWN_MAP_v4.17.0-real.md",
    "docs/OPERATOR_ACCEPTANCE_CHECKLIST.md",
    "docs/RELEASE_NOTES_v4.15.0-real.md",
    "docs/VALIDATION_v4.15.0-real.md",
    "docs/OPERATOR_NOTES_v4.15.0-real.md",
    "docs/RELEASE_NOTES_v4.7.0-real.md",
    "docs/VALIDATION_v4.7.0-real.md",
]


def version_metadata() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "version_short": APP_VERSION_SHORT,
        "release_family": RELEASE_FAMILY,
        "release_title": RELEASE_TITLE,
        "release_stage": RELEASE_STAGE,
        "release_date": "operator-defined",
        "compatibility_notes": COMPATIBILITY_NOTES,
        "docs_index": DOCS_INDEX,
        "changelog_reference": "docs/RELEASE_NOTES_v4.17.0-real.md",
        "safety_posture": "fail-closed for live execution, automated paper trading only when paper gates are enabled, no real order placement or cancellation from paper automation",
    })
