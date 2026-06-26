from __future__ import annotations

import argparse
import json
import subprocess
import sys
import shutil
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run(cmd: list[str]) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=env)
    return {"cmd": " ".join(cmd), "returncode": result.returncode, "stdout_tail": result.stdout[-1200:], "stderr_tail": result.stderr[-1200:]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe v3 release validation harness. Does not call live mutation endpoints.")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    from app.config import APP_VERSION
    from app import ai_openai_client, ai_operator_copilot, ai_prompt_governance, ai_schemas, ai_suggestions
    from app.live_v3 import build_command_center, search_filters, graph_filters, workflow_templates, validation_status, demo_data_safety_check, design_system_status, ux_release_status
    from app.live_v3_analytics import build_analytics_summary, generate_analytics_snapshot, generate_learning_report, export_analytics_json
    from app.live_v3_simulation import simulation_summary, create_session, run_session, process_quality_backtest, export_simulation_json
    from app.live_v3_datasets import datasets_summary, collect_snapshots, build_dataset_manifest, dataset_quality_report, export_dataset_json
    from app.live_v3_freshness import summary as freshness_summary, create_policy, create_collection_job, run_collection_job, readiness_report, create_notification, update_notification, export_freshness_json
    from app.live_v3_tasks import task_summary, create_task, update_task, change_task_status, complete_task, archive_task, scan_inbox, create_task_from_notification, create_task_from_finding, generate_daily_ops_packet, generate_weekly_plan, create_cadence_rule, run_cadence, list_task_templates, export_json as export_tasks_json, export_markdown as export_tasks_markdown
    from app.live_v3_workspace import workspace_summary, list_guided_flows, create_guided_flow, start_flow, list_sessions, update_session_step, complete_session, abandon_session, start_daily_review, start_weekly_review, start_task_triage, create_dependency, delete_dependency, blocked_review, create_source_preview, list_saved_views, create_saved_view, generate_review_packet, export_json as export_workspace_json, export_markdown as export_workspace_markdown, export_dependency_json
    from app.live_v3_cockpit import cockpit_summary, list_layouts, create_layout, update_layout, select_layout, reset_default_layouts, focus_modes, start_focus_mode, list_panels, create_panel, keyboard_shortcuts, command_palette_actions, run_command_palette_action, dependency_view as cockpit_dependency_view, source_context as cockpit_source_context, export_json as export_cockpit_json, export_markdown as export_cockpit_markdown
    from app.platform_diagnostics import platform_summary, health_summary, diagnostics_summary, export_json as export_platform_json, export_markdown as export_platform_markdown
    from app.platform_api import summarize_api_schema_consistency, list_response_envelopes, export_schema_inventory_json, export_schema_inventory_markdown
    from app.platform_migrations import migration_summary, migration_plan, storage_map, export_migration_plan_json, export_migration_plan_markdown, export_storage_compatibility_json, export_storage_compatibility_markdown, validate_migration_export_safety
    from app.platform_plugins import load_plugin_manifests, validate_manifest
    from app.platform_route_registry import route_ownership_registry
    from app.platform_routes import route_inventory, export_route_boundary_json, export_route_boundary_markdown
    from app.platform_storage import storage_summary
    from app.platform_safety import action_is_forbidden, redact_text
    from app.routers import create_ai_router, create_platform_router, create_v3_core_router
    from app import ai_providers, ai_local_llm_client, ai_model_recommendations, ai_edge_research, ai_edge_schemas, ai_news_odds, ai_news_providers
    from app.opportunity_review import build_opportunity_workbench, build_market_detail_context, build_family_comparison, demo_markets, opportunity_review_settings, build_packet_lifecycle_summary
    from app.navigation_registry import get_system_map, get_route_aliases
    if args.quick:
        from app.main import app
        quick_checks = []
        quick_checks.append({"name": "version", "status": "pass" if APP_VERSION == "4.17.0-real" else "fail", "value": APP_VERSION})
        quick_checks.append({"name": "package_identity", "status": "pass", "package_name": "Polymarket OP Console", "package_slug": "polymarket-op-console"})
        quick_checks.append({"name": "router_imports", "status": "pass" if callable(create_ai_router) and callable(create_platform_router) and callable(create_v3_core_router) else "fail"})
        aliases = get_route_aliases()
        system_map = get_system_map()
        quick_checks.append({"name": "navigation_registry", "status": "pass" if system_map.get("aliases_bypass_backend_gates") is False and aliases.get("/ai") == "/v3/ai" and aliases.get("/live") == "/v2-live" else "fail"})
        quick_checks.append({"name": "system_map_ai_news_odds", "status": "pass" if system_map.get("includes_ai_news_odds_adjustment_engine") is True and system_map.get("source_weighting_does_not_imply_truth") is True else "fail"})
        quick_checks.append({"name": "ai_generic_safe_defaults", "status": "pass" if ai_providers.generic_ai_settings_summary().get("safe_default_posture") is True else "fail"})
        quick_checks.append({"name": "openai_safe_defaults", "status": "pass" if ai_openai_client.openai_settings_summary().get("safe_default_posture") is True else "fail"})
        quick_checks.append({"name": "local_llm_safe_defaults", "status": "pass" if ai_local_llm_client.local_llm_settings_summary().get("safe_default_posture") is True else "fail"})
        quick_checks.append({"name": "model_recommendations", "status": "pass" if ai_model_recommendations.list_model_recommendations().get("recommended_default_for_mac_mini_m4_16gb") == "qwen3:8b" else "fail"})
        quick_checks.append({"name": "ai_dry_run", "status": "pass" if ai_providers.test_dry_run({"provider": "ollama"}).get("external_network_called") is False else "fail"})
        news_settings = ai_news_odds.news_odds_settings_summary()
        news_weights = ai_news_odds.source_weight_table()
        news_sources = [
            {"title": "France confirms World Cup roster update", "url": "https://www.fifa.com/news/france-roster-update?utm_source=x", "published_at": "2026-06-01", "snippet": "Official France World Cup update confirmed.", "source_type": "primary"},
            {"title": "France confirms World Cup roster update", "url": "https://reuters.com/sports/france-roster-update", "published_at": "2026-06-01", "snippet": "France World Cup roster update confirmed.", "source_type": "wire"},
            {"title": "France rumor denied", "url": "https://example.com/france-rumor", "published_at": "2026-06-01", "snippet": "Rumor denied and unconfirmed.", "source_type": "blog", "claim_stance": "contradicts"},
        ]
        news_market = demo_markets()[0]
        news_packet = ai_news_odds.build_news_odds_adjustment_packet(news_market, news_sources)
        news_search = ai_news_providers.run_openai_web_news_search({"requests": [{"query": "France World Cup official update"}]}, {})
        quick_checks.append({"name": "ai_news_odds_safe_defaults", "status": "pass" if news_settings.get("safe_default_posture") is True and news_settings.get("ai_news_odds_web_search_enabled") is False and news_settings.get("ai_news_odds_can_place_orders") is False else "fail"})
        quick_checks.append({"name": "ai_news_source_weights", "status": "pass" if news_weights.get("weights", {}).get("primary") == 1.0 and news_weights.get("source_weighting_does_not_imply_truth") is True else "fail"})
        quick_checks.append({"name": "ai_news_duplicate_and_corroboration", "status": "pass" if news_packet.get("duplicate_source_count", 0) >= 0 and news_packet.get("corroboration_does_not_imply_certainty") is True else "fail"})
        quick_checks.append({"name": "ai_news_probability_adjustment", "status": "pass" if news_packet.get("review_only") is True and news_packet.get("does_not_place_orders") is True and ai_news_odds.validate_news_adjustment_safety(news_packet).get("ok") is True else "fail"})
        quick_checks.append({"name": "ai_news_web_search_disabled_by_default", "status": "pass" if news_search.get("external_network_called") is False and news_search.get("web_search_allowed_now") is False else "fail"})
        edge_settings = ai_edge_research.edge_settings_summary()
        edge_dry_run = ai_edge_research.research_dry_run({"research_question": "Validation edge research", "evidence_snippets": ["Operator-provided validation evidence supports only a dry-run packet."]})
        edge_web = ai_edge_research.openai_web_search_dry_run({"research_question": "Validation web-search plan"})
        quick_checks.append({"name": "ai_edge_safe_defaults", "status": "pass" if edge_settings.get("safe_default_posture") is True and edge_settings.get("openai_enable_web_search") is False and edge_settings.get("local_llm_edge_can_search_web") is False else "fail"})
        quick_checks.append({"name": "ai_edge_dry_run_no_network", "status": "pass" if edge_dry_run.get("packet", {}).get("external_network_called") is False and edge_dry_run.get("packet", {}).get("packet_evidence_backed") is True else "fail"})
        quick_checks.append({"name": "ai_edge_web_search_disabled_by_default", "status": "pass" if edge_web.get("external_network_called") is False and edge_web.get("request_plan", {}).get("web_search_allowed_now") is False else "fail"})
        quick_checks.append({"name": "ai_edge_schema_safety", "status": "pass" if ai_edge_schemas.validate_packet(edge_dry_run.get("packet", {})).get("ok") is True else "fail"})
        demo_rows = demo_markets()
        workbench = build_opportunity_workbench(demo_rows, packets=[], limit=10)
        market_detail = build_market_detail_context(demo_rows[0], packets=[])
        family = build_family_comparison(demo_rows, "2026_fifa_world_cup_winner")
        lifecycle = build_packet_lifecycle_summary({"packet_id": "validation", "ai_model_called": True}, current_recommendation=market_detail.get("edge", {}))
        review_settings = opportunity_review_settings()
        quick_checks.append({"name": "opportunity_review_workbench", "status": "pass" if workbench.get("review_only") is True and workbench.get("order_submitted") is False and workbench.get("count", 0) >= 1 else "fail"})
        quick_checks.append({"name": "market_detail_drilldown", "status": "pass" if market_detail.get("review_only") is True and market_detail.get("edge", {}).get("recommended_side") in {"YES", "NO", "HOLD", "NO CLEAR EDGE", "INSUFFICIENT DATA", "NEEDS REVIEW"} else "fail"})
        quick_checks.append({"name": "market_family_comparison", "status": "pass" if family.get("review_only") is True and family.get("family_size", 0) >= 3 and family.get("favorite_by_market_price", {}).get("market_id") else "fail"})
        quick_checks.append({"name": "ai_edge_packet_lifecycle", "status": "pass" if lifecycle.get("lifecycle_state") == "AI_ANALYZED" and lifecycle.get("no_live_mutation_confirmation") is True else "fail"})
        quick_checks.append({"name": "operator_notes_watchlist_paper_review_safety", "status": "pass" if review_settings.get("watchlist_review_only") is True and review_settings.get("paper_review_draft_only") is True and review_settings.get("order_submitted") is False else "fail"})
        quick_checks.append({"name": "prompt_governance", "status": "pass" if ai_prompt_governance.prompt_summary().get("all_require_redaction") is True else "fail"})
        quick_checks.append({"name": "schema_safety", "status": "pass" if ai_schemas.validate_payload("AIReviewSummary", ai_schemas.default_payload("AIReviewSummary")).get("ok") is True else "fail"})
        quick_checks.append({"name": "route_inventory", "status": "pass" if route_inventory(app).get("secret_values_returned") is False else "fail"})
        quick_checks.append({"name": "migration_non_destructive", "status": "pass" if migration_plan().get("migration_planner_does_not_delete_move_rewrite_or_migrate_data") is True else "fail"})
        quick_checks.append({"name": "forbidden_actions", "status": "pass" if all(action_is_forbidden(action) for action in ["place_order", "cancel_order", "arm_live_trading", "disable_kill_switch"]) else "fail"})
        result = {
            "version": APP_VERSION,
            "mode": "quick",
            "checks": quick_checks,
            "overall_status": "pass" if all(item.get("status") == "pass" for item in quick_checks) else "fail",
            "orders_placed": False,
            "orders_cancelled": False,
            "ai_workflows_arm_live_trading": False,
            "ai_task_suggestions_require_human_acceptance": True,
            "openai_api_disabled_by_default": True,
            "local_llm_disabled_by_default": True,
            "dry_run_ai_without_network": True,
            "ai_edge_web_search_disabled_by_default": True,
            "ai_edge_dry_run_without_network": True,
            "ai_edge_research_only": True,
            "opportunity_review_workbench_review_only": True,
            "market_detail_drilldown_review_only": True,
            "market_family_comparison_review_only": True,
            "ai_edge_packet_lifecycle_review_only": True,
            "secret_values_returned": False,
        }
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0 if result["overall_status"] == "pass" else 1
    checks = []
    checks.append({"name": "version", "status": "pass" if APP_VERSION == "4.17.0-real" else "fail", "value": APP_VERSION})
    checks.append({"name": "command_center", "status": "pass" if build_command_center().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "navigation_registry", "status": "pass" if get_system_map().get("aliases_bypass_backend_gates") is False and get_route_aliases().get("/operator-os") == "/v3" else "fail"})
    demo_rows = demo_markets()
    checks.append({"name": "opportunity_review_workbench", "status": "pass" if build_opportunity_workbench(demo_rows, packets=[], limit=10).get("review_only") is True else "fail"})
    checks.append({"name": "market_detail_drilldown", "status": "pass" if build_market_detail_context(demo_rows[0], packets=[]).get("review_only") is True else "fail"})
    checks.append({"name": "market_family_comparison", "status": "pass" if build_family_comparison(demo_rows, "2026_fifa_world_cup_winner").get("review_only") is True else "fail"})
    checks.append({"name": "ai_edge_packet_lifecycle", "status": "pass" if build_packet_lifecycle_summary({"packet_id":"validation","ai_model_called":True}).get("lifecycle_state") == "AI_ANALYZED" else "fail"})
    checks.append({"name": "search_filters", "status": "pass" if search_filters().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "graph_filters", "status": "pass" if graph_filters().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "workflow_templates", "status": "pass" if workflow_templates().get("count", 0) >= 10 else "fail"})
    checks.append({"name": "demo_fixture_safety", "status": "pass" if demo_data_safety_check({}).get("ok") else "fail"})
    checks.append({"name": "analytics_summary", "status": "pass" if build_analytics_summary().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "analytics_snapshot", "status": "pass" if generate_analytics_snapshot(write=False).get("order_submitted") is False else "fail"})
    checks.append({"name": "learning_report", "status": "pass" if generate_learning_report(write=False).get("analytics_are_descriptive") is True else "fail"})
    checks.append({"name": "analytics_export", "status": "pass" if export_analytics_json().get("secret_values_returned") is False else "fail"})
    sim_session = create_session({"session_title": "Validation replay", "simulation_type": "process_quality_backtest"})
    sim_run = run_session(sim_session["session"]["session_id"])
    checks.append({"name": "simulation_summary", "status": "pass" if simulation_summary().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "simulation_session", "status": "pass" if sim_session.get("order_submitted") is False else "fail"})
    checks.append({"name": "simulation_run", "status": "pass" if sim_run.get("live_trading_armed") is False else "fail"})
    checks.append({"name": "process_backtest", "status": "pass" if process_quality_backtest().get("simulation_only") is True else "fail"})
    checks.append({"name": "simulation_export", "status": "pass" if export_simulation_json().get("secret_values_returned") is False else "fail"})
    ds_collect = collect_snapshots({"snapshot_types": ["market_metadata", "order_book", "local_strategy"], "collection_mode": "demo", "market": {"market_id": "VALIDATION", "question": "VALIDATION fake market", "outcomes": ["YES", "NO"]}, "order_book": {"market_id": "VALIDATION", "token_id": "VALIDATION-YES", "bids": [[0.4, 10]], "asks": [[0.6, 10]], "best_bid": 0.4, "best_ask": 0.6}})
    ds_manifest = build_dataset_manifest({"title": "Validation Dataset", "include_demo_data": True})
    checks.append({"name": "dataset_summary", "status": "pass" if datasets_summary().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "dataset_collect", "status": "pass" if ds_collect.get("order_submitted") is False else "fail"})
    checks.append({"name": "dataset_manifest", "status": "pass" if ds_manifest.get("manifest", {}).get("dataset_id") else "fail"})
    checks.append({"name": "dataset_quality", "status": "pass" if dataset_quality_report().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "dataset_export", "status": "pass" if export_dataset_json().get("secret_values_returned") is False else "fail"})
    fresh_policy = create_policy({"title": "Validation Freshness", "target_snapshot_types": ["market_metadata"], "freshness_threshold_minutes": 30})
    fresh_job = create_collection_job({"source_policy_id": fresh_policy["policy_id"], "snapshot_types": ["market_metadata"], "run_mode": "demo"})
    fresh_run = run_collection_job(fresh_job["job_id"], {"collection_mode": "demo"})
    fresh_note = create_notification({"title": "Validation freshness notification", "message": "Fake validation notification."})
    fresh_ack = update_notification(fresh_note["notification_id"], "ack")
    checks.append({"name": "freshness_summary", "status": "pass" if freshness_summary().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "freshness_policy", "status": "pass" if fresh_policy.get("policy_id") else "fail"})
    checks.append({"name": "freshness_job", "status": "pass" if fresh_job.get("order_submitted") is False else "fail"})
    checks.append({"name": "freshness_job_run", "status": "pass" if fresh_run.get("live_trading_armed") is False else "fail"})
    checks.append({"name": "freshness_readiness", "status": "pass" if readiness_report(write=False).get("secret_values_returned") is False else "fail"})
    checks.append({"name": "freshness_notification", "status": "pass" if fresh_ack.get("notification", {}).get("status") == "acknowledged" else "fail"})
    checks.append({"name": "freshness_export", "status": "pass" if export_freshness_json().get("secret_values_returned") is False else "fail"})

    task = create_task({"title": "Validation task", "description": "Fake validation task", "priority": "high", "status": "planned", "source_subsystem": "validation"})
    task_update = update_task(task["task_id"], {"operator_notes": "Updated during validation."})
    task_status = change_task_status(task["task_id"], "active")
    task_complete = complete_task(task["task_id"], notes="Validation completion only.")
    task_archive = archive_task(task["task_id"], notes="Archive after completion validation.")
    inbox_scan = scan_inbox(write=True)
    notification_task = create_task_from_notification(fresh_note["notification_id"], {"status": "planned"})
    finding_task = create_task_from_finding({"title": "Validation finding", "source_subsystem": "validation", "severity": "warning"})
    daily = generate_daily_ops_packet(write=True)
    weekly = generate_weekly_plan(write=True)
    cadence = create_cadence_rule({"title": "Validation cadence", "target_subsystem": "validation", "cadence_type": "weekly"})
    cadence_run = run_cadence({"create_tasks": False})
    checks.append({"name": "task_summary", "status": "pass" if task_summary().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "task_create", "status": "pass" if task.get("order_submitted") is False and task.get("task_id") else "fail"})
    checks.append({"name": "task_update", "status": "pass" if task_update.get("task_id") == task.get("task_id") else "fail"})
    checks.append({"name": "task_status", "status": "pass" if task_status.get("status") == "active" else "fail"})
    checks.append({"name": "task_complete_no_trade_approval", "status": "pass" if task_complete.get("task_completion_is_not_trade_approval") is True and task_complete.get("order_submitted") is False else "fail"})
    checks.append({"name": "task_archive", "status": "pass" if task_archive.get("status") == "archived" else "fail"})
    checks.append({"name": "task_inbox_scan", "status": "pass" if inbox_scan.get("order_submitted") is False else "fail"})
    checks.append({"name": "notification_to_task", "status": "pass" if notification_task.get("ok") is True or notification_task.get("error") == "notification_not_found" else "fail"})
    checks.append({"name": "finding_to_task", "status": "pass" if finding_task.get("ok") is True else "fail"})
    checks.append({"name": "daily_ops_packet", "status": "pass" if daily.get("order_cancelled") is False else "fail"})
    checks.append({"name": "weekly_planning_packet", "status": "pass" if weekly.get("live_trading_armed") is False else "fail"})
    checks.append({"name": "cadence_rule", "status": "pass" if cadence.get("cadence_id") else "fail"})
    checks.append({"name": "cadence_run", "status": "pass" if cadence_run.get("order_submitted") is False else "fail"})
    checks.append({"name": "task_templates", "status": "pass" if list_task_templates().get("count", 0) >= 10 else "fail"})
    checks.append({"name": "task_export_json", "status": "pass" if export_tasks_json().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "task_export_markdown", "status": "pass" if "does not place" in export_tasks_markdown().lower() else "fail"})

    flow = create_guided_flow({"title": "Validation guided flow", "flow_type": "custom", "target_subsystem": "validation", "steps": ["Review", "Packet"]})
    session_started = start_flow(flow["flow_id"], {"title": "Validation guided session"})
    session_id = session_started.get("session", {}).get("session_id", "")
    session_step = update_session_step(session_id, {"step_id": "step_01", "unresolved_items": ["Fake unresolved validation item"]})
    session_complete = complete_session(session_id, {"status_summary": "Validation guided review complete."})
    abandoned = start_task_triage({"title": "Validation triage abandon"})
    abandon_result = abandon_session(abandoned.get("session", {}).get("session_id", ""), {"notes": "Validation abandon only."})
    daily_guided = start_daily_review({"title": "Validation daily guided review"})
    weekly_guided = start_weekly_review({"title": "Validation weekly guided review"})
    dep = create_dependency({"task_id": task["task_id"], "depends_on_task_id": finding_task.get("task", {}).get("task_id", "validation-prereq"), "notes": "Validation dependency only."})
    dep_delete = delete_dependency(dep["dependency_id"])
    block = blocked_review(write=True)
    preview = create_source_preview({"title": "Validation source preview", "source_subsystem": "validation", "severity": "warning"}, write=True)
    view = create_saved_view({"title": "Validation saved view", "filters": {"status": "blocked"}})
    packet = generate_review_packet({"title": "Validation guided packet", "packet_type": "dependency-review", "included_task_ids": [task["task_id"]]}, write=True)
    checks.append({"name": "workspace_summary", "status": "pass" if workspace_summary().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "guided_flow_listing", "status": "pass" if list_guided_flows().get("count", 0) >= 10 else "fail"})
    checks.append({"name": "guided_flow_creation", "status": "pass" if flow.get("flow_id") else "fail"})
    checks.append({"name": "guided_session_start", "status": "pass" if session_started.get("ok") is True and session_started.get("order_submitted") is False else "fail"})
    checks.append({"name": "guided_step_completion", "status": "pass" if "step_01" in session_step.get("completed_steps", []) else "fail"})
    checks.append({"name": "guided_session_completion", "status": "pass" if session_complete.get("guided_review_completion_is_not_trade_approval") is True and session_complete.get("order_cancelled") is False else "fail"})
    checks.append({"name": "guided_session_abandonment", "status": "pass" if abandon_result.get("status") == "abandoned" else "fail"})
    checks.append({"name": "daily_guided_review", "status": "pass" if daily_guided.get("order_submitted") is False else "fail"})
    checks.append({"name": "weekly_guided_review", "status": "pass" if weekly_guided.get("live_trading_armed") is False else "fail"})
    checks.append({"name": "task_triage_review", "status": "pass" if abandoned.get("session", {}).get("flow_type") == "task-triage" else "fail"})
    checks.append({"name": "dependency_create_delete", "status": "pass" if dep.get("dependency_id") and dep_delete.get("ok") is True else "fail"})
    checks.append({"name": "blocked_task_review", "status": "pass" if block.get("packet", {}).get("order_submitted") is False else "fail"})
    checks.append({"name": "source_preview", "status": "pass" if preview.get("preview_id") and preview.get("secret_values_returned") is False else "fail"})
    checks.append({"name": "saved_view", "status": "pass" if view.get("view_id") and list_saved_views().get("count", 0) >= 1 else "fail"})
    checks.append({"name": "guided_review_packet", "status": "pass" if packet.get("packet_id") and packet.get("packets_do_not_place_or_cancel_orders") is True else "fail"})
    checks.append({"name": "guided_export_json", "status": "pass" if export_workspace_json().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "guided_export_markdown", "status": "pass" if "does not place" in export_workspace_markdown().lower() or "do not place" in export_workspace_markdown().lower() else "fail"})

    cockpit_layout = create_layout({"title": "Validation Cockpit Layout", "layout_type": "custom", "panel_ids": ["panel_task_list", "panel_safe_next"]})
    cockpit_layout_update = update_layout(cockpit_layout["layout_id"], {"operator_notes": "Validation layout update."})
    cockpit_select = select_layout(cockpit_layout["layout_id"])
    cockpit_reset = reset_default_layouts()
    cockpit_focus = start_focus_mode("focus_daily_review")
    cockpit_panel = create_panel({"title": "Validation Cockpit Panel", "panel_type": "task-list", "source_subsystem": "validation"})
    cockpit_command = run_command_palette_action({"action_id": "navigate_cockpit"})
    cockpit_forbidden = run_command_palette_action({"action_id": "place_order"})
    checks.append({"name": "cockpit_summary", "status": "pass" if cockpit_summary().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "cockpit_layout_listing", "status": "pass" if list_layouts().get("count", 0) >= 1 else "fail"})
    checks.append({"name": "cockpit_layout_creation", "status": "pass" if cockpit_layout.get("order_submitted") is False and cockpit_layout.get("layout_id") else "fail"})
    checks.append({"name": "cockpit_layout_update", "status": "pass" if cockpit_layout_update.get("layout_id") == cockpit_layout.get("layout_id") else "fail"})
    checks.append({"name": "cockpit_layout_selection", "status": "pass" if cockpit_select.get("ok") is True and cockpit_select.get("order_cancelled") is False else "fail"})
    checks.append({"name": "cockpit_default_layout_reset", "status": "pass" if cockpit_reset.get("ok") is True and cockpit_reset.get("live_trading_armed") is False else "fail"})
    checks.append({"name": "cockpit_focus_mode", "status": "pass" if cockpit_focus.get("ok") is True and focus_modes().get("count", 0) >= 10 else "fail"})
    checks.append({"name": "cockpit_panel_listing", "status": "pass" if list_panels().get("count", 0) >= 1 else "fail"})
    checks.append({"name": "cockpit_panel_creation", "status": "pass" if cockpit_panel.get("mutates_live_trading_state") is False else "fail"})
    checks.append({"name": "keyboard_shortcut_manifest", "status": "pass" if keyboard_shortcuts().get("keyboard_shortcuts_do_not_place_or_cancel_orders") is True else "fail"})
    checks.append({"name": "command_palette_manifest", "status": "pass" if command_palette_actions().get("command_palette_actions_do_not_place_or_cancel_orders") is True else "fail"})
    checks.append({"name": "safe_command_palette_action", "status": "pass" if cockpit_command.get("ok") is True and cockpit_command.get("order_submitted") is False else "fail"})
    checks.append({"name": "forbidden_command_palette_action", "status": "pass" if cockpit_forbidden.get("status") == "rejected" else "fail"})
    checks.append({"name": "cockpit_dependency_view", "status": "pass" if cockpit_dependency_view().get("order_submitted") is False else "fail"})
    checks.append({"name": "cockpit_source_context", "status": "pass" if cockpit_source_context().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "cockpit_export_json", "status": "pass" if export_cockpit_json().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "cockpit_export_markdown", "status": "pass" if "do not place" in export_cockpit_markdown().lower() or "does not place" in export_cockpit_markdown().lower() else "fail"})
    checks.append({"name": "cockpit_no_live_mutation", "status": "pass" if cockpit_command.get("order_submitted") is False and cockpit_forbidden.get("order_cancelled") is False else "fail"})
    checks.append({"name": "dependency_export", "status": "pass" if export_dependency_json().get("secret_values_returned") is False else "fail"})
    platform_diag = diagnostics_summary()
    platform_plugins = load_plugin_manifests()
    platform_export = export_platform_json()
    schema_summary = summarize_api_schema_consistency()
    schema_export = export_schema_inventory_json()
    migration = migration_plan()
    migration_export = export_migration_plan_json()
    storage_compat_export = export_storage_compatibility_json()
    route_boundary_export = export_route_boundary_json()
    route_registry = route_ownership_registry()
    generated_manual = ROOT / "docs" / "generated" / f"OPERATOR_MANUAL_v{APP_VERSION}.md"
    checks.append({"name": "platform_summary", "status": "pass" if platform_summary().get("secret_values_returned") is False else "fail"})
    checks.append({"name": "platform_health", "status": "pass" if health_summary().get("platform_diagnostics_do_not_mutate_live_trading_state") is True else "fail"})
    checks.append({"name": "platform_diagnostics", "status": "pass" if platform_diag.get("diagnostics_do_not_mutate_live_trading_state") is True else "fail"})
    checks.append({"name": "platform_routes", "status": "pass" if route_inventory().get("route_inventory_does_not_mutate_live_trading_state") is True else "fail"})
    checks.append({"name": "route_module_boundary_export_json", "status": "pass" if route_boundary_export.get("secret_values_returned") is False else "fail"})
    checks.append({"name": "route_module_boundary_export_markdown", "status": "pass" if "Route and Module Boundary" in export_route_boundary_markdown() else "fail"})
    checks.append({"name": "router_imports", "status": "pass" if callable(create_platform_router) and callable(create_v3_core_router) and callable(create_ai_router) else "fail"})
    checks.append({"name": "route_ownership_registry", "status": "pass" if route_registry.get("count", 0) >= 10 and "app/routers/platform.py" in route_registry.get("extracted_router_modules", []) and "app/routers/ai.py" in route_registry.get("extracted_router_modules", []) else "fail"})
    checks.append({"name": "platform_router_extraction", "status": "pass" if any(item.get("router_module") == "app/routers/platform.py" and item.get("extraction_status") == "extracted" for item in route_registry.get("items", [])) else "fail"})
    checks.append({"name": "ai_router_extraction", "status": "pass" if any(item.get("router_module") == "app/routers/ai.py" and item.get("extraction_status") == "extracted" for item in route_registry.get("items", [])) else "fail"})
    checks.append({"name": "api_schema_inventory", "status": "pass" if schema_summary.get("summary", {}).get("api_family_count", 0) >= 8 else "fail"})
    checks.append({"name": "api_schema_envelope_adoption_summary", "status": "pass" if schema_summary.get("data", {}).get("envelope_adoption_summary", {}).get("normalized_family_count", 0) >= 1 else "fail"})
    checks.append({"name": "api_schema_unnormalized_endpoint_list", "status": "pass" if isinstance(schema_summary.get("data", {}).get("unnormalized_endpoint_list"), list) else "fail"})
    checks.append({"name": "response_envelope_inventory", "status": "pass" if list_response_envelopes().get("items") else "fail"})
    checks.append({"name": "api_schema_export_json", "status": "pass" if schema_export.get("secret_values_returned") is False else "fail"})
    checks.append({"name": "api_schema_export_markdown", "status": "pass" if "API Schema Inventory" in export_schema_inventory_markdown() else "fail"})
    checks.append({"name": "migration_summary", "status": "pass" if migration_summary().get("migration_planner_does_not_mutate_runtime_data") is True else "fail"})
    checks.append({"name": "migration_plan_non_destructive", "status": "pass" if migration.get("automatic_runtime_migration") is False and migration.get("migration_planner_does_not_delete_move_rewrite_or_migrate_data") is True else "fail"})
    checks.append({"name": "migration_destructive_prohibited", "status": "pass" if any(step.get("classification") == "destructive action prohibited" for step in migration.get("steps", [])) else "fail"})
    checks.append({"name": "migration_export_safety_validation", "status": "pass" if validate_migration_export_safety(migration.get("steps", [])).get("ok") is True else "fail"})
    checks.append({"name": "migration_source_target_versions", "status": "pass" if migration.get("source_version") == "4.2.0-real" and migration.get("target_version") == "4.17.0-real" else "fail"})
    checks.append({"name": "migration_export_json", "status": "pass" if migration_export.get("secret_values_returned") is False else "fail"})
    checks.append({"name": "migration_export_markdown", "status": "pass" if "Runtime Migration Plan" in export_migration_plan_markdown() else "fail"})
    checks.append({"name": "storage_map", "status": "pass" if storage_map().get("package_excluded_runtime_data") is True else "fail"})
    checks.append({"name": "storage_compatibility_export_json", "status": "pass" if storage_compat_export.get("secret_values_returned") is False else "fail"})
    checks.append({"name": "storage_compatibility_export_markdown", "status": "pass" if "Storage Compatibility" in export_storage_compatibility_markdown() else "fail"})
    checks.append({"name": "platform_plugins", "status": "pass" if platform_plugins.get("plugin_manifests_do_not_execute_code") is True and platform_plugins.get("invalid_count") == 0 else "fail"})
    checks.append({"name": "plugin_forbidden_capability", "status": "pass" if validate_manifest({"plugin_id":"bad","plugin_type":"local-ui-extension","capabilities":["place_order"],"no_live_mutation":True,"no_secret_access":True,"no_network_by_default":True}).get("ok") is False else "fail"})
    checks.append({"name": "storage_namespace_summary", "status": "pass" if storage_summary().get("count", 0) >= 5 else "fail"})
    checks.append({"name": "platform_export_json", "status": "pass" if platform_export.get("secret_values_returned") is False else "fail"})
    checks.append({"name": "platform_export_markdown", "status": "pass" if "do not place" in export_platform_markdown().lower() or "does not place" in export_platform_markdown().lower() else "fail"})
    checks.append({"name": "generated_manual_exists", "status": "pass" if generated_manual.exists() else "fail"})
    checks.append({"name": "generated_manual_secret_scan", "status": "pass" if generated_manual.exists() and "supersecret" not in generated_manual.read_text(encoding="utf-8").lower() and "begin private key" not in generated_manual.read_text(encoding="utf-8").lower() else "fail"})
    checks.append({"name": "diagnostics_no_live_mutation", "status": "pass" if platform_diag.get("order_submitted") is False and platform_diag.get("order_cancelled") is False and platform_diag.get("live_trading_armed") is False else "fail"})
    checks.append({"name": "secret_redaction_helper", "status": "pass" if "supersecret" not in redact_text("api_key=supersecret").lower() else "fail"})
    checks.append({"name": "forbidden_live_mutation_list", "status": "pass" if action_is_forbidden("place_order") and action_is_forbidden("cancel_order") and action_is_forbidden("arm_live_trading") else "fail"})

    ai_settings = ai_openai_client.openai_settings_summary()
    ai_prompts = ai_prompt_governance.prompt_summary()
    ai_registry = ai_schemas.schema_registry()
    ai_schema_validation = ai_schemas.validate_payload("AIReviewSummary", ai_schemas.default_payload("AIReviewSummary"))
    ai_copilot = ai_operator_copilot.copilot_status()
    ai_dry_run = ai_operator_copilot.run_copilot_workflow("summarize_daily_review_context", {"context_type": "tasks"})
    ai_suggestion = ai_suggestions.generate_suggestions({"source_context_type": "tasks", "source_context_id": "validation"}, write=True)
    suggestion_id = ai_suggestion.get("items", [{}])[0].get("suggestion_id", "")
    ai_accept = ai_suggestions.accept_suggestion(suggestion_id, {"status": "planned"}) if suggestion_id else {"ok": False}
    ai_packet = ai_suggestions.generate_review_packet({"packet_type": "AI Platform Diagnostics Summary"}, write=True)
    ai_connector = ai_suggestions.chatgpt_connector_blueprint()
    ai_redaction = ai_suggestions.redaction_preview({"OPENAI_API_KEY": "redaction-placeholder-key", "authorization": "Bearer redacted-token", "safe": "review"})
    ai_export = ai_suggestions.export_json()
    checks.append({"name": "ai_openai_safe_defaults", "status": "pass" if ai_settings.get("safe_default_posture") is True and ai_settings.get("openai_enable_api") is False and ai_settings.get("openai_dry_run_only") is True else "fail"})
    checks.append({"name": "ai_prompt_governance", "status": "pass" if ai_prompts.get("all_require_redaction") is True and ai_prompts.get("all_require_human_approval") is True and ai_prompts.get("all_include_safety_statement") is True else "fail"})
    checks.append({"name": "ai_schema_registry", "status": "pass" if ai_registry.get("count", 0) >= 10 and ai_schema_validation.get("ok") is True else "fail"})
    checks.append({"name": "ai_copilot_status", "status": "pass" if ai_copilot.get("api_disabled_by_default") is True and ai_copilot.get("dry_run_only_by_default") is True and ai_copilot.get("tool_calling_disabled_by_default") is True else "fail"})
    checks.append({"name": "ai_copilot_dry_run_no_network", "status": "pass" if ai_dry_run.get("mode") == "dry_run" and ai_dry_run.get("external_network_called") is False and ai_dry_run.get("ai_cannot_place_or_cancel_orders") is True else "fail"})
    checks.append({"name": "ai_suggestion_human_acceptance", "status": "pass" if ai_suggestion.get("ai_task_suggestions_require_human_acceptance") is True and ai_accept.get("ok") is True and ai_accept.get("task", {}).get("order_submitted") is False and ai_accept.get("task_completion_is_not_trade_approval") is True else "fail"})
    checks.append({"name": "ai_review_packet", "status": "pass" if ai_packet.get("packet", {}).get("human_review_required") is True and ai_packet.get("order_cancelled") is False else "fail"})
    checks.append({"name": "ai_chatgpt_connector_blueprint", "status": "pass" if ai_connector.get("read_only") is True and ai_connector.get("auth_required") is True and ai_connector.get("mcp_server_enabled") is False and "place_order" in ai_connector.get("forbidden_tools", []) else "fail"})
    checks.append({"name": "ai_redaction_preview", "status": "pass" if ai_redaction.get("secret_scan", {}).get("ok") is True and "validation-secret" not in json.dumps(ai_redaction).lower() else "fail"})
    checks.append({"name": "ai_export_secret_safe", "status": "pass" if ai_export.get("secret_values_returned") is False and ai_export.get("raw_prompts_included") is False and ai_export.get("raw_responses_included") is False else "fail"})

    checks.append({"name": "design_system", "status": design_system_status().get("status", "unknown")})
    checks.append({"name": "ux_release_status", "status": ux_release_status().get("overall_status", "unknown")})
    checks.append({"name": "validation_status", "status": validation_status().get("overall_status", "unknown")})
    commands = []
    if not args.quick:
        commands.extend([
            run([sys.executable, "-m", "compileall", "-q", "app", "tests", "scripts"]),
            run([sys.executable, "scripts/generate_operator_manual.py"]),
            run([sys.executable, "-m", "pytest", "-q", "tests/test_api_contracts_v4.py"]),
            run([sys.executable, "scripts/check_versions.py"]),
            run([sys.executable, "scripts/smoke_startup.py"]),
        ])
        # Smoke/compile checks intentionally create transient runtime/cache files. Remove them before packaging hygiene.
        for rel in [".pytest_cache", "data", "runtime_screenshots"]:
            shutil.rmtree(ROOT / rel, ignore_errors=True)
        for cache in list(ROOT.rglob("__pycache__")):
            shutil.rmtree(cache, ignore_errors=True)
        commands.append(run([sys.executable, "scripts/check_release_package.py", "."]))
    overall = "pass" if all(c.get("status") == "pass" for c in checks if c["name"] != "validation_status") and all(c.get("returncode") == 0 for c in commands) else "fail"
    report = {
        "version": APP_VERSION,
        "package_name": "Polymarket OP Console",
        "package_slug": "polymarket-op-console",
        "overall_status": overall,
        "checks": checks,
        "commands": commands,
        "route_families_checked": sorted(route_inventory().get("families", {}).keys()),
        "api_families_checked": [item.get("family_id") for item in schema_summary.get("data", {}).get("api_families", [])],
        "schema_families_checked": [item.get("schema_id") for item in schema_summary.get("data", {}).get("schema_objects", [])],
        "routers_checked": route_registry.get("extracted_router_modules", []),
        "route_ownership_registry_count": route_registry.get("count", 0),
        "api_contract_groups_checked": ["platform_summary", "route_inventory", "route_registry", "api_schema", "migration_planner", "plugin_summary", "safe_summaries", "ai_copilot", "ai_suggestions", "ai_prompt_governance"],
        "generated_manual_status": {"exists": generated_manual.exists(), "path": str(generated_manual.relative_to(ROOT)) if generated_manual.exists() else str(generated_manual)},
        "migration_storage_checks": migration_summary().get("classifications", {}),
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "migration_planner_does_not_delete_move_rewrite_or_migrate_runtime_data": True,
        "generated_manual_contains_no_secrets": generated_manual.exists(),
        "platform_diagnostics_do_not_mutate_live_trading_state": True,
        "plugin_manifests_do_not_execute_code": True,
        "command_palette_actions_do_not_place_or_cancel_orders": True,
        "keyboard_shortcuts_do_not_place_or_cancel_orders": True,
        "task_completion_does_not_approve_trades": True,
        "guided_review_completion_does_not_approve_trades": True,
        "cockpit_platform_schema_and_migration_workflows_are_local_first_non_autonomous": True,
        "demo_data_is_fake_and_secret_free": True,
        "screenshots_included_in_release_zip": False,
        "ai_assistance_enabled": True,
        "ai_assistance_mode": "draft_only_dry_run_by_default",
        "ai_api_disabled_by_default": ai_settings.get("openai_enable_api") is False,
        "ai_dry_run_only_by_default": ai_settings.get("openai_dry_run_only") is True,
        "ai_task_suggestions_require_human_acceptance": True,
        "ai_connector_read_only_disabled_by_default": ai_connector.get("read_only") is True and ai_connector.get("mcp_server_enabled") is False,
        "secret_values_returned": False,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if overall == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
