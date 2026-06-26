# Runtime Migration Plan Template - v4.17.0-real

Plan ID: `runtime_migration_plan_v4_3_0`

Source version: `4.2.0-real`

Target version: `4.17.0-real`

This is a dry-run-only planning template. It does not delete, move, rewrite, copy, migrate, export, or inspect full runtime records.

Dry-run guarantee: This plan is advisory. It does not delete, move, rewrite, copy, migrate, export, or inspect full runtime records.

## Backup Recommendation

Before any future v4.x data migration, stop the app and make an operator-controlled backup of package-excluded runtime data. v4.3 only reports recommendations.

## Steps

| Step | Namespace | Classification | Auto Mutation | Instruction |
| --- | --- | --- | --- | --- |
| mig_01_live_v2_audit | live_v2_audit | manual review required | False | Review locally, create an operator-controlled backup, and do not include it in release ZIPs. |
| mig_02_live_v2_strategy | live_v2_strategy | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_03_live_v2_research | live_v2_research | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_04_live_v2_monitoring | live_v2_monitoring | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_05_live_v2_portfolio | live_v2_portfolio | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_06_live_v2_governance | live_v2_governance | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_07_v3_workflows | v3_workflows | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_08_v3_analytics | v3_analytics | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_09_v3_simulation | v3_simulation | backup recommended | False | Back up before future v4.x migrations; v4.3 does not copy, delete, rewrite, or move this data automatically. |
| mig_10_v3_datasets | v3_datasets | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_11_v3_freshness | v3_freshness | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_12_v3_tasks | v3_tasks | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_13_v3_workspace | v3_workspace | backup recommended | False | Back up before future v4.x migrations; v4.3 does not copy, delete, rewrite, or move this data automatically. |
| mig_14_v3_cockpit | v3_cockpit | backup recommended | False | Back up before future v4.x migrations; v4.3 does not copy, delete, rewrite, or move this data automatically. |
| mig_15_v4_platform | v4_platform | no-op | False | No action is required unless you expected local runtime data in this namespace. |
| mig_16_v4_ai | v4_ai | manual review required | False | Review locally, create an operator-controlled backup, and do not include it in release ZIPs. |
| mig_17_v4_ai_edge | v4_ai_edge | manual review required | False | Review locally, create an operator-controlled backup, and do not include it in release ZIPs. |
| mig_destructive_actions | all_runtime_namespaces | destructive action prohibited | False | Reject any workflow that attempts destructive migration or live trading mutation from diagnostics or planning. |
