from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import ai_edge_calibration, ai_evidence, ai_openai_client
from .ai_edge_schemas import AI_EDGE_SAFETY_STATEMENT, base_safety, default_probability_draft, record_id, schema_registry, validate_packet
from .config import APP_VERSION, DATA_DIR, settings
from .platform_safety import redact_data, redact_text, safety_flags, secret_scan
from .opportunity_review import AI_EDGE_PACKET_LIFECYCLE_STATES, build_packet_lifecycle_summary, normalize_review_status

EDGE_DIR = DATA_DIR / "ai" / "edge"
RESEARCH_PACKETS_PATH = EDGE_DIR / "research_packets.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    EDGE_DIR.mkdir(parents=True, exist_ok=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_dir()
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
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(redact_data(parsed))
        except json.JSONDecodeError:
            rows.append({"packet_id": record_id("edge_packet_invalid"), "status": "invalid_json", "secret_values_returned": False})
    return rows


def _latest_by_id(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[str(row.get(key) or record_id("edge_packet"))] = row
    return sorted(latest.values(), key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)


def edge_settings_summary() -> dict[str, Any]:
    safe_default = (
        settings.ai_edge_enable is False
        and settings.ai_edge_provider == "mock"
        and settings.ai_edge_dry_run_only is True
        and settings.ai_edge_require_operator_approval is True
        and settings.ai_edge_allow_web_search is False
        and settings.openai_enable_web_search is False
        and settings.ai_edge_allow_market_implied_comparison is False
        and settings.ai_edge_redact_before_send is True
        and settings.ai_edge_store_raw_prompts is False
        and settings.ai_edge_store_raw_responses is False
        and settings.local_llm_enable_edge_review is False
        and settings.local_llm_edge_requires_app_evidence is True
        and settings.local_llm_edge_can_search_web is False
    )
    return safety_flags({
        "version": APP_VERSION,
        "safe_default_posture": safe_default,
        "ai_edge_enable": settings.ai_edge_enable,
        "ai_edge_provider": settings.ai_edge_provider,
        "ai_edge_dry_run_only": settings.ai_edge_dry_run_only,
        "ai_edge_require_operator_approval": settings.ai_edge_require_operator_approval,
        "ai_edge_allow_web_search": settings.ai_edge_allow_web_search,
        "ai_edge_allow_market_context": settings.ai_edge_allow_market_context,
        "ai_edge_allow_runtime_data": settings.ai_edge_allow_runtime_data,
        "ai_edge_allow_source_urls": settings.ai_edge_allow_source_urls,
        "ai_edge_allow_model_probability_drafts": settings.ai_edge_allow_model_probability_drafts,
        "ai_edge_allow_market_implied_comparison": settings.ai_edge_allow_market_implied_comparison,
        "ai_edge_allow_calibration_tracking": settings.ai_edge_allow_calibration_tracking,
        "ai_edge_redact_before_send": settings.ai_edge_redact_before_send,
        "ai_edge_store_raw_prompts": settings.ai_edge_store_raw_prompts,
        "ai_edge_store_raw_responses": settings.ai_edge_store_raw_responses,
        "ai_edge_log_prompt_hashes_only": settings.ai_edge_log_prompt_hashes_only,
        "ai_edge_max_input_chars": settings.ai_edge_max_input_chars,
        "ai_edge_max_output_tokens": settings.ai_edge_max_output_tokens,
        "ai_edge_timeout_seconds": settings.ai_edge_timeout_seconds,
        "openai_enable_web_search": settings.openai_enable_web_search,
        "openai_web_search_require_operator_confirmation": settings.openai_web_search_require_operator_confirmation,
        "openai_web_search_max_queries": settings.openai_web_search_max_queries,
        "openai_web_search_max_sources": settings.openai_web_search_max_sources,
        "openai_web_search_require_citations": settings.openai_web_search_require_citations,
        "openai_web_search_recency_required": settings.openai_web_search_recency_required,
        "openai_web_search_allow_market_research": settings.openai_web_search_allow_market_research,
        "openai_web_search_allow_private_data": settings.openai_web_search_allow_private_data,
        "local_llm_enable_edge_review": settings.local_llm_enable_edge_review,
        "local_llm_edge_requires_app_evidence": settings.local_llm_edge_requires_app_evidence,
        "local_llm_edge_can_search_web": settings.local_llm_edge_can_search_web,
        "local_llm_edge_model": settings.local_llm_edge_model,
        "local_llm_edge_max_input_chars": settings.local_llm_edge_max_input_chars,
        "local_llm_edge_timeout_seconds": settings.local_llm_edge_timeout_seconds,
        "edge_min_yes_pp": settings.edge_min_yes_pp,
        "edge_min_no_pp": settings.edge_min_no_pp,
        "edge_min_liquidity": settings.edge_min_liquidity,
        "edge_min_volume_24h": settings.edge_min_volume_24h,
        "edge_require_fresh_data": settings.edge_require_fresh_data,
        "edge_max_data_age_minutes": settings.edge_max_data_age_minutes,
        "edge_show_favorite_rank": settings.edge_show_favorite_rank,
        "edge_show_family_groups": settings.edge_show_family_groups,
        "edge_show_ai_edge_actions": settings.edge_show_ai_edge_actions,
        "edge_default_recommendation_mode": settings.edge_default_recommendation_mode,
        "opportunity_review_enabled": getattr(settings, "opportunity_review_enabled", True),
        "opportunity_notes_enabled": getattr(settings, "opportunity_notes_enabled", True),
        "ai_edge_packet_lifecycle_enabled": getattr(settings, "ai_edge_packet_lifecycle_enabled", True),
        "ai_edge_review_only": getattr(settings, "ai_edge_review_only", True),
        "watchlist_review_only": getattr(settings, "watchlist_review_only", True),
        "paper_review_draft_only": getattr(settings, "paper_review_draft_only", True),
        "ai_edge_packet_lifecycle_states": AI_EDGE_PACKET_LIFECYCLE_STATES,
        "runtime_storage_namespace": "data/ai/edge/",
        "runtime_records_excluded_from_release_zip": True,
        **base_safety(),
    })


def edge_summary() -> dict[str, Any]:
    packets = list_packets(limit=1000)["items"]
    evidence = ai_evidence.list_evidence_sources(limit=1000)["items"]
    calibration = ai_edge_calibration.calibration_summary()
    return safety_flags({
        "version": APP_VERSION,
        "settings": edge_settings_summary(),
        "packet_count": len(packets),
        "active_packet_count": len([packet for packet in packets if packet.get("status") != "archived"]),
        "evidence_source_count": len(evidence),
        "calibration": calibration,
        "api_routes": [
            "/api/v3/ai/edge/summary",
            "/api/v3/ai/edge/settings",
            "/api/v3/ai/edge/packets",
            "/api/v3/ai/edge/research/dry-run",
            "/api/v3/ai/edge/openai-web-dry-run",
            "/api/v3/ai/edge/calibration",
            "/api/v3/ai/edge/market/analyze",
            "/api/v3/ai/edge/market/{market_id_or_slug}/summary",
            "/api/v3/ai/edge/market/{market_id_or_slug}/packet",
            "/api/v3/ai/edge/family/{family_id}/summary",
            "/api/v3/ai/edge/packet/{packet_id}",
            "/api/v3/ai/edge/packet/{packet_id}/review",
            "/api/v3/ai/edge/packet/{packet_id}/archive",
            "/api/v3/ai/news-odds/market/{market_id_or_slug}/adjust",
            "/api/v3/ai/news-odds/adjustments",
        ],
        "ui_routes": ["/v3/ai/edge", "/v3/ai/edge/new", "/v3/ai/edge/packets", "/v3/ai/edge/packet/{packet_id}", "/v3/ai/edge/evidence", "/v3/ai/edge/calibration", "/v3/ai/edge/settings", "/v3/ai/edge/market/{market_id_or_slug}", "/v3/ai/edge/family/{family_id}", "/v3/ai/news-odds", "/v3/ai/news-odds/adjustments"],
        "packet_lifecycle_states": AI_EDGE_PACKET_LIFECYCLE_STATES,
        **base_safety(),
    })


def openai_web_search_request_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    raw_queries = payload.get("queries") or payload.get("web_search_queries") or payload.get("query") or payload.get("research_question") or []
    if isinstance(raw_queries, str):
        raw_queries = [raw_queries]
    queries = [redact_text(query)[:220] for query in raw_queries if str(query).strip()]
    if not queries:
        queries = [redact_text(payload.get("market_title") or "Polymarket market research question")[:220]]
    queries = queries[: max(1, min(settings.openai_web_search_max_queries, 20))]
    blockers: list[str] = []
    if not settings.ai_edge_enable:
        blockers.append("AI_EDGE_ENABLE is false.")
    if not settings.ai_edge_allow_web_search:
        blockers.append("AI_EDGE_ALLOW_WEB_SEARCH is false.")
    if not settings.openai_enable_web_search:
        blockers.append("OPENAI_ENABLE_WEB_SEARCH is false.")
    if settings.openai_dry_run_only or settings.ai_edge_dry_run_only:
        blockers.append("AI/OpenAI dry-run-only mode is active.")
    if settings.openai_web_search_require_operator_confirmation and not payload.get("operator_confirmed_web_search"):
        blockers.append("OPENAI_WEB_SEARCH_REQUIRE_OPERATOR_CONFIRMATION is true and operator_confirmed_web_search was not supplied.")
    if settings.openai_web_search_allow_private_data is False and payload.get("contains_private_data"):
        blockers.append("OPENAI_WEB_SEARCH_ALLOW_PRIVATE_DATA is false.")
    return safety_flags({
        "version": APP_VERSION,
        "web_search_request_built": True,
        "web_search_allowed_now": not blockers,
        "blockers": blockers,
        "queries": queries,
        "max_sources": settings.openai_web_search_max_sources,
        "require_citations": settings.openai_web_search_require_citations,
        "recency_required": settings.openai_web_search_recency_required,
        "allow_market_research": settings.openai_web_search_allow_market_research,
        "allow_private_data": settings.openai_web_search_allow_private_data,
        "external_network_called": False,
        "openai_api_called": False,
        "raw_private_data_included": False,
        **base_safety(),
    })


def local_llm_edge_review(payload: dict[str, Any] | None = None, evidence_sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = payload or {}
    evidence_sources = evidence_sources or []
    blockers: list[str] = []
    if not settings.local_llm_enable_edge_review:
        blockers.append("LOCAL_LLM_ENABLE_EDGE_REVIEW is false.")
    if settings.local_llm_edge_requires_app_evidence and not evidence_sources:
        blockers.append("LOCAL_LLM_EDGE_REQUIRES_APP_EVIDENCE is true and no app-provided evidence was supplied.")
    if settings.local_llm_edge_can_search_web:
        blockers.append("LOCAL_LLM_EDGE_CAN_SEARCH_WEB must remain false for packaged edge review.")
    if settings.ai_edge_dry_run_only:
        blockers.append("AI_EDGE_DRY_RUN_ONLY is true.")
    return safety_flags({
        "version": APP_VERSION,
        "provider": "local_llm",
        "model": settings.local_llm_edge_model,
        "status": "dry_run" if blockers else "ready_for_operator_approved_local_review",
        "blockers": blockers,
        "review_summary": "Local LLM edge review is constrained to app-provided evidence and does not search the web.",
        "evidence_source_count": len(evidence_sources),
        "local_llm_claimed_web_search": False,
        "local_llm_edge_requires_app_evidence": settings.local_llm_edge_requires_app_evidence,
        "local_llm_edge_can_search_web": settings.local_llm_edge_can_search_web,
        "external_network_called": False,
        "ai_model_called": False,
        "raw_prompt_stored": False,
        "raw_response_stored": False,
        **base_safety(),
    })


def _probability_from_evidence(payload: dict[str, Any], evidence_sources: list[dict[str, Any]]) -> dict[str, Any]:
    if not settings.ai_edge_allow_model_probability_drafts:
        probability = default_probability_draft(None)
        probability.update({
            "model_probability": None,
            "fair_probability": None,
            "confidence": "blocked",
            "rationale": "AI_EDGE_ALLOW_MODEL_PROBABILITY_DRAFTS is false.",
            "blockers": ["Model probability drafts are disabled."],
        })
        return probability
    explicit = payload.get("fair_probability", payload.get("model_probability", payload.get("draft_probability")))
    if explicit is not None:
        probability = default_probability_draft(float(explicit))
        probability["confidence"] = "operator_supplied"
        probability["rationale"] = "Operator supplied the draft probability input; AI did not fetch market prices."
        return probability
    supports = len([src for src in evidence_sources if src.get("claim_stance") == "supports"])
    contradicts = len([src for src in evidence_sources if src.get("claim_stance") == "contradicts"])
    mixed = len([src for src in evidence_sources if src.get("claim_stance") == "mixed"])
    value = max(0.05, min(0.95, 0.5 + (supports - contradicts) * 0.08 + mixed * 0.01))
    probability = default_probability_draft(round(value, 4))
    probability["confidence"] = "low" if len(evidence_sources) < 3 else "medium"
    probability["rationale"] = "Deterministic draft based on app-provided evidence stance counts; not a pricing model and not a trade signal."
    probability["evidence_stance_counts"] = {"supports": supports, "contradicts": contradicts, "mixed": mixed, "unknown": len(evidence_sources) - supports - contradicts - mixed}
    return probability


def _market_implied_comparison(payload: dict[str, Any], probability: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("market_implied_probability")
    if raw is None:
        return {"included": False, "reason": "No market_implied_probability was supplied."}
    try:
        market_probability = max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return {"included": False, "reason": "market_implied_probability was not numeric."}
    if not settings.ai_edge_allow_market_implied_comparison or not settings.ai_edge_allow_market_context:
        return {
            "included": False,
            "market_implied_probability_redacted": True,
            "reason": "AI_EDGE_ALLOW_MARKET_IMPLIED_COMPARISON and AI_EDGE_ALLOW_MARKET_CONTEXT are false by default.",
        }
    fair_probability = probability.get("fair_probability")
    edge = None if fair_probability is None else round(float(fair_probability) - market_probability, 4)
    return {
        "included": True,
        "market_implied_probability": market_probability,
        "draft_fair_probability": fair_probability,
        "draft_edge": edge,
        "research_only": True,
        "not_financial_advice": True,
        "no_trade_approval": True,
    }


def _findings_from_sources(evidence_sources: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    missing: list[str] = []
    for source in evidence_sources:
        citation = source.get("citation_label")
        stance = source.get("claim_stance") or "unknown"
        finding = {
            "claim": source.get("snippet") or source.get("title"),
            "citation_labels": [citation] if citation else [],
            "stance": stance,
            "confidence": "medium" if source.get("quality_score", 0) >= 0.7 else "low",
            "source_id": source.get("source_id"),
        }
        findings.append(finding)
        if stance in {"contradicts", "mixed"}:
            contradictions.append({
                "source_id": source.get("source_id"),
                "citation_label": citation,
                "title": source.get("title"),
                "stance": stance,
                "issue": "Evidence source does not cleanly support the draft edge thesis.",
            })
    if not evidence_sources:
        missing.append("No app-provided evidence was supplied.")
    if not any(src.get("published_at") for src in evidence_sources):
        missing.append("Published dates are missing for at least some evidence sources.")
    if not any(src.get("url") for src in evidence_sources):
        missing.append("Source URLs are missing or redacted.")
    return findings, contradictions, missing


def generate_edge_packet(payload: dict[str, Any] | None = None, *, write: bool = True, provider: str | None = None, mode: str = "dry_run") -> dict[str, Any]:
    payload = payload or {}
    active_provider = redact_text(provider or payload.get("provider") or settings.ai_edge_provider or "mock")
    safe_payload = ai_openai_client.redact_ai_data(payload) if settings.ai_edge_redact_before_send else redact_data(payload)
    prompt_input = json.dumps(safe_payload, sort_keys=True, default=str)[: settings.ai_edge_max_input_chars]
    prompt_hash = _hash({"workflow": "ai_edge_research_packet", "provider": active_provider, "payload": prompt_input})
    secret_findings = secret_scan(prompt_input)
    include_demo = not any(key in payload for key in ("evidence_sources", "sources", "evidence_urls", "source_urls", "evidence_snippets", "snippets"))
    normalized = ai_evidence.normalize_evidence(payload, write=write, include_demo_when_empty=include_demo)
    evidence_sources = normalized["items"]
    citations = [
        {
            "citation_label": source.get("citation_label"),
            "source_id": source.get("source_id"),
            "title": source.get("title"),
            "url": source.get("url") if settings.ai_edge_allow_source_urls else "",
        }
        for source in evidence_sources
    ]
    findings, contradictions, missing = _findings_from_sources(evidence_sources)
    blockers: list[str] = []
    if not settings.ai_edge_enable:
        blockers.append("AI_EDGE_ENABLE is false.")
    if settings.ai_edge_dry_run_only:
        blockers.append("AI_EDGE_DRY_RUN_ONLY is true.")
    if settings.ai_edge_require_operator_approval and not payload.get("operator_approved"):
        blockers.append("AI_EDGE_REQUIRE_OPERATOR_APPROVAL is true and operator_approved was not supplied.")
    if secret_findings.get("ok") is not True:
        blockers.append("Secret scan found blocked content after redaction.")
    if not evidence_sources:
        blockers.append("At least one app-provided evidence source is required for evidence-backed research.")
    web_plan = openai_web_search_request_plan(payload) if payload.get("web_search_requested") or active_provider == "openai_web_search" else {"web_search_request_built": False, "external_network_called": False, "blockers": ["Web search was not requested."]}
    local_review = local_llm_edge_review(payload, evidence_sources)
    probability = _probability_from_evidence(payload, evidence_sources)
    market_compare = _market_implied_comparison(payload, probability)
    packet = {
        "packet_id": record_id("edge_packet"),
        "created_at": _now(),
        "updated_at": _now(),
        "app_version": APP_VERSION,
        "title": redact_text(payload.get("title") or payload.get("market_title") or "AI Edge Research Packet")[:220],
        "status": "draft",
        "review_status": "DRAFT",
        "lifecycle_state": "EVIDENCE_ATTACHED" if evidence_sources else "DRAFT",
        "lifecycle_states": AI_EDGE_PACKET_LIFECYCLE_STATES,
        "provider": active_provider,
        "mode": mode,
        "research_question": redact_text(payload.get("research_question") or payload.get("question") or "Evaluate the evidence-backed edge thesis.")[:500],
        "market_id": redact_text(payload.get("market_id") or ""),
        "market_slug": redact_text(payload.get("market_slug") or payload.get("slug") or ""),
        "market_title": redact_text(payload.get("market_title") or payload.get("market") or ""),
        "recommended_side": redact_text(payload.get("recommended_side") or "INSUFFICIENT DATA"),
        "side_badge": redact_text(payload.get("side_badge") or "INSUFFICIENT DATA"),
        "model_fair_source": redact_text(payload.get("model_fair_source") or "AI Edge packet probability draft"),
        "evidence_sources": evidence_sources,
        "citations": citations,
        "evidence_backed_findings": findings,
        "contradictions": contradictions,
        "missing_information": missing,
        "blockers": blockers,
        "warnings": [
            "This packet is a draft research artifact.",
            "Probability drafts require calibration and human review before any use.",
            "No OpenAI web search or local LLM call is made by default.",
            "AI News Odds snapshots are draft fair-probability adjustments only and do not approve trades.",
        ],
        "probability_draft": probability,
        "ai_draft_probability_estimate": probability,
        "market_implied_comparison": market_compare,
        "news_odds_adjustment_snapshot": redact_data(payload.get("news_odds_adjustment_snapshot") or {}),
        "news_odds_source_weights": redact_data(payload.get("source_weights") or (payload.get("news_odds_adjustment_snapshot") or {}).get("source_weights") or {}),
        "news_odds_before_after_edge": redact_data({
            "base_edge": (payload.get("news_odds_adjustment_snapshot") or {}).get("base_edge"),
            "adjusted_edge": (payload.get("news_odds_adjustment_snapshot") or {}).get("adjusted_edge"),
            "base_fair_yes": (payload.get("news_odds_adjustment_snapshot") or {}).get("base_fair_yes"),
            "adjusted_fair_yes": (payload.get("news_odds_adjustment_snapshot") or {}).get("adjusted_fair_yes"),
        }),
        "openai_web_search": web_plan,
        "local_llm_edge_review": local_review,
        "calibration_tracking": {"enabled": settings.ai_edge_allow_calibration_tracking, "status": "pending_outcome", "calibration_id": ""},
        "prompt_metadata": {
            "prompt_hash": prompt_hash,
            "raw_prompt_stored": False,
            "prompt_hashes_only": settings.ai_edge_log_prompt_hashes_only,
            "input_chars": len(prompt_input),
            "max_input_chars": settings.ai_edge_max_input_chars,
        },
        "response_metadata": {
            "response_hash": "",
            "raw_response_stored": False,
            "max_output_tokens": settings.ai_edge_max_output_tokens,
        },
        "packet_evidence_backed": bool(evidence_sources and citations),
        "evidence_count": len(evidence_sources),
        "operator_notes_count": 0,
        "packet_lifecycle_summary": build_packet_lifecycle_summary({"evidence_sources": evidence_sources, "status": "draft", "market_id": payload.get("market_id"), "market_title": payload.get("market_title") or payload.get("market")}, current_recommendation={"recommended_side": payload.get("recommended_side") or "INSUFFICIENT DATA", "model_fair_source": payload.get("model_fair_source") or "AI Edge packet probability draft"}),
        "human_review_required": True,
        "archived": False,
        "external_network_called": False,
        "ai_model_called": False,
        "secret_scan_ok": secret_findings.get("ok") is True,
        "safety_statement": AI_EDGE_SAFETY_STATEMENT,
        **base_safety(),
    }
    packet["response_metadata"]["response_hash"] = _hash(packet)
    packet["validation"] = validate_packet(packet)
    audit = ai_openai_client._audit({
        "workflow_id": "ai_edge_research_packet",
        "template_id": "ai_edge_research_packet_v1",
        "provider": active_provider,
        "model": settings.local_llm_edge_model if active_provider.startswith("local") else settings.openai_model_review,
        "mode": mode,
        "input_category": "edge_research",
        "send_allowed": False,
        "redaction_applied": settings.ai_edge_redact_before_send,
        "prompt_hash": prompt_hash,
        "response_hash": packet["response_metadata"]["response_hash"],
        "usage_summary": {"network_called": False, "dry_run": True, "evidence_sources": len(evidence_sources)},
        "warnings": packet["warnings"],
        "blockers": blockers,
    })
    packet["audit_id"] = audit.get("audit_id")
    if settings.ai_edge_allow_calibration_tracking:
        calibration = ai_edge_calibration.pending_record_for_packet(packet, write=write)
        packet["calibration_tracking"]["calibration_id"] = calibration.get("calibration_id")
    if write:
        _write_jsonl(RESEARCH_PACKETS_PATH, packet)
    return safety_flags({"version": APP_VERSION, "packet": redact_data(packet), "write": write, **base_safety()})


def research_dry_run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return generate_edge_packet(payload or {}, write=False, mode="dry_run")


def openai_web_search_dry_run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {**(payload or {}), "web_search_requested": True, "provider": "openai_web_search"}
    plan = openai_web_search_request_plan(payload)
    packet = generate_edge_packet(payload, write=False, provider="openai_web_search", mode="openai_web_search_dry_run")["packet"]
    return safety_flags({"version": APP_VERSION, "request_plan": plan, "packet": packet, "external_network_called": False, "openai_api_called": False, **base_safety()})


def list_packets(limit: int = 250, status: str | None = None, include_archived: bool = False) -> dict[str, Any]:
    rows = _latest_by_id(_read_jsonl(RESEARCH_PACKETS_PATH), "packet_id")
    if status:
        rows = [row for row in rows if row.get("status") == status]
    if not include_archived:
        rows = [row for row in rows if row.get("archived") is not True and row.get("status") != "archived"]
    capped = rows[: max(1, min(int(limit or 250), 5000))]
    return safety_flags({"version": APP_VERSION, "count": len(capped), "total_count": len(rows), "items": capped, **base_safety()})


def get_packet(packet_id: str) -> dict[str, Any]:
    safe_id = redact_text(packet_id)
    for packet in _latest_by_id(_read_jsonl(RESEARCH_PACKETS_PATH), "packet_id"):
        if packet.get("packet_id") == safe_id:
            return safety_flags({"ok": True, "packet": packet, **base_safety()})
    return safety_flags({"ok": False, "error": "packet_not_found", "packet_id": safe_id, **base_safety()})


def archive_packet(packet_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    found = get_packet(packet_id)
    if not found.get("ok"):
        return found
    packet = dict(found["packet"])
    packet["status"] = "archived"
    packet["review_status"] = "ARCHIVED"
    packet["lifecycle_state"] = "ARCHIVED"
    packet["archived"] = True
    packet["archived_at"] = _now()
    packet["archive_reason"] = redact_text((payload or {}).get("reason") or "operator_archived")
    packet["updated_at"] = _now()
    packet.update(base_safety())
    _write_jsonl(RESEARCH_PACKETS_PATH, packet)
    return safety_flags({"ok": True, "packet": packet, **base_safety()})


def review_packet(packet_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    found = get_packet(packet_id)
    if not found.get("ok"):
        return found
    packet = dict(found["packet"])
    requested = payload.get("review_status") or payload.get("status") or "OPERATOR_REVIEWED"
    review_status = normalize_review_status(requested)
    if review_status == "UNREVIEWED":
        review_status = "OPERATOR_REVIEWED"
    lifecycle_state = review_status if review_status in AI_EDGE_PACKET_LIFECYCLE_STATES else "OPERATOR_REVIEWED"
    packet["review_status"] = review_status
    packet["status"] = review_status.lower()
    packet["lifecycle_state"] = lifecycle_state
    packet["operator_reviewed_at"] = _now()
    packet["operator_review_note"] = redact_text(payload.get("operator_review_note") or payload.get("note") or "operator reviewed")[:1000]
    packet["updated_at"] = _now()
    packet["packet_lifecycle_summary"] = build_packet_lifecycle_summary(packet)
    packet.update(base_safety())
    _write_jsonl(RESEARCH_PACKETS_PATH, packet)
    return safety_flags({"ok": True, "packet": packet, "draft_review_only": True, **base_safety()})


def packet_lifecycle(packet_id: str) -> dict[str, Any]:
    found = get_packet(packet_id)
    if not found.get("ok"):
        return found
    packet = found.get("packet") or {}
    return safety_flags({"ok": True, "packet_id": packet_id, "lifecycle": build_packet_lifecycle_summary(packet), **base_safety()})


def export_json() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "summary": edge_summary(),
        "settings": edge_settings_summary(),
        "schemas": schema_registry(),
        "packets": list_packets(limit=5000, include_archived=True),
        "evidence": ai_evidence.export_evidence_json(),
        "calibration": ai_edge_calibration.export_json(),
        "raw_prompts_included": False,
        "raw_responses_included": False,
        **base_safety(),
    })


def export_markdown() -> str:
    data = export_json()
    lines = [f"# AI Edge Research Export - {APP_VERSION}", "", AI_EDGE_SAFETY_STATEMENT, ""]
    lines.extend([
        "## Safe Defaults",
        f"- AI Edge enabled: `{data['settings']['ai_edge_enable']}`",
        f"- Provider: `{data['settings']['ai_edge_provider']}`",
        f"- Dry-run only: `{data['settings']['ai_edge_dry_run_only']}`",
        f"- Web search enabled: `{data['settings']['openai_enable_web_search']}`",
        f"- Market-implied comparison enabled: `{data['settings']['ai_edge_allow_market_implied_comparison']}`",
        f"- Calibration tracking enabled: `{data['settings']['ai_edge_allow_calibration_tracking']}`",
        "",
        "## Packets",
    ])
    for packet in data["packets"]["items"]:
        lines.append(f"- `{packet.get('packet_id')}` {packet.get('title')} status `{packet.get('status')}` evidence `{len(packet.get('evidence_sources', []))}`")
    if not data["packets"]["items"]:
        lines.append("- No edge research packets yet.")
    lines.extend(["", "## Calibration", f"- Records: `{data['calibration']['summary']['record_count']}`"])
    return "\n".join(lines) + "\n"


def export_csv() -> str:
    rows = list_packets(limit=5000, include_archived=True)["items"]
    out = io.StringIO()
    fields = ["packet_id", "created_at", "status", "provider", "market_id", "market_title", "research_question", "packet_evidence_backed", "no_trade_approval", "no_live_mutation", "external_network_called"]
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return out.getvalue()


def search_items(limit: int = 250) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "result_id": "ai_edge:settings",
            "result_type": "ai_edge_settings",
            "title": "AI Edge Research Safe Defaults",
            "summary": "Evidence-backed edge research, web-search dry-run planning, local LLM evidence review, and calibration tracking.",
            "status": "safe-defaults",
            "timestamp": "",
            "url": "/v3/ai/edge",
            "quick_link": "/v3/ai/edge",
            "tags": ["ai", "edge", "research"],
            "search_text": "ai edge research evidence citations calibration web search dry run",
            "secret_values_returned": False,
        }
    ]
    for packet in list_packets(limit=limit)["items"]:
        rows.append({
            "result_id": f"ai_edge_packet:{packet.get('packet_id')}",
            "result_type": "ai_edge_research_packet",
            "title": packet.get("title"),
            "summary": packet.get("research_question"),
            "status": packet.get("status"),
            "timestamp": packet.get("created_at"),
            "url": "/v3/ai/edge/packets",
            "quick_link": "/v3/ai/edge/packets",
            "tags": ["ai", "edge", "research_packet"],
            "search_text": f"ai edge research packet {packet.get('title')} {packet.get('research_question')}",
            "secret_values_returned": False,
        })
    return rows[: max(1, min(int(limit or 250), 5000))]


def graph_nodes() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = [
        {"node_id": "ai_edge:research", "node_type": "ai_edge_research", "title": "AI Edge Research", "status": "disabled-by-default", "summary": "Evidence-backed draft research packets and calibration tracking."},
        {"node_id": "ai_edge:evidence", "node_type": "ai_edge_evidence", "title": "AI Edge Evidence", "status": "app-provided-only", "summary": "Normalized source metadata and citations."},
        {"node_id": "ai_edge:calibration", "node_type": "ai_edge_calibration", "title": "AI Edge Calibration", "status": "research-only", "summary": "Outcome tracking for draft probability calibration."},
    ]
    edges = [
        {"source_node": "ai_edge:research", "target_node": "ai_edge:evidence", "relationship_type": "requires_evidence"},
        {"source_node": "ai_edge:research", "target_node": "ai_edge:calibration", "relationship_type": "tracks_outcomes"},
        {"source_node": "ai_edge:research", "target_node": "ai:prompt_governance", "relationship_type": "governed_by"},
    ]
    for packet in list_packets(limit=50)["items"]:
        node_id = f"ai_edge_packet:{packet.get('packet_id')}"
        nodes.append({"node_id": node_id, "node_type": "ai_edge_research_packet", "title": packet.get("title"), "status": packet.get("status"), "summary": packet.get("research_question")})
        edges.append({"source_node": node_id, "target_node": "ai_edge:research", "relationship_type": "created_by"})
    return nodes, edges


def workflow_templates() -> list[dict[str, Any]]:
    return [
        {"workflow_id": "ai_edge_research_packet", "name": "AI Edge Research Packet", "read_only": True, "mutates_trading_state": False, "description": "Build an evidence-backed AI edge research packet with citations, contradictions, missing-info tracking, draft probability, and calibration scaffolding.", "sections": ["Evidence", "Findings", "Contradictions", "Probability Draft", "Calibration", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "ai_edge_web_search_review", "name": "AI Edge Web Search Dry-run Review", "read_only": True, "mutates_trading_state": False, "description": "Build a web-search request plan without making network calls unless every explicit web-search gate is enabled outside the packaged default.", "sections": ["Request Plan", "Blockers", "Citation Requirements", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
        {"workflow_id": "ai_edge_calibration_review", "name": "AI Edge Calibration Review", "read_only": True, "mutates_trading_state": False, "description": "Summarize pending and resolved draft-probability calibration records.", "sections": ["Summary", "Brier Scores", "Provider Buckets", "Safety"], "markdown_ready": True, "output_is_draft": True, "order_submitted": False, "order_cancelled": False},
    ]


def workflow_output(workflow_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if workflow_id == "ai_edge_web_search_review":
        return openai_web_search_dry_run(payload or {})
    if workflow_id == "ai_edge_calibration_review":
        return ai_edge_calibration.export_json()
    return research_dry_run(payload or {})
