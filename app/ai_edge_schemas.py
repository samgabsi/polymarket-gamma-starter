from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, settings
from .platform_safety import safety_flags

AI_EDGE_SAFETY_STATEMENT = (
    "AI Edge Research draft for human review only. Not financial advice. Not trade approval. "
    "Does not place orders, cancel orders, arm live trading, or disable safety gates."
)

EDGE_REQUIRED_PACKET_FIELDS = [
    "packet_id",
    "created_at",
    "app_version",
    "title",
    "status",
    "provider",
    "mode",
    "research_question",
    "evidence_sources",
    "citations",
    "evidence_backed_findings",
    "contradictions",
    "missing_information",
    "probability_draft",
    "safety_statement",
    "human_review_required",
    "no_financial_advice",
    "no_trade_approval",
    "no_live_mutation",
    "external_network_called",
    "ai_model_called",
    "order_submitted",
    "order_cancelled",
    "live_trading_armed",
    "secret_values_returned",
]

EDGE_BASE_PROPERTIES: dict[str, Any] = {
    "packet_id": {"type": "string"},
    "created_at": {"type": "string"},
    "app_version": {"type": "string"},
    "title": {"type": "string"},
    "status": {"type": "string"},
    "provider": {"type": "string"},
    "mode": {"type": "string"},
    "research_question": {"type": "string"},
    "market_id": {"type": "string"},
    "market_title": {"type": "string"},
    "evidence_sources": {"type": "array"},
    "citations": {"type": "array"},
    "evidence_backed_findings": {"type": "array"},
    "contradictions": {"type": "array"},
    "missing_information": {"type": "array"},
    "probability_draft": {"type": "object"},
    "market_implied_comparison": {"type": "object"},
    "calibration_tracking": {"type": "object"},
    "prompt_metadata": {"type": "object"},
    "response_metadata": {"type": "object"},
    "safety_statement": {"type": "string", "const": AI_EDGE_SAFETY_STATEMENT},
    "human_review_required": {"type": "boolean", "const": True},
    "no_financial_advice": {"type": "boolean", "const": True},
    "no_trade_approval": {"type": "boolean", "const": True},
    "no_live_mutation": {"type": "boolean", "const": True},
    "external_network_called": {"type": "boolean", "const": False},
    "ai_model_called": {"type": "boolean"},
    "order_submitted": {"type": "boolean", "const": False},
    "order_cancelled": {"type": "boolean", "const": False},
    "live_trading_armed": {"type": "boolean", "const": False},
    "secret_values_returned": {"type": "boolean", "const": False},
}

SCHEMAS: dict[str, dict[str, Any]] = {
    "AIEdgeEvidenceSource": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"polymarket-op-console.ai_edge.AIEdgeEvidenceSource.{APP_VERSION}",
        "title": "AI Edge Evidence Source",
        "type": "object",
        "required": ["source_id", "title", "citation_label", "claim_stance", "snippet", "retrieved_at", "secret_values_returned"],
        "properties": {
            "source_id": {"type": "string"},
            "url": {"type": "string"},
            "domain": {"type": "string"},
            "title": {"type": "string"},
            "citation_label": {"type": "string"},
            "claim_stance": {"type": "string"},
            "snippet": {"type": "string"},
            "retrieved_at": {"type": "string"},
            "quality_score": {"type": "number"},
            "relevance_score": {"type": "number"},
            "operator_provided": {"type": "boolean"},
            "secret_values_returned": {"type": "boolean", "const": False},
        },
    },
    "AIEdgeResearchPacket": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"polymarket-op-console.ai_edge.AIEdgeResearchPacket.{APP_VERSION}",
        "title": "AI Edge Research Packet",
        "type": "object",
        "additionalProperties": True,
        "required": EDGE_REQUIRED_PACKET_FIELDS,
        "properties": deepcopy(EDGE_BASE_PROPERTIES),
    },
    "AIEdgeCalibrationRecord": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"polymarket-op-console.ai_edge.AIEdgeCalibrationRecord.{APP_VERSION}",
        "title": "AI Edge Calibration Record",
        "type": "object",
        "required": ["calibration_id", "packet_id", "status", "draft_probability", "outcome_recorded", "no_trade_approval", "secret_values_returned"],
        "properties": {
            "calibration_id": {"type": "string"},
            "packet_id": {"type": "string"},
            "status": {"type": "string"},
            "draft_probability": {"type": "number"},
            "outcome_recorded": {"type": "boolean"},
            "resolved_outcome": {"type": "boolean"},
            "brier_score": {"type": "number"},
            "no_trade_approval": {"type": "boolean", "const": True},
            "secret_values_returned": {"type": "boolean", "const": False},
        },
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def base_safety() -> dict[str, Any]:
    return safety_flags({
        "safety_statement": AI_EDGE_SAFETY_STATEMENT,
        "research_only": True,
        "human_review_required": True,
        "no_financial_advice": True,
        "no_trade_approval": True,
        "no_live_mutation": True,
        "no_live_mutation_statement": "AI Edge Research drafts, evidence normalization, calibration tracking, web-search request plans, and exports do not place orders, cancel orders, approve trades, arm live trading, or disable safety gates.",
        "ai_edge_research_enabled": settings.ai_edge_enable,
        "ai_edge_provider": settings.ai_edge_provider,
        "ai_edge_dry_run_only": settings.ai_edge_dry_run_only,
        "web_search_disabled_by_default": settings.openai_enable_web_search is False and settings.ai_edge_allow_web_search is False,
        "market_implied_comparison_disabled_by_default": settings.ai_edge_allow_market_implied_comparison is False,
        "calibration_tracking_enabled_by_default": settings.ai_edge_allow_calibration_tracking is True,
        "source_urls_allowed_by_default": settings.ai_edge_allow_source_urls is True,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "mutates_live_trading_state": False,
        "external_network_called": False,
        "secret_values_returned": False,
    })


def default_evidence_source(index: int = 1, *, title: str = "Operator-provided evidence placeholder", snippet: str = "Evidence supplied by the app should be reviewed before relying on any AI draft.", stance: str = "mixed") -> dict[str, Any]:
    label = f"S{index}"
    return {
        "source_id": record_id("edge_src"),
        "created_at": _now(),
        "app_version": APP_VERSION,
        "title": title,
        "url": "",
        "domain": "",
        "citation_label": label,
        "claim_stance": stance,
        "snippet": snippet,
        "retrieved_at": _now(),
        "published_at": "",
        "recency_status": "unknown",
        "quality_score": 0.5,
        "relevance_score": 0.5,
        "operator_provided": True,
        "demo_only": True,
        "secret_values_returned": False,
    }


def default_probability_draft(probability: float | None = None) -> dict[str, Any]:
    value = 0.5 if probability is None else max(0.0, min(1.0, float(probability)))
    return {
        "model_probability": value,
        "fair_probability": value,
        "confidence": "low",
        "rationale": "Draft probability is research-only and must be calibrated against outcomes before trust is assigned.",
        "draft_probability_is_not_trade_signal": True,
        "not_financial_advice": True,
        "no_trade_approval": True,
        "no_live_mutation": True,
    }


def default_research_packet(payload: dict[str, Any] | None = None, *, provider: str = "mock", mode: str = "dry_run") -> dict[str, Any]:
    payload = payload or {}
    packet_id = record_id("edge_packet")
    evidence = [default_evidence_source()]
    probability = default_probability_draft(payload.get("model_probability") or payload.get("draft_probability"))
    return {
        "packet_id": packet_id,
        "created_at": _now(),
        "updated_at": _now(),
        "app_version": APP_VERSION,
        "title": str(payload.get("title") or "AI Edge Research Packet"),
        "status": "draft",
        "provider": provider,
        "mode": mode,
        "research_question": str(payload.get("research_question") or payload.get("question") or "Review edge evidence for the selected market."),
        "market_id": str(payload.get("market_id") or ""),
        "market_title": str(payload.get("market_title") or payload.get("market") or ""),
        "evidence_sources": evidence,
        "citations": [{"citation_label": "S1", "source_id": evidence[0]["source_id"], "title": evidence[0]["title"], "url": ""}],
        "evidence_backed_findings": [{"claim": evidence[0]["snippet"], "citation_labels": ["S1"], "stance": "mixed", "confidence": "low"}],
        "contradictions": [],
        "missing_information": ["No live web search was performed in the default dry-run packet."],
        "probability_draft": probability,
        "market_implied_comparison": {"included": False, "reason": "AI_EDGE_ALLOW_MARKET_IMPLIED_COMPARISON is false by default."},
        "calibration_tracking": {"enabled": settings.ai_edge_allow_calibration_tracking, "status": "pending_outcome"},
        "prompt_metadata": {"prompt_hash": "", "raw_prompt_stored": False, "prompt_hashes_only": True},
        "response_metadata": {"response_hash": "", "raw_response_stored": False},
        **base_safety(),
    }


def schema_for(schema_name: str) -> dict[str, Any]:
    return deepcopy(SCHEMAS.get(schema_name, SCHEMAS["AIEdgeResearchPacket"]))


def schema_registry() -> dict[str, Any]:
    rows = [
        {
            "schema_id": name,
            "app_version": APP_VERSION,
            "title": schema["title"],
            "required_fields": schema.get("required", []),
            "contains_no_live_mutation": "no_live_mutation" in schema.get("required", []) or name == "AIEdgeCalibrationRecord",
            "contains_no_trade_approval": "no_trade_approval" in schema.get("required", []),
            "contains_secret_safety": True,
            "safety_statement": AI_EDGE_SAFETY_STATEMENT,
            "secret_values_returned": False,
        }
        for name, schema in sorted(SCHEMAS.items())
    ]
    return safety_flags({
        "version": APP_VERSION,
        "count": len(rows),
        "items": rows,
        "schemas": deepcopy(SCHEMAS),
        "edge_research_outputs_are_drafts_only": True,
        "edge_schema_requires_citations": True,
        "edge_schema_tracks_contradictions": True,
        "edge_schema_tracks_missing_information": True,
        **base_safety(),
    })


def validate_packet(packet: dict[str, Any] | None) -> dict[str, Any]:
    value = packet or {}
    missing = [field for field in EDGE_REQUIRED_PACKET_FIELDS if field not in value]
    unsafe: list[str] = []
    if value.get("safety_statement") != AI_EDGE_SAFETY_STATEMENT:
        unsafe.append("safety_statement must match the AI Edge safety statement")
    if value.get("no_live_mutation") is not True:
        unsafe.append("no_live_mutation must be true")
    if value.get("no_trade_approval") is not True:
        unsafe.append("no_trade_approval must be true")
    if value.get("no_financial_advice") is not True and value.get("not_financial_advice") is not True:
        unsafe.append("no_financial_advice/not_financial_advice must be true")
    for field in ("order_submitted", "order_cancelled", "live_trading_armed", "secret_values_returned"):
        if value.get(field) not in {False, None}:
            unsafe.append(f"{field} must be false")
    if value.get("external_network_called") is not False:
        unsafe.append("external_network_called must be false for packaged dry-run/review paths")
    if not isinstance(value.get("citations", []), list):
        unsafe.append("citations must be a list")
    if not isinstance(value.get("evidence_sources", []), list):
        unsafe.append("evidence_sources must be a list")
    probability = value.get("probability_draft", {})
    if isinstance(probability, dict):
        for key in ("model_probability", "fair_probability"):
            if probability.get(key) is not None:
                try:
                    number = float(probability[key])
                    if number < 0 or number > 1:
                        unsafe.append(f"{key} must be between 0 and 1")
                except (TypeError, ValueError):
                    unsafe.append(f"{key} must be numeric")
    ok = not missing and not unsafe
    return safety_flags({
        "ok": ok,
        "status": "pass" if ok else "fail",
        "schema_name": "AIEdgeResearchPacket",
        "missing_required_fields": missing,
        "unsafe_findings": unsafe,
        **base_safety(),
    })
