from __future__ import annotations

import json
from urllib.parse import urlencode
from typing import Any

from fastapi import Body, Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates

from .config import APP_DIR, APP_VERSION, APP_VERSION_SHORT, settings
from .gamma_client import GammaClient
from .clob_client import ClobClient
from .history import latest_snapshot_summary, list_snapshots
from .scoring import attach_scores
from .snapshots import calculate_movers, detect_new_markets, load_latest, save_snapshot, summarize_snapshot
from .research import make_research_packet
from .watchlist import add_to_watchlist, load_watchlist, remove_from_watchlist
from .auth_status import get_api_key_status
from .probability import attach_probability, estimate_probability
from .market_edge import build_market_recommendation_row, edge_recommendation_legend, enrich_markets_with_recommendations, rank_market_family
from .paper_trading import buy as paper_buy, sell as paper_sell, reset_portfolio, summarize_portfolio, load_trades, load_portfolio
from . import paper_automation as v416_paper
from . import operator_os as v417_operator_os
from .paper_settlement import list_settlements, preview_settlement, settle_market, settlement_candidates, settlement_summary
from .paper_positions import list_position_events, position_alerts, position_control_summary, update_position_plan
from .paper_exit_tickets import create_exit_ticket, delete_exit_ticket, executable_exit_snapshot, get_exit_ticket, list_exit_tickets, summarize_exit_tickets, update_exit_ticket
from .paper_audit import audit_to_csv, build_audit_events, build_market_audit, summarize_audit
from .paper_review import build_market_review, build_review_report, review_report_to_csv
from .paper_playbooks import build_playbook_board, create_playbook_decision, evaluate_market_playbooks, get_playbook, list_playbook_decisions, list_playbooks, summarize_playbook_board, summarize_playbook_decisions, summarize_playbooks, upsert_playbook
from .playbook_performance import build_playbook_performance, build_playbook_performance_detail, playbook_performance_to_csv
from .paper_risk_budget import build_market_risk_budget, build_risk_budget, risk_budget_alerts, risk_budget_to_csv
from .paper_preflight import build_preflight_board, build_ticket_preflight, preflight_alerts, preflight_to_csv
from .paper_approvals import approval_alerts, approve_trade_ticket, approvals_to_csv, build_execution_approval_board, get_execution_approval, record_execution_decision, reject_trade_ticket, summarize_execution_approvals
from .paper_execution_queue import build_execution_queue, build_ticket_execution_queue_item, execution_queue_alerts, execution_queue_to_csv, ticket_execution_gate
from .paper_runbook import build_runbook, get_runbook_item, list_runbook_acknowledgements, record_runbook_acknowledgement, runbook_alerts, runbook_to_csv
from .paper_briefing import briefing_alerts, briefing_to_csv, build_paper_ops_briefing, list_briefing_checkpoints, record_briefing_checkpoint
from .paper_handoff import build_operator_handoff_board, build_operator_handoff_reconciliation_board, get_operator_handoff, handoff_alerts, handoff_reconciliation_to_csv, handoffs_to_csv, list_operator_handoffs, reconcile_operator_handoff, record_operator_handoff
from .paper_ops_aging import build_ops_aging_detail, build_paper_ops_aging, ops_aging_alerts, ops_aging_to_csv
from .paper_ops_escalations import build_ops_escalation_board, create_ops_escalation, get_ops_escalation, list_ops_escalations, ops_escalation_alerts, ops_escalations_to_csv, update_ops_escalation
from .paper_ops_escalation_review import build_ops_escalation_review, ops_escalation_review_alerts, ops_escalation_review_to_csv, review_ops_escalation
from .paper_ops_closeout import build_paper_ops_closeout, paper_ops_closeout_alerts, paper_ops_closeout_to_csv
from .paper_ops_closeout_signoffs import build_ops_closeout_signoff_board, get_ops_closeout_signoff, list_ops_closeout_signoffs, ops_closeout_signoff_alerts, ops_closeout_signoffs_to_csv, record_ops_closeout_signoff
from .strategy import recommend_paper_trades, explain_strategy
from .backtest import run_snapshot_backtest, list_backtests
from .risk import check_paper_buy, risk_status
from .analytics import trade_analytics, trades_to_csv
from .alerts import generate_alerts, summarize_alerts
from .notes import add_note, delete_note, load_notes, notes_for_market, notes_summary
from .auth import authenticate, create_user, delete_user, get_session_secret, get_user, list_users_public, setup_initial_admin, update_user, users_exist
from .network_security import host_guard_middleware, network_status, security_headers_middleware
from .deployment import deployment_status
from .maintenance import create_backup, delete_backup, get_backup_path, maintenance_status
from .sources import build_market_collection_targets, build_market_source_pack, build_source_links, check_sources_status, list_sources, source_summary
from .evidence import create_evidence_packet as create_manual_evidence_packet, delete_evidence_packet, evidence_summary, list_evidence_packets as list_manual_evidence_packets, load_evidence_packet
from .evidence_scoring import score_evidence_packet, score_market_evidence, score_packet_by_id
from .evidence_probability import attach_evidence_probability, evidence_adjusted_probability
from .operator_dashboard import build_operator_brief
from .opportunity_engine import rank_opportunities, opportunity_summary
from .opportunity_review import (
    REVIEW_ONLY_NOTE as OPPORTUNITY_REVIEW_ONLY_NOTE,
    build_family_comparison,
    build_market_detail_context,
    build_opportunity_workbench,
    demo_markets as opportunity_demo_markets,
    get_review_record,
    list_operator_notes as list_opportunity_notes,
    list_review_records,
    opportunity_review_settings,
    update_review_notes,
    update_review_status,
)
from .live_config import build_live_config_readiness, live_config_alerts, live_config_readiness_to_csv, live_config_template
from .live_order_intents import build_live_order_intent, build_live_order_intent_board, get_live_order_intent, list_live_order_intents, live_order_intent_alerts, live_order_intents_to_csv, record_live_order_intent
from .live_order_preflight import build_live_order_preflight_board, live_order_preflight_alerts, live_order_preflights_to_csv, list_live_order_preflights, review_live_order_intent
from .live_order_authorizations import build_live_order_authorization_board, get_live_order_authorization, live_order_authorization_alerts, live_order_authorizations_to_csv, list_live_order_authorizations, record_live_order_authorization
from .live_execution_packets import build_live_execution_packet, build_live_execution_packet_board, get_live_execution_packet, live_execution_packet_alerts, live_execution_packets_to_csv, list_live_execution_packets, record_live_execution_packet
from .live_dry_run_adapter import build_live_dry_run_board, build_live_dry_run_receipt, get_live_dry_run_receipt, live_dry_run_alerts, live_dry_run_receipts_to_csv, list_live_dry_run_receipts, record_live_dry_run_receipt
from .live_dry_run_review import build_live_dry_run_review_board, live_dry_run_review_alerts, live_dry_run_reviews_to_csv, list_live_dry_run_reviews, review_live_dry_run_packet
from .live_adapter import build_live_adapter_readiness, build_live_adapter_request, build_live_adapter_request_board, build_manual_execution_review, build_manual_execution_review_board, get_live_adapter_readonly_validation, get_live_adapter_request, get_manual_execution_review, list_live_adapter_readonly_validations, list_live_adapter_requests, list_manual_execution_reviews, live_adapter_alerts, live_adapter_readiness_to_csv, live_adapter_requests_to_csv, live_adapter_validations_to_csv, manual_execution_reviews_to_csv, preview_live_adapter_readonly_validation, record_live_adapter_readonly_validation, record_live_adapter_request, record_manual_execution_review
from .live_execution_control import build_live_execution_attempt_board, build_live_execution_control_readiness, build_manual_cancel_preview, build_manual_submit_preview, get_live_execution_attempt, list_live_execution_attempts, live_execution_attempts_to_csv, live_execution_control_alerts, live_execution_control_readiness_to_csv, record_manual_cancel_attempt, record_manual_submit_attempt
from .live_trading import autonomous_runs_to_csv, build_autonomous_run_preview, build_autonomous_status, build_live_order_board, build_live_reconciliation, build_live_trading_status, build_strategy_signal_board, get_autonomous_run, get_live_order_event, get_strategy_signal, list_autonomous_runs, list_live_order_events, list_strategy_signals, live_orders_to_csv, live_reconciliation_to_csv, live_trading_alerts, record_autonomous_run, record_strategy_signal, strategy_signals_to_csv, validate_strategy_signal_payload
from .live_clob_adapter import build_clob_adapter_status, clob_adapter_status_to_csv
from .live_v2 import (
    audit_to_csv as live_v2_audit_to_csv,
    audit_to_markdown as live_v2_audit_to_markdown,
    build_live_v2_demo_readiness,
    build_live_v2_preferences_schema,
    build_live_v2_readiness,
    build_live_v2_settings_sections,
    build_live_v2_status,
    build_live_v2_ticket_preview,
    build_live_v2_verification_report,
    cancel_live_v2_order,
    emergency_live_v2_action,
    get_live_v2_open_orders,
    get_live_v2_orderbook,
    get_live_v2_positions,
    filter_live_v2_audit_records,
    list_audit_records as list_live_v2_audit_records,
    reconcile_live_v2_orders,
    search_live_v2_markets,
    submit_live_v2_order,
    validate_live_v2_settings_payload,
    live_v2_verification_to_markdown,
)
from .live_research import (
    archive_source as research_archive_source,
    build_research_workspace,
    build_thesis_comparison as research_build_thesis_comparison,
    convert_candidate as research_convert_candidate,
    create_evidence_candidate as research_create_evidence_candidate,
    create_note as research_create_note,
    create_queue_item as research_create_queue_item,
    create_source as research_create_source,
    freshness_summary as research_freshness_summary,
    get_research_item,
    list_candidates as research_list_candidates,
    list_notes as research_list_notes,
    list_queue as research_list_queue,
    list_sources as research_list_sources,
    mark_source_reviewed as research_mark_source_reviewed,
    mark_source_stale as research_mark_source_stale,
    research_csv,
    research_export_json,
    research_export_markdown,
    update_queue_item as research_update_queue_item,
    update_source as research_update_source,
)
from .live_portfolio import (
    build_portfolio_workspace,
    create_exposure_group as portfolio_create_exposure_group,
    create_scenario as portfolio_create_scenario,
    evaluate_scenario as portfolio_evaluate_scenario,
    generate_portfolio_snapshot,
    get_bankroll_settings as portfolio_get_bankroll_settings,
    get_portfolio_item,
    list_exposure as portfolio_list_exposure,
    list_scenarios as portfolio_list_scenarios,
    list_warnings as portfolio_list_warnings,
    planned_trade_impact as portfolio_planned_trade_impact,
    portfolio_csv,
    portfolio_export_json,
    portfolio_export_markdown,
    update_bankroll as portfolio_update_bankroll,
    update_exposure_group as portfolio_update_exposure_group,
)
from .live_governance import (
    build_governance_workspace,
    create_checklist as governance_create_checklist,
    create_journal_entry as governance_create_journal_entry,
    create_mistake_pattern as governance_create_mistake_pattern,
    create_near_miss as governance_create_near_miss,
    create_review as governance_create_review,
    create_rule as governance_create_rule,
    get_governance_item,
    governance_csv,
    governance_export_json,
    governance_export_markdown,
    list_checklists as governance_list_checklists,
    list_journal as governance_list_journal,
    list_mistake_patterns as governance_list_mistake_patterns,
    list_near_misses as governance_list_near_misses,
    list_reviews as governance_list_reviews,
    list_rules as governance_list_rules,
    update_checklist as governance_update_checklist,
    update_journal_entry as governance_update_journal_entry,
    update_mistake_pattern as governance_update_mistake_pattern,
    update_review as governance_update_review,
    update_rule as governance_update_rule,
)
from .live_data import (
    build_data_workspace,
    checks_csv as data_checks_csv,
    create_backup_bundle as data_create_backup_bundle,
    export_bundle as data_export_bundle,
    health_report_json as data_health_report_json,
    health_report_markdown as data_health_report_markdown,
    import_apply as data_import_apply,
    import_preview as data_import_preview,
    list_backups as data_list_backups,
    migration_apply as data_migration_apply,
    migration_dry_run as data_migration_dry_run,
    migration_registry as data_migration_registry,
    recovery_report_json as data_recovery_report_json,
    recovery_report_markdown as data_recovery_report_markdown,
    restore_apply as data_restore_apply,
    restore_preview as data_restore_preview,
    run_health_check as data_run_health_check,
    runtime_inventory as data_runtime_inventory,
    scan_secrets as data_scan_secrets,
    validate_backup_bundle as data_validate_backup_bundle,
)
from .live_v3_analytics import (
    alert_usefulness_metrics as v3_analytics_alerts,
    analytics_context as v3_analytics_context,
    build_analytics_summary as v3_analytics_summary,
    confidence_calibration_metrics as v3_analytics_calibration,
    decision_quality_metrics as v3_analytics_decisions,
    evidence_usefulness_metrics as v3_analytics_evidence,
    export_analytics_json as v3_analytics_export_json,
    export_csv as v3_analytics_export_csv,
    export_learning_report_markdown as v3_analytics_export_markdown,
    generate_analytics_snapshot as v3_analytics_snapshot,
    generate_learning_report as v3_learning_report,
    governance_discipline_metrics as v3_analytics_governance,
    mistake_pattern_metrics as v3_analytics_mistakes,
    portfolio_risk_process_metrics as v3_analytics_portfolio,
    review_followthrough_metrics as v3_analytics_reviews,
    strength_pattern_metrics as v3_analytics_strengths,
    thesis_quality_metrics as v3_analytics_theses,
)

from .live_v3_simulation import (
    archive_session as v3_sim_archive_session,
    compare_then_now as v3_sim_compare_then_now,
    create_session as v3_sim_create_session,
    export_csv as v3_sim_export_csv,
    export_simulation_json as v3_sim_export_json,
    list_reports as v3_sim_list_reports,
    list_sessions as v3_sim_list_sessions,
    process_quality_backtest as v3_sim_process_backtest,
    reconstruct_historical_state as v3_sim_replay,
    run_session as v3_sim_run_session,
    simulate_alerts as v3_sim_alerts,
    simulate_governance as v3_sim_governance,
    simulate_no_trade as v3_sim_no_trade,
    simulate_portfolio as v3_sim_portfolio,
    simulate_pre_trade as v3_sim_pre_trade,
    simulate_thesis as v3_sim_thesis,
    simulation_report_markdown as v3_sim_export_markdown,
    simulation_summary as v3_sim_summary,
    update_session as v3_sim_update_session,
)

from .live_v3_datasets import (
    build_dataset_manifest as v3_datasets_build_manifest,
    build_dataset_settings as v3_datasets_build_settings,
    collect_snapshots as v3_datasets_collect_snapshots,
    create_demo_dataset_records as v3_datasets_create_demo_records,
    dataset_analytics_context as v3_datasets_analytics_context,
    dataset_quality_report as v3_datasets_quality_report,
    dataset_simulation_context as v3_datasets_simulation_context,
    datasets_summary as v3_datasets_summary,
    export_csv as v3_datasets_export_csv,
    export_dataset_json as v3_datasets_export_json,
    export_dataset_markdown as v3_datasets_export_markdown,
    get_collection_run as v3_datasets_get_run,
    get_dataset_manifest as v3_datasets_get_manifest,
    list_collection_runs as v3_datasets_list_runs,
    list_dataset_manifests as v3_datasets_list_manifests,
    list_provenance as v3_datasets_list_provenance,
    list_snapshots as v3_datasets_list_snapshots,
    replay_ready_datasets as v3_datasets_replay_ready,
    update_dataset_settings as v3_datasets_update_settings,
    validate_dataset_manifest as v3_datasets_validate_manifest,
    validate_snapshot as v3_datasets_validate_snapshot,
)


from .live_v3_freshness import (
    build_settings as v3_freshness_build_settings,
    cancel_collection_job as v3_freshness_cancel_job,
    create_collection_job as v3_freshness_create_job,
    create_demo_freshness_records as v3_freshness_create_demo_records,
    create_policy as v3_freshness_create_policy,
    export_csv as v3_freshness_export_csv,
    export_freshness_json as v3_freshness_export_json,
    export_freshness_markdown as v3_freshness_export_markdown,
    export_notifications_json as v3_freshness_export_notifications_json,
    freshness_scan as v3_freshness_scan,
    get_job as v3_freshness_get_job,
    list_findings as v3_freshness_list_findings,
    list_jobs as v3_freshness_list_jobs,
    list_notifications as v3_freshness_list_notifications,
    list_policies as v3_freshness_list_policies,
    list_readiness_reports as v3_freshness_list_readiness_reports,
    readiness_report as v3_freshness_readiness_report,
    run_collection_job as v3_freshness_run_job,
    summary as v3_freshness_summary,
    update_notification as v3_freshness_update_notification,
    update_policy as v3_freshness_update_policy,
    update_settings as v3_freshness_update_settings,
)

from .live_v3_tasks import (
    archive_inbox_item as v3_tasks_archive_inbox_item,
    archive_task as v3_tasks_archive_task,
    build_settings as v3_tasks_build_settings,
    build_task_context as v3_tasks_context,
    change_task_status as v3_tasks_change_status,
    complete_task as v3_tasks_complete_task,
    create_cadence_rule as v3_tasks_create_cadence_rule,
    create_task as v3_tasks_create_task,
    create_task_from_finding as v3_tasks_create_task_from_finding,
    create_task_from_inbox as v3_tasks_create_task_from_inbox,
    create_task_from_notification as v3_tasks_create_task_from_notification,
    create_task_template as v3_tasks_create_template,
    dismiss_inbox_item as v3_tasks_dismiss_inbox_item,
    export_csv as v3_tasks_export_csv,
    export_daily_ops_json as v3_tasks_export_daily_json,
    export_daily_ops_markdown as v3_tasks_export_daily_md,
    export_json as v3_tasks_export_json,
    export_markdown as v3_tasks_export_md,
    export_weekly_ops_json as v3_tasks_export_weekly_json,
    export_weekly_ops_markdown as v3_tasks_export_weekly_md,
    generate_daily_ops_packet as v3_tasks_daily_ops,
    generate_weekly_plan as v3_tasks_weekly_plan,
    get_task as v3_tasks_get_task,
    list_cadence_rules as v3_tasks_list_cadence,
    list_inbox as v3_tasks_list_inbox,
    list_task_templates as v3_tasks_list_templates,
    list_tasks as v3_tasks_list_tasks,
    run_cadence as v3_tasks_run_cadence,
    scan_inbox as v3_tasks_scan_inbox,
    snooze_inbox_item as v3_tasks_snooze_inbox_item,
    task_board as v3_tasks_board,
    task_context_for_subsystem as v3_tasks_context_for_subsystem,
    task_summary as v3_tasks_summary,
    today_view as v3_tasks_today,
    update_settings as v3_tasks_update_settings,
    update_task as v3_tasks_update_task,
    week_view as v3_tasks_week,
)


from . import live_v3_workspace as v3_workspace
from . import live_v3_cockpit as v3_cockpit
from .feature_status import build_feature_readiness_context, build_feature_status_map, build_stub_burndown_map, list_feature_readiness_acknowledgements, record_feature_readiness_acknowledgement
from . import platform_diagnostics as v4_platform
from . import platform_api as v4_platform_api
from . import platform_migrations as v4_platform_migrations
from . import platform_plugins as v4_platform_plugins
from . import platform_routes as v4_platform_routes
from . import platform_storage as v4_platform_storage
from . import platform_safety as v4_platform_safety
from . import ai_openai_client as v4_ai_openai
from . import ai_operator_copilot as v4_ai_copilot
from . import ai_prompt_governance as v4_ai_prompts
from . import ai_schemas as v4_ai_schemas
from . import ai_suggestions as v4_ai
from . import ai_providers as v4_ai_providers
from . import ai_local_llm_client as v4_ai_local_llm
from . import ai_model_recommendations as v4_ai_models
from . import ai_edge_research as v4_ai_edge
from . import ai_evidence as v4_ai_evidence
from . import ai_edge_calibration as v4_ai_edge_calibration
from . import ai_news_odds as v4_ai_news_odds
from . import ai_news_providers as v4_ai_news_providers
from . import cross_market_arbitrage as v4_arbitrage
from .routers import create_ai_router, create_platform_router, create_v3_core_router
from .navigation_registry import get_route_aliases, get_system_map, get_primary_entry_points, get_safety_explainer

from .live_v3 import (
    build_command_center as v3_build_command_center,
    build_decision_graph as v3_build_decision_graph,
    build_search_index as v3_build_search_index,
    build_v3_settings as v3_build_settings,
    clear_demo_data as v3_clear_demo_data,
    create_demo_data as v3_create_demo_data,
    data_health_backup_readiness_brief as v3_data_health_backup_readiness_brief,
    demo_status as v3_demo_status,
    export_operator_review_markdown as v3_export_operator_review_markdown,
    export_pre_trade_packet_markdown as v3_export_pre_trade_packet_markdown,
    export_report_json as v3_export_report_json,
    export_report_markdown as v3_export_report_markdown,
    filtered_decision_graph as v3_filtered_decision_graph,
    get_workflow_run as v3_get_workflow_run,
    graph_filters as v3_graph_filters,
    graph_to_markdown as v3_graph_to_markdown,
    list_workflow_runs as v3_list_workflow_runs,
    market_intelligence_brief as v3_market_intelligence_brief,
    missing_prerequisites_scan as v3_missing_prerequisites_scan,
    operator_review_packet as v3_operator_review_packet,
    portfolio_risk_brief as v3_portfolio_risk_brief,
    pre_trade_packet as v3_pre_trade_packet,
    rebuild_graph as v3_rebuild_graph,
    rebuild_search_index as v3_rebuild_search_index,
    run_workflow as v3_run_workflow,
    search_filters as v3_search_filters,
    search_local as v3_search_local,
    thesis_health_report as v3_thesis_health_report,
    update_v3_settings as v3_update_settings,
    validation_status as v3_validation_status,
    design_system_status as v3_design_system_status,
    navigation_groups as v3_navigation_groups,
    ux_release_status as v3_ux_release_status,
    workflow_outputs as v3_workflow_outputs,
    workflow_registry as v3_workflow_registry,
    workflow_templates as v3_workflow_templates,
)
from .live_monitoring import (
    acknowledge_alert as monitoring_acknowledge_alert,
    archive_rule as monitoring_archive_rule,
    build_monitoring_workspace,
    create_rule as monitoring_create_rule,
    disable_rule as monitoring_disable_rule,
    evaluate_all as monitoring_evaluate_all,
    evaluate_rule as monitoring_evaluate_rule,
    get_monitoring_item,
    list_alert_history as monitoring_list_history,
    list_alerts as monitoring_list_alerts,
    list_rules as monitoring_list_rules,
    monitoring_csv,
    monitoring_export_json,
    monitoring_export_markdown,
    snooze_alert as monitoring_snooze_alert,
    update_rule as monitoring_update_rule,
)
from .live_strategy import (
    archive_thesis as strategy_archive_thesis,
    build_strategy_workspace,
    build_ticket_from_thesis,
    create_evidence as strategy_create_evidence,
    create_review as strategy_create_review,
    create_scorecard as strategy_create_scorecard,
    create_thesis as strategy_create_thesis,
    create_watchlist_item as strategy_create_watchlist_item,
    get_strategy_item,
    list_evidence as strategy_list_evidence,
    list_reviews as strategy_list_reviews,
    list_scorecards as strategy_list_scorecards,
    list_theses as strategy_list_theses,
    list_watchlist as strategy_list_watchlist,
    strategy_csv,
    strategy_export_json,
    strategy_export_markdown,
    update_thesis as strategy_update_thesis,
)
from .live_ops import build_live_adapter_verification, build_live_readiness_checklist, build_operator_runbook, live_adapter_verification_to_csv, live_readiness_checklist_to_csv
from .market_data import build_execution_quality_board, build_execution_quality_simulation, build_market_data_board, execution_quality_to_csv, fetch_market_data_preview, get_execution_quality_simulation, get_market_snapshot, list_execution_quality_simulations, list_market_snapshots, market_data_alerts, market_snapshots_to_csv, parse_orderbook_metrics, record_execution_quality_simulation, record_market_snapshot, summarize_execution_quality, summarize_market_data
from .ui import build_ui_system_reference, build_workflow_map, compact_id, console_globals, status_tone

from .config_console import (
    CONFIG_CONFIRMATION_PHRASE,
    apply_preset,
    build_config_schema,
    config_presets,
    config_status,
    config_audit_history,
    export_sanitized_configuration,
    preview_config_diff,
    preset_diff,
    sanitized_env_template,
    save_config_changes,
    setup_runtime_status,
    settings_dashboard,
    validate_config_values,
)


from .internet_ops import (
    build_internet_data_status,
    build_internet_workflow,
    cancel_host_training_job,
    get_host_training_job,
    host_training_jobs_to_csv,
    internet_ingestion_jobs_to_csv,
    internet_schedules_to_csv,
    internet_sources_to_csv,
    list_host_training_jobs,
    list_internet_ingestion_jobs,
    list_internet_schedules,
    list_internet_sources,
    preview_due_internet_ingestion,
    preview_host_training_job,
    preview_internet_ingestion,
    register_internet_schedule,
    register_internet_source,
    run_internet_ingestion,
    start_host_training_job,
    validate_internet_source,
)

from .data_ingestion import (
    build_data_status,
    build_dataset_builder_status,
    build_training_dataset,
    data_sources_to_csv,
    dataset_builds_to_csv,
    generate_labels,
    get_dataset_manifest,
    get_raw_snapshot,
    ingestion_jobs_to_csv,
    labels_to_csv,
    list_data_audit,
    list_data_sources,
    list_dataset_builds,
    list_ingestion_jobs,
    list_labels,
    list_normalized_records,
    list_raw_snapshots,
    normalized_records_to_csv,
    preview_data_ingestion,
    preview_dataset_build,
    preview_labels,
    preview_normalization,
    raw_snapshots_to_csv,
    register_data_source,
    review_label,
    run_data_ingestion,
    run_normalization,
)

from .scoped_backfill import (
    backfills_to_csv,
    build_category_dataset,
    build_scoped_status,
    cancel_backfill,
    category_datasets_to_csv,
    data_scopes_to_csv,
    get_backfill,
    list_backfills,
    list_category_datasets,
    list_data_scopes,
    pause_backfill,
    preview_backfill,
    preview_category_dataset,
    preview_data_scope,
    register_data_scope,
    start_backfill,
)

from .training_lab import (
    backtests_to_csv,
    build_feature_set_preview,
    build_training_status,
    datasets_to_csv,
    feature_sets_to_csv,
    get_dataset,
    get_feature_set,
    list_backtests as list_training_backtests,
    list_datasets as list_training_datasets,
    list_feature_sets,
    list_models as list_training_models,
    list_training_audit,
    list_training_runs,
    models_to_csv,
    preview_backtest,
    preview_training_run,
    preview_training_signals,
    queue_training_signals,
    register_dataset,
    register_feature_set,
    register_model,
    run_backtest,
    start_training_run,
    training_runs_to_csv,
    validate_dataset_payload,
)

app = FastAPI(title="Polymarket OP Console", version=APP_VERSION_SHORT)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
templates.env.globals.update(console_globals())
templates.env.filters["status_tone"] = status_tone
templates.env.filters["compact_id"] = compact_id
client = GammaClient()
clob = ClobClient()


def _score_market_rows(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score market rows and attach explicit v4.6 YES/NO/HOLD edge recommendations."""
    return enrich_markets_with_recommendations(attach_probability(attach_scores(markets)))


async def _review_market_rows(limit: int = 100, *, demo: bool = False) -> list[dict[str, Any]]:
    """Load markets for review pages with a deterministic fixture fallback.

    The fallback keeps route/template smoke tests and offline visual QA safe. It is
    explicitly labelled demo_fixture and never represented as live market data.
    """
    if demo:
        return opportunity_demo_markets()[:limit]
    try:
        raw = await client.list_markets(limit=limit, order="volume24hr")
        if not raw:
            raise RuntimeError("empty public market response")
        scored = _score_market_rows(raw)
        return attach_evidence_probability(scored)
    except Exception:
        return opportunity_demo_markets()[:limit]


async def _review_market_by_id(market_id_or_slug: str) -> dict[str, Any] | None:
    safe_id = str(market_id_or_slug or "")
    for demo_market in opportunity_demo_markets():
        identifiers = {
            str(demo_market.get("id") or ""),
            str(demo_market.get("market_id") or ""),
            str(demo_market.get("slug") or ""),
        }
        if safe_id in identifiers:
            return demo_market
    try:
        market = await client.get_market(safe_id)
        if market:
            return _score_market_rows([market])[0]
    except Exception:
        pass
    markets = await _review_market_rows(limit=200)
    for market in markets:
        identifiers = {str(market.get("id") or ""), str(market.get("market_id") or ""), str(market.get("slug") or "")}
        if safe_id in identifiers:
            return market
    return None


PUBLIC_PATHS = {"/login", "/setup", "/logout", "/health"}


def current_user(request: Request) -> dict | None:
    username = request.session.get("username")
    if not username:
        return None
    user = get_user(username)
    if not user or user.get("status") != "active":
        request.session.clear()
        return None
    return {k: v for k, v in user.items() if k != "password_hash"}


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _safe_return_path(value: str | None, fallback: str = "/") -> str:
    path = str(value or "").strip()
    if not path or "://" in path or path.startswith("//") or not path.startswith("/"):
        return fallback
    return path


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/static") or path in PUBLIC_PATHS:
        return await call_next(request)
    if not users_exist():
        if path.startswith("/api"):
            return JSONResponse({"detail": "Initial admin setup required", "setup_url": "/setup"}, status_code=403)
        return RedirectResponse(url="/setup", status_code=303)
    if current_user(request) is None:
        if path.startswith("/api"):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return RedirectResponse(url=f"/login?next={path}", status_code=303)
    return await call_next(request)


app.add_middleware(SessionMiddleware, secret_key=get_session_secret(), same_site=settings.session_cookie_same_site, https_only=settings.session_cookie_secure)
app.middleware("http")(security_headers_middleware)
app.middleware("http")(host_guard_middleware)


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if users_exist():
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("setup.html", {"request": request, "error": None})


@app.post("/setup")
async def setup_submit(request: Request, password: str = Form(...), confirm_password: str = Form(...)):
    if users_exist():
        return RedirectResponse(url="/login", status_code=303)
    if password != confirm_password:
        return templates.TemplateResponse("setup.html", {"request": request, "error": "Passwords do not match."}, status_code=400)
    try:
        user = setup_initial_admin(password)
    except ValueError as exc:
        return templates.TemplateResponse("setup.html", {"request": request, "error": str(exc)}, status_code=400)
    request.session["username"] = user["username"]
    return RedirectResponse(url="/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = Query(default="/")):
    if not users_exist():
        return RedirectResponse(url="/setup", status_code=303)
    if current_user(request):
        return RedirectResponse(url=next or "/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "next": next})


@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form(default="/")):
    user = authenticate(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username/password or suspended account.", "next": next}, status_code=401)
    request.session["username"] = user["username"]
    return RedirectResponse(url=next or "/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: dict = Depends(require_admin), error: str = Query(default="")):
    return templates.TemplateResponse("users.html", {"request": request, "user": user, "users": list_users_public(), "error": error})


@app.post("/users/create")
async def users_create(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form(default="read_only"), user: dict = Depends(require_admin)):
    try:
        create_user(username, password, role=role, created_by=user["username"])
    except ValueError as exc:
        return RedirectResponse(url=f"/users?error={str(exc)}", status_code=303)
    return RedirectResponse(url="/users", status_code=303)


@app.post("/users/update/{username}")
async def users_update(username: str, role: str = Form(default="read_only"), status: str = Form(default="active"), password: str = Form(default=""), user: dict = Depends(require_admin)):
    try:
        update_user(username, role=role, status=status, password=password or None)
    except ValueError as exc:
        return RedirectResponse(url=f"/users?error={str(exc)}", status_code=303)
    return RedirectResponse(url="/users", status_code=303)


@app.post("/users/delete/{username}")
async def users_delete(username: str, user: dict = Depends(require_admin)):
    try:
        delete_user(username, acting_username=user["username"])
    except ValueError as exc:
        return RedirectResponse(url=f"/users?error={str(exc)}", status_code=303)
    return RedirectResponse(url="/users", status_code=303)


@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(require_user)):
    return {"authenticated": True, "user": user}


@app.get("/api/users")
async def users_api(user: dict = Depends(require_admin)):
    return {"items": list_users_public()}


@app.get("/workflow", response_class=HTMLResponse)
async def workflow_page(request: Request, user: dict = Depends(require_user)):
    workflow = build_workflow_map()
    return templates.TemplateResponse("workflow_v080.html", {"request": request, "user": user, **workflow})


@app.get("/api/ui/workflow")
async def workflow_api(user: dict = Depends(require_user)):
    return {"source": "local", **build_workflow_map()}


@app.get("/ui-system", response_class=HTMLResponse)
async def ui_system_page(request: Request, user: dict = Depends(require_user)):
    reference = build_ui_system_reference()
    return templates.TemplateResponse("ui_system_v080.html", {"request": request, "user": user, **reference})


@app.post("/api/users")
async def users_create_api(username: str = Query(...), password: str = Query(...), role: str = Query(default="read_only"), user: dict = Depends(require_admin)):
    try:
        item = create_user(username, password, role=role, created_by=user["username"])
        return {"ok": True, "item": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/users/{username}")
async def users_update_api(username: str, role: str | None = Query(default=None), status: str | None = Query(default=None), password: str | None = Query(default=None), user: dict = Depends(require_admin)):
    try:
        item = update_user(username, role=role, status=status, password=password)
        return {"ok": True, "item": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/users/{username}")
async def users_delete_api(username: str, user: dict = Depends(require_admin)):
    try:
        return {"ok": delete_user(username, acting_username=user["username"])}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc




@app.get("/administration/maintenance", response_class=HTMLResponse)
async def administration_maintenance(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("administration_maintenance.html", {"request": request, "user": user, "maintenance": maintenance_status()})


@app.post("/administration/maintenance/backups/create")
async def administration_create_backup(label: str = Form(default="manual"), user: dict = Depends(require_admin)):
    create_backup(label=label)
    return RedirectResponse(url="/administration/maintenance", status_code=303)


@app.post("/administration/maintenance/backups/delete/{filename}")
async def administration_delete_backup(filename: str, user: dict = Depends(require_admin)):
    try:
        delete_backup(filename)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(url="/administration/maintenance", status_code=303)


@app.get("/api/maintenance/status")
async def maintenance_status_api(user: dict = Depends(require_admin)):
    return maintenance_status()


@app.post("/api/maintenance/backups")
async def maintenance_create_backup_api(label: str = Query(default="manual"), user: dict = Depends(require_admin)):
    return {"ok": True, "backup": create_backup(label=label)}


@app.get("/api/maintenance/backups/{filename}/download")
async def maintenance_download_backup(filename: str, user: dict = Depends(require_admin)):
    try:
        path = get_backup_path(filename)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, filename=path.name, media_type="application/zip")


@app.delete("/api/maintenance/backups/{filename}")
async def maintenance_delete_backup_api(filename: str, user: dict = Depends(require_admin)):
    try:
        return {"ok": delete_backup(filename)}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/administration/config", response_class=HTMLResponse)
async def administration_config(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("administration_config.html", {"request": request, "user": user, "deployment": deployment_status()})




# v1.9.0 streamlined settings and configuration UX refresh.
def _config_changes_from_form(form) -> dict[str, object]:
    schema_keys = {option.key: option for option in build_config_schema()}
    changes: dict[str, object] = {}
    for key, option in schema_keys.items():
        form_key = f"cfg__{key}"
        if option.control == "multi_select":
            if form_key in form:
                changes[key] = form.getlist(form_key)
            continue
        if form_key in form:
            value = form.get(form_key)
            if option.secret and not str(value or "").strip():
                continue
            changes[key] = value
    return changes



@app.get("/settings", response_class=HTMLResponse)
async def settings_landing_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse(
        "settings_dashboard_v190.html",
        {"request": request, "user": user, "dashboard": settings_dashboard()},
    )

@app.get("/settings/configuration", response_class=HTMLResponse)
async def settings_configuration_page(request: Request, focus: str = Query(default=""), user: dict = Depends(require_admin)):
    return templates.TemplateResponse(
        "configuration_console_v190.html",
        {
            "request": request,
            "user": user,
            "status": config_status(),
            "presets": config_presets(),
            "setup_status": setup_runtime_status(),
            "focus": focus,
            "confirmation_phrase": CONFIG_CONFIRMATION_PHRASE,
            "diff_result": None,
            "save_result": None,
        },
    )


@app.get("/setup/environment", response_class=HTMLResponse)
async def setup_environment_page(request: Request, user: dict = Depends(require_admin)):
    return await settings_configuration_page(request, focus="", user=user)


@app.get("/setup/status", response_class=HTMLResponse)
async def setup_status_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse(
        "setup_status_v190.html",
        {"request": request, "user": user, "setup_status": setup_runtime_status(), "status": config_status()},
    )


@app.get("/setup/wizard", response_class=HTMLResponse)
async def setup_wizard_page(request: Request, preset_id: str = Query(default=""), user: dict = Depends(require_admin)):
    selected = preset_id or "locked_down_safe_mode"
    return templates.TemplateResponse(
        "setup_wizard_v190.html",
        {
            "request": request,
            "user": user,
            "presets": config_presets(),
            "selected_preset_id": selected,
            "diff_result": preset_diff(selected) if selected else None,
            "save_result": None,
            "confirmation_phrase": CONFIG_CONFIRMATION_PHRASE,
        },
    )


@app.post("/settings/configuration")
async def settings_configuration_submit(request: Request, user: dict = Depends(require_admin)):
    form = await request.form()
    changes = _config_changes_from_form(form)
    confirmation = str(form.get("confirmation", ""))
    intent = str(form.get("intent", "preview"))
    diff_result = preview_config_diff(changes, confirmation=confirmation)
    save_result = None
    if intent == "save":
        save_result = save_config_changes(changes, confirmation=confirmation, requested_by=user.get("username", "local"))
        diff_result = save_result
    return templates.TemplateResponse(
        "configuration_console_v190.html",
        {
            "request": request,
            "user": user,
            "status": config_status(),
            "presets": config_presets(),
            "setup_status": setup_runtime_status(),
            "focus": "",
            "confirmation_phrase": CONFIG_CONFIRMATION_PHRASE,
            "diff_result": diff_result,
            "save_result": save_result,
        },
    )


@app.post("/setup/wizard")
async def setup_wizard_submit(request: Request, user: dict = Depends(require_admin)):
    form = await request.form()
    preset_id = str(form.get("preset_id", ""))
    confirmation = str(form.get("confirmation", ""))
    intent = str(form.get("intent", "preview"))
    diff_result = preset_diff(preset_id, confirmation=confirmation)
    save_result = None
    if intent == "apply":
        save_result = apply_preset(preset_id, confirmation=confirmation, requested_by=user.get("username", "local"))
        diff_result = save_result
    return templates.TemplateResponse(
        "setup_wizard_v190.html",
        {
            "request": request,
            "user": user,
            "presets": config_presets(),
            "selected_preset_id": preset_id,
            "diff_result": diff_result,
            "save_result": save_result,
            "confirmation_phrase": CONFIG_CONFIRMATION_PHRASE,
        },
    )


@app.get("/api/config/schema")
async def config_schema_api(user: dict = Depends(require_admin)):
    return {"source": "local", "app_version": APP_VERSION, "items": [option.__dict__ for option in build_config_schema()]}


@app.get("/api/config/status")
async def config_status_api(user: dict = Depends(require_admin)):
    return config_status()


@app.post("/api/config/validate")
async def config_validate_api(payload: dict[str, Any] = Body(default_factory=dict), user: dict = Depends(require_admin)):
    changes = payload.get("changes", payload) if isinstance(payload, dict) else {}
    confirmation = payload.get("confirmation", "") if isinstance(payload, dict) else ""
    return validate_config_values(changes, confirmation=confirmation)


@app.post("/api/config/diff")
async def config_diff_api(payload: dict[str, Any] = Body(default_factory=dict), user: dict = Depends(require_admin)):
    changes = payload.get("changes", payload) if isinstance(payload, dict) else {}
    confirmation = payload.get("confirmation", "") if isinstance(payload, dict) else ""
    return preview_config_diff(changes, confirmation=confirmation)


@app.post("/api/config/save")
async def config_save_api(payload: dict[str, Any] = Body(default_factory=dict), user: dict = Depends(require_admin)):
    changes = payload.get("changes", payload) if isinstance(payload, dict) else {}
    confirmation = payload.get("confirmation", "") if isinstance(payload, dict) else ""
    return save_config_changes(changes, confirmation=confirmation, requested_by=user.get("username", "local"))


@app.get("/api/config/export-sanitized")
async def config_export_sanitized_api(user: dict = Depends(require_admin)):
    return export_sanitized_configuration()

@app.get("/api/config/audit-history")
async def config_audit_history_api(limit: int = Query(default=20), user: dict = Depends(require_admin)):
    return config_audit_history(limit=limit)


@app.get("/api/config/export-sanitized.env", response_class=PlainTextResponse)
async def config_export_sanitized_env_api(user: dict = Depends(require_admin)):
    return PlainTextResponse(sanitized_env_template(), media_type="text/plain", headers={"Content-Disposition": "attachment; filename=polymarket_gamma_sanitized.env"})


@app.get("/api/config/presets")
async def config_presets_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": config_presets()}


@app.post("/api/config/presets/{preset_id}/preview")
async def config_preset_preview_api(preset_id: str, payload: dict[str, Any] = Body(default_factory=dict), user: dict = Depends(require_admin)):
    return preset_diff(preset_id, confirmation=payload.get("confirmation", "") if isinstance(payload, dict) else "")


@app.post("/api/config/presets/{preset_id}/apply")
async def config_preset_apply_api(preset_id: str, payload: dict[str, Any] = Body(default_factory=dict), user: dict = Depends(require_admin)):
    return apply_preset(preset_id, confirmation=payload.get("confirmation", "") if isinstance(payload, dict) else "", requested_by=user.get("username", "local"))


@app.get("/api/setup/status")
async def setup_runtime_status_api(user: dict = Depends(require_admin)):
    return setup_runtime_status()


@app.get("/api/deployment/status")
async def deployment_status_api(user: dict = Depends(require_admin)):
    return deployment_status()


@app.get("/api/live/config/readiness")
async def live_config_readiness_api(user: dict = Depends(require_admin)):
    return build_live_config_readiness()


@app.get("/api/live/config/readiness.csv")
async def live_config_readiness_csv(user: dict = Depends(require_admin)):
    report = build_live_config_readiness()
    return PlainTextResponse(
        live_config_readiness_to_csv(report),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_config_readiness.csv"},
    )


@app.get("/api/live/config/template.env")
async def live_config_template_api(user: dict = Depends(require_admin)):
    return PlainTextResponse(
        live_config_template(),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=live_config_template.env"},
    )




@app.get("/api/live/dry-run-adapter")
async def live_dry_run_adapter_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_live_dry_run_board(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id),
    }


@app.get("/api/live/dry-run-adapter.csv", response_class=PlainTextResponse)
async def live_dry_run_adapter_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_dry_run_receipts(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    return PlainTextResponse(
        live_dry_run_receipts_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_dry_run_adapter_receipts.csv"},
    )


@app.get("/api/live/dry-run-adapter/{receipt_id}")
async def live_dry_run_adapter_detail_api(receipt_id: str, user: dict = Depends(require_admin)):
    item = get_live_dry_run_receipt(receipt_id)
    if not item:
        raise HTTPException(status_code=404, detail="Live dry-run adapter receipt not found")
    return {"source": "local", "item": item}


@app.get("/api/live/dry-run-review")
async def live_dry_run_review_api(
    limit: int = Query(default=100, ge=1, le=1000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_live_dry_run_review_board(limit=limit, state=state, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id),
    }


@app.get("/api/live/dry-run-review.csv", response_class=PlainTextResponse)
async def live_dry_run_review_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_dry_run_reviews(limit=limit, state=state, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    return PlainTextResponse(
        live_dry_run_reviews_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_dry_run_review.csv"},
    )


@app.get("/api/live/dry-run-review/{packet_id}")
async def live_dry_run_review_detail_api(packet_id: str, user: dict = Depends(require_admin)):
    item = review_live_dry_run_packet(packet_id)
    if not item:
        raise HTTPException(status_code=404, detail="Live dry-run review packet not found")
    return {"source": "local", "item": item}


@app.post("/api/live/execution-packets/{packet_id}/dry-run/preview")
async def live_dry_run_adapter_preview_api(
    packet_id: str,
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = build_live_dry_run_receipt(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note)
    return {"ok": True, "recorded": False, "item": item}


@app.post("/api/live/execution-packets/{packet_id}/dry-run")
async def live_dry_run_adapter_create_api(
    packet_id: str,
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_dry_run_receipt(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note)
    return {"ok": True, "recorded": True, "item": item}


@app.get("/api/live/adapter/readiness")
async def live_adapter_readiness_api(user: dict = Depends(require_admin)):
    return build_live_adapter_readiness()


@app.get("/api/live/adapter/readiness.csv", response_class=PlainTextResponse)
async def live_adapter_readiness_csv(user: dict = Depends(require_admin)):
    report = build_live_adapter_readiness()
    return PlainTextResponse(
        live_adapter_readiness_to_csv(report),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_adapter_readiness.csv"},
    )


@app.get("/api/live/adapter/readonly-validations")
async def live_adapter_readonly_validations_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_adapter_readonly_validations(limit=limit, status=status, operator=operator)
    return {"source": "local", "mode": "live_adapter_readonly_validation_v060", "items": rows}


@app.get("/api/live/adapter/readonly-validations.csv", response_class=PlainTextResponse)
async def live_adapter_readonly_validations_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_adapter_readonly_validations(limit=limit, status=status, operator=operator)
    return PlainTextResponse(
        live_adapter_validations_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_adapter_readonly_validations.csv"},
    )


@app.get("/api/live/adapter/readonly-validations/{validation_id}")
async def live_adapter_readonly_validation_detail_api(validation_id: str, user: dict = Depends(require_admin)):
    item = get_live_adapter_readonly_validation(validation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Live adapter read-only validation not found")
    return {"source": "local", "item": item}


@app.post("/api/live/adapter/readonly-validation/preview")
async def live_adapter_readonly_validation_preview_api(
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = preview_live_adapter_readonly_validation(operator=operator or user.get("username", "local"), note=note)
    return {"ok": True, "recorded": False, "item": item}


@app.post("/api/live/adapter/readonly-validation")
async def live_adapter_readonly_validation_create_api(
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_adapter_readonly_validation(operator=operator or user.get("username", "local"), note=note)
    return {"ok": True, "recorded": True, "item": item}


@app.get("/api/live/adapter/requests")
async def live_adapter_requests_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_live_adapter_request_board(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id),
    }


@app.get("/api/live/adapter/requests.csv", response_class=PlainTextResponse)
async def live_adapter_requests_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_adapter_requests(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    return PlainTextResponse(
        live_adapter_requests_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_adapter_requests.csv"},
    )


@app.get("/api/live/adapter/requests/{request_or_packet_id}")
async def live_adapter_request_detail_api(request_or_packet_id: str, user: dict = Depends(require_admin)):
    item = get_live_adapter_request(request_or_packet_id)
    if not item:
        packet = get_live_execution_packet(request_or_packet_id)
        if not packet:
            raise HTTPException(status_code=404, detail="Live adapter request or execution packet not found")
        item = build_live_adapter_request(packet_id=request_or_packet_id, operator=user.get("username", "local"))
    return {"source": "local", "item": item}


@app.post("/api/live/execution-packets/{packet_id}/adapter-request/preview")
async def live_adapter_request_preview_api(
    packet_id: str,
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = build_live_adapter_request(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note)
    return {"ok": True, "recorded": False, "item": item}


@app.post("/api/live/execution-packets/{packet_id}/adapter-request")
async def live_adapter_request_create_api(
    packet_id: str,
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_adapter_request(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note)
    return {"ok": True, "recorded": True, "item": item}


@app.get("/api/live/manual-execution-reviews")
async def manual_execution_reviews_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_manual_execution_review_board(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id),
    }


@app.get("/api/live/manual-execution-reviews.csv", response_class=PlainTextResponse)
async def manual_execution_reviews_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_manual_execution_reviews(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id)
    return PlainTextResponse(
        manual_execution_reviews_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=manual_execution_reviews.csv"},
    )


@app.get("/api/live/manual-execution-reviews/{review_id}")
async def manual_execution_review_detail_api(review_id: str, user: dict = Depends(require_admin)):
    item = get_manual_execution_review(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Manual execution review not found")
    return {"source": "local", "item": item}


@app.post("/api/live/execution-packets/{packet_id}/manual-execution-review/preview")
async def manual_execution_review_preview_api(
    packet_id: str,
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    acknowledged: bool = Query(default=False),
    user: dict = Depends(require_admin),
):
    item = build_manual_execution_review(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note, acknowledged=acknowledged)
    return {"ok": True, "recorded": False, "item": item}


@app.post("/api/live/execution-packets/{packet_id}/manual-execution-review")
async def manual_execution_review_create_api(
    packet_id: str,
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    acknowledged: bool = Query(default=False),
    user: dict = Depends(require_admin),
):
    item = record_manual_execution_review(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note, acknowledged=acknowledged)
    return {"ok": True, "recorded": True, "item": item}


@app.get("/api/live/execution-control/readiness")
async def live_execution_control_readiness_api(user: dict = Depends(require_admin)):
    return build_live_execution_control_readiness()


@app.get("/api/live/execution-control/readiness.csv", response_class=PlainTextResponse)
async def live_execution_control_readiness_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(
        live_execution_control_readiness_to_csv(build_live_execution_control_readiness()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_execution_control_readiness.csv"},
    )


@app.get("/api/live/execution-attempts")
async def live_execution_attempts_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    adapter_mode: str | None = Query(default=None),
    action: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    adapter_request_id: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_live_execution_attempt_board(
            limit=limit,
            status=status,
            adapter_mode=adapter_mode,
            action=action,
            market_id=market_id,
            operator=operator,
            adapter_request_id=adapter_request_id,
            packet_id=packet_id,
            intent_id=intent_id,
        ),
    }


@app.get("/api/live/execution-attempts.csv", response_class=PlainTextResponse)
async def live_execution_attempts_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    adapter_mode: str | None = Query(default=None),
    action: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    adapter_request_id: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_execution_attempts(
        limit=limit,
        status=status,
        adapter_mode=adapter_mode,
        action=action,
        market_id=market_id,
        operator=operator,
        adapter_request_id=adapter_request_id,
        packet_id=packet_id,
        intent_id=intent_id,
    )
    return PlainTextResponse(
        live_execution_attempts_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_execution_attempts.csv"},
    )


@app.get("/api/live/execution-attempts/{attempt_id}")
async def live_execution_attempt_detail_api(attempt_id: str, user: dict = Depends(require_admin)):
    item = get_live_execution_attempt(attempt_id)
    if not item:
        raise HTTPException(status_code=404, detail="Live execution attempt not found")
    return {"source": "local", "item": item}


@app.post("/api/live/adapter/requests/{adapter_request_id}/manual-submit/preview")
async def live_manual_submit_preview_api(
    adapter_request_id: str,
    operator: str = Form(default="local"),
    final_confirmation: str = Form(default=""),
    adapter_mode: str = Form(default="blocked"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = build_manual_submit_preview(
        adapter_request_id=adapter_request_id,
        operator=operator or user.get("username", "local"),
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        note=note,
    )
    return {"ok": True, "recorded": False, "item": item}


@app.post("/api/live/adapter/requests/{adapter_request_id}/manual-submit")
async def live_manual_submit_create_api(
    adapter_request_id: str,
    operator: str = Form(default="local"),
    final_confirmation: str = Form(default=""),
    adapter_mode: str = Form(default="blocked"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_manual_submit_attempt(
        adapter_request_id=adapter_request_id,
        operator=operator or user.get("username", "local"),
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        note=note,
    )
    return {"ok": True, "recorded": True, "item": item}


@app.post("/api/live/manual-cancel/preview")
async def live_manual_cancel_preview_api(
    original_attempt_id: str = Form(default=""),
    fake_order_id: str = Form(default=""),
    operator: str = Form(default="local"),
    final_confirmation: str = Form(default=""),
    adapter_mode: str = Form(default="blocked"),
    reason: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = build_manual_cancel_preview(
        original_attempt_id=original_attempt_id,
        fake_order_id=fake_order_id,
        operator=operator or user.get("username", "local"),
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        reason=reason,
        note=note,
    )
    return {"ok": True, "recorded": False, "item": item}


@app.post("/api/live/manual-cancel")
async def live_manual_cancel_create_api(
    original_attempt_id: str = Form(default=""),
    fake_order_id: str = Form(default=""),
    operator: str = Form(default="local"),
    final_confirmation: str = Form(default=""),
    adapter_mode: str = Form(default="blocked"),
    reason: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_manual_cancel_attempt(
        original_attempt_id=original_attempt_id,
        fake_order_id=fake_order_id,
        operator=operator or user.get("username", "local"),
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        reason=reason,
        note=note,
    )
    return {"ok": True, "recorded": True, "item": item}





def _live_v2_template_context(request: Request, section: str, audit_limit: int = 25) -> dict[str, Any]:
    status = build_live_v2_status()
    return {
        "request": request,
        "section": section,
        "status": status,
        "ui": status.get("ui", {}),
        "audit_rows": list_live_v2_audit_records(limit=audit_limit),
        "settings_sections": build_live_v2_settings_sections(),
        "strategy": build_strategy_workspace(limit=50),
        "research": build_research_workspace(limit=50),
        "monitoring": build_monitoring_workspace(limit=50),
        "portfolio": build_portfolio_workspace(limit=50),
        "governance": build_governance_workspace(limit=50),
        "data_layer": build_data_workspace(limit=50),
        "user": current_user(request),
    }


@app.get("/v2-live", response_class=HTMLResponse)
async def live_v2_console(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "dashboard", 25))


@app.get("/v2-live/readiness", response_class=HTMLResponse)
async def live_v2_readiness_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "readiness", 25))


@app.get("/v2-live/markets", response_class=HTMLResponse)
@app.get("/v2-live/market-data", response_class=HTMLResponse)
async def live_v2_market_data_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "market_data", 25))


@app.get("/v2-live/trade-ticket", response_class=HTMLResponse)
async def live_v2_trade_ticket_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "trade_ticket", 25))


@app.get("/v2-live/orders", response_class=HTMLResponse)
async def live_v2_orders_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "orders", 100))


@app.get("/v2-live/positions", response_class=HTMLResponse)
async def live_v2_positions_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "positions", 25))


@app.get("/v2-live/risk", response_class=HTMLResponse)
async def live_v2_risk_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "risk", 25))


@app.get("/v2-live/audit", response_class=HTMLResponse)
async def live_v2_audit_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "audit", 200))


@app.get("/v2-live/settings", response_class=HTMLResponse)
async def live_v2_settings_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "settings", 25))


@app.get("/v2-live/emergency", response_class=HTMLResponse)
async def live_v2_emergency_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "emergency", 25))


@app.get("/v2-live/docs", response_class=HTMLResponse)
async def live_v2_docs_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "docs", 25))


@app.get("/v2-live/verify", response_class=HTMLResponse)
async def live_v2_verify_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "verify", 25))


@app.get("/v2-live/strategy", response_class=HTMLResponse)
async def live_v2_strategy_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "strategy", 50))


@app.get("/v2-live/research", response_class=HTMLResponse)
async def live_v2_research_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "research", 50))


@app.get("/v2-live/monitoring", response_class=HTMLResponse)
async def live_v2_monitoring_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "monitoring", 50))


@app.get("/v2-live/portfolio", response_class=HTMLResponse)
async def live_v2_portfolio_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "portfolio", 50))


@app.get("/v2-live/governance", response_class=HTMLResponse)
async def live_v2_governance_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "governance", 50))


@app.get("/v2-live/data", response_class=HTMLResponse)
async def live_v2_data_page(request: Request):
    return templates.TemplateResponse("live_v2_dashboard.html", _live_v2_template_context(request, "data", 50))




def _v3_template_context(request: Request, section: str) -> dict[str, Any]:
    # Keep v3 page loads fast by only building heavy graph/search/analytics objects
    # when the active page needs them. Deep scans remain operator-triggered.
    base: dict[str, Any] = {
        "request": request,
        "section": section,
        "command_center": v3_build_command_center(),
        "search_index": {"count": 0, "items": []},
        "search_filters": {"object_types": [], "statuses": [], "tags": []},
        "graph": {"node_count": 0, "edge_count": 0, "nodes": [], "edges": []},
        "graph_filters": {"node_types": [], "relationship_types": [], "statuses": []},
        "workflows": {"workflows": []},
        "workflow_templates": {"templates": []},
        "workflow_outputs": {"items": []},
        "recent_runs": {"items": []},
        "missing_prerequisites": {"findings": []},
        "demo_status": v3_demo_status(),
        "validation_status": {"overall_status": "not_loaded"},
        "ux_status": v3_ux_release_status(),
        "design_system": v3_design_system_status(),
        "navigation_groups": v3_navigation_groups(),
        "settings": {},
        "analytics_summary": v3_analytics_summary() if section in {"command_center", "analytics"} else {},
        "analytics_snapshot": v3_analytics_snapshot(write=False) if section == "analytics" else {},
        "learning_report": v3_learning_report(write=False) if section == "analytics" else {},
        "simulation_summary": v3_sim_summary() if section in {"command_center", "simulation"} else {},
        "simulation_sessions": {"items": [], "count": 0},
        "simulation_reports": {"items": [], "count": 0},
        "simulation_process_backtest": {},
        "simulation_replay": {},
        "simulation_pre_trade": {},
        "simulation_no_trade": {},
        "datasets_summary": v3_datasets_summary() if section in {"command_center", "datasets", "simulation", "analytics", "freshness"} else {},
        "freshness_summary": v3_freshness_summary() if section in {"command_center", "freshness", "datasets", "simulation", "analytics", "tasks"} else {},
        "tasks_summary": v3_tasks_summary() if section in {"command_center", "tasks", "freshness", "datasets", "simulation", "analytics", "workflows"} else {},
        "task_context": {},
        "task_list": {"items": [], "count": 0},
        "task_inbox": {"items": [], "count": 0},
        "task_board": {"columns": [], "total_count": 0},
        "task_today": {},
        "task_week": {},
        "task_cadence": {"items": [], "count": 0},
        "task_templates": {"items": [], "count": 0},
        "task_settings": {},
        "workspace_summary": v3_workspace.workspace_summary() if section in {"command_center", "workspace", "tasks", "search", "graph", "workflows"} else {},
        "workspace_context": {},
        "workspace_flows": {"items": [], "count": 0},
        "workspace_sessions": {"items": [], "count": 0},
        "workspace_dependencies": {"items": [], "count": 0},
        "workspace_blocked_review": {},
        "workspace_source_previews": {"items": [], "count": 0},
        "workspace_saved_views": {"items": [], "count": 0},
        "workspace_review_packets": {"items": [], "count": 0},
        "workspace_settings": {},
        "cockpit_summary": v3_cockpit.cockpit_summary() if section in {"command_center", "cockpit", "tasks", "workspace", "search", "graph", "workflows"} else {},
        "cockpit_context": {},
        "cockpit_layouts": {"items": [], "count": 0},
        "cockpit_selected_layout": {},
        "cockpit_panels": {"items": [], "count": 0},
        "cockpit_focus_modes": {"items": [], "count": 0},
        "cockpit_shortcuts": {"items": [], "count": 0},
        "cockpit_command_palette": {"items": [], "count": 0},
        "cockpit_dependency_view": {},
        "cockpit_source_context": {"items": [], "count": 0},
        "cockpit_review_packets": {"items": [], "count": 0},
        "cockpit_settings": {},
        "feature_status": build_feature_status_map() if section in {"command_center", "cockpit", "platform", "settings"} else {"items": [], "count": 0, "counts": {}},
        "platform_summary": v4_platform.platform_summary(app) if section in {"command_center", "platform", "search", "graph", "workflows"} else {},
        "platform_context": {},
        "platform_health": {},
        "platform_routes": {"items": [], "count": 0, "families": {}},
        "platform_plugins": {"items": [], "count": 0},
        "platform_storage": {"items": [], "count": 0},
        "platform_api_schema": {"items": [], "summary": {}},
        "platform_response_envelopes": {"items": [], "summary": {}},
        "platform_migrations": {},
        "platform_migration_plan": {"steps": [], "runtime_namespaces": []},
        "platform_storage_map": {"items": [], "count": 0},
        "platform_diagnostics": {},
        "platform_safety": {},
        "platform_settings": {},
        "ai_summary": {},
        "ai_settings": {},
        "ai_providers": {"items": [], "count": 0},
        "ai_provider_health": {"items": [], "count": 0},
        "ai_local_llm": {},
        "ai_model_recommendations": {"items": [], "count": 0},
        "ai_prompts": {"items": [], "count": 0},
        "ai_schemas": {"items": [], "count": 0},
        "ai_suggestions": {"items": [], "count": 0},
        "ai_audit": {"items": [], "count": 0},
        "ai_review_packets": {"items": [], "count": 0},
        "ai_chatgpt_connector": {},
        "ai_redaction_preview": {},
        "ai_copilot_status": {},
        "ai_edge_summary": {},
        "ai_edge_settings": {},
        "ai_edge_packets": {"items": [], "count": 0},
        "ai_edge_evidence": {"items": [], "count": 0},
        "ai_edge_calibration": {"items": [], "count": 0},
        "ai_edge_calibration_summary": {},
        "ai_edge_schemas": {"items": [], "count": 0},
        "dataset_snapshots": {"items": [], "count": 0},
        "dataset_runs": {"items": [], "count": 0},
        "dataset_manifests": {"items": [], "count": 0},
        "dataset_quality": {},
        "dataset_provenance": {"items": [], "count": 0},
        "dataset_replay_ready": {"items": [], "count": 0},
        "dataset_settings": {},
        "user": current_user(request),
    }
    if section == "command_center":
        base["missing_prerequisites"] = v3_missing_prerequisites_scan(limit=50)
        base["validation_status"] = v3_validation_status()
        base["platform_summary"] = v4_platform.platform_summary(app)
    if section == "search":
        base["search_index"] = v3_build_search_index(limit=75)
        base["search_filters"] = v3_search_filters()
    if section == "graph":
        base["graph"] = v3_build_decision_graph(limit=75)
        base["graph_filters"] = v3_graph_filters()
    if section in {"workflows", "briefs"}:
        base["workflows"] = v3_workflow_registry()
        base["workflow_templates"] = v3_workflow_templates()
        base["workflow_outputs"] = v3_workflow_outputs(limit=25)
        base["recent_runs"] = v3_list_workflow_runs(limit=25)
    if section == "settings":
        base["settings"] = v3_build_settings()
        base["validation_status"] = v3_validation_status()
    if section == "simulation":
        # Page loads stay fast and do not run replay/simulation automatically.
        # Simulation execution remains operator-triggered via API/workflow actions.
        base["simulation_sessions"] = v3_sim_list_sessions(limit=50)
        base["simulation_reports"] = v3_sim_list_reports(limit=50)
        base["simulation_process_backtest"] = {"process_scorecard": {"score": 0, "max_score": 100, "status": "not_run"}, "metrics": {"decisions_logged": 0, "stale_evidence_count": 0}, "suggested_process_improvements": ["Run a process-quality backtest from the Simulation Lab API or workflow."], "simulation_only": True, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
        base["simulation_replay"] = {"replay_time": "not_run", "known_count": 0, "created_after_replay_time_count": 0, "historical_reconstruction_is_best_effort": True, "secret_values_returned": False}
        base["simulation_pre_trade"] = {"blockers": [], "warnings": ["Simulation is not auto-run on page load."], "unknown_unavailable": ["Run a replay to generate a packet."], "assumption_set": {"local_only_replay": True}, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
        base["simulation_no_trade"] = {"no_trade_rationale": ["No-trade simulation has not been run yet."], "order_submitted": False, "order_cancelled": False, "live_trading_armed": False, "secret_values_returned": False}
    if section == "datasets":
        # Page loads stay fast and do not collect snapshots or build datasets automatically.
        # Collection/build/validation remain explicit operator-triggered read-only actions.
        base["dataset_snapshots"] = v3_datasets_list_snapshots(limit=100)
        base["dataset_runs"] = v3_datasets_list_runs(limit=50)
        base["dataset_manifests"] = v3_datasets_list_manifests(limit=50)
        base["dataset_quality"] = v3_datasets_quality_report()
        base["dataset_provenance"] = v3_datasets_list_provenance(limit=50)
        base["dataset_replay_ready"] = v3_datasets_replay_ready(limit=50)
        base["dataset_settings"] = v3_datasets_build_settings()

    if section == "tasks":
        # Page loads stay fast and do not scan/generate tasks automatically.
        # Inbox scans, cadence generation, and packet creation remain explicit operator-triggered actions.
        base["task_context"] = v3_tasks_context()
        base["tasks_summary"] = v3_tasks_summary()
        base["task_list"] = v3_tasks_list_tasks(limit=250)
        base["task_inbox"] = v3_tasks_list_inbox(limit=250)
        base["task_board"] = v3_tasks_board()
        base["task_today"] = v3_tasks_today()
        base["task_week"] = v3_tasks_week()
        base["task_cadence"] = v3_tasks_list_cadence(limit=250)
        base["task_templates"] = v3_tasks_list_templates(limit=250)
        base["task_settings"] = v3_tasks_build_settings()
        base["workspace_summary"] = v3_workspace.workspace_summary()
        base["workspace_dependencies"] = v3_workspace.list_dependencies(limit=250)
        base["workspace_saved_views"] = v3_workspace.list_saved_views(limit=250)
        base["workspace_source_previews"] = v3_workspace.list_source_previews(limit=250)
        base["cockpit_summary"] = v3_cockpit.cockpit_summary()
    if section == "workspace":
        # Guided workspace is local-first and operator-triggered; no guided review runs on page load.
        base["workspace_context"] = v3_workspace.build_workspace_context()
        base["workspace_summary"] = base["workspace_context"]["summary"]
        base["workspace_flows"] = base["workspace_context"]["flows"]
        base["workspace_sessions"] = base["workspace_context"]["sessions"]
        base["workspace_dependencies"] = base["workspace_context"]["dependencies"]
        base["workspace_blocked_review"] = base["workspace_context"]["blocked_review"]
        base["workspace_source_previews"] = base["workspace_context"]["source_previews"]
        base["workspace_saved_views"] = base["workspace_context"]["saved_views"]
        base["workspace_review_packets"] = base["workspace_context"]["review_packets"]
        base["workspace_settings"] = base["workspace_context"]["settings"]
        base["cockpit_summary"] = v3_cockpit.cockpit_summary()
        base["cockpit_layouts"] = v3_cockpit.list_layouts(limit=250)
        base["tasks_summary"] = v3_tasks_summary()
        base["task_list"] = v3_tasks_list_tasks(limit=250)
    if section == "cockpit":
        # Cockpit pages are local-first and fast. They show safe summaries only; no scans, exports, or live mutations run on page load.
        base["cockpit_context"] = v3_cockpit.build_cockpit_context()
        base["cockpit_summary"] = base["cockpit_context"]["summary"]
        base["cockpit_layouts"] = base["cockpit_context"]["layouts"]
        base["cockpit_selected_layout"] = base["cockpit_context"]["selected_layout"]
        base["cockpit_panels"] = base["cockpit_context"]["panels"]
        base["cockpit_focus_modes"] = base["cockpit_context"]["focus_modes"]
        base["cockpit_shortcuts"] = base["cockpit_context"]["shortcuts"]
        base["cockpit_command_palette"] = base["cockpit_context"]["command_palette"]
        base["cockpit_dependency_view"] = base["cockpit_context"]["dependency_view"]
        base["cockpit_source_context"] = base["cockpit_context"]["source_context"]
        base["cockpit_review_packets"] = base["cockpit_context"]["review_packets"]
        base["cockpit_settings"] = base["cockpit_context"]["settings"]
        base["feature_status"] = build_feature_status_map()
        base["workspace_summary"] = v3_workspace.workspace_summary()
        base["tasks_summary"] = v3_tasks_summary()
        base["task_list"] = v3_tasks_list_tasks(limit=50)
    if section == "platform":
        # Platform diagnostics are local-first and inexpensive; no network, no AI/model, and no live mutation work is run.
        base["platform_context"] = v4_platform.diagnostics_summary(app)
        base["platform_summary"] = v4_platform.platform_summary(app)
        base["platform_health"] = v4_platform.health_summary(app)
        base["platform_routes"] = v4_platform_routes.route_inventory(app)
        base["platform_plugins"] = v4_platform_plugins.load_plugin_manifests()
        base["platform_storage"] = v4_platform_storage.storage_summary()
        base["platform_api_schema"] = v4_platform_api.summarize_api_schema_consistency(app)
        base["platform_response_envelopes"] = v4_platform_api.list_response_envelopes()
        base["platform_migrations"] = v4_platform_migrations.migration_summary()
        base["platform_migration_plan"] = v4_platform_migrations.migration_plan()
        base["platform_storage_map"] = v4_platform_migrations.storage_map()
        base["platform_diagnostics"] = base["platform_context"]
        base["platform_safety"] = v4_platform_safety.safety_statements()
        base["platform_settings"] = v4_platform.build_settings()

    if section == "freshness":
        # Page loads stay fast and do not collect snapshots or run jobs automatically.
        # Scans and collection jobs remain explicit operator-triggered read-only actions.
        base["freshness_summary"] = v3_freshness_summary()
        base["freshness_policies"] = v3_freshness_list_policies(limit=100)
        base["freshness_jobs"] = v3_freshness_list_jobs(limit=100)
        base["freshness_findings"] = v3_freshness_list_findings(limit=100)
        base["freshness_notifications"] = v3_freshness_list_notifications(limit=100)
        base["freshness_readiness"] = v3_freshness_readiness_report(write=False)
        base["freshness_history"] = v3_freshness_list_readiness_reports(limit=50)
        base["freshness_settings"] = v3_freshness_build_settings()
        base["related_tasks"] = v3_tasks_context_for_subsystem("freshness", limit=20)
    if section == "ai":
        # AI page loads show local settings, templates, schemas, suggestions, packets, and audit hashes only.
        # They do not call OpenAI, run tool calls, mutate live trading state, or accept AI suggestions automatically.
        base["ai_summary"] = v4_ai.ai_summary()
        base["ai_settings"] = v4_ai.ai_settings_summary()
        base["ai_providers"] = v4_ai_providers.list_providers()
        base["ai_provider_health"] = v4_ai_providers.providers_health(dry_run=True)
        base["ai_local_llm"] = v4_ai_local_llm.local_llm_settings_summary()
        base["ai_model_recommendations"] = v4_ai_models.list_model_recommendations()
        base["ai_prompts"] = v4_ai_prompts.list_prompt_templates()
        base["ai_schemas"] = v4_ai_schemas.schema_registry()
        base["ai_suggestions"] = v4_ai.list_suggestions(limit=100)
        base["ai_audit"] = v4_ai_openai.list_audit_records(limit=100)
        base["ai_review_packets"] = v4_ai.list_review_packets(limit=100)
        base["ai_chatgpt_connector"] = v4_ai.chatgpt_connector_blueprint()
        base["ai_redaction_preview"] = v4_ai.redaction_preview()
        base["ai_copilot_status"] = v4_ai_copilot.copilot_status()
        base["ai_edge_summary"] = v4_ai_edge.edge_summary()
        base["ai_edge_settings"] = v4_ai_edge.edge_settings_summary()
        base["ai_edge_packets"] = v4_ai_edge.list_packets(limit=100)
        base["ai_edge_evidence"] = v4_ai_evidence.list_evidence_sources(limit=100)
        base["ai_edge_calibration"] = v4_ai_edge_calibration.list_records(limit=100)
        base["ai_edge_calibration_summary"] = v4_ai_edge_calibration.calibration_summary()
        base["ai_edge_schemas"] = v4_ai_edge.schema_registry()
        base["ai_news_odds_summary"] = v4_ai_news_odds.summarize_news_odds()
        base["ai_news_odds_settings"] = v4_ai_news_odds.news_odds_settings_summary()
        base["tasks_summary"] = v3_tasks_summary()
        base["platform_summary"] = v4_platform.platform_summary(app)
    if section == "datasets":
        base["related_tasks"] = v3_tasks_context_for_subsystem("datasets", limit=20)
    if section == "simulation":
        base["related_tasks"] = v3_tasks_context_for_subsystem("simulation", limit=20)
    if section == "analytics":
        base["related_tasks"] = v3_tasks_context_for_subsystem("analytics", limit=20)
    return base


app.include_router(create_v3_core_router())
app.include_router(create_platform_router(
    templates=templates,
    context_factory=_v3_template_context,
    app_provider=lambda: app,
))
app.include_router(create_ai_router(
    templates=templates,
    context_factory=_v3_template_context,
))


# v4.4 unified navigation aliases. These are redirects only: they preserve auth,
# protection, backend gates, confirmations, and canonical route behavior.
for _alias_path, _target_path in get_route_aliases().items():
    async def _navigation_alias(target: str = _target_path):
        return RedirectResponse(url=target, status_code=307)
    app.add_api_route(_alias_path, _navigation_alias, methods=["GET"], include_in_schema=False)


@app.get("/system-map", response_class=HTMLResponse)
@app.get("/routes", response_class=HTMLResponse)
async def unified_system_map_page(request: Request):
    return templates.TemplateResponse(
        "system_map.html",
        {
            "request": request,
            "user": current_user(request),
            "system_map": get_system_map(),
            "primary_entry_points": get_primary_entry_points(),
            "navigation_safety_explainer": get_safety_explainer(),
            "edge_recommendation_legend": edge_recommendation_legend(),
        },
    )


def _operator_os_template_context(request: Request, workspace: str) -> dict[str, Any]:
    context = v417_operator_os.build_workspace_context(workspace)
    context.update({"request": request, "user": current_user(request)})
    return context


@app.get("/v3", response_class=HTMLResponse)
@app.get("/v3/command-center", response_class=HTMLResponse)
@app.get("/operator-os", response_class=HTMLResponse)
@app.get("/command-center", response_class=HTMLResponse)
async def v3_command_center_page(request: Request):
    return templates.TemplateResponse("operator_os_v417.html", _operator_os_template_context(request, "command_center"))


@app.get("/v3/automation", response_class=HTMLResponse)
@app.get("/automation", response_class=HTMLResponse)
async def v3_operator_automation_page(request: Request):
    return templates.TemplateResponse("operator_os_v417.html", _operator_os_template_context(request, "automation"))


@app.get("/v3/review-audit", response_class=HTMLResponse)
@app.get("/review-audit", response_class=HTMLResponse)
async def v3_operator_review_audit_page(request: Request):
    return templates.TemplateResponse("operator_os_v417.html", _operator_os_template_context(request, "review_audit"))


@app.get("/v3/settings-system", response_class=HTMLResponse)
@app.get("/settings-system", response_class=HTMLResponse)
async def v3_operator_settings_system_page(request: Request):
    return templates.TemplateResponse("operator_os_v417.html", _operator_os_template_context(request, "settings_system"))


@app.get("/api/v3/operator-os")
async def api_v3_operator_os_root():
    return v417_operator_os.build_workspace_context("command_center")


@app.get("/api/v3/operator-os/{workspace}")
async def api_v3_operator_os_workspace(workspace: str):
    return v417_operator_os.build_workspace_context(workspace)


@app.get("/v3/search", response_class=HTMLResponse)
async def v3_search_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "search"))


@app.get("/v3/graph", response_class=HTMLResponse)
async def v3_graph_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "graph"))


@app.get("/v3/workflows", response_class=HTMLResponse)
async def v3_workflows_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "workflows"))


@app.get("/v3/briefs", response_class=HTMLResponse)
@app.get("/v3/pre-trade-packet", response_class=HTMLResponse)
@app.get("/v3/market-brief", response_class=HTMLResponse)
@app.get("/v3/thesis-health", response_class=HTMLResponse)
@app.get("/v3/portfolio-brief", response_class=HTMLResponse)
@app.get("/v3/operator-review", response_class=HTMLResponse)
async def v3_briefs_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "briefs"))


@app.get("/v3/settings", response_class=HTMLResponse)
async def v3_settings_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "settings"))


@app.get("/v3/paper-trading", response_class=HTMLResponse)
async def v3_paper_trading_page(request: Request):
    status = v416_paper.build_paper_status()
    return templates.TemplateResponse(
        "paper_trading_v416.html",
        {
            "request": request,
            "user": current_user(request),
            "status": status,
            "config": status.get("config", {}),
            "account": status.get("account", {}),
            "positions": status.get("positions", []),
            "recent_orders": status.get("recent_orders", []),
            "recent_fills": status.get("recent_fills", []),
            "recent_decisions": status.get("recent_decisions", []),
            "last_run": status.get("last_run", {}),
            "action_status": request.query_params.get("action_status", ""),
            "action_detail": request.query_params.get("action_detail", ""),
        },
    )


@app.post("/v3/paper-trading/run-once")
async def v3_paper_trading_run_once_page(user: dict = Depends(require_admin)):
    result = v416_paper.run_paper_strategy_once(source_route="/v3/paper-trading", source_component="paper_trading.run_once_form")
    status = "paper_run_completed" if result.get("ok") else "paper_run_blocked"
    detail = f"trades={result.get('paper_trades_placed', 0)} candidates={result.get('candidates_considered', 0)}"
    if not result.get("ok"):
        detail = str(result.get("disabled_reason") or result.get("status") or "blocked")[:200]
    return _v3_action_redirect("/v3/paper-trading", action_status=status, action_detail=detail)


@app.post("/v3/paper-trading/reset")
async def v3_paper_trading_reset_page(starting_balance: float = Form(default=1000.0), user: dict = Depends(require_admin)):
    v416_paper.reset_paper_account(starting_balance=starting_balance, reason="operator reset from /v3/paper-trading")
    return _v3_action_redirect("/v3/paper-trading", action_status="paper_account_reset", action_detail=f"starting_balance={starting_balance}")


@app.get("/api/v3/paper/config")
async def api_v3_paper_config():
    return v416_paper.get_paper_config().to_dict()


@app.get("/api/v3/paper/status")
async def api_v3_paper_status():
    return v416_paper.build_paper_status()


@app.get("/api/v3/paper/account")
async def api_v3_paper_account():
    return {"account": v416_paper.load_paper_account(), "paper_only": True, "live_execution_used": False, "can_place_real_orders": False, "can_cancel_real_orders": False, "secret_values_returned": False}


@app.get("/api/v3/paper/orders")
async def api_v3_paper_orders(limit: int = Query(default=100, ge=1, le=2000)):
    return v416_paper.list_paper_orders(limit=limit)


@app.get("/api/v3/paper/fills")
async def api_v3_paper_fills(limit: int = Query(default=100, ge=1, le=2000)):
    return v416_paper.list_paper_fills(limit=limit)


@app.get("/api/v3/paper/positions")
async def api_v3_paper_positions(limit: int = Query(default=100, ge=1, le=2000)):
    return v416_paper.list_paper_positions(limit=limit)


@app.get("/api/v3/paper/decisions")
async def api_v3_paper_decisions(limit: int = Query(default=100, ge=1, le=2000)):
    return v416_paper.list_paper_decisions(limit=limit)


@app.get("/api/v3/paper/runs")
async def api_v3_paper_runs(limit: int = Query(default=50, ge=1, le=1000)):
    return v416_paper.list_paper_runs(limit=limit)


@app.get("/api/v3/paper/audit")
async def api_v3_paper_audit(limit: int = Query(default=100, ge=1, le=2000)):
    return v416_paper.list_paper_audit(limit=limit)


@app.post("/api/v3/paper/run-once")
async def api_v3_paper_run_once(payload: dict[str, Any] | None = Body(default=None), user: dict = Depends(require_admin)):
    return v416_paper.run_paper_strategy_once(payload or {}, source_route="/api/v3/paper/run-once", source_component="paper_strategy_runner.api")


@app.post("/api/v3/paper/reset")
async def api_v3_paper_reset(payload: dict[str, Any] | None = Body(default=None), user: dict = Depends(require_admin)):
    payload = payload or {}
    starting_balance = float(payload.get("starting_balance") or v416_paper.get_paper_config().starting_balance or 1000.0)
    return v416_paper.reset_paper_account(starting_balance=starting_balance, reason=str(payload.get("reason") or "api reset"))


@app.post("/api/v3/paper/orders/{order_id}/cancel-paper")
async def api_v3_paper_cancel_order(order_id: str, payload: dict[str, Any] | None = Body(default=None), user: dict = Depends(require_admin)):
    return v416_paper.cancel_paper_order(order_id, reason=str((payload or {}).get("reason") or "operator paper cancellation"))


@app.post("/v3/settings/preferences")
@app.post("/v3/settings/preferences/save")
async def v3_settings_preferences_submit(request: Request):
    form = await request.form()
    payload: dict[str, Any] = {
        "_source_route": "/v3/settings",
        "_source_component": "v3_settings.preferences_form",
    }
    for key in form.keys():
        if not str(key).startswith("setting__"):
            continue
        setting_key = str(key).split("setting__", 1)[1]
        values = form.getlist(key)
        payload[setting_key] = values[-1] if values else ""
    result = v3_update_settings(payload)
    status = "settings_preferences_saved" if result.get("ok") else "settings_preferences_rejected"
    if result.get("ok"):
        detail = ",".join(result.get("updated_keys") or []) or "no_changes"
    else:
        errors = result.get("errors") or []
        detail = "; ".join(str(item.get("error") or item) for item in errors)[:220] or "validation_failed"
    return _v3_action_redirect("/v3/settings", action_status=status, action_detail=detail)


@app.get("/v3/tasks", response_class=HTMLResponse)
@app.get("/v3/tasks/board", response_class=HTMLResponse)
@app.get("/v3/tasks/inbox", response_class=HTMLResponse)
@app.get("/v3/tasks/today", response_class=HTMLResponse)
@app.get("/v3/tasks/week", response_class=HTMLResponse)
@app.get("/v3/tasks/cadence", response_class=HTMLResponse)
@app.get("/v3/tasks/reviews", response_class=HTMLResponse)
@app.get("/v3/tasks/templates", response_class=HTMLResponse)
@app.get("/v3/tasks/exports", response_class=HTMLResponse)
@app.get("/v3/tasks/settings", response_class=HTMLResponse)
async def v3_tasks_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "tasks"))


@app.get("/v3/workspace", response_class=HTMLResponse)
@app.get("/v3/workspace/start", response_class=HTMLResponse)
@app.get("/v3/workspace/daily-review", response_class=HTMLResponse)
@app.get("/v3/workspace/weekly-review", response_class=HTMLResponse)
@app.get("/v3/workspace/task-triage", response_class=HTMLResponse)
@app.get("/v3/workspace/blocked", response_class=HTMLResponse)
@app.get("/v3/workspace/dependencies", response_class=HTMLResponse)
@app.get("/v3/workspace/source-preview", response_class=HTMLResponse)
@app.get("/v3/workspace/review-flows", response_class=HTMLResponse)
@app.get("/v3/workspace/review-packets", response_class=HTMLResponse)
@app.get("/v3/workspace/saved-views", response_class=HTMLResponse)
@app.get("/v3/workspace/settings", response_class=HTMLResponse)
async def v3_workspace_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "workspace"))


def _v3_action_redirect(path: str, *, action_status: str, action_detail: str = "") -> RedirectResponse:
    query = {"action_status": action_status}
    if action_detail:
        query["action_detail"] = action_detail
    separator = "&" if "?" in path else "?"
    return RedirectResponse(url=f"{path}{separator}{urlencode(query)}", status_code=303)


def _payload_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@app.post("/v3/workspace/daily-review/start")
async def v3_workspace_daily_review_start_form():
    result = v3_workspace.start_daily_review({})
    session = result.get("session", {}) if isinstance(result, dict) else {}
    return _v3_action_redirect("/v3/workspace/daily-review", action_status="daily_review_started", action_detail=str(session.get("session_id") or "session_created"))


@app.post("/v3/workspace/weekly-review/start")
async def v3_workspace_weekly_review_start_form():
    result = v3_workspace.start_weekly_review({})
    session = result.get("session", {}) if isinstance(result, dict) else {}
    return _v3_action_redirect("/v3/workspace/weekly-review", action_status="weekly_review_started", action_detail=str(session.get("session_id") or "session_created"))


@app.post("/v3/workspace/task-triage/start")
async def v3_workspace_task_triage_start_form():
    result = v3_workspace.start_task_triage({})
    session = result.get("session", {}) if isinstance(result, dict) else {}
    return _v3_action_redirect("/v3/workspace/task-triage", action_status="task_triage_started", action_detail=str(session.get("session_id") or "session_created"))


@app.post("/v3/ai/providers/test-dry-run")
async def v3_ai_provider_test_dry_run_form(provider: str = Form(default="mock")):
    result = v4_ai_providers.test_dry_run({"provider": provider or "mock"})
    return _v3_action_redirect("/v3/ai/providers", action_status="provider_dry_run_completed", action_detail=str(result.get("provider") or provider or "mock"))


@app.post("/v3/ai/edge/packets/generate")
async def v3_ai_edge_generate_packet_form(title: str = Form(default="Browser AI Edge draft packet")):
    result = v4_ai_edge.generate_edge_packet(
        {
            "title": title or "Browser AI Edge draft packet",
            "research_question": "Browser-requested AI Edge draft packet for operator review.",
            "write": True,
        },
        write=True,
        mode="browser_draft",
    )
    packet = result.get("packet", {}) if isinstance(result, dict) else {}
    return _v3_action_redirect("/v3/ai/edge/packets", action_status="ai_edge_packet_generated", action_detail=str(packet.get("packet_id") or "draft_packet"))


@app.post("/v3/ai/edge/evidence/normalize")
async def v3_ai_edge_normalize_evidence_form():
    result = v4_ai_evidence.normalize_evidence({}, write=False, include_demo_when_empty=True)
    return _v3_action_redirect("/v3/ai/edge/evidence", action_status="evidence_normalized_preview", action_detail=f"{result.get('count', 0)}_sources")


@app.post("/v3/ai/review-packets/generate")
async def v3_ai_review_packet_generate_form(title: str = Form(default="Browser AI review packet")):
    result = v4_ai.generate_review_packet({"title": title or "Browser AI review packet", "write": True}, write=True)
    packet = result.get("packet", {}) if isinstance(result, dict) else {}
    return _v3_action_redirect("/v3/ai/review-packets", action_status="ai_review_packet_generated", action_detail=str(packet.get("packet_id") or "review_packet"))


@app.get("/v3/cockpit", response_class=HTMLResponse)
@app.get("/v3/cockpit/layouts", response_class=HTMLResponse)
@app.get("/v3/cockpit/focus", response_class=HTMLResponse)
@app.get("/v3/cockpit/review", response_class=HTMLResponse)
@app.get("/v3/cockpit/tasks", response_class=HTMLResponse)
@app.get("/v3/cockpit/dependencies", response_class=HTMLResponse)
@app.get("/v3/cockpit/source", response_class=HTMLResponse)
@app.get("/v3/cockpit/packets", response_class=HTMLResponse)
@app.get("/v3/cockpit/command-palette", response_class=HTMLResponse)
@app.get("/v3/cockpit/shortcuts", response_class=HTMLResponse)
@app.get("/v3/cockpit/settings", response_class=HTMLResponse)
async def v3_cockpit_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "cockpit"))


@app.post("/v3/cockpit/layouts/{layout_id}/select")
async def v3_cockpit_layout_select_form(layout_id: str):
    result = v3_cockpit.select_layout(layout_id)
    if result.get("ok") is False:
        return RedirectResponse(url="/v3/cockpit?layout_error=not_found", status_code=303)
    return RedirectResponse(url=f"/v3/cockpit?selected_layout={layout_id}", status_code=303)


@app.post("/v3/cockpit/focus-modes/{focus_mode_id}/start")
async def v3_cockpit_focus_start_form(focus_mode_id: str):
    result = v3_cockpit.start_focus_mode(focus_mode_id)
    if result.get("ok") is False:
        return RedirectResponse(url="/v3/cockpit?focus_error=not_found", status_code=303)
    focus = result.get("focus_mode", {})
    route = str(focus.get("entry_route") or "/v3/cockpit")
    return RedirectResponse(url=f"{route}?focus_mode={focus_mode_id}", status_code=303)


@app.post("/v3/cockpit/layouts/save-selected")
async def v3_cockpit_save_selected_layout_form(title: str = Form(default="")):
    result = v3_cockpit.save_current_layout_copy(title)
    layout_id = result.get("selected_layout_id") or "saved"
    return RedirectResponse(url=f"/v3/cockpit?saved_layout={layout_id}", status_code=303)


@app.get("/v3/docs", response_class=HTMLResponse)
async def v3_docs_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "docs"))


@app.get("/v3/analytics", response_class=HTMLResponse)
@app.get("/v3/analytics/decisions", response_class=HTMLResponse)
@app.get("/v3/analytics/theses", response_class=HTMLResponse)
@app.get("/v3/analytics/evidence", response_class=HTMLResponse)
@app.get("/v3/analytics/alerts", response_class=HTMLResponse)
@app.get("/v3/analytics/governance", response_class=HTMLResponse)
@app.get("/v3/analytics/portfolio", response_class=HTMLResponse)
@app.get("/v3/analytics/calibration", response_class=HTMLResponse)
@app.get("/v3/analytics/reviews", response_class=HTMLResponse)
@app.get("/v3/analytics/learning-report", response_class=HTMLResponse)
async def v3_analytics_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "analytics"))


@app.get("/v3/simulation", response_class=HTMLResponse)
@app.get("/v3/simulation/replay", response_class=HTMLResponse)
@app.get("/v3/simulation/sessions", response_class=HTMLResponse)
@app.get("/v3/simulation/scenarios", response_class=HTMLResponse)
@app.get("/v3/simulation/pre-trade", response_class=HTMLResponse)
@app.get("/v3/simulation/thesis", response_class=HTMLResponse)
@app.get("/v3/simulation/alerts", response_class=HTMLResponse)
@app.get("/v3/simulation/portfolio", response_class=HTMLResponse)
@app.get("/v3/simulation/governance", response_class=HTMLResponse)
@app.get("/v3/simulation/no-trade", response_class=HTMLResponse)
@app.get("/v3/simulation/reports", response_class=HTMLResponse)
async def v3_simulation_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "simulation"))


@app.get("/v3/datasets", response_class=HTMLResponse)
@app.get("/v3/datasets/snapshots", response_class=HTMLResponse)
@app.get("/v3/datasets/collector", response_class=HTMLResponse)
@app.get("/v3/datasets/builder", response_class=HTMLResponse)
@app.get("/v3/datasets/quality", response_class=HTMLResponse)
@app.get("/v3/datasets/provenance", response_class=HTMLResponse)
@app.get("/v3/datasets/replay", response_class=HTMLResponse)
@app.get("/v3/datasets/exports", response_class=HTMLResponse)
@app.get("/v3/datasets/settings", response_class=HTMLResponse)
async def v3_datasets_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "datasets"))


@app.get("/v3/freshness", response_class=HTMLResponse)
@app.get("/v3/freshness/planner", response_class=HTMLResponse)
@app.get("/v3/freshness/schedules", response_class=HTMLResponse)
@app.get("/v3/freshness/jobs", response_class=HTMLResponse)
@app.get("/v3/freshness/notifications", response_class=HTMLResponse)
@app.get("/v3/freshness/readiness", response_class=HTMLResponse)
@app.get("/v3/freshness/history", response_class=HTMLResponse)
@app.get("/v3/freshness/settings", response_class=HTMLResponse)
async def v3_freshness_page(request: Request):
    return templates.TemplateResponse("live_v3_dashboard.html", _v3_template_context(request, "freshness"))

@app.get("/api/v3")
async def api_v3_root():
    return {"version": APP_VERSION, "name": "Polymarket OP Console v4.17 Operator OS API", "routes": ["/api/v3/command-center", "/api/v3/operator-os", "/api/v3/operator-os/command_center", "/api/v3/operator-os/opportunities", "/api/v3/operator-os/automation", "/api/v3/operator-os/review_audit", "/api/v3/operator-os/settings_system", "/api/v3/search", "/api/v3/graph", "/api/v3/workflows", "/api/v3/tasks", "/api/v3/tasks/summary", "/api/v3/tasks/inbox", "/api/v3/ai/summary", "/api/v3/ai/settings", "/api/v3/ai/prompts", "/api/v3/ai/suggestions", "/api/v3/ai/audit", "/api/v3/ai/review-packets", "/api/v3/ai/chatgpt-connector", "/api/v3/ai/edge/summary", "/api/v3/ai/edge/packets", "/api/v3/ai/edge/evidence", "/api/v3/ai/edge/calibration", "/api/v3/ai/news-odds/config", "/api/v3/ai/news-odds/adjustments", "/api/v3/arbitrage/config", "/api/v3/arbitrage/scan", "/api/v3/arbitrage/scan/record", "/api/v3/demo/create", "/api/v3/validation/status", "/api/v3/analytics", "/api/v3/simulation", "/api/v3/datasets", "/api/v3/freshness", "/api/v3/ux/status", "/api/v3/platform/schema", "/api/v3/platform/route-registry", "/api/v3/platform/migrations/summary", "/api/v3/platform/migrations/plan", "/api/v3/platform/migrations/storage-map"], "secret_values_returned": False}


@app.get("/api/v3/command-center")
async def api_v3_command_center():
    return v3_build_command_center()


@app.get("/api/v3/search/index")
async def api_v3_search_index(limit: int = 250):
    return v3_build_search_index(limit=limit)


@app.post("/api/v3/search/rebuild")
async def api_v3_search_rebuild():
    return v3_rebuild_search_index()


@app.get("/api/v3/search/filters")
async def api_v3_search_filters():
    return v3_search_filters()


@app.get("/api/v3/search")
async def api_v3_search_get(q: str = "", result_type: str = "", status: str = "", tag: str = "", recent: str = "", limit: int = 50):
    return v3_search_local(query=q, result_type=result_type, status=status, tag=tag, recent=recent, limit=limit)


@app.post("/api/v3/search")
async def api_v3_search_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_search_local(query=str(payload.get("query", payload.get("q", ""))), result_type=str(payload.get("result_type", "")), status=str(payload.get("status", "")), tag=str(payload.get("tag", "")), recent=str(payload.get("recent", "")), limit=int(payload.get("limit", 50) or 50))


@app.get("/api/v3/graph/filters")
async def api_v3_graph_filters():
    return v3_graph_filters()


@app.get("/api/v3/graph")
async def api_v3_graph(limit: int = 250, node_type: str = "", relationship_type: str = ""):
    if node_type or relationship_type:
        return v3_filtered_decision_graph(node_type=node_type, relationship_type=relationship_type, limit=limit)
    return v3_build_decision_graph(limit=limit)


@app.post("/api/v3/graph/rebuild")
async def api_v3_graph_rebuild():
    return v3_rebuild_graph()


@app.get("/api/v3/graph/export.json", response_class=PlainTextResponse)
async def api_v3_graph_export_json():
    return PlainTextResponse(json.dumps(v3_build_decision_graph(limit=1000), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/graph/export.md", response_class=PlainTextResponse)
async def api_v3_graph_export_markdown():
    return PlainTextResponse(v3_graph_to_markdown(v3_build_decision_graph(limit=1000)), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/workflows")
async def api_v3_workflows():
    return v3_workflow_registry()


@app.get("/api/v3/workflows/templates")
async def api_v3_workflow_templates():
    return v3_workflow_templates()


@app.get("/api/v3/workflows/outputs")
async def api_v3_workflow_outputs(limit: int = 100):
    return v3_workflow_outputs(limit=limit)


@app.post("/api/v3/workflows/run")
async def api_v3_workflows_run(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_run_workflow(payload)


@app.get("/api/v3/workflows/runs")
async def api_v3_workflow_runs(limit: int = 100):
    return v3_list_workflow_runs(limit=limit)


@app.get("/api/v3/workflows/runs/{run_id}")
async def api_v3_workflow_run_detail(run_id: str):
    row = v3_get_workflow_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return row


@app.get("/api/v3/pre-trade-packet")
async def api_v3_pre_trade_packet_get(market_id: str = "", thesis_id: str = "", outcome: str = ""):
    return v3_pre_trade_packet({"market_id": market_id, "thesis_id": thesis_id, "outcome": outcome})


@app.post("/api/v3/pre-trade-packet")
async def api_v3_pre_trade_packet_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_pre_trade_packet(payload)


@app.get("/api/v3/market-brief")
async def api_v3_market_brief_get(market_id: str = ""):
    return v3_market_intelligence_brief({"market_id": market_id})


@app.post("/api/v3/market-brief")
async def api_v3_market_brief_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_market_intelligence_brief(payload)


@app.get("/api/v3/thesis-health")
async def api_v3_thesis_health_get(thesis_id: str = ""):
    return v3_thesis_health_report({"thesis_id": thesis_id})


@app.post("/api/v3/thesis-health")
async def api_v3_thesis_health_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_thesis_health_report(payload)


@app.get("/api/v3/portfolio-brief")
async def api_v3_portfolio_brief_get():
    return v3_portfolio_risk_brief({})


@app.post("/api/v3/portfolio-brief")
async def api_v3_portfolio_brief_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_portfolio_risk_brief(payload)


@app.get("/api/v3/operator-review")
async def api_v3_operator_review_get(period: str = "daily"):
    return v3_operator_review_packet({"period": period})


@app.post("/api/v3/operator-review")
async def api_v3_operator_review_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_operator_review_packet(payload)


@app.get("/api/v3/missing-prerequisites")
async def api_v3_missing_prerequisites(limit: int = 250):
    return v3_missing_prerequisites_scan(limit=limit)


@app.post("/api/v3/missing-prerequisites/scan")
async def api_v3_missing_prerequisites_scan(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_missing_prerequisites_scan(limit=int(payload.get("limit", 250) or 250))


@app.get("/api/v3/export/report.json", response_class=PlainTextResponse)
async def api_v3_export_report_json(kind: str = "command_center"):
    return PlainTextResponse(json.dumps(v3_export_report_json(kind), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/export/report.md", response_class=PlainTextResponse)
async def api_v3_export_report_markdown(kind: str = "command_center"):
    return PlainTextResponse(v3_export_report_markdown(kind), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/simulation")
async def api_v3_simulation_summary():
    return v3_sim_summary()


@app.get("/api/v3/simulation/sessions")
async def api_v3_simulation_sessions(limit: int = 100):
    return v3_sim_list_sessions(limit=limit)


@app.post("/api/v3/simulation/sessions")
async def api_v3_simulation_create_session(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_create_session(payload)


@app.post("/api/v3/simulation/sessions/{session_id}")
async def api_v3_simulation_update_session(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_update_session(session_id, payload)


@app.post("/api/v3/simulation/sessions/{session_id}/run")
async def api_v3_simulation_run_session(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_run_session(session_id, payload)


@app.post("/api/v3/simulation/sessions/{session_id}/archive")
async def api_v3_simulation_archive_session(session_id: str):
    return v3_sim_archive_session(session_id)


@app.get("/api/v3/simulation/replay")
async def api_v3_simulation_replay_get(replay_time: str = ""):
    return v3_sim_replay({"replay_time": replay_time})


@app.post("/api/v3/simulation/replay")
async def api_v3_simulation_replay_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_replay(payload)


@app.post("/api/v3/simulation/pre-trade")
async def api_v3_simulation_pre_trade(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_pre_trade(payload)


@app.post("/api/v3/simulation/thesis")
async def api_v3_simulation_thesis(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_thesis(payload)


@app.post("/api/v3/simulation/alerts")
async def api_v3_simulation_alerts(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_alerts(payload)


@app.post("/api/v3/simulation/portfolio")
async def api_v3_simulation_portfolio(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_portfolio(payload)


@app.post("/api/v3/simulation/governance")
async def api_v3_simulation_governance(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_governance(payload)


@app.post("/api/v3/simulation/no-trade")
async def api_v3_simulation_no_trade(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_no_trade(payload)


@app.post("/api/v3/simulation/process-backtest")
async def api_v3_simulation_process_backtest(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_sim_process_backtest(payload)


@app.get("/api/v3/simulation/reports")
async def api_v3_simulation_reports(limit: int = 100):
    return v3_sim_list_reports(limit=limit)


@app.get("/api/v3/simulation/export.json", response_class=PlainTextResponse)
async def api_v3_simulation_export_json():
    return PlainTextResponse(json.dumps(v3_sim_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/simulation/export.md", response_class=PlainTextResponse)
async def api_v3_simulation_export_markdown():
    return PlainTextResponse(v3_sim_export_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/simulation/export/sessions.csv", response_class=PlainTextResponse)
async def api_v3_simulation_export_sessions_csv():
    return PlainTextResponse(v3_sim_export_csv("sessions"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/simulation/export/findings.csv", response_class=PlainTextResponse)
async def api_v3_simulation_export_findings_csv():
    return PlainTextResponse(v3_sim_export_csv("findings"), media_type="text/csv; charset=utf-8")



@app.get("/api/v3/datasets")
async def api_v3_datasets_root():
    return v3_datasets_summary()


@app.get("/api/v3/datasets/summary")
async def api_v3_datasets_summary():
    return v3_datasets_summary()


@app.get("/api/v3/datasets/snapshots")
async def api_v3_datasets_snapshots(limit: int = 250, snapshot_type: str = ""):
    return v3_datasets_list_snapshots(limit=limit, snapshot_type=snapshot_type or None)


@app.post("/api/v3/datasets/snapshots/collect")
async def api_v3_datasets_collect(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_datasets_collect_snapshots(payload)


@app.post("/api/v3/datasets/snapshots/validate")
async def api_v3_datasets_validate_snapshot(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_datasets_validate_snapshot(snapshot=payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else None, snapshot_id=payload.get("snapshot_id"))


@app.get("/api/v3/datasets/collector")
async def api_v3_datasets_collector():
    return {"version": APP_VERSION, "collector": v3_datasets_summary(), "settings": v3_datasets_build_settings(), "secret_values_returned": False}


@app.get("/api/v3/datasets/runs")
async def api_v3_datasets_runs(limit: int = 250):
    return v3_datasets_list_runs(limit=limit)


@app.get("/api/v3/datasets/runs/{run_id}")
async def api_v3_datasets_run(run_id: str):
    run = v3_datasets_get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="dataset collection run not found")
    return run


@app.post("/api/v3/datasets/build")
async def api_v3_datasets_build(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_datasets_build_manifest(payload)


@app.get("/api/v3/datasets/manifests")
async def api_v3_datasets_manifests(limit: int = 250):
    return v3_datasets_list_manifests(limit=limit)


@app.get("/api/v3/datasets/manifests/{dataset_id}")
async def api_v3_datasets_manifest(dataset_id: str):
    manifest = v3_datasets_get_manifest(dataset_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="dataset manifest not found")
    return manifest


@app.post("/api/v3/datasets/manifests/{dataset_id}/validate")
async def api_v3_datasets_manifest_validate(dataset_id: str):
    return v3_datasets_validate_manifest(dataset_id=dataset_id)


@app.get("/api/v3/datasets/quality")
async def api_v3_datasets_quality(dataset_id: str = ""):
    return v3_datasets_quality_report(dataset_id or None)


@app.get("/api/v3/datasets/provenance")
async def api_v3_datasets_provenance(limit: int = 250):
    return v3_datasets_list_provenance(limit=limit)


@app.get("/api/v3/datasets/replay-ready")
async def api_v3_datasets_replay_ready(limit: int = 250):
    return v3_datasets_replay_ready(limit=limit)


@app.get("/api/v3/datasets/export.json", response_class=PlainTextResponse)
async def api_v3_datasets_export_json(dataset_id: str = ""):
    return PlainTextResponse(json.dumps(v3_datasets_export_json(dataset_id or None), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/datasets/export.md", response_class=PlainTextResponse)
async def api_v3_datasets_export_markdown(dataset_id: str = ""):
    return PlainTextResponse(v3_datasets_export_markdown(dataset_id or None), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/datasets/export/snapshots.csv", response_class=PlainTextResponse)
async def api_v3_datasets_export_snapshots_csv():
    return PlainTextResponse(v3_datasets_export_csv("snapshots"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/datasets/export/quality.csv", response_class=PlainTextResponse)
async def api_v3_datasets_export_quality_csv():
    return PlainTextResponse(v3_datasets_export_csv("quality"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/datasets/export/provenance.csv", response_class=PlainTextResponse)
async def api_v3_datasets_export_provenance_csv():
    return PlainTextResponse(v3_datasets_export_csv("provenance"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/datasets/settings")
async def api_v3_datasets_settings_get():
    return v3_datasets_build_settings()


@app.post("/api/v3/datasets/settings")
async def api_v3_datasets_settings_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_datasets_update_settings(payload)



@app.get("/api/v3/freshness")
async def api_v3_freshness_root():
    return v3_freshness_summary()

@app.get("/api/v3/freshness/summary")
async def api_v3_freshness_summary():
    return v3_freshness_summary()

@app.get("/api/v3/freshness/policies")
async def api_v3_freshness_policies(limit: int = 250):
    return v3_freshness_list_policies(limit=limit)

@app.post("/api/v3/freshness/policies")
async def api_v3_freshness_policy_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_freshness_create_policy(payload)

@app.post("/api/v3/freshness/policies/{policy_id}")
async def api_v3_freshness_policy_update(policy_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_freshness_update_policy(policy_id, payload)

@app.get("/api/v3/freshness/jobs")
async def api_v3_freshness_jobs(limit: int = 250, status: str = ""):
    return v3_freshness_list_jobs(limit=limit, status=status or None)

@app.post("/api/v3/freshness/jobs")
async def api_v3_freshness_job_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_freshness_create_job(payload)

@app.post("/api/v3/freshness/jobs/{job_id}/run")
async def api_v3_freshness_job_run(job_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_freshness_run_job(job_id, payload)

@app.post("/api/v3/freshness/jobs/{job_id}/cancel")
async def api_v3_freshness_job_cancel(job_id: str):
    return v3_freshness_cancel_job(job_id)

@app.get("/api/v3/freshness/readiness")
async def api_v3_freshness_readiness_get(dataset_id: str = ""):
    return v3_freshness_readiness_report({"dataset_id": dataset_id}, write=False)

@app.post("/api/v3/freshness/readiness")
async def api_v3_freshness_readiness_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_freshness_readiness_report(payload)

@app.get("/api/v3/freshness/findings")
async def api_v3_freshness_findings(limit: int = 250):
    return v3_freshness_list_findings(limit=limit)

@app.post("/api/v3/freshness/scan")
async def api_v3_freshness_scan(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_freshness_scan(write=bool(payload.get("write", True)))

@app.get("/api/v3/freshness/notifications")
async def api_v3_freshness_notifications(limit: int = 250, status: str = ""):
    return v3_freshness_list_notifications(limit=limit, status=status or None)

@app.post("/api/v3/freshness/notifications/{notification_id}/ack")
async def api_v3_freshness_notification_ack(notification_id: str):
    return v3_freshness_update_notification(notification_id, "ack")

@app.post("/api/v3/freshness/notifications/{notification_id}/dismiss")
async def api_v3_freshness_notification_dismiss(notification_id: str):
    return v3_freshness_update_notification(notification_id, "dismiss")

@app.post("/api/v3/freshness/notifications/{notification_id}/snooze")
async def api_v3_freshness_notification_snooze(notification_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_freshness_update_notification(notification_id, "snooze", snooze_minutes=int(payload.get("snooze_minutes", 240) or 240))

@app.post("/api/v3/freshness/notifications/{notification_id}/resolve")
async def api_v3_freshness_notification_resolve(notification_id: str):
    return v3_freshness_update_notification(notification_id, "resolve")

@app.get("/api/v3/freshness/history")
async def api_v3_freshness_history(limit: int = 250):
    return v3_freshness_list_readiness_reports(limit=limit)

@app.get("/api/v3/freshness/export.json", response_class=PlainTextResponse)
async def api_v3_freshness_export_json():
    return PlainTextResponse(json.dumps(v3_freshness_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

@app.get("/api/v3/freshness/export.md", response_class=PlainTextResponse)
async def api_v3_freshness_export_markdown():
    return PlainTextResponse(v3_freshness_export_markdown(), media_type="text/markdown; charset=utf-8")

@app.get("/api/v3/freshness/export/jobs.csv", response_class=PlainTextResponse)
async def api_v3_freshness_export_jobs_csv():
    return PlainTextResponse(v3_freshness_export_csv("jobs"), media_type="text/csv; charset=utf-8")

@app.get("/api/v3/freshness/export/findings.csv", response_class=PlainTextResponse)
async def api_v3_freshness_export_findings_csv():
    return PlainTextResponse(v3_freshness_export_csv("findings"), media_type="text/csv; charset=utf-8")

@app.get("/api/v3/freshness/export/notifications.csv", response_class=PlainTextResponse)
async def api_v3_freshness_export_notifications_csv():
    return PlainTextResponse(v3_freshness_export_csv("notifications"), media_type="text/csv; charset=utf-8")

@app.get("/api/v3/freshness/settings")
async def api_v3_freshness_settings_get():
    return v3_freshness_build_settings()

@app.post("/api/v3/freshness/settings")
async def api_v3_freshness_settings_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_freshness_update_settings(payload)

@app.get("/api/v3/freshness/export/notifications.json", response_class=PlainTextResponse)
async def api_v3_freshness_export_notifications_json():
    return PlainTextResponse(json.dumps(v3_freshness_export_notifications_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")



@app.get("/api/v3/tasks")
async def api_v3_tasks(limit: int = 250, status: str = "", priority: str = "", source_subsystem: str = ""):
    return v3_tasks_list_tasks(limit=limit, status=status or None, priority=priority or None, source_subsystem=source_subsystem or None)


@app.get("/api/v3/tasks/summary")
async def api_v3_tasks_summary():
    return v3_tasks_summary()


@app.get("/api/v3/tasks/inbox")
async def api_v3_tasks_inbox(limit: int = 250, status: str = ""):
    return v3_tasks_list_inbox(limit=limit, status=status or None)


@app.post("/api/v3/tasks/inbox/scan")
async def api_v3_tasks_inbox_scan(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_scan_inbox(write=bool(payload.get("write", True)))


@app.post("/api/v3/tasks/inbox/{inbox_id}/create-task")
async def api_v3_tasks_inbox_create_task(inbox_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_create_task_from_inbox(inbox_id, payload)


@app.post("/api/v3/tasks/inbox/{inbox_id}/dismiss")
async def api_v3_tasks_inbox_dismiss(inbox_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_dismiss_inbox_item(inbox_id, notes=str(payload.get("notes", "")))


@app.post("/api/v3/tasks/inbox/{inbox_id}/archive")
async def api_v3_tasks_inbox_archive(inbox_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_archive_inbox_item(inbox_id, notes=str(payload.get("notes", "")))


@app.post("/api/v3/tasks/inbox/{inbox_id}/snooze")
async def api_v3_tasks_inbox_snooze(inbox_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_snooze_inbox_item(inbox_id, snooze_minutes=int(payload.get("snooze_minutes", 240) or 240), notes=str(payload.get("notes", "")))


@app.get("/api/v3/tasks/board")
async def api_v3_tasks_board():
    return v3_tasks_board()


@app.post("/api/v3/tasks")
async def api_v3_tasks_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_create_task(payload)


@app.get("/api/v3/tasks/today")
async def api_v3_tasks_today():
    return v3_tasks_today()


@app.post("/api/v3/tasks/daily-ops")
async def api_v3_tasks_daily_ops(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_daily_ops(payload, write=True)


@app.get("/api/v3/tasks/week")
async def api_v3_tasks_week():
    return v3_tasks_week()


@app.post("/api/v3/tasks/weekly-plan")
async def api_v3_tasks_weekly_plan(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_weekly_plan(payload, write=True)


@app.get("/api/v3/tasks/cadence")
async def api_v3_tasks_cadence(limit: int = 250):
    return v3_tasks_list_cadence(limit=limit)


@app.post("/api/v3/tasks/cadence")
async def api_v3_tasks_cadence_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_create_cadence_rule(payload)


@app.post("/api/v3/tasks/cadence/run")
async def api_v3_tasks_cadence_run(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_run_cadence(payload)


@app.get("/api/v3/tasks/templates")
async def api_v3_tasks_templates(limit: int = 250):
    return v3_tasks_list_templates(limit=limit)


@app.post("/api/v3/tasks/templates")
async def api_v3_tasks_template_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_create_template(payload)


@app.post("/api/v3/tasks/from-notification/{notification_id}")
async def api_v3_tasks_from_notification(notification_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_create_task_from_notification(notification_id, payload)


@app.post("/api/v3/tasks/from-finding")
async def api_v3_tasks_from_finding(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_create_task_from_finding(payload)


@app.get("/api/v3/tasks/export.json", response_class=PlainTextResponse)
async def api_v3_tasks_export_json():
    return PlainTextResponse(json.dumps(v3_tasks_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/tasks/export.md", response_class=PlainTextResponse)
async def api_v3_tasks_export_md():
    return PlainTextResponse(v3_tasks_export_md(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/tasks/export.csv", response_class=PlainTextResponse)
async def api_v3_tasks_export_csv():
    return PlainTextResponse(v3_tasks_export_csv("tasks"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/tasks/export/inbox.csv", response_class=PlainTextResponse)
async def api_v3_tasks_export_inbox_csv():
    return PlainTextResponse(v3_tasks_export_csv("inbox"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/tasks/export/cadence.csv", response_class=PlainTextResponse)
async def api_v3_tasks_export_cadence_csv():
    return PlainTextResponse(v3_tasks_export_csv("cadence"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/tasks/daily-ops/export.json", response_class=PlainTextResponse)
async def api_v3_tasks_daily_export_json():
    return PlainTextResponse(json.dumps(v3_tasks_export_daily_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/tasks/daily-ops/export.md", response_class=PlainTextResponse)
async def api_v3_tasks_daily_export_md():
    return PlainTextResponse(v3_tasks_export_daily_md(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/tasks/weekly-plan/export.json", response_class=PlainTextResponse)
async def api_v3_tasks_weekly_export_json():
    return PlainTextResponse(json.dumps(v3_tasks_export_weekly_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/tasks/weekly-plan/export.md", response_class=PlainTextResponse)
async def api_v3_tasks_weekly_export_md():
    return PlainTextResponse(v3_tasks_export_weekly_md(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/tasks/settings")
async def api_v3_tasks_settings_get():
    return v3_tasks_build_settings()


@app.post("/api/v3/tasks/settings")
async def api_v3_tasks_settings_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_update_settings(payload)


@app.get("/api/v3/tasks/{task_id}")
async def api_v3_tasks_get(task_id: str):
    task = v3_tasks_get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="operator task not found")
    return task


@app.post("/api/v3/tasks/{task_id}")
async def api_v3_tasks_update(task_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = v3_tasks_update_task(task_id, payload)
    if result.get("ok") is False:
        raise HTTPException(status_code=404, detail=result.get("error", "task not found"))
    return result


@app.post("/api/v3/tasks/{task_id}/status")
async def api_v3_tasks_status(task_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_change_status(task_id, str(payload.get("status", "planned")), notes=str(payload.get("notes", "")))


@app.post("/api/v3/tasks/{task_id}/complete")
async def api_v3_tasks_complete(task_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_complete_task(task_id, notes=str(payload.get("notes", "")))


@app.post("/api/v3/tasks/{task_id}/archive")
async def api_v3_tasks_archive(task_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_tasks_archive_task(task_id, notes=str(payload.get("notes", "")))


@app.get("/api/v3/workspace/summary")
async def api_v3_workspace_summary():
    return v3_workspace.workspace_summary()


@app.get("/api/v3/workspace/flows")
async def api_v3_workspace_flows(limit: int = 250):
    return v3_workspace.list_guided_flows(limit=limit)


@app.post("/api/v3/workspace/flows")
async def api_v3_workspace_flow_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.create_guided_flow(payload)


@app.get("/api/v3/workspace/flows/{flow_id}")
async def api_v3_workspace_flow_get(flow_id: str):
    flow = v3_workspace.get_guided_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="guided flow not found")
    return flow


@app.post("/api/v3/workspace/flows/{flow_id}")
async def api_v3_workspace_flow_update(flow_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = v3_workspace.update_guided_flow(flow_id, payload)
    if result.get("ok") is False:
        raise HTTPException(status_code=404, detail=result.get("error", "guided flow not found"))
    return result


@app.post("/api/v3/workspace/flows/{flow_id}/start")
async def api_v3_workspace_flow_start(flow_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.start_flow(flow_id, payload)


@app.get("/api/v3/workspace/sessions")
async def api_v3_workspace_sessions(limit: int = 250, status: str = ""):
    return v3_workspace.list_sessions(limit=limit, status=status or None)


@app.get("/api/v3/workspace/sessions/{session_id}")
async def api_v3_workspace_session_get(session_id: str):
    session = v3_workspace.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="guided session not found")
    return session


@app.post("/api/v3/workspace/sessions/{session_id}/step")
async def api_v3_workspace_session_step(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.update_session_step(session_id, payload)


@app.post("/api/v3/workspace/sessions/{session_id}/complete")
async def api_v3_workspace_session_complete(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.complete_session(session_id, payload)


@app.post("/api/v3/workspace/sessions/{session_id}/abandon")
async def api_v3_workspace_session_abandon(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.abandon_session(session_id, payload)


@app.get("/api/v3/workspace/daily-review")
async def api_v3_workspace_daily_review():
    return {"flow": v3_workspace.get_guided_flow("flow_daily_review"), "summary": v3_workspace.workspace_summary()}


@app.post("/api/v3/workspace/daily-review/start")
async def api_v3_workspace_daily_review_start(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.start_daily_review(payload)


@app.get("/api/v3/workspace/weekly-review")
async def api_v3_workspace_weekly_review():
    return {"flow": v3_workspace.get_guided_flow("flow_weekly_review"), "summary": v3_workspace.workspace_summary()}


@app.post("/api/v3/workspace/weekly-review/start")
async def api_v3_workspace_weekly_review_start(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.start_weekly_review(payload)


@app.get("/api/v3/workspace/task-triage")
async def api_v3_workspace_task_triage():
    return {"flow": v3_workspace.get_guided_flow("flow_task_triage"), "summary": v3_workspace.workspace_summary()}


@app.post("/api/v3/workspace/task-triage/start")
async def api_v3_workspace_task_triage_start(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.start_task_triage(payload)


@app.get("/api/v3/workspace/dependencies")
async def api_v3_workspace_dependencies(limit: int = 250):
    return v3_workspace.list_dependencies(limit=limit)


@app.post("/api/v3/workspace/dependencies")
async def api_v3_workspace_dependency_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.create_dependency(payload)


@app.post("/api/v3/workspace/dependencies/{dependency_id}/delete")
async def api_v3_workspace_dependency_delete(dependency_id: str):
    return v3_workspace.delete_dependency(dependency_id)


@app.get("/api/v3/workspace/blocked")
async def api_v3_workspace_blocked():
    return v3_workspace.blocked_review(write=False)


@app.post("/api/v3/workspace/blocked/review")
async def api_v3_workspace_blocked_review(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.blocked_review(payload, write=True)


@app.get("/api/v3/workspace/source-preview")
async def api_v3_workspace_source_preview_list(limit: int = 250):
    return v3_workspace.list_source_previews(limit=limit)


@app.post("/api/v3/workspace/source-preview")
async def api_v3_workspace_source_preview(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.create_source_preview(payload, write=True)


@app.get("/api/v3/workspace/saved-views")
async def api_v3_workspace_saved_views(limit: int = 250):
    return v3_workspace.list_saved_views(limit=limit)


@app.post("/api/v3/workspace/saved-views")
async def api_v3_workspace_saved_view_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.create_saved_view(payload)


@app.get("/api/v3/workspace/review-packets")
async def api_v3_workspace_review_packets(limit: int = 250):
    return v3_workspace.list_review_packets(limit=limit)


@app.post("/api/v3/workspace/review-packets")
async def api_v3_workspace_review_packet_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.generate_review_packet(payload, write=True)


@app.get("/api/v3/workspace/export.json", response_class=PlainTextResponse)
async def api_v3_workspace_export_json():
    return PlainTextResponse(json.dumps(v3_workspace.export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/workspace/export.md", response_class=PlainTextResponse)
async def api_v3_workspace_export_md():
    return PlainTextResponse(v3_workspace.export_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/workspace/export/dependencies.json", response_class=PlainTextResponse)
async def api_v3_workspace_export_dependencies_json():
    return PlainTextResponse(json.dumps(v3_workspace.export_dependency_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/workspace/export/dependencies.md", response_class=PlainTextResponse)
async def api_v3_workspace_export_dependencies_md():
    return PlainTextResponse(v3_workspace.export_dependency_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/workspace/export/saved-views.json", response_class=PlainTextResponse)
async def api_v3_workspace_export_saved_views_json():
    return PlainTextResponse(json.dumps(v3_workspace.export_saved_views_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/workspace/export/saved-views.md", response_class=PlainTextResponse)
async def api_v3_workspace_export_saved_views_md():
    return PlainTextResponse(v3_workspace.export_saved_views_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/workspace/export/dependencies.csv", response_class=PlainTextResponse)
async def api_v3_workspace_export_dependencies_csv():
    return PlainTextResponse(v3_workspace.export_csv("dependencies"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/workspace/export/saved-views.csv", response_class=PlainTextResponse)
async def api_v3_workspace_export_saved_views_csv():
    return PlainTextResponse(v3_workspace.export_csv("saved_views"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/workspace/settings")
async def api_v3_workspace_settings_get():
    return v3_workspace.build_settings()


@app.post("/api/v3/workspace/settings")
async def api_v3_workspace_settings_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_workspace.update_settings(payload)


@app.get("/api/v3/cockpit/summary")
async def api_v3_cockpit_summary():
    return v3_cockpit.cockpit_summary()


@app.get("/api/v3/cockpit/layouts")
async def api_v3_cockpit_layouts(limit: int = 250):
    return v3_cockpit.list_layouts(limit=limit)


@app.post("/api/v3/cockpit/layouts")
async def api_v3_cockpit_layout_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_cockpit.create_layout(payload)


@app.post("/api/v3/cockpit/layouts/reset-defaults")
async def api_v3_cockpit_layouts_reset():
    return v3_cockpit.reset_default_layouts()


@app.post("/api/v3/cockpit/layouts/save-selected")
async def api_v3_cockpit_layout_save_selected(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_cockpit.save_current_layout_copy(str(payload.get("title") or ""))


@app.get("/api/v3/cockpit/layouts/{layout_id}")
async def api_v3_cockpit_layout_get(layout_id: str):
    layout = v3_cockpit.get_layout(layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="cockpit layout not found")
    return layout


@app.post("/api/v3/cockpit/layouts/{layout_id}")
async def api_v3_cockpit_layout_update(layout_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = v3_cockpit.update_layout(layout_id, payload)
    if result.get("ok") is False:
        raise HTTPException(status_code=404, detail=result.get("error", "cockpit layout not found"))
    return result


@app.post("/api/v3/cockpit/layouts/{layout_id}/select")
async def api_v3_cockpit_layout_select(layout_id: str):
    result = v3_cockpit.select_layout(layout_id)
    if result.get("ok") is False:
        raise HTTPException(status_code=404, detail=result.get("error", "cockpit layout not found"))
    return result


@app.get("/api/v3/cockpit/focus-modes")
async def api_v3_cockpit_focus_modes():
    return v3_cockpit.focus_modes()


@app.get("/api/v3/cockpit/focus-modes/{focus_mode_id}")
async def api_v3_cockpit_focus_mode_get(focus_mode_id: str):
    focus = v3_cockpit.get_focus_mode(focus_mode_id)
    if not focus:
        raise HTTPException(status_code=404, detail="cockpit focus mode not found")
    return focus


@app.post("/api/v3/cockpit/focus-modes/{focus_mode_id}/start")
async def api_v3_cockpit_focus_mode_start(focus_mode_id: str):
    result = v3_cockpit.start_focus_mode(focus_mode_id)
    if result.get("ok") is False:
        raise HTTPException(status_code=404, detail=result.get("error", "cockpit focus mode not found"))
    return result


@app.get("/api/v3/cockpit/panels")
async def api_v3_cockpit_panels(limit: int = 250):
    return v3_cockpit.list_panels(limit=limit)


@app.post("/api/v3/cockpit/panels")
async def api_v3_cockpit_panel_create(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_cockpit.create_panel(payload)


@app.get("/api/v3/cockpit/shortcuts")
async def api_v3_cockpit_shortcuts():
    return v3_cockpit.keyboard_shortcuts()


@app.get("/api/v3/cockpit/command-palette")
async def api_v3_cockpit_command_palette():
    return v3_cockpit.command_palette_actions()


@app.post("/api/v3/cockpit/command-palette/run")
async def api_v3_cockpit_command_palette_run(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_cockpit.run_command_palette_action(payload)


@app.get("/api/v3/cockpit/dependencies")
async def api_v3_cockpit_dependencies(task_id: str = ""):
    return v3_cockpit.dependency_view(task_id=task_id)


@app.get("/api/v3/cockpit/source-context")
async def api_v3_cockpit_source_context():
    return v3_cockpit.source_context()


@app.get("/api/v3/cockpit/export.json", response_class=PlainTextResponse)
async def api_v3_cockpit_export_json():
    return PlainTextResponse(json.dumps(v3_cockpit.export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/cockpit/export.md", response_class=PlainTextResponse)
async def api_v3_cockpit_export_md():
    return PlainTextResponse(v3_cockpit.export_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/cockpit/export/focus-modes.json", response_class=PlainTextResponse)
async def api_v3_cockpit_export_focus_json():
    return PlainTextResponse(json.dumps(v3_cockpit.export_focus_mode_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/cockpit/export/focus-modes.md", response_class=PlainTextResponse)
async def api_v3_cockpit_export_focus_md():
    return PlainTextResponse(v3_cockpit.export_focus_mode_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/cockpit/export/command-palette.json", response_class=PlainTextResponse)
async def api_v3_cockpit_export_command_json():
    return PlainTextResponse(json.dumps(v3_cockpit.export_command_palette_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/cockpit/export/command-palette.md", response_class=PlainTextResponse)
async def api_v3_cockpit_export_command_md():
    return PlainTextResponse(v3_cockpit.export_command_palette_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/cockpit/export/shortcuts.json", response_class=PlainTextResponse)
async def api_v3_cockpit_export_shortcuts_json():
    return PlainTextResponse(json.dumps(v3_cockpit.export_shortcuts_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/cockpit/export/shortcuts.md", response_class=PlainTextResponse)
async def api_v3_cockpit_export_shortcuts_md():
    return PlainTextResponse(v3_cockpit.export_shortcuts_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/cockpit/export/layouts.csv", response_class=PlainTextResponse)
async def api_v3_cockpit_export_layouts_csv():
    return PlainTextResponse(v3_cockpit.export_csv("layouts"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/cockpit/export/command-palette.csv", response_class=PlainTextResponse)
async def api_v3_cockpit_export_command_csv():
    return PlainTextResponse(v3_cockpit.export_csv("command_palette"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/cockpit/export/shortcuts.csv", response_class=PlainTextResponse)
async def api_v3_cockpit_export_shortcuts_csv():
    return PlainTextResponse(v3_cockpit.export_csv("shortcuts"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/features/status")
async def api_v3_feature_status():
    return build_feature_status_map()


@app.get("/api/v3/features/stub-burndown")
async def api_v3_feature_stub_burndown():
    return build_stub_burndown_map()


@app.get("/api/v3/features/readiness")
async def api_v3_feature_readiness(status: str = "", area: str = "", limit: int = 50):
    return build_feature_readiness_context(status_filter=status, area_filter=area, limit=limit)


@app.get("/api/v3/features/readiness/acknowledgements")
async def api_v3_feature_readiness_acknowledgements(limit: int = 50):
    return list_feature_readiness_acknowledgements(limit=limit)


@app.post("/api/v3/features/readiness/acknowledgements")
async def api_v3_feature_readiness_acknowledge(payload: dict[str, Any] = Body(default_factory=dict), user: dict = Depends(require_admin)):
    return record_feature_readiness_acknowledgement(
        operator=str(payload.get("operator") or user.get("username", "local")),
        status_filter=str(payload.get("status_filter") or payload.get("status") or ""),
        area_filter=str(payload.get("area_filter") or payload.get("area") or ""),
        note=str(payload.get("note") or payload.get("reason") or ""),
        source_route=str(payload.get("source_route") or "/api/v3/features/readiness/acknowledgements"),
        source_component=str(payload.get("source_component") or "feature_readiness.api_acknowledgement"),
    )


@app.get("/v3/feature-readiness", response_class=HTMLResponse)
@app.get("/feature-readiness", response_class=HTMLResponse)
async def v3_feature_readiness_page(
    request: Request,
    status: str = Query(default=""),
    area: str = Query(default=""),
    action_status: str = Query(default=""),
    action_detail: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    return templates.TemplateResponse(
        "feature_readiness.html",
        {
            "request": request,
            "user": user,
            "context": build_feature_readiness_context(status_filter=status, area_filter=area, limit=25),
            "action_status": action_status,
            "action_detail": action_detail,
        },
    )


@app.post("/v3/feature-readiness/acknowledge")
async def v3_feature_readiness_acknowledge_page(
    status_filter: str = Form(default=""),
    area_filter: str = Form(default=""),
    operator_note: str = Form(default=""),
    return_to: str = Form(default="/v3/feature-readiness"),
    user: dict = Depends(require_admin),
):
    result = record_feature_readiness_acknowledgement(
        operator=str(user.get("username", "local")),
        status_filter=status_filter,
        area_filter=area_filter,
        note=operator_note,
        source_route="/v3/feature-readiness/acknowledge",
        source_component="feature_readiness.acknowledgement_form",
    )
    base = _safe_return_path(return_to, "/v3/feature-readiness")
    suffix = urlencode({"action_status": "feature_readiness_acknowledged", "action_detail": result.get("item", {}).get("acknowledgement_id", "recorded")})
    separator = "&" if "?" in base else "?"
    return RedirectResponse(url=f"{base}{separator}{suffix}", status_code=303)


@app.get("/api/v3/cockpit/settings")
async def api_v3_cockpit_settings_get():
    return v3_cockpit.build_settings()


@app.post("/api/v3/cockpit/settings")
async def api_v3_cockpit_settings_post(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_cockpit.update_settings(payload)


@app.post("/api/v3/demo/create")
async def api_v3_demo_create():
    return v3_create_demo_data()


@app.post("/api/v3/demo/clear")
async def api_v3_demo_clear():
    return v3_clear_demo_data()


@app.get("/api/v3/demo/status")
async def api_v3_demo_status():
    return v3_demo_status()


@app.get("/api/v3/validation/status")
async def api_v3_validation_status():
    return v3_validation_status()


@app.get("/api/v3/exports/pre-trade-packet.md", response_class=PlainTextResponse)
async def api_v3_export_pre_trade_packet_markdown():
    return PlainTextResponse(v3_export_pre_trade_packet_markdown({}), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/exports/operator-review.md", response_class=PlainTextResponse)
async def api_v3_export_operator_review_markdown(period: str = "daily"):
    return PlainTextResponse(v3_export_operator_review_markdown({"period": period}), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/settings")
async def api_v3_settings():
    return v3_build_settings()


@app.post("/api/v3/settings")
async def api_v3_settings_update(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_update_settings(payload)


@app.get("/api/v3/analytics")
async def api_v3_analytics_root():
    return v3_analytics_summary()


@app.get("/api/v3/analytics/summary")
async def api_v3_analytics_summary():
    return v3_analytics_summary()


@app.post("/api/v3/analytics/snapshot")
async def api_v3_analytics_snapshot(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_analytics_snapshot(write=True)


@app.get("/api/v3/analytics/decisions")
async def api_v3_analytics_decisions():
    return v3_analytics_decisions()


@app.get("/api/v3/analytics/theses")
async def api_v3_analytics_theses():
    return v3_analytics_theses()


@app.get("/api/v3/analytics/evidence")
async def api_v3_analytics_evidence():
    return v3_analytics_evidence()


@app.get("/api/v3/analytics/alerts")
async def api_v3_analytics_alerts():
    return v3_analytics_alerts()


@app.get("/api/v3/analytics/governance")
async def api_v3_analytics_governance():
    return v3_analytics_governance()


@app.get("/api/v3/analytics/portfolio")
async def api_v3_analytics_portfolio():
    return v3_analytics_portfolio()


@app.get("/api/v3/analytics/calibration")
async def api_v3_analytics_calibration():
    return v3_analytics_calibration()


@app.get("/api/v3/analytics/mistakes")
async def api_v3_analytics_mistakes():
    return v3_analytics_mistakes()


@app.get("/api/v3/analytics/strengths")
async def api_v3_analytics_strengths():
    return v3_analytics_strengths()


@app.get("/api/v3/analytics/reviews")
async def api_v3_analytics_reviews():
    return v3_analytics_reviews()


@app.post("/api/v3/analytics/learning-report")
async def api_v3_analytics_learning_report(payload: dict[str, Any] = Body(default_factory=dict)):
    return v3_learning_report(period=str(payload.get("period", "weekly")), start_date=str(payload.get("start_date", "")), end_date=str(payload.get("end_date", "")), write=True)


@app.get("/api/v3/analytics/export.json", response_class=PlainTextResponse)
async def api_v3_analytics_export_json():
    return PlainTextResponse(json.dumps(v3_analytics_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v3/analytics/export.md", response_class=PlainTextResponse)
async def api_v3_analytics_export_markdown(period: str = "weekly"):
    return PlainTextResponse(v3_analytics_export_markdown(period=period), media_type="text/markdown; charset=utf-8")


@app.get("/api/v3/analytics/export/decisions.csv", response_class=PlainTextResponse)
async def api_v3_analytics_export_decisions_csv():
    return PlainTextResponse(v3_analytics_export_csv("decisions"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/analytics/export/theses.csv", response_class=PlainTextResponse)
async def api_v3_analytics_export_theses_csv():
    return PlainTextResponse(v3_analytics_export_csv("theses"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/analytics/export/evidence.csv", response_class=PlainTextResponse)
async def api_v3_analytics_export_evidence_csv():
    return PlainTextResponse(v3_analytics_export_csv("evidence"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/analytics/export/alerts.csv", response_class=PlainTextResponse)
async def api_v3_analytics_export_alerts_csv():
    return PlainTextResponse(v3_analytics_export_csv("alerts"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/analytics/export/governance.csv", response_class=PlainTextResponse)
async def api_v3_analytics_export_governance_csv():
    return PlainTextResponse(v3_analytics_export_csv("governance"), media_type="text/csv; charset=utf-8")


@app.get("/api/v3/analytics/export/calibration.csv", response_class=PlainTextResponse)
async def api_v3_analytics_export_calibration_csv():
    return PlainTextResponse(v3_analytics_export_csv("calibration"), media_type="text/csv; charset=utf-8")

@app.get("/docs/{doc_path:path}", response_class=PlainTextResponse)
async def docs_file(doc_path: str):
    docs_root = (APP_DIR.parent / "docs").resolve()
    candidate = (docs_root / doc_path).resolve()
    if docs_root not in candidate.parents and candidate != docs_root:
        raise HTTPException(status_code=404, detail="Document not found")
    if not candidate.exists() or not candidate.is_file() or candidate.suffix.lower() not in {".md", ".txt"}:
        raise HTTPException(status_code=404, detail="Document not found")
    return PlainTextResponse(candidate.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")


@app.get("/api/v2/live/status")
async def api_live_v2_status():
    return build_live_v2_status()


@app.get("/api/v2/live/readiness")
async def api_live_v2_readiness():
    return build_live_v2_readiness()


@app.get("/api/v2/live/demo-readiness")
async def api_live_v2_demo_readiness():
    return build_live_v2_demo_readiness()


@app.get("/api/v2/live/verify")
async def api_live_v2_verify(attempt_network: bool = False, q: str = "polymarket", token_id: str = ""):
    return await build_live_v2_verification_report(attempt_network=attempt_network, market_query=q, token_id=token_id)


@app.get("/api/v2/live/verify/report", response_class=PlainTextResponse)
async def api_live_v2_verify_report(attempt_network: bool = False, q: str = "polymarket", token_id: str = "", format: str = "json"):
    report = await build_live_v2_verification_report(attempt_network=attempt_network, market_query=q, token_id=token_id)
    if format.lower() in {"md", "markdown"}:
        return PlainTextResponse(live_v2_verification_to_markdown(report), media_type="text/markdown; charset=utf-8")
    return PlainTextResponse(json.dumps(report, indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v2/live/verify/report.md", response_class=PlainTextResponse)
async def api_live_v2_verify_report_markdown(attempt_network: bool = False, q: str = "polymarket", token_id: str = ""):
    report = await build_live_v2_verification_report(attempt_network=attempt_network, market_query=q, token_id=token_id)
    return PlainTextResponse(live_v2_verification_to_markdown(report), media_type="text/markdown; charset=utf-8")


@app.get("/api/v2/live/markets")
async def api_live_v2_markets(q: str = "", limit: int = 25):
    return await search_live_v2_markets(query=q, limit=limit)


@app.get("/api/v2/live/orderbook/{token_id}")
async def api_live_v2_orderbook(token_id: str):
    return await get_live_v2_orderbook(token_id)


@app.post("/api/v2/live/ticket/preview")
async def api_live_v2_ticket_preview(payload: dict[str, Any] = Body(default_factory=dict)):
    return build_live_v2_ticket_preview(payload)


@app.post("/api/v2/live/order/submit")
async def api_live_v2_order_submit(payload: dict[str, Any] = Body(default_factory=dict)):
    return submit_live_v2_order(payload)


@app.post("/api/v2/live/order/cancel")
async def api_live_v2_order_cancel(payload: dict[str, Any] = Body(default_factory=dict)):
    return cancel_live_v2_order(payload)


@app.get("/api/v2/live/orders/open")
async def api_live_v2_open_orders():
    return get_live_v2_open_orders()


@app.get("/api/v2/live/positions")
async def api_live_v2_positions():
    return await get_live_v2_positions()


@app.post("/api/v2/live/reconcile")
async def api_live_v2_reconcile():
    return reconcile_live_v2_orders()


@app.get("/api/v2/live/audit")
async def api_live_v2_audit(
    limit: int = 200,
    action: str = "",
    mode: str = "",
    status: str = "",
    market: str = "",
    order_id: str = "",
    search: str = "",
):
    rows = filter_live_v2_audit_records(limit=limit, action=action, mode=mode, status=status, market=market, order_id=order_id, search=search)
    return {"items": rows, "count": len(rows)}


@app.get("/api/v2/live/ui/preferences/schema")
async def api_live_v2_preferences_schema():
    return build_live_v2_preferences_schema()


@app.get("/api/v2/live/audit.csv", response_class=PlainTextResponse)
async def api_live_v2_audit_csv():
    return live_v2_audit_to_csv(list_live_v2_audit_records(limit=10000))


@app.get("/api/v2/live/audit.md", response_class=PlainTextResponse)
async def api_live_v2_audit_markdown():
    return live_v2_audit_to_markdown(list_live_v2_audit_records(limit=500))


@app.get("/api/v2/live/strategy")
async def api_live_v2_strategy():
    return build_strategy_workspace(limit=250)


@app.get("/api/v2/live/strategy/theses")
async def api_live_v2_strategy_theses(status: str = "", limit: int = 200):
    return strategy_list_theses(status=status, limit=limit)


@app.post("/api/v2/live/strategy/theses")
async def api_live_v2_strategy_create_thesis(payload: dict[str, Any] = Body(default_factory=dict)):
    return strategy_create_thesis(payload)


@app.get("/api/v2/live/strategy/theses/{item_id}")
async def api_live_v2_strategy_get_thesis(item_id: str):
    item = get_strategy_item("theses", item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Strategy thesis not found")
    return {"item": item, "secret_values_returned": False}


@app.post("/api/v2/live/strategy/theses/{item_id}")
async def api_live_v2_strategy_update_thesis(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = strategy_update_thesis(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Strategy thesis not found")
    return result


@app.post("/api/v2/live/strategy/theses/{item_id}/archive")
async def api_live_v2_strategy_archive_thesis(item_id: str):
    result = strategy_archive_thesis(item_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Strategy thesis not found")
    return result


@app.post("/api/v2/live/strategy/theses/{item_id}/ticket-draft")
async def api_live_v2_strategy_ticket_from_thesis(item_id: str):
    return build_ticket_from_thesis(item_id)


@app.get("/api/v2/live/strategy/evidence")
async def api_live_v2_strategy_evidence(thesis_id: str = "", limit: int = 200):
    return strategy_list_evidence(thesis_id=thesis_id, limit=limit)


@app.post("/api/v2/live/strategy/evidence")
async def api_live_v2_strategy_create_evidence(payload: dict[str, Any] = Body(default_factory=dict)):
    return strategy_create_evidence(payload)


@app.get("/api/v2/live/strategy/watchlist")
async def api_live_v2_strategy_watchlist(status: str = "", limit: int = 200):
    return strategy_list_watchlist(status=status, limit=limit)


@app.post("/api/v2/live/strategy/watchlist")
async def api_live_v2_strategy_create_watchlist(payload: dict[str, Any] = Body(default_factory=dict)):
    return strategy_create_watchlist_item(payload)


@app.get("/api/v2/live/strategy/scorecards")
async def api_live_v2_strategy_scorecards(thesis_id: str = "", limit: int = 200):
    return strategy_list_scorecards(thesis_id=thesis_id, limit=limit)


@app.post("/api/v2/live/strategy/scorecards")
async def api_live_v2_strategy_create_scorecard(payload: dict[str, Any] = Body(default_factory=dict)):
    return strategy_create_scorecard(payload)


@app.get("/api/v2/live/strategy/reviews")
async def api_live_v2_strategy_reviews(thesis_id: str = "", limit: int = 200):
    return strategy_list_reviews(thesis_id=thesis_id, limit=limit)


@app.post("/api/v2/live/strategy/reviews")
async def api_live_v2_strategy_create_review(payload: dict[str, Any] = Body(default_factory=dict)):
    return strategy_create_review(payload)


@app.get("/api/v2/live/strategy/export.json", response_class=PlainTextResponse)
async def api_live_v2_strategy_export_json():
    return PlainTextResponse(json.dumps(strategy_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v2/live/strategy/export.md", response_class=PlainTextResponse)
async def api_live_v2_strategy_export_markdown():
    return PlainTextResponse(strategy_export_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v2/live/strategy/{collection}.csv", response_class=PlainTextResponse)
async def api_live_v2_strategy_export_csv(collection: str):
    if collection not in {"evidence", "watchlist", "scorecards", "theses"}:
        raise HTTPException(status_code=404, detail="Unsupported strategy CSV collection")
    return PlainTextResponse(strategy_csv(collection), media_type="text/csv; charset=utf-8")


@app.get("/api/v2/live/research")
async def api_live_v2_research():
    return build_research_workspace(limit=250)


@app.get("/api/v2/live/research/sources")
async def api_live_v2_research_sources(status: str = "", limit: int = 200):
    return research_list_sources(status=status, limit=limit)


@app.post("/api/v2/live/research/sources")
async def api_live_v2_research_create_source(payload: dict[str, Any] = Body(default_factory=dict)):
    return research_create_source(payload)


@app.get("/api/v2/live/research/sources/{item_id}")
async def api_live_v2_research_get_source(item_id: str):
    item = get_research_item("sources", item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Research source not found")
    return {"item": item, "secret_values_returned": False}


@app.post("/api/v2/live/research/sources/{item_id}")
async def api_live_v2_research_update_source(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = research_update_source(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Research source not found")
    return result


@app.post("/api/v2/live/research/sources/{item_id}/archive")
async def api_live_v2_research_archive_source(item_id: str):
    result = research_archive_source(item_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Research source not found")
    return result


@app.post("/api/v2/live/research/sources/{item_id}/mark-reviewed")
async def api_live_v2_research_mark_source_reviewed(item_id: str):
    result = research_mark_source_reviewed(item_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Research source not found")
    return result


@app.post("/api/v2/live/research/sources/{item_id}/mark-stale")
async def api_live_v2_research_mark_source_stale(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = research_mark_source_stale(item_id, stale_reason=str(payload.get("stale_reason", "")))
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Research source not found")
    return result


@app.get("/api/v2/live/research/queue")
async def api_live_v2_research_queue(status: str = "", limit: int = 200):
    return research_list_queue(status=status, limit=limit)


@app.post("/api/v2/live/research/queue")
async def api_live_v2_research_create_queue(payload: dict[str, Any] = Body(default_factory=dict)):
    return research_create_queue_item(payload)


@app.post("/api/v2/live/research/queue/{item_id}")
async def api_live_v2_research_update_queue(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = research_update_queue_item(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Research queue item not found")
    return result


@app.get("/api/v2/live/research/notes")
async def api_live_v2_research_notes(source_id: str = "", limit: int = 200):
    return research_list_notes(source_id=source_id, limit=limit)


@app.post("/api/v2/live/research/notes")
async def api_live_v2_research_create_note(payload: dict[str, Any] = Body(default_factory=dict)):
    return research_create_note(payload)


@app.get("/api/v2/live/research/evidence-candidates")
async def api_live_v2_research_candidates(thesis_id: str = "", limit: int = 200):
    return research_list_candidates(thesis_id=thesis_id, limit=limit)


@app.post("/api/v2/live/research/evidence-candidates")
async def api_live_v2_research_create_candidate(payload: dict[str, Any] = Body(default_factory=dict)):
    return research_create_evidence_candidate(payload)


@app.post("/api/v2/live/research/evidence-candidates/{item_id}/convert")
async def api_live_v2_research_convert_candidate(item_id: str):
    result = research_convert_candidate(item_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Evidence candidate not found")
    return result


@app.get("/api/v2/live/research/freshness")
async def api_live_v2_research_freshness():
    return research_freshness_summary()


@app.post("/api/v2/live/research/freshness")
async def api_live_v2_research_update_freshness(payload: dict[str, Any] = Body(default_factory=dict)):
    from .live_research import update_freshness as research_update_freshness
    return research_update_freshness(payload)


@app.get("/api/v2/live/research/thesis-comparison")
async def api_live_v2_research_thesis_comparison(thesis_id: str = ""):
    return research_build_thesis_comparison(thesis_id=thesis_id)


@app.get("/api/v2/live/research/export.json", response_class=PlainTextResponse)
async def api_live_v2_research_export_json():
    return PlainTextResponse(json.dumps(research_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v2/live/research/export.md", response_class=PlainTextResponse)
async def api_live_v2_research_export_markdown():
    return PlainTextResponse(research_export_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v2/live/research/{collection}.csv", response_class=PlainTextResponse)
async def api_live_v2_research_export_csv(collection: str):
    if collection not in {"sources", "queue", "evidence-candidates", "stale", "notes"}:
        raise HTTPException(status_code=404, detail="Unsupported research CSV collection")
    return PlainTextResponse(research_csv(collection), media_type="text/csv; charset=utf-8")


@app.get("/api/v2/live/monitoring")
async def api_live_v2_monitoring():
    return build_monitoring_workspace(limit=250)


@app.get("/api/v2/live/monitoring/rules")
async def api_live_v2_monitoring_rules(status: str = "", limit: int = 200):
    return monitoring_list_rules(status=status, limit=limit)


@app.post("/api/v2/live/monitoring/rules")
async def api_live_v2_monitoring_create_rule(payload: dict[str, Any] = Body(default_factory=dict)):
    return monitoring_create_rule(payload)


@app.get("/api/v2/live/monitoring/rules/{item_id}")
async def api_live_v2_monitoring_get_rule(item_id: str):
    item = get_monitoring_item("rules", item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Monitoring rule not found")
    return {"item": item, "secret_values_returned": False}


@app.post("/api/v2/live/monitoring/rules/{item_id}")
async def api_live_v2_monitoring_update_rule(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = monitoring_update_rule(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Monitoring rule not found")
    return result


@app.post("/api/v2/live/monitoring/rules/{item_id}/evaluate")
async def api_live_v2_monitoring_evaluate_rule(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = monitoring_evaluate_rule(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Monitoring rule not found")
    return result


@app.post("/api/v2/live/monitoring/rules/{item_id}/disable")
async def api_live_v2_monitoring_disable_rule(item_id: str):
    result = monitoring_disable_rule(item_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Monitoring rule not found")
    return result


@app.post("/api/v2/live/monitoring/rules/{item_id}/archive")
async def api_live_v2_monitoring_archive_rule(item_id: str):
    result = monitoring_archive_rule(item_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Monitoring rule not found")
    return result


@app.get("/api/v2/live/monitoring/alerts")
async def api_live_v2_monitoring_alerts(status: str = "", severity: str = "", limit: int = 200):
    return monitoring_list_alerts(status=status, severity=severity, limit=limit)


@app.post("/api/v2/live/monitoring/alerts/{alert_id}/acknowledge")
async def api_live_v2_monitoring_acknowledge_alert(alert_id: str):
    result = monitoring_acknowledge_alert(alert_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Monitoring alert not found")
    return result


@app.post("/api/v2/live/monitoring/alerts/{alert_id}/snooze")
async def api_live_v2_monitoring_snooze_alert(alert_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = monitoring_snooze_alert(alert_id, minutes=int(payload.get("minutes", 60) or 60))
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Monitoring alert not found")
    return result


@app.get("/api/v2/live/monitoring/history")
async def api_live_v2_monitoring_history(limit: int = 500):
    return monitoring_list_history(limit=limit)


@app.post("/api/v2/live/monitoring/evaluate")
async def api_live_v2_monitoring_evaluate_all(payload: dict[str, Any] = Body(default_factory=dict)):
    return monitoring_evaluate_all(payload)


@app.get("/api/v2/live/monitoring/export.json", response_class=PlainTextResponse)
async def api_live_v2_monitoring_export_json():
    return PlainTextResponse(json.dumps(monitoring_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v2/live/monitoring/export.md", response_class=PlainTextResponse)
async def api_live_v2_monitoring_export_markdown():
    return PlainTextResponse(monitoring_export_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v2/live/monitoring/export/{collection}.csv", response_class=PlainTextResponse)
async def api_live_v2_monitoring_export_csv(collection: str):
    if collection not in {"rules", "alerts", "active_alerts", "history"}:
        raise HTTPException(status_code=404, detail="Unsupported monitoring CSV collection")
    return PlainTextResponse(monitoring_csv(collection), media_type="text/csv; charset=utf-8")


@app.get("/api/v2/live/portfolio")
async def api_live_v2_portfolio():
    return build_portfolio_workspace(limit=250)


@app.get("/api/v2/live/portfolio/snapshot")
async def api_live_v2_portfolio_snapshot():
    return generate_portfolio_snapshot(record=False)


@app.post("/api/v2/live/portfolio/snapshot")
async def api_live_v2_portfolio_create_snapshot():
    return generate_portfolio_snapshot(record=True)


@app.get("/api/v2/live/portfolio/exposure")
async def api_live_v2_portfolio_exposure(limit: int = 500):
    return portfolio_list_exposure(limit=limit)


@app.get("/api/v2/live/portfolio/bankroll")
async def api_live_v2_portfolio_bankroll():
    return {"item": portfolio_get_bankroll_settings(), "secret_values_returned": False}


@app.post("/api/v2/live/portfolio/bankroll")
async def api_live_v2_portfolio_update_bankroll(payload: dict[str, Any] = Body(default_factory=dict)):
    return portfolio_update_bankroll(payload)


@app.get("/api/v2/live/portfolio/warnings")
async def api_live_v2_portfolio_warnings(limit: int = 500):
    return portfolio_list_warnings(limit=limit)


@app.post("/api/v2/live/portfolio/exposure-groups")
async def api_live_v2_portfolio_create_exposure_group(payload: dict[str, Any] = Body(default_factory=dict)):
    return portfolio_create_exposure_group(payload)


@app.post("/api/v2/live/portfolio/exposure-groups/{item_id}")
async def api_live_v2_portfolio_update_exposure_group(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = portfolio_update_exposure_group(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Portfolio exposure group not found")
    return result


@app.get("/api/v2/live/portfolio/scenarios")
async def api_live_v2_portfolio_scenarios(limit: int = 200):
    return portfolio_list_scenarios(limit=limit)


@app.post("/api/v2/live/portfolio/scenarios")
async def api_live_v2_portfolio_create_scenario(payload: dict[str, Any] = Body(default_factory=dict)):
    return portfolio_create_scenario(payload)


@app.post("/api/v2/live/portfolio/scenarios/{item_id}/evaluate")
async def api_live_v2_portfolio_evaluate_scenario(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = portfolio_evaluate_scenario(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Portfolio scenario not found")
    return result


@app.post("/api/v2/live/portfolio/planned-impact")
async def api_live_v2_portfolio_planned_impact(payload: dict[str, Any] = Body(default_factory=dict)):
    return portfolio_planned_trade_impact(payload)


@app.get("/api/v2/live/portfolio/export.json", response_class=PlainTextResponse)
async def api_live_v2_portfolio_export_json():
    return PlainTextResponse(json.dumps(portfolio_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v2/live/portfolio/export.md", response_class=PlainTextResponse)
async def api_live_v2_portfolio_export_markdown():
    return PlainTextResponse(portfolio_export_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v2/live/portfolio/export/{collection}.csv", response_class=PlainTextResponse)
async def api_live_v2_portfolio_export_csv(collection: str):
    if collection not in {"exposure", "warnings", "scenarios"}:
        raise HTTPException(status_code=404, detail="Unsupported portfolio CSV collection")
    return PlainTextResponse(portfolio_csv(collection), media_type="text/csv; charset=utf-8")


@app.get("/api/v2/live/governance")
async def api_live_v2_governance():
    return build_governance_workspace(limit=250)


@app.get("/api/v2/live/governance/journal")
async def api_live_v2_governance_journal(status: str = "", limit: int = 200):
    return governance_list_journal(status=status, limit=limit)


@app.post("/api/v2/live/governance/journal")
async def api_live_v2_governance_create_journal(payload: dict[str, Any] = Body(default_factory=dict)):
    return governance_create_journal_entry(payload)


@app.post("/api/v2/live/governance/journal/{item_id}")
async def api_live_v2_governance_update_journal(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = governance_update_journal_entry(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Governance journal entry not found")
    return result


@app.get("/api/v2/live/governance/checklists")
async def api_live_v2_governance_checklists(status: str = "", limit: int = 200):
    return governance_list_checklists(status=status, limit=limit)


@app.post("/api/v2/live/governance/checklists")
async def api_live_v2_governance_create_checklist(payload: dict[str, Any] = Body(default_factory=dict)):
    return governance_create_checklist(payload)


@app.post("/api/v2/live/governance/checklists/{item_id}")
async def api_live_v2_governance_update_checklist(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = governance_update_checklist(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Governance checklist not found")
    return result


@app.get("/api/v2/live/governance/reviews")
async def api_live_v2_governance_reviews(status: str = "", limit: int = 200):
    return governance_list_reviews(status=status, limit=limit)


@app.post("/api/v2/live/governance/reviews")
async def api_live_v2_governance_create_review(payload: dict[str, Any] = Body(default_factory=dict)):
    return governance_create_review(payload)


@app.post("/api/v2/live/governance/reviews/{item_id}")
async def api_live_v2_governance_update_review(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = governance_update_review(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Governance review not found")
    return result


@app.get("/api/v2/live/governance/rules")
async def api_live_v2_governance_rules(status: str = "", limit: int = 200):
    return governance_list_rules(status=status, limit=limit)


@app.post("/api/v2/live/governance/rules")
async def api_live_v2_governance_create_rule(payload: dict[str, Any] = Body(default_factory=dict)):
    return governance_create_rule(payload)


@app.post("/api/v2/live/governance/rules/{item_id}")
async def api_live_v2_governance_update_rule(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = governance_update_rule(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Governance rule not found")
    return result


@app.get("/api/v2/live/governance/near-misses")
async def api_live_v2_governance_near_misses(status: str = "", limit: int = 200):
    return governance_list_near_misses(status=status, limit=limit)


@app.post("/api/v2/live/governance/near-misses")
async def api_live_v2_governance_create_near_miss(payload: dict[str, Any] = Body(default_factory=dict)):
    return governance_create_near_miss(payload)


@app.get("/api/v2/live/governance/mistake-patterns")
async def api_live_v2_governance_mistake_patterns(status: str = "", limit: int = 200):
    return governance_list_mistake_patterns(status=status, limit=limit)


@app.post("/api/v2/live/governance/mistake-patterns")
async def api_live_v2_governance_create_mistake_pattern(payload: dict[str, Any] = Body(default_factory=dict)):
    return governance_create_mistake_pattern(payload)


@app.post("/api/v2/live/governance/mistake-patterns/{item_id}")
async def api_live_v2_governance_update_mistake_pattern(item_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    result = governance_update_mistake_pattern(item_id, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Governance mistake pattern not found")
    return result


@app.get("/api/v2/live/governance/export.json", response_class=PlainTextResponse)
async def api_live_v2_governance_export_json():
    return PlainTextResponse(json.dumps(governance_export_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v2/live/governance/export.md", response_class=PlainTextResponse)
async def api_live_v2_governance_export_markdown():
    return PlainTextResponse(governance_export_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v2/live/governance/export/{collection}.csv", response_class=PlainTextResponse)
async def api_live_v2_governance_export_csv(collection: str):
    if collection not in {"journal", "checklists", "mistakes", "near-misses", "rules", "reviews"}:
        raise HTTPException(status_code=404, detail="Unsupported governance CSV collection")
    return PlainTextResponse(governance_csv(collection), media_type="text/csv; charset=utf-8")


@app.get("/api/v2/live/data")
async def api_live_v2_data():
    return build_data_workspace(limit=250)


@app.get("/api/v2/live/data/health")
async def api_live_v2_data_health():
    return data_health_report_json()


@app.post("/api/v2/live/data/health/run")
async def api_live_v2_data_health_run(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_run_health_check(deep=bool(payload.get("deep", False)))


@app.get("/api/v2/live/data/inventory")
async def api_live_v2_data_inventory():
    return data_runtime_inventory()


@app.get("/api/v2/live/data/secrets/scan")
async def api_live_v2_data_secret_scan():
    return data_scan_secrets()


@app.post("/api/v2/live/data/backup")
async def api_live_v2_data_backup(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_create_backup_bundle(payload)


@app.get("/api/v2/live/data/backups")
async def api_live_v2_data_backups():
    return data_list_backups()


@app.post("/api/v2/live/data/backup/validate")
async def api_live_v2_data_backup_validate(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_validate_backup_bundle(payload)


@app.post("/api/v2/live/data/restore/preview")
async def api_live_v2_data_restore_preview(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_restore_preview(payload)


@app.post("/api/v2/live/data/restore/apply")
async def api_live_v2_data_restore_apply(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_restore_apply(payload)


@app.post("/api/v2/live/data/export")
async def api_live_v2_data_export(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_export_bundle(payload)


@app.post("/api/v2/live/data/import/preview")
async def api_live_v2_data_import_preview(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_import_preview(payload)


@app.post("/api/v2/live/data/import/apply")
async def api_live_v2_data_import_apply(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_import_apply(payload)


@app.get("/api/v2/live/data/migrations")
async def api_live_v2_data_migrations():
    return data_migration_registry()


@app.post("/api/v2/live/data/migrations/dry-run")
async def api_live_v2_data_migrations_dry_run(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_migration_dry_run(payload)


@app.post("/api/v2/live/data/migrations/apply")
async def api_live_v2_data_migrations_apply(payload: dict[str, Any] = Body(default_factory=dict)):
    return data_migration_apply(payload)


@app.get("/api/v2/live/data/reports/health.json", response_class=PlainTextResponse)
async def api_live_v2_data_report_health_json():
    return PlainTextResponse(json.dumps(data_health_report_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v2/live/data/reports/health.md", response_class=PlainTextResponse)
async def api_live_v2_data_report_health_md():
    return PlainTextResponse(data_health_report_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v2/live/data/reports/recovery.json", response_class=PlainTextResponse)
async def api_live_v2_data_report_recovery_json():
    return PlainTextResponse(json.dumps(data_recovery_report_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")


@app.get("/api/v2/live/data/reports/recovery.md", response_class=PlainTextResponse)
async def api_live_v2_data_report_recovery_md():
    return PlainTextResponse(data_recovery_report_markdown(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v2/live/data/reports/checks.csv", response_class=PlainTextResponse)
async def api_live_v2_data_report_checks_csv():
    return PlainTextResponse(data_checks_csv(), media_type="text/csv; charset=utf-8")


@app.get("/api/v2/live/settings/schema")
async def api_live_v2_settings_schema():
    return {"version": APP_VERSION, "sections": build_live_v2_settings_sections(), "secret_values_returned": False}


@app.post("/api/v2/live/settings/validate")
async def api_live_v2_settings_validate(payload: dict[str, Any] = Body(default_factory=dict)):
    return validate_live_v2_settings_payload(payload)


@app.post("/api/v2/live/emergency")
async def api_live_v2_emergency(payload: dict[str, Any] = Body(default_factory=dict)):
    return emergency_live_v2_action(payload)


@app.get("/live-clob-adapter", response_class=HTMLResponse)
async def live_clob_adapter_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("live_clob_adapter_v011.html", {"request": request, "user": user, "report": build_clob_adapter_status(), "verification": build_live_adapter_verification()})


@app.get("/api/live/clob-adapter/status")
async def live_clob_adapter_status_api(user: dict = Depends(require_admin)):
    return build_clob_adapter_status()


@app.get("/api/live/clob-adapter/status.csv", response_class=PlainTextResponse)
async def live_clob_adapter_status_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(clob_adapter_status_to_csv(build_clob_adapter_status()), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=live_clob_adapter_status.csv"})


@app.get("/api/live/clob-adapter/verification")
async def live_clob_adapter_verification_api(user: dict = Depends(require_admin)):
    return build_live_adapter_verification()


@app.post("/api/live/clob-adapter/verification/run")
async def live_clob_adapter_verification_run_api(
    operator: str = Form(default="local"),
    request_readonly_network: bool = Form(default=False),
    request_real_smoke: bool = Form(default=False),
    user: dict = Depends(require_admin),
):
    return build_live_adapter_verification(run=True, operator=operator or user.get("username", "local"), request_readonly_network=request_readonly_network, request_real_smoke=request_real_smoke)


@app.get("/api/live/clob-adapter/verification.csv", response_class=PlainTextResponse)
async def live_clob_adapter_verification_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(live_adapter_verification_to_csv(build_live_adapter_verification()), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=live_clob_adapter_verification.csv"})

@app.get("/live-trading", response_class=HTMLResponse)
async def live_trading_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("live_trading_v010.html", {"request": request, "user": user, "status": build_live_trading_status(), "orders": build_live_order_board(limit=25), "autonomous": build_autonomous_status(), "checklist": build_live_readiness_checklist()})


@app.get("/live-orders", response_class=HTMLResponse)
async def live_orders_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("live_orders_v010.html", {"request": request, "user": user, "board": build_live_order_board(limit=100)})


@app.get("/live-reconciliation", response_class=HTMLResponse)
async def live_reconciliation_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("live_reconciliation_v010.html", {"request": request, "user": user, "report": build_live_reconciliation()})


@app.get("/strategy-signals", response_class=HTMLResponse)
async def strategy_signals_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("strategy_signals_v010.html", {"request": request, "user": user, "board": build_strategy_signal_board(limit=100)})


@app.get("/autonomous-trading", response_class=HTMLResponse)
async def autonomous_trading_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("autonomous_trading_v010.html", {"request": request, "user": user, "status": build_autonomous_status(), "preview": build_autonomous_run_preview(mode="off", operator=user.get("username", "local"))})


@app.get("/autonomous-runs", response_class=HTMLResponse)
async def autonomous_runs_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("autonomous_runs_v010.html", {"request": request, "user": user, "items": list_autonomous_runs(limit=100)})


@app.get("/operator-runbook", response_class=HTMLResponse)
async def operator_runbook_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("operator_runbook_v110.html", {"request": request, "user": user, "runbook": build_operator_runbook()})


@app.get("/api/operator-runbook")
async def operator_runbook_api(user: dict = Depends(require_admin)):
    return build_operator_runbook()


@app.get("/api/live/trading/status")
async def live_trading_status_api(user: dict = Depends(require_admin)):
    return build_live_trading_status()


@app.get("/api/live/trading/readiness-checklist")
async def live_readiness_checklist_api(user: dict = Depends(require_admin)):
    return build_live_readiness_checklist()


@app.get("/api/live/trading/readiness-checklist.csv", response_class=PlainTextResponse)
async def live_readiness_checklist_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(live_readiness_checklist_to_csv(build_live_readiness_checklist()), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=live_readiness_checklist.csv"})


@app.get("/api/live/orders")
async def live_orders_api(limit: int = Query(default=100, ge=1, le=1000), status: str | None = Query(default=None), user: dict = Depends(require_admin)):
    return {"source": "local", **build_live_order_board(limit=limit, status=status)}


@app.get("/api/live/orders.csv", response_class=PlainTextResponse)
async def live_orders_csv(limit: int = Query(default=10000, ge=1, le=10000), user: dict = Depends(require_admin)):
    return PlainTextResponse(live_orders_to_csv(list_live_order_events(limit=limit)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=live_orders.csv"})


@app.get("/api/live/orders/{order_event_id}")
async def live_order_detail_api(order_event_id: str, user: dict = Depends(require_admin)):
    item = get_live_order_event(order_event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Live order event not found")
    return {"source": "local", "item": item}


@app.post("/api/live/adapter/requests/{adapter_request_id}/manual-submit-preview")
async def live_manual_submit_preview_alias_api(adapter_request_id: str, operator: str = Form(default="local"), final_confirmation: str = Form(default=""), adapter_mode: str = Form(default="blocked"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return await live_manual_submit_preview_api(adapter_request_id, operator, final_confirmation, adapter_mode, note, user)


@app.post("/api/live/orders/{order_id}/cancel-preview")
async def live_order_cancel_preview_alias_api(
    order_id: str,
    operator: str = Form(default="local"),
    final_confirmation: str = Form(default=""),
    adapter_mode: str = Form(default="blocked"),
    reason: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = build_manual_cancel_preview(
        original_attempt_id=order_id,
        fake_order_id=order_id,
        operator=operator or user.get("username", "local"),
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        reason=reason,
        note=note,
    )
    return {"ok": True, "recorded": False, "item": item}


@app.post("/api/live/orders/{order_id}/cancel")
async def live_order_cancel_alias_api(
    order_id: str,
    operator: str = Form(default="local"),
    final_confirmation: str = Form(default=""),
    adapter_mode: str = Form(default="blocked"),
    reason: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_manual_cancel_attempt(
        original_attempt_id=order_id,
        fake_order_id=order_id,
        operator=operator or user.get("username", "local"),
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        reason=reason,
        note=note,
    )
    return {"ok": True, "recorded": True, "item": item}


@app.post("/api/live/reconciliation/preview")
async def live_reconciliation_preview_api(user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "report": build_live_reconciliation()}


@app.post("/api/live/reconciliation/record")
async def live_reconciliation_record_api(user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": True, "report": build_live_reconciliation()}


@app.get("/api/live/reconciliation")
async def live_reconciliation_api(user: dict = Depends(require_admin)):
    return build_live_reconciliation()


@app.get("/api/live/reconciliation.csv", response_class=PlainTextResponse)
async def live_reconciliation_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(live_reconciliation_to_csv(build_live_reconciliation()), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=live_reconciliation.csv"})


@app.get("/api/strategy-signals")
async def strategy_signals_api(limit: int = Query(default=100, ge=1, le=1000), status: str | None = Query(default=None), user: dict = Depends(require_admin)):
    return {"source": "local", **build_strategy_signal_board(limit=limit, status=status)}


@app.get("/api/strategy-signals.csv", response_class=PlainTextResponse)
async def strategy_signals_csv(limit: int = Query(default=10000, ge=1, le=10000), user: dict = Depends(require_admin)):
    return PlainTextResponse(strategy_signals_to_csv(list_strategy_signals(limit=limit)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=strategy_signals.csv"})


@app.get("/api/strategy-signals/{signal_id}")
async def strategy_signal_detail_api(signal_id: str, user: dict = Depends(require_admin)):
    item = get_strategy_signal(signal_id)
    if not item:
        raise HTTPException(status_code=404, detail="Strategy signal not found")
    return {"source": "local", "item": item}


@app.post("/api/strategy-signals/validate-preview")
async def strategy_signal_validate_api(strategy_id: str = Form(default="manual"), market_id: str = Form(default=""), token_id: str = Form(default=""), side: str = Form(default="BUY"), limit_price: float = Form(default=0.5), size: float = Form(default=1.0), confidence: float = Form(default=0.0), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "validation": validate_strategy_signal_payload({"strategy_id": strategy_id, "market_id": market_id, "token_id": token_id, "side": side, "limit_price": limit_price, "size": size, "confidence": confidence})}


@app.post("/api/strategy-signals")
async def strategy_signal_create_api(strategy_id: str = Form(default="manual"), market_id: str = Form(default=""), token_id: str = Form(default=""), side: str = Form(default="BUY"), limit_price: float = Form(default=0.5), size: float = Form(default=1.0), confidence: float = Form(default=0.0), rationale: str = Form(default=""), expires_at: str = Form(default=""), source: str = Form(default="manual"), paper_ticket_id: str = Form(default=""), approval_id: str = Form(default=""), snapshot_id: str = Form(default=""), execution_quality_id: str = Form(default=""), adapter_request_id: str = Form(default=""), user: dict = Depends(require_admin)):
    item = record_strategy_signal(strategy_id=strategy_id, market_id=market_id, token_id=token_id, side=side, limit_price=limit_price, size=size, confidence=confidence, rationale=rationale, expires_at=expires_at, source=source, paper_ticket_id=paper_ticket_id, approval_id=approval_id, snapshot_id=snapshot_id, execution_quality_id=execution_quality_id, adapter_request_id=adapter_request_id)
    return {"ok": True, "recorded": True, "item": item}


@app.get("/api/autonomous-trading/status")
async def autonomous_trading_status_api(user: dict = Depends(require_admin)):
    return build_autonomous_status()


@app.post("/api/autonomous-trading/run-preview")
async def autonomous_run_preview_api(mode: str = Form(default="off"), operator: str = Form(default="local"), limit: int = Form(default=50), strategy_id: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "run": build_autonomous_run_preview(mode=mode, operator=operator or user.get("username", "local"), limit=limit, strategy_id=strategy_id or None)}


@app.post("/api/autonomous-trading/run")
async def autonomous_run_record_api(mode: str = Form(default="off"), operator: str = Form(default="local"), limit: int = Form(default=50), strategy_id: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": True, "run": record_autonomous_run(mode=mode, operator=operator or user.get("username", "local"), limit=limit, strategy_id=strategy_id or None)}


@app.get("/api/autonomous-runs")
async def autonomous_runs_api(limit: int = Query(default=100, ge=1, le=1000), mode: str | None = Query(default=None), user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_autonomous_runs(limit=limit, mode=mode)}


@app.get("/api/autonomous-runs.csv", response_class=PlainTextResponse)
async def autonomous_runs_csv(limit: int = Query(default=10000, ge=1, le=10000), user: dict = Depends(require_admin)):
    return PlainTextResponse(autonomous_runs_to_csv(list_autonomous_runs(limit=limit)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=autonomous_runs.csv"})


@app.get("/api/autonomous-runs/{run_id}")
async def autonomous_run_detail_api(run_id: str, user: dict = Depends(require_admin)):
    item = get_autonomous_run(run_id)
    if not item:
        raise HTTPException(status_code=404, detail="Autonomous run not found")
    return {"source": "local", "item": item}


@app.get("/live-config", response_class=HTMLResponse)
async def live_config_page(request: Request, user: dict = Depends(require_admin)):
    report = build_live_config_readiness()
    return templates.TemplateResponse(
        "live_config_v055.html",
        {
            "request": request,
            "user": user,
            "report": report,
            "summary": report.get("summary", {}),
            "fields": report.get("fields", []),
            "controls": report.get("controls", {}),
        },
    )


@app.get("/api/live/order-intents")
async def live_order_intents_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_live_order_intent_board(limit=limit, status=status, market_id=market_id, operator=operator),
    }


@app.get("/api/live/order-intents.csv", response_class=PlainTextResponse)
async def live_order_intents_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_order_intents(limit=limit, status=status, market_id=market_id, operator=operator)
    return PlainTextResponse(
        live_order_intents_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_order_intents.csv"},
    )



@app.get("/api/live/order-intents/preflight")
async def live_order_intent_preflight_api(
    limit: int = Query(default=100, ge=1, le=1000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_live_order_preflight_board(limit=limit, state=state, market_id=market_id, operator=operator),
    }


@app.get("/api/live/order-intents/preflight.csv", response_class=PlainTextResponse)
async def live_order_intent_preflight_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_order_preflights(limit=limit, state=state, market_id=market_id, operator=operator)
    return PlainTextResponse(
        live_order_preflights_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_order_intent_preflight.csv"},
    )


@app.get("/api/live/order-intents/{intent_id}/preflight")
async def live_order_intent_preflight_detail_api(intent_id: str, user: dict = Depends(require_admin)):
    item = review_live_order_intent(intent_id)
    if not item:
        raise HTTPException(status_code=404, detail="Live order intent not found")
    return {"source": "local", "item": item}


@app.get("/api/live/order-intents/authorizations")
async def live_order_authorizations_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_live_order_authorization_board(limit=limit, status=status, decision=decision, market_id=market_id, operator=operator, intent_id=intent_id),
    }


@app.get("/api/live/order-intents/authorizations.csv", response_class=PlainTextResponse)
async def live_order_authorizations_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_order_authorizations(limit=limit, status=status, decision=decision, market_id=market_id, operator=operator, intent_id=intent_id)
    return PlainTextResponse(
        live_order_authorizations_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_order_authorizations.csv"},
    )


@app.get("/api/live/order-intents/authorizations/{authorization_id}")
async def live_order_authorization_detail_api(authorization_id: str, user: dict = Depends(require_admin)):
    item = get_live_order_authorization(authorization_id)
    if not item:
        raise HTTPException(status_code=404, detail="Live order authorization not found")
    return {"source": "local", "item": item}


@app.post("/api/live/order-intents/{intent_id}/authorization")
async def live_order_authorization_create_api(
    intent_id: str,
    decision: str = Query(default="authorize"),
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    acknowledged: bool = Query(default=False),
    user: dict = Depends(require_admin),
):
    item = record_live_order_authorization(
        intent_id=intent_id,
        decision=decision,
        operator=operator or user.get("username", "local"),
        note=note,
        acknowledged=acknowledged,
    )
    return {"ok": True, "recorded": True, "item": item}


@app.get("/api/live/execution-packets")
async def live_execution_packets_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    authorization_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    return {
        "source": "local",
        **build_live_execution_packet_board(limit=limit, status=status, market_id=market_id, operator=operator, intent_id=intent_id, authorization_id=authorization_id),
    }


@app.get("/api/live/execution-packets.csv", response_class=PlainTextResponse)
async def live_execution_packets_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    authorization_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    rows = list_live_execution_packets(limit=limit, status=status, market_id=market_id, operator=operator, intent_id=intent_id, authorization_id=authorization_id)
    return PlainTextResponse(
        live_execution_packets_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=live_execution_packets.csv"},
    )


@app.get("/api/live/execution-packets/{packet_id}")
async def live_execution_packet_detail_api(packet_id: str, user: dict = Depends(require_admin)):
    item = get_live_execution_packet(packet_id)
    if not item:
        raise HTTPException(status_code=404, detail="Live execution packet not found")
    return {"source": "local", "item": item}


@app.post("/api/live/order-intents/{intent_id}/execution-packet")
async def live_execution_packet_create_api(
    intent_id: str,
    authorization_id: str = Query(default=""),
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_execution_packet(
        intent_id=intent_id,
        authorization_id=authorization_id or None,
        operator=operator or user.get("username", "local"),
        note=note,
    )
    return {"ok": True, "recorded": True, "item": item}


@app.post("/api/live/order-intents/{intent_id}/execution-packet/preview")
async def live_execution_packet_preview_api(
    intent_id: str,
    authorization_id: str = Query(default=""),
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = build_live_execution_packet(
        intent_id=intent_id,
        authorization_id=authorization_id or None,
        operator=operator or user.get("username", "local"),
        note=note,
    )
    return {"ok": True, "recorded": False, "item": item}

@app.get("/api/live/order-intents/{intent_id}")
async def live_order_intent_detail_api(intent_id: str, user: dict = Depends(require_admin)):
    record = get_live_order_intent(intent_id)
    if not record:
        raise HTTPException(status_code=404, detail="Live order intent not found")
    return {"source": "local", "item": record}


@app.post("/api/live/order-intents/preview")
async def live_order_intent_preview_api(
    market_id: str = Query(...),
    outcome: str = Query(default="YES"),
    side: str = Query(default="BUY"),
    price: float = Query(default=0.5, gt=0),
    size: float = Query(default=1.0, gt=0),
    token_id: str = Query(default=""),
    order_type: str = Query(default="limit"),
    time_in_force: str = Query(default="GTC"),
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    source_ticket_id: str = Query(default=""),
    source_approval_id: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = build_live_order_intent(
        market_id=market_id,
        outcome=outcome,
        side=side,
        price=price,
        size=size,
        token_id=token_id,
        order_type=order_type,
        time_in_force=time_in_force,
        operator=operator or user.get("username", "local"),
        note=note,
        source_ticket_id=source_ticket_id,
        source_approval_id=source_approval_id,
    )
    return {"ok": True, "recorded": False, "item": item}


@app.post("/api/live/order-intents")
async def live_order_intent_create_api(
    market_id: str = Query(...),
    outcome: str = Query(default="YES"),
    side: str = Query(default="BUY"),
    price: float = Query(default=0.5, gt=0),
    size: float = Query(default=1.0, gt=0),
    token_id: str = Query(default=""),
    order_type: str = Query(default="limit"),
    time_in_force: str = Query(default="GTC"),
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    source_ticket_id: str = Query(default=""),
    source_approval_id: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_order_intent(
        market_id=market_id,
        outcome=outcome,
        side=side,
        price=price,
        size=size,
        token_id=token_id,
        order_type=order_type,
        time_in_force=time_in_force,
        operator=operator or user.get("username", "local"),
        note=note,
        source_ticket_id=source_ticket_id,
        source_approval_id=source_approval_id,
    )
    return {"ok": True, "recorded": True, "item": item}


@app.get("/live-order-intents", response_class=HTMLResponse)
async def live_order_intents_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_order_intent_board(limit=limit, status=status, market_id=market_id, operator=operator)
    return templates.TemplateResponse(
        "live_order_intents_v056.html",
        {
            "request": request,
            "user": user,
            "generated_at": board.get("generated_at"),
            "guardrail": board.get("guardrail"),
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "sample_preview": board.get("sample_preview", {}),
            "limit": limit,
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "default_operator": (user or {}).get("username") or "local",
        },
    )



@app.get("/live-order-intent-preflight", response_class=HTMLResponse)
async def live_order_intent_preflight_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_order_preflight_board(limit=limit, state=state, market_id=market_id, operator=operator)
    return templates.TemplateResponse(
        "live_order_intent_preflight_v057.html",
        {
            "request": request,
            "user": user,
            "generated_at": board.get("generated_at"),
            "guardrail": board.get("guardrail"),
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "limit": limit,
            "state": state or "",
            "market_id": market_id or "",
            "operator": operator or "",
        },
    )


@app.get("/live-order-authorizations", response_class=HTMLResponse)
async def live_order_authorizations_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_order_authorization_board(limit=limit, status=status, decision=decision, market_id=market_id, operator=operator, intent_id=intent_id)
    preflight_board = build_live_order_preflight_board(limit=25, state=None, market_id=market_id, operator=operator)
    return templates.TemplateResponse(
        "live_order_authorizations_v058.html",
        {
            "request": request,
            "user": user,
            "generated_at": board.get("generated_at"),
            "guardrail": board.get("guardrail"),
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "preflight_items": preflight_board.get("items", []),
            "limit": limit,
            "status": status or "",
            "decision": decision or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "intent_id": intent_id or "",
            "default_operator": (user or {}).get("username") or "local",
        },
    )


@app.get("/live-execution-packets", response_class=HTMLResponse)
async def live_execution_packets_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    authorization_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_execution_packet_board(limit=limit, status=status, market_id=market_id, operator=operator, intent_id=intent_id, authorization_id=authorization_id)
    authorization_board = build_live_order_authorization_board(limit=25, status=None, decision="authorize", market_id=market_id, operator=operator, intent_id=intent_id)
    return templates.TemplateResponse(
        "live_execution_packets_v059.html",
        {
            "request": request,
            "user": user,
            "generated_at": board.get("generated_at"),
            "guardrail": board.get("guardrail"),
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "authorization_items": authorization_board.get("items", []),
            "limit": limit,
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "intent_id": intent_id or "",
            "authorization_id": authorization_id or "",
            "default_operator": (user or {}).get("username") or "local",
        },
    )




@app.get("/live-dry-run-adapter", response_class=HTMLResponse)
async def live_dry_run_adapter_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_dry_run_board(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    return templates.TemplateResponse(
        "live_dry_run_adapter_v0510.html",
        {
            "request": request,
            **board,
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "packet_candidates": board.get("packet_candidates", []),
            "limit": limit,
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "packet_id": packet_id or "",
            "intent_id": intent_id or "",
            "default_operator": (user or {}).get("username") or "local",
        },
    )


@app.get("/live-dry-run-review", response_class=HTMLResponse)
async def live_dry_run_review_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_dry_run_review_board(limit=limit, state=state, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    return templates.TemplateResponse(
        "live_dry_run_review_v0511.html",
        {
            "request": request,
            **board,
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "limit": limit,
            "state": state or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "packet_id": packet_id or "",
            "intent_id": intent_id or "",
            "user": user,
        },
    )


@app.get("/live-adapter", response_class=HTMLResponse)
async def live_adapter_page(request: Request, user: dict = Depends(require_admin)):
    report = build_live_adapter_readiness()
    validations = list_live_adapter_readonly_validations(limit=25)
    return templates.TemplateResponse(
        "live_adapter_v060.html",
        {
            "request": request,
            "user": user,
            "report": report,
            "summary": report,
            "credential_presence": report.get("credential_presence", {}),
            "validations": validations,
            "default_operator": (user or {}).get("username") or "local",
        },
    )


@app.get("/live-adapter-requests", response_class=HTMLResponse)
async def live_adapter_requests_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_adapter_request_board(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id, intent_id=intent_id)
    return templates.TemplateResponse(
        "live_adapter_requests_v060.html",
        {
            "request": request,
            **board,
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "packet_candidates": board.get("packet_candidates", []),
            "limit": limit,
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "packet_id": packet_id or "",
            "intent_id": intent_id or "",
            "default_operator": (user or {}).get("username") or "local",
            "user": user,
        },
    )


@app.get("/manual-execution-boundary", response_class=HTMLResponse)
async def manual_execution_boundary_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_manual_execution_review_board(limit=limit, status=status, market_id=market_id, operator=operator, packet_id=packet_id)
    return templates.TemplateResponse(
        "manual_execution_boundary_v060.html",
        {
            "request": request,
            **board,
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "adapter_request_candidates": board.get("adapter_request_candidates", []),
            "limit": limit,
            "status": status or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "packet_id": packet_id or "",
            "default_operator": (user or {}).get("username") or "local",
            "user": user,
        },
    )


@app.get("/live-manual-execution", response_class=HTMLResponse)
async def live_manual_execution_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    adapter_mode: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    adapter_request_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    readiness = build_live_execution_control_readiness()
    board = build_live_execution_attempt_board(
        limit=limit,
        status=status,
        adapter_mode=adapter_mode,
        action="submit",
        market_id=market_id,
        operator=operator,
        adapter_request_id=adapter_request_id,
    )
    return templates.TemplateResponse(
        "live_manual_execution_v070.html",
        {
            "request": request,
            "user": user,
            "readiness": readiness,
            **board,
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "adapter_request_candidates": board.get("adapter_request_candidates", []),
            "limit": limit,
            "status": status or "",
            "adapter_mode": adapter_mode or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "adapter_request_id": adapter_request_id or "",
            "default_operator": (user or {}).get("username") or "local",
        },
    )


@app.get("/live-execution-attempts", response_class=HTMLResponse)
async def live_execution_attempts_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    adapter_mode: str | None = Query(default=None),
    action: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    adapter_request_id: str | None = Query(default=None),
    packet_id: str | None = Query(default=None),
    intent_id: str | None = Query(default=None),
    attempt_id: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_execution_attempt_board(
        limit=limit,
        status=status,
        adapter_mode=adapter_mode,
        action=action,
        market_id=market_id,
        operator=operator,
        adapter_request_id=adapter_request_id,
        packet_id=packet_id,
        intent_id=intent_id,
    )
    detail = get_live_execution_attempt(attempt_id) if attempt_id else None
    return templates.TemplateResponse(
        "live_execution_attempts_v070.html",
        {
            "request": request,
            "user": user,
            **board,
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "detail": detail,
            "limit": limit,
            "status": status or "",
            "adapter_mode": adapter_mode or "",
            "action": action or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "adapter_request_id": adapter_request_id or "",
            "packet_id": packet_id or "",
            "intent_id": intent_id or "",
            "attempt_id": attempt_id or "",
        },
    )


@app.get("/live-manual-cancel", response_class=HTMLResponse)
async def live_manual_cancel_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    adapter_mode: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    user: dict = Depends(require_admin),
):
    board = build_live_execution_attempt_board(limit=limit, status=status, adapter_mode=adapter_mode, action="cancel", market_id=market_id, operator=operator)
    fake_submits = list_live_execution_attempts(limit=50, status="submitted_fake_adapter_only", adapter_mode="fake_local", action="submit")
    return templates.TemplateResponse(
        "live_manual_cancel_v070.html",
        {
            "request": request,
            "user": user,
            **board,
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "fake_submits": fake_submits,
            "limit": limit,
            "status": status or "",
            "adapter_mode": adapter_mode or "",
            "market_id": market_id or "",
            "operator": operator or "",
            "default_operator": (user or {}).get("username") or "local",
        },
    )


@app.post("/live-execution-packets/{packet_id}/adapter-request")
async def live_adapter_request_record_page(
    packet_id: str,
    operator: str = Form(default="local"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_adapter_request(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note)
    return RedirectResponse(url=f"/live-adapter-requests?status={item.get('status', '')}", status_code=303)


@app.post("/live-execution-packets/{packet_id}/manual-execution-review")
async def manual_execution_review_record_page(
    packet_id: str,
    operator: str = Form(default="local"),
    note: str = Form(default=""),
    acknowledged: bool = Form(default=False),
    user: dict = Depends(require_admin),
):
    item = record_manual_execution_review(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note, acknowledged=acknowledged)
    return RedirectResponse(url=f"/manual-execution-boundary?status={item.get('status', '')}", status_code=303)


@app.post("/live-adapter-requests/{adapter_request_id}/manual-submit")
async def live_manual_submit_record_page(
    adapter_request_id: str,
    operator: str = Form(default="local"),
    adapter_mode: str = Form(default="blocked"),
    final_confirmation: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_manual_submit_attempt(
        adapter_request_id=adapter_request_id,
        operator=operator or user.get("username", "local"),
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        note=note,
    )
    return RedirectResponse(url=f"/live-execution-attempts?attempt_id={item.get('attempt_id', '')}", status_code=303)


@app.post("/live-manual-cancel")
async def live_manual_cancel_record_page(
    original_attempt_id: str = Form(default=""),
    fake_order_id: str = Form(default=""),
    operator: str = Form(default="local"),
    adapter_mode: str = Form(default="blocked"),
    final_confirmation: str = Form(default=""),
    reason: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_manual_cancel_attempt(
        original_attempt_id=original_attempt_id,
        fake_order_id=fake_order_id,
        operator=operator or user.get("username", "local"),
        final_confirmation=final_confirmation,
        adapter_mode=adapter_mode,
        reason=reason,
        note=note,
    )
    return RedirectResponse(url=f"/live-execution-attempts?attempt_id={item.get('attempt_id', '')}", status_code=303)


@app.post("/live-adapter/readonly-validation")
async def live_adapter_readonly_validation_record_page(
    operator: str = Form(default="local"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_adapter_readonly_validation(operator=operator or user.get("username", "local"), note=note)
    return RedirectResponse(url=f"/live-adapter?validation_status={item.get('status', '')}", status_code=303)


@app.post("/live-execution-packets/{packet_id}/dry-run")
async def live_dry_run_adapter_record_page(
    packet_id: str,
    operator: str = Form(default="local"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_dry_run_receipt(packet_id=packet_id, operator=operator or user.get("username", "local"), note=note)
    return RedirectResponse(url=f"/live-dry-run-adapter?status={item.get('status', '')}", status_code=303)


@app.post("/live-order-intents/{intent_id}/execution-packet")
async def live_execution_packet_record_page(
    intent_id: str,
    authorization_id: str = Form(default=""),
    operator: str = Form(default="local"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_execution_packet(
        intent_id=intent_id,
        authorization_id=authorization_id or None,
        operator=operator or user.get("username", "local"),
        note=note,
    )
    return RedirectResponse(url=f"/live-execution-packets?status={item.get('status', '')}", status_code=303)


@app.post("/live-order-intents/{intent_id}/authorization")
async def live_order_authorization_record_page(
    intent_id: str,
    decision: str = Form(default="authorize"),
    operator: str = Form(default="local"),
    note: str = Form(default=""),
    acknowledged: bool = Form(default=False),
    user: dict = Depends(require_admin),
):
    item = record_live_order_authorization(
        intent_id=intent_id,
        decision=decision,
        operator=operator or user.get("username", "local"),
        note=note,
        acknowledged=acknowledged,
    )
    return RedirectResponse(url=f"/live-order-authorizations?status={item.get('status', '')}", status_code=303)

@app.post("/live-order-intents/record")
async def live_order_intents_record_page(
    market_id: str = Form(...),
    outcome: str = Form(default="YES"),
    side: str = Form(default="BUY"),
    price: float = Form(default=0.5),
    size: float = Form(default=1.0),
    token_id: str = Form(default=""),
    order_type: str = Form(default="limit"),
    time_in_force: str = Form(default="GTC"),
    operator: str = Form(default="local"),
    note: str = Form(default=""),
    source_ticket_id: str = Form(default=""),
    source_approval_id: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_live_order_intent(
        market_id=market_id,
        outcome=outcome,
        side=side,
        price=price,
        size=size,
        token_id=token_id,
        order_type=order_type,
        time_in_force=time_in_force,
        operator=operator or user.get("username", "local"),
        note=note,
        source_ticket_id=source_ticket_id,
        source_approval_id=source_approval_id,
    )
    return RedirectResponse(url=f"/live-order-intents?status={item.get('status', '')}", status_code=303)


@app.get("/health")
async def health():
    return {"ok": True, "version": APP_VERSION, "mode": settings.app_mode, "read_only": settings.read_only}


@app.get("/api/status")
async def status():
    return {
        "ok": True,
        "version": APP_VERSION,
        "mode": settings.app_mode,
        "read_only": settings.read_only,
        "live_trading_enabled": settings.live_trading_enabled,
        "keys": get_api_key_status(),
        "live_config": build_live_config_readiness().get("summary", {}),
        "live_order_intents": build_live_order_intent_board(limit=10).get("summary", {}),
        "live_order_preflight": build_live_order_preflight_board(limit=10).get("summary", {}),
        "live_order_authorizations": build_live_order_authorization_board(limit=10).get("summary", {}),
        "live_execution_packets": build_live_execution_packet_board(limit=10).get("summary", {}),
        "live_dry_run_adapter": build_live_dry_run_board(limit=10).get("summary", {}),
        "live_dry_run_review": build_live_dry_run_review_board(limit=10).get("summary", {}),
        "live_adapter": build_live_adapter_readiness(),
        "live_adapter_requests": build_live_adapter_request_board(limit=10).get("summary", {}),
        "manual_execution_reviews": build_manual_execution_review_board(limit=10).get("summary", {}),
        "live_execution_control": build_live_execution_control_readiness(),
        "live_execution_attempts": build_live_execution_attempt_board(limit=10).get("summary", {}),
        "market_data": summarize_market_data(),
        "execution_quality": summarize_execution_quality(),
        "latest_snapshot": latest_snapshot_summary(),
        "watchlist_count": len(load_watchlist()),
        "notes_count": notes_summary().get("count", 0),
        "network": network_status(),
    }


@app.get("/api/network/status")
async def network_status_api(user: dict = Depends(require_admin)):
    return network_status()


@app.get("/api/market-data/snapshots")
async def market_data_snapshots_api(
    limit: int = Query(default=100, ge=1, le=2000),
    market_id: str | None = Query(default=None),
    token_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    return {"source": "local", "mode": "market_data_snapshots_v090", **build_market_data_board(limit=limit, market_id=market_id, token_id=token_id, status=status)}


@app.get("/api/market-data/snapshots.csv", response_class=PlainTextResponse)
async def market_data_snapshots_csv(
    limit: int = Query(default=2000, ge=1, le=10000),
    market_id: str | None = Query(default=None),
    token_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    rows = list_market_snapshots(limit=limit, market_id=market_id, token_id=token_id, status=status)
    return PlainTextResponse(market_snapshots_to_csv(rows), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=market_data_snapshots.csv"})


@app.get("/api/market-data/snapshots/{snapshot_id}")
async def market_data_snapshot_detail_api(snapshot_id: str):
    item = get_market_snapshot(snapshot_id)
    if not item:
        raise HTTPException(status_code=404, detail="Market-data snapshot not found")
    return {"source": "local", "mode": "market_data_snapshot_detail_v090", "item": item}


@app.post("/api/market-data/snapshots/parse-preview")
async def market_data_parse_preview_api(orderbook_json: str = Form(...), source: str = Form(default="manual_json"), user: dict = Depends(require_user)):
    payload = json_loads_form(orderbook_json)
    return {"source": "local", "recorded": False, "metrics": parse_orderbook_metrics(payload), "item": build_market_data_preview_item(payload, source=source)}


@app.post("/api/market-data/snapshots")
async def market_data_record_snapshot_api(orderbook_json: str = Form(...), source: str = Form(default="manual_json"), user: dict = Depends(require_admin)):
    item = record_market_snapshot(json_loads_form(orderbook_json), source=source)
    return {"source": "local", "recorded": True, "item": item}


@app.post("/api/market-data/snapshots/fetch-preview")
async def market_data_fetch_preview_api(market_id: str = Form(default=""), token_id: str = Form(default=""), user: dict = Depends(require_user)):
    return {"source": "local", "recorded": False, "item": fetch_market_data_preview(market_id=market_id, token_id=token_id)}


@app.post("/api/market-data/snapshots/fetch-record")
async def market_data_fetch_record_api(market_id: str = Form(default=""), token_id: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"source": "local", "recorded": False, "item": fetch_market_data_preview(market_id=market_id, token_id=token_id)}


@app.get("/api/execution-quality")
async def execution_quality_api(
    limit: int = Query(default=100, ge=1, le=2000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    token_id: str | None = Query(default=None),
):
    return {"source": "local", "mode": "execution_quality_v090", **build_execution_quality_board(limit=limit, state=state, market_id=market_id, token_id=token_id)}


@app.get("/api/execution-quality.csv", response_class=PlainTextResponse)
async def execution_quality_csv(
    limit: int = Query(default=2000, ge=1, le=10000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    token_id: str | None = Query(default=None),
):
    rows = list_execution_quality_simulations(limit=limit, state=state, market_id=market_id, token_id=token_id)
    return PlainTextResponse(execution_quality_to_csv(rows), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=execution_quality.csv"})


@app.get("/api/execution-quality/{simulation_id}")
async def execution_quality_detail_api(simulation_id: str):
    item = get_execution_quality_simulation(simulation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Execution-quality simulation not found")
    return {"source": "local", "mode": "execution_quality_detail_v090", "item": item}


@app.post("/api/execution-quality/preview")
async def execution_quality_preview_api(
    side: str = Form(default="BUY"),
    token_id: str = Form(default=""),
    market_id: str = Form(default=""),
    snapshot_id: str = Form(default=""),
    price: float = Form(default=0.5),
    size: float = Form(default=1.0),
    order_type: str = Form(default="limit"),
    time_in_force: str = Form(default="GTC"),
    max_spread_bps: float | None = Form(default=None),
    max_slippage_bps: float | None = Form(default=None),
    source_ticket_id: str = Form(default=""),
    source_intent_id: str = Form(default=""),
    user: dict = Depends(require_user),
):
    item = build_execution_quality_simulation(side=side, token_id=token_id, market_id=market_id, snapshot_id=snapshot_id, price=price, size=size, order_type=order_type, time_in_force=time_in_force, max_spread_bps=max_spread_bps, max_slippage_bps=max_slippage_bps, source_ticket_id=source_ticket_id, source_intent_id=source_intent_id)
    return {"source": "local", "recorded": False, "item": item}


@app.post("/api/execution-quality/record")
async def execution_quality_record_api(
    side: str = Form(default="BUY"),
    token_id: str = Form(default=""),
    market_id: str = Form(default=""),
    snapshot_id: str = Form(default=""),
    price: float = Form(default=0.5),
    size: float = Form(default=1.0),
    order_type: str = Form(default="limit"),
    time_in_force: str = Form(default="GTC"),
    max_spread_bps: float | None = Form(default=None),
    max_slippage_bps: float | None = Form(default=None),
    source_ticket_id: str = Form(default=""),
    source_intent_id: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = record_execution_quality_simulation(side=side, token_id=token_id, market_id=market_id, snapshot_id=snapshot_id, price=price, size=size, order_type=order_type, time_in_force=time_in_force, max_spread_bps=max_spread_bps, max_slippage_bps=max_slippage_bps, source_ticket_id=source_ticket_id, source_intent_id=source_intent_id)
    return {"source": "local", "recorded": True, "item": item}


@app.get("/market-data", response_class=HTMLResponse)
async def market_data_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    market_id: str | None = Query(default=None),
    token_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    board = build_market_data_board(limit=limit, market_id=market_id, token_id=token_id, status=status)
    quality = build_execution_quality_board(limit=25, market_id=market_id, token_id=token_id)
    return templates.TemplateResponse("market_data_v090.html", {"request": request, "user": current_user(request), **board, "quality_summary": quality.get("summary", {}), "limit": limit, "market_id": market_id or "", "token_id": token_id or "", "status": status or ""})


@app.get("/market-data/snapshots", response_class=HTMLResponse)
async def market_data_snapshots_page(request: Request, limit: int = Query(default=100, ge=1, le=1000), market_id: str | None = Query(default=None), token_id: str | None = Query(default=None), status: str | None = Query(default=None)):
    return await market_data_page(request, limit=limit, market_id=market_id, token_id=token_id, status=status)


@app.get("/market-data/snapshots/{snapshot_id}", response_class=HTMLResponse)
async def market_data_snapshot_detail_page(request: Request, snapshot_id: str):
    item = get_market_snapshot(snapshot_id)
    if not item:
        raise HTTPException(status_code=404, detail="Market-data snapshot not found")
    related = build_execution_quality_board(limit=50, market_id=str(item.get("market_id") or ""), token_id=str(item.get("token_id") or ""))
    return templates.TemplateResponse("market_data_snapshot_detail_v090.html", {"request": request, "user": current_user(request), "item": item, "related_quality": related.get("items", [])})


@app.get("/execution-quality", response_class=HTMLResponse)
async def execution_quality_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    state: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    token_id: str | None = Query(default=None),
):
    board = build_execution_quality_board(limit=limit, state=state, market_id=market_id, token_id=token_id)
    market_board = build_market_data_board(limit=25, market_id=market_id, token_id=token_id)
    return templates.TemplateResponse("execution_quality_v090.html", {"request": request, "user": current_user(request), **board, "market_summary": market_board.get("summary", {}), "snapshots": market_board.get("items", []), "limit": limit, "state": state or "", "market_id": market_id or "", "token_id": token_id or ""})


@app.get("/execution-quality/{simulation_id}", response_class=HTMLResponse)
async def execution_quality_detail_page(request: Request, simulation_id: str):
    item = get_execution_quality_simulation(simulation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Execution-quality simulation not found")
    snapshot = get_market_snapshot(str(item.get("snapshot_id") or "")) if item.get("snapshot_id") else None
    return templates.TemplateResponse("execution_quality_detail_v090.html", {"request": request, "user": current_user(request), "item": item, "snapshot": snapshot})


def json_loads_form(raw: str) -> dict:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON payload must be an object")
    return payload


def build_market_data_preview_item(payload: dict, *, source: str) -> dict:
    from .market_data import build_market_snapshot

    return build_market_snapshot(payload, source=source)


@app.get("/dashboard")
async def dashboard_alias():
    return RedirectResponse(url="/", status_code=307)


@app.get("/api/navigation/system-map")
async def navigation_system_map_api():
    return get_system_map()


@app.get("/api/navigation/aliases")
async def navigation_aliases_api():
    return {"aliases": get_route_aliases(), "order_submitted": False, "order_cancelled": False, "live_trading_armed": False}


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    limit: int = Query(default=settings.default_limit, ge=1, le=100),
    save: bool = Query(default=False),
):
    try:
        events = await client.list_events(limit=limit)
    except Exception:
        events = []
    try:
        raw_markets = await client.list_markets(limit=limit)
    except Exception:
        raw_markets = []
    previous = load_latest()
    markets = _score_market_rows(raw_markets)
    paper_recommendations = recommend_paper_trades(markets, max_recommendations=10)
    backtests = list_backtests(limit=5)
    movers = calculate_movers(markets, previous)[:20]
    new_markets = detect_new_markets(markets, previous)[:20]
    summary = summarize_snapshot(markets)
    snapshot = save_snapshot(markets) if save else None
    portfolio_summary = summarize_portfolio(markets)
    current_risk_status = risk_status(load_portfolio())
    alerts = generate_alerts(markets, movers=movers, portfolio=portfolio_summary, risk=current_risk_status, max_items=20)
    alerts.extend(position_alerts(portfolio_summary))
    risk_budget_report = build_risk_budget(markets, limit=20)
    preflight_report = build_preflight_board(limit=20)
    alerts.extend(risk_budget_alerts(risk_budget_report))
    alerts.extend(preflight_alerts(preflight_report))
    approval_report = build_execution_approval_board(limit=20)
    alerts.extend(approval_alerts(approval_report))
    execution_queue_report = build_execution_queue(limit=20)
    alerts.extend(execution_queue_alerts(execution_queue_report))
    runbook_report = build_runbook(limit=20)
    alerts.extend(runbook_alerts(runbook_report))
    briefing_report = build_paper_ops_briefing(limit=25)
    alerts.extend(briefing_alerts(briefing_report))
    handoff_board = build_operator_handoff_board(limit=25)
    handoff_reconciliation = build_operator_handoff_reconciliation_board(limit=25)
    alerts.extend(handoff_alerts(handoff_board))
    ops_aging_report = build_paper_ops_aging(limit=25)
    alerts.extend(ops_aging_alerts(ops_aging_report))
    ops_escalation_board = build_ops_escalation_board(limit=25)
    alerts.extend(ops_escalation_alerts(ops_escalation_board))
    ops_escalation_review = build_ops_escalation_review(limit=25)
    alerts.extend(ops_escalation_review_alerts(ops_escalation_review))
    ops_closeout = build_paper_ops_closeout(limit=25)
    alerts.extend(paper_ops_closeout_alerts(ops_closeout))
    ops_closeout_signoffs = build_ops_closeout_signoff_board(limit=25, closeout_report=ops_closeout)
    alerts.extend(ops_closeout_signoff_alerts(ops_closeout_signoffs))
    live_config_report = build_live_config_readiness()
    alerts.extend(live_config_alerts(live_config_report))
    live_intent_board = build_live_order_intent_board(limit=20)
    alerts.extend(live_order_intent_alerts(live_intent_board))
    live_preflight_board = build_live_order_preflight_board(limit=20)
    alerts.extend(live_order_preflight_alerts(live_preflight_board))
    live_authorization_board = build_live_order_authorization_board(limit=20)
    alerts.extend(live_order_authorization_alerts(live_authorization_board))
    live_execution_packet_board = build_live_execution_packet_board(limit=20)
    alerts.extend(live_execution_packet_alerts(live_execution_packet_board))
    live_dry_run_board = build_live_dry_run_board(limit=20)
    alerts.extend(live_dry_run_alerts(live_dry_run_board))
    live_dry_run_review_board = build_live_dry_run_review_board(limit=20)
    alerts.extend(live_dry_run_review_alerts(live_dry_run_review_board))
    live_adapter_report = build_live_adapter_readiness()
    live_adapter_request_board = build_live_adapter_request_board(limit=20)
    manual_execution_review_board = build_manual_execution_review_board(limit=20)
    alerts.extend(live_adapter_alerts(live_adapter_report, live_adapter_request_board, manual_execution_review_board))
    live_execution_control_report = build_live_execution_control_readiness()
    live_execution_attempt_board = build_live_execution_attempt_board(limit=20)
    alerts.extend(live_execution_control_alerts(live_execution_control_report, live_execution_attempt_board))
    market_data_board = build_market_data_board(limit=50)
    execution_quality_board = build_execution_quality_board(limit=50)
    alerts.extend(market_data_alerts(market_data_board, execution_quality_board))
    training_status = build_training_status()
    data_status = build_data_status()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "events": events,
            "markets": markets,
            "movers": movers,
            "new_markets": new_markets,
            "summary": summary,
            "snapshot": snapshot,
            "latest_snapshot": latest_snapshot_summary(),
            "snapshots": list_snapshots(limit=10),
            "limit": limit,
            "watchlist": load_watchlist(),
            "api_key_status": get_api_key_status(),
            "portfolio": portfolio_summary,
            "risk_status": current_risk_status,
            "trade_analytics": trade_analytics(load_trades(), portfolio_summary),
            "alerts": alerts,
            "alert_summary": summarize_alerts(alerts),
            "recent_trades": list(reversed(load_trades()))[:10],
            "notes_summary": notes_summary(limit=10),
            "source_summary": source_summary(),
            "evidence_summary": evidence_summary(limit=5),
            "evidence_readiness": {"note": "Evidence readiness comes from saved packets; market-specific scores appear on detail pages."},
            "evidence_probability_markets": attach_evidence_probability(markets[:20]),
            "probability_markets": markets[:20],
            "paper_recommendations": paper_recommendations,
            "backtests": backtests,
            "ticket_summary": summarize_trade_tickets(),
            "audit_summary": summarize_audit(build_audit_events(limit=500)),
            "playbook_summary": summarize_playbooks(list_playbooks()),
            "playbook_decision_summary": summarize_playbook_decisions(list_playbook_decisions(limit=10000)),
            "playbook_performance_summary": build_playbook_performance(limit=100).get("summary", {}),
            "risk_budget_summary": risk_budget_report.get("summary", {}),
            "risk_budget_flags": risk_budget_report.get("flags", [])[:5],
            "preflight_summary": preflight_report.get("summary", {}),
            "approval_summary": approval_report.get("summary", {}),
            "execution_queue_summary": execution_queue_report.get("summary", {}),
            "runbook_summary": runbook_report.get("summary", {}),
            "briefing_summary": briefing_report.get("summary", {}),
            "handoff_summary": handoff_board.get("summary", {}),
            "handoff_reconciliation_summary": handoff_reconciliation.get("summary", {}),
            "ops_aging_summary": ops_aging_report.get("summary", {}),
            "ops_escalation_summary": ops_escalation_board.get("summary", {}),
            "ops_escalation_candidate_summary": ops_escalation_board.get("candidate_summary", {}),
            "ops_escalation_review_summary": ops_escalation_review.get("summary", {}),
            "ops_closeout_summary": ops_closeout.get("summary", {}),
            "ops_closeout_signoff_summary": ops_closeout_signoffs.get("summary", {}),
            "live_config_summary": live_config_report.get("summary", {}),
            "live_order_intent_summary": live_intent_board.get("summary", {}),
            "live_order_preflight_summary": live_preflight_board.get("summary", {}),
            "live_order_authorization_summary": live_authorization_board.get("summary", {}),
            "live_execution_packet_summary": live_execution_packet_board.get("summary", {}),
            "live_dry_run_summary": live_dry_run_board.get("summary", {}),
            "live_dry_run_review_summary": live_dry_run_review_board.get("summary", {}),
            "live_adapter_summary": live_adapter_report,
            "live_adapter_request_summary": live_adapter_request_board.get("summary", {}),
            "manual_execution_review_summary": manual_execution_review_board.get("summary", {}),
            "live_execution_control_summary": live_execution_control_report,
            "live_execution_attempt_summary": live_execution_attempt_board.get("summary", {}),
            "market_data_summary": market_data_board.get("summary", {}),
            "execution_quality_summary": execution_quality_board.get("summary", {}),
            "training_status": training_status,
            "data_status": data_status,
            "user": current_user(request),
            "primary_entry_points": get_primary_entry_points(),
            "system_map": get_system_map(),
            "navigation_safety_explainer": get_safety_explainer(),
        },
    )




@app.get("/operator", response_class=HTMLResponse)
async def operator_dashboard(request: Request, limit: int = Query(default=75, ge=10, le=200)):
    previous = load_latest()
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    movers = calculate_movers(markets, previous)[:50]
    portfolio_summary = summarize_portfolio(markets)
    current_risk_status = risk_status(load_portfolio())
    alerts = generate_alerts(markets, movers=movers, portfolio=portfolio_summary, risk=current_risk_status, max_items=50)
    alerts.extend(position_alerts(portfolio_summary))
    alerts.extend(risk_budget_alerts(build_risk_budget(markets, limit=20)))
    alerts.extend(preflight_alerts(build_preflight_board(limit=20)))
    alerts.extend(approval_alerts(build_execution_approval_board(limit=20)))
    alerts.extend(execution_queue_alerts(build_execution_queue(limit=20)))
    alerts.extend(runbook_alerts(build_runbook(limit=20)))
    alerts.extend(briefing_alerts(build_paper_ops_briefing(limit=20)))
    alerts.extend(handoff_alerts(build_operator_handoff_board(limit=20)))
    alerts.extend(ops_aging_alerts(build_paper_ops_aging(limit=20)))
    alerts.extend(ops_escalation_alerts(build_ops_escalation_board(limit=20)))
    alerts.extend(ops_escalation_review_alerts(build_ops_escalation_review(limit=20)))
    op_closeout = build_paper_ops_closeout(limit=20)
    alerts.extend(paper_ops_closeout_alerts(op_closeout))
    alerts.extend(ops_closeout_signoff_alerts(build_ops_closeout_signoff_board(limit=20, closeout_report=op_closeout)))
    alerts.extend(live_config_alerts(build_live_config_readiness()))
    alerts.extend(live_order_intent_alerts(build_live_order_intent_board(limit=20)))
    alerts.extend(live_order_preflight_alerts(build_live_order_preflight_board(limit=20)))
    alerts.extend(live_order_authorization_alerts(build_live_order_authorization_board(limit=20)))
    alerts.extend(live_execution_packet_alerts(build_live_execution_packet_board(limit=20)))
    alerts.extend(live_dry_run_alerts(build_live_dry_run_board(limit=20)))
    alerts.extend(live_dry_run_review_alerts(build_live_dry_run_review_board(limit=20)))
    alerts.extend(live_adapter_alerts(build_live_adapter_readiness(), build_live_adapter_request_board(limit=20), build_manual_execution_review_board(limit=20)))
    alerts.extend(live_execution_control_alerts(build_live_execution_control_readiness(), build_live_execution_attempt_board(limit=20)))
    recommendations = recommend_paper_trades(markets, max_recommendations=20)
    evidence_markets = attach_evidence_probability(markets[:40])
    brief = build_operator_brief(
        markets=markets,
        movers=movers,
        alerts=alerts,
        recommendations=recommendations,
        portfolio=portfolio_summary,
        risk=current_risk_status,
        watchlist=load_watchlist(),
        evidence_markets=evidence_markets,
        max_items=12,
    )
    return templates.TemplateResponse(
        "operator.html",
        {
            "request": request,
            "user": current_user(request),
            "brief": brief,
            "limit": limit,
        },
    )


@app.get("/api/operator/brief")
async def operator_brief_api(limit: int = Query(default=75, ge=10, le=200)):
    previous = load_latest()
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    movers = calculate_movers(markets, previous)[:50]
    portfolio_summary = summarize_portfolio(markets)
    current_risk_status = risk_status(load_portfolio())
    alerts = generate_alerts(markets, movers=movers, portfolio=portfolio_summary, risk=current_risk_status, max_items=50)
    alerts.extend(position_alerts(portfolio_summary))
    alerts.extend(risk_budget_alerts(build_risk_budget(markets, limit=20)))
    alerts.extend(preflight_alerts(build_preflight_board(limit=20)))
    alerts.extend(approval_alerts(build_execution_approval_board(limit=20)))
    alerts.extend(execution_queue_alerts(build_execution_queue(limit=20)))
    alerts.extend(runbook_alerts(build_runbook(limit=20)))
    alerts.extend(briefing_alerts(build_paper_ops_briefing(limit=20)))
    alerts.extend(handoff_alerts(build_operator_handoff_board(limit=20)))
    alerts.extend(ops_aging_alerts(build_paper_ops_aging(limit=20)))
    alerts.extend(ops_escalation_alerts(build_ops_escalation_board(limit=20)))
    alerts.extend(ops_escalation_review_alerts(build_ops_escalation_review(limit=20)))
    op_closeout = build_paper_ops_closeout(limit=20)
    alerts.extend(paper_ops_closeout_alerts(op_closeout))
    alerts.extend(ops_closeout_signoff_alerts(build_ops_closeout_signoff_board(limit=20, closeout_report=op_closeout)))
    alerts.extend(live_config_alerts(build_live_config_readiness()))
    alerts.extend(live_order_intent_alerts(build_live_order_intent_board(limit=20)))
    alerts.extend(live_order_preflight_alerts(build_live_order_preflight_board(limit=20)))
    alerts.extend(live_order_authorization_alerts(build_live_order_authorization_board(limit=20)))
    alerts.extend(live_execution_packet_alerts(build_live_execution_packet_board(limit=20)))
    alerts.extend(live_dry_run_alerts(build_live_dry_run_board(limit=20)))
    alerts.extend(live_dry_run_review_alerts(build_live_dry_run_review_board(limit=20)))
    alerts.extend(live_adapter_alerts(build_live_adapter_readiness(), build_live_adapter_request_board(limit=20), build_manual_execution_review_board(limit=20)))
    alerts.extend(live_execution_control_alerts(build_live_execution_control_readiness(), build_live_execution_attempt_board(limit=20)))
    recommendations = recommend_paper_trades(markets, max_recommendations=20)
    evidence_markets = attach_evidence_probability(markets[:40])
    return build_operator_brief(
        markets=markets,
        movers=movers,
        alerts=alerts,
        recommendations=recommendations,
        portfolio=portfolio_summary,
        risk=current_risk_status,
        watchlist=load_watchlist(),
        evidence_markets=evidence_markets,
        max_items=12,
    )


@app.get("/v3/opportunities", response_class=HTMLResponse)
@app.get("/opportunities", response_class=HTMLResponse)
@app.get("/v3/markets", response_class=HTMLResponse)
async def opportunities_page(request: Request, limit: int = Query(default=100, ge=10, le=200), demo: bool = Query(default=False)):
    markets = await _review_market_rows(limit=limit, demo=demo)
    rows = rank_opportunities(markets, watchlist=load_watchlist(), max_items=50)
    packets = v4_ai_edge.list_packets(limit=250).get("items", [])
    workbench = build_opportunity_workbench(rows, packets, limit=50, requested_demo=demo, source_route="/v3/opportunities")
    return templates.TemplateResponse(
        "opportunity_workbench.html",
        {
            "request": request,
            "user": current_user(request),
            "limit": limit,
            "demo_mode": demo or any(row.get("demo_fixture") for row in markets),
            "opportunities": rows,
            "summary": opportunity_summary(rows),
            "workbench": workbench,
            "review_settings": opportunity_review_settings(),
        },
    )


@app.get("/api/opportunities/engine")
async def opportunity_engine_api(limit: int = Query(default=100, ge=10, le=200), max_items: int = Query(default=50, ge=1, le=100), demo: bool = Query(default=False)):
    markets = await _review_market_rows(limit=limit, demo=demo)
    rows = rank_opportunities(markets, watchlist=load_watchlist(), max_items=max_items)
    return {
        "source": "gamma+local_evidence+paper_risk" if not any(row.get("demo_fixture") for row in markets) else "safe_demo_fixture+local",
        "mode": "opportunity_review_workbench_v46",
        "note": "Research and paper-review candidate ranking only. No live trading, no approvals, no order placement.",
        "summary": opportunity_summary(rows),
        "workbench": build_opportunity_workbench(rows, v4_ai_edge.list_packets(limit=250).get("items", []), limit=max_items, requested_demo=demo, source_route="/api/opportunities/engine"),
        "items": rows,
        "review_only": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
    }


@app.get("/api/v3/opportunities")
async def api_v3_opportunities(limit: int = Query(default=100, ge=10, le=200), max_items: int = Query(default=50, ge=1, le=100), demo: bool = Query(default=False)):
    markets = await _review_market_rows(limit=limit, demo=demo)
    rows = rank_opportunities(markets, watchlist=load_watchlist(), max_items=max_items)
    return build_opportunity_workbench(rows, v4_ai_edge.list_packets(limit=250).get("items", []), limit=max_items, requested_demo=demo, source_route="/api/v3/opportunities")


@app.get("/api/v3/opportunities/reviews")
async def api_v3_opportunity_reviews(limit: int = Query(default=500, ge=1, le=5000), include_archived: bool = Query(default=True)):
    return list_review_records(limit=limit, include_archived=include_archived)


@app.get("/api/v3/opportunities/review/{market_id_or_slug}")
async def api_v3_opportunity_review_detail(market_id_or_slug: str):
    return get_review_record(market_id_or_slug)


@app.post("/api/v3/opportunities/review/{market_id_or_slug}/notes")
async def api_v3_opportunity_review_notes(market_id_or_slug: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return update_review_notes(market_id_or_slug, payload)


@app.post("/api/v3/opportunities/review/{market_id_or_slug}/status")
async def api_v3_opportunity_review_status(market_id_or_slug: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return update_review_status(market_id_or_slug, payload)


@app.post("/v3/opportunities/review/{market_id_or_slug}/notes")
async def v3_opportunity_review_notes_page(
    market_id_or_slug: str,
    operator_notes: str = Form(default=""),
    review_status: str = Form(default=""),
    market_title: str = Form(default=""),
    data_state: str = Form(default=""),
    data_freshness: str = Form(default=""),
    source_route: str = Form(default=""),
    source_component: str = Form(default="opportunity_review.notes_form"),
    reason: str = Form(default="Operator saved opportunity review notes."),
    return_to: str = Form(default="/v3/opportunities"),
    user: dict = Depends(require_admin),
):
    result = update_review_notes(
        market_id_or_slug,
        {
            "operator_notes": operator_notes,
            "review_status": review_status or None,
            "market_title": market_title,
            "data_state": data_state,
            "data_freshness": data_freshness,
            "source_route": source_route or return_to,
            "source_component": source_component,
            "reason": reason,
            "return_to": return_to,
            "operator": str(user.get("username") or ""),
        },
    )
    suffix = urlencode({"notes": "saved" if result.get("ok") else "blocked"})
    separator = "&" if "?" in return_to else "?"
    return RedirectResponse(url=f"{_safe_return_path(return_to, '/v3/opportunities')}{separator}{suffix}", status_code=303)


@app.post("/v3/opportunities/review/{market_id_or_slug}/status")
async def v3_opportunity_review_status_page(
    market_id_or_slug: str,
    action: str = Form(default=""),
    review_status: str = Form(default=""),
    market_title: str = Form(default=""),
    data_state: str = Form(default=""),
    data_freshness: str = Form(default=""),
    source_route: str = Form(default=""),
    source_component: str = Form(default="opportunity_review.status_form"),
    previous_state: str = Form(default=""),
    reason: str = Form(default="Operator updated opportunity review status."),
    return_to: str = Form(default="/v3/opportunities"),
    user: dict = Depends(require_admin),
):
    requested = action or review_status
    result = update_review_status(
        market_id_or_slug,
        {
            "action": requested,
            "review_status": review_status or None,
            "market_title": market_title,
            "data_state": data_state,
            "data_freshness": data_freshness,
            "source_route": source_route or return_to,
            "source_component": source_component,
            "previous_state": previous_state,
            "reason": reason,
            "return_to": return_to,
            "operator": str(user.get("username") or ""),
        },
    )
    status = result.get("item", {}).get("review_status") if result.get("ok") else "blocked"
    suffix = urlencode({"review_status": status})
    separator = "&" if "?" in return_to else "?"
    return RedirectResponse(url=f"{_safe_return_path(return_to, '/v3/opportunities')}{separator}{suffix}", status_code=303)


@app.get("/api/v3/opportunities/settings")
async def api_v3_opportunity_settings():
    return opportunity_review_settings()


@app.get("/v3/arbitrage", response_class=HTMLResponse)
@app.get("/arbitrage", response_class=HTMLResponse)
async def v3_cross_market_arbitrage_page(
    request: Request,
    min_margin: float = Query(default=1.0, ge=0.0, le=100.0),
    min_confidence: float = Query(default=0.72, ge=0.0, le=1.0),
    demo: bool = Query(default=True),
):
    scan = await v4_arbitrage.scan_cross_market_arbitrage(min_net_margin_pct=min_margin, min_confidence=min_confidence, demo=demo, write=False)
    feature_status_map = build_feature_status_map()
    stub_burndown = feature_status_map.get("stub_burndown", {})
    readiness_ids = {"arbitrage.scanner", "arbitrage.review_actions", "arbitrage.polymarket_adapter", "arbitrage.kalshi_adapter", "settings.ai_arbitrage_config"}
    stub_ids = {"arbitrage.scanner_review", "venues.kalshi", "venues.registry", "audit.operator_log", "live.execution_controls"}
    return templates.TemplateResponse(
        "cross_market_arbitrage.html",
        {
            "request": request,
            "user": current_user(request),
            "scan": scan,
            "settings": v4_arbitrage.arbitrage_settings_summary(),
            "min_margin": min_margin,
            "min_confidence": min_confidence,
            "demo_mode": demo or not bool(getattr(settings, "arbitrage_scanner_enabled", False)),
            "feature_statuses": [item for item in feature_status_map.get("items", []) if item.get("feature_id") in readiness_ids],
            "stub_burndown_items": [item for item in stub_burndown.get("items", []) if item.get("feature_id") in stub_ids],
            "data_state_values": v4_arbitrage.DATA_STATE_VALUES,
        },
    )


@app.post("/v3/arbitrage/scan/record")
async def v3_arbitrage_scan_record_page(
    min_margin: float = Form(default=1.0),
    min_confidence: float = Form(default=0.72),
    demo: bool = Form(default=True),
    return_to: str = Form(default="/v3/arbitrage"),
    reason: str = Form(default="Operator recorded scan snapshot from arbitrage page."),
    user: dict = Depends(require_admin),
):
    scan = await v4_arbitrage.scan_cross_market_arbitrage(
        min_net_margin_pct=max(0.0, min(float(min_margin), 100.0)),
        min_confidence=max(0.0, min(float(min_confidence), 1.0)),
        demo=demo,
        write=True,
        source_route="/v3/arbitrage/scan/record",
        operator=str(user.get("username", "admin")),
        reason=reason,
    )
    base = _safe_return_path(return_to, "/v3/arbitrage")
    suffix = urlencode({"action_status": "arbitrage_scan_recorded", "action_detail": scan.get("scan_id", "scan_snapshot")})
    separator = "&" if "?" in base else "?"
    return RedirectResponse(url=f"{base}{separator}{suffix}", status_code=303)


@app.get("/api/v3/arbitrage/config")
async def api_v3_arbitrage_config():
    return v4_arbitrage.arbitrage_settings_summary()


@app.get("/api/v3/arbitrage/opportunities")
@app.get("/api/v3/arbitrage/scan")
async def api_v3_arbitrage_scan(
    limit_per_venue: int = Query(default=25, ge=1, le=200),
    min_margin: float = Query(default=1.0, ge=0.0, le=100.0),
    min_confidence: float = Query(default=0.72, ge=0.0, le=1.0),
    demo: bool = Query(default=True),
    write: bool = Query(default=False),
):
    return await v4_arbitrage.scan_cross_market_arbitrage(
        limit_per_venue=limit_per_venue,
        min_net_margin_pct=min_margin,
        min_confidence=min_confidence,
        demo=demo,
        write=write,
    )


@app.post("/api/v3/arbitrage/scan/record")
async def api_v3_arbitrage_scan_record(payload: dict[str, Any] = Body(default_factory=dict)):
    try:
        limit_per_venue = max(1, min(int(float(payload.get("limit_per_venue", 25))), 200))
    except (TypeError, ValueError):
        limit_per_venue = 25
    try:
        min_margin = max(0.0, min(float(payload.get("min_margin", 1.0)), 100.0))
    except (TypeError, ValueError):
        min_margin = 1.0
    try:
        min_confidence = max(0.0, min(float(payload.get("min_confidence", 0.72)), 1.0))
    except (TypeError, ValueError):
        min_confidence = 0.72
    scan = await v4_arbitrage.scan_cross_market_arbitrage(
        limit_per_venue=limit_per_venue,
        min_net_margin_pct=min_margin,
        min_confidence=min_confidence,
        demo=_payload_bool(payload.get("demo"), True),
        write=True,
        source_route="/api/v3/arbitrage/scan/record",
        operator=str(payload.get("operator") or ""),
        reason=str(payload.get("reason") or "API caller recorded scan snapshot."),
    )
    return {
        "version": APP_VERSION,
        "ok": True,
        "scan": scan,
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
    }


@app.get("/api/v3/arbitrage/opportunity/{opportunity_id}/review")
async def api_v3_arbitrage_review_action_link(opportunity_id: str, action: str = Query(default="review_requested")):
    return {
        "version": APP_VERSION,
        "ok": False,
        "opportunity_id": opportunity_id,
        "requested_action": action,
        "method_required": "POST",
        "message": "Arbitrage review actions are state-changing local review records and must be submitted with POST.",
        "review_only": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
    }


@app.post("/api/v3/arbitrage/opportunity/{opportunity_id}/review")
async def api_v3_arbitrage_review_action(opportunity_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    action = str(payload.get("action") or "review_requested")
    return v4_arbitrage.record_operator_action(opportunity_id, action, payload)


@app.post("/v3/arbitrage/opportunity/{opportunity_id}/review")
async def v3_arbitrage_review_action_page(
    opportunity_id: str,
    action: str = Form(default="review_requested"),
    operator_note: str = Form(default=""),
    data_state: str = Form(default="unavailable"),
    data_freshness: str = Form(default="unavailable"),
    scan_id: str = Form(default=""),
    target_name: str = Form(default=""),
    return_to: str = Form(default="/v3/arbitrage"),
    user: dict = Depends(require_admin),
):
    result = v4_arbitrage.record_operator_action(
        opportunity_id,
        action,
        {
            "operator_note": operator_note,
            "operator": user.get("username", "admin"),
            "data_state": data_state,
            "data_freshness": data_freshness or data_state,
            "scan_id": scan_id,
            "target_name": target_name,
            "source_route": "/v3/arbitrage",
            "source_component": "cross_market_arbitrage.review_form",
        },
    )
    status = "recorded" if result.get("ok", True) is not False else "blocked"
    suffix = urlencode({"arbitrage_review": status, "action": action})
    separator = "&" if "?" in return_to else "?"
    return RedirectResponse(url=f"{_safe_return_path(return_to, '/v3/arbitrage')}{separator}{suffix}", status_code=303)


@app.get("/v3/ai/news-odds", response_class=HTMLResponse)
async def v3_ai_news_odds_page(request: Request):
    return templates.TemplateResponse(
        "ai_news_odds.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": v4_ai_news_odds.summarize_news_odds(),
            "settings": v4_ai_news_odds.news_odds_settings_summary(),
            "source_weights": v4_ai_news_odds.source_weight_table(),
            "adjustments": v4_ai_news_odds.list_adjustments(limit=25, include_archived=False),
        },
    )


@app.get("/v3/ai/news-odds/run", response_class=HTMLResponse)
async def v3_ai_news_odds_run_page(request: Request):
    markets = await _review_market_rows(limit=25, demo=True)
    return templates.TemplateResponse(
        "ai_news_odds_run.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": v4_ai_news_odds.summarize_news_odds(),
            "markets": markets,
            "settings": v4_ai_news_odds.news_odds_settings_summary(),
        },
    )


@app.get("/v3/ai/news-odds/adjustments", response_class=HTMLResponse)
async def v3_ai_news_odds_adjustments_page(request: Request, include_archived: bool = Query(default=False)):
    return templates.TemplateResponse(
        "ai_news_odds_adjustments.html",
        {
            "request": request,
            "user": current_user(request),
            "adjustments": v4_ai_news_odds.list_adjustments(limit=250, include_archived=include_archived),
            "include_archived": include_archived,
        },
    )


@app.get("/v3/ai/news-odds/adjustment/{adjustment_id}", response_class=HTMLResponse)
async def v3_ai_news_odds_adjustment_detail_page(request: Request, adjustment_id: str):
    detail = v4_ai_news_odds.get_adjustment(adjustment_id)
    return templates.TemplateResponse(
        "ai_news_odds_adjustment_detail.html",
        {
            "request": request,
            "user": current_user(request),
            "detail": detail,
            "adjustment": detail.get("adjustment", {}),
        },
    )


@app.get("/v3/ai/news-odds/source-weights", response_class=HTMLResponse)
async def v3_ai_news_odds_source_weights_page(request: Request):
    return templates.TemplateResponse(
        "ai_news_odds_source_weights.html",
        {
            "request": request,
            "user": current_user(request),
            "source_weights": v4_ai_news_odds.source_weight_table(),
            "settings": v4_ai_news_odds.news_odds_settings_summary(),
        },
    )


@app.get("/api/v3/ai/news-odds/config")
async def api_v3_ai_news_odds_config():
    return v4_ai_news_odds.news_odds_settings_summary()


@app.post("/api/v3/ai/news-odds/market/{market_id_or_slug}/plan")
async def api_v3_ai_news_odds_market_plan(market_id_or_slug: str, payload: dict[str, Any] = Body(default_factory=dict)):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return v4_ai_news_odds.build_market_search_plan(market, operator_notes=payload.get("operator_notes"), prior_context=payload.get("prior_context") if isinstance(payload.get("prior_context"), dict) else None)


@app.post("/v3/ai/news-odds/market/{market_id_or_slug}/plan")
async def v3_ai_news_odds_market_plan_page(
    market_id_or_slug: str,
    operator_notes: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    plan = v4_ai_news_odds.build_market_search_plan(market, operator_notes=operator_notes)
    return _v3_action_redirect(
        f"/v3/markets/{market_id_or_slug}/news-odds",
        action_status="news_odds_plan_previewed",
        action_detail=f"{len(plan.get('queries', []))}_queries",
    )


@app.post("/api/v3/ai/news-odds/market/{market_id_or_slug}/search")
async def api_v3_ai_news_odds_market_search(market_id_or_slug: str, payload: dict[str, Any] = Body(default_factory=dict)):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    requests = v4_ai_news_providers.build_news_search_requests(market, payload)
    return v4_ai_news_providers.run_openai_web_news_search(requests, payload)


@app.post("/v3/ai/news-odds/market/{market_id_or_slug}/search")
async def v3_ai_news_odds_market_search_page(
    market_id_or_slug: str,
    operator_notes: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    payload = {"operator_notes": operator_notes}
    requests = v4_ai_news_providers.build_news_search_requests(market, payload)
    result = v4_ai_news_providers.run_openai_web_news_search(requests, payload)
    status = "news_odds_search_completed" if result.get("external_network_called") else "news_odds_search_config_required"
    detail = result.get("message") or f"{len(requests.get('requests', []))}_requests"
    return _v3_action_redirect(
        f"/v3/markets/{market_id_or_slug}/news-odds",
        action_status=status,
        action_detail=str(detail)[:160],
    )


@app.post("/api/v3/ai/news-odds/market/{market_id_or_slug}/manual-evidence")
async def api_v3_ai_news_odds_market_manual_evidence(market_id_or_slug: str, payload: dict[str, Any] = Body(default_factory=dict)):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    evidence = payload.get("evidence") or payload.get("sources") or payload.get("items") or []
    packet = v4_ai_news_providers.run_manual_evidence_news_analysis(evidence)
    return {**packet, "market_id_or_slug": market_id_or_slug, "market_title": market.get("question") or market.get("title"), "review_only": True, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False}


@app.post("/v3/ai/news-odds/market/{market_id_or_slug}/manual-evidence")
async def v3_ai_news_odds_market_manual_evidence_page(
    market_id_or_slug: str,
    evidence_text: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    evidence = [{"title": "Operator manual evidence", "snippet": evidence_text, "source_type": "manual"}] if evidence_text.strip() else []
    packet = v4_ai_news_providers.run_manual_evidence_news_analysis(evidence)
    return _v3_action_redirect(
        f"/v3/markets/{market_id_or_slug}/news-odds",
        action_status="manual_evidence_previewed",
        action_detail=f"{packet.get('source_count', len(evidence))}_sources",
    )


@app.post("/api/v3/ai/news-odds/market/{market_id_or_slug}/adjust")
async def api_v3_ai_news_odds_market_adjust(market_id_or_slug: str, payload: dict[str, Any] = Body(default_factory=dict)):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    evidence = payload.get("evidence") or payload.get("sources") or payload.get("items") or []
    base = build_market_recommendation_row(market)
    packet = v4_ai_news_odds.build_news_odds_adjustment_packet(market, evidence, base)
    packet["explanation"] = v4_ai_news_odds.explain_news_odds_adjustment(packet)
    packet["safety_validation"] = v4_ai_news_odds.validate_news_adjustment_safety(packet)
    persisted = v4_ai_news_odds.persist_adjustment(packet) if bool(payload.get("write", True)) else {"ok": True, "adjustment": packet, "write": False}
    ai_edge_payload = {
        "title": f"AI News Odds Adjustment: {packet.get('market_title')}",
        "market_id": packet.get("market_id"),
        "market_title": packet.get("market_title"),
        "research_question": f"Review draft news-adjusted fair odds for {packet.get('market_title')}",
        "news_odds_adjustment_snapshot": packet,
        "evidence_sources": packet.get("source_records", []),
        "recommended_side": base.get("recommended_side"),
        "model_fair_yes": packet.get("adjusted_fair_yes"),
        "model_fair_source": "AI News Odds draft fair probability adjustment",
        "write": bool(payload.get("write_ai_edge_packet", False)),
    }
    ai_edge_packet = v4_ai_edge.generate_edge_packet(ai_edge_payload, write=bool(payload.get("write_ai_edge_packet", False)), mode="news_odds_adjustment")
    return {
        "version": APP_VERSION,
        "ok": True,
        "adjustment": persisted.get("adjustment", packet),
        "ai_edge_packet": ai_edge_packet.get("packet"),
        "review_only": True,
        "not_financial_advice": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
    }


@app.post("/v3/ai/news-odds/market/{market_id_or_slug}/adjust")
async def v3_ai_news_odds_market_adjust_page(
    market_id_or_slug: str,
    evidence_text: str = Form(default=""),
    write: bool = Form(default=False),
    user: dict = Depends(require_admin),
):
    evidence = [{"title": "Operator manual evidence", "snippet": evidence_text, "source_type": "manual"}] if evidence_text.strip() else []
    result = await api_v3_ai_news_odds_market_adjust(market_id_or_slug, {"evidence": evidence, "write": write, "write_ai_edge_packet": False})
    adjustment = result.get("adjustment", {}) if isinstance(result, dict) else {}
    adjustment_id = str(adjustment.get("adjustment_id") or "")
    if write and adjustment_id:
        return _v3_action_redirect(
            f"/v3/ai/news-odds/adjustment/{adjustment_id}",
            action_status="news_odds_adjustment_saved",
            action_detail=adjustment_id,
        )
    return _v3_action_redirect(
        f"/v3/markets/{market_id_or_slug}/news-odds",
        action_status="news_odds_adjustment_previewed",
        action_detail="preview_not_saved",
    )


@app.get("/api/v3/ai/news-odds/adjustments")
async def api_v3_ai_news_odds_adjustments(limit: int = Query(default=250, ge=1, le=5000), include_archived: bool = Query(default=False)):
    return v4_ai_news_odds.list_adjustments(limit=limit, include_archived=include_archived)


@app.get("/api/v3/ai/news-odds/adjustment/{adjustment_id}")
async def api_v3_ai_news_odds_adjustment(adjustment_id: str):
    return v4_ai_news_odds.get_adjustment(adjustment_id)


@app.post("/api/v3/ai/news-odds/adjustment/{adjustment_id}/accept-to-review-context")
async def api_v3_ai_news_odds_accept(adjustment_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v4_ai_news_odds.accept_adjustment_to_review_context(adjustment_id, payload)


@app.post("/api/v3/ai/news-odds/adjustment/{adjustment_id}/reject")
async def api_v3_ai_news_odds_reject(adjustment_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v4_ai_news_odds.reject_adjustment(adjustment_id, payload)


@app.post("/api/v3/ai/news-odds/adjustment/{adjustment_id}/archive")
async def api_v3_ai_news_odds_archive(adjustment_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    return v4_ai_news_odds.archive_adjustment(adjustment_id, payload)


@app.post("/v3/ai/news-odds/adjustment/{adjustment_id}/accept-to-review-context")
async def v3_ai_news_odds_accept_page(
    adjustment_id: str,
    operator_note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    result = v4_ai_news_odds.accept_adjustment_to_review_context(adjustment_id, {"operator_note": operator_note, "operator": user.get("username", "admin")})
    return _v3_action_redirect(
        f"/v3/ai/news-odds/adjustment/{adjustment_id}",
        action_status="news_odds_review_action_recorded" if result.get("ok") else "news_odds_review_action_blocked",
        action_detail="accepted_to_review_context",
    )


@app.post("/v3/ai/news-odds/adjustment/{adjustment_id}/reject")
async def v3_ai_news_odds_reject_page(
    adjustment_id: str,
    operator_note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    result = v4_ai_news_odds.reject_adjustment(adjustment_id, {"operator_note": operator_note, "operator": user.get("username", "admin")})
    return _v3_action_redirect(
        f"/v3/ai/news-odds/adjustment/{adjustment_id}",
        action_status="news_odds_review_action_recorded" if result.get("ok") else "news_odds_review_action_blocked",
        action_detail="rejected",
    )


@app.post("/v3/ai/news-odds/adjustment/{adjustment_id}/archive")
async def v3_ai_news_odds_archive_page(
    adjustment_id: str,
    operator_note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    result = v4_ai_news_odds.archive_adjustment(adjustment_id, {"operator_note": operator_note, "operator": user.get("username", "admin")})
    return _v3_action_redirect(
        f"/v3/ai/news-odds/adjustment/{adjustment_id}",
        action_status="news_odds_review_action_recorded" if result.get("ok") else "news_odds_review_action_blocked",
        action_detail="archived",
    )


@app.get("/api/v3/ai/news-odds/source/{source_id}")
async def api_v3_ai_news_odds_source(source_id: str):
    safe_id = str(source_id or "")
    matches = []
    for adjustment in v4_ai_news_odds.list_adjustments(limit=5000, include_archived=True).get("items", []):
        for source in adjustment.get("source_records", []) or []:
            if str(source.get("source_id") or source.get("canonical_domain") or source.get("url") or "") == safe_id:
                matches.append(source)
    return {"version": APP_VERSION, "source_id": safe_id, "count": len(matches), "items": matches, "review_only": True, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False}


@app.get("/v3/markets/{market_id_or_slug}/news-odds", response_class=HTMLResponse)
async def v3_market_news_odds_page(request: Request, market_id_or_slug: str):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    base = build_market_recommendation_row(market)
    preview = v4_ai_news_odds.build_news_odds_adjustment_packet(market, [], base)
    preview["explanation"] = v4_ai_news_odds.explain_news_odds_adjustment(preview)
    return templates.TemplateResponse(
        "market_news_odds.html",
        {
            "request": request,
            "user": current_user(request),
            "market": market,
            "edge": base,
            "preview": preview,
            "settings": v4_ai_news_odds.news_odds_settings_summary(),
        },
    )


@app.get("/v3/markets/family/{family_id}/news-odds", response_class=HTMLResponse)
async def v3_market_family_news_odds_page(request: Request, family_id: str, demo: bool = Query(default=True)):
    markets = await _review_market_rows(limit=200, demo=demo)
    comparison = build_family_comparison(markets, family_id)
    return templates.TemplateResponse(
        "family_news_odds.html",
        {
            "request": request,
            "user": current_user(request),
            "family": comparison,
            "settings": v4_ai_news_odds.news_odds_settings_summary(),
        },
    )


@app.post("/api/v3/ai/news-odds/family/{family_id}/plan")
async def api_v3_ai_news_odds_family_plan(family_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    markets = await _review_market_rows(limit=200, demo=bool(payload.get("demo", True)))
    family = build_family_comparison(markets, family_id)
    title = family.get("family_title") or family_id
    return v4_ai_news_odds.build_market_search_plan({"id": family_id, "question": title, "family_title": title}, operator_notes=payload.get("operator_notes"))


@app.post("/api/v3/ai/news-odds/family/{family_id}/search")
async def api_v3_ai_news_odds_family_search(family_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    plan = await api_v3_ai_news_odds_family_plan(family_id, payload)
    return v4_ai_news_providers.run_openai_web_news_search({"requests": plan.get("queries", [])}, payload)


@app.post("/api/v3/ai/news-odds/family/{family_id}/adjust")
async def api_v3_ai_news_odds_family_adjust(family_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    markets = await _review_market_rows(limit=200, demo=bool(payload.get("demo", True)))
    family = build_family_comparison(markets, family_id)
    items = []
    for row in family.get("items", [])[:25]:
        market = await _review_market_by_id(str(row.get("market_id")))
        if market:
            packet = v4_ai_news_odds.build_news_odds_adjustment_packet(market, payload.get("evidence") or payload.get("sources") or [], build_market_recommendation_row(market))
            packet["family_normalization_applied"] = False
            packet["family_normalization_note"] = "Family normalization not applied unless the family is clearly complete and mutually exhaustive."
            items.append(packet)
    return {"version": APP_VERSION, "family_id": family_id, "count": len(items), "items": items, "family_normalization_applied": False, "review_only": True, "order_submitted": False, "order_cancelled": False, "trade_approved": False, "live_trading_armed": False, "no_live_mutation": True}


@app.get("/v3/markets/family/{family_id}", response_class=HTMLResponse)
@app.get("/v3/ai/edge/family/{family_id}", response_class=HTMLResponse)
async def v3_market_family_page(request: Request, family_id: str, limit: int = Query(default=200, ge=20, le=500), demo: bool = Query(default=False)):
    markets = await _review_market_rows(limit=limit, demo=demo)
    comparison = build_family_comparison(markets, family_id)
    return templates.TemplateResponse(
        "market_family_comparison.html",
        {
            "request": request,
            "user": current_user(request),
            "family": comparison,
            "limit": limit,
            "demo_mode": demo or any(row.get("demo_fixture") for row in markets),
        },
    )


@app.get("/api/v3/markets/family/{family_id}/summary")
async def api_v3_market_family_summary(family_id: str, limit: int = Query(default=200, ge=20, le=500), demo: bool = Query(default=False)):
    markets = await _review_market_rows(limit=limit, demo=demo)
    return build_family_comparison(markets, family_id)


@app.get("/v3/markets/{market_id_or_slug}", response_class=HTMLResponse)
@app.get("/market/{market_id_or_slug}", response_class=HTMLResponse)
async def v3_market_detail_page(request: Request, market_id_or_slug: str):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    detail = build_market_detail_context(market, v4_ai_edge.list_packets(limit=500).get("items", []))
    return templates.TemplateResponse(
        "market_detail_v46.html",
        {
            "request": request,
            "user": current_user(request),
            "detail": detail,
            "market": detail["market"],
            "edge": detail["edge"],
            "review_record": detail["review_record"],
            "operator_notes": detail["operator_notes"],
            "ai_edge_packet_lifecycle": detail["ai_edge_packet_lifecycle"],
        },
    )


@app.get("/api/v3/markets/{market_id_or_slug}/summary")
async def api_v3_market_summary(market_id_or_slug: str):
    market = await _review_market_by_id(market_id_or_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return build_market_detail_context(market, v4_ai_edge.list_packets(limit=500).get("items", []))


@app.get("/markets/{market_id}", response_class=HTMLResponse)
async def market_detail(request: Request, market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    books = []
    if scored.get("clob_token_ids"):
        books = await clob.get_books_for_tokens(scored["clob_token_ids"])
    research = make_research_packet(scored)
    source_pack = build_market_source_pack(scored)
    watched_ids = {str(item.get("market_id")) for item in load_watchlist()}
    return templates.TemplateResponse("market_detail.html", {"request": request, "market": scored, "order_books": books, "research": research, "source_pack": source_pack, "is_watched": str(scored.get("id")) in watched_ids, "portfolio": summarize_portfolio([scored]), "risk_status": risk_status(load_portfolio()), "risk_check": check_paper_buy(scored, load_portfolio(), stake=100.0, price=float(scored.get("probability_model", {}).get("market_probability") or 0.5), outcome="YES"), "market_notes": notes_for_market(market_id), "evidence_packets": [p for p in list_manual_evidence_packets(limit=25) if str(p.get("market_id")) == str(market_id)], "evidence_score": score_market_evidence(market_id), "evidence_probability": evidence_adjusted_probability(scored), "user": current_user(request)})


@app.get("/research/sources", response_class=HTMLResponse)
async def research_sources_page(request: Request):
    return templates.TemplateResponse("research_sources.html", {"request": request, "user": current_user(request), "summary": source_summary(), "sources": list_sources(), "status_url": "/api/sources/status"})


@app.get("/research/evidence", response_class=HTMLResponse)
async def research_evidence_page(request: Request):
    packets = []
    for row in list_manual_evidence_packets(limit=100):
        enriched = dict(row)
        packet_id = str(row.get("packet_id") or "")
        if packet_id:
            try:
                score = score_packet_by_id(packet_id)
                enriched["score"] = score.get("score")
                enriched["readiness"] = score.get("readiness")
            except Exception:
                enriched["readiness"] = "score_unavailable"
        packets.append(enriched)
    return templates.TemplateResponse("research_evidence.html", {"request": request, "user": current_user(request), "summary": evidence_summary(limit=20), "packets": packets})


@app.get("/api/evidence")
async def evidence_api(limit: int = Query(default=50, ge=1, le=200)):
    return {"source": "local", "summary": evidence_summary(limit=limit), "items": list_manual_evidence_packets(limit=limit)}


@app.get("/api/evidence/{packet_id}")
async def evidence_detail_api(packet_id: str):
    try:
        return {"source": "local", "item": load_evidence_packet(packet_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evidence packet not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc






@app.get("/api/markets/{market_id}/evidence-probability")
async def market_evidence_probability_api(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    return {"source": "local", "mode": "evidence_adjusted_probability", "item": evidence_adjusted_probability(scored)}


@app.get("/api/evidence-probabilities")
async def evidence_probabilities_api(limit: int = Query(default=settings.default_limit, ge=1, le=100)):
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    return {"source": "gamma+local_evidence", "mode": "evidence_adjusted_probability", "items": attach_evidence_probability(markets)}

@app.get("/api/evidence/{packet_id}/score")
async def evidence_score_api(packet_id: str):
    try:
        return {"source": "local", "mode": "evidence_readiness_score", "item": score_packet_by_id(packet_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evidence packet not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/markets/{market_id}/evidence-score")
async def market_evidence_score_api(market_id: str):
    return {"source": "local", "mode": "market_evidence_readiness", "item": score_market_evidence(market_id)}

@app.delete("/api/evidence/{packet_id}")
async def evidence_delete_api(packet_id: str, user: dict = Depends(require_admin)):
    try:
        return {"ok": delete_evidence_packet(packet_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/markets/{market_id}/evidence-packet")
async def create_market_evidence_packet_api(market_id: str, include_weak_sources: bool = Query(default=False), note: str = Query(default=""), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    return {"source": "local", "item": create_manual_evidence_packet(scored, created_by=user.get("username", "admin"), note=note, include_weak_sources=include_weak_sources)}


@app.post("/markets/{market_id}/evidence-packet")
async def create_market_evidence_packet_page(market_id: str, include_weak_sources: bool = Form(default=False), note: str = Form(default=""), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    create_manual_evidence_packet(scored, created_by=user.get("username", "admin"), note=note, include_weak_sources=include_weak_sources)
    return RedirectResponse(url=f"/markets/{market_id}", status_code=303)


@app.get("/api/markets/{market_id}/evidence-packets")
async def market_evidence_packets_api(market_id: str, limit: int = Query(default=50, ge=1, le=200)):
    items = [row for row in list_manual_evidence_packets(limit=limit) if str(row.get("market_id")) == str(market_id)]
    return {"source": "local", "market_id": market_id, "items": items}


@app.get("/api/sources")
async def sources_api(category: str | None = Query(default=None)):
    return {"source": "local", "summary": source_summary(), "items": list_sources(category=category)}


@app.get("/api/source-links")
async def source_links_api(q: str = Query(..., min_length=1), category: str | None = Query(default=None)):
    return {"source": "local", "query": q, "items": build_source_links(q, category=category)}


@app.get("/api/markets/{market_id}/source-pack")
async def market_source_pack_api(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    return {"source": "local", "item": build_market_source_pack(scored)}


@app.get("/api/sources/status")
async def sources_status_api(category: str | None = Query(default=None), timeout: float = Query(default=4.0, ge=1.0, le=10.0)):
    return {"source": "local", "mode": "live_availability_check", "result": await check_sources_status(category=category, timeout=timeout)}


@app.get("/api/markets/{market_id}/collection-targets")
async def market_collection_targets_api(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    return {"source": "local", "mode": "research_collection_targets", "item": build_market_collection_targets(scored)}


@app.get("/api/markets/{market_id}/links")
async def market_links(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return {
        "source": "local",
        "note": "Use high-confidence direct URLs when parent event_slug is known; otherwise the app falls back to Polymarket search instead of guessing a dead event URL.",
        "market_id": market_id,
        "question": market.get("question"),
        "primary_url": market.get("polymarket_url"),
        "confidence": market.get("polymarket_url_confidence"),
        "search_url": market.get("polymarket_search_url"),
        "candidates": market.get("polymarket_url_candidates", []),
        "raw_slug_fields": {"slug": market.get("slug"), "event_slug": market.get("event_slug")},
    }


@app.get("/api/notes")
async def notes_api(limit: int = Query(default=25, ge=1, le=100)):
    return {"source": "local", "summary": notes_summary(limit=limit), "items": list(reversed(load_notes()))[:limit]}


@app.get("/api/markets/{market_id}/notes")
async def market_notes_api(market_id: str):
    return {"source": "local", "market_id": market_id, "items": notes_for_market(market_id)}


@app.post("/api/markets/{market_id}/notes")
async def add_market_note_api(market_id: str, text: str = Query(..., min_length=1), tag: str = Query(default="research"), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    try:
        return add_note(market, text=text, tag=tag)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/notes/add/{market_id}")
async def add_market_note_page(market_id: str, text: str = Query(..., min_length=1), tag: str = Query(default="research"), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    try:
        add_note(market, text=text, tag=tag)
    except ValueError:
        pass
    return RedirectResponse(url=f"/markets/{market_id}", status_code=303)


@app.get("/notes/delete/{note_id}")
async def delete_market_note_page(note_id: str, market_id: str = Query(default=""), user: dict = Depends(require_admin)):
    delete_note(note_id)
    if market_id:
        return RedirectResponse(url=f"/markets/{market_id}", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/keys/status")
async def api_key_status():
    return get_api_key_status()


@app.get("/api/events/top")
async def top_events(limit: int = Query(default=settings.default_limit, ge=1, le=100)):
    return {"source": "gamma", "items": await client.list_events(limit=limit)}


@app.get("/api/markets/top")
async def top_markets(limit: int = Query(default=settings.default_limit, ge=1, le=100)):
    markets = _score_market_rows(await client.list_markets(limit=limit))
    return {"source": "gamma", "summary": summarize_snapshot(markets), "items": markets}


@app.get("/api/markets/opportunities")
async def opportunities(limit: int = Query(default=settings.default_limit, ge=1, le=100)):
    markets = _score_market_rows(await client.list_markets(limit=limit))
    return {"source": "gamma", "note": "Probability model v1 is for paper trading only, not financial advice.", "items": markets}


@app.get("/api/markets/edge-legend")
async def market_edge_legend_api():
    return {"source": "local", "item": edge_recommendation_legend(), "order_submitted": False, "order_cancelled": False, "trade_approved": False, "live_trading_armed": False}


@app.get("/api/markets/family-rankings")
async def market_family_rankings_api(limit: int = Query(default=settings.default_limit, ge=2, le=200)):
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    return {"source": "gamma+local", "items": rank_market_family(markets), "note": "Favorite ranking is separate from edge and is research-only.", "order_submitted": False, "order_cancelled": False, "trade_approved": False}


@app.get("/api/markets/{market_id}/edge-recommendation")
async def market_edge_recommendation_api(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    return {"source": "gamma+local", "item": scored.get("market_edge_recommendation"), "legend": edge_recommendation_legend(), "order_submitted": False, "order_cancelled": False, "trade_approved": False, "live_trading_armed": False}


@app.get("/api/markets/{market_id}")
async def market_api(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return {"source": "gamma", "item": _score_market_rows([market])[0]}


@app.post("/api/snapshots")
async def create_snapshot(limit: int = Query(default=100, ge=1, le=500), user: dict = Depends(require_admin)):
    markets = _score_market_rows(await client.list_markets(limit=limit))
    return save_snapshot(markets)


@app.get("/api/snapshots/latest")
async def latest_snapshot():
    payload = load_latest()
    if not payload:
        return {"found": False, "snapshot": None}
    return {"found": True, "snapshot": payload}


@app.get("/api/snapshots")
async def snapshots(limit: int = Query(default=25, ge=1, le=100)):
    return {"items": list_snapshots(limit=limit)}


@app.get("/api/movers")
async def movers(limit: int = Query(default=100, ge=1, le=500)):
    previous = load_latest()
    markets = _score_market_rows(await client.list_markets(limit=limit))
    return {
        "source": "gamma",
        "previous_snapshot_found": previous is not None,
        "items": calculate_movers(markets, previous),
        "new_markets": detect_new_markets(markets, previous),
    }


@app.get("/api/clob/book/{token_id}")
async def clob_book(token_id: str):
    return {"source": "clob", "auth_required": False, "item": await clob.get_order_book(token_id)}


@app.get("/api/markets/{market_id}/orderbooks")
async def market_orderbooks(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    token_ids = market.get("clob_token_ids") or []
    if not token_ids:
        return {"source": "clob", "market_id": market_id, "items": [], "note": "No CLOB token IDs were present in Gamma metadata."}
    return {"source": "clob", "auth_required": False, "market_id": market_id, "items": await clob.get_books_for_tokens(token_ids)}


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1), limit: int = Query(default=20, ge=1, le=100)):
    return {"source": "gamma", "query": q, "results": await client.search(q, limit=limit)}


@app.get("/api/markets/{market_id}/research")
async def market_research(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    return {"source": "local", "note": "Research packet only; not a trading signal.", "item": make_research_packet(scored)}



@app.get("/watchlist/add/{market_id}")
async def add_watchlist_page(market_id: str, note: str = Query(default="Research candidate"), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    add_to_watchlist(market, note=note)
    return RedirectResponse(url=f"/markets/{market_id}", status_code=303)


@app.get("/watchlist/remove/{market_id}")
async def remove_watchlist_page(market_id: str, user: dict = Depends(require_admin)):
    remove_from_watchlist(market_id)
    return RedirectResponse(url=f"/markets/{market_id}", status_code=303)


@app.get("/api/watchlist")
async def watchlist_api():
    return {"items": load_watchlist()}


@app.post("/api/watchlist/{market_id}")
async def add_watchlist_api(market_id: str, note: str = Query(default=""), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return {"ok": True, "item": add_to_watchlist(market, note=note)}


@app.delete("/api/watchlist/{market_id}")
async def remove_watchlist_api(market_id: str, user: dict = Depends(require_admin)):
    return {"ok": remove_from_watchlist(market_id)}


@app.get("/api/probabilities")
async def probabilities(limit: int = Query(default=settings.default_limit, ge=1, le=100)):
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    return {"source": "local", "note": "Deterministic probability model v1 for paper trading only.", "items": markets}




@app.get("/api/alerts")
async def alerts_api(limit: int = Query(default=100, ge=1, le=500)):
    previous = load_latest()
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    movers = calculate_movers(markets, previous)[:50]
    portfolio = summarize_portfolio(markets)
    risk = risk_status(load_portfolio())
    alerts = generate_alerts(markets, movers=movers, portfolio=portfolio, risk=risk, max_items=100)
    alerts.extend(position_alerts(portfolio))
    alerts.extend(risk_budget_alerts(build_risk_budget(markets, limit=20)))
    alerts.extend(preflight_alerts(build_preflight_board(limit=20)))
    alerts.extend(approval_alerts(build_execution_approval_board(limit=20)))
    alerts.extend(execution_queue_alerts(build_execution_queue(limit=20)))
    return {"source": "local", "mode": "paper_only", "summary": summarize_alerts(alerts), "items": alerts}


@app.get("/api/paper/analytics")
async def paper_analytics():
    markets = _score_market_rows(await client.list_markets(limit=100, order="volume24hr"))
    portfolio = summarize_portfolio(markets)
    trades = load_trades()
    return {"source": "local", "mode": "paper_only", "analytics": trade_analytics(trades, portfolio), "portfolio": portfolio}


@app.get("/api/paper/trades.csv", response_class=PlainTextResponse)
async def paper_trades_csv():
    return PlainTextResponse(trades_to_csv(load_trades()), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=paper_trades.csv"})

@app.get("/api/portfolio")
async def portfolio_api(limit: int = Query(default=100, ge=1, le=500)):
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    return summarize_portfolio(markets)


@app.get("/api/paper/trades")
async def paper_trades_api():
    return {"items": load_trades()}


@app.get("/api/paper/audit")
async def paper_audit_api(
    limit: int = Query(default=250, ge=1, le=2000),
    market_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    rows = build_audit_events(limit=limit, market_id=market_id, category=category)
    return {"source": "local", "mode": "paper_audit_ledger_v038", "summary": summarize_audit(rows), "items": rows}


@app.get("/api/paper/audit.csv", response_class=PlainTextResponse)
async def paper_audit_csv(
    limit: int = Query(default=2000, ge=1, le=10000),
    market_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    rows = build_audit_events(limit=limit, market_id=market_id, category=category)
    return PlainTextResponse(audit_to_csv(rows), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=paper_audit.csv"})


@app.get("/api/paper/audit/{market_id}")
async def paper_market_audit_api(market_id: str, limit: int = Query(default=250, ge=1, le=2000)):
    return {"source": "local", "mode": "paper_market_audit_v038", **build_market_audit(market_id, limit=limit)}


@app.get("/audit", response_class=HTMLResponse)
async def paper_audit_page(
    request: Request,
    limit: int = Query(default=250, ge=1, le=2000),
    market_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
):
    rows = build_audit_events(limit=limit, market_id=market_id, category=category)
    return templates.TemplateResponse(
        "audit_v038.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": summarize_audit(rows),
            "items": rows,
            "limit": limit,
            "market_id": market_id or "",
            "category": category or "",
        },
    )




@app.get("/api/paper/review-report")
async def paper_review_report_api(
    limit: int = Query(default=100, ge=1, le=1000),
    market_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    report = build_review_report(limit=limit, market_id=market_id, status=status)
    return {"source": "local", "mode": "paper_review_report_v039", **report}


@app.get("/api/paper/review-report.csv", response_class=PlainTextResponse)
async def paper_review_report_csv(
    limit: int = Query(default=1000, ge=1, le=10000),
    market_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    report = build_review_report(limit=limit, market_id=market_id, status=status)
    return PlainTextResponse(
        review_report_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_review_report.csv"},
    )


@app.get("/api/paper/review-report/{market_id}")
async def paper_market_review_api(market_id: str):
    return {"source": "local", "mode": "paper_market_review_v039", **build_market_review(market_id)}


@app.get("/review-report", response_class=HTMLResponse)
async def paper_review_report_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    market_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    report = build_review_report(limit=limit, market_id=market_id, status=status)
    return templates.TemplateResponse(
        "review_report_v039.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "limit": limit,
            "market_id": market_id or "",
            "status": status or "",
            "guardrail": report.get("guardrail", ""),
        },
    )


@app.get("/api/paper/positions")
async def paper_positions_api(limit: int = Query(default=100, ge=1, le=500)):
    try:
        markets = _score_market_rows(await client.list_markets(limit=min(limit, 200), order="volume24hr"))
    except Exception:
        markets = []
    portfolio = summarize_portfolio(markets)
    return {
        "source": "local",
        "mode": "paper_position_lifecycle_v036",
        "summary": position_control_summary(portfolio),
        "alerts": position_alerts(portfolio),
        "portfolio": portfolio,
        "events": list_position_events(limit=limit),
    }


@app.get("/api/paper/position-alerts")
async def paper_position_alerts_api(limit: int = Query(default=100, ge=1, le=500)):
    try:
        markets = _score_market_rows(await client.list_markets(limit=min(limit, 200), order="volume24hr"))
    except Exception:
        markets = []
    portfolio = summarize_portfolio(markets)
    rows = position_alerts(portfolio)
    return {"source": "local", "mode": "paper_position_lifecycle_v036", "count": len(rows), "items": rows[:limit]}


@app.post("/api/paper/positions/{market_id}/plan")
async def paper_position_plan_api(
    market_id: str,
    outcome: str = Query(default="YES"),
    target_price: str | None = Query(default=None),
    stop_price: str | None = Query(default=None),
    max_hold_days: str | None = Query(default=None),
    status: str = Query(default="active"),
    review_note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    try:
        return update_position_plan(
            market_id,
            outcome=outcome,
            target_price=target_price,
            stop_price=stop_price,
            max_hold_days=max_hold_days,
            status=status,
            review_note=review_note,
            updated_by=user.get("username", "admin"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/positions", response_class=HTMLResponse)
async def positions_page(request: Request, limit: int = Query(default=100, ge=1, le=500)):
    try:
        markets = _score_market_rows(await client.list_markets(limit=min(limit, 200), order="volume24hr"))
    except Exception:
        markets = []
    portfolio = summarize_portfolio(markets)
    return templates.TemplateResponse(
        "positions_v036.html",
        {
            "request": request,
            "user": current_user(request),
            "portfolio": portfolio,
            "summary": position_control_summary(portfolio),
            "alerts": position_alerts(portfolio),
            "events": list_position_events(limit=50),
            "limit": limit,
        },
    )


@app.post("/paper/positions/plan")
async def paper_position_plan_page(
    market_id: str = Form(...),
    outcome: str = Form(default="YES"),
    target_price: str = Form(default=""),
    stop_price: str = Form(default=""),
    max_hold_days: str = Form(default=""),
    status: str = Form(default="active"),
    review_note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    try:
        update_position_plan(
            market_id,
            outcome=outcome,
            target_price=target_price,
            stop_price=stop_price,
            max_hold_days=max_hold_days,
            status=status,
            review_note=review_note,
            updated_by=user.get("username", "admin"),
        )
    except ValueError:
        pass
    return RedirectResponse(url="/positions", status_code=303)


@app.post("/api/paper/reset")
async def paper_reset_api(cash: float = Query(default=10000.0, gt=0), user: dict = Depends(require_admin)):
    return reset_portfolio(cash=cash)


@app.post("/api/paper/buy/{market_id}")
async def paper_buy_api(market_id: str, stake: float = Query(default=100.0, gt=0), outcome: str = Query(default="YES"), reason: str = Query(default="manual paper buy"), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    try:
        return paper_buy(scored, outcome=outcome, stake=stake, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/paper/sell/{market_id}")
async def paper_sell_api(market_id: str, outcome: str = Query(default="YES"), shares: float | None = Query(default=None), reason: str = Query(default="manual paper sell"), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    try:
        return paper_sell(scored, outcome=outcome, shares=shares, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/paper/settlements")
async def paper_settlements_api(limit: int = Query(default=100, ge=1, le=500), market_id: str | None = Query(default=None)):
    rows = list_settlements(limit=limit, market_id=market_id)
    return {"source": "local", "mode": "paper_only_manual_settlements", "summary": settlement_summary(rows), "items": rows}


@app.get("/api/paper/settlement-candidates")
async def paper_settlement_candidates_api(limit: int = Query(default=100, ge=1, le=500)):
    rows = settlement_candidates(limit=limit)
    return {"source": "local", "mode": "paper_only_manual_settlement_candidates", "count": len(rows), "items": rows}


@app.get("/api/paper/settlement-preview/{market_id}")
async def paper_settlement_preview_api(market_id: str, winning_outcome: str = Query(default="YES")):
    return {"source": "local", "mode": "paper_only_manual_settlement_preview", "item": preview_settlement(market_id, winning_outcome=winning_outcome)}


@app.post("/api/paper/settle/{market_id}")
async def paper_settle_api(
    market_id: str,
    winning_outcome: str = Query(default="YES"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    try:
        return settle_market(market_id, winning_outcome=winning_outcome, note=note, resolved_by=user.get("username", "admin"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/settlements", response_class=HTMLResponse)
async def settlements_page(request: Request, limit: int = Query(default=100, ge=1, le=500)):
    try:
        markets = _score_market_rows(await client.list_markets(limit=min(limit, 100), order="volume24hr"))
    except Exception:
        markets = []
    portfolio_summary = summarize_portfolio(markets)
    rows = list_settlements(limit=limit)
    return templates.TemplateResponse(
        "settlements_v035.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": settlement_summary(rows),
            "settlements": rows,
            "candidates": settlement_candidates(limit=limit),
            "portfolio": portfolio_summary,
            "limit": limit,
        },
    )


@app.post("/paper/settle")
async def paper_settle_page(
    market_id: str = Form(...),
    winning_outcome: str = Form(default="YES"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    try:
        settle_market(market_id, winning_outcome=winning_outcome, note=note, resolved_by=user.get("username", "admin"))
    except ValueError:
        pass
    return RedirectResponse(url="/settlements", status_code=303)


@app.get("/paper/buy/{market_id}")
async def paper_buy_page(market_id: str, stake: float = Query(default=100.0, gt=0), outcome: str = Query(default="YES"), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    try:
        paper_buy(scored, outcome=outcome, stake=stake, reason="dashboard paper buy")
    except ValueError:
        pass
    return RedirectResponse(url=f"/markets/{market_id}", status_code=303)


@app.get("/paper/sell/{market_id}")
async def paper_sell_page(market_id: str, outcome: str = Query(default="YES"), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    try:
        paper_sell(scored, outcome=outcome, reason="dashboard paper sell all")
    except ValueError:
        pass
    return RedirectResponse(url=f"/markets/{market_id}", status_code=303)


@app.get("/api/risk/status")
async def risk_status_api():
    return risk_status(load_portfolio())


# --- v0.4.2 Paper Risk Budget Review ---

async def _risk_budget_markets(limit: int = 200) -> list[dict[str, Any]]:
    try:
        return _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    except Exception:
        return []


@app.get("/api/paper/risk-budget")
async def paper_risk_budget_api(
    limit: int = Query(default=100, ge=1, le=1000),
    market_id: str | None = Query(default=None),
):
    markets = await _risk_budget_markets(limit=min(max(limit, 50), 200))
    return {"source": "local", "mode": "paper_risk_budget_v042", **build_risk_budget(markets, limit=limit, market_id=market_id)}


@app.get("/api/paper/risk-budget.csv", response_class=PlainTextResponse)
async def paper_risk_budget_csv(
    limit: int = Query(default=1000, ge=1, le=10000),
    market_id: str | None = Query(default=None),
):
    markets = await _risk_budget_markets(limit=200)
    report = build_risk_budget(markets, limit=limit, market_id=market_id)
    return PlainTextResponse(
        risk_budget_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_risk_budget.csv"},
    )


@app.get("/api/paper/risk-budget/{market_id}")
async def paper_market_risk_budget_api(market_id: str):
    markets = await _risk_budget_markets(limit=200)
    return {"source": "local", "mode": "paper_market_risk_budget_v042", **build_market_risk_budget(market_id, markets)}


@app.get("/risk-budget", response_class=HTMLResponse)
async def paper_risk_budget_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    market_id: str | None = Query(default=None),
):
    markets = await _risk_budget_markets(limit=min(max(limit, 50), 200))
    report = build_risk_budget(markets, limit=limit, market_id=market_id)
    detail = build_market_risk_budget(market_id, markets) if market_id else None
    return templates.TemplateResponse(
        "risk_budget_v042.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": report.get("summary", {}),
            "limits": report.get("limits", {}),
            "items": report.get("items", []),
            "flags": report.get("flags", []),
            "guardrail": report.get("guardrail", ""),
            "limit": limit,
            "market_id": market_id or "",
            "detail": detail,
        },
    )


# --- v0.4.3 Paper Entry Preflight Gate ---

async def _preflight_opportunities_map(limit: int = 200) -> dict[str, dict]:
    try:
        opportunities = await _ranked_opportunities(limit=max(50, min(max(limit, 50), 300)))
    except Exception:
        opportunities = []
    return {str(row.get("market_id") or row.get("id") or row.get("conditionId") or row.get("slug") or ""): row for row in opportunities}


@app.get("/api/paper/preflight")
async def paper_preflight_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    strict_playbook: bool = Query(default=False),
    live: bool = Query(default=True),
):
    opportunities_by_market = await _preflight_opportunities_map(limit=limit) if live else {}
    return {"source": "local", "mode": "paper_preflight_gate_v043", **build_preflight_board(limit=limit, status=status, strict_playbook=strict_playbook, opportunities_by_market=opportunities_by_market)}


@app.get("/api/paper/preflight.csv", response_class=PlainTextResponse)
async def paper_preflight_csv(
    limit: int = Query(default=1000, ge=1, le=10000),
    status: str | None = Query(default=None),
    strict_playbook: bool = Query(default=False),
    live: bool = Query(default=True),
):
    opportunities_by_market = await _preflight_opportunities_map(limit=min(limit, 300)) if live else {}
    report = build_preflight_board(limit=limit, status=status, strict_playbook=strict_playbook, opportunities_by_market=opportunities_by_market)
    return PlainTextResponse(
        preflight_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_preflight.csv"},
    )


@app.get("/api/paper/preflight/{ticket_id}")
async def paper_ticket_preflight_api(
    ticket_id: str,
    strict_playbook: bool = Query(default=False),
    live: bool = Query(default=True),
):
    ticket = get_trade_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Trade ticket not found")
    opportunity = None
    if live:
        try:
            opportunity = await _get_opportunity_for_ticket(str(ticket.get("market_id") or ""))
        except Exception:
            opportunity = None
    return {"source": "local", "mode": "paper_ticket_preflight_v043", "item": build_ticket_preflight(ticket, opportunity=opportunity, strict_playbook=strict_playbook)}


@app.post("/api/trade-tickets/{ticket_id}/preflight")
async def paper_ticket_preflight_post_api(
    ticket_id: str,
    strict_playbook: bool = Query(default=False),
    live: bool = Query(default=True),
    user: dict = Depends(require_admin),
):
    return await paper_ticket_preflight_api(ticket_id, strict_playbook=strict_playbook, live=live)


@app.get("/preflight", response_class=HTMLResponse)
async def paper_preflight_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    strict_playbook: bool = Query(default=False),
    ticket_id: str | None = Query(default=None),
    live: bool = Query(default=True),
):
    opportunities_by_market = await _preflight_opportunities_map(limit=limit) if live else {}
    report = build_preflight_board(limit=limit, status=status, strict_playbook=strict_playbook, opportunities_by_market=opportunities_by_market)
    detail = None
    if ticket_id:
        ticket = get_trade_ticket(ticket_id)
        if ticket:
            opportunity = opportunities_by_market.get(str(ticket.get("market_id") or ""))
            detail = build_ticket_preflight(ticket, opportunity=opportunity, strict_playbook=strict_playbook)
    return templates.TemplateResponse(
        "preflight_v043.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "guardrail": report.get("guardrail", ""),
            "limit": limit,
            "status": status or "",
            "strict_playbook": strict_playbook,
            "live": live,
            "ticket_id": ticket_id or "",
            "detail": detail,
        },
    )


# --- v0.4.4 Paper Execution Approvals ---


@app.get("/api/paper/approvals")
async def paper_approvals_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    ticket_id: str | None = Query(default=None),
):
    return {"source": "local", "mode": "paper_execution_approvals_v044", **build_execution_approval_board(limit=limit, status=status, market_id=market_id, ticket_id=ticket_id)}


@app.get("/api/paper/approvals.csv", response_class=PlainTextResponse)
async def paper_approvals_csv(
    limit: int = Query(default=1000, ge=1, le=10000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    ticket_id: str | None = Query(default=None),
):
    report = build_execution_approval_board(limit=limit, status=status, market_id=market_id, ticket_id=ticket_id)
    return PlainTextResponse(
        approvals_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_execution_approvals.csv"},
    )


@app.get("/api/paper/approvals/{approval_id}")
async def paper_approval_detail_api(approval_id: str):
    item = get_execution_approval(approval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Paper approval record not found")
    return {"source": "local", "mode": "paper_execution_approval_v044", "item": item}


@app.post("/api/trade-tickets/{ticket_id}/approval")
async def approve_trade_ticket_api(
    ticket_id: str,
    note: str = Query(default=""),
    strict_playbook: bool = Query(default=False),
    live: bool = Query(default=True),
    user: dict = Depends(require_admin),
):
    opportunity = None
    if live:
        ticket = get_trade_ticket(ticket_id)
        if ticket:
            try:
                opportunity = await _get_opportunity_for_ticket(str(ticket.get("market_id") or ""))
            except Exception:
                opportunity = None
    try:
        item = approve_trade_ticket(ticket_id, operator=user.get("username", "admin"), note=note, strict_playbook=strict_playbook, opportunity=opportunity)
        return {"ok": bool(item.get("approved")), "item": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/trade-tickets/{ticket_id}/approval")
async def approve_trade_ticket_page(
    ticket_id: str,
    note: str = Form(default=""),
    strict_playbook: bool = Form(default=False),
    live: bool = Form(default=True),
    user: dict = Depends(require_admin),
):
    try:
        await approve_trade_ticket_api(ticket_id, note=note, strict_playbook=strict_playbook, live=live, user=user)
    except HTTPException:
        pass
    return RedirectResponse(url=f"/approvals?ticket_id={ticket_id}", status_code=303)


@app.post("/api/trade-tickets/{ticket_id}/reject")
async def reject_trade_ticket_api(
    ticket_id: str,
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    try:
        item = reject_trade_ticket(ticket_id, operator=user.get("username", "admin"), note=note)
        return {"ok": True, "item": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/trade-tickets/{ticket_id}/reject")
async def reject_trade_ticket_page(
    ticket_id: str,
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    try:
        await reject_trade_ticket_api(ticket_id, note=note, user=user)
    except HTTPException:
        pass
    return RedirectResponse(url=f"/approvals?ticket_id={ticket_id}", status_code=303)


@app.get("/approvals", response_class=HTMLResponse)
async def paper_approvals_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    ticket_id: str | None = Query(default=None),
    approval_id: str | None = Query(default=None),
):
    report = build_execution_approval_board(limit=limit, status=status, market_id=market_id, ticket_id=ticket_id)
    detail = get_execution_approval(approval_id) if approval_id else None
    if not detail and approval_id:
        raise HTTPException(status_code=404, detail="Paper approval record not found")
    return templates.TemplateResponse(
        "approvals_v044.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "guardrail": report.get("guardrail", ""),
            "limit": limit,
            "status": status or "",
            "market_id": market_id or "",
            "ticket_id": ticket_id or "",
            "approval_id": approval_id or "",
            "detail": detail,
        },
    )


# --- v0.4.6 Paper Execution Queue ---


@app.get("/api/paper/execution-queue")
async def paper_execution_queue_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    ticket_id: str | None = Query(default=None),
    strict_playbook: bool = Query(default=False),
):
    return {
        "source": "local",
        "mode": "paper_execution_queue_v045",
        **build_execution_queue(limit=limit, status=status, market_id=market_id, ticket_id=ticket_id, strict_playbook=strict_playbook),
    }


@app.get("/api/paper/execution-queue.csv", response_class=PlainTextResponse)
async def paper_execution_queue_csv(
    limit: int = Query(default=1000, ge=1, le=10000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    ticket_id: str | None = Query(default=None),
    strict_playbook: bool = Query(default=False),
):
    report = build_execution_queue(limit=limit, status=status, market_id=market_id, ticket_id=ticket_id, strict_playbook=strict_playbook)
    return PlainTextResponse(
        execution_queue_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_execution_queue.csv"},
    )


@app.get("/api/paper/execution-queue/{ticket_id}")
async def paper_execution_queue_detail_api(ticket_id: str, strict_playbook: bool = Query(default=False)):
    ticket = get_trade_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Trade ticket not found")
    return {"source": "local", "mode": "paper_execution_queue_v045", "item": build_ticket_execution_queue_item(ticket, strict_playbook=strict_playbook)}


@app.get("/execution-queue", response_class=HTMLResponse)
async def paper_execution_queue_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    ticket_id: str | None = Query(default=None),
    strict_playbook: bool = Query(default=False),
):
    report = build_execution_queue(limit=limit, status=status, market_id=market_id, ticket_id=ticket_id, strict_playbook=strict_playbook)
    detail = None
    if ticket_id:
        ticket = get_trade_ticket(ticket_id)
        if ticket:
            detail = build_ticket_execution_queue_item(ticket, strict_playbook=strict_playbook)
    return templates.TemplateResponse(
        "execution_queue_v045.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "guardrail": report.get("guardrail", ""),
            "limit": limit,
            "status": status or "",
            "market_id": market_id or "",
            "ticket_id": ticket_id or "",
            "strict_playbook": strict_playbook,
            "detail": detail,
        },
    )


# --- v0.5.0 Ops Aging + v0.4.9 Handoff Reconciliation + v0.4.8 Handoffs + v0.4.7 Briefing + v0.4.6 Runbook ---


@app.get("/api/paper/briefing")
async def paper_ops_briefing_api(
    limit: int = Query(default=100, ge=1, le=1000),
    section: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    return build_paper_ops_briefing(limit=limit, section=section, status=status, market_id=market_id)


@app.get("/api/paper/briefing.csv", response_class=PlainTextResponse)
async def paper_ops_briefing_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    section: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    report = build_paper_ops_briefing(limit=limit, section=section, status=status, market_id=market_id)
    return PlainTextResponse(
        briefing_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_ops_briefing.csv"},
    )


@app.get("/api/paper/briefing/checkpoints")
async def paper_ops_briefing_checkpoints_api(limit: int = Query(default=100, ge=1, le=1000), status: str | None = Query(default=None)):
    return {"source": "local", "mode": "paper_ops_briefing_checkpoints_v047", "items": list_briefing_checkpoints(limit=limit, status=status)}


@app.post("/api/paper/briefing/checkpoint")
async def paper_ops_briefing_checkpoint_api(
    status: str = Form(default="reviewed"),
    note: str = Form(default=""),
    section: str = Form(default=""),
    user: dict = Depends(require_user),
):
    snapshot = build_paper_ops_briefing(limit=100, section=section or None)
    record = record_briefing_checkpoint(status=status, note=note, section=section or None, operator=user.get("username", "admin"), briefing_snapshot=snapshot)
    return {"ok": True, "record": record}


@app.post("/paper-ops-briefing/checkpoint")
async def paper_ops_briefing_checkpoint_page(
    status: str = Form(default="reviewed"),
    note: str = Form(default=""),
    section: str = Form(default=""),
    user: dict = Depends(require_user),
):
    snapshot = build_paper_ops_briefing(limit=100, section=section or None)
    record_briefing_checkpoint(status=status, note=note, section=section or None, operator=user.get("username", "admin"), briefing_snapshot=snapshot)
    suffix = f"?section={section}" if section else ""
    return RedirectResponse(url=f"/paper-ops-briefing{suffix}", status_code=303)


@app.get("/paper-ops-briefing", response_class=HTMLResponse)
async def paper_ops_briefing_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    section: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    report = build_paper_ops_briefing(limit=limit, section=section, status=status, market_id=market_id)
    return templates.TemplateResponse(
        "paper_ops_briefing_v047.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "checkpoints": report.get("recent_checkpoints", []),
            "guardrail": report.get("guardrail"),
            "generated_at": report.get("generated_at"),
            "limit": limit,
            "section": section or "",
            "status": status or "",
            "market_id": market_id or "",
        },
    )


@app.get("/api/paper/handoffs")
async def paper_handoffs_api(
    limit: int = Query(default=25, ge=1, le=1000),
    section: str | None = Query(default=None),
    item_status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    record_status: str | None = Query(default=None),
):
    return {
        "source": "local",
        **build_operator_handoff_board(limit=limit, section=section, item_status=item_status, market_id=market_id, handoff_status=record_status),
    }


@app.get("/api/paper/handoffs.csv", response_class=PlainTextResponse)
async def paper_handoffs_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    record_status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    rows = list_operator_handoffs(limit=limit, status=record_status, market_id=market_id)
    return PlainTextResponse(
        handoffs_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_operator_handoffs.csv"},
    )


@app.get("/api/paper/handoffs/reconciliation")
async def paper_handoff_reconciliation_api(
    limit: int = Query(default=25, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    return {
        "source": "local",
        **build_operator_handoff_reconciliation_board(limit=limit, status=status, market_id=market_id),
    }


@app.get("/api/paper/handoffs/reconciliation.csv", response_class=PlainTextResponse)
async def paper_handoff_reconciliation_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    report = build_operator_handoff_reconciliation_board(limit=limit, status=status, market_id=market_id)
    return PlainTextResponse(
        handoff_reconciliation_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_handoff_reconciliation.csv"},
    )


@app.get("/api/paper/handoffs/{handoff_id}/reconciliation")
async def paper_handoff_reconciliation_detail_api(handoff_id: str):
    report = reconcile_operator_handoff(handoff_id)
    if not report:
        raise HTTPException(status_code=404, detail="Paper operator handoff not found")
    return {"source": "local", **report}


@app.get("/api/paper/handoffs/{handoff_id}")
async def paper_handoff_detail_api(handoff_id: str):
    item = get_operator_handoff(handoff_id)
    if not item:
        raise HTTPException(status_code=404, detail="Paper operator handoff not found")
    return {"source": "local", "mode": "paper_operator_handoff_v048", "item": item}


@app.post("/api/paper/handoffs")
async def paper_handoff_record_api(
    status: str = Form(default="open"),
    incoming_operator: str = Form(default=""),
    note: str = Form(default=""),
    section: str = Form(default=""),
    item_status: str = Form(default=""),
    market_id: str = Form(default=""),
    user: dict = Depends(require_user),
):
    record = record_operator_handoff(
        status=status,
        outgoing_operator=user.get("username", "admin"),
        incoming_operator=incoming_operator,
        note=note,
        section=section or None,
        item_status=item_status or None,
        market_id=market_id or None,
    )
    return {"ok": True, "record": record}


@app.post("/paper-handoffs/record")
async def paper_handoff_record_page(
    status: str = Form(default="open"),
    incoming_operator: str = Form(default=""),
    note: str = Form(default=""),
    section: str = Form(default=""),
    item_status: str = Form(default=""),
    market_id: str = Form(default=""),
    user: dict = Depends(require_user),
):
    record_operator_handoff(
        status=status,
        outgoing_operator=user.get("username", "admin"),
        incoming_operator=incoming_operator,
        note=note,
        section=section or None,
        item_status=item_status or None,
        market_id=market_id or None,
    )
    params = {k: v for k, v in {"section": section, "item_status": item_status, "market_id": market_id}.items() if v}
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(url=f"/paper-handoffs{suffix}", status_code=303)


@app.get("/paper-handoffs", response_class=HTMLResponse)
async def paper_handoffs_page(
    request: Request,
    limit: int = Query(default=25, ge=1, le=1000),
    section: str | None = Query(default=None),
    item_status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    record_status: str | None = Query(default=None),
    handoff_id: str | None = Query(default=None),
):
    board = build_operator_handoff_board(limit=limit, section=section, item_status=item_status, market_id=market_id, handoff_status=record_status)
    detail = get_operator_handoff(handoff_id) if handoff_id else None
    return templates.TemplateResponse(
        "paper_handoffs_v048.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": board.get("summary", {}),
            "current": board.get("current", {}),
            "handoffs": board.get("items", []),
            "detail": detail,
            "guardrail": board.get("guardrail", ""),
            "generated_at": board.get("generated_at"),
            "limit": limit,
            "section": section or "",
            "item_status": item_status or "",
            "market_id": market_id or "",
            "record_status": record_status or "",
        },
    )


@app.get("/paper-handoff-reconciliation", response_class=HTMLResponse)
async def paper_handoff_reconciliation_page(
    request: Request,
    limit: int = Query(default=25, ge=1, le=1000),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    handoff_id: str | None = Query(default=None),
):
    board = build_operator_handoff_reconciliation_board(limit=limit, status=status, market_id=market_id)
    detail = reconcile_operator_handoff(handoff_id) if handoff_id else None
    return templates.TemplateResponse(
        "paper_handoff_reconciliation_v049.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "detail": detail,
            "guardrail": board.get("guardrail", ""),
            "generated_at": board.get("generated_at"),
            "limit": limit,
            "status": status or "",
            "market_id": market_id or "",
        },
    )


@app.get("/api/paper/ops-aging")
async def paper_ops_aging_api(
    limit: int = Query(default=100, ge=1, le=1000),
    section: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    min_age_hours: float | None = Query(default=None, ge=0),
):
    return build_paper_ops_aging(limit=limit, section=section, status=status, severity=severity, market_id=market_id, min_age_hours=min_age_hours)


@app.get("/api/paper/ops-aging.csv", response_class=PlainTextResponse)
async def paper_ops_aging_csv(
    limit: int = Query(default=1000, ge=1, le=10000),
    section: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    min_age_hours: float | None = Query(default=None, ge=0),
):
    report = build_paper_ops_aging(limit=limit, section=section, status=status, severity=severity, market_id=market_id, min_age_hours=min_age_hours)
    return PlainTextResponse(
        ops_aging_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_ops_aging.csv"},
    )


@app.get("/api/paper/ops-aging/{item_id:path}")
async def paper_ops_aging_detail_api(item_id: str):
    detail = build_ops_aging_detail(item_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Paper ops aging item not found")
    return detail


@app.get("/paper-ops-aging", response_class=HTMLResponse)
async def paper_ops_aging_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    section: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    min_age_hours: float | None = Query(default=None, ge=0),
    item_id: str | None = Query(default=None),
):
    report = build_paper_ops_aging(limit=limit, section=section, status=status, severity=severity, market_id=market_id, min_age_hours=min_age_hours)
    detail = build_ops_aging_detail(item_id) if item_id else None
    return templates.TemplateResponse(
        "paper_ops_aging_v050.html",
        {
            "request": request,
            "user": current_user(request),
            "generated_at": report.get("generated_at"),
            "guardrail": report.get("guardrail"),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "detail": detail,
            "thresholds": report.get("thresholds_hours", {}),
            "limit": limit,
            "section": section or "",
            "status": status or "",
            "severity": severity or "",
            "market_id": market_id or "",
            "min_age_hours": "" if min_age_hours is None else min_age_hours,
        },
    )




@app.get("/api/paper/ops-closeout")
async def paper_ops_closeout_api(
    limit: int = Query(default=100, ge=1, le=1000),
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    handoff_required: bool | None = Query(default=None),
):
    return {
        "source": "local",
        **build_paper_ops_closeout(limit=limit, source=source, status=status, market_id=market_id, handoff_required=handoff_required),
    }


@app.get("/api/paper/ops-closeout.csv", response_class=PlainTextResponse)
async def paper_ops_closeout_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    handoff_required: bool | None = Query(default=None),
):
    report = build_paper_ops_closeout(limit=limit, source=source, status=status, market_id=market_id, handoff_required=handoff_required)
    return PlainTextResponse(
        paper_ops_closeout_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_ops_closeout.csv"},
    )


@app.get("/paper-ops-closeout", response_class=HTMLResponse)
async def paper_ops_closeout_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    handoff_required: bool | None = Query(default=None),
):
    report = build_paper_ops_closeout(limit=limit, source=source, status=status, market_id=market_id, handoff_required=handoff_required)
    return templates.TemplateResponse(
        "paper_ops_closeout_v053.html",
        {
            "request": request,
            "user": current_user(request),
            "generated_at": report.get("generated_at"),
            "guardrail": report.get("guardrail"),
            "summary": report.get("summary", {}),
            "component_summaries": report.get("component_summaries", {}),
            "items": report.get("items", []),
            "limit": limit,
            "source": source or "",
            "status": status or "",
            "market_id": market_id or "",
            "handoff_required": "" if handoff_required is None else str(bool(handoff_required)).lower(),
        },
    )


@app.get("/api/paper/ops-closeout/signoffs")
async def paper_ops_closeout_signoffs_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    return {
        "source": "local",
        **build_ops_closeout_signoff_board(limit=limit, status=status, operator=operator, market_id=market_id),
    }


@app.get("/api/paper/ops-closeout/signoffs.csv", response_class=PlainTextResponse)
async def paper_ops_closeout_signoffs_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    rows = list_ops_closeout_signoffs(limit=limit, status=status, operator=operator, market_id=market_id)
    return PlainTextResponse(
        ops_closeout_signoffs_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_ops_closeout_signoffs.csv"},
    )


@app.get("/api/paper/ops-closeout/signoffs/{signoff_id}")
async def paper_ops_closeout_signoff_detail_api(signoff_id: str):
    record = get_ops_closeout_signoff(signoff_id)
    if not record:
        raise HTTPException(status_code=404, detail="Paper ops closeout signoff not found")
    return {"source": "local", "item": record}


@app.post("/api/paper/ops-closeout/signoffs")
async def paper_ops_closeout_signoff_create_api(
    status: str = Query(default=""),
    operator: str = Query(default="local"),
    note: str = Query(default=""),
    limit: int = Query(default=25, ge=1, le=1000),
    source: str | None = Query(default=None),
    item_status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    handoff_required: bool | None = Query(default=None),
):
    record = record_ops_closeout_signoff(status=status, operator=operator, note=note, limit=limit, source=source, item_status=item_status, market_id=market_id, handoff_required=handoff_required)
    return {"ok": True, "record": record}


@app.get("/paper-ops-closeout-signoffs", response_class=HTMLResponse)
async def paper_ops_closeout_signoffs_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    operator: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    board = build_ops_closeout_signoff_board(limit=limit, status=status, operator=operator, market_id=market_id)
    user = current_user(request)
    return templates.TemplateResponse(
        "paper_ops_closeout_signoffs_v054.html",
        {
            "request": request,
            "user": user,
            "generated_at": board.get("generated_at"),
            "guardrail": board.get("guardrail"),
            "summary": board.get("summary", {}),
            "items": board.get("items", []),
            "current_closeout_summary": board.get("current_closeout_summary", {}),
            "current_signoff_preview": board.get("current_signoff_preview", {}),
            "limit": limit,
            "status": status or "",
            "operator": operator or "",
            "market_id": market_id or "",
            "default_operator": (user or {}).get("username") or "local",
        },
    )


@app.post("/paper-ops-closeout-signoffs/record")
async def paper_ops_closeout_signoffs_record_page(
    request: Request,
    status: str = Form(default=""),
    operator: str = Form(default="local"),
    note: str = Form(default=""),
    limit: int = Form(default=25),
    market_id: str = Form(default=""),
):
    record = record_ops_closeout_signoff(status=status, operator=operator or "local", note=note, limit=limit, market_id=market_id or None)
    return RedirectResponse(url=f"/paper-ops-closeout-signoffs?status={record.get('status', '')}", status_code=303)


@app.get("/api/paper/ops-escalations")
async def paper_ops_escalations_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    include_candidates: bool = Query(default=True),
):
    return {
        "source": "local",
        **build_ops_escalation_board(limit=limit, status=status, severity=severity, market_id=market_id, owner=owner, include_candidates=include_candidates),
    }


@app.get("/api/paper/ops-escalations.csv", response_class=PlainTextResponse)
async def paper_ops_escalations_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    owner: str | None = Query(default=None),
):
    rows = list_ops_escalations(limit=limit, status=status, severity=severity, market_id=market_id, owner=owner)
    return PlainTextResponse(
        ops_escalations_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_ops_escalations.csv"},
    )


@app.get("/api/paper/ops-escalations/review")
async def paper_ops_escalation_review_api(
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    review_state: str | None = Query(default=None),
):
    return {
        "source": "local",
        **build_ops_escalation_review(limit=limit, status=status, severity=severity, market_id=market_id, owner=owner, review_state=review_state),
    }


@app.get("/api/paper/ops-escalations/review.csv", response_class=PlainTextResponse)
async def paper_ops_escalation_review_csv(
    limit: int = Query(default=10000, ge=1, le=10000),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    review_state: str | None = Query(default=None),
):
    report = build_ops_escalation_review(limit=limit, status=status, severity=severity, market_id=market_id, owner=owner, review_state=review_state)
    return PlainTextResponse(
        ops_escalation_review_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_ops_escalation_review.csv"},
    )


@app.get("/api/paper/ops-escalations/{escalation_id}/review")
async def paper_ops_escalation_review_detail_api(escalation_id: str):
    item = review_ops_escalation(escalation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Paper ops escalation review record not found")
    return {"source": "local", "mode": "paper_ops_escalation_review_detail_v052", "item": item}


@app.get("/paper-ops-escalation-review", response_class=HTMLResponse)
async def paper_ops_escalation_review_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    review_state: str | None = Query(default=None),
    escalation_id: str | None = Query(default=None),
):
    report = build_ops_escalation_review(limit=limit, status=status, severity=severity, market_id=market_id, owner=owner, review_state=review_state)
    detail = review_ops_escalation(escalation_id) if escalation_id else None
    return templates.TemplateResponse(
        "paper_ops_escalation_review_v052.html",
        {
            "request": request,
            "user": current_user(request),
            "generated_at": report.get("generated_at"),
            "guardrail": report.get("guardrail"),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "detail": detail,
            "limit": limit,
            "status": status or "",
            "severity": severity or "",
            "market_id": market_id or "",
            "owner": owner or "",
            "review_state": review_state or "",
        },
    )


@app.get("/api/paper/ops-escalations/{escalation_id}")
async def paper_ops_escalation_detail_api(escalation_id: str):
    item = get_ops_escalation(escalation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Paper ops escalation not found")
    return {"source": "local", "mode": "paper_ops_escalation_detail_v051", "item": item}


@app.post("/api/paper/ops-escalations")
async def paper_ops_escalation_create_api(
    aging_item_id: str = Form(...),
    status: str = Form(default="open"),
    severity: str = Form(default=""),
    owner: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_user),
):
    try:
        record = create_ops_escalation(
            aging_item_id=aging_item_id,
            status=status,
            severity=severity,
            owner=owner or user.get("username", "local"),
            note=note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "record": record}


@app.post("/api/paper/ops-escalations/{escalation_id}")
async def paper_ops_escalation_update_api(
    escalation_id: str,
    status: str = Form(default=""),
    severity: str = Form(default=""),
    owner: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_user),
):
    record = update_ops_escalation(
        escalation_id,
        status=status or None,
        severity=severity or None,
        owner=owner or user.get("username", "local"),
        note=note,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Paper ops escalation not found")
    return {"ok": True, "record": record}


@app.post("/paper-ops-escalations/create")
async def paper_ops_escalation_create_page(
    aging_item_id: str = Form(...),
    status: str = Form(default="open"),
    severity: str = Form(default=""),
    owner: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_user),
):
    try:
        record = create_ops_escalation(
            aging_item_id=aging_item_id,
            status=status,
            severity=severity,
            owner=owner or user.get("username", "local"),
            note=note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/paper-ops-escalations?escalation_id={record['escalation_id']}", status_code=303)


@app.post("/paper-ops-escalations/{escalation_id}/update")
async def paper_ops_escalation_update_page(
    escalation_id: str,
    status: str = Form(default=""),
    severity: str = Form(default=""),
    owner: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_user),
):
    record = update_ops_escalation(
        escalation_id,
        status=status or None,
        severity=severity or None,
        owner=owner or user.get("username", "local"),
        note=note,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Paper ops escalation not found")
    return RedirectResponse(url=f"/paper-ops-escalations?escalation_id={escalation_id}", status_code=303)


@app.get("/paper-ops-escalations", response_class=HTMLResponse)
async def paper_ops_escalations_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    escalation_id: str | None = Query(default=None),
):
    board = build_ops_escalation_board(limit=limit, status=status, severity=severity, market_id=market_id, owner=owner)
    detail = get_ops_escalation(escalation_id) if escalation_id else None
    return templates.TemplateResponse(
        "paper_ops_escalations_v051.html",
        {
            "request": request,
            "user": current_user(request),
            "generated_at": board.get("generated_at"),
            "guardrail": board.get("guardrail"),
            "summary": board.get("summary", {}),
            "candidate_summary": board.get("candidate_summary", {}),
            "items": board.get("items", []),
            "candidates": board.get("candidates", []),
            "detail": detail,
            "limit": limit,
            "status": status or "",
            "severity": severity or "",
            "market_id": market_id or "",
            "owner": owner or "",
        },
    )


@app.get("/api/paper/runbook")
async def paper_runbook_api(
    limit: int = Query(default=100, ge=1, le=1000),
    scope: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    item_id: str | None = Query(default=None),
    include_completed: bool = Query(default=False),
):
    return {
        "source": "local",
        "mode": "paper_operator_runbook_v046",
        **build_runbook(limit=limit, scope=scope, status=status, market_id=market_id, item_id=item_id, include_completed=include_completed),
    }


@app.get("/api/paper/runbook.csv", response_class=PlainTextResponse)
async def paper_runbook_csv(
    limit: int = Query(default=1000, ge=1, le=10000),
    scope: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    item_id: str | None = Query(default=None),
    include_completed: bool = Query(default=False),
):
    report = build_runbook(limit=limit, scope=scope, status=status, market_id=market_id, item_id=item_id, include_completed=include_completed)
    return PlainTextResponse(
        runbook_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_operator_runbook.csv"},
    )


@app.get("/api/paper/runbook/item/{item_id:path}")
async def paper_runbook_item_api(item_id: str, include_completed: bool = Query(default=True)):
    item = get_runbook_item(item_id, include_completed=include_completed)
    if not item:
        raise HTTPException(status_code=404, detail="Runbook item not found")
    return {"source": "local", "mode": "paper_operator_runbook_v046", "item": item}


@app.post("/api/paper/runbook/item/{item_id:path}/ack")
async def paper_runbook_ack_api(
    item_id: str,
    status: str = Query(default="done"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    item = get_runbook_item(item_id, include_completed=True)
    if not item:
        raise HTTPException(status_code=404, detail="Runbook item not found")
    record = record_runbook_acknowledgement(item_id, status=status, note=note, operator=user.get("username", "admin"), item_snapshot=item)
    return {"ok": True, "item": record}


@app.post("/runbook/ack")
async def paper_runbook_ack_page(
    item_id: str = Form(...),
    status: str = Form(default="done"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    item = get_runbook_item(item_id, include_completed=True)
    if item:
        record_runbook_acknowledgement(item_id, status=status, note=note, operator=user.get("username", "admin"), item_snapshot=item)
    return RedirectResponse(url=f"/runbook?item_id={item_id}", status_code=303)


@app.get("/runbook", response_class=HTMLResponse)
async def paper_runbook_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    scope: str | None = Query(default=None),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
    item_id: str | None = Query(default=None),
    include_completed: bool = Query(default=False),
):
    report = build_runbook(limit=limit, scope=scope, status=status, market_id=market_id, item_id=item_id, include_completed=include_completed)
    detail = get_runbook_item(item_id, include_completed=True) if item_id else None
    acks = list_runbook_acknowledgements(limit=20, item_id=item_id or None)
    return templates.TemplateResponse(
        "runbook_v046.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "guardrail": report.get("guardrail", ""),
            "acknowledgement_count": report.get("acknowledgement_count", 0),
            "acknowledgements": acks,
            "limit": limit,
            "scope": scope or "",
            "status": status or "",
            "market_id": market_id or "",
            "item_id": item_id or "",
            "include_completed": include_completed,
            "detail": detail,
        },
    )


@app.get("/api/risk/check/{market_id}")
async def risk_check_api(
    market_id: str,
    stake: float = Query(default=100.0, gt=0),
    outcome: str = Query(default="YES"),
):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = _score_market_rows([market])[0]
    price = float((scored.get("probability_model") or {}).get("market_probability") or 0.5)
    return check_paper_buy(scored, load_portfolio(), stake=stake, price=price, outcome=outcome)


@app.get("/api/strategy")
async def strategy_api():
    return explain_strategy()


@app.get("/api/strategy/recommendations")
async def strategy_recommendations_api(
    limit: int = Query(default=100, ge=1, le=500),
    min_edge: float = Query(default=0.02, ge=0.0, le=1.0),
    min_confidence_score: float = Query(default=35.0, ge=0.0, le=100.0),
    max_recommendations: int = Query(default=20, ge=1, le=100),
    stake: float = Query(default=100.0, gt=0),
):
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    return {
        "source": "local",
        "note": "Simulation-only recommendations. No orders are placed.",
        "items": recommend_paper_trades(
            markets,
            min_edge=min_edge,
            min_confidence_score=min_confidence_score,
            max_recommendations=max_recommendations,
            default_stake=stake,
        ),
    }


@app.get("/api/backtests")
async def backtests_api(limit: int = Query(default=20, ge=1, le=100)):
    return {"items": list_backtests(limit=limit)}


@app.post("/api/backtests/run")
async def run_backtest_api(user: dict = Depends(require_admin), 
    min_edge: float = Query(default=0.02, ge=0.0, le=1.0),
    min_confidence_score: float = Query(default=35.0, ge=0.0, le=100.0),
    stake: float = Query(default=100.0, gt=0),
    max_trades_per_snapshot: int = Query(default=5, ge=1, le=100),
):
    return run_snapshot_backtest(
        min_edge=min_edge,
        min_confidence_score=min_confidence_score,
        stake=stake,
        max_trades_per_snapshot=max_trades_per_snapshot,
        save=True,
    )

from .thesis_scoring import score_market_theses, score_all_market_theses
from .review_queue import build_review_queue, build_review_queue_payload, list_review_queue_actions, list_review_queue_audit, record_review_queue_action


async def _ranked_opportunities(limit: int = 50) -> list[dict]:
    """Build ranked, evidence-adjusted opportunities from live Gamma data.

    This keeps review/readiness/ticket workflows on the same data path as the
    visible opportunity engine instead of relying on older placeholder helpers.
    """
    markets = _score_market_rows(await client.list_markets(limit=limit, order="volume24hr"))
    markets = attach_evidence_probability(markets)
    return rank_opportunities(markets, watchlist=load_watchlist(), max_items=limit)


# --- v0.3.1 Thesis Scoring and Review Queue Routes ---

def _load_json_file_safe(path, default):
    try:
        from pathlib import Path
        import json
        p = Path(path)
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _data_path(*parts):
    from pathlib import Path
    return Path("data").joinpath(*parts)

@app.get("/api/thesis-scores")
async def api_thesis_scores():
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    market_ids = sorted({str(t.get("market_id", "")) for t in theses if t.get("market_id")})
    return {"items": score_all_market_theses(market_ids, theses)}

@app.get("/api/markets/{market_id}/thesis-score")
async def api_market_thesis_score(market_id: str):
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    return score_market_theses(market_id, theses).to_dict()

@app.get("/api/review-queue")
async def api_review_queue(limit: int = 25, demo: bool = Query(default=False)):
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    thesis_ids = sorted({str(t.get("market_id", "")) for t in theses if t.get("market_id")})
    thesis_score_items = score_all_market_theses(thesis_ids, theses)
    thesis_score_map = {str(item["market_id"]): item for item in thesis_score_items}
    if demo:
        opportunities = opportunity_demo_markets()
        source_state = "demo_fixture"
    else:
        try:
            opportunities = await _ranked_opportunities(limit=limit)
            source_state = "configured_local_or_network_source" if opportunities else "no_source_rows"
        except Exception:
            opportunities = []
            source_state = "source_unavailable"
    return build_review_queue_payload(
        opportunities,
        thesis_score_map,
        limit=limit,
        requested_demo=demo,
        source_state=source_state,
        source_route=f"/api/review-queue?demo={'true' if demo else 'false'}",
    )


@app.get("/api/review-queue/actions")
async def api_review_queue_actions(limit: int = Query(default=100, ge=1, le=500), market_id: str = Query(default="")):
    items = list_review_queue_actions(market_id=market_id or None, limit=limit)
    return {
        "version": APP_VERSION,
        "items": items,
        "count": len(items),
        "market_id": market_id or "",
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    }


@app.get("/api/review-queue/audit")
async def api_review_queue_audit():
    return {"items": list_review_queue_audit(), "review_only": True, "live_disabled": True, "order_submitted": False, "order_cancelled": False}


@app.post("/api/review-queue/{market_id}/action")
async def api_review_queue_action(market_id: str, payload: dict[str, Any] = Body(default_factory=dict)):
    action = str(payload.get("action") or "mark_reviewed")
    return record_review_queue_action(market_id, action, payload)


@app.get("/review-queue")
async def review_queue_page(
    request: Request,
    limit: int = 25,
    demo: bool = Query(default=False),
    rq_action: str = Query(default=""),
    action: str = Query(default=""),
    status: str = Query(default=""),
    market_id: str = Query(default=""),
):
    data = await api_review_queue(limit=limit, demo=demo)
    return templates.TemplateResponse(
        "review_queue_v031.html",
        {
            "request": request,
            "queue": data,
            "payload": data,
            "items": data["items"],
            "limit": limit,
            "demo_mode": demo,
            "feedback": {"rq_action": rq_action, "action": action, "status": status, "market_id": market_id},
        },
    )


@app.post("/review-queue/{market_id}/action")
async def review_queue_action_page(
    market_id: str,
    action: str = Form(default="mark_reviewed"),
    market_title: str = Form(default=""),
    previous_state: str = Form(default="UNREVIEWED"),
    reason: str = Form(default=""),
    operator_note: str = Form(default=""),
    queue_stage: str = Form(default=""),
    queue_action: str = Form(default=""),
    data_state: str = Form(default="cached"),
    data_freshness: str = Form(default="cached_runtime"),
    source_state: str = Form(default="configured_or_cached_source"),
    source_route: str = Form(default="/review-queue"),
    source_component: str = Form(default="review_queue.action_form"),
    return_to: str = Form(default="/review-queue"),
    user: dict = Depends(require_admin),
):
    result = record_review_queue_action(
        market_id,
        action,
        {
            "market_title": market_title,
            "previous_state": previous_state,
            "reason": reason,
            "operator_note": operator_note,
            "queue_stage": queue_stage,
            "queue_action": queue_action,
            "data_state": data_state,
            "data_freshness": data_freshness,
            "source_state": source_state,
            "source_route": source_route,
            "source_component": source_component,
            "requested_by": user.get("username", "local"),
        },
    )
    redirect_base = _safe_return_path(return_to, "/review-queue")
    separator = "&" if "?" in redirect_base else "?"
    suffix = urlencode({"rq_action": "recorded" if result.get("ok") else "error", "action": action, "status": result.get("item", {}).get("new_state", result.get("status", "error")), "market_id": market_id})
    return RedirectResponse(url=f"{redirect_base}{separator}{suffix}", status_code=303)

from .evidence_automation import create_evidence_packet as create_automated_evidence_packet, build_evidence_workbench, build_evidence_tasks_for_market


# --- v0.3.2 Evidence Automation Routes ---

async def _get_market_list_for_evidence(limit: int = 25):
    try:
        return await client.list_markets(limit=limit, order="volume24hr")
    except Exception:
        return []

@app.get("/api/evidence-workbench")
async def api_evidence_workbench(limit: int = 25):
    markets = await _get_market_list_for_evidence(limit=limit)
    return build_evidence_workbench(markets, limit=limit)

@app.get("/evidence-workbench")
async def evidence_workbench_page(request: Request, limit: int = 25):
    data = await api_evidence_workbench(limit=limit)
    return templates.TemplateResponse("evidence_workbench_v032.html", {"request": request, "items": data["items"], "generated_at": data["generated_at"], "limit": limit})

@app.post("/api/markets/{market_id}/evidence/auto-packet")
async def api_auto_evidence_packet(market_id: str):
    markets = await _get_market_list_for_evidence(limit=200)
    market = next((m for m in markets if str(m.get("id") or m.get("market_id") or m.get("conditionId") or m.get("slug")) == str(market_id)), None)
    if market is None:
        market = {"id": market_id, "title": market_id}
    packet = create_automated_evidence_packet(market, reason="Created from evidence automation route")
    return packet

@app.get("/api/markets/{market_id}/evidence-tasks")
async def api_market_evidence_tasks(market_id: str):
    markets = await _get_market_list_for_evidence(limit=200)
    market = next((m for m in markets if str(m.get("id") or m.get("market_id") or m.get("conditionId") or m.get("slug")) == str(market_id)), None)
    if market is None:
        market = {"id": market_id, "title": market_id}
    return {"items": build_evidence_tasks_for_market(market)}

from .readiness_engine import build_readiness_board, build_readiness_result


# --- v0.3.3 Paper Readiness Board ---

async def _get_opportunities_for_readiness(limit: int = 50):
    try:
        return await _ranked_opportunities(limit=limit)
    except Exception:
        return []

@app.get("/api/readiness-board")
async def api_readiness_board(limit: int = 50):
    opportunities = await _get_opportunities_for_readiness(limit=limit)
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    thesis_ids = [str(o.get("market_id") or o.get("id") or o.get("conditionId") or o.get("slug") or "") for o in opportunities]
    thesis_score_map = {str(item["market_id"]): item.get("score", 0.0) for item in score_all_market_theses(thesis_ids, theses)}
    return build_readiness_board(opportunities, thesis_scores=thesis_score_map, limit=limit)

@app.get("/readiness")
async def readiness_page(request: Request, limit: int = 50):
    data = await api_readiness_board(limit=limit)
    return templates.TemplateResponse("readiness_board_v033.html", {"request": request, "summary": data["summary"], "items": data["items"], "limit": limit})

@app.get("/api/markets/{market_id}/readiness")
async def api_market_readiness(market_id: str):
    opportunities = await _get_opportunities_for_readiness(limit=200)
    opportunity = next((o for o in opportunities if str(o.get("market_id") or o.get("id") or o.get("conditionId") or o.get("slug")) == str(market_id)), None)
    if opportunity is None:
        opportunity = {"id": market_id, "title": market_id}
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    thesis_score = score_market_theses(market_id, theses).score
    return build_readiness_result(opportunity, thesis_score=thesis_score)


# --- v0.4.1 Strategy Playbooks ---

def _market_id_from_row(row: dict) -> str:
    return str(row.get("market_id") or row.get("id") or row.get("conditionId") or row.get("slug") or "")


async def _get_opportunity_for_playbook(market_id: str) -> dict:
    opportunities = await _get_opportunities_for_readiness(limit=200)
    opportunity = next((o for o in opportunities if _market_id_from_row(o) == str(market_id)), None)
    if opportunity is not None:
        return opportunity
    try:
        market = await client.get_market(market_id)
    except Exception:
        market = None
    if market:
        scored = attach_evidence_probability(_score_market_rows([market]))
        rows = rank_opportunities(scored, watchlist=load_watchlist(), max_items=1)
        return rows[0] if rows else scored[0]
    return {"id": market_id, "market_id": market_id, "title": market_id, "question": market_id}


def _review_map_for_playbooks() -> dict[str, dict]:
    report = build_review_report(limit=10000)
    return {str(row.get("market_id")): row for row in report.get("items", []) if row.get("market_id")}


@app.get("/api/playbooks")
async def api_playbooks(active_only: bool = Query(default=False)):
    rows = list_playbooks(active_only=active_only)
    return {"source": "local", "mode": "strategy_playbooks_v040", "summary": summarize_playbooks(rows), "items": rows}


@app.get("/api/playbooks/board")
async def api_playbook_board(
    limit: int = Query(default=50, ge=1, le=200),
    playbook_id: str | None = Query(default=None),
):
    opportunities = await _get_opportunities_for_readiness(limit=limit)
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    thesis_ids = [_market_id_from_row(o) for o in opportunities]
    thesis_score_map = {str(item["market_id"]): item.get("score", 0.0) for item in score_all_market_theses(thesis_ids, theses)}
    readiness_by_market = {
        _market_id_from_row(o): build_readiness_result(o, thesis_score=thesis_score_map.get(_market_id_from_row(o), 0.0))
        for o in opportunities
    }
    return {
        "source": "local",
        "mode": "strategy_playbook_board_v040",
        **build_playbook_board(
            opportunities,
            readiness_by_market=readiness_by_market,
            review_by_market=_review_map_for_playbooks(),
            playbook_id=playbook_id,
            limit=limit,
        ),
    }


@app.get("/api/playbook-decisions")
async def api_playbook_decisions(
    limit: int = Query(default=100, ge=1, le=1000),
    market_id: str | None = Query(default=None),
    playbook_id: str | None = Query(default=None),
):
    rows = list_playbook_decisions(limit=limit, market_id=market_id, playbook_id=playbook_id)
    return {"source": "local", "mode": "strategy_playbook_decisions_v040", "summary": summarize_playbook_decisions(rows), "items": rows}


@app.get("/api/playbooks/{playbook_id}")
async def api_playbook_detail(playbook_id: str):
    playbook = get_playbook(playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return {"source": "local", "mode": "strategy_playbook_v040", "item": playbook}


@app.get("/api/markets/{market_id}/playbook-fit")
async def api_market_playbook_fit(market_id: str, playbook_id: str | None = Query(default=None)):
    opportunity = await _get_opportunity_for_playbook(market_id)
    readiness = await api_market_readiness(market_id)
    review = build_market_review(market_id).get("item") or {}
    return {"source": "local", "mode": "market_playbook_fit_v040", **evaluate_market_playbooks(opportunity, readiness=readiness, review=review, playbook_id=playbook_id)}


@app.post("/api/markets/{market_id}/playbook-decision")
async def api_create_playbook_decision(
    market_id: str,
    playbook_id: str = Query(...),
    status: str = Query(default="assigned"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    fit = await api_market_playbook_fit(market_id, playbook_id=playbook_id)
    try:
        decision = create_playbook_decision(
            market_id,
            playbook_id,
            status=status,
            note=note,
            created_by=user.get("username", "admin"),
            fit_snapshot=fit.get("best_fit") or {},
        )
        return {"ok": True, "item": decision}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/markets/{market_id}/playbook-decision")
async def create_playbook_decision_page(
    market_id: str,
    playbook_id: str = Form(...),
    status: str = Form(default="assigned"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    try:
        fit = await api_market_playbook_fit(market_id, playbook_id=playbook_id)
        create_playbook_decision(
            market_id,
            playbook_id,
            status=status,
            note=note,
            created_by=user.get("username", "admin"),
            fit_snapshot=fit.get("best_fit") or {},
        )
    except Exception:
        pass
    return RedirectResponse(url=f"/playbooks?market_id={market_id}", status_code=303)


@app.post("/playbooks/custom")
async def create_custom_playbook_page(
    name: str = Form(...),
    playbook_id: str = Form(default=""),
    min_edge_percent: str = Form(default=""),
    min_confidence_percent: str = Form(default=""),
    min_evidence_percent: str = Form(default=""),
    min_thesis_percent: str = Form(default=""),
    action: str = Form(default="manual_review"),
    user: dict = Depends(require_admin),
):
    def pct(value: str) -> float | None:
        if not str(value).strip():
            return None
        return max(0.0, min(1.0, float(value) / 100.0))

    gates = {}
    values = {
        "min_edge": pct(min_edge_percent),
        "min_confidence": pct(min_confidence_percent),
        "min_evidence_score": pct(min_evidence_percent),
        "min_thesis_score": pct(min_thesis_percent),
    }
    gates.update({k: v for k, v in values.items() if v is not None})
    payload = {
        "playbook_id": playbook_id.strip() or "custom_" + name.lower().replace(" ", "_")[:40],
        "version": "0.4.2-custom",
        "name": name,
        "status": "active",
        "intended_use": "Custom local paper-workflow playbook created from the UI.",
        "recommended_action": action,
        "gates": gates,
        "sizing": {"default_stake": 0.0, "max_stake": 0.0},
        "checklist": ["Human review required before any simulated entry."],
        "guardrail": "Custom local paper-only playbook. No live execution.",
        "created_by": user.get("username", "admin"),
    }
    try:
        upsert_playbook(payload)
    except Exception:
        pass
    return RedirectResponse(url="/playbooks", status_code=303)


@app.get("/playbooks", response_class=HTMLResponse)
async def playbooks_page(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    playbook_id: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    board = await api_playbook_board(limit=limit, playbook_id=playbook_id)
    decisions = await api_playbook_decisions(limit=25, market_id=market_id, playbook_id=playbook_id)
    market_fit = await api_market_playbook_fit(market_id, playbook_id=playbook_id) if market_id else None
    return templates.TemplateResponse(
        "playbooks_v040.html",
        {
            "request": request,
            "user": current_user(request),
            "limit": limit,
            "playbook_id": playbook_id or "",
            "market_id": market_id or "",
            "summary": board["summary"],
            "items": board["items"],
            "playbooks": list_playbooks(),
            "decisions": decisions["items"],
            "decision_summary": decisions["summary"],
            "market_fit": market_fit,
            "guardrail": board.get("guardrail"),
        },
    )


# --- v0.4.1 Playbook Performance Review ---

@app.get("/api/playbook-performance")
async def api_playbook_performance(
    limit: int = Query(default=100, ge=1, le=1000),
    playbook_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    return {"source": "local", "mode": "playbook_performance_v041", **build_playbook_performance(limit=limit, playbook_id=playbook_id, status=status)}


@app.get("/api/playbook-performance.csv", response_class=PlainTextResponse)
async def api_playbook_performance_csv(
    limit: int = Query(default=1000, ge=1, le=10000),
    playbook_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    report = build_playbook_performance(limit=limit, playbook_id=playbook_id, status=status)
    return PlainTextResponse(
        playbook_performance_to_csv(report.get("items", [])),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=playbook_performance.csv"},
    )


@app.get("/api/playbook-performance/{playbook_id}")
async def api_playbook_performance_detail(playbook_id: str):
    return {"source": "local", "mode": "playbook_performance_detail_v041", **build_playbook_performance_detail(playbook_id)}


@app.get("/playbook-performance", response_class=HTMLResponse)
async def playbook_performance_page(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    playbook_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    report = build_playbook_performance(limit=limit, playbook_id=playbook_id, status=status)
    detail = build_playbook_performance_detail(playbook_id) if playbook_id else None
    return templates.TemplateResponse(
        "playbook_performance_v041.html",
        {
            "request": request,
            "user": current_user(request),
            "summary": report.get("summary", {}),
            "items": report.get("items", []),
            "playbooks": list_playbooks(),
            "limit": limit,
            "playbook_id": playbook_id or "",
            "status": status or "",
            "detail": detail,
            "guardrail": report.get("guardrail", ""),
        },
    )

from .trade_tickets import (
    create_trade_ticket,
    delete_trade_ticket,
    get_trade_ticket,
    list_trade_tickets,
    summarize_trade_tickets,
    update_trade_ticket,
)


# --- v0.3.4 Paper Trade Tickets ---

async def _get_opportunity_for_ticket(market_id: str) -> dict:
    opportunities = await _get_opportunities_for_readiness(limit=200)
    opportunity = next((o for o in opportunities if str(o.get("market_id") or o.get("id") or o.get("conditionId") or o.get("slug")) == str(market_id)), None)
    if opportunity is not None:
        return opportunity
    market = await client.get_market(market_id)
    if market:
        scored = attach_evidence_probability(_score_market_rows([market]))
        rows = rank_opportunities(scored, watchlist=load_watchlist(), max_items=1)
        return rows[0] if rows else scored[0]
    return {"id": market_id, "market_id": market_id, "title": market_id, "question": market_id}


def _parse_optional_stake(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid stake") from exc


@app.get("/api/trade-tickets")
async def api_trade_tickets(limit: int = Query(default=100, ge=1, le=500), status: str | None = Query(default=None)):
    rows = list_trade_tickets(limit=limit, status=status)
    return {"source": "local", "mode": "paper_trade_tickets", "summary": summarize_trade_tickets(rows), "items": rows}


@app.get("/trade-tickets", response_class=HTMLResponse)
async def trade_tickets_page(request: Request, limit: int = Query(default=100, ge=1, le=500), status: str | None = Query(default=None)):
    data = await api_trade_tickets(limit=limit, status=status)
    return templates.TemplateResponse("trade_tickets_v034.html", {"request": request, "summary": data["summary"], "items": data["items"], "limit": limit, "status": status or ""})


@app.get("/api/trade-tickets/{ticket_id}")
async def api_trade_ticket_detail(ticket_id: str):
    ticket = get_trade_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Trade ticket not found")
    return {"source": "local", "mode": "paper_trade_ticket", "item": ticket}


@app.post("/api/markets/{market_id}/trade-ticket")
async def api_create_trade_ticket(
    market_id: str,
    stake: float | None = Query(default=None, gt=0),
    outcome: str = Query(default="YES"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    opportunity = await _get_opportunity_for_ticket(market_id)
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    readiness = build_readiness_result(opportunity, thesis_score=score_market_theses(market_id, theses).score)
    ticket = create_trade_ticket(opportunity, readiness, stake=stake, outcome=outcome, created_by=user.get("username", "admin"), operator_note=note)
    return {"ok": True, "item": ticket}


@app.post("/markets/{market_id}/trade-ticket")
async def create_trade_ticket_page(
    market_id: str,
    stake: str = Form(default=""),
    outcome: str = Form(default="YES"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    opportunity = await _get_opportunity_for_ticket(market_id)
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    readiness = build_readiness_result(opportunity, thesis_score=score_market_theses(market_id, theses).score)
    create_trade_ticket(opportunity, readiness, stake=_parse_optional_stake(stake), outcome=outcome, created_by=user.get("username", "admin"), operator_note=note)
    return RedirectResponse(url="/trade-tickets", status_code=303)


@app.post("/api/trade-tickets/{ticket_id}/status")
async def api_update_trade_ticket_status(
    ticket_id: str,
    status: str = Query(...),
    note: str = Query(default=""),
    decision: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    try:
        ticket = update_trade_ticket(ticket_id, status=status, operator_note=note, operator_decision=decision or status)
        return {"ok": True, "item": ticket}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/trade-tickets/{ticket_id}/status")
async def update_trade_ticket_status_page(
    ticket_id: str,
    status: str = Form(...),
    note: str = Form(default=""),
    decision: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    try:
        update_trade_ticket(ticket_id, status=status, operator_note=note, operator_decision=decision or status)
    except ValueError:
        pass
    return RedirectResponse(url="/trade-tickets", status_code=303)


@app.post("/api/trade-tickets/{ticket_id}/paper-buy")
async def api_trade_ticket_paper_buy(ticket_id: str, user: dict = Depends(require_admin)):
    ticket = get_trade_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Trade ticket not found")
    preflight = build_ticket_preflight(ticket)
    gate = ticket_execution_gate(ticket, preflight=preflight)
    if not gate.get("paper_buy_executable"):
        blockers = "; ".join(str(row.get("detail") or row.get("name")) for row in preflight.get("blockers", [])[:5])
        reason = gate.get("reason_summary") or blockers or "Ticket is not approved in the paper execution queue."
        approval = record_execution_decision(
            ticket,
            preflight=preflight,
            status="blocked",
            operator=user.get("username", "admin"),
            source="execution_attempt",
            reason=f"Execution gate blocked simulated paper buy: {reason}",
        )
        raise HTTPException(status_code=400, detail=f"Paper execution gate blocked ticket: {reason}; approval_record={approval.get('approval_id')}")
    try:
        result = paper_buy(
            ticket.get("market_snapshot") or {"id": ticket.get("market_id"), "question": ticket.get("title")},
            outcome=ticket.get("outcome", "YES"),
            price=float(ticket.get("price") or 0.5),
            stake=float(ticket.get("stake") or 0.0),
            reason=f"paper trade ticket {ticket_id}",
        )
        trade_id = result.get("trade", {}).get("id")
        approval = record_execution_decision(
            ticket,
            preflight=preflight,
            status="executed",
            operator=user.get("username", "admin"),
            source="execution_attempt",
            paper_trade_id=trade_id,
            reason="Simulated paper buy executed from approved ticket preflight and execution-queue approval gate.",
        )
        updated = update_trade_ticket(ticket_id, status="paper_executed", operator_decision=f"paper_executed:{approval.get('approval_id')}", paper_trade_id=trade_id)
        return {"ok": True, "ticket": updated, "paper_result": result, "preflight": preflight, "execution_gate": gate, "approval": approval}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/trade-tickets/{ticket_id}/paper-buy")
async def trade_ticket_paper_buy_page(ticket_id: str, user: dict = Depends(require_admin)):
    try:
        await api_trade_ticket_paper_buy(ticket_id, user=user)
    except HTTPException:
        pass
    return RedirectResponse(url="/trade-tickets", status_code=303)


@app.delete("/api/trade-tickets/{ticket_id}")
async def api_delete_trade_ticket(ticket_id: str, user: dict = Depends(require_admin)):
    return {"ok": delete_trade_ticket(ticket_id)}


# --- v0.3.7 Paper Exit Tickets ---


def _parse_optional_float_form(value: str | None, field_name: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}") from exc


async def _market_or_none(market_id: str) -> dict | None:
    try:
        return await client.get_market(market_id)
    except Exception:
        return None


@app.get("/api/exit-tickets")
async def api_exit_tickets(
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    market_id: str | None = Query(default=None),
):
    rows = list_exit_tickets(limit=limit, status=status, market_id=market_id)
    return {"source": "local", "mode": "paper_exit_tickets_v037", "summary": summarize_exit_tickets(rows), "items": rows}


@app.get("/exit-tickets", response_class=HTMLResponse)
async def exit_tickets_page(request: Request, limit: int = Query(default=100, ge=1, le=500), status: str | None = Query(default=None)):
    data = await api_exit_tickets(limit=limit, status=status)
    return templates.TemplateResponse(
        "exit_tickets_v037.html",
        {"request": request, "summary": data["summary"], "items": data["items"], "limit": limit, "status": status or ""},
    )


@app.get("/api/exit-tickets/{ticket_id}")
async def api_exit_ticket_detail(ticket_id: str):
    ticket = get_exit_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Exit ticket not found")
    return {"source": "local", "mode": "paper_exit_ticket_v037", "item": ticket}


@app.post("/api/paper/positions/{market_id}/exit-ticket")
async def api_create_exit_ticket(
    market_id: str,
    outcome: str = Query(default="YES"),
    shares: float | None = Query(default=None),
    price: float | None = Query(default=None),
    reason: str = Query(default="manual paper exit review"),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    market = await _market_or_none(market_id)
    ticket = create_exit_ticket(
        market_id,
        outcome=outcome,
        market=market,
        shares=shares,
        price=price,
        reason=reason,
        created_by=user.get("username", "admin"),
        operator_note=note,
    )
    return {"ok": True, "item": ticket}


@app.post("/paper/positions/exit-ticket")
async def create_exit_ticket_page(
    market_id: str = Form(...),
    outcome: str = Form(default="YES"),
    shares: str = Form(default=""),
    price: str = Form(default=""),
    reason: str = Form(default="manual paper exit review"),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    market = await _market_or_none(market_id)
    create_exit_ticket(
        market_id,
        outcome=outcome,
        market=market,
        shares=_parse_optional_float_form(shares, "shares"),
        price=_parse_optional_float_form(price, "price"),
        reason=reason,
        created_by=user.get("username", "admin"),
        operator_note=note,
    )
    return RedirectResponse(url="/exit-tickets", status_code=303)


@app.post("/api/exit-tickets/{ticket_id}/status")
async def api_update_exit_ticket_status(
    ticket_id: str,
    status: str = Query(default="draft_review"),
    decision: str = Query(default=""),
    note: str = Query(default=""),
    user: dict = Depends(require_admin),
):
    try:
        ticket = update_exit_ticket(ticket_id, status=status, operator_note=note, operator_decision=decision or status)
        return {"ok": True, "item": ticket}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/exit-tickets/{ticket_id}/status")
async def update_exit_ticket_status_page(
    ticket_id: str,
    status: str = Form(default="draft_review"),
    decision: str = Form(default=""),
    note: str = Form(default=""),
    user: dict = Depends(require_admin),
):
    try:
        update_exit_ticket(ticket_id, status=status, operator_note=note, operator_decision=decision or status)
    except ValueError:
        pass
    return RedirectResponse(url="/exit-tickets", status_code=303)


@app.post("/api/exit-tickets/{ticket_id}/paper-sell")
async def api_exit_ticket_paper_sell(ticket_id: str, user: dict = Depends(require_admin)):
    ticket = get_exit_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Exit ticket not found")
    if not ticket.get("execution_allowed"):
        raise HTTPException(status_code=400, detail="Ticket is not paper-execution-ready. Resolve blockers first.")
    if ticket.get("status") == "paper_executed":
        raise HTTPException(status_code=400, detail="Ticket has already been paper executed.")
    try:
        market = await _market_or_none(str(ticket.get("market_id")))
        snapshot = market or executable_exit_snapshot(ticket)
        result = paper_sell(
            snapshot,
            outcome=ticket.get("outcome", "YES"),
            price=float(ticket.get("price") or 0.5),
            shares=float(ticket.get("shares") or 0.0),
            reason=f"paper exit ticket {ticket_id}: {ticket.get('exit_reason') or 'operator reviewed exit'}",
        )
        updated = update_exit_ticket(
            ticket_id,
            status="paper_executed",
            operator_decision="paper_executed",
            paper_trade_id=result.get("trade", {}).get("id"),
            execution_result=result,
        )
        return {"ok": True, "ticket": updated, "paper_result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/exit-tickets/{ticket_id}/paper-sell")
async def exit_ticket_paper_sell_page(ticket_id: str, user: dict = Depends(require_admin)):
    try:
        await api_exit_ticket_paper_sell(ticket_id, user=user)
    except HTTPException:
        pass
    return RedirectResponse(url="/exit-tickets", status_code=303)


@app.delete("/api/exit-tickets/{ticket_id}")
async def api_delete_exit_ticket(ticket_id: str, user: dict = Depends(require_admin)):
    return {"ok": delete_exit_ticket(ticket_id)}

# v1.2.0 Training & Evaluation Lab routes. Offline-only: these never submit/cancel or touch live trading.
def _training_template_context(request: Request, user: dict, page: str = "overview") -> dict:
    return {
        "request": request,
        "user": user,
        "page": page,
        "status": build_training_status(),
        "datasets": list_training_datasets(limit=200),
        "feature_sets": list_feature_sets(limit=200),
        "training_runs": list_training_runs(limit=200),
        "models": list_training_models(limit=200),
        "backtests": list_training_backtests(limit=200),
        "host_jobs": list_host_training_jobs(limit=200),
        "internet_status": build_internet_data_status(),
        "audit_events": list_training_audit(limit=50),
        "guardrail": "TRAINING ONLY · NO LIVE TRADING · MODEL OUTPUTS REQUIRE OPERATOR REVIEW",
    }


@app.get("/training", response_class=HTMLResponse)
async def training_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("training_lab_v120.html", _training_template_context(request, user, "overview"))


@app.get("/training/datasets", response_class=HTMLResponse)
async def training_datasets_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("training_lab_v120.html", _training_template_context(request, user, "datasets"))


@app.get("/training/features", response_class=HTMLResponse)
async def training_features_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("training_lab_v120.html", _training_template_context(request, user, "features"))


@app.get("/training/runs", response_class=HTMLResponse)
async def training_runs_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("training_lab_v120.html", _training_template_context(request, user, "runs"))


@app.get("/training/models", response_class=HTMLResponse)
async def training_models_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("training_lab_v120.html", _training_template_context(request, user, "models"))


@app.get("/training/backtests", response_class=HTMLResponse)
async def training_backtests_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("training_lab_v120.html", _training_template_context(request, user, "backtests"))


@app.get("/training/signals", response_class=HTMLResponse)
async def training_signals_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("training_lab_v120.html", _training_template_context(request, user, "signals"))


@app.get("/training/host-jobs", response_class=HTMLResponse)
async def training_host_jobs_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("training_lab_v120.html", _training_template_context(request, user, "host_jobs"))


@app.get("/api/training/status")
async def training_status_api(user: dict = Depends(require_admin)):
    return build_training_status()


@app.get("/api/training/datasets")
async def training_datasets_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_training_datasets(limit=1000), "status": build_training_status()}


@app.get("/api/training/datasets.csv", response_class=PlainTextResponse)
async def training_datasets_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(datasets_to_csv(list_training_datasets(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_datasets.csv"})


@app.get("/api/training/datasets/{dataset_id}")
async def training_dataset_detail_api(dataset_id: str, user: dict = Depends(require_admin)):
    item = get_dataset(dataset_id)
    if not item:
        raise HTTPException(status_code=404, detail="Training dataset not found")
    return {"source": "local", "item": item}


@app.post("/api/training/datasets/register")
async def training_dataset_register_api(name: str = Form(default=""), dataset_type: str = Form(default="custom_csv"), dataset_path: str = Form(default=""), source: str = Form(default="local_file"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": register_dataset(name=name, dataset_type=dataset_type, source_path=dataset_path, source=source, notes=note)}


@app.post("/api/training/datasets/validate")
async def training_dataset_validate_api(name: str = Form(default=""), dataset_type: str = Form(default="custom_csv"), dataset_path: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": validate_dataset_payload(name=name, dataset_type=dataset_type, source_path=dataset_path)}


@app.get("/api/training/features")
async def training_features_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_feature_sets(limit=1000)}


@app.get("/api/training/features.csv", response_class=PlainTextResponse)
async def training_features_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(feature_sets_to_csv(list_feature_sets(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_feature_sets.csv"})


@app.post("/api/training/features/build-preview")
async def training_features_preview_api(dataset_id: str = Form(default=""), name: str = Form(default=""), feature_groups: str = Form(default="market_metadata,spread_liquidity,execution_quality"), target: str = Form(default=""), lookback_window: str = Form(default=""), prediction_horizon: str = Form(default=""), user: dict = Depends(require_admin)):
    groups = [item.strip() for item in feature_groups.split(",") if item.strip()]
    return {"ok": True, "recorded": False, "item": build_feature_set_preview(dataset_id=dataset_id, name=name, feature_groups=groups, target_column=target, lookback_window=lookback_window, prediction_horizon=prediction_horizon)}


@app.post("/api/training/features/register")
async def training_features_register_api(dataset_id: str = Form(default=""), name: str = Form(default=""), feature_groups: str = Form(default="market_metadata,spread_liquidity,execution_quality"), target: str = Form(default=""), lookback_window: str = Form(default=""), prediction_horizon: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    groups = [item.strip() for item in feature_groups.split(",") if item.strip()]
    return {"ok": True, "item": register_feature_set(dataset_id=dataset_id, name=name, feature_groups=groups, target_column=target, lookback_window=lookback_window, prediction_horizon=prediction_horizon, notes=note)}


@app.get("/api/training/runs")
async def training_runs_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_training_runs(limit=1000)}


@app.get("/api/training/runs.csv", response_class=PlainTextResponse)
async def training_runs_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(training_runs_to_csv(list_training_runs(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_runs.csv"})


@app.post("/api/training/runs/preview")
async def training_run_preview_api(dataset_id: str = Form(default=""), feature_set_id: str = Form(default=""), model_type: str = Form(default="heuristic_baseline"), target: str = Form(default=""), name: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_training_run(dataset_id=dataset_id, feature_set_id=feature_set_id, model_type=model_type, target=target, name=name)}


@app.post("/api/training/runs/start")
async def training_run_start_api(dataset_id: str = Form(default=""), feature_set_id: str = Form(default=""), model_type: str = Form(default="heuristic_baseline"), target: str = Form(default=""), name: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": start_training_run(dataset_id=dataset_id, feature_set_id=feature_set_id, model_type=model_type, target=target, name=name, notes=note)}


@app.get("/api/training/models")
async def training_models_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_training_models(limit=1000)}


@app.get("/api/training/models.csv", response_class=PlainTextResponse)
async def training_models_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(models_to_csv(list_training_models(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_models.csv"})


@app.post("/api/training/models/register")
async def training_model_register_api(name: str = Form(default=""), training_run_id: str = Form(default=""), strategy_id: str = Form(default="training_baseline"), model_type: str = Form(default="heuristic_baseline"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": register_model(name=name, training_run_id=training_run_id, strategy_id=strategy_id, model_type=model_type, notes=note)}


@app.get("/api/training/backtests")
async def training_backtests_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_training_backtests(limit=1000)}


@app.get("/api/training/backtests.csv", response_class=PlainTextResponse)
async def training_backtests_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(backtests_to_csv(list_training_backtests(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_backtests.csv"})


@app.post("/api/training/backtests/preview")
async def training_backtest_preview_api(training_run_id: str = Form(default=""), dataset_id: str = Form(default=""), feature_set_id: str = Form(default=""), strategy_id: str = Form(default="training_baseline"), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_backtest(training_run_id=training_run_id, dataset_id=dataset_id, feature_set_id=feature_set_id, strategy_id=strategy_id)}


@app.post("/api/training/backtests/run")
async def training_backtest_run_api(training_run_id: str = Form(default=""), dataset_id: str = Form(default=""), feature_set_id: str = Form(default=""), strategy_id: str = Form(default="training_baseline"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": run_backtest(training_run_id=training_run_id, dataset_id=dataset_id, feature_set_id=feature_set_id, strategy_id=strategy_id, notes=note)}


@app.post("/api/training/signals/generate-preview")
async def training_signals_preview_api(model_id: str = Form(default=""), backtest_id: str = Form(default=""), strategy_id: str = Form(default="training_baseline"), market_id: str = Form(default=""), token_id: str = Form(default=""), side: str = Form(default="BUY"), price: float = Form(default=0.5), size: float = Form(default=1.0), confidence: float = Form(default=0.55), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, **preview_training_signals(model_id=model_id, backtest_id=backtest_id, strategy_id=strategy_id, market_id=market_id, token_id=token_id, side=side, limit_price=price, size=size, confidence=confidence)}


@app.post("/api/training/signals/queue-for-review")
async def training_signals_queue_api(model_id: str = Form(default=""), backtest_id: str = Form(default=""), strategy_id: str = Form(default="training_baseline"), market_id: str = Form(default=""), token_id: str = Form(default=""), side: str = Form(default="BUY"), price: float = Form(default=0.5), size: float = Form(default=1.0), confidence: float = Form(default=0.55), user: dict = Depends(require_admin)):
    return {"ok": True, **queue_training_signals(model_id=model_id, backtest_id=backtest_id, strategy_id=strategy_id, market_id=market_id, token_id=token_id, side=side, limit_price=price, size=size, confidence=confidence)}

# v1.3.0 Data Ingestion + Dataset Builder routes. Local-first; no endpoint trades.
def _split_csv(text: str) -> list[str]:
    return [item.strip() for item in (text or "").split(",") if item.strip()]


def _data_template_context(request: Request, user: dict, page: str = "overview") -> dict:
    return {
        "request": request,
        "user": user,
        "page": page,
        "status": build_data_status(),
        "internet_status": build_internet_data_status(),
        "internet_workflow": build_internet_workflow() if page == "internet_workflow" else {},
        "sources": list_data_sources(limit=200),
        "ingestion_jobs": list_ingestion_jobs(limit=200),
        "snapshots": list_raw_snapshots(limit=200),
        "normalized_records": list_normalized_records(limit=200),
        "labels": list_labels(limit=200),
        "dataset_builder_status": build_dataset_builder_status(),
        "dataset_builds": list_dataset_builds(limit=200),
        "internet_sources": list_internet_sources(limit=200),
        "internet_ingestion_jobs": list_internet_ingestion_jobs(limit=200),
        "internet_schedules": list_internet_schedules(limit=200),
        "scoped_status": build_scoped_status(),
        "data_scopes": list_data_scopes(limit=200),
        "backfills": list_backfills(limit=200),
        "category_datasets": list_category_datasets(limit=200),
        "audit_events": list_data_audit(limit=50),
        "guardrail": "DATA INGESTION · NETWORK DISABLED BY DEFAULT · LOCAL FIRST · NO LIVE TRADING · TRAINING DATA ONLY",
    }


@app.get("/data", response_class=HTMLResponse)
async def data_overview_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "overview"))


@app.get("/data/sources", response_class=HTMLResponse)
async def data_sources_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "sources"))


@app.get("/data/ingestion", response_class=HTMLResponse)
async def data_ingestion_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "ingestion"))


@app.get("/data/snapshots", response_class=HTMLResponse)
async def data_snapshots_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "snapshots"))


@app.get("/data/normalized", response_class=HTMLResponse)
async def data_normalized_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "normalized"))


@app.get("/data/labels", response_class=HTMLResponse)
async def data_labels_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "labels"))


@app.get("/data/internet-sources", response_class=HTMLResponse)
async def data_internet_sources_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "internet_sources"))


@app.get("/data/internet-ingestion", response_class=HTMLResponse)
async def data_internet_ingestion_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "internet_ingestion"))


@app.get("/data/internet-workflow", response_class=HTMLResponse)
async def data_internet_workflow_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "internet_workflow"))


@app.get("/data/scopes", response_class=HTMLResponse)
async def data_scopes_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "scopes"))


@app.get("/data/backfills", response_class=HTMLResponse)
async def data_backfills_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "backfills"))


@app.get("/training/category-datasets", response_class=HTMLResponse)
async def training_category_datasets_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "category_datasets"))


@app.get("/training/dataset-builder", response_class=HTMLResponse)
async def training_dataset_builder_page(request: Request, user: dict = Depends(require_admin)):
    return templates.TemplateResponse("data_lab_v130.html", _data_template_context(request, user, "dataset_builder"))


@app.get("/api/data/scopes")
async def data_scopes_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_data_scopes(limit=1000), "status": build_scoped_status()}


@app.post("/api/data/scopes/register")
async def data_scope_register_api(name: str = Form(default=""), scope_type: str = Form(default="category"), category: str = Form(default=""), keywords: str = Form(default=""), market_ids: str = Form(default=""), condition_ids: str = Form(default=""), event_slugs: str = Form(default=""), market_slugs: str = Form(default=""), date_start: str = Form(default=""), date_end: str = Form(default=""), resolved_only: bool = Form(default=False), active_only: bool = Form(default=False), min_volume: float = Form(default=0), min_liquidity: float = Form(default=0), max_markets: int = Form(default=1000), max_records: int = Form(default=100000), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": register_data_scope(name=name, scope_type=scope_type, category=category, keywords=keywords, market_ids=market_ids, condition_ids=condition_ids, event_slugs=event_slugs, market_slugs=market_slugs, date_start=date_start, date_end=date_end, resolved_only=resolved_only, active_only=active_only, min_volume=min_volume, min_liquidity=min_liquidity, max_markets=max_markets, max_records=max_records, notes=note)}


@app.post("/api/data/scopes/preview")
async def data_scope_preview_api(scope_id: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_data_scope(scope_id=scope_id)}


@app.get("/api/data/scopes.csv", response_class=PlainTextResponse)
async def data_scopes_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(data_scopes_to_csv(list_data_scopes(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=data_scopes.csv"})


@app.get("/api/data/backfills")
async def data_backfills_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_backfills(limit=1000), "status": build_scoped_status()}


@app.get("/api/data/backfills.csv", response_class=PlainTextResponse)
async def data_backfills_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(backfills_to_csv(list_backfills(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=data_backfills.csv"})


@app.get("/api/data/backfills/{backfill_job_id}")
async def data_backfill_detail_api(backfill_job_id: str, user: dict = Depends(require_admin)):
    item = get_backfill(backfill_job_id)
    if not item:
        raise HTTPException(status_code=404, detail="Backfill job not found")
    return {"source": "local", "item": item}


@app.post("/api/data/backfills/preview")
async def data_backfill_preview_api(scope_id: str = Form(default=""), source_ids: str = Form(default=""), name: str = Form(default=""), operator: str = Form(default="local"), max_records: int = Form(default=0), max_requests: int = Form(default=0), max_runtime_seconds: int = Form(default=300), pagination_method: str = Form(default="offset_limit"), page_size: int = Form(default=1000), max_pages: int = Form(default=10), batch_size: int = Form(default=1000), confirmation: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_backfill(scope_id=scope_id, source_ids=source_ids, name=name, requested_by=operator, max_records=max_records, max_requests=max_requests, max_runtime_seconds=max_runtime_seconds, pagination_method=pagination_method, page_size=page_size, max_pages=max_pages, batch_size=batch_size, confirmation=confirmation, notes=note)}


@app.post("/api/data/backfills/start")
async def data_backfill_start_api(scope_id: str = Form(default=""), source_ids: str = Form(default=""), name: str = Form(default=""), operator: str = Form(default="local"), max_records: int = Form(default=0), max_requests: int = Form(default=0), max_runtime_seconds: int = Form(default=300), pagination_method: str = Form(default="offset_limit"), page_size: int = Form(default=1000), max_pages: int = Form(default=10), batch_size: int = Form(default=1000), confirmation: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": start_backfill(scope_id=scope_id, source_ids=source_ids, name=name, requested_by=operator, max_records=max_records, max_requests=max_requests, max_runtime_seconds=max_runtime_seconds, pagination_method=pagination_method, page_size=page_size, max_pages=max_pages, batch_size=batch_size, confirmation=confirmation, notes=note)}


@app.post("/api/data/backfills/{backfill_job_id}/pause")
async def data_backfill_pause_api(backfill_job_id: str, operator: str = Form(default="local"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": pause_backfill(backfill_job_id=backfill_job_id, operator=operator, note=note)}


@app.post("/api/data/backfills/{backfill_job_id}/cancel")
async def data_backfill_cancel_api(backfill_job_id: str, operator: str = Form(default="local"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": cancel_backfill(backfill_job_id=backfill_job_id, operator=operator, note=note)}


@app.get("/api/training/category-datasets")
async def training_category_datasets_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_category_datasets(limit=1000), "status": build_scoped_status()}


@app.get("/api/training/category-datasets.csv", response_class=PlainTextResponse)
async def training_category_datasets_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(category_datasets_to_csv(list_category_datasets(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_category_datasets.csv"})


@app.post("/api/training/category-datasets/preview")
async def training_category_dataset_preview_api(scope_id: str = Form(default=""), category: str = Form(default=""), source_ids: str = Form(default=""), snapshot_ids: str = Form(default=""), label_types: str = Form(default=""), feature_groups: str = Form(default="market_metadata,price_movement,spread_liquidity"), split_method: str = Form(default="chronological"), max_rows: int = Form(default=0), operator: str = Form(default="local"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_category_dataset(scope_id=scope_id, category=category, source_ids=source_ids, snapshot_ids=snapshot_ids, label_types=label_types, feature_groups=feature_groups, split_method=split_method, max_rows=max_rows, operator=operator, note=note)}


@app.post("/api/training/category-datasets/build")
async def training_category_dataset_build_api(scope_id: str = Form(default=""), category: str = Form(default=""), source_ids: str = Form(default=""), snapshot_ids: str = Form(default=""), label_types: str = Form(default=""), feature_groups: str = Form(default="market_metadata,price_movement,spread_liquidity"), split_method: str = Form(default="chronological"), max_rows: int = Form(default=0), operator: str = Form(default="local"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": build_category_dataset(scope_id=scope_id, category=category, source_ids=source_ids, snapshot_ids=snapshot_ids, label_types=label_types, feature_groups=feature_groups, split_method=split_method, max_rows=max_rows, operator=operator, note=note)}


@app.get("/api/data/status")
async def data_status_api(user: dict = Depends(require_admin)):
    return build_data_status()


@app.get("/api/data/sources")
async def data_sources_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_data_sources(limit=1000), "status": build_data_status()}


@app.post("/api/data/sources/register")
async def data_source_register_api(name: str = Form(default=""), source_type: str = Form(default="custom_csv"), source_path: str = Form(default=""), endpoint_name: str = Form(default=""), mode: str = Form(default="local_import"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": register_data_source(name=name, source_type=source_type, source_path=source_path, endpoint_name=endpoint_name, mode=mode, notes=note)}


@app.get("/api/data/sources.csv", response_class=PlainTextResponse)
async def data_sources_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(data_sources_to_csv(list_data_sources(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=data_sources.csv"})


@app.get("/api/data/ingestion/jobs")
async def data_ingestion_jobs_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_ingestion_jobs(limit=1000)}


@app.get("/api/data/ingestion/jobs.csv", response_class=PlainTextResponse)
async def data_ingestion_jobs_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(ingestion_jobs_to_csv(list_ingestion_jobs(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=data_ingestion_jobs.csv"})


@app.post("/api/data/ingestion/preview")
async def data_ingestion_preview_api(source_id: str = Form(default=""), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_data_ingestion(source_id=source_id, operator=operator, note=note)}


@app.post("/api/data/ingestion/run")
async def data_ingestion_run_api(source_id: str = Form(default=""), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, **run_data_ingestion(source_id=source_id, operator=operator, note=note)}


@app.get("/api/data/snapshots")
async def data_snapshots_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_raw_snapshots(limit=1000)}


@app.get("/api/data/snapshots.csv", response_class=PlainTextResponse)
async def data_snapshots_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(raw_snapshots_to_csv(list_raw_snapshots(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=data_raw_snapshots.csv"})


@app.get("/api/data/snapshots/{snapshot_id}")
async def data_snapshot_detail_api(snapshot_id: str, user: dict = Depends(require_admin)):
    item = get_raw_snapshot(snapshot_id)
    if not item:
        raise HTTPException(status_code=404, detail="Data snapshot not found")
    return {"item": item}


@app.get("/api/data/normalized")
async def data_normalized_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_normalized_records(limit=1000)}


@app.get("/api/data/normalized.csv", response_class=PlainTextResponse)
async def data_normalized_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(normalized_records_to_csv(list_normalized_records(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=data_normalized_records.csv"})


@app.post("/api/data/normalize/preview")
async def data_normalize_preview_api(snapshot_id: str = Form(default=""), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_normalization(snapshot_id=snapshot_id, operator=operator, note=note)}


@app.post("/api/data/normalize/run")
async def data_normalize_run_api(snapshot_id: str = Form(default=""), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, **run_normalization(snapshot_id=snapshot_id, operator=operator, note=note)}


@app.get("/api/data/labels")
async def data_labels_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_labels(limit=1000)}


@app.get("/api/data/labels.csv", response_class=PlainTextResponse)
async def data_labels_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(labels_to_csv(list_labels(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=data_labels.csv"})


@app.post("/api/data/labels/preview")
async def data_labels_preview_api(snapshot_id: str = Form(default=""), label_type: str = Form(default="price_movement_over_horizon"), horizon: str = Form(default="1h"), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_labels(snapshot_id=snapshot_id, label_type=label_type, horizon=horizon, operator=operator, note=note)}


@app.post("/api/data/labels/generate")
async def data_labels_generate_api(snapshot_id: str = Form(default=""), dataset_id: str = Form(default=""), label_type: str = Form(default="price_movement_over_horizon"), horizon: str = Form(default="1h"), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, **generate_labels(snapshot_id=snapshot_id, dataset_id=dataset_id, label_type=label_type, horizon=horizon, operator=operator, note=note)}


@app.post("/api/data/labels/review")
async def data_label_review_api(label_id: str = Form(default=""), status: str = Form(default="label_approved"), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return review_label(label_id=label_id, status=status, operator=operator, note=note)


# v1.5.0 Internet ingestion + host training jobs. Disabled by default; no endpoint trades.
@app.get("/api/data/internet-sources")
async def internet_sources_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_internet_sources(limit=1000), "status": build_internet_data_status()}


@app.post("/api/data/internet-sources/register")
async def internet_source_register_api(name: str = Form(default=""), source_type: str = Form(default="public_json_url"), base_url: str = Form(default=""), endpoint_path: str = Form(default=""), allowed_domain: str = Form(default=""), query_params: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": register_internet_source(name=name, source_type=source_type, base_url=base_url, endpoint_path=endpoint_path, allowed_domain=allowed_domain, query_params=query_params, notes=note)}


@app.post("/api/data/internet-sources/validate")
async def internet_source_validate_api(source_id: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": validate_internet_source(source_id=source_id)}


@app.get("/api/data/internet-sources.csv", response_class=PlainTextResponse)
async def internet_sources_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(internet_sources_to_csv(list_internet_sources(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=internet_data_sources.csv"})


@app.post("/api/data/internet-ingestion/preview")
async def internet_ingestion_preview_api(source_id: str = Form(default=""), operator: str = Form(default="local"), confirmation: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_internet_ingestion(source_id=source_id, operator=operator, confirmation=confirmation, note=note)}


@app.post("/api/data/internet-ingestion/run")
async def internet_ingestion_run_api(source_id: str = Form(default=""), operator: str = Form(default="local"), confirmation: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": run_internet_ingestion(source_id=source_id, operator=operator, confirmation=confirmation, note=note)}


@app.get("/api/data/internet-ingestion/jobs")
async def internet_ingestion_jobs_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_internet_ingestion_jobs(limit=1000)}


@app.get("/api/data/internet-ingestion/jobs.csv", response_class=PlainTextResponse)
async def internet_ingestion_jobs_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(internet_ingestion_jobs_to_csv(list_internet_ingestion_jobs(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=internet_ingestion_jobs.csv"})


@app.get("/api/data/internet-ingestion/schedules")
async def internet_ingestion_schedules_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_internet_schedules(limit=1000), "status": build_internet_data_status()}


@app.post("/api/data/internet-ingestion/schedules/register")
async def internet_ingestion_schedule_register_api(source_id: str = Form(default=""), name: str = Form(default=""), interval_minutes: int = Form(default=60), max_runs_per_day: int = Form(default=24), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": register_internet_schedule(source_id=source_id, name=name, interval_minutes=interval_minutes, max_runs_per_day=max_runs_per_day, enabled=False, notes=note)}


@app.post("/api/data/internet-ingestion/schedules/due-preview")
async def internet_ingestion_due_preview_api(user: dict = Depends(require_admin)):
    return {"ok": True, "item": preview_due_internet_ingestion()}


@app.get("/api/data/internet-workflow")
async def internet_workflow_api(user: dict = Depends(require_admin)):
    return build_internet_workflow()


@app.get("/api/training/host-jobs")
async def training_host_jobs_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_host_training_jobs(limit=1000), "status": build_internet_data_status()}


@app.get("/api/training/host-jobs.csv", response_class=PlainTextResponse)
async def training_host_jobs_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(host_training_jobs_to_csv(list_host_training_jobs(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_host_jobs.csv"})


@app.post("/api/training/host-jobs/preview")
async def training_host_job_preview_api(job_type: str = Form(default="baseline_training"), dataset_id: str = Form(default=""), dataset_build_id: str = Form(default=""), feature_set_id: str = Form(default=""), model_type: str = Form(default="heuristic_baseline"), operator: str = Form(default="local"), confirmation: str = Form(default=""), note: str = Form(default=""), max_rows: int = Form(default=0), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_host_training_job(job_type=job_type, dataset_id=dataset_id, dataset_build_id=dataset_build_id, feature_set_id=feature_set_id, model_type=model_type, operator=operator, confirmation=confirmation, note=note, max_rows=max_rows)}


@app.post("/api/training/host-jobs/start")
async def training_host_job_start_api(job_type: str = Form(default="baseline_training"), dataset_id: str = Form(default=""), dataset_build_id: str = Form(default=""), feature_set_id: str = Form(default=""), model_type: str = Form(default="heuristic_baseline"), operator: str = Form(default="local"), confirmation: str = Form(default=""), note: str = Form(default=""), max_rows: int = Form(default=0), user: dict = Depends(require_admin)):
    return {"ok": True, "item": start_host_training_job(job_type=job_type, dataset_id=dataset_id, dataset_build_id=dataset_build_id, feature_set_id=feature_set_id, model_type=model_type, operator=operator, confirmation=confirmation, note=note, max_rows=max_rows)}


@app.post("/api/training/host-jobs/dataset-quality-scan")
async def training_host_job_dataset_quality_scan_api(dataset_id: str = Form(default=""), dataset_build_id: str = Form(default=""), operator: str = Form(default="local"), confirmation: str = Form(default=""), note: str = Form(default=""), max_rows: int = Form(default=0), user: dict = Depends(require_admin)):
    return {"ok": True, "item": start_host_training_job(job_type="dataset_quality_scan", dataset_id=dataset_id, dataset_build_id=dataset_build_id, feature_set_id="", model_type="deterministic_quality_scan", operator=operator, confirmation=confirmation, note=note, max_rows=max_rows)}


@app.post("/api/training/host-jobs/signal-generation-preview")
async def training_host_job_signal_generation_preview_api(dataset_id: str = Form(default=""), dataset_build_id: str = Form(default=""), operator: str = Form(default="local"), confirmation: str = Form(default=""), note: str = Form(default=""), max_rows: int = Form(default=0), user: dict = Depends(require_admin)):
    return {"ok": True, "item": start_host_training_job(job_type="signal_generation_preview", dataset_id=dataset_id, dataset_build_id=dataset_build_id, feature_set_id="", model_type="manual_review_signal_preview", operator=operator, confirmation=confirmation, note=note, max_rows=max_rows)}


@app.post("/api/training/host-jobs/{host_training_job_id}/cancel")
async def training_host_job_cancel_api(host_training_job_id: str, operator: str = Form(default="local"), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "item": cancel_host_training_job(host_training_job_id=host_training_job_id, operator=operator, note=note)}


@app.get("/api/training/host-jobs/caps")
async def training_host_job_caps_api(user: dict = Depends(require_admin)):
    status = build_internet_data_status()
    return {"source": "local", "training_caps": status.get("training_caps", {}), "host_training_jobs_enabled": status.get("host_training_jobs_enabled", False), "guardrail": status.get("guardrail", "")}


@app.get("/api/training/host-jobs/{host_training_job_id}")
async def training_host_job_detail_api(host_training_job_id: str, user: dict = Depends(require_admin)):
    item = get_host_training_job(host_training_job_id)
    if not item:
        raise HTTPException(status_code=404, detail="Host training job not found")
    return {"source": "local", "item": item}


@app.get("/api/training/dataset-builder/status")
async def training_dataset_builder_status_api(user: dict = Depends(require_admin)):
    return build_dataset_builder_status()


@app.post("/api/training/dataset-builder/preview")
async def training_dataset_builder_preview_api(name: str = Form(default=""), source_ids: str = Form(default=""), snapshot_ids: str = Form(default=""), label_types: str = Form(default=""), feature_groups: str = Form(default="market_metadata,price_movement,spread_liquidity"), split_method: str = Form(default="chronological"), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, "recorded": False, "item": preview_dataset_build(name=name, source_ids=_split_csv(source_ids), snapshot_ids=_split_csv(snapshot_ids), label_types=_split_csv(label_types), feature_groups=_split_csv(feature_groups), split_method=split_method, operator=operator, note=note)}


@app.post("/api/training/dataset-builder/build")
async def training_dataset_builder_build_api(name: str = Form(default=""), source_ids: str = Form(default=""), snapshot_ids: str = Form(default=""), label_types: str = Form(default=""), feature_groups: str = Form(default="market_metadata,price_movement,spread_liquidity"), split_method: str = Form(default="chronological"), operator: str = Form(default=""), note: str = Form(default=""), user: dict = Depends(require_admin)):
    return {"ok": True, **build_training_dataset(name=name, source_ids=_split_csv(source_ids), snapshot_ids=_split_csv(snapshot_ids), label_types=_split_csv(label_types), feature_groups=_split_csv(feature_groups), split_method=split_method, operator=operator, note=note)}


@app.get("/api/training/dataset-builds")
async def training_dataset_builds_api(user: dict = Depends(require_admin)):
    return {"source": "local", "items": list_dataset_builds(limit=1000)}


@app.get("/api/training/dataset-builds.csv", response_class=PlainTextResponse)
async def training_dataset_builds_csv(user: dict = Depends(require_admin)):
    return PlainTextResponse(dataset_builds_to_csv(list_dataset_builds(limit=10000)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_dataset_builds.csv"})


@app.get("/api/training/dataset-builds/{dataset_build_id}/manifest")
async def training_dataset_build_manifest_api(dataset_build_id: str, user: dict = Depends(require_admin)):
    return get_dataset_manifest(dataset_build_id)
