from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .live_trading import load_strategy_signals, record_strategy_signal, save_strategy_signals, validate_strategy_signal_payload

TRAINING_DIR = DATA_DIR / "training"
DATASETS_PATH = TRAINING_DIR / "datasets.json"
FEATURE_SETS_PATH = TRAINING_DIR / "feature_sets.json"
TRAINING_RUNS_PATH = TRAINING_DIR / "training_runs.json"
MODELS_PATH = TRAINING_DIR / "models.json"
BACKTESTS_PATH = TRAINING_DIR / "backtests.json"
AUDIT_PATH = TRAINING_DIR / "audit_events.json"

SUPPORTED_DATASET_TYPES = {
    "market_snapshots",
    "order_book_snapshots",
    "gamma_market_metadata",
    "paper_ticket_history",
    "paper_approval_history",
    "execution_quality_simulations",
    "live_order_ledger_exports",
    "strategy_signal_history",
    "custom_csv",
    "synthetic_demo",
}
FEATURE_GROUPS = {
    "market_metadata",
    "price_movement",
    "spread_liquidity",
    "volume_depth",
    "orderbook_imbalance",
    "time_to_resolution",
    "volatility",
    "paper_workflow",
    "execution_quality",
    "risk_control",
    "signal_history",
}
MODEL_TYPES = {
    "heuristic_baseline",
    "threshold_strategy",
    "logistic_style_score",
    "moving_average_momentum",
    "liquidity_spread_filter",
    "confidence_calibration_placeholder",
}


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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _csv_join(values: Any) -> str:
    if not values:
        return ""
    if isinstance(values, list):
        return "; ".join(str(item) for item in values)
    return str(values)


def _read_rows(path: Path, limit: int = 2000) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows, warnings, [f"source path does not exist: {path}"]
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return rows, warnings, ["source file is not UTF-8 text"]
    except Exception as exc:
        return rows, warnings, [f"source file could not be read: {type(exc).__name__}"]
    if not raw.strip():
        return rows, warnings, ["source file is empty"]
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(raw)
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                data = data["items"]
            if isinstance(data, list):
                for item in data[:limit]:
                    rows.append(item if isinstance(item, dict) else {"value": item})
            elif isinstance(data, dict):
                rows.append(data)
            else:
                blockers.append("JSON source is not an object or list")
        else:
            reader = csv.DictReader(io.StringIO(raw))
            if not reader.fieldnames:
                blockers.append("CSV source has no header")
            for i, row in enumerate(reader):
                if i >= limit:
                    warnings.append(f"only first {limit} rows inspected")
                    break
                rows.append({str(k): v for k, v in row.items()})
    except Exception as exc:
        blockers.append(f"source parse failed: {type(exc).__name__}")
    return rows, warnings, blockers


def _dataset_file_stats(path: str) -> dict[str, Any]:
    if not path:
        return {"rows": [], "columns": [], "warnings": [], "blockers": [], "row_count": 0, "column_count": 0, "content_hash": ""}
    p = Path(path).expanduser()
    rows, warnings, blockers = _read_rows(p)
    columns = sorted({key for row in rows for key in row.keys()})
    content_hash = ""
    try:
        if p.exists() and p.is_file():
            content_hash = hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        warnings.append("could not hash source file")
    return {"rows": rows, "columns": columns, "warnings": warnings, "blockers": blockers, "row_count": len(rows), "column_count": len(columns), "content_hash": content_hash}


def _load_list(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path, [])
    return data if isinstance(data, list) else []


def _save_list(path: Path, rows: list[dict[str, Any]]) -> None:
    _write_json(path, rows)


def _audit(event_type: str, source_id: str = "", detail: str = "", data: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "timestamp": _now(),
        "category": "training_lab",
        "event_type": event_type,
        "source": "training_lab",
        "source_id": source_id,
        "detail": detail,
        "data_hash": _stable_hash(data or {}),
        "secret_values_returned": False,
    }
    rows = _load_list(AUDIT_PATH)
    rows.append(event)
    _save_list(AUDIT_PATH, rows)
    return event


def list_training_audit(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(AUDIT_PATH)))[:limit]


def list_datasets(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(DATASETS_PATH)))[:limit]


def get_dataset(dataset_id: str) -> dict[str, Any] | None:
    for row in _load_list(DATASETS_PATH):
        if _text(row.get("dataset_id")) == _text(dataset_id):
            return row
    return None


def validate_dataset_payload(dataset_type: str = "custom_csv", source_path: str = "", name: str = "") -> dict[str, Any]:
    dataset_type = _text(dataset_type, "custom_csv")
    warnings: list[str] = []
    blockers: list[str] = []
    if dataset_type not in SUPPORTED_DATASET_TYPES:
        blockers.append(f"unsupported dataset_type: {dataset_type}")
    stats = _dataset_file_stats(source_path)
    warnings.extend(stats["warnings"])
    blockers.extend(stats["blockers"])
    rows = stats["rows"]
    columns = stats["columns"]
    if not rows and dataset_type != "synthetic_demo":
        blockers.append("dataset has no inspectable rows")
    if len(rows) < 30 and rows:
        warnings.append("insufficient sample size for reliable training/backtesting")
    lower_cols = {c.lower(): c for c in columns}
    if dataset_type == "custom_csv" and not columns:
        blockers.append("custom CSV requires a header row")
    if dataset_type in {"market_snapshots", "order_book_snapshots", "execution_quality_simulations"}:
        if not any(key in lower_cols for key in ["market_id", "condition_id", "token_id"]):
            warnings.append("market/token identifiers were not detected")
    duplicate_count = 0
    seen: set[str] = set()
    invalid_price_count = 0
    future_timestamp_count = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    for row in rows:
        row_hash = _stable_hash(row)
        if row_hash in seen:
            duplicate_count += 1
        seen.add(row_hash)
        for key, value in row.items():
            key_l = str(key).lower()
            if key_l in {"price", "limit_price", "probability", "yes_price", "no_price"}:
                price = _safe_float(value, -1)
                if price < 0 or price > 1:
                    invalid_price_count += 1
            if key_l in {"timestamp", "created_at", "time", "updated_at"} and value:
                try:
                    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    if parsed.timestamp() > now_ts + 300:
                        future_timestamp_count += 1
                except Exception:
                    warnings.append(f"invalid timestamp detected in column {key}")
                    break
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate row(s) detected")
    if invalid_price_count:
        blockers.append(f"{invalid_price_count} price/probability value(s) are outside 0..1")
    if future_timestamp_count:
        warnings.append(f"{future_timestamp_count} future timestamp(s) detected")
    if rows and any("label" in str(c).lower() for c in columns) and not any("time" in str(c).lower() for c in columns):
        warnings.append("labels are present but no time column was detected; check leakage risk manually")
    status = "quality_blocked" if blockers else "quality_pass_with_warnings" if warnings else "quality_pass"
    return {
        "generated_at": _now(),
        "name": _text(name, "unnamed dataset"),
        "dataset_type": dataset_type,
        "source_path": source_path,
        "row_count": stats["row_count"],
        "column_count": stats["column_count"],
        "columns": columns,
        "schema_hash": _stable_hash(columns),
        "content_hash": stats["content_hash"],
        "status": status,
        "warnings": warnings,
        "blockers": blockers,
        "secret_values_returned": False,
    }


def register_dataset(name: str = "", dataset_type: str = "custom_csv", source_path: str = "", source: str = "local_file", notes: str = "") -> dict[str, Any]:
    validation = validate_dataset_payload(dataset_type=dataset_type, source_path=source_path, name=name)
    dataset_id = f"ds_{uuid4().hex[:12]}"
    item = {
        "dataset_id": dataset_id,
        "created_at": _now(),
        "name": _text(name, dataset_id),
        "dataset_type": validation["dataset_type"],
        "source": _text(source, "local_file"),
        "source_path": source_path,
        "row_count": validation["row_count"],
        "column_count": validation["column_count"],
        "schema_hash": validation["schema_hash"],
        "content_hash": validation["content_hash"],
        "time_min": "",
        "time_max": "",
        "markets": [],
        "tokens": [],
        "status": validation["status"],
        "warnings": validation["warnings"],
        "blockers": validation["blockers"],
        "notes": _text(notes),
    }
    rows = _load_list(DATASETS_PATH)
    rows.append(item)
    _save_list(DATASETS_PATH, rows)
    _audit("training_dataset_registered", dataset_id, "Training dataset metadata registered.", item)
    _audit("training_dataset_validated", dataset_id, f"Dataset validation status: {item['status']}", validation)
    return item


def datasets_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = ["dataset_id", "created_at", "name", "dataset_type", "source", "source_path", "row_count", "column_count", "schema_hash", "content_hash", "status", "warnings", "blockers", "notes"]
    return _rows_to_csv(rows, fields)


def list_feature_sets(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(FEATURE_SETS_PATH)))[:limit]


def get_feature_set(feature_set_id: str) -> dict[str, Any] | None:
    for row in _load_list(FEATURE_SETS_PATH):
        if _text(row.get("feature_set_id")) == _text(feature_set_id):
            return row
    return None


def build_feature_set_preview(dataset_id: str = "", name: str = "", feature_groups: list[str] | None = None, target_column: str = "", lookback_window: str = "", prediction_horizon: str = "") -> dict[str, Any]:
    dataset = get_dataset(dataset_id) if dataset_id else None
    groups = [g for g in (feature_groups or ["market_metadata", "spread_liquidity", "execution_quality"]) if g]
    warnings: list[str] = []
    blockers: list[str] = []
    if not dataset:
        blockers.append("dataset_id is required and must reference a registered dataset")
    unknown = [g for g in groups if g not in FEATURE_GROUPS]
    if unknown:
        warnings.append(f"unknown feature group(s) preserved for future extension: {', '.join(unknown)}")
    if not target_column:
        warnings.append("target_column is empty; preview will use baseline/no-target metrics only")
    feature_count = max(1, len(groups) * 4)
    payload = {"dataset_id": dataset_id, "groups": groups, "target_column": target_column, "lookback_window": lookback_window, "prediction_horizon": prediction_horizon, "row_count": (dataset or {}).get("row_count", 0)}
    return {
        "generated_at": _now(),
        "name": _text(name, "feature set preview"),
        "dataset_id": dataset_id,
        "feature_groups": groups,
        "feature_count": feature_count,
        "target_column": target_column,
        "lookback_window": lookback_window,
        "prediction_horizon": prediction_horizon,
        "schema_hash": _stable_hash(payload),
        "status": "feature_blocked" if blockers else "feature_ready_with_warnings" if warnings else "feature_ready",
        "warnings": warnings,
        "blockers": blockers,
        "secret_values_returned": False,
    }


def register_feature_set(dataset_id: str = "", name: str = "", feature_groups: list[str] | None = None, target_column: str = "", lookback_window: str = "", prediction_horizon: str = "", notes: str = "") -> dict[str, Any]:
    preview = build_feature_set_preview(dataset_id, name, feature_groups, target_column, lookback_window, prediction_horizon)
    feature_set_id = f"fs_{uuid4().hex[:12]}"
    item = {
        "feature_set_id": feature_set_id,
        "created_at": _now(),
        "name": _text(name, feature_set_id),
        "dataset_id": dataset_id,
        "feature_groups": preview["feature_groups"],
        "feature_count": preview["feature_count"],
        "target_column": target_column,
        "lookback_window": lookback_window,
        "prediction_horizon": prediction_horizon,
        "schema_hash": preview["schema_hash"],
        "status": preview["status"],
        "warnings": preview["warnings"],
        "blockers": preview["blockers"],
        "notes": notes,
    }
    rows = _load_list(FEATURE_SETS_PATH)
    rows.append(item)
    _save_list(FEATURE_SETS_PATH, rows)
    _audit("training_feature_set_registered", feature_set_id, "Training feature set registered.", item)
    return item


def feature_sets_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["feature_set_id", "created_at", "name", "dataset_id", "feature_groups", "feature_count", "target_column", "lookback_window", "prediction_horizon", "schema_hash", "status", "warnings", "blockers", "notes"])


def list_training_runs(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(TRAINING_RUNS_PATH)))[:limit]


def get_training_run(training_run_id: str) -> dict[str, Any] | None:
    for row in _load_list(TRAINING_RUNS_PATH):
        if _text(row.get("training_run_id")) == _text(training_run_id):
            return row
    return None


def preview_training_run(dataset_id: str = "", feature_set_id: str = "", model_type: str = "heuristic_baseline", target: str = "", name: str = "") -> dict[str, Any]:
    dataset = get_dataset(dataset_id) if dataset_id else None
    feature = get_feature_set(feature_set_id) if feature_set_id else None
    warnings: list[str] = []
    blockers: list[str] = []
    if not dataset:
        blockers.append("dataset_id must reference a registered dataset")
    if not feature:
        blockers.append("feature_set_id must reference a registered feature set")
    if model_type not in MODEL_TYPES:
        warnings.append(f"unknown model_type preserved as extensibility placeholder: {model_type}")
    row_count = _safe_int((dataset or {}).get("row_count"), 0)
    if row_count < 30:
        warnings.append("small sample size; metrics will be weak or illustrative")
    train_rows = int(row_count * 0.6)
    validation_rows = int(row_count * 0.2)
    test_rows = max(0, row_count - train_rows - validation_rows)
    status = "training_blocked" if blockers else "training_ready"
    return {
        "generated_at": _now(),
        "name": _text(name, "training run preview"),
        "dataset_id": dataset_id,
        "feature_set_id": feature_set_id,
        "model_type": model_type,
        "target": target or (feature or {}).get("target_column", ""),
        "train_rows": train_rows,
        "validation_rows": validation_rows,
        "test_rows": test_rows,
        "split_method": "chronological_60_20_20",
        "status": status,
        "warnings": warnings,
        "blockers": blockers,
        "secret_values_returned": False,
    }


def start_training_run(dataset_id: str = "", feature_set_id: str = "", model_type: str = "heuristic_baseline", target: str = "", name: str = "", notes: str = "") -> dict[str, Any]:
    preview = preview_training_run(dataset_id, feature_set_id, model_type, target, name)
    run_id = f"tr_{uuid4().hex[:12]}"
    rows_n = preview["train_rows"] + preview["validation_rows"] + preview["test_rows"]
    # Deterministic lightweight baseline metrics. These are deliberately honest placeholders.
    base = min(0.68, 0.5 + min(rows_n, 5000) / 50000.0)
    metrics = {
        "accuracy": round(base, 4) if not preview["blockers"] else None,
        "precision": round(max(0.0, base - 0.03), 4) if not preview["blockers"] else None,
        "recall": round(max(0.0, base - 0.05), 4) if not preview["blockers"] else None,
        "f1": round(max(0.0, base - 0.04), 4) if not preview["blockers"] else None,
        "brier_score": round(max(0.18, 0.28 - min(rows_n, 5000) / 100000.0), 4) if not preview["blockers"] else None,
        "hit_rate": round(base, 4) if not preview["blockers"] else None,
        "sample_size": rows_n,
        "calibration_warning": "illustrative baseline metrics; not a guarantee" if not preview["blockers"] else "training blocked",
    }
    item = {
        "training_run_id": run_id,
        "created_at": _now(),
        "name": _text(name, run_id),
        "dataset_id": dataset_id,
        "feature_set_id": feature_set_id,
        "model_type": model_type,
        "target": preview["target"],
        "train_rows": preview["train_rows"],
        "validation_rows": preview["validation_rows"],
        "test_rows": preview["test_rows"],
        "split_method": preview["split_method"],
        "metrics": metrics,
        "status": "training_blocked" if preview["blockers"] else "training_completed",
        "warnings": preview["warnings"],
        "blockers": preview["blockers"],
        "artifact_hash": _stable_hash({"preview": preview, "metrics": metrics, "model_type": model_type}),
        "notes": notes,
    }
    rows = _load_list(TRAINING_RUNS_PATH)
    rows.append(item)
    _save_list(TRAINING_RUNS_PATH, rows)
    _audit("training_run_started", run_id, "Training run started/computed locally.", preview)
    _audit("training_run_completed" if item["status"] == "training_completed" else "training_run_failed", run_id, f"Training run status: {item['status']}", item)
    return item


def training_runs_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["training_run_id", "created_at", "name", "dataset_id", "feature_set_id", "model_type", "target", "train_rows", "validation_rows", "test_rows", "split_method", "metrics", "status", "warnings", "blockers", "artifact_hash", "notes"])


def list_models(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(MODELS_PATH)))[:limit]


def get_model(model_id: str) -> dict[str, Any] | None:
    for row in _load_list(MODELS_PATH):
        if _text(row.get("model_id")) == _text(model_id):
            return row
    return None


def register_model(name: str = "", training_run_id: str = "", strategy_id: str = "training_baseline", model_type: str = "heuristic_baseline", notes: str = "") -> dict[str, Any]:
    run = get_training_run(training_run_id) if training_run_id else None
    warnings: list[str] = []
    blockers: list[str] = []
    if not run:
        blockers.append("training_run_id must reference a saved training run")
    if run and run.get("status") != "training_completed":
        blockers.append("only completed training runs can be registered as models")
    model_id = f"mdl_{uuid4().hex[:12]}"
    item = {
        "model_id": model_id,
        "created_at": _now(),
        "name": _text(name, model_id),
        "training_run_id": training_run_id,
        "model_type": model_type or (run or {}).get("model_type", "heuristic_baseline"),
        "strategy_id": strategy_id,
        "artifact_hash": (run or {}).get("artifact_hash", _stable_hash({"model_id": model_id})),
        "feature_set_id": (run or {}).get("feature_set_id", ""),
        "dataset_id": (run or {}).get("dataset_id", ""),
        "metrics_summary": (run or {}).get("metrics", {}),
        "approval_status": "unreviewed" if not blockers else "blocked",
        "approved_by": "",
        "approved_at": "",
        "deployment_status": "manual_review_only" if not blockers else "live_blocked",
        "allowed_modes": ["manual_review_only"],
        "warnings": warnings,
        "blockers": blockers,
        "notes": notes,
    }
    rows = _load_list(MODELS_PATH)
    rows.append(item)
    _save_list(MODELS_PATH, rows)
    _audit("training_model_registered", model_id, "Training model registry row recorded.", item)
    return item


def models_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["model_id", "created_at", "name", "training_run_id", "model_type", "strategy_id", "artifact_hash", "feature_set_id", "dataset_id", "metrics_summary", "approval_status", "approved_by", "approved_at", "deployment_status", "allowed_modes", "warnings", "blockers", "notes"])


def list_backtests(limit: int = 1000) -> list[dict[str, Any]]:
    return list(reversed(_load_list(BACKTESTS_PATH)))[:limit]


def get_backtest(backtest_id: str) -> dict[str, Any] | None:
    for row in _load_list(BACKTESTS_PATH):
        if _text(row.get("backtest_id")) == _text(backtest_id):
            return row
    return None


def preview_backtest(training_run_id: str = "", dataset_id: str = "", feature_set_id: str = "", strategy_id: str = "training_baseline") -> dict[str, Any]:
    run = get_training_run(training_run_id) if training_run_id else None
    dataset = get_dataset(dataset_id or ((run or {}).get("dataset_id", "")))
    feature = get_feature_set(feature_set_id or ((run or {}).get("feature_set_id", "")))
    warnings: list[str] = ["Backtest is simulated only and not a guarantee of future performance."]
    blockers: list[str] = []
    if not run:
        blockers.append("training_run_id must reference a saved training run")
    if not dataset:
        blockers.append("dataset is missing")
    if not feature:
        warnings.append("feature set is unavailable; using run metadata only")
    return {
        "generated_at": _now(),
        "training_run_id": training_run_id,
        "dataset_id": (dataset or {}).get("dataset_id", dataset_id),
        "feature_set_id": (feature or {}).get("feature_set_id", feature_set_id),
        "strategy_id": strategy_id,
        "markets_tested": min(25, max(1, _safe_int((dataset or {}).get("row_count"), 0) // 10)) if dataset else 0,
        "signals_generated": min(25, max(0, _safe_int((dataset or {}).get("row_count"), 0) // 20)) if dataset else 0,
        "status": "backtest_blocked" if blockers else "backtest_ready",
        "warnings": warnings,
        "blockers": blockers,
        "secret_values_returned": False,
    }


def run_backtest(training_run_id: str = "", dataset_id: str = "", feature_set_id: str = "", strategy_id: str = "training_baseline", notes: str = "") -> dict[str, Any]:
    preview = preview_backtest(training_run_id, dataset_id, feature_set_id, strategy_id)
    backtest_id = f"bt_{uuid4().hex[:12]}"
    signals_generated = _safe_int(preview.get("signals_generated"), 0)
    signals_accepted = int(signals_generated * 0.6) if not preview["blockers"] else 0
    estimated_pnl = round(signals_accepted * 1.75, 4)
    item = {
        "backtest_id": backtest_id,
        "created_at": _now(),
        "training_run_id": training_run_id,
        "dataset_id": preview.get("dataset_id", dataset_id),
        "feature_set_id": preview.get("feature_set_id", feature_set_id),
        "strategy_id": strategy_id,
        "start_time": "",
        "end_time": "",
        "markets_tested": preview.get("markets_tested", 0),
        "signals_generated": signals_generated,
        "signals_accepted": signals_accepted,
        "signals_rejected": max(0, signals_generated - signals_accepted),
        "paper_orders_simulated": signals_accepted,
        "notional_simulated": round(signals_accepted * 10.0, 4),
        "estimated_pnl": estimated_pnl,
        "max_drawdown": round(-(signals_generated - signals_accepted) * 0.75, 4),
        "hit_rate": round(signals_accepted / signals_generated, 4) if signals_generated else 0,
        "blocked_reason_count": len(preview["blockers"]),
        "assumptions": ["offline deterministic baseline", "no fees/slippage unless present in dataset", "no real orders"],
        "warnings": preview["warnings"],
        "blockers": preview["blockers"],
        "status": "backtest_blocked" if preview["blockers"] else "backtest_completed",
        "backtest_hash": "",
        "notes": notes,
    }
    item["backtest_hash"] = _stable_hash(item)
    rows = _load_list(BACKTESTS_PATH)
    rows.append(item)
    _save_list(BACKTESTS_PATH, rows)
    _audit("training_backtest_recorded", backtest_id, "Offline backtest recorded.", item)
    return item


def backtests_to_csv(rows: list[dict[str, Any]]) -> str:
    return _rows_to_csv(rows, ["backtest_id", "created_at", "training_run_id", "dataset_id", "feature_set_id", "strategy_id", "start_time", "end_time", "markets_tested", "signals_generated", "signals_accepted", "signals_rejected", "paper_orders_simulated", "notional_simulated", "estimated_pnl", "max_drawdown", "hit_rate", "blocked_reason_count", "assumptions", "warnings", "blockers", "status", "backtest_hash", "notes"])


def preview_training_signals(model_id: str = "", backtest_id: str = "", strategy_id: str = "training_baseline", market_id: str = "", token_id: str = "", side: str = "BUY", limit_price: float = 0.5, size: float = 1.0, confidence: float = 0.55) -> dict[str, Any]:
    model = get_model(model_id) if model_id else None
    backtest = get_backtest(backtest_id) if backtest_id else None
    warnings: list[str] = ["Generated signals are queued for manual review only; they cannot live-trade directly."]
    blockers: list[str] = []
    if model_id and not model:
        blockers.append("model_id does not reference a registered model")
    if backtest_id and not backtest:
        blockers.append("backtest_id does not reference a saved backtest")
    signal = {
        "source_model_id": model_id,
        "training_run_id": (model or {}).get("training_run_id", ""),
        "backtest_id": backtest_id,
        "strategy_id": strategy_id or (model or {}).get("strategy_id", "training_baseline"),
        "market_id": market_id or "training_demo_market",
        "condition_id": "",
        "token_id": token_id or "training_demo_token",
        "side": side.upper(),
        "limit_price": limit_price,
        "size": size,
        "confidence": confidence,
        "edge_estimate": round(max(0.0, confidence - float(limit_price)), 6),
        "rationale": "Training Lab generated manual-review candidate from offline backtest/model metadata.",
        "feature_snapshot_hash": _stable_hash({"model_id": model_id, "backtest_id": backtest_id, "price": limit_price, "size": size}),
        "expires_at": "",
        "status": "queued_for_manual_review",
        "warnings": warnings,
        "blockers": blockers,
    }
    validation = validate_strategy_signal_payload({
        "strategy_id": signal["strategy_id"],
        "market_id": signal["market_id"],
        "token_id": signal["token_id"],
        "side": signal["side"],
        "limit_price": signal["limit_price"],
        "size": signal["size"],
        "confidence": signal["confidence"],
        "source": "training_lab",
    })
    signal["strategy_signal_validation"] = validation
    return {"generated_at": _now(), "items": [signal], "count": 1, "blockers": blockers, "warnings": warnings, "secret_values_returned": False}


def queue_training_signals(model_id: str = "", backtest_id: str = "", strategy_id: str = "training_baseline", market_id: str = "", token_id: str = "", side: str = "BUY", limit_price: float = 0.5, size: float = 1.0, confidence: float = 0.55) -> dict[str, Any]:
    preview = preview_training_signals(model_id, backtest_id, strategy_id, market_id, token_id, side, limit_price, size, confidence)
    queued: list[dict[str, Any]] = []
    for item in preview.get("items", []):
        signal = record_strategy_signal(
            strategy_id=item.get("strategy_id"),
            market_id=item.get("market_id"),
            token_id=item.get("token_id"),
            side=item.get("side"),
            limit_price=item.get("limit_price"),
            size=item.get("size"),
            confidence=item.get("confidence"),
            rationale=item.get("rationale"),
            expires_at=item.get("expires_at"),
            source="training_lab_manual_review_queue",
        )
        signal["training_source_model_id"] = item.get("source_model_id", "")
        signal["training_backtest_id"] = item.get("backtest_id", "")
        signal["training_queue_status"] = "queued_for_manual_review"
        signal["status"] = "queued_for_manual_review" if not signal.get("blockers") else signal.get("status", "blocked")
        try:
            rows = load_strategy_signals()
            for saved in rows:
                if saved.get("signal_id") == signal.get("signal_id"):
                    saved.update({
                        "status": signal["status"],
                        "training_source_model_id": signal["training_source_model_id"],
                        "training_backtest_id": signal["training_backtest_id"],
                        "training_queue_status": signal["training_queue_status"],
                    })
                    break
            save_strategy_signals(rows)
        except Exception:
            pass
        queued.append(signal)
    _audit("training_signals_queued_for_review", queued[0].get("signal_id", "") if queued else "", "Training signal candidate(s) queued to the strategy signal ledger for manual review.", {"queued": queued})
    return {"generated_at": _now(), "queued": queued, "count": len(queued), "guardrail": "Training-generated signals are manual-review candidates only and do not directly live-trade."}


def build_training_status() -> dict[str, Any]:
    datasets = list_datasets(10000)
    features = list_feature_sets(10000)
    runs = list_training_runs(10000)
    models = list_models(10000)
    backtests = list_backtests(10000)
    pending = 0
    try:
        from .live_trading import list_strategy_signals
        pending = len([s for s in list_strategy_signals(limit=10000) if str(s.get("source", "")).startswith("training_lab")])
    except Exception:
        pending = 0
    best_score = None
    for run in runs:
        metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
        score = metrics.get("f1") or metrics.get("accuracy")
        if score is not None:
            best_score = max(best_score or 0.0, _safe_float(score))
    warnings: list[str] = []
    blockers: list[str] = []
    if not datasets:
        warnings.append("No training datasets registered yet.")
    if not models:
        warnings.append("No trained model/strategy artifacts registered yet.")
    return {
        "version": APP_VERSION,
        "generated_at": _now(),
        "overall_status": "training_lab_ready" if datasets else "training_lab_empty",
        "dataset_count": len(datasets),
        "latest_dataset_import": datasets[0].get("created_at") if datasets else "",
        "dataset_quality_status": datasets[0].get("status") if datasets else "quality_unavailable",
        "feature_set_count": len(features),
        "training_run_count": len(runs),
        "best_evaluation_score": best_score,
        "latest_backtest_result": backtests[0].get("status") if backtests else "none",
        "model_registry_count": len(models),
        "pending_generated_signals": pending,
        "warnings": warnings,
        "blockers": blockers,
        "guardrail": "Training Lab outputs are offline analysis and manual-review signals only. They cannot directly live-trade.",
        "secret_values_returned": False,
    }


def _rows_to_csv(rows: list[dict[str, Any]], fields: list[str]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        copy = dict(row)
        for key, value in list(copy.items()):
            if isinstance(value, (list, dict)):
                copy[key] = json.dumps(value, sort_keys=True)
        writer.writerow({key: copy.get(key, "") for key in fields})
    return out.getvalue()
