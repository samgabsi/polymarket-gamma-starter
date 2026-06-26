from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlparse

import httpx

from .ai_schemas import AI_DRAFT_SAFETY_STATEMENT, default_payload, validate_payload
from .config import APP_VERSION, settings
from .platform_safety import redact_data, safety_flags
from . import ai_openai_client


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _is_localhost_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def local_llm_settings_summary() -> dict[str, Any]:
    localhost_ok = _is_localhost_url(settings.local_llm_base_url)
    return safety_flags({
        "version": APP_VERSION,
        "local_llm_enable": settings.local_llm_enable,
        "local_llm_provider": settings.local_llm_provider,
        "local_llm_base_url": settings.local_llm_base_url,
        "local_llm_model": settings.local_llm_model,
        "local_llm_openai_compatible": settings.local_llm_openai_compatible,
        "local_llm_require_localhost": settings.local_llm_require_localhost,
        "local_llm_allow_network": settings.local_llm_allow_network,
        "local_llm_allow_runtime_data": settings.local_llm_allow_runtime_data,
        "local_llm_timeout_seconds": settings.local_llm_timeout_seconds,
        "local_llm_max_input_chars": settings.local_llm_max_input_chars,
        "local_llm_max_output_tokens": settings.local_llm_max_output_tokens,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "llama_cpp_base_url": settings.llama_cpp_base_url,
        "llama_cpp_model": settings.llama_cpp_model,
        "lm_studio_base_url": settings.lm_studio_base_url,
        "lm_studio_model": settings.lm_studio_model,
        "localhost_requirement_satisfied": localhost_ok,
        "safe_default_posture": settings.local_llm_enable is False and settings.local_llm_allow_network is False and settings.local_llm_require_localhost is True,
        "safety_statement": "Local LLMs are disabled by default and still use redaction, prompt governance, audit hashes, human review, and no-live-mutation controls.",
        "secret_values_returned": False,
        "no_live_mutation": True,
    })


def health_check(*, dry_run: bool = True) -> dict[str, Any]:
    status = local_llm_settings_summary()
    blockers: list[str] = []
    if not settings.local_llm_enable:
        blockers.append("LOCAL_LLM_ENABLE is false.")
    if settings.ai_dry_run_only:
        blockers.append("AI_DRY_RUN_ONLY is true.")
    if not settings.local_llm_allow_network:
        blockers.append("LOCAL_LLM_ALLOW_NETWORK is false.")
    if settings.local_llm_require_localhost and not status["localhost_requirement_satisfied"]:
        blockers.append("LOCAL_LLM_REQUIRE_LOCALHOST is true but the configured endpoint is not localhost.")
    if dry_run or blockers:
        return safety_flags({
            "version": APP_VERSION,
            "provider": settings.local_llm_provider,
            "model": settings.local_llm_model,
            "status": "dry_run" if dry_run else "blocked",
            "available": False,
            "external_network_called": False,
            "ai_model_called": False,
            "blockers": blockers,
            "safe_test_prompt_only": True,
            "no_live_mutation": True,
            "secret_values_returned": False,
        })
    try:
        with httpx.Client(timeout=settings.local_llm_timeout_seconds) as client:
            result = client.get(f"{settings.local_llm_base_url.rstrip('/')}/models")
            result.raise_for_status()
            data = result.json()
        return safety_flags({
            "version": APP_VERSION,
            "provider": settings.local_llm_provider,
            "model": settings.local_llm_model,
            "status": "available",
            "available": True,
            "models_response_summary": {"type": type(data).__name__, "key_count": len(data) if isinstance(data, dict) else 0},
            "external_network_called": True,
            "ai_model_called": False,
            "no_live_mutation": True,
            "secret_values_returned": False,
        })
    except Exception as exc:
        return safety_flags({
            "version": APP_VERSION,
            "provider": settings.local_llm_provider,
            "model": settings.local_llm_model,
            "status": "unavailable",
            "available": False,
            "error": ai_openai_client.redact_ai_text(str(exc))[:300],
            "external_network_called": True,
            "ai_model_called": False,
            "no_live_mutation": True,
            "secret_values_returned": False,
        })


def dry_run_structured_output(*, workflow_id: str, schema_name: str, prompt_hash: str, input_category: str) -> dict[str, Any]:
    output = default_payload(
        schema_name,
        summary=f"Local LLM dry-run draft for {workflow_id} using {settings.local_llm_model}.",
        rationale="Local LLM calls are disabled/dry-run-by-default unless the operator explicitly enables localhost network use.",
    )
    output["suggested_human_next_actions"] = ["Review the local LLM draft manually.", "Keep redaction enabled before any live local endpoint call."]
    validation = validate_payload(schema_name, output)
    response_hash = _hash(output)
    audit = ai_openai_client._audit({  # intentional internal reuse to keep one AI audit namespace
        "workflow_id": workflow_id,
        "template_id": workflow_id,
        "provider": settings.local_llm_provider,
        "model": settings.local_llm_model,
        "mode": "dry_run",
        "input_category": input_category,
        "send_allowed": False,
        "redaction_applied": True,
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        "usage_summary": {"network_called": False, "dry_run": True, "local_llm": True},
        "warnings": output["warnings"],
        "blockers": output["blockers"],
    })
    return safety_flags({
        "ok": True,
        "mode": "dry_run",
        "provider": settings.local_llm_provider,
        "workflow_id": workflow_id,
        "schema_name": schema_name,
        "model": settings.local_llm_model,
        "output": output,
        "validation": validation,
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        "audit": audit,
        "external_network_called": False,
        "ai_model_called": False,
        "safety_statement": AI_DRAFT_SAFETY_STATEMENT,
    })


def request_structured_output(
    *,
    workflow_id: str,
    template_id: str,
    instructions: str,
    input_data: Any,
    schema_name: str = "AIReviewSummary",
    input_category: str = "runtime_data",
    operator_approved: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    safe_input = ai_openai_client.redact_ai_data(input_data) if settings.ai_redact_before_send else input_data
    input_text = json.dumps(safe_input, sort_keys=True, default=str)[: settings.local_llm_max_input_chars]
    prompt_hash = _hash({"provider": settings.local_llm_provider, "instructions": ai_openai_client.redact_ai_text(instructions), "input": input_text, "schema_name": schema_name})
    blockers: list[str] = []
    if not settings.ai_enable:
        blockers.append("AI_ENABLE is false.")
    if not settings.local_llm_enable:
        blockers.append("LOCAL_LLM_ENABLE is false.")
    if settings.ai_dry_run_only:
        blockers.append("AI_DRY_RUN_ONLY is true.")
    if not settings.local_llm_allow_network:
        blockers.append("LOCAL_LLM_ALLOW_NETWORK is false.")
    if settings.ai_require_operator_approval and not operator_approved:
        blockers.append("Operator approval is required before local LLM calls.")
    if settings.local_llm_require_localhost and not _is_localhost_url(settings.local_llm_base_url):
        blockers.append("Configured local LLM endpoint is not localhost.")
    if ai_openai_client.secret_scan(input_text)["ok"] is not True:
        blockers.append("Secret scan failed after redaction.")
    if blockers:
        response = dry_run_structured_output(workflow_id=workflow_id, schema_name=schema_name, prompt_hash=prompt_hash, input_category=input_category)
        response["api_blockers"] = blockers
        response["send_permission"] = {"send_allowed": False, "provider": settings.local_llm_provider, "redaction_required": settings.ai_redact_before_send}
        return response

    payload = {
        "model": model or settings.local_llm_model,
        "messages": [
            {"role": "system", "content": ai_openai_client.redact_ai_text(instructions)},
            {"role": "user", "content": input_text},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": settings.local_llm_max_output_tokens,
    }
    try:
        with httpx.Client(timeout=settings.local_llm_timeout_seconds) as client:
            result = client.post(f"{settings.local_llm_base_url.rstrip('/')}/chat/completions", json=payload)
            result.raise_for_status()
            raw = result.json()
    except Exception as exc:
        safe_error = ai_openai_client.redact_ai_text(str(exc))[:300]
        audit = ai_openai_client._audit({
            "workflow_id": workflow_id,
            "template_id": template_id,
            "provider": settings.local_llm_provider,
            "model": model or settings.local_llm_model,
            "mode": "local_llm",
            "input_category": input_category,
            "send_allowed": True,
            "redaction_applied": settings.ai_redact_before_send,
            "prompt_hash": prompt_hash,
            "response_hash": _hash({"error": safe_error}),
            "usage_summary": {"network_called": True, "error": safe_error},
            "warnings": ["Local LLM call failed safely."],
            "blockers": [safe_error],
        })
        return safety_flags({"ok": False, "mode": "local_llm", "provider": settings.local_llm_provider, "workflow_id": workflow_id, "schema_name": schema_name, "error": safe_error, "audit": audit, "external_network_called": True, "ai_model_called": True})

    content = ""
    try:
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        content = ""
    try:
        parsed = json.loads(content) if content.strip() else {}
    except json.JSONDecodeError:
        parsed = {}
    if not parsed:
        parsed = default_payload(schema_name, summary="Local LLM response did not include parseable structured JSON.")
        parsed["warnings"].append("Structured parse failed; fallback draft inserted.")
    parsed = ai_openai_client.redact_ai_data(parsed)
    validation = validate_payload(schema_name, parsed)
    response_hash = _hash(parsed)
    audit = ai_openai_client._audit({
        "workflow_id": workflow_id,
        "template_id": template_id,
        "provider": settings.local_llm_provider,
        "model": model or settings.local_llm_model,
        "mode": "local_llm",
        "input_category": input_category,
        "send_allowed": True,
        "redaction_applied": settings.ai_redact_before_send,
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        "usage_summary": redact_data(raw.get("usage", {})),
        "warnings": parsed.get("warnings", []),
        "blockers": parsed.get("blockers", []),
    })
    return safety_flags({"ok": validation["ok"], "mode": "local_llm", "provider": settings.local_llm_provider, "workflow_id": workflow_id, "schema_name": schema_name, "model": model or settings.local_llm_model, "output": parsed, "validation": validation, "prompt_hash": prompt_hash, "response_hash": response_hash, "audit": audit, "external_network_called": True, "ai_model_called": True, "tool_calls_executed": False})
