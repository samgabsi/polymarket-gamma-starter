from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from .. import (
    ai_edge_calibration,
    ai_edge_research,
    ai_edge_schemas,
    ai_evidence,
    ai_openai_client,
    ai_operator_copilot,
    ai_prompt_governance,
    ai_schemas,
    ai_suggestions,
    ai_providers,
    ai_local_llm_client,
    ai_model_recommendations,
    market_edge,
)
from ..platform_safety import safety_flags


def create_ai_router(
    *,
    templates: Jinja2Templates,
    context_factory: Callable[[Request, str], dict[str, Any]],
) -> APIRouter:
    router = APIRouter(tags=["v4-ai"])

    @router.get("/v3/ai", response_class=HTMLResponse)
    @router.get("/v3/ai/copilot", response_class=HTMLResponse)
    @router.get("/v3/ai/providers", response_class=HTMLResponse)
    @router.get("/v3/ai/openai", response_class=HTMLResponse)
    @router.get("/v3/ai/local-llm", response_class=HTMLResponse)
    @router.get("/v3/ai/model-recommendations", response_class=HTMLResponse)
    @router.get("/v3/ai/suggestions", response_class=HTMLResponse)
    @router.get("/v3/ai/prompts", response_class=HTMLResponse)
    @router.get("/v3/ai/audit", response_class=HTMLResponse)
    @router.get("/v3/ai/settings", response_class=HTMLResponse)
    @router.get("/v3/ai/chatgpt-connector", response_class=HTMLResponse)
    @router.get("/v3/ai/review-packets", response_class=HTMLResponse)
    @router.get("/v3/ai/edge", response_class=HTMLResponse)
    @router.get("/v3/ai/edge/new", response_class=HTMLResponse)
    @router.get("/v3/ai/edge/packets", response_class=HTMLResponse)
    @router.get("/v3/ai/edge/packet/{packet_id}", response_class=HTMLResponse)
    @router.get("/v3/ai/edge/evidence", response_class=HTMLResponse)
    @router.get("/v3/ai/edge/calibration", response_class=HTMLResponse)
    @router.get("/v3/ai/edge/settings", response_class=HTMLResponse)
    @router.get("/v3/ai/edge/market/{market_id_or_slug}", response_class=HTMLResponse)
    async def v3_ai_page(request: Request):
        return templates.TemplateResponse("live_v3_dashboard.html", context_factory(request, "ai"))

    @router.get("/api/v3/ai/summary")
    async def api_v3_ai_summary():
        return ai_suggestions.ai_summary()

    @router.get("/api/v3/ai/settings")
    async def api_v3_ai_settings():
        return ai_suggestions.ai_settings_summary()

    @router.post("/api/v3/ai/settings")
    async def api_v3_ai_settings_post(payload: dict[str, Any] = Body(default_factory=dict)):
        allowed = {
            "ai_enable",
            "ai_provider",
            "ai_dry_run_only",
            "ai_redact_before_send",
            "ai_require_operator_approval",
            "ai_allow_network",
            "openai_enable_api",
            "openai_enable_responses_api",
            "openai_dry_run_only",
            "openai_redact_before_send",
            "openai_require_operator_approval",
            "local_llm_enable",
            "local_llm_provider",
            "local_llm_model",
            "local_llm_base_url",
        }
        requested = {key: (bool(value) if not key.endswith(("provider", "model", "base_url")) else str(value)) for key, value in payload.items() if key in allowed}
        return safety_flags({
            "ok": True,
            "persisted": False,
            "reason": "AI settings are environment-driven in v4.7.0-real; POST returns a safe preview only.",
            "requested_settings_preview": requested,
            "settings": ai_suggestions.ai_settings_summary(),
            "no_live_mutation": True,
            "secret_values_returned": False,
        })

    @router.get("/api/v3/ai/edge/summary")
    async def api_v3_ai_edge_summary():
        return ai_edge_research.edge_summary()

    @router.post("/api/v3/ai/edge/market/analyze")
    async def api_v3_ai_edge_market_analyze(payload: dict[str, Any] = Body(default_factory=dict)):
        recommendation = market_edge.build_market_recommendation_row(payload, model_context=payload.get("model_context") if isinstance(payload.get("model_context"), dict) else None)
        packet_payload = {
            **payload,
            "title": payload.get("title") or payload.get("market_title") or payload.get("question") or "AI Edge Market Row Analysis",
            "market_id": recommendation.get("market_id"),
            "market_title": recommendation.get("question"),
            "market_yes_price": recommendation.get("market_yes_price"),
            "market_no_price": recommendation.get("market_no_price"),
            "model_fair_yes": recommendation.get("model_fair_yes"),
            "model_fair_no": recommendation.get("model_fair_no"),
            "recommended_side": recommendation.get("recommended_side"),
            "side_badge": recommendation.get("side_badge"),
            "edge_explanation": recommendation.get("explanation"),
            "family_id": recommendation.get("family_id"),
            "group_rank_label": recommendation.get("group_rank_label"),
            "model_fair_source": recommendation.get("model_fair_source"),
            "research_question": payload.get("research_question") or f"Review the draft market edge for {recommendation.get('question')}",
        }
        packet = ai_edge_research.generate_edge_packet(packet_payload, write=bool(payload.get("write", False)), mode="market_row_analysis")
        return safety_flags({
            "version": recommendation.get("app_version"),
            "market_recommendation": recommendation,
            "packet": packet.get("packet"),
            "write": bool(payload.get("write", False)),
            "draft_review_only": True,
            "not_financial_advice": True,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "live_trading_armed": False,
            "no_live_mutation": True,
        })

    @router.get("/api/v3/ai/edge/market/{market_id_or_slug}/summary")
    async def api_v3_ai_edge_market_summary(market_id_or_slug: str):
        return safety_flags({
            "version": ai_edge_research.APP_VERSION if hasattr(ai_edge_research, "APP_VERSION") else "4.7.0-real",
            "market_id_or_slug": market_id_or_slug,
            "summary": "Market-row AI Edge summary endpoint is wired for review-only packets. Provide current prices/model fair probability to POST /api/v3/ai/edge/market/analyze for a deterministic recommendation.",
            "legend": market_edge.edge_recommendation_legend(),
            "draft_review_only": True,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "live_trading_armed": False,
            "no_live_mutation": True,
        })

    @router.get("/api/v3/ai/edge/market/{market_id_or_slug}/packet")
    async def api_v3_ai_edge_market_packet(market_id_or_slug: str):
        packets = ai_edge_research.list_packets(limit=500).get("items", [])
        matched = [packet for packet in packets if str(packet.get("market_id") or packet.get("market_slug") or "") == str(market_id_or_slug)]
        return safety_flags({
            "version": ai_edge_research.APP_VERSION if hasattr(ai_edge_research, "APP_VERSION") else "4.7.0-real",
            "market_id_or_slug": market_id_or_slug,
            "count": len(matched),
            "items": matched,
            "draft_review_only": True,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "live_trading_armed": False,
            "no_live_mutation": True,
        })

    @router.get("/api/v3/ai/edge/family/{family_id}/summary")
    async def api_v3_ai_edge_family_summary(family_id: str):
        return safety_flags({
            "version": ai_edge_research.APP_VERSION if hasattr(ai_edge_research, "APP_VERSION") else "4.7.0-real",
            "family_id": family_id,
            "summary": "Family comparison endpoint is wired as a review-only helper. Favorite rank is not the same thing as edge.",
            "favorite_vs_edge": market_edge.FAVORITE_VS_EDGE_EXPLAINER,
            "favorite_ranking_does_not_imply_edge": True,
            "legend": market_edge.edge_recommendation_legend(),
            "draft_review_only": True,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "live_trading_armed": False,
            "no_live_mutation": True,
        })

    @router.get("/api/v3/ai/edge/settings")
    async def api_v3_ai_edge_settings():
        return ai_edge_research.edge_settings_summary()

    @router.post("/api/v3/ai/edge/settings")
    async def api_v3_ai_edge_settings_post(payload: dict[str, Any] = Body(default_factory=dict)):
        allowed = {
            "ai_edge_enable",
            "ai_edge_provider",
            "ai_edge_dry_run_only",
            "ai_edge_require_operator_approval",
            "ai_edge_allow_web_search",
            "ai_edge_allow_market_context",
            "ai_edge_allow_runtime_data",
            "ai_edge_allow_source_urls",
            "ai_edge_allow_model_probability_drafts",
            "ai_edge_allow_market_implied_comparison",
            "ai_edge_allow_calibration_tracking",
            "openai_enable_web_search",
            "openai_web_search_require_operator_confirmation",
            "local_llm_enable_edge_review",
            "local_llm_edge_can_search_web",
            "edge_min_yes_pp",
            "edge_min_no_pp",
            "edge_min_liquidity",
            "edge_min_volume_24h",
            "edge_require_fresh_data",
            "edge_max_data_age_minutes",
            "edge_show_favorite_rank",
            "edge_show_family_groups",
            "edge_show_ai_edge_actions",
            "edge_default_recommendation_mode",
        }
        requested = {key: (str(value) if key.endswith(("provider", "model")) else bool(value)) for key, value in payload.items() if key in allowed}
        return safety_flags({
            "ok": True,
            "persisted": False,
            "reason": "AI Edge settings are environment-driven in v4.7.0-real; POST returns a safe preview only.",
            "requested_settings_preview": requested,
            "settings": ai_edge_research.edge_settings_summary(),
            "no_live_mutation": True,
            "secret_values_returned": False,
        })

    @router.get("/api/v3/ai/edge/schemas")
    async def api_v3_ai_edge_schemas():
        return ai_edge_schemas.schema_registry()

    @router.get("/api/v3/ai/edge/packets")
    async def api_v3_ai_edge_packets(limit: int = 250, status: str = "", include_archived: bool = False):
        return ai_edge_research.list_packets(limit=limit, status=status or None, include_archived=include_archived)

    @router.post("/api/v3/ai/edge/packets/generate")
    async def api_v3_ai_edge_packets_generate(payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_edge_research.generate_edge_packet(payload, write=bool(payload.get("write", True)))

    @router.post("/api/v3/ai/edge/research/dry-run")
    async def api_v3_ai_edge_research_dry_run(payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_edge_research.research_dry_run(payload)

    @router.post("/api/v3/ai/edge/openai-web-dry-run")
    async def api_v3_ai_edge_openai_web_dry_run(payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_edge_research.openai_web_search_dry_run(payload)

    @router.post("/api/v3/ai/edge/local-llm/review")
    async def api_v3_ai_edge_local_llm_review(payload: dict[str, Any] = Body(default_factory=dict)):
        normalized = ai_evidence.normalize_evidence(payload, write=False, include_demo_when_empty=False)
        return ai_edge_research.local_llm_edge_review(payload, normalized["items"])

    @router.get("/api/v3/ai/edge/evidence")
    async def api_v3_ai_edge_evidence(limit: int = 250, stance: str = ""):
        return ai_evidence.list_evidence_sources(limit=limit, stance=stance or None)

    @router.post("/api/v3/ai/edge/evidence/normalize")
    async def api_v3_ai_edge_evidence_normalize(payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_evidence.normalize_evidence(payload, write=bool(payload.get("write", False)), include_demo_when_empty=bool(payload.get("include_demo_when_empty", False)))

    @router.get("/api/v3/ai/edge/calibration")
    async def api_v3_ai_edge_calibration(limit: int = 250, status: str = ""):
        return ai_edge_calibration.list_records(limit=limit, status=status or None)

    @router.post("/api/v3/ai/edge/calibration/outcome")
    async def api_v3_ai_edge_calibration_outcome(payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_edge_calibration.record_outcome(payload, write=bool(payload.get("write", True)))

    @router.get("/api/v3/ai/edge/calibration/summary")
    async def api_v3_ai_edge_calibration_summary():
        return ai_edge_calibration.calibration_summary()

    @router.get("/api/v3/ai/edge/export.json", response_class=PlainTextResponse)
    async def api_v3_ai_edge_export_json():
        return PlainTextResponse(json.dumps(ai_edge_research.export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/ai/edge/export.md", response_class=PlainTextResponse)
    async def api_v3_ai_edge_export_md():
        return PlainTextResponse(ai_edge_research.export_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/ai/edge/export.csv", response_class=PlainTextResponse)
    async def api_v3_ai_edge_export_csv():
        return PlainTextResponse(ai_edge_research.export_csv(), media_type="text/csv; charset=utf-8")

    @router.get("/api/v3/ai/edge/evidence/export.json", response_class=PlainTextResponse)
    async def api_v3_ai_edge_evidence_export_json():
        return PlainTextResponse(json.dumps(ai_evidence.export_evidence_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/ai/edge/evidence/export.md", response_class=PlainTextResponse)
    async def api_v3_ai_edge_evidence_export_md():
        return PlainTextResponse(ai_evidence.export_evidence_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/ai/edge/calibration/export.json", response_class=PlainTextResponse)
    async def api_v3_ai_edge_calibration_export_json():
        return PlainTextResponse(json.dumps(ai_edge_calibration.export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/ai/edge/calibration/export.md", response_class=PlainTextResponse)
    async def api_v3_ai_edge_calibration_export_md():
        return PlainTextResponse(ai_edge_calibration.export_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/ai/edge/calibration/export.csv", response_class=PlainTextResponse)
    async def api_v3_ai_edge_calibration_export_csv():
        return PlainTextResponse(ai_edge_calibration.export_csv(), media_type="text/csv; charset=utf-8")

    @router.get("/api/v3/ai/edge/packets/{packet_id}")
    @router.get("/api/v3/ai/edge/packet/{packet_id}")
    async def api_v3_ai_edge_packet_detail(packet_id: str):
        return ai_edge_research.get_packet(packet_id)

    @router.get("/api/v3/ai/edge/packet/{packet_id}/lifecycle")
    async def api_v3_ai_edge_packet_lifecycle(packet_id: str):
        return ai_edge_research.packet_lifecycle(packet_id)

    @router.post("/api/v3/ai/edge/packets/{packet_id}/review")
    @router.post("/api/v3/ai/edge/packet/{packet_id}/review")
    async def api_v3_ai_edge_packet_review(packet_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_edge_research.review_packet(packet_id, payload)

    @router.post("/api/v3/ai/edge/packets/{packet_id}/archive")
    @router.post("/api/v3/ai/edge/packet/{packet_id}/archive")
    async def api_v3_ai_edge_packet_archive(packet_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_edge_research.archive_packet(packet_id, payload)

    @router.get("/api/v3/ai/providers")
    async def api_v3_ai_providers():
        return ai_providers.list_providers()

    @router.get("/api/v3/ai/providers/health")
    async def api_v3_ai_providers_health():
        return ai_providers.providers_health(dry_run=True)

    @router.post("/api/v3/ai/providers/test-dry-run")
    async def api_v3_ai_providers_test_dry_run(payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_providers.test_dry_run(payload)

    @router.get("/api/v3/ai/openai/status")
    async def api_v3_ai_openai_status():
        return ai_openai_client.openai_settings_summary()

    @router.get("/api/v3/ai/local-llm/status")
    async def api_v3_ai_local_llm_status():
        return ai_local_llm_client.local_llm_settings_summary()

    @router.get("/api/v3/ai/model-recommendations")
    async def api_v3_ai_model_recommendations():
        return ai_model_recommendations.list_model_recommendations()

    @router.get("/api/v3/ai/prompts")
    async def api_v3_ai_prompts():
        return ai_prompt_governance.list_prompt_templates()

    @router.get("/api/v3/ai/schemas")
    async def api_v3_ai_schemas():
        return ai_schemas.schema_registry()

    @router.get("/api/v3/ai/suggestions")
    async def api_v3_ai_suggestions(limit: int = 250, status: str = ""):
        return ai_suggestions.list_suggestions(limit=limit, status=status or None)

    @router.post("/api/v3/ai/suggestions/generate")
    async def api_v3_ai_suggestions_generate(payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_suggestions.generate_suggestions(payload, write=bool(payload.get("write", True)))

    @router.post("/api/v3/ai/suggestions/{suggestion_id}/accept")
    async def api_v3_ai_suggestions_accept(suggestion_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_suggestions.accept_suggestion(suggestion_id, payload)

    @router.post("/api/v3/ai/suggestions/{suggestion_id}/dismiss")
    async def api_v3_ai_suggestions_dismiss(suggestion_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_suggestions.dismiss_suggestion(suggestion_id, payload)

    @router.get("/api/v3/ai/audit")
    async def api_v3_ai_audit(limit: int = 250):
        return ai_openai_client.list_audit_records(limit=limit)

    @router.post("/api/v3/ai/copilot/dry-run")
    async def api_v3_ai_copilot_dry_run(payload: dict[str, Any] = Body(default_factory=dict)):
        workflow_id = str(payload.get("workflow_id") or "summarize_daily_review_context")
        return ai_operator_copilot.run_copilot_workflow(workflow_id, {**payload, "operator_approved": False}, operator_approved=False)

    @router.post("/api/v3/ai/copilot/review")
    async def api_v3_ai_copilot_review(payload: dict[str, Any] = Body(default_factory=dict)):
        workflow_id = str(payload.get("workflow_id") or "summarize_daily_review_context")
        return ai_operator_copilot.run_copilot_workflow(workflow_id, payload, operator_approved=bool(payload.get("operator_approved", False)))

    @router.get("/api/v3/ai/review-packets")
    async def api_v3_ai_review_packets(limit: int = 250):
        return ai_suggestions.list_review_packets(limit=limit)

    @router.post("/api/v3/ai/review-packets/generate")
    async def api_v3_ai_review_packets_generate(payload: dict[str, Any] = Body(default_factory=dict)):
        return ai_suggestions.generate_review_packet(payload, write=bool(payload.get("write", True)))

    @router.get("/api/v3/ai/chatgpt-connector")
    async def api_v3_ai_chatgpt_connector():
        return ai_suggestions.chatgpt_connector_blueprint()

    @router.get("/api/v3/ai/chatgpt-connector/blueprint")
    async def api_v3_ai_chatgpt_connector_blueprint():
        return ai_suggestions.chatgpt_connector_blueprint()

    @router.get("/api/v3/ai/redaction-preview")
    async def api_v3_ai_redaction_preview():
        return ai_suggestions.redaction_preview()

    @router.get("/api/v3/ai/export.json", response_class=PlainTextResponse)
    async def api_v3_ai_export_json():
        return PlainTextResponse(json.dumps(ai_suggestions.export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/ai/export.md", response_class=PlainTextResponse)
    async def api_v3_ai_export_md():
        return PlainTextResponse(ai_suggestions.export_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/ai/suggestions/export.csv", response_class=PlainTextResponse)
    async def api_v3_ai_suggestions_export_csv():
        return PlainTextResponse(ai_suggestions.suggestions_csv(), media_type="text/csv; charset=utf-8")

    @router.get("/api/v3/ai/prompts/export.json", response_class=PlainTextResponse)
    async def api_v3_ai_prompts_export_json():
        return PlainTextResponse(json.dumps(ai_prompt_governance.export_prompt_registry_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/ai/prompts/export.md", response_class=PlainTextResponse)
    async def api_v3_ai_prompts_export_md():
        return PlainTextResponse(ai_prompt_governance.export_prompt_registry_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/ai/providers/export.json", response_class=PlainTextResponse)
    async def api_v3_ai_providers_export_json():
        return PlainTextResponse(json.dumps(ai_providers.export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/ai/providers/export.md", response_class=PlainTextResponse)
    async def api_v3_ai_providers_export_md():
        return PlainTextResponse(ai_providers.export_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/ai/model-recommendations/export.json", response_class=PlainTextResponse)
    async def api_v3_ai_model_recommendations_export_json():
        return PlainTextResponse(ai_model_recommendations.export_json_text(), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/ai/model-recommendations/export.md", response_class=PlainTextResponse)
    async def api_v3_ai_model_recommendations_export_md():
        return PlainTextResponse(ai_model_recommendations.export_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/ai/audit/export.md", response_class=PlainTextResponse)
    async def api_v3_ai_audit_export_md():
        return PlainTextResponse(ai_openai_client.export_audit_markdown(), media_type="text/markdown; charset=utf-8")

    return router
