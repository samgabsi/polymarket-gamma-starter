from __future__ import annotations

from typing import Any

from .config import APP_VERSION, settings
from . import ai_openai_client
from .ai_news_odds import build_market_search_plan, normalize_source_url, canonicalize_source_domain
from .platform_safety import redact_data, redact_text, safety_flags, secret_scan


def build_news_search_requests(market: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    plan = build_market_search_plan(market, operator_notes=config.get("operator_notes"), prior_context=config.get("prior_context") if isinstance(config.get("prior_context"), dict) else None)
    return safety_flags({
        "version": APP_VERSION,
        "provider": "openai_web_search_or_manual_evidence",
        "market_id_or_slug": plan.get("market_id_or_slug"),
        "requests": plan.get("queries", []),
        "max_queries": getattr(settings, "openai_web_search_max_queries", 5),
        "secrets_included": False,
        "review_only": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
    })


def _web_search_blockers(payload: dict[str, Any] | None = None) -> list[str]:
    payload = payload or {}
    blockers: list[str] = []
    if not getattr(settings, "ai_news_odds_web_search_enabled", False):
        blockers.append("AI_NEWS_ODDS_WEB_SEARCH_ENABLED is false.")
    if not getattr(settings, "openai_enable_api", False):
        blockers.append("OPENAI_ENABLE_API is false.")
    if not getattr(settings, "openai_enable_responses_api", False):
        blockers.append("OPENAI_ENABLE_RESPONSES_API is false.")
    if not getattr(settings, "openai_enable_web_search", False):
        blockers.append("OPENAI_ENABLE_WEB_SEARCH is false.")
    if getattr(settings, "openai_dry_run_only", True):
        blockers.append("OPENAI_DRY_RUN_ONLY is true.")
    if getattr(settings, "openai_require_operator_approval", True) and not payload.get("operator_approved"):
        blockers.append("Operator approval is required before an OpenAI web search call.")
    if getattr(settings, "openai_web_search_require_operator_confirmation", True) and not payload.get("operator_confirmed_web_search"):
        blockers.append("Operator confirmation is required before web search.")
    if not getattr(settings, "openai_api_key", None):
        blockers.append("OPENAI_API_KEY is not configured.")
    return blockers


def run_openai_web_news_search(requests: list[dict[str, Any]] | dict[str, Any], provider_config: dict[str, Any] | None = None) -> dict[str, Any]:
    provider_config = provider_config or {}
    request_items = requests.get("requests", []) if isinstance(requests, dict) else requests
    if not isinstance(request_items, list):
        request_items = []
    blockers = _web_search_blockers(provider_config)
    if blockers:
        return safety_flags({
            "version": APP_VERSION,
            "ok": True,
            "mode": "dry_run_or_blocked",
            "external_network_called": False,
            "web_search_allowed_now": False,
            "blockers": blockers,
            "request_plan": request_items,
            "items": [],
            "message": "Web search unavailable; add manual evidence or enable a provider.",
            "review_only": True,
            "order_submitted": False,
            "order_cancelled": False,
            "live_trading_armed": False,
        })
    if secret_scan(request_items).get("ok") is not True:
        return safety_flags({"ok": False, "error": "secret_like_search_payload_rejected", "external_network_called": False, "review_only": True})
    input_data = {"queries": request_items, "web_search_required": True, "no_private_data": True}
    response = ai_openai_client.request_structured_output(
        workflow_id="ai_news_odds_web_search",
        template_id="ai_news_odds_web_search",
        instructions="Search the web for source-backed market news. Return cited source metadata only. Do not provide trading instructions.",
        input_data=input_data,
        schema_name="AIReviewSummary",
        input_category="market_data",
        operator_approved=bool(provider_config.get("operator_approved")),
    )
    return safety_flags({
        "version": APP_VERSION,
        "ok": bool(response.get("ok")),
        "mode": response.get("mode"),
        "external_network_called": bool(response.get("external_network_called")),
        "ai_model_called": bool(response.get("ai_model_called")),
        "request_plan": request_items,
        "raw_provider_response_redacted": redact_data(response),
        "items": [],
        "review_only": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
    })


def normalize_news_search_result(result: dict[str, Any]) -> dict[str, Any]:
    safe = redact_data(result)
    url = safe.get("url") or safe.get("source_url") or ""
    return {
        "source_id": safe.get("source_id") or "source_" + canonicalize_source_domain(url).replace(".", "_")[:40],
        "title": redact_text(safe.get("title") or safe.get("headline") or "Untitled source")[:240],
        "url": normalize_source_url(url),
        "canonical_domain": canonicalize_source_domain(url),
        "snippet": redact_text(safe.get("snippet") or safe.get("summary") or safe.get("claim") or "")[:1200],
        "published_at": redact_text(safe.get("published_at") or safe.get("date") or "")[:80],
        "source_type": redact_text(safe.get("source_type") or safe.get("type") or "unknown")[:80],
        "claim_stance": redact_text(safe.get("claim_stance") or safe.get("stance") or "mixed")[:80],
        "review_only": True,
        "secret_values_returned": False,
    }


def build_source_packet(results: list[dict[str, Any]]) -> dict[str, Any]:
    items = [normalize_news_search_result(item) for item in results if isinstance(item, dict)]
    return safety_flags({"version": APP_VERSION, "count": len(items), "items": items, "sources": items, "review_only": True, "secret_values_returned": False, "order_submitted": False, "order_cancelled": False})


def run_manual_evidence_news_analysis(evidence_items: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    items = evidence_items.get("items") or evidence_items.get("sources") or evidence_items.get("evidence") if isinstance(evidence_items, dict) else evidence_items
    if not isinstance(items, list):
        items = []
    packet = build_source_packet(items)
    return safety_flags({"version": APP_VERSION, "mode": "manual_evidence", "manual_evidence_mode_available": True, "external_network_called": False, "items": packet["items"], "sources": packet["items"], "review_only": True, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False})


def run_local_llm_evidence_analysis(evidence_items: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    packet = run_manual_evidence_news_analysis(evidence_items)
    return safety_flags({
        "version": APP_VERSION,
        "mode": "local_llm_evidence_review_preview",
        "local_llm_enabled": bool(getattr(settings, "ai_news_odds_local_llm_enabled", False) and getattr(settings, "local_llm_enable", False)),
        "local_llm_can_browse_web": False,
        "warning": "Local LLM does not browse the web by itself; it can only analyze app-provided evidence packets.",
        "items": packet.get("items", []),
        "external_network_called": False,
        "review_only": True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
    })
