from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_VERSION, DATA_DIR, PROJECT_ROOT

BACKUP_DIR = DATA_DIR / "backups"
MANIFEST_NAME = "backup_manifest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _iter_data_files() -> list[Path]:
    files: list[Path] = []
    if not DATA_DIR.exists():
        return files
    for path in DATA_DIR.rglob("*"):
        if not path.is_file():
            continue
        if BACKUP_DIR in path.parents:
            continue
        if path.name.startswith("."):
            continue
        files.append(path)
    return sorted(files)


def data_inventory() -> dict[str, Any]:
    files = _iter_data_files()
    total_bytes = sum(p.stat().st_size for p in files if p.exists())
    by_type: dict[str, int] = {}
    for path in files:
        suffix = path.suffix.lower() or "[no extension]"
        by_type[suffix] = by_type.get(suffix, 0) + 1
    return {
        "data_dir": str(DATA_DIR),
        "backup_dir": str(BACKUP_DIR),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1024 / 1024, 3),
        "by_type": by_type,
        "files": [{"path": _safe_rel(p), "size_bytes": p.stat().st_size} for p in files[:250]],
    }


def create_backup(label: str = "manual") -> dict[str, Any]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(ch for ch in label.strip().lower().replace(" ", "-") if ch.isalnum() or ch in {"-", "_"}) or "manual"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"polymarket-gamma-data-{stamp}-{safe_label}.zip"
    backup_path = BACKUP_DIR / filename
    files = _iter_data_files()
    manifest = {
        "created_at": utc_now(),
        "label": safe_label,
        "version": APP_VERSION,
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(DATA_DIR),
        "file_count": len(files),
        "files": [_safe_rel(p) for p in files],
        "note": "Local data backup only. Does not include virtualenvs, source caches, or external API secrets outside the project data directory.",
    }
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True))
        for path in files:
            zf.write(path, arcname=_safe_rel(path))
    return backup_info(backup_path)


def backup_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "filename": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / 1024 / 1024, 3),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat(),
        "download_url": f"/api/maintenance/backups/{path.name}/download",
    }


def list_backups(limit: int = 50) -> list[dict[str, Any]]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [backup_info(p) for p in backups[:limit]]


def get_backup_path(filename: str) -> Path:
    if "/" in filename or "\\" in filename or filename.startswith(".") or not filename.endswith(".zip"):
        raise ValueError("Invalid backup filename.")
    path = BACKUP_DIR / filename
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(filename)
    return path


def delete_backup(filename: str) -> bool:
    path = get_backup_path(filename)
    path.unlink()
    return True


def maintenance_status() -> dict[str, Any]:
    return {
        "version": APP_VERSION,
        "inventory": data_inventory(),
        "backups": list_backups(),
        "restore_supported": False,
        "restore_note": "Restore is intentionally not enabled in the web UI yet. For now backups are export/download only to avoid accidental overwrite of user accounts or paper-trading data.",
    }
