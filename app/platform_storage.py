from __future__ import annotations

from typing import Any
from .config import APP_VERSION, DATA_DIR
from .platform_safety import safety_flags

KNOWN_STORAGE_NAMESPACES = [
    {"namespace": "live_v2_audit", "path": "data/live_v2/audit_ledger.jsonl", "expected_format": "jsonl", "introduced_in": "v2.0.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": True, "backup_recommended": True, "compatibility_note": "Audit ledgers are runtime-only and may contain operator/account-adjacent context."},
    {"namespace": "live_v2_strategy", "path": "data/live_v2/strategy", "expected_format": "directory", "introduced_in": "v2.4.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Strategy records are local operator data and not release assets."},
    {"namespace": "live_v2_research", "path": "data/live_v2/research", "expected_format": "directory", "introduced_in": "v2.5.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Research notes may contain private operator notes and must be excluded from packages."},
    {"namespace": "live_v2_monitoring", "path": "data/live_v2/monitoring", "expected_format": "directory", "introduced_in": "v2.6.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Monitoring rules and alerts are local runtime records."},
    {"namespace": "live_v2_portfolio", "path": "data/live_v2/portfolio", "expected_format": "directory", "introduced_in": "v2.7.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": True, "backup_recommended": True, "compatibility_note": "Portfolio records can be sensitive and require manual review before migration."},
    {"namespace": "live_v2_governance", "path": "data/live_v2/governance", "expected_format": "directory", "introduced_in": "v2.8.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Governance journals are local review records."},
    {"namespace": "v3_workflows", "path": "data/live_v3/workflow_runs.jsonl", "expected_format": "jsonl", "introduced_in": "v3.0.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Workflow runs are generated local outputs."},
    {"namespace": "v3_analytics", "path": "data/live_v3/analytics", "expected_format": "directory", "introduced_in": "v3.2.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Analytics snapshots are descriptive local outputs and not package assets."},
    {"namespace": "v3_simulation", "path": "data/live_v3/simulation", "expected_format": "directory", "introduced_in": "v3.4.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Simulation sessions and reports are local runtime records."},
    {"namespace": "v3_datasets", "path": "data/live_v3/datasets", "expected_format": "directory", "introduced_in": "v3.5.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Dataset manifests, replay records, and snapshot payloads are runtime-only."},
    {"namespace": "v3_freshness", "path": "data/live_v3/freshness", "expected_format": "directory", "introduced_in": "v3.6.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Freshness policies, jobs, readiness reports, and notifications are runtime-only."},
    {"namespace": "v3_tasks", "path": "data/live_v3/tasks", "expected_format": "directory", "introduced_in": "v3.7.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Task records and daily/weekly packets are workflow data, not trade approval."},
    {"namespace": "v3_workspace", "path": "data/live_v3/workspace", "expected_format": "directory", "introduced_in": "v3.8.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Guided review sessions, dependencies, saved views, and packets are local runtime data."},
    {"namespace": "v3_cockpit", "path": "data/live_v3/cockpit", "expected_format": "directory", "introduced_in": "v3.9.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "compatibility_note": "Cockpit layouts, command logs, and exports are local workflow artifacts."},
    {"namespace": "v4_platform", "path": "data/live_v3/platform", "expected_format": "directory", "introduced_in": "v4.0.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": False, "backup_recommended": True, "docs_link": "/docs/V4_PLATFORM_ARCHITECTURE_GUIDE_v4.7.0-real.md", "compatibility_note": "Platform diagnostics, plugin manifests, schema inventories, generated-manual status, and migration exports are runtime-only."},
    {"namespace": "v4_ai", "path": "data/ai", "expected_format": "directory", "introduced_in": "v4.7.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": True, "backup_recommended": True, "docs_link": "/docs/V4_AI_SAFETY_AND_PRIVACY_GUIDE_v4.7.0-real.md", "compatibility_note": "AI suggestions, review packets, and hash-only audit records are runtime-only, redacted, and excluded from release ZIPs."},
    {"namespace": "v4_ai_edge", "path": "data/ai/edge", "expected_format": "directory", "introduced_in": "v4.7.0-real", "created_lazily": True, "package_excluded": True, "may_contain_sensitive_data": True, "backup_recommended": True, "docs_link": "/docs/V4_AI_EDGE_RESEARCH_GUIDE_v4.7.0-real.md", "compatibility_note": "AI Edge evidence sources, research packets, and calibration records are runtime-only, redacted, and excluded from release ZIPs."},
]
PACKAGE_EXCLUDED_RUNTIME_DIRS = [
    "data", "runtime_screenshots", ".pytest_cache", "__pycache__", "venv", ".venv", "node_modules", "logs", "backups",
]
COMPATIBILITY_NOTES = [
    "v3.5 dataset manifests, v3.6 freshness records, v3.7 task records, v3.8 workspace records, v4.0 cockpit records, v4.0 platform diagnostics, and v4.3 AI records are local JSON/JSONL runtime stores.",
    "Stores are created lazily by operator-triggered actions and are excluded from clean release packages.",
    "v4.7.0-real adds the AI Edge runtime namespace for evidence-backed research packets and calibration records while keeping package exclusion and backup guidance explicit.",
    "Live trading state is not migrated, deleted, approved, submitted, cancelled, or armed by storage helpers.",
]


def storage_summary() -> dict[str, Any]:
    rows = []
    for item in KNOWN_STORAGE_NAMESPACES:
        path = DATA_DIR.parent / item["path"]
        rows.append({
            **item,
            "exists_now": path.exists(),
            "manual_migration_guidance": "Back up this namespace before future schema changes; v4.3 reports only and does not mutate data.",
            "docs_link": item.get("docs_link", "/docs/V4_RUNTIME_MIGRATION_PLANNER_GUIDE_v4.7.0-real.md"),
            "safety_note": "Runtime only; exclude from release ZIP.",
        })
    return safety_flags({
        "version": APP_VERSION,
        "count": len(rows),
        "items": rows,
        "package_excluded_runtime_dirs": PACKAGE_EXCLUDED_RUNTIME_DIRS,
        "compatibility_notes": COMPATIBILITY_NOTES,
        "migration_policy": "non-destructive planning only, no automatic delete/move/rewrite/migration",
        "known_compatibility_range": "v3.5.0-real through v4.7.0-real",
    })
