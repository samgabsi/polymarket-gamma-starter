from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .training_lab import register_dataset

DATA_SYSTEM_DIR = DATA_DIR / "data_system"
SOURCES_PATH = DATA_SYSTEM_DIR / "sources.json"
INGESTION_JOBS_PATH = DATA_SYSTEM_DIR / "ingestion_jobs.json"
SNAPSHOTS_PATH = DATA_SYSTEM_DIR / "snapshots.json"
NORMALIZED_PATH = DATA_SYSTEM_DIR / "normalized_records.json"
LABELS_PATH = DATA_SYSTEM_DIR / "labels.json"
DATASET_BUILDS_PATH = DATA_SYSTEM_DIR / "dataset_builds.json"
AUDIT_PATH = DATA_SYSTEM_DIR / "audit_events.json"
RAW_DIR = DATA_SYSTEM_DIR / "raw_snapshots"
BUILT_DATASETS_DIR = DATA_SYSTEM_DIR / "built_datasets"
MANIFESTS_DIR = DATA_SYSTEM_DIR / "manifests"

SUPPORTED_SOURCE_TYPES = {
    "gamma_markets",
    "clob_markets",
    "clob_orderbook",
    "clob_trades",
    "price_snapshots",
    "market_snapshots",
    "paper_tickets",
    "paper_approvals",
    "live_order_ledger",
    "fake_adapter_ledger",
    "strategy_signal_history",
    "execution_quality_simulations",
    "custom_csv",
    "custom_json",
}
NETWORK_SOURCE_TYPES = {"gamma_markets", "clob_markets", "clob_orderbook", "clob_trades"}
SNAPSHOT_TYPE_BY_SOURCE = {
    "gamma_markets": "gamma_market_snapshot",
    "clob_markets": "clob_market_snapshot",
    "clob_orderbook": "orderbook_snapshot",
    "clob_trades": "trade_snapshot",
    "price_snapshots": "price_snapshot",
    "market_snapshots": "custom_snapshot",
    "paper_tickets": "ledger_snapshot",
    "paper_approvals": "ledger_snapshot",
    "live_order_ledger": "ledger_snapshot",
    "fake_adapter_ledger": "ledger_snapshot",
    "strategy_signal_history": "signal_snapshot",
    "execution_quality_simulations": "custom_snapshot",
    "custom_csv": "custom_snapshot",
    "custom_json": "custom_snapshot",
}
LOCAL_SOURCE_TYPES = SUPPORTED_SOURCE_TYPES - NETWORK_SOURCE_TYPES
LABEL_TYPES = {
    "price_movement_over_horizon",
    "probability_movement_over_horizon",
    "resolved_outcome",
    "simulated_edge_exceeded_threshold",
    "spread_acceptable",
    "liquidity_acceptable",
    "execution_quality_acceptable",
    "signal_accepted_rejected_historically",
    "paper_approval_accepted_rejected",
    "manual_custom_label",
}
SPLIT_METHODS = {"chronological", "market_grouped", "random_seed_fixed", "walk_forward", "holdout_by_market", "holdout_by_date"}


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
        if value is None or value == "":
            return default
        number = float(value)
        if not math.isfinite(number):
            return default
        return number
    except Exception:
        return default


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        pass
    return ""


def _rows_to_csv(rows: list[dict[str, Any]], fields: list[str]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        clean: dict[str, Any] = {}
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, (list, dict)):
                value = json.dumps(value, sort_keys=True, default=str)
            clean[field] = value
        writer.writerow(clean)
    return out.getvalue()


def _read_rows_from_path(path_text: str, limit: int = 10000) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    columns: list[str] = []
    path = Path(path_text).expanduser() if path_text else Path("")
    if not path_text:
        return rows, columns, warnings, ["source_path is required for local/import ingestion"]
    if not path.exists():
        return rows, columns, warnings, [f"source path does not exist: {path}"]
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return rows, columns, warnings, ["source file is not UTF-8 text"]
    except Exception as exc:
        return rows, columns, warnings, [f"source file could not be read: {type(exc).__name__}"]
    if not raw.strip():
        return rows, columns, warnings, ["source file is empty"]
    try:
        if path.suffix.lower() == ".json":
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
                parsed = parsed["items"]
            if isinstance(parsed, list):
                for item in parsed[:limit]:
                    rows.append(item if isinstance(item, dict) else {"value": item})
            elif isinstance(parsed, dict):
                rows.append(parsed)
            else:
                blockers.append("JSON source is not an object or list")
        else:
            reader = csv.DictReader(io.StringIO(raw))
            if not reader.fieldnames:
                blockers.append("CSV source has no header")
            for index, row in enumerate(reader):
                if index >= limit:
                    warnings.append(f"only first {limit} rows imported")
                    break
                rows.append({str(k): v for k, v in row.items()})
    except Exception as exc:
        blockers.append(f"source parse failed: {type(exc).__name__}")
    columns = sorted({str(key) for row in rows for key in row.keys()})
    return rows, columns, warnings, blockers


def _audit(event_type: str, source_id: str = "", detail: str = "", data: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "timestamp": _now(),
        "category": "data_system",
        "event_type": event_type,
        "source": "data_ingestion",
        "source_id": source_id,
        "detail": detail,
        "data_hash": _stable_hash(data or {}),
        "secret_values_returned": False,
    }
    rows = _load_list(AUDIT_PATH)
    rows.append(event)
    _save_list(AUDIT_PATH, rows)
    return event


def list_data_audit(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(AUDIT_PATH)))[:limit]


def list_data_sources(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(SOURCES_PATH)))[:limit]


def get_data_source(source_id: str) -> dict[str, Any] | None:
    needle = _text(source_id)
    for row in _load_list(SOURCES_PATH):
        if _text(row.get("source_id")) == needle:
            return row
    return None


def register_data_source(name: str = "", source_type: str = "custom_csv", source_path: str = "", endpoint_name: str = "", mode: str = "local_import", enabled: bool = True, schedule_enabled: bool = False, notes: str = "") -> dict[str, Any]:
    source_type = _text(source_type, "custom_csv")
    warnings: list[str] = []
    blockers: list[str] = []
    if source_type not in SUPPORTED_SOURCE_TYPES:
        blockers.append(f"unsupported source_type: {source_type}")
    network_required = source_type in NETWORK_SOURCE_TYPES or str(mode).lower() in {"network", "readonly_network"}
    if network_required:
        enabled = False if enabled is True else enabled
        warnings.append("network source registered disabled by default; explicit opt-in is required before network ingestion")
    if schedule_enabled:
        warnings.append("scheduler requested but forced disabled; background ingestion is not enabled by default")
    item = {
        "source_id": f"src_{uuid4().hex[:12]}",
        "created_at": _now(),
        "name": _text(name, source_type),
        "source_type": source_type,
        "mode": _text(mode, "local_import"),
        "network_required": bool(network_required),
        "enabled": bool(enabled and not network_required),
        "schedule_enabled": False,
        "source_path": source_path,
        "endpoint_name": endpoint_name,
        "last_run_at": "",
        "last_status": "never_run",
        "records_collected": 0,
        "warnings": warnings,
        "blockers": blockers,
        "notes": notes,
    }
    rows = _load_list(SOURCES_PATH)
    rows.append(item)
    _save_list(SOURCES_PATH, rows)
    _audit("data_source_registered", item["source_id"], "Data source registered.", item)
    return item


def data_sources_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["source_id", "created_at", "name", "source_type", "mode", "network_required", "enabled", "schedule_enabled", "source_path", "endpoint_name", "last_run_at", "last_status", "records_collected", "warnings", "blockers", "notes"])


def preview_data_ingestion(source_id: str = "", operator: str = "", note: str = "") -> dict[str, Any]:
    source = get_data_source(source_id) if source_id else None
    warnings: list[str] = []
    blockers: list[str] = []
    network_attempted = False
    if not source:
        blockers.append("source_id must reference a registered data source")
        source = {}
    source_type = _text(source.get("source_type"), "unknown")
    network_required = bool(source.get("network_required"))
    if network_required:
        blockers.append("network ingestion is disabled by default; set POLYMARKET_DATA_ALLOW_NETWORK=true and explicitly run an opt-in workflow")
    if source and not source.get("enabled") and not network_required:
        warnings.append("source is not enabled, but local preview can still inspect configuration")
    if source and source_type in LOCAL_SOURCE_TYPES:
        rows, columns, read_warnings, read_blockers = _read_rows_from_path(_text(source.get("source_path")), limit=1000)
        warnings.extend(read_warnings)
        blockers.extend(read_blockers)
        records_seen = len(rows)
    else:
        rows = []
        columns = []
        records_seen = 0
    status = "ingestion_blocked" if blockers else "ingestion_ready"
    item = {
        "ingestion_job_id": f"preview_{uuid4().hex[:10]}",
        "created_at": _now(),
        "source_id": source_id,
        "source_type": source_type,
        "requested_by": operator,
        "mode": _text(source.get("mode"), "local_import"),
        "network_attempted": network_attempted,
        "started_at": "",
        "finished_at": "",
        "status": status,
        "records_seen": records_seen,
        "records_written": 0,
        "records_skipped": 0,
        "raw_snapshot_hash": "",
        "normalized_snapshot_hash": "",
        "columns": columns,
        "warnings": warnings,
        "blockers": blockers,
        "notes": note,
        "secret_values_returned": False,
    }
    _audit("data_ingestion_previewed", source_id, f"Ingestion preview status: {status}", item)
    return item


def _update_source_after_run(source_id: str, status: str, records_collected: int) -> None:
    rows = _load_list(SOURCES_PATH)
    for row in rows:
        if row.get("source_id") == source_id:
            row["last_run_at"] = _now()
            row["last_status"] = status
            row["records_collected"] = _safe_int(row.get("records_collected"), 0) + records_collected
            break
    _save_list(SOURCES_PATH, rows)


def record_raw_snapshot(source_id: str, ingestion_job_id: str, snapshot_type: str, rows: list[dict[str, Any]], warnings: list[str] | None = None, blockers: list[str] | None = None, notes: str = "") -> dict[str, Any]:
    snapshot_id = f"snap_{uuid4().hex[:12]}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    storage_ref = RAW_DIR / f"{snapshot_id}.json"
    storage_ref.write_text(json.dumps(rows, indent=2, sort_keys=True, default=str), encoding="utf-8")
    markets = sorted({str(row.get("market_id") or row.get("condition_id") or "") for row in rows if row.get("market_id") or row.get("condition_id")})[:100]
    tokens = sorted({str(row.get("token_id") or row.get("asset_id") or "") for row in rows if row.get("token_id") or row.get("asset_id")})[:100]
    times: list[str] = []
    for row in rows:
        for key in ("timestamp", "created_at", "updated_at", "time"):
            value = row.get(key)
            if value:
                times.append(str(value))
                break
    item = {
        "snapshot_id": snapshot_id,
        "created_at": _now(),
        "source_id": source_id,
        "ingestion_job_id": ingestion_job_id,
        "snapshot_type": snapshot_type,
        "record_count": len(rows),
        "content_hash": _stable_hash(rows),
        "schema_hash": _stable_hash(sorted({str(key) for row in rows for key in row.keys()})),
        "time_min": min(times) if times else "",
        "time_max": max(times) if times else "",
        "markets": markets,
        "tokens": tokens,
        "storage_ref": str(storage_ref),
        "status": "snapshot_blocked" if blockers else "snapshot_recorded",
        "warnings": warnings or [],
        "blockers": blockers or [],
        "notes": notes,
    }
    snapshots = _load_list(SNAPSHOTS_PATH)
    snapshots.append(item)
    _save_list(SNAPSHOTS_PATH, snapshots)
    _audit("data_snapshot_recorded", snapshot_id, "Raw snapshot metadata recorded.", item)
    return item


def run_data_ingestion(source_id: str = "", operator: str = "", note: str = "") -> dict[str, Any]:
    preview = preview_data_ingestion(source_id=source_id, operator=operator, note=note)
    source = get_data_source(source_id) if source_id else None
    job_id = f"ing_{uuid4().hex[:12]}"
    job = dict(preview)
    job.update({"ingestion_job_id": job_id, "started_at": _now(), "status": "ingestion_started"})
    _audit("data_ingestion_started", job_id, "Ingestion run started.", job)
    rows: list[dict[str, Any]] = []
    columns: list[str] = []
    warnings = list(preview.get("warnings", []))
    blockers = list(preview.get("blockers", []))
    if not blockers and source:
        rows, columns, read_warnings, read_blockers = _read_rows_from_path(_text(source.get("source_path")), limit=100000)
        warnings.extend(read_warnings)
        blockers.extend(read_blockers)
    snapshot: dict[str, Any] | None = None
    if rows and not blockers and source:
        snapshot = record_raw_snapshot(source_id, job_id, SNAPSHOT_TYPE_BY_SOURCE.get(_text(source.get("source_type")), "custom_snapshot"), rows, warnings=warnings, blockers=[], notes=note)
    job.update({
        "finished_at": _now(),
        "status": "ingestion_failed" if blockers else "ingestion_completed" if snapshot else "ingestion_skipped",
        "records_seen": len(rows),
        "records_written": len(rows) if snapshot else 0,
        "records_skipped": 0 if snapshot else len(rows),
        "raw_snapshot_hash": (snapshot or {}).get("content_hash", ""),
        "normalized_snapshot_hash": "",
        "columns": columns,
        "warnings": warnings,
        "blockers": blockers,
        "network_attempted": False,
    })
    jobs = _load_list(INGESTION_JOBS_PATH)
    jobs.append(job)
    _save_list(INGESTION_JOBS_PATH, jobs)
    _update_source_after_run(source_id, job["status"], len(rows) if snapshot else 0)
    _audit("data_ingestion_failed" if blockers else "data_ingestion_completed", job_id, f"Ingestion run finished with status {job['status']}.", job)
    return {"job": job, "snapshot": snapshot, "secret_values_returned": False}


def list_ingestion_jobs(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(INGESTION_JOBS_PATH)))[:limit]


def ingestion_jobs_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["ingestion_job_id", "created_at", "source_id", "source_type", "requested_by", "mode", "network_attempted", "started_at", "finished_at", "status", "records_seen", "records_written", "records_skipped", "raw_snapshot_hash", "normalized_snapshot_hash", "warnings", "blockers", "notes"])


def list_raw_snapshots(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(SNAPSHOTS_PATH)))[:limit]


def get_raw_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    needle = _text(snapshot_id)
    for row in _load_list(SNAPSHOTS_PATH):
        if _text(row.get("snapshot_id")) == needle:
            return row
    return None


def _load_snapshot_rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not snapshot:
        return []
    try:
        path = Path(str(snapshot.get("storage_ref") or ""))
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def raw_snapshots_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["snapshot_id", "created_at", "source_id", "ingestion_job_id", "snapshot_type", "record_count", "content_hash", "schema_hash", "time_min", "time_max", "markets", "tokens", "storage_ref", "status", "warnings", "blockers", "notes"])


def _pick(row: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        if row.get(key) not in (None, ""):
            return str(row.get(key))
    return default


def _classify_record_type(row: dict[str, Any], snapshot_type: str) -> str:
    keys = {str(k).lower() for k in row.keys()}
    if "bid" in keys or "ask" in keys or "best_bid" in keys or "best_ask" in keys:
        return "price_record"
    if "price" in keys or "probability" in keys or "yes_price" in keys:
        return "price_record"
    if "outcome" in keys or "token_id" in keys or "asset_id" in keys:
        return "token_outcome_record"
    if "approval" in keys or "decision" in keys:
        return "approval_record"
    if "signal_id" in keys or "confidence" in keys:
        return "strategy_signal_record"
    if "spread_bps" in keys or "execution_quality" in keys:
        return "execution_quality_record"
    if "order_id" in keys or "lifecycle_status" in keys:
        return "order_lifecycle_record"
    if snapshot_type.startswith("gamma") or snapshot_type.startswith("clob_market"):
        return "market_metadata_record"
    return "normalized_generic_record"


def _normalize_rows_from_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _load_snapshot_rows(snapshot)
    normalized: list[dict[str, Any]] = []
    snapshot_type = _text(snapshot.get("snapshot_type"), "custom_snapshot")
    for row in rows:
        record_type = _classify_record_type(row, snapshot_type)
        normalized_row = {
            "record_id": f"rec_{uuid4().hex[:12]}",
            "created_at": _now(),
            "source_id": snapshot.get("source_id", ""),
            "snapshot_id": snapshot.get("snapshot_id", ""),
            "market_id": _pick(row, ["market_id", "condition_id", "market", "question_id"]),
            "condition_id": _pick(row, ["condition_id", "market_id"]),
            "token_id": _pick(row, ["token_id", "asset_id", "token", "outcome_token_id"]),
            "timestamp": _pick(row, ["timestamp", "created_at", "updated_at", "time"], snapshot.get("created_at", "")),
            "record_type": record_type,
            "schema_version": "normalized_market_data_v1",
            "content_hash": _stable_hash(row),
            "raw": row,
            "warnings": [],
            "blockers": [],
        }
        price = _safe_float(_pick(row, ["price", "probability", "yes_price", "limit_price"], ""), None)  # type: ignore[arg-type]
        if price is not None:
            normalized_row["price"] = price
            if price < 0 or price > 1:
                normalized_row["warnings"].append("price/probability outside 0..1")
        spread = _safe_float(_pick(row, ["spread", "spread_bps"], ""), None)  # type: ignore[arg-type]
        if spread is not None:
            normalized_row["spread"] = spread
        normalized.append(normalized_row)
    return normalized


def preview_normalization(snapshot_id: str = "", operator: str = "", note: str = "") -> dict[str, Any]:
    snapshot = get_raw_snapshot(snapshot_id) if snapshot_id else None
    warnings: list[str] = []
    blockers: list[str] = []
    if not snapshot:
        blockers.append("snapshot_id must reference a raw snapshot")
        normalized: list[dict[str, Any]] = []
    else:
        normalized = _normalize_rows_from_snapshot(snapshot)
        if not normalized:
            blockers.append("snapshot has no readable rows to normalize")
    record_types = Counter(row.get("record_type", "unknown") for row in normalized)
    payload = {
        "generated_at": _now(),
        "snapshot_id": snapshot_id,
        "record_count": len(normalized),
        "record_types": dict(record_types),
        "schema_version": "normalized_market_data_v1",
        "status": "normalization_blocked" if blockers else "normalization_ready",
        "warnings": warnings,
        "blockers": blockers,
        "network_attempted": False,
        "secret_values_returned": False,
    }
    _audit("data_normalization_previewed", snapshot_id, f"Normalization preview status: {payload['status']}", payload)
    return payload


def run_normalization(snapshot_id: str = "", operator: str = "", note: str = "") -> dict[str, Any]:
    preview = preview_normalization(snapshot_id, operator, note)
    snapshot = get_raw_snapshot(snapshot_id) if snapshot_id else None
    if preview.get("blockers"):
        return {"recorded": False, "preview": preview, "items": [], "secret_values_returned": False}
    normalized = _normalize_rows_from_snapshot(snapshot or {})
    rows = _load_list(NORMALIZED_PATH)
    rows.extend(normalized)
    _save_list(NORMALIZED_PATH, rows)
    result = {"recorded": True, "count": len(normalized), "items": normalized[:1000], "normalized_snapshot_hash": _stable_hash(normalized), "secret_values_returned": False}
    _audit("data_normalization_completed", snapshot_id, f"Normalized {len(normalized)} record(s).", result)
    return result


def list_normalized_records(limit: int = 1000, snapshot_id: str = "") -> list[dict[str, Any]]:
    rows = list(reversed(_load_list(NORMALIZED_PATH)))
    if snapshot_id:
        rows = [row for row in rows if _text(row.get("snapshot_id")) == _text(snapshot_id)]
    return rows[:limit]


def normalized_records_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["record_id", "created_at", "source_id", "snapshot_id", "market_id", "condition_id", "token_id", "timestamp", "record_type", "schema_version", "content_hash", "price", "spread", "warnings", "blockers"])


def _leakage_warnings(records: list[dict[str, Any]], labels: list[dict[str, Any]], split_method: str = "chronological") -> list[str]:
    warnings: list[str] = []
    if len(records) < 30 and records:
        warnings.append("insufficient sample size for reliable train/test evaluation")
    markets = [str(r.get("market_id") or r.get("condition_id") or "") for r in records if r.get("market_id") or r.get("condition_id")]
    if markets:
        counts = Counter(markets)
        dominant, dominant_count = counts.most_common(1)[0]
        if dominant_count / max(1, len(markets)) > 0.75:
            warnings.append(f"overconcentrated market/category: {dominant} represents more than 75% of records")
        if split_method in {"holdout_by_market", "market_grouped"} and len(counts) < 2:
            warnings.append("market holdout requested but fewer than two markets are present")
    label_values = [str(l.get("label_value")) for l in labels if l.get("label_value") not in (None, "")]
    if label_values:
        lc = Counter(label_values)
        if len(lc) < 2:
            warnings.append("label imbalance: only one label class detected")
    if not labels:
        warnings.append("no labels found; generated dataset will be analysis-only unless labels are added")
    now_ts = datetime.now(timezone.utc).timestamp()
    future = 0
    for row in records:
        value = row.get("timestamp")
        if value:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed.timestamp() > now_ts + 300:
                    future += 1
            except Exception:
                pass
    if future:
        warnings.append(f"future timestamps detected in normalized records: {future}")
    return warnings


def preview_labels(snapshot_id: str = "", label_type: str = "price_movement_over_horizon", horizon: str = "1h", operator: str = "", note: str = "") -> dict[str, Any]:
    records = list_normalized_records(limit=10000, snapshot_id=snapshot_id)
    warnings: list[str] = []
    blockers: list[str] = []
    if label_type not in LABEL_TYPES:
        warnings.append(f"unknown label_type preserved for manual extension: {label_type}")
    if not records:
        blockers.append("no normalized records available for label generation")
    if label_type in {"price_movement_over_horizon", "probability_movement_over_horizon"} and len(records) < 2:
        blockers.append("movement labels require at least two normalized records")
    preview_count = min(25, len(records)) if not blockers else 0
    payload = {
        "generated_at": _now(),
        "snapshot_id": snapshot_id,
        "label_type": label_type,
        "horizon": horizon,
        "preview_count": preview_count,
        "status": "label_blocked" if blockers else "label_ready",
        "warnings": warnings,
        "blockers": blockers,
        "secret_values_returned": False,
    }
    _audit("data_label_previewed", snapshot_id, f"Label preview status: {payload['status']}", payload)
    return payload


def generate_labels(snapshot_id: str = "", dataset_id: str = "", label_type: str = "price_movement_over_horizon", horizon: str = "1h", operator: str = "", note: str = "") -> dict[str, Any]:
    preview = preview_labels(snapshot_id=snapshot_id, label_type=label_type, horizon=horizon, operator=operator, note=note)
    if preview.get("blockers"):
        return {"recorded": False, "preview": preview, "items": [], "secret_values_returned": False}
    records = list_normalized_records(limit=10000, snapshot_id=snapshot_id)
    labels: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        next_record = records[index + 1] if index + 1 < len(records) else None
        price = _safe_float(record.get("price"), 0.0)
        next_price = _safe_float((next_record or {}).get("price"), price)
        if label_type in {"price_movement_over_horizon", "probability_movement_over_horizon"}:
            label_value = "up" if next_price > price else "down" if next_price < price else "flat"
            confidence = min(1.0, abs(next_price - price) + 0.5)
        elif label_type in {"spread_acceptable", "liquidity_acceptable", "execution_quality_acceptable"}:
            spread = _safe_float(record.get("spread"), 0.0)
            label_value = "yes" if spread <= 250 or spread == 0 else "no"
            confidence = 0.6
        else:
            label_value = "review_required"
            confidence = 0.25
        label = {
            "label_id": f"lbl_{uuid4().hex[:12]}",
            "created_at": _now(),
            "dataset_id": dataset_id,
            "snapshot_id": record.get("snapshot_id", snapshot_id),
            "record_id": record.get("record_id", ""),
            "market_id": record.get("market_id", ""),
            "condition_id": record.get("condition_id", ""),
            "token_id": record.get("token_id", ""),
            "label_type": label_type,
            "label_value": label_value,
            "label_window": horizon,
            "horizon": horizon,
            "method": "deterministic_local_labeler_v1",
            "confidence": round(confidence, 6),
            "source": "data_labeling_workbench",
            "status": "label_generated" if label_value != "review_required" else "label_review_required",
            "warnings": ["labels can be wrong and require review"],
            "blockers": [],
            "notes": note,
        }
        labels.append(label)
    rows = _load_list(LABELS_PATH)
    rows.extend(labels)
    _save_list(LABELS_PATH, rows)
    result = {"recorded": True, "count": len(labels), "items": labels[:1000], "secret_values_returned": False}
    _audit("data_label_generated", snapshot_id, f"Generated {len(labels)} label(s).", result)
    return result


def review_label(label_id: str = "", status: str = "label_approved", operator: str = "", note: str = "") -> dict[str, Any]:
    rows = _load_list(LABELS_PATH)
    found = None
    for row in rows:
        if row.get("label_id") == label_id:
            row["status"] = status if status in {"label_approved", "label_rejected", "label_review_required"} else "label_review_required"
            row["reviewed_at"] = _now()
            row["reviewed_by"] = operator
            row["review_note"] = note
            found = row
            break
    if found:
        _save_list(LABELS_PATH, rows)
        _audit("data_label_reviewed", label_id, f"Label reviewed as {found.get('status')}.", found)
        return {"ok": True, "item": found, "secret_values_returned": False}
    return {"ok": False, "error": "label not found", "secret_values_returned": False}


def list_labels(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(LABELS_PATH)))[:limit]


def labels_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["label_id", "created_at", "dataset_id", "snapshot_id", "record_id", "market_id", "condition_id", "token_id", "label_type", "label_value", "label_window", "horizon", "method", "confidence", "source", "status", "warnings", "blockers", "notes"])


def preview_dataset_build(name: str = "", source_ids: list[str] | None = None, snapshot_ids: list[str] | None = None, label_types: list[str] | None = None, feature_groups: list[str] | None = None, split_method: str = "chronological", filters: dict[str, Any] | None = None, operator: str = "", note: str = "") -> dict[str, Any]:
    source_ids = source_ids or []
    snapshot_ids = snapshot_ids or []
    label_types = label_types or []
    feature_groups = feature_groups or ["market_metadata", "price_movement", "spread_liquidity"]
    filters = filters or {}
    warnings: list[str] = []
    blockers: list[str] = []
    if split_method not in SPLIT_METHODS:
        warnings.append(f"unknown split_method preserved for extension: {split_method}")
    if not snapshot_ids:
        blockers.append("at least one snapshot_id is required to build a dataset")
    records: list[dict[str, Any]] = []
    for snapshot_id in snapshot_ids:
        records.extend(list_normalized_records(limit=100000, snapshot_id=snapshot_id))
    if not records:
        blockers.append("no normalized records were found for selected snapshots")
    labels = [row for row in _load_list(LABELS_PATH) if (not snapshot_ids or row.get("snapshot_id") in snapshot_ids) and (not label_types or row.get("label_type") in label_types)]
    warnings.extend(_leakage_warnings(records, labels, split_method))
    row_count = len(records)
    if split_method in {"chronological", "walk_forward"}:
        train_rows = int(row_count * 0.6)
        validation_rows = int(row_count * 0.2)
    else:
        train_rows = int(row_count * 0.7)
        validation_rows = int(row_count * 0.15)
    test_rows = max(0, row_count - train_rows - validation_rows)
    manifest = {
        "source_ids": source_ids,
        "snapshot_ids": snapshot_ids,
        "snapshot_hashes": [s.get("content_hash") for s in _load_list(SNAPSHOTS_PATH) if s.get("snapshot_id") in snapshot_ids],
        "normalization_schema_version": "normalized_market_data_v1",
        "label_configuration": {"label_types": label_types},
        "feature_configuration": {"feature_groups": feature_groups},
        "split_method": split_method,
        "filter_configuration": filters,
        "row_counts": {"total": row_count, "train": train_rows, "validation": validation_rows, "test": test_rows},
        "schema_hash": _stable_hash(sorted({str(key) for row in records for key in row.keys()})),
        "content_hash": _stable_hash(records),
        "build_timestamp": _now(),
        "software_version": APP_VERSION,
        "warnings": warnings,
        "blockers": blockers,
    }
    payload = {
        "generated_at": _now(),
        "name": _text(name, "dataset build preview"),
        "source_ids": source_ids,
        "snapshot_ids": snapshot_ids,
        "label_types": label_types,
        "feature_groups": feature_groups,
        "filters": filters,
        "split_method": split_method,
        "train_rows": train_rows,
        "validation_rows": validation_rows,
        "test_rows": test_rows,
        "manifest_hash": _stable_hash(manifest),
        "status": "dataset_build_blocked" if blockers else "dataset_build_ready_with_warnings" if warnings else "dataset_build_ready",
        "warnings": warnings,
        "blockers": blockers,
        "manifest": manifest,
        "secret_values_returned": False,
    }
    _audit("training_dataset_build_previewed", "", f"Dataset build preview status: {payload['status']}", payload)
    return payload


def build_training_dataset(name: str = "", source_ids: list[str] | None = None, snapshot_ids: list[str] | None = None, label_types: list[str] | None = None, feature_groups: list[str] | None = None, split_method: str = "chronological", filters: dict[str, Any] | None = None, operator: str = "", note: str = "") -> dict[str, Any]:
    preview = preview_dataset_build(name=name, source_ids=source_ids, snapshot_ids=snapshot_ids, label_types=label_types, feature_groups=feature_groups, split_method=split_method, filters=filters, operator=operator, note=note)
    build_id = f"db_{uuid4().hex[:12]}"
    if preview.get("blockers"):
        item = {"dataset_build_id": build_id, "created_at": _now(), **{k: preview.get(k) for k in ["name", "source_ids", "snapshot_ids", "label_types", "feature_groups", "filters", "split_method", "train_rows", "validation_rows", "test_rows", "manifest_hash", "status", "warnings", "blockers"]}, "dataset_id": "", "notes": note}
    else:
        records: list[dict[str, Any]] = []
        for snapshot_id in (snapshot_ids or []):
            records.extend(list_normalized_records(limit=100000, snapshot_id=snapshot_id))
        BUILT_DATASETS_DIR.mkdir(parents=True, exist_ok=True)
        dataset_csv = BUILT_DATASETS_DIR / f"{build_id}.csv"
        fields = sorted({str(key) for row in records for key in row.keys() if key != "raw"})
        dataset_csv.write_text(_rows_to_csv(records, fields), encoding="utf-8")
        dataset = register_dataset(name=_text(name, build_id), dataset_type="custom_csv", source_path=str(dataset_csv), source="dataset_builder", notes="Generated by local Dataset Builder. Outputs require Training Lab/manual review gates.")
        manifest = preview.get("manifest", {})
        manifest.update({"dataset_id": dataset.get("dataset_id"), "dataset_build_id": build_id})
        MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = MANIFESTS_DIR / f"{build_id}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
        item = {"dataset_build_id": build_id, "created_at": _now(), **{k: preview.get(k) for k in ["name", "source_ids", "snapshot_ids", "label_types", "feature_groups", "filters", "split_method", "train_rows", "validation_rows", "test_rows", "manifest_hash", "warnings", "blockers"]}, "status": "dataset_built", "dataset_id": dataset.get("dataset_id"), "manifest_path": str(manifest_path), "notes": note}
    builds = _load_list(DATASET_BUILDS_PATH)
    builds.append(item)
    _save_list(DATASET_BUILDS_PATH, builds)
    _audit("training_dataset_built", build_id, f"Dataset build recorded with status {item.get('status')}.", item)
    return {"item": item, "preview": preview, "secret_values_returned": False}


def list_dataset_builds(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(DATASET_BUILDS_PATH)))[:limit]


def get_dataset_build(dataset_build_id: str) -> dict[str, Any] | None:
    needle = _text(dataset_build_id)
    for row in _load_list(DATASET_BUILDS_PATH):
        if _text(row.get("dataset_build_id")) == needle:
            return row
    return None


def get_dataset_manifest(dataset_build_id: str) -> dict[str, Any]:
    build = get_dataset_build(dataset_build_id)
    if not build:
        return {"ok": False, "error": "dataset build not found", "secret_values_returned": False}
    path = Path(_text(build.get("manifest_path")))
    try:
        manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        manifest = {}
    _audit("training_dataset_manifest_viewed", dataset_build_id, "Dataset build manifest viewed.", {"dataset_build_id": dataset_build_id, "manifest_hash": build.get("manifest_hash")})
    return {"ok": bool(manifest), "dataset_build": build, "manifest": manifest, "manifest_hash": build.get("manifest_hash", ""), "secret_values_returned": False}


def dataset_builds_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["dataset_build_id", "created_at", "name", "source_ids", "snapshot_ids", "label_types", "feature_groups", "filters", "split_method", "train_rows", "validation_rows", "test_rows", "dataset_id", "manifest_hash", "status", "warnings", "blockers", "notes"])


def build_dataset_builder_status() -> dict[str, Any]:
    builds = list_dataset_builds(10000)
    latest = builds[0] if builds else {}
    warnings: list[str] = []
    blockers: list[str] = []
    if not list_raw_snapshots(1):
        warnings.append("No raw snapshots recorded yet. Register a source and run local ingestion first.")
    if not list_normalized_records(1):
        warnings.append("No normalized records available yet. Run normalization before dataset build.")
    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "status": "dataset_builder_ready" if not blockers else "dataset_builder_blocked",
        "dataset_build_count": len(builds),
        "latest_dataset_build": latest.get("dataset_build_id", ""),
        "latest_manifest_hash": latest.get("manifest_hash", ""),
        "recommended_split_method": "chronological",
        "leakage_warning_count": len([w for w in (latest.get("warnings", []) if isinstance(latest.get("warnings"), list) else []) if "leak" in str(w).lower() or "holdout" in str(w).lower()]),
        "warnings": warnings,
        "blockers": blockers,
        "guardrail": "Dataset Builder is local-first and produces Training Lab datasets only. It does not trade.",
        "secret_values_returned": False,
    }


def build_data_status() -> dict[str, Any]:
    sources = list_data_sources(10000)
    jobs = list_ingestion_jobs(10000)
    snapshots = list_raw_snapshots(10000)
    normalized = list_normalized_records(10000)
    labels = list_labels(10000)
    builds = list_dataset_builds(10000)
    warnings: list[str] = []
    blockers: list[str] = []
    if not sources:
        warnings.append("No data sources registered yet.")
    network_sources = [s for s in sources if s.get("network_required")]
    if network_sources:
        warnings.append("Network sources exist but remain disabled unless explicitly opted in.")
    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "status": "data_system_ready" if sources else "data_system_empty",
        "source_count": len(sources),
        "ingestion_job_count": len(jobs),
        "raw_snapshot_count": len(snapshots),
        "normalized_record_count": len(normalized),
        "label_count": len(labels),
        "dataset_build_count": len(builds),
        "network_enabled_by_default": False,
        "scheduler_enabled_by_default": False,
        "guardrail": "Data ingestion is local-first, network-disabled by default, and cannot place or cancel orders.",
        "warnings": warnings,
        "blockers": blockers,
        "secret_values_returned": False,
    }
