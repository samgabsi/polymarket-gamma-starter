from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .data_ingestion import list_normalized_records, list_raw_snapshots, list_labels
from .internet_ops import internet_config, list_internet_sources

SCOPED_DIR = DATA_DIR / "scoped_backfill"
SCOPES_PATH = SCOPED_DIR / "data_scopes.json"
BACKFILLS_PATH = SCOPED_DIR / "backfill_jobs.json"
CATEGORY_DATASETS_PATH = SCOPED_DIR / "category_datasets.json"
AUDIT_PATH = SCOPED_DIR / "audit_events.json"

SCOPE_TYPES = {
    "category", "theme", "market_id_list", "condition_id_list", "event_slug",
    "market_slug", "keyword_search", "date_range", "resolved_markets",
    "active_markets", "high_volume_markets", "high_liquidity_markets", "custom_filter",
}
PAGINATION_METHODS = {"none", "offset_limit", "cursor", "page_limit", "time_window", "market_batch", "token_batch"}
SPLIT_METHODS = {"chronological", "walk_forward", "holdout_by_market", "holdout_by_date", "market_grouped", "random_seed_fixed"}
DEFAULT_CATEGORIES = {"crypto", "sports", "politics", "elections", "macro", "fed_rates", "daily_price_up_down", "economics", "technology", "weather", "geopolitics"}
CONFIRMATION_TEXT = "I_UNDERSTAND_SCOPED_BACKFILL_FETCHES_PUBLIC_DATA"


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
    text = str(value).strip()
    return text if text else default


def _split(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = _text(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(v).strip() for v in parsed if str(v).strip()]
    except Exception:
        pass
    return [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return _safe_bool(raw, default)


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


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


def _audit(event_type: str, detail: str = "", record_id: str = "", data: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "timestamp": _now(),
        "category": "scoped_backfill",
        "event_type": event_type,
        "source": "scoped_backfill",
        "source_id": record_id,
        "detail": detail,
        "data_hash": _stable_hash(data or {}),
        "secret_values_returned": False,
    }
    rows = _load_list(AUDIT_PATH)
    rows.append(event)
    _save_list(AUDIT_PATH, rows)
    return event


def scoped_config() -> dict[str, Any]:
    return {
        "internet_enabled": _bool_env("POLYMARKET_DATA_ALLOW_INTERNET", False),
        "max_backfill_records": max(1, _safe_int(os.getenv("POLYMARKET_DATA_MAX_BACKFILL_RECORDS", "500000"), 500000)),
        "max_backfill_requests": max(1, _safe_int(os.getenv("POLYMARKET_DATA_MAX_BACKFILL_REQUESTS", "500"), 500)),
        "backfill_batch_size": max(1, _safe_int(os.getenv("POLYMARKET_DATA_BACKFILL_BATCH_SIZE", "1000"), 1000)),
        "max_storage_mb_per_job": max(1, _safe_int(os.getenv("POLYMARKET_DATA_MAX_STORAGE_MB_PER_JOB", "5000"), 5000)),
        "block_large_backfills_by_default": _bool_env("POLYMARKET_DATA_BLOCK_LARGE_BACKFILLS_BY_DEFAULT", True),
        "training_default_max_rows": max(1, _safe_int(os.getenv("POLYMARKET_TRAINING_DEFAULT_MAX_ROWS", "250000"), 250000)),
        "training_hard_max_rows": max(1, _safe_int(os.getenv("POLYMARKET_TRAINING_HARD_MAX_ROWS", "1000000"), 1000000)),
        "training_batch_size": max(1, _safe_int(os.getenv("POLYMARKET_TRAINING_BATCH_SIZE", "5000"), 5000)),
        "training_block_over_hard_max_rows": _bool_env("POLYMARKET_TRAINING_BLOCK_OVER_HARD_MAX_ROWS", True),
        "host_jobs_enabled": _bool_env("POLYMARKET_TRAINING_HOST_JOBS_ENABLED", False),
    }


def estimate_size(records: int, requests: int = 1, record_bytes: int = 1200) -> dict[str, Any]:
    records = max(0, _safe_int(records, 0))
    requests = max(1, _safe_int(requests, 1))
    raw_bytes = records * record_bytes
    normalized = records
    labels = records
    training_rows = records
    if records <= 100000:
        risk = "safe_small"
        recommendation = "Safe for a 16 GB RAM local run with lightweight models."
    elif records <= 250000:
        risk = "safe_medium"
        recommendation = "Medium local run; keep browser/app load low and prefer batched labeling/training."
    elif records <= 500000:
        risk = "caution_large"
        recommendation = "Caution: use batches, monitor disk/RAM, and avoid concurrent heavy jobs."
    elif records <= 1000000:
        risk = "caution_large"
        recommendation = "High caution on 16 GB RAM; cap training rows and use batch jobs only."
    else:
        risk = "blocked_too_large"
        recommendation = "Too large for default local safety posture; reduce scope or explicitly override limits."
    return {
        "expected_records": records,
        "request_count": requests,
        "raw_response_bytes": raw_bytes,
        "storage_bytes_estimate": raw_bytes * 2,
        "storage_mb_estimate": round((raw_bytes * 2) / (1024 * 1024), 2),
        "normalized_record_count": normalized,
        "label_count": labels,
        "dataset_row_count": records,
        "training_rows": training_rows,
        "runtime_risk": risk,
        "disk_risk": risk if raw_bytes < 5_000_000_000 else "blocked_too_large",
        "ram_risk": risk,
        "recommended_caps": {"safe": 100000, "medium": 250000, "caution": 500000, "hard_default": 1000000},
        "risk_level": risk,
        "recommendation": recommendation,
    }


def pagination_plan(method: str = "offset_limit", page_size: int = 1000, max_pages: int = 10, max_requests: int = 10, batch_size: int = 1000, **kwargs: Any) -> dict[str, Any]:
    method = _text(method, "offset_limit")
    warnings: list[str] = []
    blockers: list[str] = []
    if method not in PAGINATION_METHODS:
        blockers.append(f"unsupported pagination method: {method}")
        method = "none"
    page_size = max(1, _safe_int(page_size, 1000))
    max_pages = max(1, _safe_int(max_pages, 10))
    max_requests = max(1, _safe_int(max_requests, max_pages))
    planned = min(max_pages, max_requests)
    if method == "none" and planned > 1:
        warnings.append("pagination_method=none limits plan to one request")
        planned = 1
    return {
        "pagination_method": method,
        "limit_param": _text(kwargs.get("limit_param"), "limit"),
        "offset_param": _text(kwargs.get("offset_param"), "offset"),
        "cursor_param": _text(kwargs.get("cursor_param"), "cursor"),
        "page_param": _text(kwargs.get("page_param"), "page"),
        "page_size": page_size,
        "max_pages": max_pages,
        "max_requests": max_requests,
        "planned_requests": planned,
        "next_cursor": _text(kwargs.get("next_cursor")),
        "next_offset": _safe_int(kwargs.get("next_offset"), 0),
        "next_page": _safe_int(kwargs.get("next_page"), 1),
        "time_window_start": _text(kwargs.get("time_window_start")),
        "time_window_end": _text(kwargs.get("time_window_end")),
        "batch_size": max(1, _safe_int(batch_size, 1000)),
        "supports_pagination": method != "none",
        "warnings": warnings,
        "blockers": blockers,
    }


def list_data_scopes(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(SCOPES_PATH)))[:limit]


def get_data_scope(scope_id: str) -> dict[str, Any] | None:
    for item in _load_list(SCOPES_PATH):
        if item.get("scope_id") == scope_id:
            return item
    return None


def register_data_scope(name: str = "", scope_type: str = "category", category: str = "", keywords: Any = None, market_ids: Any = None, condition_ids: Any = None, event_slugs: Any = None, market_slugs: Any = None, date_start: str = "", date_end: str = "", resolved_only: bool = False, active_only: bool = False, min_volume: Any = 0, min_liquidity: Any = 0, max_markets: Any = 1000, max_records: Any = 100000, notes: str = "") -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []
    scope_type = _text(scope_type, "category")
    if scope_type not in SCOPE_TYPES:
        blockers.append(f"unsupported scope_type: {scope_type}")
    keyword_list = _split(keywords)
    market_list = _split(market_ids)
    condition_list = _split(condition_ids)
    event_list = _split(event_slugs)
    slug_list = _split(market_slugs)
    category = _text(category)
    if scope_type in {"category", "theme"} and not category and not keyword_list:
        warnings.append("category/theme scope has no category or keywords")
    if category and category not in DEFAULT_CATEGORIES:
        warnings.append(f"non-standard category/theme: {category}")
    max_records_int = max(0, _safe_int(max_records, 100000))
    cfg = scoped_config()
    if max_records_int > cfg["training_hard_max_rows"]:
        blockers.append(f"max_records exceeds hard row cap: {cfg['training_hard_max_rows']}")
    item = {
        "scope_id": "scope_" + uuid4().hex[:12],
        "created_at": _now(),
        "name": _text(name, category or scope_type),
        "scope_type": scope_type,
        "category": category,
        "keywords": keyword_list,
        "market_ids": market_list,
        "condition_ids": condition_list,
        "event_slugs": event_list,
        "market_slugs": slug_list,
        "date_start": _text(date_start),
        "date_end": _text(date_end),
        "resolved_only": bool(resolved_only),
        "active_only": bool(active_only),
        "min_volume": _safe_float(min_volume, 0),
        "min_liquidity": _safe_float(min_liquidity, 0),
        "max_markets": max(0, _safe_int(max_markets, 1000)),
        "max_records": max_records_int,
        "status": "scope_blocked" if blockers else "scope_ready",
        "warnings": warnings,
        "blockers": blockers,
        "notes": _text(notes),
        "scope_hash": "",
    }
    item["scope_hash"] = _stable_hash({k: v for k, v in item.items() if k not in {"scope_hash"}})
    rows = _load_list(SCOPES_PATH)
    rows.append(item)
    _save_list(SCOPES_PATH, rows)
    _audit("data_scope_registered", item["name"], item["scope_id"], item)
    return item


def preview_data_scope(scope_id: str = "", **kwargs: Any) -> dict[str, Any]:
    scope = get_data_scope(scope_id) if scope_id else None
    if not scope:
        if kwargs:
            scope = register_data_scope(**kwargs)
        else:
            return {"status": "scope_blocked", "blockers": ["scope_id must reference a registered scope"], "warnings": [], "estimate": estimate_size(0)}
    est = estimate_size(_safe_int(scope.get("max_records"), 0), requests=max(1, min(100, _safe_int(scope.get("max_records"), 0) // 1000 or 1)))
    result = {"status": scope.get("status", "scope_ready"), "scope": scope, "estimate": est, "warnings": scope.get("warnings", []), "blockers": scope.get("blockers", []), "network_attempted": False}
    _audit("data_scope_previewed", scope.get("name", ""), scope.get("scope_id", ""), result)
    return result


def data_scopes_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = ["scope_id", "created_at", "name", "scope_type", "category", "keywords", "market_ids", "date_start", "date_end", "resolved_only", "active_only", "min_volume", "min_liquidity", "max_markets", "max_records", "status", "warnings", "blockers", "notes"]
    return _csv(rows, fields)


def list_backfills(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(BACKFILLS_PATH)))[:limit]


def get_backfill(backfill_job_id: str) -> dict[str, Any] | None:
    for item in _load_list(BACKFILLS_PATH):
        if item.get("backfill_job_id") == backfill_job_id:
            return item
    return None


def _source_ids(value: Any) -> list[str]:
    return _split(value)


def _source_summary(source_ids: list[str]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    rows = list_internet_sources(limit=10000)
    by_id = {row.get("source_id"): row for row in rows}
    selected: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []
    for source_id in source_ids:
        row = by_id.get(source_id)
        if not row:
            blockers.append(f"source not found: {source_id}")
        else:
            selected.append(row)
            if not row.get("enabled"):
                warnings.append(f"source disabled: {source_id}")
    if not source_ids:
        warnings.append("no source_ids supplied; preview uses scope-only sizing")
    return selected, warnings, blockers


def preview_backfill(scope_id: str = "", source_ids: Any = None, name: str = "", requested_by: str = "", mode: str = "preview", max_records: Any = None, max_requests: Any = None, max_runtime_seconds: Any = 300, rate_limit_seconds: Any = 1, pagination_method: str = "offset_limit", page_size: Any = 1000, max_pages: Any = 10, batch_size: Any = 1000, confirmation: str = "", notes: str = "") -> dict[str, Any]:
    cfg = scoped_config()
    scope = get_data_scope(scope_id) if scope_id else None
    warnings: list[str] = []
    blockers: list[str] = []
    if not scope:
        blockers.append("scope_id must reference a registered scope")
        scope_max = 0
    else:
        warnings.extend(scope.get("warnings", []))
        blockers.extend(scope.get("blockers", []))
        scope_max = _safe_int(scope.get("max_records"), 0)
    source_id_list = _source_ids(source_ids)
    sources, source_warnings, source_blockers = _source_summary(source_id_list)
    warnings.extend(source_warnings)
    blockers.extend(source_blockers)
    if sources and not cfg["internet_enabled"]:
        blockers.append("network ingestion is disabled by default; set POLYMARKET_DATA_ALLOW_INTERNET=true for real fetches")
    max_records_int = _safe_int(max_records, scope_max or cfg["max_backfill_records"])
    if max_records_int <= 0:
        max_records_int = min(scope_max or cfg["max_backfill_records"], cfg["max_backfill_records"])
    max_requests_int = min(cfg["max_backfill_requests"], max(1, _safe_int(max_requests, cfg["max_backfill_requests"])))
    plan = pagination_plan(pagination_method, page_size, max_pages, max_requests_int, batch_size)
    warnings.extend(plan.get("warnings", []))
    blockers.extend(plan.get("blockers", []))
    planned_records = min(max_records_int, plan["planned_requests"] * plan["page_size"])
    if max_records_int > cfg["max_backfill_records"]:
        blockers.append(f"requested max_records exceeds configured max backfill records: {cfg['max_backfill_records']}")
    if cfg["block_large_backfills_by_default"] and max_records_int > 500000:
        blockers.append("large backfills above 500k are blocked by default")
    estimate = estimate_size(planned_records, plan["planned_requests"])
    if estimate["storage_mb_estimate"] > cfg["max_storage_mb_per_job"]:
        blockers.append(f"estimated storage exceeds per-job cap: {cfg['max_storage_mb_per_job']} MB")
    network_allowed = cfg["internet_enabled"] and bool(sources) and not blockers and confirmation == CONFIRMATION_TEXT
    return {
        "backfill_job_id": "preview_" + uuid4().hex[:8],
        "created_at": _now(),
        "requested_by": _text(requested_by, "local"),
        "scope_id": scope_id,
        "scope": scope or {},
        "source_ids": source_id_list,
        "name": _text(name, (scope or {}).get("name", "scoped_backfill")),
        "mode": _text(mode, "preview"),
        "status": "backfill_blocked" if blockers else "backfill_ready",
        "network_attempted": False,
        "network_would_be_allowed": network_allowed,
        "cursor": "",
        "offset": plan["next_offset"],
        "page": plan["next_page"],
        "pages_completed": 0,
        "requests_attempted": 0,
        "records_seen": 0,
        "records_written": 0,
        "records_skipped": 0,
        "duplicates_skipped": 0,
        "estimated_records_total": planned_records,
        "max_records": max_records_int,
        "max_requests": max_requests_int,
        "max_runtime_seconds": max(1, _safe_int(max_runtime_seconds, 300)),
        "rate_limit_seconds": _safe_float(rate_limit_seconds, 1.0),
        "storage_bytes_estimate": estimate["storage_bytes_estimate"],
        "pagination_plan": plan,
        "size_estimate": estimate,
        "deduplication_plan": {"keys": ["source_id", "market_id", "condition_id", "token_id", "timestamp", "record_type", "content_hash", "schema_version"], "best_effort": True},
        "batch_plan": {"batch_size": plan["batch_size"], "normalization_batches": max(1, math.ceil(planned_records / max(1, plan["batch_size"]))), "labeling_batches": max(1, math.ceil(planned_records / max(1, plan["batch_size"])))},
        "warnings": warnings,
        "blockers": blockers,
        "notes": _text(notes),
    }


def start_backfill(**kwargs: Any) -> dict[str, Any]:
    preview = preview_backfill(**kwargs)
    preview["backfill_job_id"] = "backfill_" + uuid4().hex[:12]
    preview["started_at"] = _now()
    preview["finished_at"] = ""
    if preview["blockers"]:
        preview["status"] = "backfill_blocked"
        _audit("scoped_backfill_previewed", preview.get("name", ""), preview["backfill_job_id"], preview)
    else:
        # This milestone records an operator-controlled backfill plan. Network fetching remains in the internet ingestion layer.
        preview["status"] = "backfill_completed"
        preview["finished_at"] = _now()
        preview["records_seen"] = 0
        preview["records_written"] = 0
        preview["requests_attempted"] = 0
        preview["warnings"] = preview.get("warnings", []) + ["start recorded plan metadata only; use internet ingestion for actual fetches"]
        _audit("scoped_backfill_started", preview.get("name", ""), preview["backfill_job_id"], preview)
        _audit("scoped_backfill_completed", preview.get("name", ""), preview["backfill_job_id"], preview)
    rows = _load_list(BACKFILLS_PATH)
    rows.append(preview)
    _save_list(BACKFILLS_PATH, rows)
    return preview


def pause_backfill(backfill_job_id: str, operator: str = "", note: str = "") -> dict[str, Any]:
    rows = _load_list(BACKFILLS_PATH)
    for row in rows:
        if row.get("backfill_job_id") == backfill_job_id:
            row["status"] = "backfill_paused"
            row["pause_requested_by"] = _text(operator, "local")
            row["notes"] = (row.get("notes", "") + "\n" + _text(note)).strip()
            _save_list(BACKFILLS_PATH, rows)
            _audit("scoped_backfill_paused", row.get("name", ""), backfill_job_id, row)
            return row
    return {"backfill_job_id": backfill_job_id, "status": "backfill_not_found", "blockers": ["backfill job not found"]}


def cancel_backfill(backfill_job_id: str, operator: str = "", note: str = "") -> dict[str, Any]:
    rows = _load_list(BACKFILLS_PATH)
    for row in rows:
        if row.get("backfill_job_id") == backfill_job_id:
            row["status"] = "backfill_cancelled"
            row["cancel_requested_by"] = _text(operator, "local")
            row["notes"] = (row.get("notes", "") + "\n" + _text(note)).strip()
            _save_list(BACKFILLS_PATH, rows)
            _audit("scoped_backfill_cancel_requested", row.get("name", ""), backfill_job_id, row)
            _audit("scoped_backfill_cancelled", row.get("name", ""), backfill_job_id, row)
            return row
    return {"backfill_job_id": backfill_job_id, "status": "backfill_not_found", "blockers": ["backfill job not found"]}


def backfills_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = ["backfill_job_id", "created_at", "requested_by", "scope_id", "source_ids", "name", "mode", "status", "network_attempted", "started_at", "finished_at", "cursor", "offset", "page", "pages_completed", "requests_attempted", "records_seen", "records_written", "records_skipped", "duplicates_skipped", "estimated_records_total", "max_records", "max_requests", "max_runtime_seconds", "rate_limit_seconds", "storage_bytes_estimate", "warnings", "blockers", "notes"]
    return _csv(rows, fields)


def _available_rows(scope_id: str = "") -> list[dict[str, Any]]:
    rows = list_normalized_records(limit=100000)
    if not scope_id:
        return rows
    scope = get_data_scope(scope_id)
    if not scope:
        return []
    markets = set(scope.get("market_ids") or [])
    conditions = set(scope.get("condition_ids") or [])
    keywords = [k.lower() for k in (scope.get("keywords") or [])]
    out = []
    for row in rows:
        text = json.dumps(row, default=str).lower()
        if markets and row.get("market_id") not in markets:
            continue
        if conditions and row.get("condition_id") not in conditions:
            continue
        if keywords and not any(k in text for k in keywords):
            continue
        out.append(row)
    return out


def preview_category_dataset(scope_id: str = "", category: str = "", source_ids: Any = None, snapshot_ids: Any = None, label_types: Any = None, feature_groups: Any = None, date_start: str = "", date_end: str = "", market_ids: Any = None, condition_ids: Any = None, resolved_only: bool = False, active_only: bool = False, split_method: str = "chronological", max_rows: Any = None, train_rows_target: Any = None, validation_rows_target: Any = None, test_rows_target: Any = None, operator: str = "", note: str = "") -> dict[str, Any]:
    cfg = scoped_config()
    warnings: list[str] = []
    blockers: list[str] = []
    scope = get_data_scope(scope_id) if scope_id else None
    if scope_id and not scope:
        blockers.append("scope_id not found")
    row_cap = _safe_int(max_rows, cfg["training_default_max_rows"])
    if row_cap > cfg["training_hard_max_rows"] and cfg["training_block_over_hard_max_rows"]:
        blockers.append(f"max_rows exceeds hard cap: {cfg['training_hard_max_rows']}")
    if split_method not in SPLIT_METHODS:
        blockers.append(f"unsupported split_method: {split_method}")
    available = _available_rows(scope_id)
    row_count = min(len(available), row_cap)
    if row_count == 0:
        warnings.append("no normalized records are currently available for this scope; build will create metadata only")
        row_count = min(row_cap, _safe_int((scope or {}).get("max_records"), 0) or 0)
    estimate = estimate_size(row_count, requests=max(1, row_count // 1000 or 1))
    if estimate["risk_level"] == "blocked_too_large":
        blockers.append("dataset estimate is blocked_too_large")
    train_target = _safe_int(train_rows_target, int(row_count * 0.7))
    val_target = _safe_int(validation_rows_target, int(row_count * 0.15))
    test_target = _safe_int(test_rows_target, max(0, row_count - train_target - val_target))
    leakage_warnings = []
    if split_method in {"random_seed_fixed"}:
        leakage_warnings.append("random splits can leak market-time information; prefer chronological or walk-forward")
    if row_count < 1000:
        leakage_warnings.append("small sample size; metrics may not be meaningful")
    return {
        "dataset_build_id": "preview_" + uuid4().hex[:8],
        "created_at": _now(),
        "name": _text(category or (scope or {}).get("name"), "category_dataset"),
        "scope_id": scope_id,
        "category": _text(category or (scope or {}).get("category")),
        "source_ids": _source_ids(source_ids),
        "snapshot_ids": _split(snapshot_ids),
        "label_types": _split(label_types),
        "feature_groups": _split(feature_groups) or ["market_metadata", "price_movement", "spread_liquidity"],
        "date_start": _text(date_start),
        "date_end": _text(date_end),
        "market_ids": _split(market_ids) or ((scope or {}).get("market_ids") or []),
        "condition_ids": _split(condition_ids) or ((scope or {}).get("condition_ids") or []),
        "resolved_only": bool(resolved_only),
        "active_only": bool(active_only),
        "split_method": split_method,
        "max_rows": row_cap,
        "train_rows": min(train_target, row_count),
        "validation_rows": min(val_target, max(0, row_count - train_target)),
        "test_rows": min(test_target, max(0, row_count - train_target - val_target)),
        "available_rows": len(available),
        "dataset_id": "",
        "manifest_hash": "",
        "content_hash": "",
        "quality_status": "quality_blocked" if blockers else ("quality_pass_with_warnings" if warnings or leakage_warnings else "quality_pass"),
        "size_estimate": estimate,
        "leakage_warnings": leakage_warnings,
        "warnings": warnings,
        "blockers": blockers,
        "status": "category_dataset_blocked" if blockers else "category_dataset_ready",
        "notes": _text(note),
    }


def build_category_dataset(**kwargs: Any) -> dict[str, Any]:
    preview = preview_category_dataset(**kwargs)
    preview["dataset_build_id"] = "catds_" + uuid4().hex[:12]
    if preview["blockers"]:
        preview["status"] = "category_dataset_blocked"
    else:
        preview["dataset_id"] = "dataset_" + uuid4().hex[:12]
        preview["manifest_hash"] = _stable_hash(preview)
        preview["content_hash"] = _stable_hash({"scope_id": preview.get("scope_id"), "rows": preview.get("max_rows"), "features": preview.get("feature_groups"), "labels": preview.get("label_types")})
        preview["status"] = "category_dataset_built"
    rows = _load_list(CATEGORY_DATASETS_PATH)
    rows.append(preview)
    _save_list(CATEGORY_DATASETS_PATH, rows)
    _audit("category_dataset_built" if not preview["blockers"] else "category_dataset_previewed", preview.get("name", ""), preview["dataset_build_id"], preview)
    return preview


def list_category_datasets(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(CATEGORY_DATASETS_PATH)))[:limit]


def category_datasets_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = ["dataset_build_id", "created_at", "name", "scope_id", "category", "source_ids", "snapshot_ids", "label_types", "feature_groups", "split_method", "max_rows", "train_rows", "validation_rows", "test_rows", "dataset_id", "manifest_hash", "content_hash", "quality_status", "status", "warnings", "blockers", "notes"]
    return _csv(rows, fields)


def build_scoped_status() -> dict[str, Any]:
    scopes = _load_list(SCOPES_PATH)
    backfills = _load_list(BACKFILLS_PATH)
    catds = _load_list(CATEGORY_DATASETS_PATH)
    return {
        "version": APP_VERSION,
        "scope_count": len(scopes),
        "backfill_count": len(backfills),
        "category_dataset_count": len(catds),
        "config": scoped_config(),
        "guardrail": "SCOPED BACKFILL · NETWORK DISABLED BY DEFAULT · BATCHED INGESTION · MEMORY-SAFE TRAINING · NO LIVE TRADING",
        "recommended_row_caps": {"safe": 100000, "medium": 250000, "caution": 500000, "hard_default": 1000000},
    }
