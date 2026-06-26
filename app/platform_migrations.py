from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_VERSION, DATA_DIR
from .platform_exports import export_manifest, to_markdown
from .platform_safety import NO_LIVE_MUTATION_STATEMENT, STANDARD_SAFETY_STATEMENT, redact_data, safety_flags
from .platform_storage import KNOWN_STORAGE_NAMESPACES, storage_summary

SOURCE_VERSION = "4.2.0-real"
TARGET_VERSION = "4.17.0-real"
KNOWN_COMPATIBILITY_RANGE = "v3.5.0-real through v4.17.0-real"
PLAN_ID = "runtime_migration_plan_v4_3_0"
CLASSIFICATIONS = {
    "no-op",
    "backup recommended",
    "manual review required",
    "safe copy suggested",
    "schema unknown",
    "destructive action prohibited",
}
DESTRUCTIVE_TOKENS = {"delete", "remove", "rewrite", "truncate", "move", "overwrite", "drop", "cancel_order", "place_order", "arm_live_trading"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RuntimeNamespaceStatus:
    namespace: str
    path: str
    exists_now: bool
    expected_format: str
    introduced_in: str
    package_excluded: bool
    created_lazily: bool
    may_contain_sensitive_data: bool
    backup_recommended: bool
    detected_kind: str
    detected_file_count: int | None
    compatibility_note: str
    docs_link: str


@dataclass(frozen=True)
class MigrationStep:
    step_id: str
    namespace: str
    classification: str
    action: str
    rationale: str
    operator_instruction: str
    automatic_mutation_allowed: bool


def classify_migration_action(action: str) -> str:
    text = str(action or "").lower()
    if any(token in text for token in DESTRUCTIVE_TOKENS):
        return "destructive action prohibited"
    if "manual" in text or "review" in text:
        return "manual review required"
    if "backup" in text:
        return "backup recommended"
    if "copy" in text:
        return "safe copy suggested"
    if "unknown" in text:
        return "schema unknown"
    return "no-op"


def _inspect_path(path: Path) -> tuple[str, int | None]:
    if not path.exists():
        return "not-created-yet", None
    if path.is_dir():
        try:
            return "directory", min(sum(1 for _ in path.iterdir()), 1000)
        except OSError:
            return "directory-unreadable", None
    if path.is_file():
        suffix = path.suffix.lower().lstrip(".") or "file"
        return suffix, 1
    return "unknown", None


def runtime_namespace_inventory() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    root = DATA_DIR.parent
    for item in KNOWN_STORAGE_NAMESPACES:
        path = root / item["path"]
        detected_kind, detected_file_count = _inspect_path(path)
        may_contain_sensitive = bool(item.get("may_contain_sensitive_data", False))
        backup_recommended = bool(item.get("backup_recommended", True) or may_contain_sensitive)
        row = RuntimeNamespaceStatus(
            namespace=str(item["namespace"]),
            path=str(item["path"]),
            exists_now=path.exists(),
            expected_format=str(item.get("expected_format", "json/jsonl/directory")),
            introduced_in=str(item.get("introduced_in", "unknown")),
            package_excluded=bool(item.get("package_excluded", True)),
            created_lazily=bool(item.get("created_lazily", True)),
            may_contain_sensitive_data=may_contain_sensitive,
            backup_recommended=backup_recommended,
            detected_kind=detected_kind,
            detected_file_count=detected_file_count,
            compatibility_note=str(item.get("compatibility_note", "Runtime namespace is local and package-excluded.")),
            docs_link=str(item.get("docs_link", "/docs/V4_RUNTIME_MIGRATION_PLANNER_GUIDE_v4.7.0-real.md")),
        )
        rows.append(asdict(row))
    return safety_flags({
        "version": APP_VERSION,
        "generated_at": _now(),
        "source_version": SOURCE_VERSION,
        "target_version": TARGET_VERSION,
        "known_compatibility_range": KNOWN_COMPATIBILITY_RANGE,
        "count": len(rows),
        "items": redact_data(rows),
        "missing_namespaces": [row["namespace"] for row in rows if not row["exists_now"]],
        "detected_namespaces": [row["namespace"] for row in rows if row["exists_now"]],
        "unknown_unavailable_data": ["Missing namespaces may simply be clean-package lazy stores that have not been created yet."],
        "dry_run_only_guarantee": "Inventory reads path existence and lightweight directory counts only; it does not create, delete, move, rewrite, copy, migrate, or export runtime data.",
        "migration_planner_does_not_mutate_runtime_data": True,
    })


def build_migration_steps() -> list[dict[str, Any]]:
    inventory = runtime_namespace_inventory()
    steps: list[dict[str, Any]] = []
    for index, row in enumerate(inventory["items"], start=1):
        namespace = row["namespace"]
        if not row["exists_now"]:
            step = MigrationStep(
                step_id=f"mig_{index:02d}_{namespace}",
                namespace=namespace,
                classification="no-op",
                action="no-op; namespace not created yet",
                rationale="Clean packages often do not include lazily-created runtime namespaces.",
                operator_instruction="No action is required unless you expected local runtime data in this namespace.",
                automatic_mutation_allowed=False,
            )
        elif row["may_contain_sensitive_data"]:
            step = MigrationStep(
                step_id=f"mig_{index:02d}_{namespace}",
                namespace=namespace,
                classification="manual review required",
                action="manual review and backup recommended before any future copy",
                rationale="Namespace may contain sensitive or account-adjacent local data.",
                operator_instruction="Review locally, create an operator-controlled backup, and do not include it in release ZIPs.",
                automatic_mutation_allowed=False,
            )
        elif row["detected_kind"] not in {row["expected_format"], "directory", "json", "jsonl", "not-created-yet"}:
            step = MigrationStep(
                step_id=f"mig_{index:02d}_{namespace}",
                namespace=namespace,
                classification="schema unknown",
                action="schema unknown; manual review required",
                rationale="Detected storage kind does not match the documented expectation.",
                operator_instruction="Inspect the namespace manually before planning any v4.x schema migration.",
                automatic_mutation_allowed=False,
            )
        else:
            step = MigrationStep(
                step_id=f"mig_{index:02d}_{namespace}",
                namespace=namespace,
                classification="backup recommended",
                action="backup recommended; safe copy may be planned manually",
                rationale="Namespace exists and is package-excluded runtime data.",
                operator_instruction="Back up before future v4.x migrations; v4.3 does not copy, delete, rewrite, or move this data automatically.",
                automatic_mutation_allowed=False,
            )
        steps.append(asdict(step))
    steps.append(asdict(MigrationStep(
        step_id="mig_destructive_actions",
        namespace="all_runtime_namespaces",
        classification="destructive action prohibited",
        action="automatic delete, rewrite, move, order placement, order cancellation, or live arming",
        rationale="The v4.3 migration planner is advisory and fail-closed.",
        operator_instruction="Reject any workflow that attempts destructive migration or live trading mutation from diagnostics or planning.",
        automatic_mutation_allowed=False,
    )))
    return steps


def migration_summary() -> dict[str, Any]:
    plan = migration_plan()
    classifications: dict[str, int] = {}
    for step in plan["steps"]:
        classifications[step["classification"]] = classifications.get(step["classification"], 0) + 1
    return safety_flags({
        "version": APP_VERSION,
        "generated_at": _now(),
        "plan_id": PLAN_ID,
        "source_version": SOURCE_VERSION,
        "target_version": TARGET_VERSION,
        "known_compatibility_range": KNOWN_COMPATIBILITY_RANGE,
        "runtime_namespace_count": plan["runtime_namespace_count"],
        "step_count": len(plan["steps"]),
        "classifications": classifications,
        "destructive_actions_prohibited": True,
        "manual_review_required": any(step["classification"] in {"manual review required", "backup recommended", "schema unknown"} for step in plan["steps"]),
        "dry_run_only": True,
        "automatic_runtime_migration": False,
        "migration_planner_does_not_mutate_runtime_data": True,
        "storage_summary": storage_summary(),
        "unknown_unavailable_data": plan["unknown_unavailable_data"],
    })


def migration_plan() -> dict[str, Any]:
    inventory = runtime_namespace_inventory()
    steps = build_migration_steps()
    blockers = [step["action"] for step in steps if step["classification"] == "destructive action prohibited"]
    warnings = [step["operator_instruction"] for step in steps if step["classification"] in {"backup recommended", "manual review required", "schema unknown"}][:20]
    return safety_flags({
        "version": APP_VERSION,
        "generated_at": _now(),
        "plan_id": PLAN_ID,
        "plan_timestamp": _now(),
        "source_version": SOURCE_VERSION,
        "target_version": TARGET_VERSION,
        "current_app_version": APP_VERSION,
        "known_compatibility_range": KNOWN_COMPATIBILITY_RANGE,
        "runtime_namespace_count": inventory["count"],
        "runtime_namespaces": inventory["items"],
        "steps": steps,
        "warnings": warnings,
        "blockers": blockers,
        "backup_recommendation": "Before any future v4.x data migration, stop the app and make an operator-controlled backup of package-excluded runtime data. v4.3 only reports recommendations.",
        "manual_review_required": any(step["classification"] in {"manual review required", "backup recommended", "schema unknown"} for step in steps),
        "dry_run_only": True,
        "dry_run_only_guarantee": "This plan is advisory. It does not delete, move, rewrite, copy, migrate, export, or inspect full runtime records.",
        "destructive_action_prohibited_status": "enforced",
        "export_safety_validation": validate_migration_export_safety(steps),
        "unknown_unavailable_data": inventory["unknown_unavailable_data"],
        "safety_statement": STANDARD_SAFETY_STATEMENT,
        "no_live_mutation_statement": NO_LIVE_MUTATION_STATEMENT,
        "automatic_runtime_migration": False,
        "migration_planner_does_not_delete_move_rewrite_or_migrate_data": True,
        "migration_planner_does_not_mutate_live_trading_state": True,
    })


def storage_map() -> dict[str, Any]:
    inventory = runtime_namespace_inventory()
    return safety_flags({
        "version": APP_VERSION,
        "generated_at": _now(),
        "source_version": SOURCE_VERSION,
        "target_version": TARGET_VERSION,
        "known_compatibility_range": KNOWN_COMPATIBILITY_RANGE,
        "count": inventory["count"],
        "items": inventory["items"],
        "package_excluded_runtime_data": True,
        "manual_migration_guidance": [
            "Do not include runtime namespaces in release ZIPs.",
            "Back up runtime data before future schema changes.",
            "Do not store private keys, API keys, auth headers, or sensitive account data in browser local storage or exported diagnostics.",
        ],
        "dry_run_only": True,
        "unknown_unavailable_data": inventory["unknown_unavailable_data"],
    })


def validate_migration_export_safety(steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = steps or build_migration_steps()
    unsafe = [
        row for row in rows
        if row.get("automatic_mutation_allowed") is True or classify_migration_action(row.get("action", "")) == "destructive action prohibited" and row.get("classification") != "destructive action prohibited"
    ]
    return safety_flags({
        "ok": not unsafe,
        "status": "pass" if not unsafe else "fail",
        "unsafe_step_count": len(unsafe),
        "checked_step_count": len(rows),
        "dry_run_only": True,
        "export_contains_runtime_records": False,
        "export_contains_secrets": False,
    })


def export_migration_plan_json() -> dict[str, Any]:
    plan = migration_plan()
    return export_manifest(
        "runtime_migration_plan_json",
        "v4.3 Runtime Migration Plan",
        included_object_ids=["runtime_namespaces", "migration_steps", "storage_compatibility", "backup_recommendations"],
        related_object_ids=["platform_storage", "platform_routes", "platform_api_schema"],
        warnings=plan.get("warnings", []),
        unknown_unavailable_data=plan.get("unknown_unavailable_data", []),
        payload=plan,
    )


def export_migration_plan_markdown() -> str:
    return to_markdown(export_migration_plan_json())


def export_storage_compatibility_json() -> dict[str, Any]:
    summary = storage_map()
    return export_manifest(
        "storage_compatibility_json",
        "v4.3 Storage Compatibility Report",
        included_object_ids=["runtime_namespaces", "package_exclusions", "compatibility_range", "manual_migration_guidance"],
        related_object_ids=["runtime_migration_plan", "platform_diagnostics"],
        unknown_unavailable_data=summary.get("unknown_unavailable_data", []),
        payload=summary,
    )


def export_storage_compatibility_markdown() -> str:
    return to_markdown(export_storage_compatibility_json())
