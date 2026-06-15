from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlencode, parse_qsl, urlunparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .data_ingestion import record_raw_snapshot, run_normalization

INTERNET_DIR = DATA_DIR / "internet_ingestion"
INTERNET_SOURCES_PATH = INTERNET_DIR / "internet_sources.json"
INTERNET_JOBS_PATH = INTERNET_DIR / "internet_ingestion_jobs.json"
INTERNET_SCHEDULES_PATH = INTERNET_DIR / "internet_ingestion_schedules.json"
INTERNET_AUDIT_PATH = INTERNET_DIR / "audit_events.json"
RAW_RESPONSES_DIR = INTERNET_DIR / "raw_responses"

HOST_JOBS_DIR = DATA_DIR / "host_training_jobs"
HOST_JOBS_PATH = HOST_JOBS_DIR / "host_training_jobs.json"
HOST_JOB_ARTIFACTS_DIR = HOST_JOBS_DIR / "artifacts"

INTERNET_SOURCE_TYPES = {
    "gamma_api_markets",
    "gamma_api_events",
    "gamma_api_market_detail",
    "clob_api_markets",
    "clob_api_orderbook",
    "clob_api_trades",
    "public_csv_url",
    "public_json_url",
    "public_http_snapshot",
}
SAFE_JOB_TYPES = {
    "baseline_training",
    "threshold_training",
    "momentum_training",
    "walk_forward_backtest",
    "dataset_quality_scan",
    "feature_build",
    "signal_generation_preview",
}
JOB_TYPE_ALIASES = {
    "baseline": "baseline_training",
    "threshold": "threshold_training",
    "momentum": "momentum_training",
    "backtest": "walk_forward_backtest",
    "walk_forward": "walk_forward_backtest",
    "quality": "dataset_quality_scan",
    "quality_scan": "dataset_quality_scan",
    "features": "feature_build",
    "signals": "signal_generation_preview",
    "signal_preview": "signal_generation_preview",
}
PRICE_FIELD_HINTS = {"price", "probability", "yes_price", "no_price", "limit_price", "market_probability", "model_probability"}
TIMESTAMP_FIELD_HINTS = {"timestamp", "created_at", "updated_at", "time", "date", "datetime"}
LABEL_FIELD_HINTS = {"label", "label_value", "target", "outcome", "resolved_outcome", "result", "accepted", "decision"}
ARTIFACT_SECRET_HINTS = {"api_key", "secret", "password", "private_key", "signature", "passphrase", "authorization", "credential"}
TRADING_PATH_HINTS = ("/order", "/orders", "/trade", "/trades", "/cancel", "/fill", "/sign", "/submit")
SENSITIVE_QUERY_HINTS = {"key", "secret", "token", "password", "private", "api_key", "signature", "sig"}
CONFIRMATION_TEXT = "I_UNDERSTAND_INTERNET_INGESTION_FETCHES_PUBLIC_DATA"
HOST_CONFIRMATION_TEXT = "I_UNDERSTAND_HOST_TRAINING_RUNS_LOCAL_JOBS"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _load_list(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path, [])
    return data if isinstance(data, list) else []


def _save_list(path: Path, rows: list[dict[str, Any]]) -> None:
    _write_json(path, rows)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        number = int(float(value))
        return number
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if not math.isfinite(number):
            return default
        return number
    except Exception:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _csv(rows: list[dict[str, Any]], fields: list[str]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        clean = {}
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True, default=str)
            clean[field] = value
        writer.writerow(clean)
    return out.getvalue()


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _audit(event_type: str, source_id: str = "", detail: str = "", data: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "timestamp": _now(),
        "category": "internet_training",
        "event_type": event_type,
        "source": "internet_ops",
        "source_id": source_id,
        "detail": detail,
        "data_hash": _stable_hash(data or {}),
        "secret_values_returned": False,
    }
    rows = _load_list(INTERNET_AUDIT_PATH)
    rows.append(event)
    _save_list(INTERNET_AUDIT_PATH, rows)
    return event


def _canonical_job_type(job_type: str) -> str:
    raw = _text(job_type).lower()
    return JOB_TYPE_ALIASES.get(raw, raw)


def internet_config() -> dict[str, Any]:
    allowed_domains = [d.strip().lower() for d in os.getenv("POLYMARKET_DATA_ALLOWED_DOMAINS", "").split(",") if d.strip()]
    raw_allowed_jobs = [
        j.strip()
        for j in os.getenv(
            "POLYMARKET_TRAINING_ALLOWED_JOB_TYPES",
            "baseline_training,threshold_training,momentum_training,walk_forward_backtest,dataset_quality_scan,feature_build,signal_generation_preview",
        ).split(",")
        if j.strip()
    ]
    allowed_jobs = sorted({_canonical_job_type(job) for job in raw_allowed_jobs if _canonical_job_type(job) in SAFE_JOB_TYPES})
    training_default_max_rows = max(1, _safe_int(os.getenv("POLYMARKET_TRAINING_DEFAULT_MAX_ROWS", "100000"), 100000))
    training_hard_max_rows = max(1, _safe_int(os.getenv("POLYMARKET_TRAINING_HARD_MAX_ROWS", "1000000"), 1000000))
    training_max_rows = max(1, _safe_int(os.getenv("POLYMARKET_TRAINING_MAX_ROWS", str(training_default_max_rows)), training_default_max_rows))
    training_batch_size = max(1, _safe_int(os.getenv("POLYMARKET_TRAINING_BATCH_SIZE", "5000"), 5000))
    return {
        "internet_enabled": _bool_env("POLYMARKET_DATA_ALLOW_INTERNET", False),
        "scheduler_enabled": _bool_env("POLYMARKET_DATA_INGESTION_SCHEDULER_ENABLED", False),
        "allowed_domains": allowed_domains,
        "max_requests_per_run": max(1, _safe_int(os.getenv("POLYMARKET_DATA_MAX_REQUESTS_PER_RUN", "25"), 25)),
        "request_timeout_seconds": max(1, _safe_int(os.getenv("POLYMARKET_DATA_REQUEST_TIMEOUT_SECONDS", "10"), 10)),
        "rate_limit_seconds": max(0, _safe_float(os.getenv("POLYMARKET_DATA_RATE_LIMIT_SECONDS", "1"), 1.0)),
        "user_agent": _text(os.getenv("POLYMARKET_DATA_USER_AGENT"), "PolymarketGammaStarterLocalResearch/1.0"),
        "store_raw_responses": _bool_env("POLYMARKET_DATA_STORE_RAW_RESPONSES", False),
        "max_raw_response_bytes": max(1000, _safe_int(os.getenv("POLYMARKET_DATA_MAX_RAW_RESPONSE_BYTES", "1000000"), 1000000)),
        "require_operator_confirmation": _bool_env("POLYMARKET_DATA_REQUIRE_OPERATOR_CONFIRMATION", True),
        "host_jobs_enabled": _bool_env("POLYMARKET_TRAINING_HOST_JOBS_ENABLED", False),
        "training_max_runtime_seconds": max(5, _safe_int(os.getenv("POLYMARKET_TRAINING_MAX_RUNTIME_SECONDS", "900"), 900)),
        "training_default_max_rows": training_default_max_rows,
        "training_hard_max_rows": training_hard_max_rows,
        "training_max_rows": training_max_rows,
        "training_batch_size": training_batch_size,
        "training_block_over_hard_max_rows": _bool_env("POLYMARKET_TRAINING_BLOCK_OVER_HARD_MAX_ROWS", True),
        "training_max_artifact_bytes": max(1000, _safe_int(os.getenv("POLYMARKET_TRAINING_MAX_ARTIFACT_BYTES", "50000000"), 50000000)),
        "training_allowed_job_types": allowed_jobs or sorted(SAFE_JOB_TYPES),
    }

def _parse_params(query_params: Any) -> dict[str, str]:
    if isinstance(query_params, dict):
        return {str(k): str(v) for k, v in query_params.items() if str(k)}
    text = _text(query_params)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items() if str(k)}
    except Exception:
        pass
    return {str(k): str(v) for k, v in parse_qsl(text, keep_blank_values=False)}


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    redacted = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in SENSITIVE_QUERY_HINTS:
            value = "REDACTED"
        redacted.append((key, value))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(redacted), parsed.fragment))


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0]


def _request_url(source: dict[str, Any]) -> str:
    base = _text(source.get("base_url"))
    path = _text(source.get("endpoint_path"))
    url = urljoin(base if base.endswith("/") else base + "/", path.lstrip("/")) if base else path
    params = _parse_params(source.get("query_params"))
    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urlencode(params)
    return url


def list_internet_sources(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(INTERNET_SOURCES_PATH)))[:limit]


def get_internet_source(source_id: str) -> dict[str, Any] | None:
    needle = _text(source_id)
    for row in _load_list(INTERNET_SOURCES_PATH):
        if _text(row.get("source_id")) == needle:
            return row
    return None


def register_internet_source(name: str = "", source_type: str = "public_json_url", base_url: str = "", endpoint_path: str = "", allowed_domain: str = "", query_params: Any = "", enabled: bool = False, schedule_enabled: bool = False, notes: str = "") -> dict[str, Any]:
    source_type = _text(source_type, "public_json_url")
    warnings: list[str] = []
    blockers: list[str] = []
    if source_type not in INTERNET_SOURCE_TYPES:
        blockers.append(f"unsupported internet source_type: {source_type}")
    url = _request_url({"base_url": base_url, "endpoint_path": endpoint_path, "query_params": query_params})
    domain = _text(allowed_domain) or _domain(url)
    if not base_url and not endpoint_path:
        blockers.append("base_url or endpoint_path is required")
    if urlparse(url).scheme not in {"http", "https"}:
        blockers.append("internet source must use http or https")
    if schedule_enabled:
        warnings.append("schedule requested but disabled by default until global scheduler and source schedule gates are enabled")
    item = {
        "source_id": f"inet_{uuid4().hex[:12]}",
        "created_at": _now(),
        "name": _text(name, source_type),
        "source_type": source_type,
        "base_url": base_url,
        "endpoint_path": endpoint_path,
        "query_params": _parse_params(query_params),
        "allowed_domain": domain,
        "network_required": True,
        "requires_credentials": False,
        "enabled": bool(enabled),
        "schedule_enabled": False,
        "rate_limit_seconds": internet_config()["rate_limit_seconds"],
        "timeout_seconds": internet_config()["request_timeout_seconds"],
        "max_records_per_run": internet_config()["max_requests_per_run"],
        "last_run_at": "",
        "last_status": "never_run",
        "records_collected": 0,
        "warnings": warnings,
        "blockers": blockers,
        "notes": notes,
        "request_url_redacted": _redact_url(url),
        "secret_values_returned": False,
    }
    rows = _load_list(INTERNET_SOURCES_PATH)
    rows.append(item)
    _save_list(INTERNET_SOURCES_PATH, rows)
    _audit("internet_data_source_registered", item["source_id"], "Internet data source registered.", item)
    return item


def validate_internet_source(source_id: str = "", source: dict[str, Any] | None = None) -> dict[str, Any]:
    source = source or get_internet_source(source_id) or {}
    cfg = internet_config()
    warnings: list[str] = []
    blockers: list[str] = []
    url = _request_url(source)
    parsed = urlparse(url)
    domain = _domain(url)
    allowed_domain = _text(source.get("allowed_domain")) or domain
    if not source:
        blockers.append("source_id must reference a registered internet source")
    if source and source.get("source_type") not in INTERNET_SOURCE_TYPES:
        blockers.append("unsupported internet source type")
    if parsed.scheme not in {"http", "https"}:
        blockers.append("only http/https read-only sources are supported")
    if any(hint in parsed.path.lower() for hint in TRADING_PATH_HINTS):
        blockers.append("endpoint path looks like a trading/order/cancel endpoint and is blocked")
    if not cfg["internet_enabled"]:
        blockers.append("POLYMARKET_DATA_ALLOW_INTERNET is false")
    if not source.get("enabled"):
        blockers.append("internet source is disabled")
    if not cfg["allowed_domains"]:
        blockers.append("POLYMARKET_DATA_ALLOWED_DOMAINS is empty")
    elif domain not in cfg["allowed_domains"] and allowed_domain not in cfg["allowed_domains"]:
        blockers.append(f"domain not allowlisted: {domain}")
    if _safe_int(source.get("max_records_per_run"), cfg["max_requests_per_run"]) > cfg["max_requests_per_run"]:
        warnings.append("source max_records_per_run exceeds global max and will be clamped")
    result = {
        "source_id": _text(source.get("source_id")),
        "source_type": _text(source.get("source_type")),
        "request_url_redacted": _redact_url(url),
        "domain": domain,
        "allowed_domain": allowed_domain,
        "internet_enabled": cfg["internet_enabled"],
        "allowed_domains": cfg["allowed_domains"],
        "source_enabled": bool(source.get("enabled")),
        "status": "source_valid" if not blockers else "source_blocked",
        "warnings": warnings,
        "blockers": blockers,
        "network_would_be_allowed": not blockers,
        "secret_values_returned": False,
    }
    _audit("internet_data_source_validated", result["source_id"], f"Internet source validation: {result['status']}", result)
    return result


def internet_sources_to_csv(rows: list[dict[str, Any]]) -> str:
    return _csv(rows, ["source_id", "created_at", "name", "source_type", "base_url", "endpoint_path", "allowed_domain", "network_required", "requires_credentials", "enabled", "schedule_enabled", "rate_limit_seconds", "timeout_seconds", "max_records_per_run", "last_run_at", "last_status", "records_collected", "warnings", "blockers", "notes"])


def list_internet_ingestion_jobs(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(INTERNET_JOBS_PATH)))[:limit]


def _save_job(job: dict[str, Any]) -> dict[str, Any]:
    rows = _load_list(INTERNET_JOBS_PATH)
    replaced = False
    for i, row in enumerate(rows):
        if row.get("ingestion_job_id") == job.get("ingestion_job_id"):
            rows[i] = job
            replaced = True
            break
    if not replaced:
        rows.append(job)
    _save_list(INTERNET_JOBS_PATH, rows)
    return job


def preview_internet_ingestion(source_id: str = "", operator: str = "", confirmation: str = "", note: str = "") -> dict[str, Any]:
    source = get_internet_source(source_id) if source_id else None
    source = source or {}
    validation = validate_internet_source(source_id=source_id, source=source)
    cfg = internet_config()
    blockers = list(validation.get("blockers", []))
    warnings = list(validation.get("warnings", []))
    if cfg["require_operator_confirmation"] and confirmation != CONFIRMATION_TEXT:
        warnings.append("operator confirmation is required before a real internet ingestion run")
    item = {
        "ingestion_job_id": f"inet_preview_{uuid4().hex[:10]}",
        "created_at": _now(),
        "source_id": source_id,
        "source_type": _text(source.get("source_type"), "unknown"),
        "requested_by": operator,
        "mode": "internet_preview",
        "network_attempted": False,
        "network_would_be_attempted": False if blockers else True,
        "request_url_redacted": validation.get("request_url_redacted", ""),
        "timeout_seconds": cfg["request_timeout_seconds"],
        "rate_limit_seconds": cfg["rate_limit_seconds"],
        "max_request_count": cfg["max_requests_per_run"],
        "storage_target": str(INTERNET_DIR),
        "raw_response_storage_enabled": cfg["store_raw_responses"],
        "status": "ingestion_blocked" if blockers else "ingestion_ready",
        "records_seen": 0,
        "records_written": 0,
        "records_skipped": 0,
        "raw_snapshot_hash": "",
        "normalized_snapshot_hash": "",
        "warnings": warnings,
        "blockers": blockers,
        "notes": note,
        "secret_values_returned": False,
    }
    _audit("internet_ingestion_previewed", source_id, f"Internet ingestion preview: {item['status']}", item)
    return item


def _parse_response_bytes(payload: bytes, source_type: str) -> list[dict[str, Any]]:
    text = payload.decode("utf-8", errors="replace")
    if source_type == "public_csv_url" or text.lstrip().startswith(("market_id,", "timestamp,")):
        rows = list(csv.DictReader(io.StringIO(text)))
        return [{str(k): v for k, v in row.items()} for row in rows]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
            parsed = parsed["data"]
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
            parsed = parsed["items"]
        if isinstance(parsed, list):
            return [item if isinstance(item, dict) else {"value": item} for item in parsed]
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass
    return [{"raw_text_preview": text[:1000]}]


def run_internet_ingestion(source_id: str = "", operator: str = "", confirmation: str = "", note: str = "") -> dict[str, Any]:
    preview = preview_internet_ingestion(source_id=source_id, operator=operator, confirmation=confirmation, note=note)
    cfg = internet_config()
    job_id = f"inet_ing_{uuid4().hex[:12]}"
    job = dict(preview)
    job.update({"ingestion_job_id": job_id, "started_at": _now(), "status": "ingestion_started"})
    blockers = list(job.get("blockers", []))
    warnings = list(job.get("warnings", []))
    if cfg["require_operator_confirmation"] and confirmation != CONFIRMATION_TEXT:
        blockers.append("operator confirmation phrase is required for internet ingestion")
    source = get_internet_source(source_id) if source_id else None
    if blockers or not source:
        job.update({"finished_at": _now(), "status": "ingestion_blocked", "blockers": blockers, "network_attempted": False})
        _save_job(job)
        _audit("internet_ingestion_failed", source_id, "Internet ingestion blocked before network.", job)
        return job
    _audit("internet_ingestion_started", source_id, "Internet ingestion run started.", job)
    url = _request_url(source)
    rows: list[dict[str, Any]] = []
    response_hash = ""
    try:
        request = Request(url, method="GET", headers={"User-Agent": cfg["user_agent"], "Accept": "application/json,text/csv,text/plain;q=0.8"})
        with urlopen(request, timeout=cfg["request_timeout_seconds"]) as response:
            payload = response.read(cfg["max_raw_response_bytes"] + 1)
        job["network_attempted"] = True
        if len(payload) > cfg["max_raw_response_bytes"]:
            blockers.append("raw response exceeded POLYMARKET_DATA_MAX_RAW_RESPONSE_BYTES")
            payload = payload[: cfg["max_raw_response_bytes"]]
        response_hash = hashlib.sha256(payload).hexdigest()
        if cfg["store_raw_responses"]:
            RAW_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
            (RAW_RESPONSES_DIR / f"{job_id}.bin").write_bytes(payload)
        rows = _parse_response_bytes(payload, _text(source.get("source_type")))[: cfg["max_requests_per_run"]]
    except HTTPError as exc:
        blockers.append(f"http error: {exc.code}")
    except URLError as exc:
        blockers.append(f"network error: {type(exc.reason).__name__}")
    except Exception as exc:
        blockers.append(f"fetch failed: {type(exc).__name__}")
    snapshot: dict[str, Any] | None = None
    if rows and not blockers:
        snapshot_type = "custom_snapshot"
        if str(source.get("source_type", "")).startswith("gamma_api"):
            snapshot_type = "gamma_market_snapshot"
        elif str(source.get("source_type", "")).startswith("clob_api"):
            snapshot_type = "clob_market_snapshot"
        snapshot = record_raw_snapshot(source_id=source_id, ingestion_job_id=job_id, snapshot_type=snapshot_type, rows=rows, warnings=warnings, blockers=[], notes=note)
    status = "ingestion_completed" if rows and not blockers else "ingestion_failed"
    job.update({
        "finished_at": _now(),
        "status": status,
        "records_seen": len(rows),
        "records_written": len(rows) if snapshot else 0,
        "records_skipped": 0 if rows else 1,
        "raw_snapshot_id": snapshot.get("snapshot_id") if snapshot else "",
        "raw_snapshot_hash": snapshot.get("content_hash") if snapshot else response_hash,
        "normalized_snapshot_hash": "",
        "warnings": warnings,
        "blockers": blockers,
        "secret_values_returned": False,
    })
    _save_job(job)
    # Update source stats.
    sources = _load_list(INTERNET_SOURCES_PATH)
    for row in sources:
        if row.get("source_id") == source_id:
            row["last_run_at"] = _now()
            row["last_status"] = status
            row["records_collected"] = _safe_int(row.get("records_collected"), 0) + _safe_int(job.get("records_written"), 0)
            break
    _save_list(INTERNET_SOURCES_PATH, sources)
    _audit("internet_ingestion_completed" if status == "ingestion_completed" else "internet_ingestion_failed", source_id, f"Internet ingestion {status}.", job)
    return job


def internet_ingestion_jobs_to_csv(rows: list[dict[str, Any]]) -> str:
    return _csv(rows, ["ingestion_job_id", "created_at", "source_id", "source_type", "requested_by", "mode", "network_attempted", "status", "records_seen", "records_written", "raw_snapshot_hash", "warnings", "blockers", "notes"])


def list_internet_schedules(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(INTERNET_SCHEDULES_PATH)))[:limit]


def register_internet_schedule(source_id: str = "", name: str = "", interval_minutes: int = 60, max_runs_per_day: int = 24, enabled: bool = False, notes: str = "") -> dict[str, Any]:
    cfg = internet_config()
    source = get_internet_source(source_id) if source_id else None
    blockers: list[str] = []
    warnings: list[str] = []
    if not source:
        blockers.append("source_id must reference a registered internet source")
    if not cfg["scheduler_enabled"]:
        warnings.append("global internet ingestion scheduler is disabled")
        enabled = False
    item = {
        "schedule_id": f"sched_{uuid4().hex[:12]}",
        "created_at": _now(),
        "source_id": source_id,
        "name": _text(name, "Internet ingestion schedule"),
        "enabled": bool(enabled),
        "interval_minutes": max(1, _safe_int(interval_minutes, 60)),
        "max_runs_per_day": max(1, _safe_int(max_runs_per_day, 24)),
        "last_run_at": "",
        "next_run_at": "",
        "last_status": "never_run",
        "warnings": warnings,
        "blockers": blockers,
        "notes": notes,
    }
    rows = _load_list(INTERNET_SCHEDULES_PATH)
    rows.append(item)
    _save_list(INTERNET_SCHEDULES_PATH, rows)
    _audit("internet_ingestion_schedule_registered", source_id, "Internet ingestion schedule registered.", item)
    return item


def preview_due_internet_ingestion() -> dict[str, Any]:
    cfg = internet_config()
    due: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not cfg["scheduler_enabled"]:
        blockers.append("POLYMARKET_DATA_INGESTION_SCHEDULER_ENABLED is false")
    now = datetime.now(timezone.utc)
    for schedule in _load_list(INTERNET_SCHEDULES_PATH):
        last = _text(schedule.get("last_run_at"))
        last_dt = None
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
            except Exception:
                last_dt = None
        interval = max(1, _safe_int(schedule.get("interval_minutes"), 60))
        is_due = not last_dt or (now - last_dt) >= timedelta(minutes=interval)
        due.append({**schedule, "is_due": bool(is_due and schedule.get("enabled") and not blockers), "would_run": bool(is_due and schedule.get("enabled") and cfg["scheduler_enabled"])})
    result = {"generated_at": _now(), "scheduler_enabled": cfg["scheduler_enabled"], "due_items": due, "blockers": blockers, "network_attempted": False}
    _audit("internet_ingestion_due_previewed", "", "Due internet ingestion preview generated.", result)
    return result


def internet_schedules_to_csv(rows: list[dict[str, Any]]) -> str:
    return _csv(rows, ["schedule_id", "created_at", "source_id", "name", "enabled", "interval_minutes", "max_runs_per_day", "last_run_at", "next_run_at", "last_status", "warnings", "blockers", "notes"])


def build_internet_workflow() -> dict[str, Any]:
    cfg = internet_config()
    steps = [
        ("Register internet source", "Define approved public/read-only source metadata."),
        ("Validate source", "Check allowlist, timeout, rate limit, and trading-endpoint blockers."),
        ("Preview ingestion", "Confirm no network occurs unless explicitly allowed."),
        ("Run ingestion", "Fetch public data only after gates and confirmation pass."),
        ("Review snapshot", "Inspect hashes, row counts, warnings, and blockers."),
        ("Normalize records", "Convert raw rows into deterministic normalized records."),
        ("Generate/review labels", "Create supervised labels and review them before training."),
        ("Build dataset", "Create manifest-backed train/validation/test splits."),
        ("Preview host training job", "Check job type, dataset, max runtime, and row gates."),
        ("Start host training job", "Only when host jobs are explicitly enabled."),
        ("Review metrics/artifacts", "Inspect local job output and logs."),
        ("Register model metadata", "Default to manual_review_only / live_blocked."),
        ("Queue generated signals", "Manual review queue only; no direct live trading."),
    ]
    result = {
        "version": APP_VERSION,
        "generated_at": _now(),
        "internet_enabled": cfg["internet_enabled"],
        "host_jobs_enabled": cfg["host_jobs_enabled"],
        "source_count": len(_load_list(INTERNET_SOURCES_PATH)),
        "ingestion_job_count": len(_load_list(INTERNET_JOBS_PATH)),
        "host_job_count": len(_load_list(HOST_JOBS_PATH)),
        "steps": [{"step": i + 1, "title": title, "description": desc, "status": "operator_action_required"} for i, (title, desc) in enumerate(steps)],
        "guardrail": "Guidance only. Each action must be explicitly triggered by the operator. Internet ingestion and host training are disabled by default.",
    }
    _audit("internet_training_workflow_viewed", "", "Internet-to-training workflow viewed.", result)
    return result


def list_host_training_jobs(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(HOST_JOBS_PATH)))[:limit]


def get_host_training_job(host_training_job_id: str) -> dict[str, Any] | None:
    needle = _text(host_training_job_id)
    for row in _load_list(HOST_JOBS_PATH):
        if row.get("host_training_job_id") == needle:
            return row
    return None


def _save_host_job(job: dict[str, Any]) -> dict[str, Any]:
    rows = _load_list(HOST_JOBS_PATH)
    replaced = False
    for i, row in enumerate(rows):
        if row.get("host_training_job_id") == job.get("host_training_job_id"):
            rows[i] = job
            replaced = True
            break
    if not replaced:
        rows.append(job)
    _save_list(HOST_JOBS_PATH, rows)
    return job



def _row_cap(cfg: dict[str, Any], requested_max_rows: Any = None, warnings: list[str] | None = None, blockers: list[str] | None = None) -> int:
    warnings = warnings if warnings is not None else []
    blockers = blockers if blockers is not None else []
    requested = _safe_int(requested_max_rows, 0) if requested_max_rows not in (None, "") else 0
    cap = requested or _safe_int(cfg.get("training_max_rows"), _safe_int(cfg.get("training_default_max_rows"), 100000))
    hard = _safe_int(cfg.get("training_hard_max_rows"), 1000000)
    if cap > hard:
        msg = f"requested max rows {cap} exceeds hard cap {hard}"
        if cfg.get("training_block_over_hard_max_rows", True):
            blockers.append(msg)
        else:
            warnings.append(msg + "; clamped to hard cap")
            cap = hard
    return max(1, cap)


def _artifact_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in row.items():
        key_l = str(key).lower()
        if any(hint in key_l for hint in ARTIFACT_SECRET_HINTS):
            clean[str(key)] = "REDACTED"
        elif isinstance(value, dict):
            clean[str(key)] = _artifact_safe_row(value)
        elif isinstance(value, list):
            clean[str(key)] = [(_artifact_safe_row(v) if isinstance(v, dict) else v) for v in value[:20]]
        else:
            clean[str(key)] = value
    return clean


def _load_rows_from_path(path_text: str, max_rows: int) -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    columns: set[str] = set()
    rows_available = 0
    path = Path(path_text).expanduser() if path_text else Path("")
    if not path_text:
        return {"rows": rows, "columns": [], "rows_available": 0, "warnings": warnings, "blockers": ["source_path is empty"]}
    if not path.exists() or not path.is_file():
        return {"rows": rows, "columns": [], "rows_available": 0, "warnings": warnings, "blockers": [f"source path does not exist or is not a file: {path}"]}
    suffix = path.suffix.lower()
    try:
        if suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    rows_available += 1
                    if len(rows) < max_rows:
                        item = json.loads(line)
                        row = item if isinstance(item, dict) else {"value": item}
                        rows.append(row)
                        columns.update(str(k) for k in row.keys())
        elif suffix == ".json":
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                for key in ("items", "records", "rows", "data", "results"):
                    if isinstance(parsed.get(key), list):
                        parsed = parsed[key]
                        break
            if isinstance(parsed, list):
                rows_available = len(parsed)
                for item in parsed[:max_rows]:
                    row = item if isinstance(item, dict) else {"value": item}
                    rows.append(row)
                    columns.update(str(k) for k in row.keys())
            elif isinstance(parsed, dict):
                rows_available = 1
                rows = [parsed]
                columns.update(str(k) for k in parsed.keys())
            else:
                blockers.append("JSON source is not an object, list, or known records container")
        else:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    blockers.append("CSV source has no header")
                else:
                    columns.update(str(k) for k in reader.fieldnames if k is not None)
                for row in reader:
                    rows_available += 1
                    if len(rows) < max_rows:
                        cleaned = {str(k): v for k, v in row.items()}
                        rows.append(cleaned)
                        columns.update(str(k) for k in cleaned.keys())
    except UnicodeDecodeError:
        blockers.append("source file is not UTF-8 text")
    except Exception as exc:
        blockers.append(f"source parse failed: {type(exc).__name__}: {exc}")
    if rows_available > len(rows):
        warnings.append(f"selected first {len(rows)} row(s) from {rows_available} available row(s) because of row cap")
    return {"rows": rows, "columns": sorted(columns), "rows_available": rows_available, "warnings": warnings, "blockers": blockers, "source_path": str(path)}


def _load_snapshot_storage_rows(snapshot: dict[str, Any], max_rows: int) -> dict[str, Any]:
    storage_ref = _text(snapshot.get("storage_ref"))
    if storage_ref:
        return _load_rows_from_path(storage_ref, max_rows)
    return {"rows": [], "columns": [], "rows_available": 0, "warnings": [], "blockers": ["snapshot metadata has no storage_ref"]}


def _load_training_rows(dataset_id: str = "", dataset_build_id: str = "", max_rows: int = 100000) -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []
    references: dict[str, Any] = {"dataset_id": _text(dataset_id), "dataset_build_id": _text(dataset_build_id), "reference_type": "unresolved"}
    rows: list[dict[str, Any]] = []
    columns: set[str] = set()
    rows_available = 0
    selected_dataset_id = _text(dataset_id)
    build: dict[str, Any] | None = None
    category_dataset: dict[str, Any] | None = None
    manifest: dict[str, Any] = {}

    try:
        if dataset_build_id:
            from .data_ingestion import get_dataset_build, get_dataset_manifest
            build = get_dataset_build(dataset_build_id)
            if build:
                references.update({"reference_type": "dataset_build", "dataset_build_status": build.get("status", ""), "manifest_path": build.get("manifest_path", "")})
                selected_dataset_id = selected_dataset_id or _text(build.get("dataset_id"))
                manifest_payload = get_dataset_manifest(dataset_build_id)
                manifest = manifest_payload.get("manifest") if isinstance(manifest_payload, dict) and isinstance(manifest_payload.get("manifest"), dict) else {}
                if manifest.get("dataset_id") and not selected_dataset_id:
                    selected_dataset_id = _text(manifest.get("dataset_id"))
            else:
                try:
                    from .scoped_backfill import list_category_datasets
                    for candidate in list_category_datasets(limit=10000):
                        if _text(candidate.get("dataset_build_id")) == _text(dataset_build_id):
                            category_dataset = candidate
                            break
                except Exception as exc:
                    warnings.append(f"could not inspect category datasets: {type(exc).__name__}")
                if category_dataset:
                    references.update({"reference_type": "category_dataset", "category": category_dataset.get("category", ""), "scope_id": category_dataset.get("scope_id", ""), "dataset_build_status": category_dataset.get("status", "")})
                    selected_dataset_id = selected_dataset_id or _text(category_dataset.get("dataset_id"))
                else:
                    warnings.append(f"dataset_build_id not found in dataset builder or category datasets: {dataset_build_id}")
    except Exception as exc:
        warnings.append(f"dataset build resolution warning: {type(exc).__name__}: {exc}")

    if selected_dataset_id:
        try:
            from .training_lab import get_dataset
            dataset = get_dataset(selected_dataset_id)
            if dataset:
                references.update({"dataset_id": selected_dataset_id, "dataset_name": dataset.get("name", ""), "dataset_type": dataset.get("dataset_type", ""), "reference_type": references.get("reference_type") if references.get("reference_type") != "unresolved" else "training_dataset"})
                source_path = _text(dataset.get("source_path"))
                if source_path:
                    loaded = _load_rows_from_path(source_path, max_rows)
                    rows.extend(loaded["rows"])
                    columns.update(loaded["columns"])
                    rows_available = max(rows_available, _safe_int(loaded.get("rows_available"), 0), _safe_int(dataset.get("row_count"), 0))
                    warnings.extend(loaded.get("warnings", []))
                    blockers.extend(loaded.get("blockers", []))
                else:
                    warnings.append("training dataset metadata has no source_path")
                    rows_available = max(rows_available, _safe_int(dataset.get("row_count"), 0))
            else:
                warnings.append(f"dataset_id not found in Training Lab dataset registry: {selected_dataset_id}")
        except Exception as exc:
            warnings.append(f"dataset registry resolution warning: {type(exc).__name__}: {exc}")

    if not rows and len(rows) < max_rows:
        snapshot_ids: list[str] = []
        for source in (manifest, build or {}, category_dataset or {}):
            values = source.get("snapshot_ids") if isinstance(source, dict) else []
            if isinstance(values, list):
                snapshot_ids.extend(str(v) for v in values if str(v))
        if snapshot_ids:
            try:
                from .data_ingestion import get_raw_snapshot, list_normalized_records
                for snapshot_id in dict.fromkeys(snapshot_ids):
                    if len(rows) >= max_rows:
                        break
                    normalized = list_normalized_records(limit=max_rows - len(rows), snapshot_id=snapshot_id)
                    if normalized:
                        rows.extend(normalized)
                        for row in normalized:
                            columns.update(str(k) for k in row.keys())
                        rows_available += len(normalized)
                    else:
                        snapshot = get_raw_snapshot(snapshot_id)
                        if snapshot:
                            loaded = _load_snapshot_storage_rows(snapshot, max_rows - len(rows))
                            rows.extend(loaded.get("rows", []))
                            columns.update(loaded.get("columns", []))
                            rows_available += _safe_int(loaded.get("rows_available"), 0)
                            warnings.extend(loaded.get("warnings", []))
                            blockers.extend(loaded.get("blockers", []))
            except Exception as exc:
                warnings.append(f"snapshot-backed row load warning: {type(exc).__name__}: {exc}")

    if category_dataset and not rows and len(rows) < max_rows:
        try:
            from .scoped_backfill import _available_rows
            scoped_rows = _available_rows(_text(category_dataset.get("scope_id")))
            rows_available = max(rows_available, len(scoped_rows), _safe_int(category_dataset.get("available_rows"), 0))
            for row in scoped_rows[: max_rows - len(rows)]:
                rows.append(row)
                columns.update(str(k) for k in row.keys())
        except Exception as exc:
            warnings.append(f"category dataset row load warning: {type(exc).__name__}: {exc}")

    if not rows and not selected_dataset_id and not dataset_build_id:
        warnings.append("no dataset_id or dataset_build_id provided; no rows selected")
    if rows_available == 0:
        rows_available = len(rows)
    if not rows and rows_available > 0:
        blockers.append("dataset reference resolved only to metadata; no usable local rows were available")
    if not rows and selected_dataset_id:
        blockers.append("dataset reference has no usable local rows")
    selected = rows[:max_rows]
    if rows_available > len(selected):
        rows_skipped = rows_available - len(selected)
    else:
        rows_skipped = max(0, len(rows) - len(selected))
    references["resolved_dataset_id"] = selected_dataset_id
    references["row_source"] = references.get("reference_type", "unresolved")
    return {
        "rows": selected,
        "columns": sorted(columns),
        "rows_available": rows_available,
        "rows_selected": len(selected),
        "rows_skipped": rows_skipped,
        "warnings": warnings,
        "blockers": blockers,
        "dataset_reference": references,
        "manifest": manifest,
        "secret_values_returned": False,
    }


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, str) and not value.strip())


def _coerce_number(value: Any) -> float | None:
    try:
        if _is_blank(value):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _find_numeric_columns(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    numeric: list[str] = []
    sample = rows[: min(len(rows), 1000)]
    for column in columns:
        values = [row.get(column) for row in sample if not _is_blank(row.get(column))]
        if values and sum(1 for value in values if _coerce_number(value) is not None) / max(1, len(values)) >= 0.8:
            numeric.append(column)
    return numeric


def _timestamp_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps: list[str] = []
    parse_failures = 0
    for row in rows:
        value = ""
        for key, raw in row.items():
            if str(key).lower() in TIMESTAMP_FIELD_HINTS and raw:
                value = str(raw)
                break
        if not value:
            continue
        timestamps.append(value)
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            parse_failures += 1
    return {
        "rows_with_timestamp": len(timestamps),
        "time_min": min(timestamps) if timestamps else "",
        "time_max": max(timestamps) if timestamps else "",
        "parse_failures": parse_failures,
    }


def _price_sanity(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    price_columns = [c for c in columns if c.lower() in PRICE_FIELD_HINTS or "price" in c.lower() or "prob" in c.lower()]
    invalid = 0
    observed = 0
    for row in rows:
        for column in price_columns:
            value = _coerce_number(row.get(column))
            if value is None:
                continue
            observed += 1
            if value < 0 or value > 1:
                invalid += 1
    return {"price_columns": price_columns, "price_values_observed": observed, "invalid_price_values": invalid}


def _label_value(row: dict[str, Any]) -> str:
    for key, value in row.items():
        key_l = str(key).lower()
        if key_l in LABEL_FIELD_HINTS or key_l.startswith("label") or key_l in {"target", "y"}:
            if not _is_blank(value):
                return str(value).strip().lower()
    return ""


def _truthy_label(value: str) -> bool | None:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "up", "win", "winner", "accepted", "approved", "positive", "resolved_yes", "correct"}:
        return True
    if text in {"0", "false", "no", "down", "loss", "loser", "rejected", "denied", "negative", "resolved_no", "incorrect"}:
        return False
    return None


def _dataset_quality_metrics(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    total_cells = max(1, len(rows) * max(1, len(columns)))
    missing = sum(1 for row in rows for column in columns if _is_blank(row.get(column)))
    hashes = [_stable_hash(row) for row in rows]
    duplicates = len(hashes) - len(set(hashes))
    timestamp = _timestamp_summary(rows)
    price = _price_sanity(rows, columns)
    leakage: list[str] = []
    lower_cols = [c.lower() for c in columns]
    if any("label" in c or c in {"target", "outcome", "result"} for c in lower_cols) and not timestamp.get("rows_with_timestamp"):
        leakage.append("label/target-like columns exist without timestamp coverage; verify leakage manually")
    if len(rows) < 30 and rows:
        leakage.append("small dataset; validation metrics will be unstable")
    return {
        "row_count": len(rows),
        "column_count": len(columns),
        "missing_value_count": missing,
        "missing_value_rate": round(missing / total_cells, 6),
        "duplicate_estimate": duplicates,
        "timestamp_coverage": timestamp,
        "probability_price_sanity": price,
        "leakage_warnings": leakage,
    }


def _feature_build_metrics(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    numeric = _find_numeric_columns(rows, columns)
    rejected = [c for c in columns if any(hint in c.lower() for hint in ARTIFACT_SECRET_HINTS)]
    text_like = [c for c in columns if c not in numeric and c not in rejected]
    feature_columns = [c for c in columns if c not in rejected and c.lower() not in LABEL_FIELD_HINTS]
    schema = {"feature_columns": feature_columns, "numeric_columns": numeric, "text_or_categorical_columns": text_like, "schema_hash": _stable_hash(feature_columns)}
    return {
        "detected_feature_columns": feature_columns,
        "numeric_feature_count": len([c for c in numeric if c in feature_columns]),
        "categorical_text_feature_count": len([c for c in text_like if c in feature_columns]),
        "generated_feature_schema_hash": schema["schema_hash"],
        "rejected_unsafe_fields": rejected,
        "feature_schema": schema,
    }


def _baseline_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [_label_value(row) for row in rows]
    labels = [label for label in labels if label]
    n = len(rows)
    train = int(n * 0.7)
    validation = int(n * 0.15)
    test = max(0, n - train - validation)
    if labels:
        counts = Counter(labels)
        majority, majority_count = counts.most_common(1)[0]
        return {
            "sample_count": n,
            "label_count": len(labels),
            "majority_label": majority,
            "baseline_hit_rate": round(majority_count / max(1, len(labels)), 6),
            "train_validation_test_split": {"train": train, "validation": validation, "test": test},
        }
    return {
        "sample_count": n,
        "label_count": 0,
        "baseline_hit_rate": None,
        "fallback_diagnostic_metrics": {"row_count": n, "unique_market_count": len({str(row.get("market_id") or row.get("condition_id") or "") for row in rows if row.get("market_id") or row.get("condition_id")})},
        "train_validation_test_split": {"train": train, "validation": validation, "test": test},
    }


def _first_price(row: dict[str, Any]) -> float | None:
    for key, value in row.items():
        key_l = str(key).lower()
        if key_l in PRICE_FIELD_HINTS or "price" in key_l or "prob" in key_l:
            number = _coerce_number(value)
            if number is not None:
                return number
    return None


def _threshold_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    thresholds = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    scored: list[dict[str, Any]] = []
    labeled_pairs: list[tuple[float, bool]] = []
    prices = []
    for row in rows:
        price = _first_price(row)
        if price is None:
            continue
        prices.append(price)
        label_bool = _truthy_label(_label_value(row))
        if label_bool is not None:
            labeled_pairs.append((price, label_bool))
    for threshold in thresholds:
        if labeled_pairs:
            correct = sum(1 for price, label in labeled_pairs if (price >= threshold) == label)
            score = round(correct / max(1, len(labeled_pairs)), 6)
        else:
            above = sum(1 for price in prices if price >= threshold)
            score = round(above / max(1, len(prices)), 6) if prices else 0
        scored.append({"threshold": threshold, "score": score, "support": len(labeled_pairs) or len(prices), "metric": "hit_rate" if labeled_pairs else "share_above_threshold"})
    best = max(scored, key=lambda row: (row["score"], row["support"])) if scored else {}
    return {"threshold_candidates": thresholds, "score_table": scored, "best_threshold": best, "price_observation_count": len(prices), "label_count": len(labeled_pairs)}


def _momentum_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    priced: list[tuple[str, str, float]] = []
    for row in rows:
        price = _first_price(row)
        if price is None:
            continue
        ts = ""
        for key, value in row.items():
            if str(key).lower() in TIMESTAMP_FIELD_HINTS and value:
                ts = str(value)
                break
        market = str(row.get("market_id") or row.get("condition_id") or row.get("token_id") or "global")
        priced.append((market, ts, price))
    by_market: dict[str, list[tuple[str, float]]] = {}
    for market, ts, price in priced:
        by_market.setdefault(market, []).append((ts, price))
    movements: list[float] = []
    for values in by_market.values():
        values.sort(key=lambda item: item[0])
        for i in range(1, len(values)):
            movements.append(values[i][1] - values[i - 1][1])
    warning = "" if movements else "insufficient time-series price/probability data for momentum windows"
    return {
        "price_probability_observations": len(priced),
        "movement_window_count": len(movements),
        "average_movement": round(sum(movements) / len(movements), 8) if movements else 0,
        "max_up_movement": round(max(movements), 8) if movements else 0,
        "max_down_movement": round(min(movements), 8) if movements else 0,
        "warning": warning,
    }


def _walk_forward_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def ts_value(row: dict[str, Any]) -> str:
        for key, value in row.items():
            if str(key).lower() in TIMESTAMP_FIELD_HINTS and value:
                return str(value)
        return ""
    ordered = sorted(rows, key=ts_value)
    fold_count = min(5, max(1, len(ordered) // 20))
    if len(ordered) < 20:
        fold_count = 1
    fold_size = max(1, len(ordered) // fold_count) if ordered else 0
    folds: list[dict[str, Any]] = []
    for index in range(fold_count):
        fold_rows = ordered[index * fold_size : (index + 1) * fold_size if index < fold_count - 1 else len(ordered)]
        prices = [_first_price(row) for row in fold_rows]
        prices = [p for p in prices if p is not None]
        labels = [_truthy_label(_label_value(row)) for row in fold_rows]
        label_count = len([l for l in labels if l is not None])
        folds.append({"fold": index + 1, "rows": len(fold_rows), "price_observations": len(prices), "label_count": label_count, "mean_price": round(sum(prices) / len(prices), 6) if prices else None})
    warnings = []
    if not any(ts_value(row) for row in rows):
        warnings.append("no timestamp column detected; walk-forward order fell back to existing row order")
    return {"chronological_split_summary": {"rows": len(ordered), "fold_count": fold_count, "fold_size": fold_size}, "per_fold_metrics": folds, "leakage_warnings": warnings}


def _signal_preview_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        price = _first_price(row)
        if price is None or not (0 <= price <= 1):
            continue
        market_id = _text(row.get("market_id") or row.get("condition_id") or row.get("market") or "training_review_market")
        token_id = _text(row.get("token_id") or row.get("asset_id") or row.get("token") or "training_review_token")
        confidence = min(0.99, max(0.01, abs(0.5 - price) + 0.5))
        edge = round(confidence - price, 6)
        candidates.append({
            "candidate_id": f"sigcand_{uuid4().hex[:10]}",
            "market_id": market_id,
            "token_id": token_id,
            "side": "BUY" if edge >= 0 else "REVIEW",
            "reference_price": price,
            "confidence": round(confidence, 6),
            "edge_estimate": edge,
            "rationale": "Dataset-backed host job generated a manual-review-only signal candidate from local rows.",
            "feature_snapshot_hash": _stable_hash(_artifact_safe_row(row)),
            "status": "queued_for_manual_review",
            "manual_review_only": True,
            "can_live_trade": False,
        })
        if len(candidates) >= 50:
            break
    return {"signal_candidates_generated": len(candidates), "manual_review_queue": candidates, "manual_review_only": True, "can_live_trade": False}


def _metrics_for_job(job_type: str, rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    quality = _dataset_quality_metrics(rows, columns)
    if job_type == "dataset_quality_scan":
        return quality
    if job_type == "feature_build":
        return {**quality, **_feature_build_metrics(rows, columns)}
    if job_type == "baseline_training":
        return {**quality, **_baseline_metrics(rows)}
    if job_type == "threshold_training":
        return {**quality, **_threshold_metrics(rows)}
    if job_type == "momentum_training":
        return {**quality, **_momentum_metrics(rows)}
    if job_type == "walk_forward_backtest":
        return {**quality, **_walk_forward_metrics(rows)}
    if job_type == "signal_generation_preview":
        return {**quality, **_signal_preview_metrics(rows)}
    return quality


def _write_job_artifact(job_id: str, name: str, payload: Any, max_artifact_bytes: int) -> dict[str, Any]:
    artifact_dir = HOST_JOB_ARTIFACTS_DIR / job_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / name
    raw = json.dumps(payload, indent=2, sort_keys=True, default=str)
    encoded = raw.encode("utf-8")
    truncated = False
    if len(encoded) > max_artifact_bytes:
        truncated = True
        payload = {
            "artifact_truncated": True,
            "max_artifact_bytes": max_artifact_bytes,
            "original_bytes": len(encoded),
            "summary_hash": _stable_hash(payload),
            "message": "Artifact exceeded configured cap; full payload was not written.",
        }
        raw = json.dumps(payload, indent=2, sort_keys=True, default=str)
    path.write_text(raw, encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size, "truncated": truncated}


def preview_host_training_job(
    job_type: str = "baseline_training",
    dataset_id: str = "",
    dataset_build_id: str = "",
    feature_set_id: str = "",
    model_type: str = "heuristic_baseline",
    operator: str = "",
    confirmation: str = "",
    note: str = "",
    max_rows: Any = None,
) -> dict[str, Any]:
    cfg = internet_config()
    warnings: list[str] = []
    blockers: list[str] = []
    canonical_job_type = _canonical_job_type(job_type)
    if canonical_job_type not in SAFE_JOB_TYPES:
        blockers.append(f"unsupported host training job type: {job_type}")
    allowed = set(cfg["training_allowed_job_types"])
    if canonical_job_type not in allowed:
        warnings.append("job_type is not listed in POLYMARKET_TRAINING_ALLOWED_JOB_TYPES; start will be blocked unless explicitly allowed")
    requested_cap = _row_cap(cfg, max_rows, warnings, blockers)
    probe_cap = min(requested_cap, 1000)
    dataset_probe = _load_training_rows(dataset_id=dataset_id, dataset_build_id=dataset_build_id, max_rows=probe_cap)
    warnings.extend(dataset_probe.get("warnings", []))
    # Preview should not fail merely because no rows were loaded, but it should make the issue visible.
    if not dataset_id and not dataset_build_id:
        warnings.append("no dataset_id or dataset_build_id provided; start will process zero rows unless a dataset reference is supplied")
    item = {
        "host_training_job_id": f"host_preview_{uuid4().hex[:10]}",
        "created_at": _now(),
        "started_at": "",
        "finished_at": "",
        "requested_by": operator,
        "job_type": canonical_job_type,
        "requested_job_type": job_type,
        "dataset_id": dataset_id,
        "dataset_build_id": dataset_build_id,
        "dataset_reference": dataset_probe.get("dataset_reference", {"dataset_id": dataset_id, "dataset_build_id": dataset_build_id}),
        "feature_set_id": feature_set_id,
        "model_type": model_type,
        "status": "job_blocked" if blockers else "job_ready",
        "progress_percent": 0,
        "pid": "internal-python",
        "runtime_seconds": 0,
        "max_runtime_seconds": cfg["training_max_runtime_seconds"],
        "requested_max_rows": requested_cap,
        "rows_available": dataset_probe.get("rows_available", 0),
        "rows_selected": dataset_probe.get("rows_selected", 0),
        "rows_processed": 0,
        "rows_skipped": dataset_probe.get("rows_skipped", 0),
        "batch_size": cfg["training_batch_size"],
        "batches_total": 0,
        "batches_completed": 0,
        "metrics": {},
        "artifact_refs": [],
        "artifact_hashes": [],
        "log_tail": ["Preview only: no host training job was started.", f"Configured row cap: {requested_cap}; preview inspected up to {probe_cap} rows."],
        "warnings": warnings,
        "blockers": blockers,
        "notes": note,
        "host_jobs_enabled": cfg["host_jobs_enabled"],
        "training_outputs_manual_review_only": True,
        "manual_review_only": True,
        "can_live_trade": False,
        "secret_values_returned": False,
    }
    _audit("training_host_job_previewed", dataset_id or dataset_build_id, f"Host training job preview: {item['status']}", item)
    return item


def _complete_host_job(job: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    cfg = internet_config()
    warnings = list(job.get("warnings", []))
    blockers = list(job.get("blockers", []))
    row_cap = _row_cap(cfg, job.get("requested_max_rows"), warnings, blockers)
    batch_size = max(1, _safe_int(job.get("batch_size") or cfg.get("training_batch_size"), 5000))
    job.update({
        "status": "job_running",
        "started_at": _now(),
        "progress_percent": 5,
        "requested_max_rows": row_cap,
        "batch_size": batch_size,
        "log_tail": ["Host job started using approved internal Python job type.", "Loading local dataset-backed records; no shell commands or live trading paths are used."],
        "warnings": warnings,
        "blockers": blockers,
    })
    _save_host_job(job)

    if blockers:
        job.update({
            "finished_at": _now(),
            "status": "job_failed",
            "progress_percent": 100,
            "runtime_seconds": round(time.time() - started, 3),
            "log_tail": job.get("log_tail", [])[-8:] + ["Host job failed before dataset load because blockers were present."],
        })
        _save_host_job(job)
        _audit("training_host_job_failed", job.get("host_training_job_id", ""), "Host training job failed before dataset load.", job)
        return job

    dataset_payload = _load_training_rows(dataset_id=_text(job.get("dataset_id")), dataset_build_id=_text(job.get("dataset_build_id")), max_rows=row_cap)
    warnings.extend(dataset_payload.get("warnings", []))
    blockers.extend(dataset_payload.get("blockers", []))
    rows = dataset_payload.get("rows", []) if isinstance(dataset_payload.get("rows"), list) else []
    columns = dataset_payload.get("columns", []) if isinstance(dataset_payload.get("columns"), list) else []
    rows_available = _safe_int(dataset_payload.get("rows_available"), len(rows))
    rows_selected = len(rows)
    rows_skipped = _safe_int(dataset_payload.get("rows_skipped"), max(0, rows_available - rows_selected))
    batches_total = math.ceil(rows_selected / batch_size) if rows_selected else 0
    job.update({
        "dataset_reference": dataset_payload.get("dataset_reference", job.get("dataset_reference", {})),
        "rows_available": rows_available,
        "rows_selected": rows_selected,
        "rows_processed": 0,
        "rows_skipped": rows_skipped,
        "batches_total": batches_total,
        "batches_completed": 0,
        "warnings": warnings,
        "blockers": blockers,
        "progress_percent": 20,
    })
    _save_host_job(job)

    if blockers or not rows:
        if not rows and "no usable local rows" not in " ".join(blockers).lower():
            blockers.append("no usable local rows were available; job did not generate fake success metrics")
        job.update({
            "finished_at": _now(),
            "status": "job_failed",
            "progress_percent": 100,
            "runtime_seconds": round(time.time() - started, 3),
            "rows_processed": 0,
            "warnings": warnings,
            "blockers": blockers,
            "metrics": {"sample_size": 0, "training_outputs_manual_review_only": True, "manual_review_only": True, "can_live_trade": False},
            "log_tail": job.get("log_tail", [])[-8:] + ["Host job failed: no usable local records were processed."],
        })
        _save_host_job(job)
        _audit("training_host_job_failed", job.get("host_training_job_id", ""), "Host training job failed without usable records.", job)
        return job

    processed = 0
    for start_index in range(0, rows_selected, batch_size):
        batch = rows[start_index : start_index + batch_size]
        processed += len(batch)
        completed = (start_index // batch_size) + 1
        elapsed = time.time() - started
        if elapsed > cfg["training_max_runtime_seconds"]:
            blockers.append(f"max runtime exceeded after {processed} row(s): {cfg['training_max_runtime_seconds']}s")
            break
        progress = 20 + int(60 * (processed / max(1, rows_selected)))
        job.update({"rows_processed": processed, "batches_completed": completed, "progress_percent": min(80, progress), "runtime_seconds": round(elapsed, 3)})
        if completed == 1 or completed == batches_total or completed % 10 == 0:
            job["log_tail"] = (job.get("log_tail", []) + [f"Processed batch {completed}/{batches_total}; rows processed={processed}."])[-12:]
            _save_host_job(job)

    if blockers:
        job.update({
            "finished_at": _now(),
            "status": "job_failed",
            "progress_percent": 100,
            "runtime_seconds": round(time.time() - started, 3),
            "warnings": warnings,
            "blockers": blockers,
            "log_tail": job.get("log_tail", [])[-8:] + ["Host job failed due to runtime or safety blockers."],
        })
        _save_host_job(job)
        _audit("training_host_job_failed", job.get("host_training_job_id", ""), "Host training job failed during batch processing.", job)
        return job

    job_type = _canonical_job_type(_text(job.get("job_type"), "dataset_quality_scan"))
    metrics = _metrics_for_job(job_type, rows[:processed], columns)
    metrics.update({
        "sample_size": processed,
        "rows_available": rows_available,
        "rows_selected": rows_selected,
        "rows_processed": processed,
        "rows_skipped": rows_skipped,
        "batch_size": batch_size,
        "batches_total": batches_total,
        "batches_completed": job.get("batches_completed", batches_total),
        "training_outputs_manual_review_only": True,
        "manual_review_only": True,
        "can_live_trade": False,
    })
    summary_payload = {
        "host_training_job_id": job.get("host_training_job_id"),
        "job_type": job_type,
        "dataset_id": job.get("dataset_id"),
        "dataset_build_id": job.get("dataset_build_id"),
        "dataset_reference": job.get("dataset_reference", {}),
        "model_type": job.get("model_type"),
        "rows_available": rows_available,
        "rows_selected": rows_selected,
        "rows_processed": processed,
        "rows_skipped": rows_skipped,
        "batch_size": batch_size,
        "manual_review_only": True,
        "can_live_trade": False,
        "software_version": APP_VERSION,
        "generated_at": _now(),
    }
    artifact_infos: list[dict[str, Any]] = []
    max_artifact_bytes = _safe_int(cfg.get("training_max_artifact_bytes"), 50000000)
    artifact_infos.append(_write_job_artifact(job["host_training_job_id"], "job_summary.json", summary_payload, max_artifact_bytes))
    artifact_infos.append(_write_job_artifact(job["host_training_job_id"], "metrics.json", metrics, max_artifact_bytes))
    sample_payload = {"sample_size": min(25, processed), "rows": [_artifact_safe_row(row) for row in rows[:25]], "secret_values_returned": False}
    artifact_infos.append(_write_job_artifact(job["host_training_job_id"], "rows_sample_audit.json", sample_payload, max_artifact_bytes))
    if job_type == "feature_build" or "feature_schema" in metrics:
        artifact_infos.append(_write_job_artifact(job["host_training_job_id"], "feature_schema.json", metrics.get("feature_schema", _feature_build_metrics(rows[:processed], columns).get("feature_schema", {})), max_artifact_bytes))
    if job_type == "signal_generation_preview":
        artifact_infos.append(_write_job_artifact(job["host_training_job_id"], "signal_preview.json", {"items": metrics.get("manual_review_queue", []), "manual_review_only": True, "can_live_trade": False}, max_artifact_bytes))
    runtime = time.time() - started
    job.update({
        "finished_at": _now(),
        "status": "job_completed",
        "progress_percent": 100,
        "runtime_seconds": round(runtime, 3),
        "rows_processed": processed,
        "rows_selected": rows_selected,
        "rows_available": rows_available,
        "rows_skipped": rows_skipped,
        "batches_total": batches_total,
        "batches_completed": batches_total,
        "metrics": metrics,
        "artifact_refs": [info["path"] for info in artifact_infos],
        "artifact_hashes": [info["sha256"] for info in artifact_infos],
        "artifact_details": artifact_infos,
        "warnings": warnings,
        "blockers": [],
        "training_outputs_manual_review_only": True,
        "manual_review_only": True,
        "can_live_trade": False,
        "log_tail": (job.get("log_tail", []) + ["Host job completed with real dataset-backed batch processing.", "Artifacts stored in runtime data directory.", "Output is manual-review-only and cannot live-trade."])[-12:],
    })
    _save_host_job(job)
    _audit("training_host_job_completed", job.get("host_training_job_id", ""), "Host training job completed.", job)
    return job


def start_host_training_job(
    job_type: str = "baseline_training",
    dataset_id: str = "",
    dataset_build_id: str = "",
    feature_set_id: str = "",
    model_type: str = "heuristic_baseline",
    operator: str = "",
    confirmation: str = "",
    note: str = "",
    max_rows: Any = None,
) -> dict[str, Any]:
    preview = preview_host_training_job(job_type=job_type, dataset_id=dataset_id, dataset_build_id=dataset_build_id, feature_set_id=feature_set_id, model_type=model_type, operator=operator, confirmation=confirmation, note=note, max_rows=max_rows)
    cfg = internet_config()
    job_id = f"host_{uuid4().hex[:12]}"
    job = dict(preview)
    job["host_training_job_id"] = job_id
    blockers = list(job.get("blockers", []))
    if not cfg["host_jobs_enabled"]:
        blockers.append("POLYMARKET_TRAINING_HOST_JOBS_ENABLED is false")
    if _canonical_job_type(job_type) not in set(cfg["training_allowed_job_types"]):
        blockers.append("job_type is not allowed by POLYMARKET_TRAINING_ALLOWED_JOB_TYPES")
    if confirmation != HOST_CONFIRMATION_TEXT:
        blockers.append("operator confirmation phrase is required to start host training job")
    if not dataset_id and not dataset_build_id:
        blockers.append("dataset_id or dataset_build_id is required to start a dataset-backed host training job")
    if blockers:
        job.update({"status": "job_blocked", "blockers": blockers, "created_at": _now(), "finished_at": _now(), "log_tail": ["Host job blocked before start."], "manual_review_only": True, "can_live_trade": False})
        _save_host_job(job)
        _audit("training_host_job_failed", job_id, "Host training job blocked before start.", job)
        return job
    job.update({"created_at": _now(), "status": "job_queued", "progress_percent": 0, "blockers": [], "manual_review_only": True, "can_live_trade": False})
    _save_host_job(job)
    _audit("training_host_job_started", job_id, "Host training job accepted for approved internal execution.", job)
    # Run quick internal jobs synchronously to keep the local package dependency-light while avoiding shell execution.
    return _complete_host_job(job)

def cancel_host_training_job(host_training_job_id: str = "", operator: str = "", note: str = "") -> dict[str, Any]:
    job = get_host_training_job(host_training_job_id) or {
        "host_training_job_id": host_training_job_id,
        "created_at": _now(),
        "status": "job_blocked",
        "warnings": [],
        "blockers": ["host_training_job_id not found"],
        "log_tail": [],
    }
    if job.get("status") in {"job_completed", "job_failed", "job_cancelled", "job_blocked"}:
        job.setdefault("warnings", []).append("job is not running; cancel recorded as no-op")
    else:
        job["status"] = "job_cancelled"
        job["finished_at"] = _now()
        job.setdefault("log_tail", []).append("Cancel requested by operator; internal job marked cancelled.")
    job["cancel_requested_by"] = operator
    job["notes"] = note or job.get("notes", "")
    _save_host_job(job)
    _audit("training_host_job_cancel_requested", host_training_job_id, "Host training job cancel requested.", job)
    _audit("training_host_job_cancelled", host_training_job_id, "Host training job cancel recorded.", job)
    return job


def host_training_jobs_to_csv(rows: list[dict[str, Any]]) -> str:
    return _csv(rows, [
        "host_training_job_id", "created_at", "started_at", "finished_at", "requested_by", "job_type", "requested_job_type",
        "dataset_id", "dataset_build_id", "feature_set_id", "model_type", "status", "progress_percent", "pid",
        "runtime_seconds", "max_runtime_seconds", "requested_max_rows", "rows_available", "rows_selected", "rows_processed",
        "rows_skipped", "batch_size", "batches_total", "batches_completed", "metrics", "artifact_refs", "artifact_hashes",
        "warnings", "blockers", "notes", "manual_review_only", "can_live_trade",
    ])


def build_internet_data_status() -> dict[str, Any]:
    cfg = internet_config()
    host_jobs = _load_list(HOST_JOBS_PATH)
    latest = host_jobs[-1] if host_jobs else {}
    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "internet_ingestion_enabled": cfg["internet_enabled"],
        "internet_scheduler_enabled": cfg["scheduler_enabled"],
        "allowed_domain_count": len(cfg["allowed_domains"]),
        "internet_source_count": len(_load_list(INTERNET_SOURCES_PATH)),
        "internet_ingestion_job_count": len(_load_list(INTERNET_JOBS_PATH)),
        "internet_schedule_count": len(_load_list(INTERNET_SCHEDULES_PATH)),
        "host_training_jobs_enabled": cfg["host_jobs_enabled"],
        "host_training_job_count": len(host_jobs),
        "running_host_job_count": sum(1 for row in host_jobs if row.get("status") == "job_running"),
        "training_caps": {
            "training_max_rows": cfg["training_max_rows"],
            "training_default_max_rows": cfg["training_default_max_rows"],
            "training_hard_max_rows": cfg["training_hard_max_rows"],
            "training_batch_size": cfg["training_batch_size"],
            "training_block_over_hard_max_rows": cfg["training_block_over_hard_max_rows"],
            "training_max_runtime_seconds": cfg["training_max_runtime_seconds"],
            "training_max_artifact_bytes": cfg["training_max_artifact_bytes"],
            "training_allowed_job_types": cfg["training_allowed_job_types"],
        },
        "latest_rows_processed": latest.get("rows_processed", 0),
        "guardrail": "Internet ingestion and host training jobs are disabled by default. Data ingestion does not trade. Training outputs are manual-review-only and cannot directly live-trade.",
        "warnings": [],
        "blockers": [b for b, active in (("internet ingestion disabled", not cfg["internet_enabled"]), ("host training jobs disabled", not cfg["host_jobs_enabled"])) if active],
    }
