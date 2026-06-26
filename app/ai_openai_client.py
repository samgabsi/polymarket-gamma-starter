from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from .ai_schemas import AI_DRAFT_SAFETY_STATEMENT, default_payload, schema_for, validate_payload
from .config import APP_VERSION, DATA_DIR, settings
from .platform_safety import redact_data as platform_redact_data, redact_text as platform_redact_text, safety_flags, secret_scan

AI_DIR = DATA_DIR / "ai"
AI_AUDIT_PATH = AI_DIR / "ai_audit.jsonl"

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)(OPENAI_API_KEY|api[_-]?key|authorization|bearer|private[_-]?key|secret|password|token)\s*[:=]\s*[^\s,;}\]]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
]

DATA_CATEGORY_FLAGS = {
    "runtime_data": "openai_allow_sending_runtime_data",
    "market_data": "openai_allow_sending_market_data",
    "tasks": "openai_allow_sending_tasks",
    "docs": "openai_allow_sending_docs",
    "platform_diagnostics": "openai_allow_sending_platform_diagnostics",
    "migration_reports": "openai_allow_sending_migration_reports",
    "validation": "openai_allow_sending_platform_diagnostics",
    "route_inventory": "openai_allow_sending_platform_diagnostics",
    "connector_blueprint": "openai_allow_sending_docs",
    "redacted_local_summary": "openai_allow_sending_runtime_data",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def redact_ai_text(value: Any) -> str:
    text = platform_redact_text(str(value or ""))
    for pattern in SECRET_TEXT_PATTERNS:
        text = pattern.sub(lambda match: match.group(0).split("=")[0] + "=[REDACTED]" if "=" in match.group(0) else "[REDACTED]", text)
    return text


def redact_ai_data(value: Any) -> Any:
    redacted = platform_redact_data(value)
    if isinstance(redacted, str):
        return redact_ai_text(redacted)
    if isinstance(redacted, list):
        return [redact_ai_data(item) for item in redacted]
    if isinstance(redacted, dict):
        safe: dict[str, Any] = {}
        for key, item in redacted.items():
            if any(token in str(key).lower() for token in ["api_key", "private_key", "secret", "authorization", "password", "token", "cookie"]):
                safe[key] = "[REDACTED]"
            else:
                safe[key] = redact_ai_data(item)
        return safe
    return redacted


def openai_settings_summary() -> dict[str, Any]:
    return safety_flags({
        "version": APP_VERSION,
        "openai_api_key_configured": bool(settings.openai_api_key),
        "openai_api_key_value_returned": False,
        "openai_project_id_configured": bool(settings.openai_project_id),
        "openai_org_id_configured": bool(settings.openai_org_id),
        "openai_base_url": settings.openai_base_url,
        "model_review": settings.openai_model_review,
        "model_fast": settings.openai_model_fast,
        "model_low_cost": settings.openai_model_low_cost,
        "openai_enable_api": settings.openai_enable_api,
        "openai_enable_responses_api": settings.openai_enable_responses_api,
        "openai_enable_structured_outputs": settings.openai_enable_structured_outputs,
        "openai_enable_tool_calling": settings.openai_enable_tool_calling,
        "openai_enable_remote_mcp": settings.openai_enable_remote_mcp,
        "openai_enable_web_search": settings.openai_enable_web_search,
        "openai_enable_file_search": settings.openai_enable_file_search,
        "openai_enable_code_interpreter": settings.openai_enable_code_interpreter,
        "openai_allow_sending_runtime_data": settings.openai_allow_sending_runtime_data,
        "openai_allow_sending_market_data": settings.openai_allow_sending_market_data,
        "openai_allow_sending_tasks": settings.openai_allow_sending_tasks,
        "openai_allow_sending_docs": settings.openai_allow_sending_docs,
        "openai_allow_sending_platform_diagnostics": settings.openai_allow_sending_platform_diagnostics,
        "openai_allow_sending_migration_reports": settings.openai_allow_sending_migration_reports,
        "openai_redact_before_send": settings.openai_redact_before_send,
        "openai_require_operator_approval": settings.openai_require_operator_approval,
        "openai_max_input_chars": settings.openai_max_input_chars,
        "openai_max_output_tokens": settings.openai_max_output_tokens,
        "openai_timeout_seconds": settings.openai_timeout_seconds,
        "openai_dry_run_only": settings.openai_dry_run_only,
        "openai_log_prompt_hashes_only": settings.openai_log_prompt_hashes_only,
        "openai_audit_enabled": settings.openai_audit_enabled,
        "chatgpt_connector_blueprint_enabled": settings.chatgpt_connector_blueprint_enabled,
        "chatgpt_mcp_server_enabled": settings.chatgpt_mcp_server_enabled,
        "chatgpt_mcp_require_auth": settings.chatgpt_mcp_require_auth,
        "chatgpt_mcp_read_only": settings.chatgpt_mcp_read_only,
        "safe_default_posture": (
            not settings.openai_enable_api
            and settings.openai_dry_run_only
            and settings.openai_redact_before_send
            and settings.openai_require_operator_approval
            and not settings.openai_enable_tool_calling
            and not settings.openai_enable_remote_mcp
            and not settings.chatgpt_mcp_server_enabled
        ),
        "safety_statement": AI_DRAFT_SAFETY_STATEMENT,
    })


def send_permission(data_category: str) -> dict[str, Any]:
    category = str(data_category or "runtime_data")
    attr = DATA_CATEGORY_FLAGS.get(category, "openai_allow_sending_runtime_data")
    allowed = bool(getattr(settings, attr, False))
    return safety_flags({
        "data_category": category,
        "permission_flag": attr,
        "send_allowed": allowed,
        "api_enabled": settings.openai_enable_api,
        "dry_run_only": settings.openai_dry_run_only,
        "redaction_required": settings.openai_redact_before_send,
        "operator_approval_required": settings.openai_require_operator_approval,
    })


def _audit(record: dict[str, Any]) -> dict[str, Any]:
    if not settings.openai_audit_enabled:
        return safety_flags({"audit_written": False, "reason": "audit_disabled"})
    AI_DIR.mkdir(parents=True, exist_ok=True)
    row = redact_ai_data({
        "audit_id": record.get("audit_id") or f"ai_audit_{uuid4().hex[:12]}",
        "created_at": _now(),
        "app_version": APP_VERSION,
        **record,
        "raw_prompt_stored": False,
        "raw_response_stored": False,
        "no_secret_values": True,
        "secret_values_returned": False,
        "safety_statement": AI_DRAFT_SAFETY_STATEMENT,
        "no_live_mutation": True,
        "no_trade_approval": True,
    })
    with AI_AUDIT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    return row


def list_audit_records(limit: int = 250) -> dict[str, Any]:
    if not AI_AUDIT_PATH.exists():
        return safety_flags({"version": APP_VERSION, "count": 0, "items": [], "runtime_records_path": "data/ai/ai_audit.jsonl"})
    rows: list[dict[str, Any]] = []
    for line in AI_AUDIT_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(redact_ai_data(parsed))
        except json.JSONDecodeError:
            rows.append({"audit_id": "invalid", "created_at": _now(), "status": "invalid_json", "secret_values_returned": False})
    rows = list(reversed(rows))[: max(1, min(int(limit or 250), 5000))]
    return safety_flags({
        "version": APP_VERSION,
        "count": len(rows),
        "items": rows,
        "raw_prompts_stored": False,
        "raw_responses_stored": False,
        "audit_records_contain_no_secrets": all(item.get("no_secret_values") is True for item in rows),
    })


def build_responses_api_payload(
    *,
    model: str,
    instructions: str,
    input_text: str,
    schema_name: str,
    workflow_id: str,
) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": redact_ai_text(instructions)[: settings.openai_max_input_chars],
        "input": redact_ai_text(input_text)[: settings.openai_max_input_chars],
        "max_output_tokens": settings.openai_max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema_for(schema_name),
                "strict": True,
            }
        },
        "metadata": {
            "app_version": APP_VERSION,
            "workflow_id": workflow_id,
            "no_live_mutation": "true",
            "no_trade_approval": "true",
        },
    }


def _dry_run_response(workflow_id: str, schema_name: str, prompt_hash: str, input_category: str) -> dict[str, Any]:
    output = default_payload(
        schema_name,
        summary=f"Dry-run AI draft for {workflow_id}.",
        rationale="OpenAI API is disabled by default or dry-run-only mode is active.",
    )
    validation = validate_payload(schema_name, output)
    response_hash = _hash(output)
    audit = _audit({
        "workflow_id": workflow_id,
        "template_id": workflow_id,
        "model": settings.openai_model_review,
        "mode": "dry_run",
        "input_category": input_category,
        "send_allowed": False,
        "redaction_applied": True,
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        "usage_summary": {"network_called": False, "dry_run": True},
        "warnings": output["warnings"],
        "blockers": output["blockers"],
    })
    return safety_flags({
        "ok": True,
        "mode": "dry_run",
        "workflow_id": workflow_id,
        "schema_name": schema_name,
        "model": settings.openai_model_review,
        "output": output,
        "validation": validation,
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        "audit": audit,
        "external_network_called": False,
        "ai_model_called": False,
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
    safe_input = redact_ai_data(input_data) if settings.openai_redact_before_send else input_data
    input_text = json.dumps(safe_input, sort_keys=True, default=str)[: settings.openai_max_input_chars]
    prompt_hash = _hash({"instructions": redact_ai_text(instructions), "input": input_text, "schema_name": schema_name})
    permission = send_permission(input_category)
    api_blockers: list[str] = []
    if not settings.openai_api_key:
        api_blockers.append("OPENAI_API_KEY is not configured.")
    if not settings.openai_enable_api:
        api_blockers.append("OPENAI_ENABLE_API is false.")
    if not settings.openai_enable_responses_api:
        api_blockers.append("OPENAI_ENABLE_RESPONSES_API is false.")
    if settings.openai_dry_run_only:
        api_blockers.append("OPENAI_DRY_RUN_ONLY is true.")
    if settings.openai_require_operator_approval and not operator_approved:
        api_blockers.append("Operator approval is required before an API call.")
    if not permission["send_allowed"]:
        api_blockers.append(f"Data category {input_category} is not allowed to be sent.")
    if secret_scan(input_text)["ok"] is not True:
        api_blockers.append("Secret scan failed after redaction.")
    if api_blockers:
        response = _dry_run_response(workflow_id, schema_name, prompt_hash, input_category)
        response["api_blockers"] = api_blockers
        response["send_permission"] = permission
        return response

    payload = build_responses_api_payload(
        model=model or settings.openai_model_review,
        instructions=instructions,
        input_text=input_text,
        schema_name=schema_name,
        workflow_id=workflow_id,
    )
    try:
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        if settings.openai_project_id:
            headers["OpenAI-Project"] = settings.openai_project_id
        if settings.openai_org_id:
            headers["OpenAI-Organization"] = settings.openai_org_id
        with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
            result = client.post(f"{settings.openai_base_url.rstrip('/')}/responses", headers=headers, json=payload)
            result.raise_for_status()
            raw = result.json()
    except Exception as exc:
        safe_error = redact_ai_text(str(exc))
        audit = _audit({
            "workflow_id": workflow_id,
            "template_id": template_id,
            "model": model or settings.openai_model_review,
            "mode": "api_call",
            "input_category": input_category,
            "send_allowed": True,
            "redaction_applied": settings.openai_redact_before_send,
            "prompt_hash": prompt_hash,
            "response_hash": _hash({"error": safe_error}),
            "usage_summary": {"network_called": True, "error": safe_error[:300]},
            "warnings": ["OpenAI API call failed safely."],
            "blockers": [safe_error[:300]],
        })
        return safety_flags({
            "ok": False,
            "mode": "api_call",
            "workflow_id": workflow_id,
            "schema_name": schema_name,
            "error": safe_error,
            "audit": audit,
            "external_network_called": True,
            "ai_model_called": True,
        })

    output_text = raw.get("output_text") or ""
    parsed: dict[str, Any]
    try:
        parsed = json.loads(output_text) if isinstance(output_text, str) and output_text.strip() else {}
    except json.JSONDecodeError:
        parsed = {}
    if not parsed:
        parsed = default_payload(schema_name, summary="OpenAI response did not include parseable structured JSON.")
        parsed["warnings"].append("Structured parse failed; fallback draft inserted.")
    parsed = redact_ai_data(parsed)
    validation = validate_payload(schema_name, parsed)
    response_hash = _hash(parsed)
    audit = _audit({
        "workflow_id": workflow_id,
        "template_id": template_id,
        "model": model or settings.openai_model_review,
        "mode": "api_call",
        "input_category": input_category,
        "send_allowed": True,
        "redaction_applied": settings.openai_redact_before_send,
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        "usage_summary": redact_ai_data(raw.get("usage", {})),
        "warnings": parsed.get("warnings", []),
        "blockers": parsed.get("blockers", []),
    })
    return safety_flags({
        "ok": validation["ok"],
        "mode": "api_call",
        "workflow_id": workflow_id,
        "schema_name": schema_name,
        "model": model or settings.openai_model_review,
        "output": parsed,
        "validation": validation,
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        "audit": audit,
        "external_network_called": True,
        "ai_model_called": True,
        "tool_calls_executed": False,
    })


def export_audit_markdown(limit: int = 250) -> str:
    records = list_audit_records(limit=limit)
    lines = [
        f"# AI Audit Summary - {APP_VERSION}",
        "",
        AI_DRAFT_SAFETY_STATEMENT,
        "",
        "Raw prompts, raw responses, and secrets are not stored by default.",
        "",
    ]
    for item in records["items"]:
        lines.append(f"- `{item.get('audit_id')}` `{item.get('mode')}` `{item.get('workflow_id')}` prompt `{item.get('prompt_hash')}` response `{item.get('response_hash')}`")
    if not records["items"]:
        lines.append("- No AI audit records yet.")
    return "\n".join(lines) + "\n"


def cleanup_runtime_ai_records(root: Path | None = None) -> dict[str, Any]:
    root = root or AI_DIR
    removed = []
    if root.exists():
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
                removed.append(str(path))
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            root.rmdir()
        except OSError:
            pass
    return safety_flags({"removed_count": len(removed), "removed_paths": removed[:100]})
