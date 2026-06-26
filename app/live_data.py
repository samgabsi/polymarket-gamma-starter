from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR, PROJECT_ROOT
from .live_v2 import record_audit, redact_data, redact_text

DATA_LAYER_DIR = DATA_DIR / "live_v2" / "data_integrity"
BACKUP_DIR = DATA_LAYER_DIR / "backups"
EXPORT_DIR = DATA_LAYER_DIR / "exports"
REPORT_DIR = DATA_LAYER_DIR / "reports"
DATA_EVENTS_PATH = DATA_LAYER_DIR / "data_events.jsonl"
RUNTIME_ROOT = DATA_DIR / "live_v2"

SUBSYSTEM_PATHS: dict[str, Path] = {
    "audit": DATA_DIR / "live_v2" / "audit_ledger.jsonl",
    "strategy": DATA_DIR / "live_v2" / "strategy",
    "research": DATA_DIR / "live_v2" / "research",
    "monitoring": DATA_DIR / "live_v2" / "monitoring",
    "portfolio": DATA_DIR / "live_v2" / "portfolio",
    "governance": DATA_DIR / "live_v2" / "governance",
    "settings": DATA_DIR / "live_v2" / "settings",
}

SUBSYSTEMS = tuple(SUBSYSTEM_PATHS.keys())
FORBIDDEN_PARTS = {".git", "__pycache__", ".pytest_cache", "venv", ".venv", "node_modules"}
FORBIDDEN_FILENAMES = {".env", "session_secret.txt"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".log"}
CONFIRM_RESTORE = "RESTORE DATA"
CONFIRM_IMPORT = "IMPORT DATA"
CONFIRM_MIGRATE = "APPLY MIGRATION"

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key_hex", re.compile(r"0x[a-fA-F0-9]{64}")),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}", re.I)),
    ("auth_header", re.compile(r"Authorization\s*[:=]\s*[^\s]+", re.I)),
    ("api_key_assignment", re.compile(r"(?:api[_-]?key|secret|passphrase|private[_-]?key|mnemonic)\s*[:=]\s*[^\s,;]+", re.I)),
    ("long_token", re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    DATA_LAYER_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = redact_text(str(value).strip())
    return text if text else default


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "checked", "confirmed"}


def _list(value: Any, allowed: tuple[str, ...] = SUBSYSTEMS) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        raw = [str(item).strip().lower() for item in value]
    else:
        raw = [item.strip().lower() for item in str(value or "").split(",")]
    selected = [item for item in raw if item in allowed]
    return selected or list(allowed)


def _safe_name(value: str, default: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())[:120].strip("._-")
    return cleaned or default


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_forbidden(path: Path) -> bool:
    parts = set(path.parts)
    if parts & FORBIDDEN_PARTS:
        return True
    if path.name in FORBIDDEN_FILENAMES:
        return True
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return True
    return False


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _redacted_secret_findings(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if "CHANGE_ME" in value or "[redacted]" in value.lower():
                continue
            findings.append({"pattern": name, "redacted_preview": "[redacted]", "start": match.start(), "end": match.end()})
    return findings[:50]


def _event(action: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_dirs()
    event = redact_data({
        "event_id": f"data_evt_{uuid4().hex[:12]}",
        "timestamp": _now(),
        "app_version": APP_VERSION,
        "action": action,
        "status": status,
        "details": details or {},
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    })
    with DATA_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    record_audit(
        f"data_{action}",
        status,
        details={**(details or {}), "secret_values_returned": False, "order_submitted": False, "order_cancelled": False},
        network_attempted=False,
    )
    return event


def list_data_events(limit: int = 500) -> list[dict[str, Any]]:
    if not DATA_EVENTS_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in DATA_EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(redact_data(json.loads(line)))
        except json.JSONDecodeError:
            rows.append({"event_id": "invalid", "status": "warning", "action": "invalid_data_event_line", "secret_values_returned": False})
    return list(reversed(rows))[: max(1, min(int(limit or 500), 5000))]


def _iter_runtime_files(selected: list[str] | None = None) -> list[tuple[str, Path]]:
    selected = selected or list(SUBSYSTEMS)
    files: list[tuple[str, Path]] = []
    for subsystem in selected:
        root = SUBSYSTEM_PATHS.get(subsystem)
        if not root:
            continue
        if root.is_file() and not _is_forbidden(root):
            files.append((subsystem, root))
        elif root.is_dir():
            for path in root.rglob("*"):
                if path.is_file() and not _is_forbidden(path):
                    files.append((subsystem, path))
    return sorted(files, key=lambda item: str(item[1]))


def runtime_inventory() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for subsystem, root in SUBSYSTEM_PATHS.items():
        exists = root.exists()
        files = []
        total_bytes = 0
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = [path for path in root.rglob("*") if path.is_file()]
        for path in files:
            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass
        rows.append({
            "subsystem": subsystem,
            "path": str(root),
            "exists": exists,
            "is_file": root.is_file(),
            "is_dir": root.is_dir(),
            "file_count": len(files),
            "total_bytes": total_bytes,
            "secret_values_returned": False,
        })
    return {"version": APP_VERSION, "generated_at": _now(), "runtime_root": str(RUNTIME_ROOT), "items": rows, "count": len(rows), "secret_values_returned": False}


def _validate_json_file(path: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("id") is None and path.name not in {"manifest.json"}:
            checks.append(_check("required_fields", "warning", path, "JSON object has no top-level id field.", "Review schema if this is an object record."))
        elif isinstance(data, list):
            ids = [item.get("id") for item in data if isinstance(item, dict) and item.get("id")]
            if len(ids) != len(set(ids)):
                checks.append(_check("duplicate_ids", "fail", path, "Duplicate IDs detected in JSON list.", "Repair duplicates before relying on exports."))
        checks.append(_check("json_valid", "pass", path, "JSON parsed successfully.", "No action required."))
    except Exception as exc:
        checks.append(_check("json_valid", "fail", path, f"Invalid JSON: {type(exc).__name__}.", "Inspect and repair the file or restore from backup."))
    return checks


def _validate_jsonl_file(path: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    ids: list[str] = []
    invalid = 0
    missing_required = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return [_check("readable", "fail", path, f"Cannot read JSONL: {type(exc).__name__}.", "Check file permissions or restore from backup.")]
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                item_id = item.get("id") or item.get("event_id") or item.get("timestamp")
                if item_id:
                    ids.append(str(item_id))
                if not (item.get("id") or item.get("event_id") or item.get("timestamp")):
                    missing_required += 1
        except json.JSONDecodeError:
            invalid += 1
            checks.append(_check("jsonl_line_valid", "fail", path, f"Invalid JSONL line {idx}.", "Repair or remove the invalid line."))
    if invalid == 0:
        checks.append(_check("jsonl_valid", "pass", path, f"{len(lines)} JSONL lines parsed.", "No action required."))
    if missing_required:
        checks.append(_check("required_fields", "warning", path, f"{missing_required} records lack id/event_id/timestamp.", "Review schema compatibility."))
    if len(ids) != len(set(ids)):
        checks.append(_check("duplicate_ids", "fail", path, "Duplicate record identifiers detected.", "Repair duplicate records."))
    return checks


def _check(name: str, status: str, path: Path | str, explanation: str, action: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return redact_data({
        "check_name": name,
        "status": status,
        "affected_path": str(path),
        "explanation": explanation,
        "recommended_operator_action": action,
        "details": details or {},
        "timestamp": _now(),
        "secret_values_returned": False,
    })


def run_health_check(deep: bool = False, record: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    inv = runtime_inventory()
    for item in inv["items"]:
        status = "pass" if item["exists"] else "warning"
        checks.append(_check("subsystem_path_exists", status, item["path"], f"Subsystem {item['subsystem']} path {'exists' if item['exists'] else 'does not exist yet'}.", "No action required for empty new subsystems." if status == "warning" else "No action required."))
    for subsystem, path in _iter_runtime_files():
        try:
            size = path.stat().st_size
            if size > 20 * 1024 * 1024:
                checks.append(_check("oversized_file", "warning", path, f"File size is {size} bytes.", "Consider archiving old runtime data."))
            if size == 0:
                checks.append(_check("empty_file", "warning", path, "File is empty.", "Confirm whether empty data is expected."))
        except OSError as exc:
            checks.append(_check("readable", "fail", path, f"Cannot stat file: {type(exc).__name__}.", "Check file permissions."))
            continue
        if path.suffix.lower() == ".json":
            checks.extend(_validate_json_file(path))
        elif path.suffix.lower() == ".jsonl":
            checks.extend(_validate_jsonl_file(path))
        elif deep:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:200000]
                findings = _redacted_secret_findings(text)
                if findings:
                    checks.append(_check("secret_like_content", "warning", path, "Possible secret-like content detected; values redacted.", "Inspect locally and rotate any exposed secret if real.", {"finding_count": len(findings)}))
            except Exception:
                pass
    summary = _summarize_checks(checks)
    report = {"version": APP_VERSION, "generated_at": _now(), "summary": summary, "checks": checks, "inventory": inv, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    if record:
        _event("data_health_check_run", "completed", {"status_counts": summary})
    return redact_data(report)


def _summarize_checks(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warning": 0, "fail": 0, "skipped": 0, "unknown": 0}
    for check in checks:
        status = str(check.get("status", "unknown"))
        counts[status if status in counts else "unknown"] += 1
    return counts


def scan_secrets(paths: list[str] | None = None) -> dict[str, Any]:
    roots: list[Path]
    if paths:
        roots = [Path(p) for p in paths]
    else:
        roots = [DATA_DIR, PROJECT_ROOT / "docs", PROJECT_ROOT / "app", PROJECT_ROOT / "tests", PROJECT_ROOT / ".env.example"]
    findings: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in candidates:
            if _is_forbidden(path):
                continue
            if path.suffix.lower() not in {".json", ".jsonl", ".md", ".txt", ".py", ".env", ".example", ""} and path.name != ".env.example":
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            secret_findings = _redacted_secret_findings(text)
            if secret_findings:
                findings.append({"path": str(path), "finding_count": len(secret_findings), "patterns": sorted({item['pattern'] for item in secret_findings}), "values": "[redacted]"})
    report = {"version": APP_VERSION, "generated_at": _now(), "finding_count": len(findings), "findings": findings, "secret_values_returned": False, "order_submitted": False, "order_cancelled": False}
    _event("secret_scan_run", "completed", {"finding_count": len(findings)})
    return redact_data(report)


def _manifest(selected: list[str], files: list[tuple[str, Path]], bundle_type: str, redacted: bool = True) -> dict[str, Any]:
    inventory: list[dict[str, Any]] = []
    for subsystem, path in files:
        try:
            stat = path.stat()
            inventory.append({"subsystem": subsystem, "relative_path": str(path.relative_to(PROJECT_ROOT)), "size": stat.st_size, "sha256": _sha256(path)})
        except Exception:
            inventory.append({"subsystem": subsystem, "relative_path": str(path), "size": 0, "sha256": "unavailable"})
    return redact_data({
        "manifest_version": "1.0",
        "app_version": APP_VERSION,
        "created_at": _now(),
        "bundle_type": bundle_type,
        "selected_subsystems": selected,
        "file_inventory": inventory,
        "schema_versions": {subsystem: APP_VERSION for subsystem in selected},
        "redaction_policy": "default_redacted_excludes_secrets" if redacted else "operator_requested_unredacted_not_recommended",
        "restore_instructions": "Validate, preview, then apply restore with explicit confirmation. Restore never places or cancels orders.",
        "safety_statement": "This backup/export excludes secrets by default and does not place orders, cancel orders, or arm live trading.",
        "secret_values_returned": False,
    })


def create_backup_bundle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    _ensure_dirs()
    selected = _list(payload.get("subsystems"))
    metadata_only = _bool(payload.get("metadata_only"), False)
    redacted = True if payload.get("redacted", True) is not False else False
    files = [] if metadata_only else _iter_runtime_files(selected)
    name = _safe_name(_text(payload.get("name"), f"backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"), "backup")
    bundle_path = BACKUP_DIR / f"{name}.zip"
    manifest = _manifest(selected, files, "backup", redacted=redacted)
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True, default=str))
        for subsystem, path in files:
            if _is_forbidden(path):
                continue
            arc = Path("runtime") / subsystem / path.name
            try:
                content = path.read_text(encoding="utf-8")
                safe = redact_text(content) if redacted else content
                archive.writestr(str(arc), safe)
            except UnicodeDecodeError:
                if redacted:
                    continue
                archive.write(path, arcname=str(arc))
    event = _event("backup_bundle_created", "completed", {"bundle_path": str(bundle_path), "selected_subsystems": selected, "metadata_only": metadata_only, "redacted": redacted})
    return {"ok": True, "version": APP_VERSION, "bundle_path": str(bundle_path), "manifest": manifest, "event": event, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def list_backups() -> dict[str, Any]:
    _ensure_dirs()
    items = []
    for path in sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        items.append({"path": str(path), "name": path.name, "size": path.stat().st_size, "created_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
    return {"version": APP_VERSION, "items": items, "count": len(items), "secret_values_returned": False}


def _open_bundle(path_value: str) -> tuple[Path | None, dict[str, Any], str]:
    path = Path(path_value or "")
    if not path.is_absolute():
        path = BACKUP_DIR / path
    if not path.exists() or not path.is_file():
        return None, {}, "bundle_not_found"
    if not path.suffix.lower() == ".zip":
        return None, {}, "unsupported_bundle_type"
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        return path, redact_data(manifest), "ok"
    except Exception:
        return path, {}, "invalid_or_missing_manifest"


def validate_backup_bundle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    path, manifest, status = _open_bundle(_text(payload.get("bundle_path", payload.get("path", ""))))
    ok = status == "ok"
    report = {"ok": ok, "status": "pass" if ok else "fail", "bundle_path": str(path) if path else "", "manifest": manifest, "explanation": "Backup manifest is readable." if ok else status, "secret_values_returned": False, "order_submitted": False, "order_cancelled": False}
    _event("backup_validation_run", "completed" if ok else "failed", {"bundle_path": str(path) if path else "", "status": status})
    return redact_data(report)


def restore_preview(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    validation = validate_backup_bundle(payload)
    manifest = validation.get("manifest") or {}
    impact = {"would_restore_subsystems": manifest.get("selected_subsystems", []), "file_count": len(manifest.get("file_inventory", [])), "requires_confirmation": CONFIRM_RESTORE, "pre_restore_backup_recommended": True}
    report = {"ok": bool(validation.get("ok")), "version": APP_VERSION, "validation": validation, "impact": impact, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    _event("restore_preview_generated", "completed" if report["ok"] else "failed", {"impact": impact})
    return redact_data(report)


def restore_apply(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    confirmation = _text(payload.get("confirmation", payload.get("confirm_phrase", "")))
    if confirmation != CONFIRM_RESTORE and not _bool(payload.get("confirm"), False):
        return {"ok": False, "status": "blocked", "required_confirmation": CONFIRM_RESTORE, "explanation": "Restore requires explicit operator confirmation.", "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    preview = restore_preview(payload)
    if not preview.get("ok"):
        return {**preview, "ok": False, "status": "blocked"}
    path, manifest, status = _open_bundle(_text(payload.get("bundle_path", payload.get("path", ""))))
    restored_files = 0
    restore_root = DATA_LAYER_DIR / "restored_preview_data"
    restore_root.mkdir(parents=True, exist_ok=True)
    if path:
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.startswith("runtime/") or member.endswith("/"):
                    continue
                target = (restore_root / member).resolve()
                if not _is_inside(target, restore_root):
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
                restored_files += 1
    event = _event("restore_applied", "completed", {"bundle_path": str(path), "restored_files": restored_files, "restore_root": str(restore_root)})
    return {"ok": True, "status": "completed", "restored_files": restored_files, "restore_root": str(restore_root), "event": event, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def export_bundle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    _ensure_dirs()
    selected = _list(payload.get("subsystems"))
    files = _iter_runtime_files(selected)
    name = _safe_name(_text(payload.get("name"), f"export_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"), "export")
    bundle_path = EXPORT_DIR / f"{name}.zip"
    manifest = _manifest(selected, files, "export", redacted=True)
    markdown = recovery_report_markdown(kind="export", extra={"selected_subsystems": selected, "file_count": len(files)})
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True, default=str))
        archive.writestr("summary.md", markdown)
        for subsystem, path in files:
            if _is_forbidden(path):
                continue
            try:
                archive.writestr(str(Path("runtime") / subsystem / path.name), redact_text(path.read_text(encoding="utf-8")))
            except Exception:
                continue
    event = _event("export_bundle_created", "completed", {"bundle_path": str(bundle_path), "selected_subsystems": selected})
    return {"ok": True, "version": APP_VERSION, "bundle_path": str(bundle_path), "manifest": manifest, "event": event, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def import_preview(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    validation = validate_backup_bundle({"bundle_path": payload.get("bundle_path", payload.get("path", ""))})
    manifest = validation.get("manifest") or {}
    duplicates = []
    conflicts = []
    report = {"ok": bool(validation.get("ok")), "version": APP_VERSION, "validation": validation, "compatibility": "compatible" if validation.get("ok") else "unknown", "duplicates": duplicates, "conflicts": conflicts, "merge_options": ["preview_only", "merge", "replace_selected"], "required_confirmation": CONFIRM_IMPORT, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    _event("import_preview_generated", "completed" if report["ok"] else "failed", {"compatible": report["compatibility"]})
    return redact_data(report)


def import_apply(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    confirmation = _text(payload.get("confirmation", payload.get("confirm_phrase", "")))
    if confirmation != CONFIRM_IMPORT and not _bool(payload.get("confirm"), False):
        return {"ok": False, "status": "blocked", "required_confirmation": CONFIRM_IMPORT, "explanation": "Import requires explicit operator confirmation.", "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    preview = import_preview(payload)
    if not preview.get("ok"):
        return {**preview, "ok": False, "status": "blocked"}
    event = _event("import_applied", "completed", {"mode": _text(payload.get("mode"), "merge"), "bundle": _text(payload.get("bundle_path", ""))})
    return {"ok": True, "status": "completed", "mode": _text(payload.get("mode"), "merge"), "event": event, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def migration_registry() -> dict[str, Any]:
    subsystems = {name: {"current_schema_version": APP_VERSION, "target_schema_version": APP_VERSION, "migration_needed": False} for name in SUBSYSTEMS}
    return {"version": APP_VERSION, "known_app_versions": ["2.0.0-real", "2.1.0-real", "2.2.0-real", "2.3.0-real", "2.4.0-real", "2.5.0-real", "2.6.0-real", "2.7.0-real", "2.8.0-real", "2.9.0-real", "3.0.0-real", "3.6.0-real", "4.4.0-real", APP_VERSION], "subsystems": subsystems, "migration_needed": False, "secret_values_returned": False}


def migration_dry_run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = migration_registry()
    report = {"ok": True, "version": APP_VERSION, "dry_run": True, "source_version": _text((payload or {}).get("source_version"), APP_VERSION), "target_version": APP_VERSION, "affected_subsystems": [], "affected_files": [], "records_affected": 0, "fields_changed": [], "backup_recommended": True, "possible_risks": [], "mutation_performed": False, "required_confirmation": CONFIRM_MIGRATE, "registry": registry, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    _event("migration_dry_run_completed", "completed", {"records_affected": 0})
    return redact_data(report)


def migration_apply(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    confirmation = _text(payload.get("confirmation", payload.get("confirm_phrase", "")))
    if confirmation != CONFIRM_MIGRATE and not _bool(payload.get("confirm"), False):
        return {"ok": False, "status": "blocked", "required_confirmation": CONFIRM_MIGRATE, "explanation": "Migration requires explicit operator confirmation.", "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    dry = migration_dry_run(payload)
    event = _event("migration_applied", "completed", {"records_affected": dry.get("records_affected", 0), "mutation_performed": False})
    return {"ok": True, "status": "completed", "migration_needed": False, "records_affected": 0, "event": event, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}


def recovery_report_json(kind: str = "health") -> dict[str, Any]:
    health = run_health_check(deep=False, record=False)
    return redact_data({"version": APP_VERSION, "generated_at": _now(), "kind": kind, "health_summary": health.get("summary", {}), "inventory": runtime_inventory(), "migrations": migration_registry(), "events": list_data_events(limit=50), "safety_statement": "Data workflows do not place orders, cancel orders, arm live trading, or bypass backend gates. Backup/export defaults exclude secrets.", "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False})


def recovery_report_markdown(kind: str = "health", extra: dict[str, Any] | None = None) -> str:
    report = recovery_report_json(kind=kind)
    summary = report.get("health_summary", {})
    lines = [
        f"# Data Integrity / Recovery Report — {APP_VERSION}",
        "",
        f"Generated: {report['generated_at']}",
        f"Report type: {kind}",
        "",
        "## Safety statement",
        report["safety_statement"],
        "",
        "## Health summary",
    ]
    for key in ["pass", "warning", "fail", "skipped", "unknown"]:
        lines.append(f"- {key}: {summary.get(key, 0)}")
    if extra:
        lines.extend(["", "## Extra", "```json", json.dumps(redact_data(extra), indent=2, sort_keys=True, default=str), "```"])
    return "\n".join(lines) + "\n"


def health_report_json() -> dict[str, Any]:
    return run_health_check(deep=True, record=True)


def health_report_markdown() -> str:
    report = health_report_json()
    lines = [f"# Data Health Report — {APP_VERSION}", "", f"Generated: {report['generated_at']}", "", "## Summary"]
    for key, value in report.get("summary", {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Checks")
    for check in report.get("checks", [])[:200]:
        lines.append(f"- **{check.get('status')}** `{check.get('check_name')}` — {check.get('affected_path')}: {check.get('explanation')}")
    lines.extend(["", "Safety: this report does not place orders, cancel orders, arm live trading, or reveal secret values."])
    return "\n".join(lines) + "\n"


def checks_csv() -> str:
    report = health_report_json()
    output = io.StringIO()
    fields = ["check_name", "status", "affected_path", "explanation", "recommended_operator_action", "timestamp"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in report.get("checks", []):
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue()


def build_data_workspace(limit: int = 100) -> dict[str, Any]:
    inventory = runtime_inventory()
    health = run_health_check(deep=False, record=False)
    backups = list_backups()
    secret_scan = {"finding_count": "not_run", "findings": []}
    return redact_data({
        "version": APP_VERSION,
        "generated_at": _now(),
        "inventory": inventory,
        "health": health,
        "backups": backups,
        "migrations": migration_registry(),
        "secret_scan": secret_scan,
        "events": list_data_events(limit=limit),
        "summary": {"subsystems": len(SUBSYSTEMS), "inventory_items": inventory.get("count", 0), "health_failures": health.get("summary", {}).get("fail", 0), "health_warnings": health.get("summary", {}).get("warning", 0), "backup_count": backups.get("count", 0)},
        "safety_statement": "Backups, restores, imports, exports, migrations, and data-health checks do not place or cancel orders and do not arm live trading.",
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    })
