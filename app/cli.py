from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .gamma_client import GammaClient
from .clob_client import ClobClient
from .scoring import attach_scores
from .history import latest_snapshot_summary, list_snapshots
from .snapshots import calculate_movers, detect_new_markets, load_latest, save_snapshot, summarize_snapshot
from .research import make_research_packet
from .watchlist import add_to_watchlist, load_watchlist, remove_from_watchlist
from .auth_status import get_api_key_status
from .probability import attach_probability
from .paper_trading import buy as paper_buy, sell as paper_sell, reset_portfolio, summarize_portfolio, load_trades, load_portfolio
from .strategy import recommend_paper_trades, explain_strategy
from .backtest import run_snapshot_backtest, list_backtests
from .risk import risk_status, check_paper_buy
from .alerts import generate_alerts, summarize_alerts
from .notes import add_note, delete_note, load_notes, notes_for_market, notes_summary
from .sources import build_market_collection_targets, build_market_source_pack, build_source_links, check_sources_status, list_sources, source_summary
from .evidence import create_evidence_packet, evidence_summary, list_evidence_packets, load_evidence_packet
from .evidence_scoring import score_market_evidence, score_packet_by_id
from .evidence_probability import attach_evidence_probability, evidence_adjusted_probability
from .opportunity_engine import rank_opportunities, opportunity_summary
from .readiness_engine import build_readiness_result
from .trade_tickets import create_trade_ticket, get_trade_ticket, list_trade_tickets, summarize_trade_tickets, update_trade_ticket
from .paper_settlement import list_settlements, preview_settlement, settle_market, settlement_candidates, settlement_summary
from .paper_positions import list_position_events, position_alerts, position_control_summary, update_position_plan
from .paper_exit_tickets import create_exit_ticket, executable_exit_snapshot, get_exit_ticket, list_exit_tickets, summarize_exit_tickets, update_exit_ticket
from .analytics import trade_analytics, trades_to_csv
from .paper_audit import audit_to_csv, build_audit_events, build_market_audit, summarize_audit
from .paper_review import build_market_review, build_review_report, review_report_to_csv
from .paper_playbooks import build_playbook_board, create_playbook_decision, evaluate_market_playbooks, get_playbook, list_playbook_decisions, list_playbooks, summarize_playbook_decisions, summarize_playbooks
from .playbook_performance import build_playbook_performance, build_playbook_performance_detail, playbook_performance_to_csv
from .paper_risk_budget import build_market_risk_budget, build_risk_budget, risk_budget_to_csv
from .paper_preflight import build_preflight_board, build_ticket_preflight, preflight_to_csv
from .paper_approvals import approvals_to_csv, approve_trade_ticket, build_execution_approval_board, get_execution_approval, reject_trade_ticket
from .paper_execution_queue import build_execution_queue, build_ticket_execution_queue_item, execution_queue_to_csv
from .paper_runbook import build_runbook, get_runbook_item, record_runbook_acknowledgement, runbook_to_csv
from .paper_briefing import briefing_to_csv, build_paper_ops_briefing, list_briefing_checkpoints, record_briefing_checkpoint
from .paper_handoff import build_operator_handoff_board, build_operator_handoff_reconciliation_board, get_operator_handoff, handoff_reconciliation_to_csv, handoffs_to_csv, list_operator_handoffs, reconcile_operator_handoff, record_operator_handoff
from .paper_ops_aging import build_ops_aging_detail, build_paper_ops_aging, ops_aging_to_csv
from .paper_ops_escalations import build_ops_escalation_board, create_ops_escalation, get_ops_escalation, list_ops_escalations, ops_escalations_to_csv, update_ops_escalation
from .paper_ops_escalation_review import build_ops_escalation_review, ops_escalation_review_to_csv, review_ops_escalation
from .paper_ops_closeout import build_paper_ops_closeout, paper_ops_closeout_to_csv
from .paper_ops_closeout_signoffs import build_ops_closeout_signoff_board, get_ops_closeout_signoff, list_ops_closeout_signoffs, ops_closeout_signoffs_to_csv, record_ops_closeout_signoff
from .live_config import build_live_config_readiness, live_config_readiness_to_csv, live_config_template
from .live_order_intents import build_live_order_intent, build_live_order_intent_board, get_live_order_intent, live_order_intents_to_csv, list_live_order_intents, record_live_order_intent
from .live_order_preflight import build_live_order_preflight_board, live_order_preflights_to_csv, list_live_order_preflights, review_live_order_intent
from .live_order_authorizations import build_live_order_authorization_board, get_live_order_authorization, live_order_authorizations_to_csv, list_live_order_authorizations, record_live_order_authorization
from .live_execution_packets import build_live_execution_packet, build_live_execution_packet_board, get_live_execution_packet, live_execution_packets_to_csv, list_live_execution_packets, record_live_execution_packet
from .live_dry_run_adapter import build_live_dry_run_board, build_live_dry_run_receipt, get_live_dry_run_receipt, live_dry_run_receipts_to_csv, list_live_dry_run_receipts, record_live_dry_run_receipt
from .live_dry_run_review import build_live_dry_run_review_board, live_dry_run_reviews_to_csv, list_live_dry_run_reviews, review_live_dry_run_packet
from .live_adapter import build_live_adapter_readiness, build_live_adapter_request, build_live_adapter_request_board, build_manual_execution_review, build_manual_execution_review_board, get_live_adapter_readonly_validation, get_live_adapter_request, get_manual_execution_review, list_live_adapter_readonly_validations, list_live_adapter_requests, list_manual_execution_reviews, live_adapter_readiness_to_csv, live_adapter_requests_to_csv, live_adapter_validations_to_csv, manual_execution_reviews_to_csv, preview_live_adapter_readonly_validation, record_live_adapter_readonly_validation, record_live_adapter_request, record_manual_execution_review
from .live_execution_control import build_live_execution_attempt_board, build_live_execution_control_readiness, build_manual_cancel_preview, build_manual_submit_preview, get_live_execution_attempt, list_live_execution_attempts, live_execution_attempts_to_csv, live_execution_control_readiness_to_csv, record_manual_cancel_attempt, record_manual_submit_attempt
from .live_trading import autonomous_runs_to_csv, build_autonomous_run_preview, build_autonomous_status, build_live_order_board, build_live_reconciliation, build_live_trading_status, build_strategy_signal_board, get_autonomous_run, get_live_order_event, get_strategy_signal, list_autonomous_runs, list_live_order_events, list_strategy_signals, live_orders_to_csv, live_reconciliation_to_csv, record_autonomous_run, record_strategy_signal, strategy_signals_to_csv, validate_strategy_signal_payload
from .live_clob_adapter import build_clob_adapter_status, clob_adapter_status_to_csv
from .live_ops import build_live_adapter_verification, build_live_readiness_checklist, build_operator_runbook, live_adapter_verification_to_csv, live_readiness_checklist_to_csv
from .market_data import build_execution_quality_board, build_execution_quality_simulation, build_market_data_board, build_market_snapshot, execution_quality_to_csv, fetch_market_data_preview, get_execution_quality_simulation, get_market_snapshot, list_execution_quality_simulations, list_market_snapshots, market_snapshots_to_csv, parse_orderbook_metrics, record_execution_quality_simulation, record_market_snapshot

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
    get_dataset as get_training_dataset,
    list_backtests as list_training_backtests,
    list_datasets as list_training_datasets,
    list_feature_sets,
    list_models as list_training_models,
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

console = Console()


def money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def signed_money(value: Any) -> str:
    try:
        n = float(value)
        return f"{n:+,.0f}"
    except (TypeError, ValueError):
        return "+0"


def price_summary(outcomes: list[dict[str, Any]]) -> str:
    if not outcomes:
        return ""
    parts = []
    for row in outcomes[:3]:
        parts.append(f"{row.get('name')}: {float(row.get('price', 0)):.2f}")
    return " | ".join(parts)


def _json_arg(value: str) -> dict[str, Any]:
    text = value or "{}"
    if text.startswith("@"):
        text = Path(text[1:]).read_text(encoding="utf-8")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("JSON input must decode to an object")
    return parsed


async def run(args: argparse.Namespace) -> None:
    client = GammaClient()
    clob = ClobClient()


    # v1.6.0 Scoped historical backfill + category datasets. Operator-controlled; no command trades.
    if args.data_scopes:
        console.print_json(data={"items": list_data_scopes(limit=args.limit), "status": build_scoped_status()})
        return

    if args.register_data_scope:
        item = register_data_scope(name=args.name, scope_type=args.scope_type, category=args.category, keywords=args.keywords, market_ids=args.market_ids, condition_ids=args.condition_ids, event_slugs=args.event_slugs, market_slugs=args.market_slugs, date_start=args.date_start, date_end=args.date_end, resolved_only=args.resolved_only, active_only=args.active_only, min_volume=args.min_volume, min_liquidity=args.min_liquidity, max_markets=args.max_markets, max_records=args.max_records, notes=args.note)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.preview_data_scope:
        console.print_json(data={"recorded": False, "item": preview_data_scope(scope_id=args.scope_id)})
        return

    if args.export_data_scopes:
        out = Path(args.export_data_scopes)
        out.write_text(data_scopes_to_csv(list_data_scopes(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported data scopes CSV:[/green] {out}")
        return

    if args.data_backfills:
        console.print_json(data={"items": list_backfills(limit=args.limit), "status": build_scoped_status()})
        return

    if args.data_backfill_detail:
        item = get_backfill(args.data_backfill_detail)
        console.print_json(data={"found": bool(item), "item": item or {}})
        return

    if args.preview_data_backfill or args.start_data_backfill:
        fn = start_backfill if args.start_data_backfill else preview_backfill
        item = fn(scope_id=args.scope_id, source_ids=args.source_id, name=args.name, requested_by=args.operator, max_records=args.max_records, max_requests=args.max_requests, max_runtime_seconds=args.max_runtime_seconds, pagination_method=args.pagination_method, page_size=args.page_size, max_pages=args.max_pages, batch_size=args.batch_size, confirmation=args.confirmation, notes=args.note)
        console.print_json(data={"recorded": bool(args.start_data_backfill), "item": item})
        return

    if args.pause_data_backfill:
        item = pause_backfill(backfill_job_id=args.data_backfill_detail or args.pause_data_backfill, operator=args.operator, note=args.note)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.cancel_data_backfill:
        item = cancel_backfill(backfill_job_id=args.data_backfill_detail or args.cancel_data_backfill, operator=args.operator, note=args.note)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.export_data_backfills:
        out = Path(args.export_data_backfills)
        out.write_text(backfills_to_csv(list_backfills(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported scoped backfills CSV:[/green] {out}")
        return

    if args.training_category_datasets:
        console.print_json(data={"items": list_category_datasets(limit=args.limit), "status": build_scoped_status()})
        return

    if getattr(args, "export_training_category_datasets", None):
        out = Path(args.export_training_category_datasets)
        out.write_text(category_datasets_to_csv(list_category_datasets(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported category datasets CSV:[/green] {out}")
        return

    if args.preview_training_category_dataset or args.build_training_category_dataset:
        fn = build_category_dataset if args.build_training_category_dataset else preview_category_dataset
        item = fn(scope_id=args.scope_id, category=args.category, source_ids=args.source_id, snapshot_ids=args.snapshot_id, label_types=args.label_type, feature_groups=args.feature_groups, split_method=args.split_method, max_rows=(args.max_rows or args.max_records), operator=args.operator, note=args.note)
        console.print_json(data={"recorded": bool(args.build_training_category_dataset), "item": item})
        return

    # v1.5.0 Internet ingestion + host training jobs. Disabled by default; no command trades.
    if args.internet_data_sources:
        console.print_json(data={"items": list_internet_sources(limit=args.limit), "status": build_internet_data_status()})
        return

    if args.register_internet_data_source:
        item = register_internet_source(name=args.name, source_type=args.source_type, base_url=args.base_url, endpoint_path=args.endpoint_path, allowed_domain=args.allowed_domain, query_params=args.query_params, enabled=False, notes=args.note)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.validate_internet_data_source:
        console.print_json(data={"item": validate_internet_source(source_id=args.source_id)})
        return

    if args.export_internet_data_sources:
        out = Path(args.export_internet_data_sources)
        out.write_text(internet_sources_to_csv(list_internet_sources(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported internet data sources CSV:[/green] {out}")
        return

    if args.preview_internet_data_ingestion or args.run_internet_data_ingestion:
        item = run_internet_ingestion(source_id=args.source_id, operator=args.operator, confirmation=args.confirmation, note=args.note) if args.run_internet_data_ingestion else preview_internet_ingestion(source_id=args.source_id, operator=args.operator, confirmation=args.confirmation, note=args.note)
        console.print_json(data={"recorded": bool(args.run_internet_data_ingestion), "item": item})
        return

    if args.internet_ingestion_schedules:
        console.print_json(data={"items": list_internet_schedules(limit=args.limit), "status": build_internet_data_status()})
        return

    if args.register_internet_ingestion_schedule:
        item = register_internet_schedule(source_id=args.source_id, name=args.name, interval_minutes=args.interval_minutes, max_runs_per_day=args.max_runs_per_day, enabled=False, notes=args.note)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.preview_due_internet_ingestion:
        console.print_json(data=preview_due_internet_ingestion())
        return

    if args.internet_training_workflow:
        console.print_json(data=build_internet_workflow())
        return

    if args.training_host_jobs:
        console.print_json(data={"items": list_host_training_jobs(limit=args.limit), "status": build_internet_data_status()})
        return

    if getattr(args, "training_job_caps", False):
        status = build_internet_data_status()
        console.print_json(data={"training_caps": status.get("training_caps", {}), "host_training_jobs_enabled": status.get("host_training_jobs_enabled", False), "guardrail": status.get("guardrail", "")})
        return

    if args.training_host_job_detail:
        item = get_host_training_job(args.training_host_job_detail)
        console.print_json(data={"found": bool(item), "item": item or {}})
        return

    if getattr(args, "run_dataset_quality_scan", False):
        item = start_host_training_job(job_type="dataset_quality_scan", dataset_id=args.dataset_id, dataset_build_id=args.dataset_build_id, feature_set_id=args.feature_set_id, model_type="deterministic_quality_scan", operator=args.operator, confirmation=args.confirmation, note=args.note, max_rows=args.training_max_rows)
        console.print_json(data={"recorded": True, "item": item})
        return

    if getattr(args, "run_signal_generation_preview", False):
        item = start_host_training_job(job_type="signal_generation_preview", dataset_id=args.dataset_id, dataset_build_id=args.dataset_build_id, feature_set_id=args.feature_set_id, model_type="manual_review_signal_preview", operator=args.operator, confirmation=args.confirmation, note=args.note, max_rows=args.training_max_rows)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.preview_training_host_job or args.start_training_host_job:
        item = start_host_training_job(job_type=args.job_type, dataset_id=args.dataset_id, dataset_build_id=args.dataset_build_id, feature_set_id=args.feature_set_id, model_type=args.model_type, operator=args.operator, confirmation=args.confirmation, note=args.note, max_rows=args.training_max_rows) if args.start_training_host_job else preview_host_training_job(job_type=args.job_type, dataset_id=args.dataset_id, dataset_build_id=args.dataset_build_id, feature_set_id=args.feature_set_id, model_type=args.model_type, operator=args.operator, confirmation=args.confirmation, note=args.note, max_rows=args.training_max_rows)
        console.print_json(data={"recorded": bool(args.start_training_host_job), "item": item})
        return

    if args.cancel_training_host_job:
        item = cancel_host_training_job(host_training_job_id=args.host_training_job_id or args.cancel_training_host_job, operator=args.operator, note=args.note)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.export_training_host_jobs:
        out = Path(args.export_training_host_jobs)
        out.write_text(host_training_jobs_to_csv(list_host_training_jobs(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported host training jobs CSV:[/green] {out}")
        return

    # v1.3.0 Data Ingestion + Dataset Builder commands. Local-first; no command trades.
    if args.data_status:
        console.print_json(data=build_data_status())
        return

    if args.data_sources:
        console.print_json(data={"items": list_data_sources(limit=args.limit), "status": build_data_status()})
        return

    if args.register_data_source:
        item = register_data_source(name=args.name, source_type=args.source_type, source_path=args.dataset_path, endpoint_name=args.endpoint_name, mode=args.data_mode, notes=args.note)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.export_data_sources:
        out = Path(args.export_data_sources)
        out.write_text(data_sources_to_csv(list_data_sources(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported data sources CSV:[/green] {out}")
        return

    if args.data_ingestion_jobs:
        console.print_json(data={"items": list_ingestion_jobs(limit=args.limit)})
        return

    if args.preview_data_ingestion or args.run_data_ingestion:
        item = run_data_ingestion(source_id=args.source_id, operator=args.operator, note=args.note) if args.run_data_ingestion else preview_data_ingestion(source_id=args.source_id, operator=args.operator, note=args.note)
        console.print_json(data={"recorded": bool(args.run_data_ingestion), "item": item})
        return

    if args.export_data_ingestion_jobs:
        out = Path(args.export_data_ingestion_jobs)
        out.write_text(ingestion_jobs_to_csv(list_ingestion_jobs(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported data ingestion jobs CSV:[/green] {out}")
        return

    if args.data_snapshots:
        console.print_json(data={"items": list_raw_snapshots(limit=args.limit)})
        return

    if args.data_snapshot_detail:
        item = get_raw_snapshot(args.data_snapshot_detail)
        console.print_json(data={"item": item or {}, "found": bool(item)})
        return

    if args.export_data_snapshots:
        out = Path(args.export_data_snapshots)
        out.write_text(raw_snapshots_to_csv(list_raw_snapshots(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported raw snapshots CSV:[/green] {out}")
        return

    if args.preview_data_normalization or args.run_data_normalization:
        item = run_normalization(snapshot_id=args.snapshot_id, operator=args.operator, note=args.note) if args.run_data_normalization else preview_normalization(snapshot_id=args.snapshot_id, operator=args.operator, note=args.note)
        console.print_json(data={"recorded": bool(args.run_data_normalization), "item": item})
        return

    if args.data_normalized_records:
        console.print_json(data={"items": list_normalized_records(limit=args.limit, snapshot_id=args.snapshot_id)})
        return

    if args.export_data_normalized_records:
        out = Path(args.export_data_normalized_records)
        out.write_text(normalized_records_to_csv(list_normalized_records(limit=10000, snapshot_id=args.snapshot_id)), encoding="utf-8")
        console.print(f"[green]Exported normalized records CSV:[/green] {out}")
        return

    if args.data_labels:
        console.print_json(data={"items": list_labels(limit=args.limit)})
        return

    if args.preview_data_labels or args.generate_data_labels:
        item = generate_labels(snapshot_id=args.snapshot_id, dataset_id=args.dataset_id, label_type=args.label_type, horizon=args.horizon, operator=args.operator, note=args.note) if args.generate_data_labels else preview_labels(snapshot_id=args.snapshot_id, label_type=args.label_type, horizon=args.horizon, operator=args.operator, note=args.note)
        console.print_json(data={"recorded": bool(args.generate_data_labels), "item": item})
        return

    if args.review_data_label:
        item = review_label(label_id=args.label_id, status=args.label_status, operator=args.operator, note=args.note)
        console.print_json(data=item)
        return

    if args.export_data_labels:
        out = Path(args.export_data_labels)
        out.write_text(labels_to_csv(list_labels(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported labels CSV:[/green] {out}")
        return

    if args.training_dataset_builder_status:
        console.print_json(data=build_dataset_builder_status())
        return

    if args.preview_training_dataset_build or args.build_training_dataset:
        source_ids = [x.strip() for x in (args.source_id or "").split(",") if x.strip()]
        snapshot_ids = [x.strip() for x in (args.snapshot_id or "").split(",") if x.strip()]
        label_types = [x.strip() for x in (args.label_type or "").split(",") if x.strip()]
        feature_groups = [x.strip() for x in (args.feature_groups or "market_metadata,price_movement,spread_liquidity").split(",") if x.strip()]
        item = build_training_dataset(name=args.name, source_ids=source_ids, snapshot_ids=snapshot_ids, label_types=label_types, feature_groups=feature_groups, split_method=args.split_method, operator=args.operator, note=args.note) if args.build_training_dataset else preview_dataset_build(name=args.name, source_ids=source_ids, snapshot_ids=snapshot_ids, label_types=label_types, feature_groups=feature_groups, split_method=args.split_method, operator=args.operator, note=args.note)
        console.print_json(data={"recorded": bool(args.build_training_dataset), "item": item})
        return

    if args.training_dataset_builds:
        console.print_json(data={"items": list_dataset_builds(limit=args.limit)})
        return

    if args.training_dataset_build_manifest:
        console.print_json(data=get_dataset_manifest(args.dataset_build_id))
        return

    if args.export_training_dataset_builds:
        out = Path(args.export_training_dataset_builds)
        out.write_text(dataset_builds_to_csv(list_dataset_builds(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported dataset builds CSV:[/green] {out}")
        return

    if args.training_status:
        console.print_json(data=build_training_status())
        return

    if args.training_datasets:
        rows = list_training_datasets(limit=args.limit)
        if args.json:
            console.print_json(data={"items": rows, "status": build_training_status()})
        else:
            table = Table(title="Training Datasets")
            table.add_column("Dataset")
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Rows", justify="right")
            table.add_column("Status")
            for row in rows:
                table.add_row(str(row.get("dataset_id")), str(row.get("name")), str(row.get("dataset_type")), str(row.get("row_count")), str(row.get("status")))
            console.print(table)
        return

    if args.training_dataset_detail:
        item = get_training_dataset(args.training_dataset_detail)
        if not item:
            console.print(f"[red]Training dataset not found:[/red] {args.training_dataset_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.validate_training_dataset or args.register_training_dataset:
        item = register_dataset(name=args.name, dataset_type=args.dataset_type, source_path=args.dataset_path, source=args.source, notes=args.note) if args.register_training_dataset else validate_dataset_payload(name=args.name, dataset_type=args.dataset_type, source_path=args.dataset_path)
        console.print_json(data={"recorded": bool(args.register_training_dataset), "item": item})
        return

    if args.export_training_datasets:
        out = Path(args.export_training_datasets)
        out.write_text(datasets_to_csv(list_training_datasets(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported training datasets CSV:[/green] {out}")
        return

    if args.training_features:
        rows = list_feature_sets(limit=args.limit)
        if args.json:
            console.print_json(data={"items": rows})
        else:
            table = Table(title="Training Feature Sets")
            table.add_column("Feature set")
            table.add_column("Name")
            table.add_column("Dataset")
            table.add_column("Features", justify="right")
            table.add_column("Status")
            for row in rows:
                table.add_row(str(row.get("feature_set_id")), str(row.get("name")), str(row.get("dataset_id")), str(row.get("feature_count")), str(row.get("status")))
            console.print(table)
        return

    if args.build_training_features_preview or args.register_training_feature_set:
        groups = [x.strip() for x in (args.feature_groups or "market_metadata,spread_liquidity,execution_quality").split(",") if x.strip()]
        item = register_feature_set(dataset_id=args.dataset_id, name=args.name, feature_groups=groups, target_column=args.target, lookback_window=args.lookback_window, prediction_horizon=args.prediction_horizon, notes=args.note) if args.register_training_feature_set else build_feature_set_preview(dataset_id=args.dataset_id, name=args.name, feature_groups=groups, target_column=args.target, lookback_window=args.lookback_window, prediction_horizon=args.prediction_horizon)
        console.print_json(data={"recorded": bool(args.register_training_feature_set), "item": item})
        return

    if args.export_training_features:
        out = Path(args.export_training_features)
        out.write_text(feature_sets_to_csv(list_feature_sets(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported training feature sets CSV:[/green] {out}")
        return

    if args.training_runs:
        rows = list_training_runs(limit=args.limit)
        console.print_json(data={"items": rows}) if args.json else console.print_json(data={"count": len(rows), "items": rows[:10]})
        return

    if args.preview_training_run or args.start_training_run:
        item = start_training_run(dataset_id=args.dataset_id, feature_set_id=args.feature_set_id, model_type=args.model_type, target=args.target, name=args.name, notes=args.note) if args.start_training_run else preview_training_run(dataset_id=args.dataset_id, feature_set_id=args.feature_set_id, model_type=args.model_type, target=args.target, name=args.name)
        console.print_json(data={"recorded": bool(args.start_training_run), "item": item})
        return

    if args.export_training_runs:
        out = Path(args.export_training_runs)
        out.write_text(training_runs_to_csv(list_training_runs(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported training runs CSV:[/green] {out}")
        return

    if args.training_models:
        console.print_json(data={"items": list_training_models(limit=args.limit)})
        return

    if args.register_training_model:
        item = register_model(name=args.name, training_run_id=args.training_run_id, strategy_id=args.strategy_id, model_type=args.model_type, notes=args.note)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.export_training_models:
        out = Path(args.export_training_models)
        out.write_text(models_to_csv(list_training_models(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported training models CSV:[/green] {out}")
        return

    if args.training_backtests:
        console.print_json(data={"items": list_training_backtests(limit=args.limit)})
        return

    if args.preview_training_backtest or args.run_training_backtest:
        item = run_backtest(training_run_id=args.training_run_id, dataset_id=args.dataset_id, feature_set_id=args.feature_set_id, strategy_id=args.strategy_id, notes=args.note) if args.run_training_backtest else preview_backtest(training_run_id=args.training_run_id, dataset_id=args.dataset_id, feature_set_id=args.feature_set_id, strategy_id=args.strategy_id)
        console.print_json(data={"recorded": bool(args.run_training_backtest), "item": item})
        return

    if args.export_training_backtests:
        out = Path(args.export_training_backtests)
        out.write_text(backtests_to_csv(list_training_backtests(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported training backtests CSV:[/green] {out}")
        return

    if args.preview_training_signals or args.queue_training_signals:
        item = queue_training_signals(model_id=args.model_id, backtest_id=args.backtest_id, strategy_id=args.strategy_id, market_id=args.market_id, token_id=args.token_id, side=args.side, limit_price=args.price, size=args.size, confidence=args.confidence) if args.queue_training_signals else preview_training_signals(model_id=args.model_id, backtest_id=args.backtest_id, strategy_id=args.strategy_id, market_id=args.market_id, token_id=args.token_id, side=args.side, limit_price=args.price, size=args.size, confidence=args.confidence)
        console.print_json(data={"recorded": bool(args.queue_training_signals), "item": item})
        return

    if args.market_data_snapshots:
        board = build_market_data_board(limit=args.limit, market_id=args.market_id, token_id=args.token_id, status=args.market_data_status)
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "fetch_boundary": board.get("fetch_boundary", {})})
            table = Table(title="Market Data Snapshots")
            table.add_column("Snapshot")
            table.add_column("Status")
            table.add_column("Market")
            table.add_column("Token")
            table.add_column("Bid/Ask")
            table.add_column("Spread")
            table.add_column("Depth")
            for row in board.get("items", []):
                table.add_row(str(row.get("snapshot_id") or ""), str(row.get("status") or ""), str(row.get("market_id") or ""), str(row.get("token_id") or ""), f"{row.get('best_bid')}/{row.get('best_ask')}", f"{row.get('spread_bps') or 0} bps", f"{row.get('total_bid_depth') or 0}/{row.get('total_ask_depth') or 0}")
            console.print(table)
        return

    if args.market_data_snapshot_detail:
        item = get_market_snapshot(args.market_data_snapshot_detail)
        if not item:
            console.print(f"[red]Market-data snapshot not found:[/red] {args.market_data_snapshot_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.parse_market_data_snapshot_preview or args.record_market_data_snapshot:
        payload = _json_arg(args.orderbook_json)
        if args.parse_market_data_snapshot_preview:
            console.print_json(data={"recorded": False, "metrics": parse_orderbook_metrics(payload), "item": build_market_snapshot(payload, source=args.source)})
            return
        item = record_market_snapshot(payload, source=args.source)
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.fetch_market_data_snapshot_preview or args.fetch_market_data_snapshot_record:
        item = fetch_market_data_preview(market_id=args.market_id, token_id=args.token_id)
        console.print_json(data={"recorded": False, "item": item})
        return

    if args.export_market_data_snapshots:
        rows = list_market_snapshots(limit=10000, market_id=args.market_id, token_id=args.token_id, status=args.market_data_status)
        out = Path(args.export_market_data_snapshots)
        out.write_text(market_snapshots_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported market-data snapshots CSV:[/green] {out}")
        return

    if args.execution_quality:
        board = build_execution_quality_board(limit=args.limit, state=args.execution_quality_state, market_id=args.market_id, token_id=args.token_id)
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Execution Quality Simulations")
            table.add_column("Simulation")
            table.add_column("State")
            table.add_column("Market")
            table.add_column("Side")
            table.add_column("Avg Fill")
            table.add_column("Unfilled")
            table.add_column("Action", overflow="fold")
            for row in board.get("items", []):
                table.add_row(str(row.get("simulation_id") or ""), str(row.get("state") or ""), str(row.get("market_id") or ""), str(row.get("side") or ""), str(row.get("estimated_average_fill_price") or ""), str(row.get("estimated_unfilled_size") or ""), str(row.get("recommended_action") or ""))
            console.print(table)
        return

    if args.execution_quality_detail:
        item = get_execution_quality_simulation(args.execution_quality_detail)
        if not item:
            console.print(f"[red]Execution-quality simulation not found:[/red] {args.execution_quality_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.preview_execution_quality or args.record_execution_quality:
        builder = record_execution_quality_simulation if args.record_execution_quality else build_execution_quality_simulation
        item = builder(side=args.side, token_id=args.token_id, market_id=args.market_id, snapshot_id=args.snapshot_id, price=args.price, size=args.size, order_type=args.order_type, time_in_force=args.time_in_force, max_spread_bps=args.max_spread_bps, max_slippage_bps=args.max_slippage_bps)
        console.print_json(data={"recorded": bool(args.record_execution_quality), "item": item})
        return

    if args.export_execution_quality:
        rows = list_execution_quality_simulations(limit=10000, state=args.execution_quality_state, market_id=args.market_id, token_id=args.token_id)
        out = Path(args.export_execution_quality)
        out.write_text(execution_quality_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported execution-quality CSV:[/green] {out}")
        return

    if args.live_config_readiness:
        report = build_live_config_readiness()
        if args.json:
            console.print_json(data=report)
        else:
            summary = report.get("summary", {})
            console.print_json(data={"summary": summary, "controls": report.get("controls", {})})
            table = Table(title="Live Configuration Readiness")
            table.add_column("Group")
            table.add_column("Field")
            table.add_column("Status")
            table.add_column("Value")
            table.add_column("Required For", overflow="fold")
            for row in report.get("fields", []):
                table.add_row(str(row.get("group") or ""), str(row.get("key") or ""), str(row.get("status") or ""), str(row.get("redacted_value") or ""), str(row.get("required_for") or ""))
            console.print(table)
        return

    if args.export_live_config_readiness:
        report = build_live_config_readiness()
        out = Path(args.export_live_config_readiness)
        out.write_text(live_config_readiness_to_csv(report), encoding="utf-8")
        console.print(f"[green]Exported live config readiness CSV:[/green] {out}")
        return

    if args.export_live_config_template:
        out = Path(args.export_live_config_template)
        out.write_text(live_config_template(), encoding="utf-8")
        console.print(f"[green]Exported live config env template:[/green] {out}")
        return

    if args.live_adapter_readiness:
        report = build_live_adapter_readiness()
        if args.json:
            console.print_json(data=report)
        else:
            console.print_json(data={"overall_status": report.get("overall_status"), "recommended_next_action": report.get("recommended_next_action")})
            table = Table(title="Live Adapter Readiness")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in [
                "configured_host",
                "configured_chain_id",
                "dependency_present",
                "live_mode_enabled",
                "read_only_network_validation_enabled",
                "order_submission_requested",
                "order_submission_enabled",
                "order_cancellation_requested",
                "order_cancellation_enabled",
                "manual_auth_required",
                "kill_switch_active",
                "dry_run_receipt_required",
            ]:
                table.add_row(key, str(report.get(key)))
            console.print(table)
        return

    if args.export_live_adapter_readiness:
        out = Path(args.export_live_adapter_readiness)
        out.write_text(live_adapter_readiness_to_csv(build_live_adapter_readiness()), encoding="utf-8")
        console.print(f"[green]Exported live adapter readiness CSV:[/green] {out}")
        return

    if args.preview_live_adapter_readonly_validation or args.record_live_adapter_readonly_validation:
        item = (record_live_adapter_readonly_validation if args.record_live_adapter_readonly_validation else preview_live_adapter_readonly_validation)(
            operator=args.live_adapter_operator or "local",
            note=args.live_adapter_note or args.live_intent_note or "",
        )
        console.print_json(data={"recorded": bool(args.record_live_adapter_readonly_validation), "item": item})
        return

    if args.live_adapter_readonly_validations:
        rows = list_live_adapter_readonly_validations(limit=args.limit, status=args.live_adapter_validation_status, operator=args.live_adapter_operator or None)
        data = {"mode": "live_adapter_readonly_validation_v060", "items": rows}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Live Adapter Read-Only Validations")
            table.add_column("Validation")
            table.add_column("Status")
            table.add_column("Network")
            table.add_column("Dependency")
            table.add_column("Action", overflow="fold")
            for row in rows:
                table.add_row(
                    str(row.get("validation_id") or ""),
                    str(row.get("status") or ""),
                    "attempted" if row.get("network_attempted") else "not attempted",
                    "present" if row.get("dependency_present") else "missing",
                    str(row.get("next_required_action") or ""),
                )
            console.print(table)
        return

    if args.live_adapter_validation_detail:
        item = get_live_adapter_readonly_validation(args.live_adapter_validation_detail)
        if not item:
            console.print(f"[red]Live adapter read-only validation not found:[/red] {args.live_adapter_validation_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.export_live_adapter_validations:
        rows = list_live_adapter_readonly_validations(limit=10000, status=args.live_adapter_validation_status, operator=args.live_adapter_operator or None)
        out = Path(args.export_live_adapter_validations)
        out.write_text(live_adapter_validations_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live adapter validations CSV:[/green] {out}")
        return

    if args.live_adapter_requests:
        board = build_live_adapter_request_board(
            limit=args.limit,
            status=args.live_adapter_request_status,
            market_id=args.live_intent_market,
            operator=args.live_adapter_operator or None,
            packet_id=args.live_adapter_request_packet_id,
            intent_id=args.live_execution_packet_intent_id,
        )
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Live Adapter Request Validations")
            table.add_column("Request")
            table.add_column("Status")
            table.add_column("Packet")
            table.add_column("Market")
            table.add_column("Submit")
            table.add_column("Action", overflow="fold")
            for row in board.get("items", []):
                table.add_row(
                    str(row.get("request_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("packet_id") or ""),
                    str(row.get("market_id") or ""),
                    "enabled" if row.get("order_submission_enabled") else "disabled",
                    str(row.get("next_required_action") or ""),
                )
            console.print(table)
        return

    if args.live_adapter_request_detail:
        item = get_live_adapter_request(args.live_adapter_request_detail)
        if not item:
            packet = get_live_execution_packet(args.live_adapter_request_detail)
            item = build_live_adapter_request(packet_id=args.live_adapter_request_detail, operator=args.live_adapter_operator or "local") if packet else None
        if not item:
            console.print(f"[red]Live adapter request or packet not found:[/red] {args.live_adapter_request_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.preview_live_adapter_request or args.record_live_adapter_request:
        packet_id = args.live_adapter_request_packet_id or args.live_dry_run_packet_id or args.live_execution_packet_detail or ""
        item = (record_live_adapter_request if args.record_live_adapter_request else build_live_adapter_request)(
            packet_id=packet_id,
            operator=args.live_adapter_operator or args.live_intent_operator or "local",
            note=args.live_adapter_note or args.live_intent_note or "",
        )
        console.print_json(data={"recorded": bool(args.record_live_adapter_request), "item": item})
        return

    if args.export_live_adapter_requests:
        rows = list_live_adapter_requests(
            limit=10000,
            status=args.live_adapter_request_status,
            market_id=args.live_intent_market,
            operator=args.live_adapter_operator or None,
            packet_id=args.live_adapter_request_packet_id,
            intent_id=args.live_execution_packet_intent_id,
        )
        out = Path(args.export_live_adapter_requests)
        out.write_text(live_adapter_requests_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live adapter requests CSV:[/green] {out}")
        return

    if args.manual_execution_reviews:
        board = build_manual_execution_review_board(
            limit=args.limit,
            status=args.manual_execution_review_status,
            market_id=args.live_intent_market,
            operator=args.live_adapter_operator or None,
            packet_id=args.manual_execution_review_packet_id or args.live_adapter_request_packet_id,
        )
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Manual Execution Reviews")
            table.add_column("Review")
            table.add_column("Status")
            table.add_column("Packet")
            table.add_column("Acknowledged")
            table.add_column("Submitted")
            table.add_column("Action", overflow="fold")
            for row in board.get("items", []):
                table.add_row(
                    str(row.get("review_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("packet_id") or ""),
                    "yes" if row.get("final_confirmation_acknowledged") else "no",
                    "no" if row.get("not_submitted") else "unknown",
                    str(row.get("next_required_action") or ""),
                )
            console.print(table)
        return

    if args.manual_execution_review_detail:
        item = get_manual_execution_review(args.manual_execution_review_detail)
        if not item:
            console.print(f"[red]Manual execution review not found:[/red] {args.manual_execution_review_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.preview_manual_execution_review or args.record_manual_execution_review:
        packet_id = args.manual_execution_review_packet_id or args.live_adapter_request_packet_id or args.live_dry_run_packet_id or ""
        item = (record_manual_execution_review if args.record_manual_execution_review else build_manual_execution_review)(
            packet_id=packet_id,
            operator=args.live_adapter_operator or args.live_intent_operator or "local",
            note=args.live_adapter_note or args.live_intent_note or "",
            acknowledged=bool(args.manual_execution_ack),
        )
        console.print_json(data={"recorded": bool(args.record_manual_execution_review), "item": item})
        return

    if args.export_manual_execution_reviews:
        rows = list_manual_execution_reviews(
            limit=10000,
            status=args.manual_execution_review_status,
            market_id=args.live_intent_market,
            operator=args.live_adapter_operator or None,
            packet_id=args.manual_execution_review_packet_id or args.live_adapter_request_packet_id,
        )
        out = Path(args.export_manual_execution_reviews)
        out.write_text(manual_execution_reviews_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported manual execution reviews CSV:[/green] {out}")
        return


    if args.live_clob_adapter_status:
        report = build_clob_adapter_status()
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Live CLOB Adapter Boundary")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["overall_status", "real_submit_implemented", "real_cancel_implemented", "recommended_next_action"]:
                table.add_row(key, str(report.get(key)))
            table.add_row("dependency_status", str(report.get("dependency", {}).get("status")))
            console.print(table)
            if report.get("blockers"):
                console.print_json(data={"blockers": report.get("blockers")})
        return

    if args.export_live_clob_adapter_status:
        out = Path(args.export_live_clob_adapter_status)
        out.write_text(clob_adapter_status_to_csv(build_clob_adapter_status()), encoding="utf-8")
        console.print(f"[green]Exported live CLOB adapter status CSV:[/green] {out}")
        return

    if args.live_clob_adapter_verify or args.live_clob_adapter_verification_report:
        report = build_live_adapter_verification(run=bool(args.live_clob_adapter_verify), operator=args.operator or "local", request_readonly_network=bool(args.request_readonly_network), request_real_smoke=bool(args.request_real_smoke))
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Live CLOB Adapter Verification")
            table.add_column("Level")
            table.add_column("Status")
            table.add_column("Detail", overflow="fold")
            for row in report.get("levels", []):
                table.add_row(str(row.get("level")), str(row.get("status")), str(row.get("detail")))
            console.print(table)
            if report.get("blockers"):
                console.print_json(data={"blockers": report.get("blockers")})
        return

    if args.export_live_clob_adapter_verification:
        out = Path(args.export_live_clob_adapter_verification)
        out.write_text(live_adapter_verification_to_csv(build_live_adapter_verification()), encoding="utf-8")
        console.print(f"[green]Exported live CLOB adapter verification CSV:[/green] {out}")
        return

    if args.live_trading_status:
        report = build_live_trading_status()
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Live Trading Status")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["overall_status", "real_live_submit_implemented", "real_live_cancel_implemented", "autonomous_live_mode_implemented", "recommended_next_action"]:
                table.add_row(key, str(report.get(key)))
            console.print(table)
            if report.get("blockers"):
                console.print_json(data={"blockers": report.get("blockers")})
        return

    if args.live_readiness_checklist:
        report = build_live_readiness_checklist()
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Live Readiness Checklist")
            table.add_column("Area")
            table.add_column("Requirement")
            table.add_column("Status")
            table.add_column("Remediation", overflow="fold")
            for row in report.get("rows", []):
                table.add_row(str(row.get("area")), str(row.get("requirement")), str(row.get("status")), str(row.get("remediation_hint")))
            console.print(table)
        return

    if args.export_live_readiness_checklist:
        out = Path(args.export_live_readiness_checklist)
        out.write_text(live_readiness_checklist_to_csv(build_live_readiness_checklist()), encoding="utf-8")
        console.print(f"[green]Exported live readiness checklist CSV:[/green] {out}")
        return

    if args.operator_runbook:
        report = build_operator_runbook()
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Operator Runbook")
            table.add_column("Step")
            table.add_column("Title")
            table.add_column("Instruction", overflow="fold")
            for row in report.get("steps", []):
                table.add_row(str(row.get("step")), str(row.get("title")), str(row.get("instruction")))
            console.print(table)
        return

    if args.live_orders:
        board = build_live_order_board(limit=args.limit, status=args.live_execution_attempt_status)
        if args.json:
            console.print_json(data=board)
        else:
            table = Table(title="Live Order Ledger")
            table.add_column("Event")
            table.add_column("Type")
            table.add_column("Status")
            table.add_column("Market")
            table.add_column("Network")
            for row in board.get("items", []):
                table.add_row(str(row.get("order_event_id")), str(row.get("event_type")), str(row.get("adapter_status")), str(row.get("market_id")), str(row.get("network_attempted")))
            console.print(table)
        return

    if args.live_order_detail:
        item = get_live_order_event(args.live_order_detail)
        if not item:
            console.print(f"[red]Live order event not found:[/red] {args.live_order_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.export_live_orders:
        out = Path(args.export_live_orders)
        out.write_text(live_orders_to_csv(list_live_order_events(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported live order ledger CSV:[/green] {out}")
        return

    if args.preview_live_submit or args.record_live_submit:
        item = (record_manual_submit_attempt if args.record_live_submit else build_manual_submit_preview)(
            adapter_request_id=args.adapter_request_id or args.live_adapter_request_detail or "",
            operator=args.operator or args.live_adapter_operator or args.live_intent_operator or "local",
            final_confirmation=args.final_confirmation or "",
            adapter_mode=args.adapter_mode or "blocked",
            note=args.live_adapter_note or args.live_intent_note or args.note or "",
        )
        console.print_json(data={"recorded": bool(args.record_live_submit), "item": item})
        return

    if args.preview_live_cancel or args.record_live_cancel:
        item = (record_manual_cancel_attempt if args.record_live_cancel else build_manual_cancel_preview)(
            original_attempt_id=args.original_attempt_id or args.live_execution_attempt_detail or "",
            fake_order_id=args.fake_order_id or args.order_id or "",
            operator=args.operator or args.live_adapter_operator or args.live_intent_operator or "local",
            final_confirmation=args.final_confirmation or "",
            adapter_mode=args.adapter_mode or "blocked",
            reason=args.cancel_reason or args.reason or "",
            note=args.live_adapter_note or args.live_intent_note or args.note or "",
        )
        console.print_json(data={"recorded": bool(args.record_live_cancel), "item": item})
        return

    if args.live_reconciliation or args.record_live_reconciliation:
        report = build_live_reconciliation()
        if args.json:
            console.print_json(data=report)
        else:
            console.print_json(data={"overall_status": report.get("overall_status"), "summary": report.get("summary", {}), "remote_network_attempted": report.get("remote_network_attempted")})
        return

    if args.export_live_reconciliation:
        out = Path(args.export_live_reconciliation)
        out.write_text(live_reconciliation_to_csv(build_live_reconciliation()), encoding="utf-8")
        console.print(f"[green]Exported live reconciliation CSV:[/green] {out}")
        return

    if args.strategy_signals:
        board = build_strategy_signal_board(limit=args.limit, status=args.live_execution_attempt_status)
        if args.json:
            console.print_json(data=board)
        else:
            table = Table(title="Strategy Signals")
            table.add_column("Signal")
            table.add_column("Strategy")
            table.add_column("Status")
            table.add_column("Market")
            table.add_column("Token")
            for row in board.get("items", []):
                table.add_row(str(row.get("signal_id")), str(row.get("strategy_id")), str(row.get("status")), str(row.get("market_id")), str(row.get("token_id")))
            console.print(table)
        return

    if args.strategy_signal_detail:
        item = get_strategy_signal(args.strategy_signal_detail)
        if not item:
            console.print(f"[red]Strategy signal not found:[/red] {args.strategy_signal_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.validate_strategy_signal or args.record_strategy_signal:
        payload = {"strategy_id": args.strategy_id, "market_id": args.market_id or args.live_intent_market or "", "token_id": args.token_id or args.live_intent_token_id or "", "side": args.side or args.live_intent_side or "BUY", "limit_price": args.price or args.live_intent_price, "size": args.size or args.live_intent_size, "confidence": args.confidence, "rationale": args.rationale, "expires_at": args.expires_at, "source": args.source, "adapter_request_id": args.adapter_request_id_for_signal}
        item = record_strategy_signal(**payload) if args.record_strategy_signal else validate_strategy_signal_payload(payload)
        console.print_json(data={"recorded": bool(args.record_strategy_signal), "item": item})
        return

    if args.export_strategy_signals:
        out = Path(args.export_strategy_signals)
        out.write_text(strategy_signals_to_csv(list_strategy_signals(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported strategy signals CSV:[/green] {out}")
        return

    if args.autonomous_trading_status:
        report = build_autonomous_status()
        console.print_json(data=report)
        return

    if args.preview_autonomous_run or args.record_autonomous_run:
        item = (record_autonomous_run if args.record_autonomous_run else build_autonomous_run_preview)(mode=args.mode, operator=args.operator or "local", limit=args.limit, strategy_id=args.strategy_id or None)
        console.print_json(data={"recorded": bool(args.record_autonomous_run), "run": item})
        return

    if args.autonomous_runs:
        rows = list_autonomous_runs(limit=args.limit, mode=args.mode if args.mode != "off" else None)
        if args.json:
            console.print_json(data={"items": rows})
        else:
            table = Table(title="Autonomous Runs")
            table.add_column("Run")
            table.add_column("Mode")
            table.add_column("Signals")
            table.add_column("Fake")
            table.add_column("Real")
            for row in rows:
                table.add_row(str(row.get("run_id")), str(row.get("mode")), str(row.get("signals_considered")), str(row.get("fake_orders_submitted")), str(row.get("real_orders_submitted")))
            console.print(table)
        return

    if args.autonomous_run_detail:
        item = get_autonomous_run(args.autonomous_run_detail)
        if not item:
            console.print(f"[red]Autonomous run not found:[/red] {args.autonomous_run_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.export_autonomous_runs:
        out = Path(args.export_autonomous_runs)
        out.write_text(autonomous_runs_to_csv(list_autonomous_runs(limit=10000)), encoding="utf-8")
        console.print(f"[green]Exported autonomous runs CSV:[/green] {out}")
        return

    if args.live_execution_control_readiness:
        report = build_live_execution_control_readiness()
        if args.json:
            console.print_json(data=report)
        else:
            console.print_json(data={"overall_status": report.get("overall_status"), "recommended_next_action": report.get("recommended_next_action")})
            table = Table(title="Live Execution Control Readiness")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in [
                "kill_switch_active",
                "submit_enabled",
                "cancel_enabled",
                "fake_adapter_enabled",
                "manual_auth_required",
                "network_mode",
                "real_submit_implemented",
                "real_cancel_implemented",
                "final_confirmation_phrase_configured",
                "ready_adapter_request_count",
            ]:
                table.add_row(key, str(report.get(key)))
            console.print(table)
        return

    if args.export_live_execution_control_readiness:
        out = Path(args.export_live_execution_control_readiness)
        out.write_text(live_execution_control_readiness_to_csv(build_live_execution_control_readiness()), encoding="utf-8")
        console.print(f"[green]Exported live execution control readiness CSV:[/green] {out}")
        return

    if args.live_execution_attempts:
        board = build_live_execution_attempt_board(
            limit=args.limit,
            status=args.live_execution_attempt_status,
            adapter_mode=args.live_execution_attempt_adapter_mode or args.adapter_mode or None,
            action=args.live_execution_attempt_action,
            market_id=args.live_intent_market,
            operator=args.operator or args.live_adapter_operator or None,
            adapter_request_id=args.adapter_request_id,
            packet_id=args.packet_id or args.live_adapter_request_packet_id,
            intent_id=args.intent_id or args.live_execution_packet_intent_id,
        )
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Live Execution Attempts")
            table.add_column("Attempt")
            table.add_column("Action")
            table.add_column("Status")
            table.add_column("Adapter")
            table.add_column("Request")
            table.add_column("Network")
            table.add_column("Action", overflow="fold")
            for row in board.get("items", []):
                table.add_row(
                    str(row.get("attempt_id") or ""),
                    str(row.get("action") or ""),
                    str(row.get("status") or ""),
                    str(row.get("adapter_mode") or ""),
                    str(row.get("adapter_request_id") or row.get("original_attempt_id") or ""),
                    "attempted" if row.get("real_network_attempted") else "no",
                    str(row.get("recommended_next_action") or ""),
                )
            console.print(table)
        return

    if args.live_execution_attempt_detail:
        item = get_live_execution_attempt(args.live_execution_attempt_detail)
        if not item:
            console.print(f"[red]Live execution attempt not found:[/red] {args.live_execution_attempt_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.preview_live_manual_submit or args.record_live_manual_submit:
        item = (record_manual_submit_attempt if args.record_live_manual_submit else build_manual_submit_preview)(
            adapter_request_id=args.adapter_request_id or args.live_adapter_request_detail or "",
            operator=args.operator or args.live_adapter_operator or args.live_intent_operator or "local",
            final_confirmation=args.final_confirmation or "",
            adapter_mode=args.adapter_mode or "blocked",
            note=args.live_adapter_note or args.live_intent_note or args.note or "",
        )
        console.print_json(data={"recorded": bool(args.record_live_manual_submit), "item": item})
        return

    if args.preview_live_manual_cancel or args.record_live_manual_cancel:
        item = (record_manual_cancel_attempt if args.record_live_manual_cancel else build_manual_cancel_preview)(
            original_attempt_id=args.original_attempt_id or args.live_execution_attempt_detail or "",
            fake_order_id=args.fake_order_id or args.order_id or "",
            operator=args.operator or args.live_adapter_operator or args.live_intent_operator or "local",
            final_confirmation=args.final_confirmation or "",
            adapter_mode=args.adapter_mode or "blocked",
            reason=args.cancel_reason or args.reason or "",
            note=args.live_adapter_note or args.live_intent_note or args.note or "",
        )
        console.print_json(data={"recorded": bool(args.record_live_manual_cancel), "item": item})
        return

    if args.export_live_execution_attempts:
        rows = list_live_execution_attempts(
            limit=10000,
            status=args.live_execution_attempt_status,
            adapter_mode=args.live_execution_attempt_adapter_mode or args.adapter_mode or None,
            action=args.live_execution_attempt_action,
            market_id=args.live_intent_market,
            operator=args.operator or args.live_adapter_operator or None,
            adapter_request_id=args.adapter_request_id,
            packet_id=args.packet_id or args.live_adapter_request_packet_id,
            intent_id=args.intent_id or args.live_execution_packet_intent_id,
        )
        out = Path(args.export_live_execution_attempts)
        out.write_text(live_execution_attempts_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live execution attempts CSV:[/green] {out}")
        return


    if args.live_order_intents:
        board = build_live_order_intent_board(limit=args.limit, status=args.live_intent_status, market_id=args.live_intent_market, operator=args.live_intent_operator)
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Live Order Intent Previews")
            table.add_column("ID")
            table.add_column("Status")
            table.add_column("Market")
            table.add_column("Side")
            table.add_column("Price")
            table.add_column("Size")
            table.add_column("Notional")
            table.add_column("Blockers", overflow="fold")
            for row in board.get("items", []):
                blockers = "; ".join(str(item) for item in (row.get("blockers") or [])[:2])
                table.add_row(
                    str(row.get("intent_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("market_id") or ""),
                    f"{row.get('side', '')} {row.get('outcome', '')}",
                    str(row.get("price") or ""),
                    str(row.get("size") or ""),
                    str(row.get("notional") or ""),
                    blockers,
                )
            console.print(table)
        return

    if args.live_order_intent_detail:
        item = get_live_order_intent(args.live_order_intent_detail)
        if not item:
            console.print(f"[red]Live order intent not found:[/red] {args.live_order_intent_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.live_order_intent_preflight:
        board = build_live_order_preflight_board(limit=args.limit, state=args.live_preflight_state, market_id=args.live_intent_market, operator=args.live_intent_operator)
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Live Order Intent Preflight")
            table.add_column("Intent")
            table.add_column("State")
            table.add_column("Market")
            table.add_column("Ticket")
            table.add_column("Approval")
            table.add_column("Notional")
            table.add_column("Blockers", overflow="fold")
            for row in board.get("items", []):
                blockers = "; ".join(str(item) for item in (row.get("blockers") or [])[:2])
                table.add_row(
                    str(row.get("intent_id") or ""),
                    str(row.get("state") or ""),
                    str(row.get("market_id") or ""),
                    str(row.get("source_ticket_id") or ""),
                    str(row.get("source_approval_id") or ""),
                    str(row.get("notional") or ""),
                    blockers,
                )
            console.print(table)
        return

    if args.live_order_intent_preflight_detail:
        item = review_live_order_intent(args.live_order_intent_preflight_detail)
        if not item:
            console.print(f"[red]Live order intent not found:[/red] {args.live_order_intent_preflight_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.export_live_order_intent_preflight:
        rows = list_live_order_preflights(limit=10000, state=args.live_preflight_state, market_id=args.live_intent_market, operator=args.live_intent_operator)
        out = Path(args.export_live_order_intent_preflight)
        out.write_text(live_order_preflights_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live order intent preflight CSV:[/green] {out}")
        return


    if args.live_order_authorizations:
        authorization_operator_filter = args.live_intent_operator if args.live_intent_operator and args.live_intent_operator != "local" else None
        board = build_live_order_authorization_board(
            limit=args.limit,
            status=args.live_authorization_status,
            decision=args.live_authorization_decision_filter,
            market_id=args.live_intent_market,
            operator=authorization_operator_filter,
            intent_id=args.live_authorization_intent_id,
        )
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Live Operator Authorization Ledger")
            table.add_column("Authorization")
            table.add_column("Status")
            table.add_column("Decision")
            table.add_column("Intent")
            table.add_column("Market")
            table.add_column("Notional")
            table.add_column("Action", overflow="fold")
            for row in board.get("items", []):
                table.add_row(
                    str(row.get("authorization_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("decision") or ""),
                    str(row.get("intent_id") or ""),
                    str(row.get("market_id") or ""),
                    str(row.get("notional") or ""),
                    str(row.get("next_required_action") or ""),
                )
            console.print(table)
        return

    if args.live_order_authorization_detail:
        item = get_live_order_authorization(args.live_order_authorization_detail)
        if not item:
            console.print(f"[red]Live order authorization not found:[/red] {args.live_order_authorization_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.record_live_order_authorization:
        item = record_live_order_authorization(
            intent_id=args.record_live_order_authorization,
            decision=args.live_authorization_decision,
            operator=args.live_intent_operator or "local",
            note=args.live_intent_note or "",
            acknowledged=bool(args.live_authorization_ack),
        )
        console.print_json(data={"recorded": True, "item": item})
        return

    if args.export_live_order_authorizations:
        authorization_operator_filter = args.live_intent_operator if args.live_intent_operator and args.live_intent_operator != "local" else None
        rows = list_live_order_authorizations(
            limit=10000,
            status=args.live_authorization_status,
            decision=args.live_authorization_decision_filter,
            market_id=args.live_intent_market,
            operator=authorization_operator_filter,
            intent_id=args.live_authorization_intent_id,
        )
        out = Path(args.export_live_order_authorizations)
        out.write_text(live_order_authorizations_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live order authorizations CSV:[/green] {out}")
        return

    if args.live_execution_packets:
        packet_operator_filter = args.live_intent_operator if args.live_intent_operator and args.live_intent_operator != "local" else None
        board = build_live_execution_packet_board(
            limit=args.limit,
            status=args.live_execution_packet_status,
            market_id=args.live_intent_market,
            operator=packet_operator_filter,
            intent_id=args.live_execution_packet_intent_id,
            authorization_id=args.live_execution_packet_authorization_id,
        )
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Live Execution Packets")
            table.add_column("Packet")
            table.add_column("Status")
            table.add_column("Intent")
            table.add_column("Authorization")
            table.add_column("Market")
            table.add_column("Notional")
            table.add_column("Action", overflow="fold")
            for row in board.get("items", []):
                table.add_row(
                    str(row.get("packet_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("intent_id") or ""),
                    str(row.get("authorization_id") or ""),
                    str(row.get("market_id") or ""),
                    str(row.get("notional") or ""),
                    str(row.get("next_required_action") or ""),
                )
            console.print(table)
        return

    if args.live_execution_packet_detail:
        item = get_live_execution_packet(args.live_execution_packet_detail)
        if not item:
            console.print(f"[red]Live execution packet not found:[/red] {args.live_execution_packet_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.preview_live_execution_packet or args.record_live_execution_packet:
        item = (record_live_execution_packet if args.record_live_execution_packet else build_live_execution_packet)(
            intent_id=args.live_execution_packet_intent_id or args.live_authorization_intent_id or "",
            authorization_id=args.live_execution_packet_authorization_id or None,
            operator=args.live_intent_operator or "local",
            note=args.live_intent_note or "",
        )
        console.print_json(data={"recorded": bool(args.record_live_execution_packet), "item": item})
        return

    if args.export_live_execution_packets:
        packet_operator_filter = args.live_intent_operator if args.live_intent_operator and args.live_intent_operator != "local" else None
        rows = list_live_execution_packets(
            limit=10000,
            status=args.live_execution_packet_status,
            market_id=args.live_intent_market,
            operator=packet_operator_filter,
            intent_id=args.live_execution_packet_intent_id,
            authorization_id=args.live_execution_packet_authorization_id,
        )
        out = Path(args.export_live_execution_packets)
        out.write_text(live_execution_packets_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live execution packets CSV:[/green] {out}")
        return

    if args.live_dry_run_adapter:
        dry_operator_filter = args.live_intent_operator if args.live_intent_operator and args.live_intent_operator != "local" else None
        board = build_live_dry_run_board(
            limit=args.limit,
            status=args.live_dry_run_status,
            market_id=args.live_intent_market,
            operator=dry_operator_filter,
            packet_id=args.live_dry_run_packet_id or args.live_execution_packet_detail or "",
            intent_id=args.live_execution_packet_intent_id,
        )
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Live Dry-Run Adapter Receipts")
            table.add_column("Receipt")
            table.add_column("Status")
            table.add_column("Packet")
            table.add_column("Intent")
            table.add_column("Market")
            table.add_column("Network")
            table.add_column("Action", overflow="fold")
            for row in board.get("items", []):
                table.add_row(
                    str(row.get("receipt_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("packet_id") or ""),
                    str(row.get("intent_id") or ""),
                    str(row.get("market_id") or ""),
                    "attempted" if row.get("network_attempted") else "offline",
                    str(row.get("next_required_action") or ""),
                )
            console.print(table)
        return

    if args.live_dry_run_receipt_detail:
        item = get_live_dry_run_receipt(args.live_dry_run_receipt_detail)
        if not item:
            console.print(f"[red]Live dry-run adapter receipt not found:[/red] {args.live_dry_run_receipt_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.preview_live_dry_run_adapter or args.record_live_dry_run_adapter:
        packet_id = args.live_dry_run_packet_id or args.live_execution_packet_detail or ""
        item = (record_live_dry_run_receipt if args.record_live_dry_run_adapter else build_live_dry_run_receipt)(
            packet_id=packet_id,
            operator=args.live_intent_operator or "local",
            note=args.live_intent_note or "",
        )
        console.print_json(data={"recorded": bool(args.record_live_dry_run_adapter), "item": item})
        return

    if args.export_live_dry_run_adapter:
        dry_operator_filter = args.live_intent_operator if args.live_intent_operator and args.live_intent_operator != "local" else None
        rows = list_live_dry_run_receipts(
            limit=10000,
            status=args.live_dry_run_status,
            market_id=args.live_intent_market,
            operator=dry_operator_filter,
            packet_id=args.live_dry_run_packet_id,
            intent_id=args.live_execution_packet_intent_id,
        )
        out = Path(args.export_live_dry_run_adapter)
        out.write_text(live_dry_run_receipts_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live dry-run adapter receipts CSV:[/green] {out}")
        return

    if args.live_dry_run_review:
        review_operator_filter = args.live_intent_operator if args.live_intent_operator and args.live_intent_operator != "local" else None
        board = build_live_dry_run_review_board(
            limit=args.limit,
            state=args.live_dry_run_review_state,
            market_id=args.live_intent_market,
            operator=review_operator_filter,
            packet_id=args.live_dry_run_packet_id,
            intent_id=args.live_execution_packet_intent_id,
        )
        if args.json:
            console.print_json(data=board)
        else:
            console.print_json(data={"summary": board.get("summary", {}), "guardrail": board.get("guardrail", "")})
            table = Table(title="Live Dry-Run Review Board")
            table.add_column("Packet")
            table.add_column("State")
            table.add_column("Receipt")
            table.add_column("Intent")
            table.add_column("Market")
            table.add_column("Action", overflow="fold")
            for row in board.get("items", []):
                table.add_row(
                    str(row.get("packet_id") or ""),
                    str(row.get("state") or ""),
                    str(row.get("latest_receipt_id") or "missing"),
                    str(row.get("intent_id") or ""),
                    str(row.get("market_id") or ""),
                    str(row.get("next_required_action") or ""),
                )
            console.print(table)
        return

    if args.live_dry_run_review_detail:
        item = review_live_dry_run_packet(args.live_dry_run_review_detail)
        if not item:
            console.print(f"[red]Live dry-run review packet not found:[/red] {args.live_dry_run_review_detail}")
            return
        console.print_json(data={"item": item})
        return

    if args.export_live_dry_run_review:
        review_operator_filter = args.live_intent_operator if args.live_intent_operator and args.live_intent_operator != "local" else None
        rows = list_live_dry_run_reviews(
            limit=10000,
            state=args.live_dry_run_review_state,
            market_id=args.live_intent_market,
            operator=review_operator_filter,
            packet_id=args.live_dry_run_packet_id,
            intent_id=args.live_execution_packet_intent_id,
        )
        out = Path(args.export_live_dry_run_review)
        out.write_text(live_dry_run_reviews_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live dry-run review CSV:[/green] {out}")
        return

    if args.preview_live_order_intent or args.record_live_order_intent:
        kwargs = {
            "market_id": args.live_intent_market or "",
            "token_id": args.live_intent_token_id or "",
            "outcome": args.live_intent_outcome,
            "side": args.live_intent_side,
            "order_type": args.live_intent_order_type,
            "time_in_force": args.live_intent_time_in_force,
            "price": args.live_intent_price,
            "size": args.live_intent_size,
            "operator": args.live_intent_operator or "local",
            "note": args.live_intent_note or "",
            "source_ticket_id": args.live_intent_source_ticket_id or "",
            "source_approval_id": args.live_intent_source_approval_id or "",
        }
        item = record_live_order_intent(**kwargs) if args.record_live_order_intent else build_live_order_intent(**kwargs)
        console.print_json(data={"recorded": bool(args.record_live_order_intent), "item": item})
        return

    if args.export_live_order_intents:
        rows = list_live_order_intents(limit=10000, status=args.live_intent_status, market_id=args.live_intent_market, operator=args.live_intent_operator)
        out = Path(args.export_live_order_intents)
        out.write_text(live_order_intents_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported live order intents CSV:[/green] {out}")
        return

    if args.playbooks:
        rows = list_playbooks(active_only=args.active_playbooks)
        data = {"summary": summarize_playbooks(rows), "items": rows}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Strategy Playbooks")
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Status")
            table.add_column("Action")
            table.add_column("Gates", overflow="fold")
            for row in rows:
                gates = ", ".join(f"{k}={v}" for k, v in (row.get("gates") or {}).items())
                table.add_row(str(row.get("playbook_id")), str(row.get("name")), str(row.get("status")), str(row.get("recommended_action")), gates)
            console.print(table)
            console.print_json(data={"summary": data["summary"]})
        return

    if args.playbook_board:
        markets = attach_evidence_probability(attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr"))))
        opportunities = rank_opportunities(markets, watchlist=load_watchlist(), max_items=args.limit)
        readiness_by_market = {str(o.get("market_id") or o.get("id") or ""): build_readiness_result(o) for o in opportunities}
        board = build_playbook_board(opportunities, readiness_by_market=readiness_by_market, playbook_id=args.playbook_id, limit=args.limit)
        if args.json:
            console.print_json(data=board)
        else:
            table = Table(title="Strategy Playbook Board")
            table.add_column("#", justify="right")
            table.add_column("Fit", justify="right")
            table.add_column("Playbook")
            table.add_column("Action")
            table.add_column("Market", overflow="fold")
            table.add_column("Blockers", overflow="fold")
            for i, row in enumerate(board.get("items", []), 1):
                table.add_row(
                    str(i),
                    f"{float(row.get('fit_score') or 0) * 100:.1f}%",
                    str(row.get("best_playbook_name") or ""),
                    str(row.get("recommended_action") or ""),
                    str(row.get("title") or row.get("market_id") or ""),
                    "; ".join(str(x) for x in (row.get("blockers") or [])[:3]),
                )
            console.print(table)
            console.print_json(data={"summary": board.get("summary", {})})
        return

    if args.playbook_fit:
        market = await client.get_market(args.playbook_fit)
        if market:
            markets = attach_evidence_probability(attach_probability(attach_scores([market])))
            opportunities = rank_opportunities(markets, watchlist=load_watchlist(), max_items=1)
            opportunity = opportunities[0] if opportunities else markets[0]
        else:
            opportunity = {"id": args.playbook_fit, "market_id": args.playbook_fit, "title": args.playbook_fit}
        readiness = build_readiness_result(opportunity)
        data = evaluate_market_playbooks(opportunity, readiness=readiness, playbook_id=args.playbook_id)
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title=f"Market Playbook Fit: {args.playbook_fit}")
            table.add_column("Playbook")
            table.add_column("Matched")
            table.add_column("Fit", justify="right")
            table.add_column("Action")
            table.add_column("Blockers", overflow="fold")
            for row in data.get("items", []):
                table.add_row(
                    str(row.get("playbook_name")),
                    "yes" if row.get("matched") else "no",
                    f"{float(row.get('fit_score') or 0) * 100:.1f}%",
                    str(row.get("recommended_action") or ""),
                    "; ".join(str(x) for x in (row.get("blockers") or [])[:4]),
                )
            console.print(table)
            if data.get("best_fit"):
                console.print_json(data={"best_fit": data.get("best_fit")})
        return

    if args.playbook_decisions:
        rows = list_playbook_decisions(limit=args.limit, market_id=args.playbook_market, playbook_id=args.playbook_id)
        data = {"summary": summarize_playbook_decisions(rows), "items": rows}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Strategy Playbook Decisions")
            table.add_column("#", justify="right")
            table.add_column("Time")
            table.add_column("Status")
            table.add_column("Playbook")
            table.add_column("Market")
            table.add_column("Note", overflow="fold")
            for i, row in enumerate(rows, 1):
                table.add_row(str(i), str(row.get("created_at") or ""), str(row.get("status") or ""), str(row.get("playbook_name") or row.get("playbook_id") or ""), str(row.get("market_id") or ""), str(row.get("note") or ""))
            console.print(table)
            console.print_json(data={"summary": data["summary"]})
        return

    if args.playbook_performance:
        report = build_playbook_performance(limit=args.limit, playbook_id=args.playbook_id, status=args.decision_status_filter)
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Playbook Performance Review")
            table.add_column("Playbook")
            table.add_column("Decisions", justify="right")
            table.add_column("Markets", justify="right")
            table.add_column("Lifecycle", justify="right")
            table.add_column("Win %", justify="right")
            table.add_column("Net P&L", justify="right")
            table.add_column("Warnings", justify="right")
            for row in report.get("items", []):
                table.add_row(
                    str(row.get("playbook_name") or row.get("playbook_id") or ""),
                    str(row.get("decision_count") or 0),
                    str(row.get("unique_market_count") or 0),
                    str(row.get("paper_lifecycle_market_count") or 0),
                    f"{float(row.get('win_rate_percent') or 0):.1f}%",
                    signed_money(row.get("net_pnl")),
                    str(row.get("warning_count") or 0),
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.playbook_performance_detail:
        data = build_playbook_performance_detail(args.playbook_performance_detail)
        if args.json:
            console.print_json(data=data)
        else:
            item = data.get("item") or {}
            table = Table(title=f"Playbook Performance Detail: {args.playbook_performance_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            table.add_row("Playbook", str(item.get("playbook_name") or args.playbook_performance_detail))
            table.add_row("Decisions", str(item.get("decision_count") or 0))
            table.add_row("Markets", str(item.get("unique_market_count") or 0))
            table.add_row("Paper lifecycle markets", str(item.get("paper_lifecycle_market_count") or 0))
            table.add_row("Realized P&L", signed_money(item.get("realized_pnl")))
            table.add_row("Unrealized P&L", signed_money(item.get("unrealized_pnl")))
            table.add_row("Net P&L", signed_money(item.get("net_pnl")))
            table.add_row("Warnings", str(item.get("warning_count") or 0))
            table.add_row("Flag counts", str(item.get("flag_counts") or {}))
            console.print(table)
        return

    if args.export_playbook_performance:
        report = build_playbook_performance(limit=10000, playbook_id=args.playbook_id, status=args.decision_status_filter)
        out = Path(args.export_playbook_performance)
        out.write_text(playbook_performance_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported playbook performance CSV:[/green] {out}")
        return

    if args.risk_budget:
        try:
            markets = attach_probability(attach_scores(await client.list_markets(limit=min(max(args.limit, 50), 200), order="volume24hr")))
        except Exception:
            markets = []
        report = build_risk_budget(markets, limit=args.limit, market_id=args.risk_budget_market)
        if args.json:
            console.print_json(data=report)
        else:
            summary = report.get("summary", {})
            table = Table(title="Paper Risk Budget Review")
            table.add_column("Market", overflow="fold")
            table.add_column("State")
            table.add_column("Open", justify="right")
            table.add_column("Pending", justify="right")
            table.add_column("Combined", justify="right")
            table.add_column("Usage", justify="right")
            table.add_column("Warnings", justify="right")
            for row in report.get("items", []):
                table.add_row(
                    str(row.get("question") or row.get("market_id") or ""),
                    str(row.get("budget_state") or ""),
                    money(row.get("open_cost_basis")),
                    money(row.get("pending_ticket_stake")),
                    money(row.get("combined_open_and_pending")),
                    f"{float(row.get('combined_market_utilization_percent') or 0):.1f}%",
                    str(row.get("warning_count") or 0),
                )
            console.print(table)
            console.print_json(data={"summary": summary, "flags": report.get("flags", [])[:10]})
        return

    if args.risk_budget_detail:
        try:
            markets = attach_probability(attach_scores(await client.list_markets(limit=200, order="volume24hr")))
        except Exception:
            markets = []
        data = build_market_risk_budget(args.risk_budget_detail, markets)
        if args.json:
            console.print_json(data=data)
        else:
            item = data.get("item") or {}
            table = Table(title=f"Paper Risk Budget Detail: {args.risk_budget_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            table.add_row("Question", str(item.get("question") or args.risk_budget_detail))
            table.add_row("State", str(item.get("budget_state") or "no local exposure"))
            table.add_row("Open exposure", money(item.get("open_cost_basis", data.get("market_open_exposure", 0))))
            table.add_row("Pending tickets", money(item.get("pending_ticket_stake", 0)))
            table.add_row("Combined usage", f"{float(item.get('combined_market_utilization_percent') or 0):.1f}%")
            table.add_row("Room after pending", money(item.get("market_exposure_remaining_after_pending", data.get("market_exposure_remaining", 0))))
            table.add_row("Warnings", str(item.get("warning_count") or 0))
            console.print(table)
        return

    if args.export_risk_budget:
        try:
            markets = attach_probability(attach_scores(await client.list_markets(limit=200, order="volume24hr")))
        except Exception:
            markets = []
        report = build_risk_budget(markets, limit=10000, market_id=args.risk_budget_market)
        out = Path(args.export_risk_budget)
        out.write_text(risk_budget_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper risk budget CSV:[/green] {out}")
        return

    if args.preflight:
        report = build_preflight_board(limit=args.limit, status=args.preflight_status, strict_playbook=args.strict_playbook_preflight)
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Entry Preflight Gate")
            table.add_column("Ticket")
            table.add_column("Status")
            table.add_column("Market", overflow="fold")
            table.add_column("Stake", justify="right")
            table.add_column("Blockers", justify="right")
            table.add_column("Warnings", justify="right")
            for row in report.get("items", []):
                table.add_row(
                    str(row.get("ticket_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("title") or row.get("market_id") or ""),
                    money(row.get("stake")),
                    str(row.get("blocker_count") or 0),
                    str(row.get("warning_count") or 0),
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.preflight_ticket:
        try:
            data = build_ticket_preflight(args.preflight_ticket, strict_playbook=args.strict_playbook_preflight)
        except ValueError as exc:
            if args.json:
                console.print_json(data={"ok": False, "error": str(exc), "ticket_id": args.preflight_ticket})
            else:
                console.print(f"[red]{exc}:[/red] {args.preflight_ticket}")
            return
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title=f"Paper Preflight: {args.preflight_ticket}")
            table.add_column("Check")
            table.add_column("Result")
            table.add_column("Severity")
            table.add_column("Detail", overflow="fold")
            for row in data.get("checks", []):
                table.add_row(str(row.get("name") or ""), "pass" if row.get("passed") else "fail", str(row.get("severity") or ""), str(row.get("detail") or ""))
            console.print(table)
            console.print_json(data={"status": data.get("status"), "approved": data.get("approved"), "blocker_count": data.get("blocker_count"), "warning_count": data.get("warning_count")})
        return

    if args.export_preflight:
        report = build_preflight_board(limit=10000, status=args.preflight_status, strict_playbook=args.strict_playbook_preflight)
        out = Path(args.export_preflight)
        out.write_text(preflight_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper preflight CSV:[/green] {out}")
        return

    if args.approvals:
        report = build_execution_approval_board(limit=args.limit, status=args.approval_status_filter, market_id=args.approval_market, ticket_id=args.approval_ticket)
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Execution Approvals")
            table.add_column("#", justify="right")
            table.add_column("Status")
            table.add_column("Ticket")
            table.add_column("Market", overflow="fold")
            table.add_column("Stake", justify="right")
            table.add_column("Preflight")
            table.add_column("Issues", overflow="fold")
            for i, row in enumerate(report.get("items", []), 1):
                issues = row.get("blocker_summary") or row.get("warning_summary") or row.get("note") or row.get("reason") or ""
                table.add_row(
                    str(i),
                    str(row.get("status") or ""),
                    str(row.get("ticket_id") or ""),
                    str(row.get("title") or row.get("market_id") or ""),
                    money(row.get("stake")),
                    str(row.get("preflight_status") or "n/a"),
                    str(issues),
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.approval_detail:
        item = get_execution_approval(args.approval_detail)
        if args.json:
            console.print_json(data={"item": item, "found": bool(item)})
        elif item:
            table = Table(title=f"Paper Approval Detail: {args.approval_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["approval_id", "created_at", "status", "operator", "source", "ticket_id", "market_id", "title", "stake", "price", "preflight_status", "blocker_summary", "warning_summary", "note", "reason", "paper_trade_id"]:
                table.add_row(key, str(item.get(key) if item.get(key) is not None else ""))
            console.print(table)
        else:
            console.print("[red]Paper approval record not found.[/red]")
        return

    if args.approve_ticket:
        try:
            item = approve_trade_ticket(args.approve_ticket, operator="cli", note=args.approval_note or args.note or args.reason, strict_playbook=args.strict_approval_preflight)
            if args.json:
                console.print_json(data=item)
            else:
                console.print(f"[green]Recorded paper approval:[/green] {item.get('approval_id')} status={item.get('status')} preflight={item.get('preflight_status')}")
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.reject_ticket:
        try:
            item = reject_trade_ticket(args.reject_ticket, operator="cli", note=args.approval_note or args.note or args.reason)
            if args.json:
                console.print_json(data=item)
            else:
                console.print(f"[yellow]Rejected paper ticket:[/yellow] {item.get('approval_id')} ticket={item.get('ticket_id')}")
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.export_approvals:
        report = build_execution_approval_board(limit=10000, status=args.approval_status_filter, market_id=args.approval_market, ticket_id=args.approval_ticket)
        out = Path(args.export_approvals)
        out.write_text(approvals_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper approvals CSV:[/green] {out}")
        return

    if args.execution_queue:
        report = build_execution_queue(limit=args.limit, status=args.execution_queue_status, market_id=args.execution_queue_market, ticket_id=args.execution_queue_ticket, strict_playbook=args.strict_execution_queue)
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Execution Queue")
            table.add_column("#", justify="right")
            table.add_column("Queue")
            table.add_column("Ticket")
            table.add_column("Market", overflow="fold")
            table.add_column("Stake", justify="right")
            table.add_column("Preflight")
            table.add_column("Approval")
            table.add_column("Action / Reason", overflow="fold")
            for i, row in enumerate(report.get("items", []), 1):
                approval = row.get("latest_approval_status") or "none"
                if row.get("latest_approval_id"):
                    approval = f"{approval} ({row.get('latest_approval_id')})"
                table.add_row(
                    str(i),
                    str(row.get("queue_status") or ""),
                    str(row.get("ticket_id") or ""),
                    str(row.get("title") or row.get("market_id") or ""),
                    money(row.get("stake")),
                    str(row.get("preflight_status") or "n/a"),
                    approval,
                    f"{row.get('recommended_action') or ''}: {row.get('reason_summary') or ''}",
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.execution_queue_detail:
        try:
            item = build_ticket_execution_queue_item(args.execution_queue_detail, strict_playbook=args.strict_execution_queue)
            if args.json:
                console.print_json(data={"item": item})
            else:
                table = Table(title=f"Paper Execution Queue Detail: {args.execution_queue_detail}")
                table.add_column("Field")
                table.add_column("Value", overflow="fold")
                for key in ["ticket_id", "market_id", "title", "queue_status", "recommended_action", "paper_buy_executable", "preflight_status", "latest_approval_id", "latest_approval_status", "stake", "price", "reason_summary"]:
                    table.add_row(key, str(item.get(key) if item.get(key) is not None else ""))
                console.print(table)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.export_execution_queue:
        report = build_execution_queue(limit=10000, status=args.execution_queue_status, market_id=args.execution_queue_market, ticket_id=args.execution_queue_ticket, strict_playbook=args.strict_execution_queue)
        out = Path(args.export_execution_queue)
        out.write_text(execution_queue_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper execution queue CSV:[/green] {out}")
        return

    if args.runbook:
        report = build_runbook(
            limit=args.limit,
            scope=args.runbook_scope,
            status=args.runbook_status,
            market_id=args.runbook_market,
            item_id=args.runbook_item,
            include_completed=args.include_completed_runbook,
        )
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Operator Runbook")
            table.add_column("#", justify="right")
            table.add_column("Status")
            table.add_column("Scope")
            table.add_column("Item")
            table.add_column("Market", overflow="fold")
            table.add_column("Priority", justify="right")
            table.add_column("Action / Detail", overflow="fold")
            for i, row in enumerate(report.get("items", []), 1):
                table.add_row(
                    str(i),
                    str(row.get("effective_status") or row.get("status") or ""),
                    str(row.get("scope") or ""),
                    str(row.get("item_id") or ""),
                    str(row.get("question") or row.get("market_id") or ""),
                    str(row.get("priority") or 0),
                    f"{row.get('recommended_action') or ''}: {row.get('detail') or ''}",
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.runbook_detail:
        item = get_runbook_item(args.runbook_detail, include_completed=True)
        if args.json:
            console.print_json(data={"item": item, "found": bool(item)})
        elif item:
            table = Table(title=f"Paper Runbook Detail: {args.runbook_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["item_id", "scope", "effective_status", "status", "priority", "market_id", "ticket_id", "title", "recommended_action", "detail", "acknowledgement_status", "acknowledgement_note"]:
                table.add_row(key, str(item.get(key) if item.get(key) is not None else ""))
            console.print(table)
            if item.get("checklist"):
                checklist = Table(title="Checklist")
                checklist.add_column("Step")
                checklist.add_column("Required")
                checklist.add_column("State", overflow="fold")
                for row in item.get("checklist") or []:
                    checklist.add_row(str(row.get("step") or ""), "yes" if row.get("required", True) else "no", str(row.get("state") or ""))
                console.print(checklist)
        else:
            console.print("[red]Runbook item not found.[/red]")
        return

    if args.ack_runbook_item:
        item = get_runbook_item(args.ack_runbook_item, include_completed=True)
        if not item:
            if args.json:
                console.print_json(data={"ok": False, "error": "Runbook item not found", "item_id": args.ack_runbook_item})
            else:
                console.print("[red]Runbook item not found.[/red]")
            return
        record = record_runbook_acknowledgement(args.ack_runbook_item, status=args.runbook_ack_status, note=args.note or args.reason, operator="cli", item_snapshot=item)
        if args.json:
            console.print_json(data=record)
        else:
            console.print(f"[green]Recorded runbook acknowledgement:[/green] {record.get('ack_id')} item={record.get('item_id')} status={record.get('status')}")
        return

    if args.export_runbook:
        report = build_runbook(
            limit=10000,
            scope=args.runbook_scope,
            status=args.runbook_status,
            market_id=args.runbook_market,
            item_id=args.runbook_item,
            include_completed=args.include_completed_runbook,
        )
        out = Path(args.export_runbook)
        out.write_text(runbook_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper operator runbook CSV:[/green] {out}")
        return

    if args.paper_ops_briefing:
        report = build_paper_ops_briefing(limit=args.limit, section=args.briefing_section, status=args.briefing_status, market_id=args.briefing_market)
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Daily Paper Ops Briefing")
            table.add_column("#", justify="right")
            table.add_column("Status")
            table.add_column("Section")
            table.add_column("Priority", justify="right")
            table.add_column("Item", overflow="fold")
            table.add_column("Market", overflow="fold")
            table.add_column("Action / Detail", overflow="fold")
            for i, row in enumerate(report.get("items", []), 1):
                table.add_row(
                    str(i),
                    str(row.get("status") or ""),
                    str(row.get("section") or ""),
                    str(row.get("priority") or 0),
                    str(row.get("title") or row.get("briefing_item_id") or ""),
                    str(row.get("question") or row.get("market_id") or "portfolio/system"),
                    f"{row.get('recommended_action') or ''}: {row.get('detail') or ''}",
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {}), "recent_checkpoints": report.get("recent_checkpoints", [])[:3]})
        return

    if args.briefing_checkpoints:
        rows = list_briefing_checkpoints(limit=args.limit, status=args.briefing_checkpoint_status)
        if args.json:
            console.print_json(data={"items": rows})
        else:
            table = Table(title="Paper Ops Briefing Checkpoints")
            table.add_column("Time")
            table.add_column("Status")
            table.add_column("Section")
            table.add_column("Items", justify="right")
            table.add_column("Blocked", justify="right")
            table.add_column("Action Required", justify="right")
            table.add_column("Note", overflow="fold")
            for row in rows:
                table.add_row(
                    str(row.get("created_at") or ""),
                    str(row.get("status") or ""),
                    str(row.get("section") or ""),
                    str(row.get("item_count_snapshot") or 0),
                    str(row.get("blocked_snapshot") or 0),
                    str(row.get("action_required_snapshot") or 0),
                    str(row.get("note") or ""),
                )
            console.print(table)
        return

    if args.record_briefing_checkpoint:
        snapshot = build_paper_ops_briefing(limit=100, section=args.briefing_section, status=args.briefing_status, market_id=args.briefing_market)
        record = record_briefing_checkpoint(status=args.briefing_checkpoint_status, note=args.note or args.reason, section=args.briefing_section, operator="cli", briefing_snapshot=snapshot)
        if args.json:
            console.print_json(data=record)
        else:
            console.print(f"[green]Recorded paper ops briefing checkpoint:[/green] {record.get('checkpoint_id')} status={record.get('status')}")
        return

    if args.export_briefing:
        report = build_paper_ops_briefing(limit=10000, section=args.briefing_section, status=args.briefing_status, market_id=args.briefing_market)
        out = Path(args.export_briefing)
        out.write_text(briefing_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper ops briefing CSV:[/green] {out}")
        return

    if args.paper_handoffs:
        report = build_operator_handoff_board(
            limit=args.limit,
            section=args.handoff_section,
            item_status=args.handoff_item_status,
            market_id=args.handoff_market,
            handoff_status=args.handoff_status_filter,
        )
        if args.json:
            console.print_json(data=report)
        else:
            current = report.get("current", {})
            table = Table(title="Paper Operator Handoff Preview")
            table.add_column("#", justify="right")
            table.add_column("Status")
            table.add_column("Section")
            table.add_column("Priority", justify="right")
            table.add_column("Item", overflow="fold")
            table.add_column("Action / Detail", overflow="fold")
            for i, row in enumerate(current.get("handoff_items", []), 1):
                table.add_row(
                    str(i),
                    str(row.get("status") or ""),
                    str(row.get("section") or ""),
                    str(row.get("priority") or 0),
                    str(row.get("title") or row.get("briefing_item_id") or ""),
                    f"{row.get('recommended_action') or ''}: {row.get('detail') or ''}",
                )
            console.print(table)
            saved = Table(title="Saved Paper Operator Handoffs")
            saved.add_column("Time")
            saved.add_column("Status")
            saved.add_column("Handoff")
            saved.add_column("Unresolved", justify="right")
            saved.add_column("Blocked", justify="right")
            saved.add_column("Action Required", justify="right")
            saved.add_column("Note", overflow="fold")
            for row in report.get("items", []):
                saved.add_row(
                    str(row.get("created_at") or ""),
                    str(row.get("status") or ""),
                    str(row.get("handoff_id") or ""),
                    str(row.get("unresolved_count_snapshot") or 0),
                    str(row.get("blocked_snapshot") or 0),
                    str(row.get("action_required_snapshot") or 0),
                    str(row.get("note") or ""),
                )
            console.print(saved)
            console.print_json(data={"summary": report.get("summary", {}), "focus": current.get("next_operator_focus", [])})
        return

    if args.handoff_detail:
        item = get_operator_handoff(args.handoff_detail)
        if args.json:
            console.print_json(data={"item": item, "found": bool(item)})
        elif item:
            table = Table(title=f"Paper Handoff Detail: {args.handoff_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["handoff_id", "created_at", "status", "outgoing_operator", "incoming_operator", "unresolved_count_snapshot", "blocked_snapshot", "action_required_snapshot", "ready_snapshot", "top_priority_snapshot", "note"]:
                table.add_row(key, str(item.get(key) if item.get(key) is not None else ""))
            console.print(table)
            if item.get("handoff_items"):
                items = Table(title="Handoff Items")
                items.add_column("Priority", justify="right")
                items.add_column("Status")
                items.add_column("Section")
                items.add_column("Item", overflow="fold")
                items.add_column("Action", overflow="fold")
                for row in item.get("handoff_items") or []:
                    items.add_row(str(row.get("priority") or 0), str(row.get("status") or ""), str(row.get("section") or ""), str(row.get("title") or ""), str(row.get("recommended_action") or ""))
                console.print(items)
        else:
            console.print("[red]Paper handoff record not found.[/red]")
        return

    if args.record_handoff:
        record = record_operator_handoff(
            status=args.handoff_status,
            outgoing_operator=args.handoff_outgoing or "cli",
            incoming_operator=args.handoff_incoming,
            note=args.note or args.reason,
            limit=args.limit,
            section=args.handoff_section,
            item_status=args.handoff_item_status,
            market_id=args.handoff_market,
        )
        if args.json:
            console.print_json(data=record)
        else:
            console.print(f"[green]Recorded paper operator handoff:[/green] {record.get('handoff_id')} status={record.get('status')} unresolved={record.get('unresolved_count_snapshot')}")
        return

    if args.export_handoffs:
        rows = list_operator_handoffs(limit=10000, status=args.handoff_status_filter, market_id=args.handoff_market)
        out = Path(args.export_handoffs)
        out.write_text(handoffs_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported paper operator handoffs CSV:[/green] {out}")
        return


    if args.paper_ops_closeout:
        report = build_paper_ops_closeout(
            limit=args.limit,
            source=args.ops_closeout_source,
            status=args.ops_closeout_status,
            market_id=args.ops_closeout_market,
            handoff_required=True if args.ops_closeout_handoff_required else None,
        )
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Ops Closeout")
            table.add_column("Priority", justify="right")
            table.add_column("Source")
            table.add_column("Status")
            table.add_column("Severity")
            table.add_column("Handoff")
            table.add_column("Item", overflow="fold")
            table.add_column("Action", overflow="fold")
            for row in report.get("items", []):
                table.add_row(
                    str(row.get("priority") or 0),
                    str(row.get("source") or ""),
                    str(row.get("status") or ""),
                    str(row.get("severity") or ""),
                    "yes" if row.get("handoff_required") else "no",
                    str(row.get("title") or row.get("source_id") or ""),
                    str(row.get("recommended_action") or ""),
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.export_ops_closeout:
        report = build_paper_ops_closeout(
            limit=10000,
            source=args.ops_closeout_source,
            status=args.ops_closeout_status,
            market_id=args.ops_closeout_market,
            handoff_required=True if args.ops_closeout_handoff_required else None,
        )
        out = Path(args.export_ops_closeout)
        out.write_text(paper_ops_closeout_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper ops closeout CSV:[/green] {out}")
        return


    if args.paper_ops_closeout_signoffs:
        report = build_ops_closeout_signoff_board(
            limit=args.limit,
            status=args.ops_closeout_signoff_status_filter,
            operator=args.ops_closeout_signoff_operator,
            market_id=args.ops_closeout_market,
        )
        if args.json:
            console.print_json(data=report)
        else:
            current = report.get("current_closeout_summary", {})
            console.print_json(data={"summary": report.get("summary", {}), "current_closeout_summary": current})
            table = Table(title="Paper Ops Closeout Signoffs")
            table.add_column("Time")
            table.add_column("Status")
            table.add_column("Operator")
            table.add_column("Closeout")
            table.add_column("Rows", justify="right")
            table.add_column("Handoff", justify="right")
            table.add_column("Note / Gate", overflow="fold")
            for row in report.get("items", []):
                table.add_row(
                    str(row.get("created_at") or ""),
                    str(row.get("status") or ""),
                    str(row.get("operator") or ""),
                    str(row.get("closeout_status_snapshot") or ""),
                    str(row.get("item_count_snapshot") or 0),
                    str(row.get("handoff_required_count_snapshot") or 0),
                    str(row.get("note") or row.get("closure_gate") or ""),
                )
            console.print(table)
        return

    if args.record_ops_closeout_signoff:
        record = record_ops_closeout_signoff(
            status=args.ops_closeout_signoff_status,
            operator=args.ops_closeout_signoff_operator or "cli",
            note=args.note or args.reason,
            limit=args.limit,
            source=args.ops_closeout_source,
            item_status=args.ops_closeout_status,
            market_id=args.ops_closeout_market,
            handoff_required=True if args.ops_closeout_handoff_required else None,
        )
        if args.json:
            console.print_json(data={"ok": True, "record": record})
        else:
            console.print(f"[green]Recorded paper ops closeout signoff:[/green] {record.get('signoff_id')} status={record.get('status')} closeout={record.get('closeout_status_snapshot')} handoff_required={record.get('handoff_required_count_snapshot')}")
        return

    if args.ops_closeout_signoff_detail:
        record = get_ops_closeout_signoff(args.ops_closeout_signoff_detail)
        if args.json:
            console.print_json(data={"item": record, "found": bool(record)})
        elif record:
            table = Table(title=f"Paper Ops Closeout Signoff Detail: {args.ops_closeout_signoff_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["signoff_id", "created_at", "operator", "status", "closeout_status_snapshot", "closure_gate", "item_count_snapshot", "handoff_required_count_snapshot", "briefing_blocked_snapshot", "briefing_action_required_snapshot", "aging_critical_snapshot", "open_escalations_snapshot", "escalation_review_required_snapshot", "closed_but_reappeared_snapshot", "note"]:
                table.add_row(key, str(record.get(key) if record.get(key) is not None else ""))
            console.print(table)
            if record.get("top_closeout_items"):
                items = Table(title="Signed-off Closeout Items")
                items.add_column("Source")
                items.add_column("Status")
                items.add_column("Handoff")
                items.add_column("Item", overflow="fold")
                items.add_column("Action", overflow="fold")
                for row in (record.get("top_closeout_items") or [])[:10]:
                    items.add_row(str(row.get("source") or ""), str(row.get("status") or ""), "yes" if row.get("handoff_required") else "no", str(row.get("title") or row.get("source_id") or ""), str(row.get("recommended_action") or ""))
                console.print(items)
        else:
            console.print("[red]Paper ops closeout signoff not found.[/red]")
        return

    if args.export_ops_closeout_signoffs:
        rows = list_ops_closeout_signoffs(
            limit=10000,
            status=args.ops_closeout_signoff_status_filter,
            operator=args.ops_closeout_signoff_operator,
            market_id=args.ops_closeout_market,
        )
        out = Path(args.export_ops_closeout_signoffs)
        out.write_text(ops_closeout_signoffs_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported paper ops closeout signoffs CSV:[/green] {out}")
        return

    if args.handoff_reconciliation:
        report = build_operator_handoff_reconciliation_board(limit=args.limit, status=args.handoff_status_filter, market_id=args.handoff_market)
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Handoff Reconciliation")
            table.add_column("Handoff")
            table.add_column("State")
            table.add_column("Saved Status")
            table.add_column("Items", justify="right")
            table.add_column("Still Open", justify="right")
            table.add_column("Changed", justify="right")
            table.add_column("Not Visible", justify="right")
            table.add_column("Action", overflow="fold")
            for row in report.get("items", []):
                table.add_row(
                    str(row.get("handoff_id") or ""),
                    str(row.get("reconciliation_state") or ""),
                    str(row.get("handoff_status") or ""),
                    str(row.get("saved_item_count") or 0),
                    str(row.get("still_open") or 0),
                    str(row.get("changed_open") or 0),
                    str(row.get("not_visible") or 0),
                    str(row.get("recommended_action") or ""),
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.handoff_reconciliation_detail:
        report = reconcile_operator_handoff(args.handoff_reconciliation_detail)
        if args.json:
            console.print_json(data={"item": report, "found": bool(report)})
        elif report:
            summary = report.get("summary", {})
            table = Table(title=f"Paper Handoff Reconciliation Detail: {args.handoff_reconciliation_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["handoff_id", "handoff_status", "reconciliation_state", "recommended_action", "saved_item_count", "followup_required", "still_open", "changed_open", "not_visible", "no_longer_unresolved"]:
                table.add_row(key, str(summary.get(key) if summary.get(key) is not None else ""))
            console.print(table)
            if report.get("items"):
                items = Table(title="Reconciled Handoff Items")
                items.add_column("Status")
                items.add_column("Saved")
                items.add_column("Current")
                items.add_column("Item", overflow="fold")
                items.add_column("Action / Detail", overflow="fold")
                for row in report.get("items") or []:
                    items.add_row(
                        str(row.get("reconciliation_status") or ""),
                        str(row.get("saved_status") or ""),
                        str(row.get("current_status") or "not_visible"),
                        str(row.get("title") or row.get("briefing_item_id") or ""),
                        f"{row.get('recommended_action') or ''}: {row.get('detail') or ''}",
                    )
                console.print(items)
        else:
            console.print("[red]Paper handoff record not found.[/red]")
        return

    if args.export_handoff_reconciliation:
        report = build_operator_handoff_reconciliation_board(limit=10000, status=args.handoff_status_filter, market_id=args.handoff_market)
        out = Path(args.export_handoff_reconciliation)
        out.write_text(handoff_reconciliation_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper handoff reconciliation CSV:[/green] {out}")
        return

    if args.paper_ops_aging:
        report = build_paper_ops_aging(
            limit=args.limit,
            section=args.ops_aging_section,
            status=args.ops_aging_status,
            severity=args.ops_aging_severity,
            market_id=args.ops_aging_market,
            min_age_hours=args.ops_aging_min_hours,
        )
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Ops Aging Review")
            table.add_column("Severity")
            table.add_column("Age", justify="right")
            table.add_column("Status")
            table.add_column("Section")
            table.add_column("Item", overflow="fold")
            table.add_column("Handoffs", justify="right")
            table.add_column("Action", overflow="fold")
            for row in report.get("items", []):
                age = "?" if row.get("age_hours") is None else f"{float(row.get('age_hours') or 0):.1f}h"
                table.add_row(
                    str(row.get("severity") or ""),
                    age,
                    str(row.get("status") or ""),
                    str(row.get("section") or ""),
                    str(row.get("title") or row.get("aging_item_id") or ""),
                    str(row.get("handoff_count") or 0),
                    str(row.get("recommended_action") or ""),
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.ops_aging_detail:
        detail = build_ops_aging_detail(args.ops_aging_detail)
        if args.json:
            console.print_json(data={"item": detail, "found": bool(detail)})
        elif detail:
            item = detail.get("item", {})
            table = Table(title=f"Paper Ops Aging Detail: {args.ops_aging_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["aging_item_id", "severity", "status", "section", "age_hours", "origin_at", "origin_source", "handoff_count", "last_handoff_id", "recommended_action", "detail"]:
                table.add_row(key, str(item.get(key) if item.get(key) is not None else ""))
            console.print(table)
        else:
            console.print("[red]Paper ops aging item not found.[/red]")
        return

    if args.export_ops_aging:
        report = build_paper_ops_aging(
            limit=10000,
            section=args.ops_aging_section,
            status=args.ops_aging_status,
            severity=args.ops_aging_severity,
            market_id=args.ops_aging_market,
            min_age_hours=args.ops_aging_min_hours,
        )
        out = Path(args.export_ops_aging)
        out.write_text(ops_aging_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper ops aging CSV:[/green] {out}")
        return

    if args.paper_ops_escalations:
        report = build_ops_escalation_board(
            limit=args.limit,
            status=args.ops_escalation_status_filter,
            severity=args.ops_escalation_severity_filter,
            market_id=args.ops_escalation_market,
            owner=args.ops_escalation_owner_filter,
        )
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Ops Escalation Register")
            table.add_column("Status")
            table.add_column("Severity")
            table.add_column("Owner")
            table.add_column("Item", overflow="fold")
            table.add_column("Market")
            table.add_column("Note / Action", overflow="fold")
            for row in report.get("items", []):
                table.add_row(
                    str(row.get("status") or ""),
                    str(row.get("severity") or ""),
                    str(row.get("owner") or ""),
                    str(row.get("title") or row.get("escalation_id") or ""),
                    str(row.get("market_id") or ""),
                    str(row.get("note") or row.get("recommended_action_at_escalation") or ""),
                )
            console.print(table)
            if report.get("candidates"):
                candidates = Table(title="Escalation Candidates")
                candidates.add_column("Severity")
                candidates.add_column("Age", justify="right")
                candidates.add_column("Item", overflow="fold")
                candidates.add_column("Action", overflow="fold")
                for row in report.get("candidates", [])[:10]:
                    age = "?" if row.get("age_hours") is None else f"{float(row.get('age_hours') or 0):.1f}h"
                    candidates.add_row(
                        str(row.get("recommended_escalation_severity") or ""),
                        age,
                        str(row.get("title") or row.get("aging_item_id") or ""),
                        str(row.get("recommended_action") or ""),
                    )
                console.print(candidates)
            console.print_json(data={"summary": report.get("summary", {}), "candidate_summary": report.get("candidate_summary", {})})
        return

    if args.create_ops_escalation:
        try:
            record = create_ops_escalation(
                aging_item_id=args.create_ops_escalation,
                status=args.ops_escalation_status,
                severity=args.ops_escalation_severity,
                owner=args.ops_escalation_owner or "local",
                note=args.note or "",
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if args.json:
            console.print_json(data={"ok": True, "record": record})
        else:
            console.print(f"[green]Created paper ops escalation:[/green] {record.get('escalation_id')}")
        return

    if args.update_ops_escalation:
        record = update_ops_escalation(
            args.update_ops_escalation,
            status=args.ops_escalation_status or None,
            severity=args.ops_escalation_severity or None,
            owner=args.ops_escalation_owner or None,
            note=args.note or "",
        )
        if not record:
            raise SystemExit(f"Paper ops escalation not found: {args.update_ops_escalation}")
        if args.json:
            console.print_json(data={"ok": True, "record": record})
        else:
            console.print(f"[green]Updated paper ops escalation:[/green] {record.get('escalation_id')}")
        return

    if args.ops_escalation_detail:
        item = get_ops_escalation(args.ops_escalation_detail)
        if args.json:
            console.print_json(data={"item": item, "found": bool(item)})
        elif item:
            table = Table(title=f"Paper Ops Escalation Detail: {args.ops_escalation_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["escalation_id", "aging_item_id", "status", "severity", "owner", "section", "market_id", "ticket_id", "created_at", "updated_at", "recommended_action_at_escalation", "note"]:
                table.add_row(key, str(item.get(key) if item.get(key) is not None else ""))
            console.print(table)
        else:
            console.print("[red]Paper ops escalation not found.[/red]")
        return

    if args.export_ops_escalations:
        rows = list_ops_escalations(
            limit=10000,
            status=args.ops_escalation_status_filter,
            severity=args.ops_escalation_severity_filter,
            market_id=args.ops_escalation_market,
            owner=args.ops_escalation_owner_filter,
        )
        out = Path(args.export_ops_escalations)
        out.write_text(ops_escalations_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported paper ops escalation CSV:[/green] {out}")
        return

    if args.paper_ops_escalation_review:
        report = build_ops_escalation_review(
            limit=args.limit,
            status=args.ops_escalation_status_filter,
            severity=args.ops_escalation_severity_filter,
            market_id=args.ops_escalation_market,
            owner=args.ops_escalation_owner_filter,
            review_state=args.ops_escalation_review_state,
        )
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Ops Escalation Review")
            table.add_column("Review")
            table.add_column("Escalation")
            table.add_column("Current")
            table.add_column("Owner")
            table.add_column("Item", overflow="fold")
            table.add_column("Action", overflow="fold")
            for row in report.get("items", []):
                current = "not visible"
                if row.get("current_item_visible"):
                    age = "?" if row.get("current_age_hours") is None else f"{float(row.get('current_age_hours') or 0):.1f}h"
                    current = f"{row.get('current_status')}/{row.get('current_severity')} ({age})"
                table.add_row(
                    str(row.get("review_state") or ""),
                    f"{row.get('escalation_status')}/{row.get('escalation_severity')}",
                    current,
                    str(row.get("owner") or ""),
                    str(row.get("title") or row.get("escalation_id") or ""),
                    str(row.get("recommended_action") or ""),
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.ops_escalation_review_detail:
        item = review_ops_escalation(args.ops_escalation_review_detail)
        if args.json:
            console.print_json(data={"item": item, "found": bool(item)})
        elif item:
            table = Table(title=f"Paper Ops Escalation Review Detail: {args.ops_escalation_review_detail}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            for key in ["escalation_id", "aging_item_id", "review_state", "recommended_action", "escalation_status", "escalation_severity", "owner", "current_status", "current_severity", "current_age_hours", "current_handoff_count", "status_changed", "severity_changed"]:
                table.add_row(key, str(item.get(key) if item.get(key) is not None else ""))
            console.print(table)
        else:
            console.print("[red]Paper ops escalation review item not found.[/red]")
        return

    if args.export_ops_escalation_review:
        report = build_ops_escalation_review(
            limit=10000,
            status=args.ops_escalation_status_filter,
            severity=args.ops_escalation_severity_filter,
            market_id=args.ops_escalation_market,
            owner=args.ops_escalation_owner_filter,
            review_state=args.ops_escalation_review_state,
        )
        out = Path(args.export_ops_escalation_review)
        out.write_text(ops_escalation_review_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper ops escalation review CSV:[/green] {out}")
        return

    if args.assign_playbook:
        playbook_id = args.playbook_id or "edge_evidence_confluence"
        if not get_playbook(playbook_id):
            raise SystemExit(f"Unknown playbook: {playbook_id}")
        fit_snapshot = {}
        try:
            market = await client.get_market(args.assign_playbook)
            if market:
                markets = attach_evidence_probability(attach_probability(attach_scores([market])))
                opportunities = rank_opportunities(markets, watchlist=load_watchlist(), max_items=1)
                opportunity = opportunities[0] if opportunities else markets[0]
                fit_snapshot = (evaluate_market_playbooks(opportunity, readiness=build_readiness_result(opportunity), playbook_id=playbook_id).get("best_fit") or {})
        except Exception:
            fit_snapshot = {}
        decision = create_playbook_decision(args.assign_playbook, playbook_id, status=args.decision_status, note=args.note or args.reason, created_by="cli", fit_snapshot=fit_snapshot)
        if args.json:
            console.print_json(data=decision)
        else:
            console.print(f"[green]Logged playbook decision:[/green] {decision.get('decision_id')} ({decision.get('playbook_name')})")
        return

    if args.review_report:
        report = build_review_report(limit=args.limit, status=args.review_status)
        if args.json:
            console.print_json(data=report)
        else:
            table = Table(title="Paper Review Report")
            table.add_column("#", justify="right")
            table.add_column("Status")
            table.add_column("Market", overflow="fold")
            table.add_column("Realized", justify="right")
            table.add_column("Unrealized", justify="right")
            table.add_column("Net", justify="right")
            table.add_column("Warnings", justify="right")
            table.add_column("Lesson", overflow="fold")
            for i, row in enumerate(report.get("items", []), 1):
                table.add_row(
                    str(i),
                    str(row.get("lifecycle_status") or ""),
                    str(row.get("question") or row.get("market_id") or ""),
                    signed_money(row.get("realized_pnl")),
                    signed_money(row.get("unrealized_pnl")),
                    signed_money(row.get("net_pnl")),
                    str(row.get("warning_count") or 0),
                    str(row.get("lesson") or ""),
                )
            console.print(table)
            console.print_json(data={"summary": report.get("summary", {})})
        return

    if args.review_market:
        data = build_market_review(args.review_market)
        if args.json:
            console.print_json(data=data)
        else:
            item = data.get("item") or {}
            table = Table(title=f"Paper Market Review: {args.review_market}")
            table.add_column("Field")
            table.add_column("Value", overflow="fold")
            table.add_row("Question", str(item.get("question") or args.review_market))
            table.add_row("Lifecycle", str(item.get("lifecycle_status") or "no local paper lifecycle"))
            table.add_row("Realized P&L", signed_money(item.get("realized_pnl")))
            table.add_row("Unrealized P&L", signed_money(item.get("unrealized_pnl")))
            table.add_row("Net P&L", signed_money(item.get("net_pnl")))
            table.add_row("Lesson", str(item.get("lesson") or "No local paper records found."))
            table.add_row("Warnings", str(item.get("warning_count") or 0))
            table.add_row("Audit rows", str(len(data.get("audit_items", []))))
            console.print(table)
        return

    if args.export_review_report:
        report = build_review_report(limit=10000, status=args.review_status)
        out = Path(args.export_review_report)
        out.write_text(review_report_to_csv(report.get("items", [])), encoding="utf-8")
        console.print(f"[green]Exported paper review report CSV:[/green] {out}")
        return

    if args.audit_log:
        rows = build_audit_events(limit=args.limit, category=args.audit_category)
        data = {"summary": summarize_audit(rows), "items": rows}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Paper Audit Ledger")
            table.add_column("#", justify="right")
            table.add_column("Time")
            table.add_column("Category")
            table.add_column("Event")
            table.add_column("Market", overflow="fold")
            table.add_column("Amount", justify="right")
            table.add_column("P&L", justify="right")
            for i, row in enumerate(rows, 1):
                amount = row.get("amount")
                pnl = row.get("pnl")
                table.add_row(
                    str(i),
                    str(row.get("timestamp") or ""),
                    str(row.get("category") or ""),
                    str(row.get("event_type") or ""),
                    str(row.get("question") or row.get("market_id") or ""),
                    money(amount) if amount is not None else "",
                    signed_money(pnl) if pnl is not None else "",
                )
            console.print(table)
            console.print_json(data={"summary": data["summary"]})
        return

    if args.audit_market:
        data = build_market_audit(args.audit_market, limit=args.limit)
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title=f"Paper Audit Ledger: {args.audit_market}")
            table.add_column("#", justify="right")
            table.add_column("Time")
            table.add_column("Category")
            table.add_column("Event")
            table.add_column("Status")
            table.add_column("Detail", overflow="fold")
            for i, row in enumerate(data["items"], 1):
                table.add_row(str(i), str(row.get("timestamp") or ""), str(row.get("category") or ""), str(row.get("event_type") or ""), str(row.get("status") or ""), str(row.get("detail") or ""))
            console.print(table)
            console.print_json(data={"summary": data["summary"]})
        return

    if args.export_audit:
        rows = build_audit_events(limit=10000, category=args.audit_category)
        out = Path(args.export_audit)
        out.write_text(audit_to_csv(rows), encoding="utf-8")
        console.print(f"[green]Exported paper audit CSV:[/green] {out}")
        return


    if args.exit_tickets:
        rows = list_exit_tickets(limit=args.limit, status=args.exit_ticket_status_filter)
        data = {"summary": summarize_exit_tickets(rows), "items": rows}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Paper Exit Tickets")
            table.add_column("#", justify="right")
            table.add_column("Status")
            table.add_column("Market", overflow="fold")
            table.add_column("Outcome")
            table.add_column("Price", justify="right")
            table.add_column("Shares", justify="right")
            table.add_column("Est. P&L", justify="right")
            table.add_column("Ticket")
            for i, row in enumerate(rows, 1):
                table.add_row(
                    str(i),
                    row.get("status", ""),
                    row.get("title", ""),
                    row.get("outcome", ""),
                    f"{float(row.get('price') or 0):.4f}",
                    f"{float(row.get('shares') or 0):.4f}",
                    signed_money(row.get("estimated_realized_pnl")),
                    row.get("ticket_id", ""),
                )
            console.print(table)
            console.print_json(data={"summary": data["summary"]})
        return

    if args.create_exit_ticket:
        market = await client.get_market(args.create_exit_ticket)
        if not market:
            market = None
        try:
            ticket = create_exit_ticket(
                args.create_exit_ticket,
                outcome=args.outcome,
                market=market,
                shares=args.shares,
                price=args.exit_price,
                reason=args.reason or args.note or "cli paper exit review",
                created_by="cli",
                operator_note=args.note,
            )
            console.print_json(data=ticket)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.update_exit_ticket:
        try:
            ticket = update_exit_ticket(args.update_exit_ticket, status=args.exit_ticket_status, operator_note=args.note or args.reason, operator_decision=args.exit_ticket_status)
            console.print_json(data=ticket)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.exit_ticket_detail:
        ticket = get_exit_ticket(args.exit_ticket_detail)
        if ticket:
            console.print_json(data=ticket)
        else:
            console.print("[red]Exit ticket not found.[/red]")
        return

    if args.execute_exit_ticket:
        ticket = get_exit_ticket(args.execute_exit_ticket)
        if not ticket:
            console.print("[red]Exit ticket not found.[/red]")
            return
        if not ticket.get("execution_allowed"):
            console.print("[red]Exit ticket is not execution-ready. Resolve blockers first.[/red]")
            return
        if ticket.get("status") == "paper_executed":
            console.print("[yellow]Exit ticket has already been paper executed.[/yellow]")
            return
        market = await client.get_market(str(ticket.get("market_id")))
        snapshot = market or executable_exit_snapshot(ticket)
        try:
            result = paper_sell(
                snapshot,
                outcome=ticket.get("outcome", "YES"),
                price=float(ticket.get("price") or 0.5),
                shares=float(ticket.get("shares") or 0.0),
                reason=f"paper exit ticket {ticket.get('ticket_id')}: {ticket.get('exit_reason') or 'cli reviewed exit'}",
            )
            updated = update_exit_ticket(
                str(ticket.get("ticket_id")),
                status="paper_executed",
                operator_decision="paper_executed",
                paper_trade_id=result.get("trade", {}).get("id"),
                execution_result=result,
            )
            console.print_json(data={"ticket": updated, "paper_result": result})
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.trade_tickets:
        rows = list_trade_tickets(limit=args.limit, status=args.ticket_status_filter)
        data = {"summary": summarize_trade_tickets(rows), "items": rows}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Paper Trade Tickets")
            table.add_column("#", justify="right")
            table.add_column("Status")
            table.add_column("Market", overflow="fold")
            table.add_column("Outcome")
            table.add_column("Price", justify="right")
            table.add_column("Stake", justify="right")
            table.add_column("Ticket")
            for i, row in enumerate(rows, 1):
                table.add_row(str(i), row.get("status", ""), row.get("title", ""), row.get("outcome", ""), f"{float(row.get('price') or 0):.4f}", money(row.get("stake")), row.get("ticket_id", ""))
            console.print(table)
            console.print_json(data={"summary": data["summary"]})
        return

    if args.create_ticket:
        market = await client.get_market(args.create_ticket)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_evidence_probability(attach_probability(attach_scores([market])))
        rows = rank_opportunities(scored, watchlist=load_watchlist(), max_items=1)
        opportunity = rows[0] if rows else scored[0]
        readiness = build_readiness_result(opportunity)
        ticket = create_trade_ticket(opportunity, readiness, stake=args.stake, outcome=args.outcome, created_by="cli", operator_note=args.note or args.reason)
        console.print_json(data=ticket)
        return

    if args.update_ticket:
        try:
            ticket = update_trade_ticket(args.update_ticket, status=args.ticket_status, operator_note=args.note or args.reason, operator_decision=args.ticket_status)
            console.print_json(data=ticket)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.ticket_detail:
        ticket = get_trade_ticket(args.ticket_detail)
        if ticket:
            console.print_json(data=ticket)
        else:
            console.print("[red]Trade ticket not found.[/red]")
        return

    if args.settlements:
        rows = list_settlements(limit=args.limit)
        data = {"summary": settlement_summary(rows), "items": rows}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Manual Paper Settlements")
            table.add_column("#", justify="right")
            table.add_column("Settled")
            table.add_column("Market")
            table.add_column("Winner")
            table.add_column("Payout", justify="right")
            table.add_column("Realized P&L", justify="right")
            for i, row in enumerate(rows, 1):
                table.add_row(str(i), row.get("settled_at", ""), row.get("market_id", ""), row.get("winning_outcome", ""), money(row.get("total_payout")), signed_money(row.get("total_realized_pnl")))
            console.print(table)
            console.print_json(data={"summary": data["summary"]})
        return

    if args.settlement_candidates:
        rows = settlement_candidates(limit=args.limit)
        if args.json:
            console.print_json(data={"count": len(rows), "items": rows})
        else:
            table = Table(title="Open Paper Settlement Candidates")
            table.add_column("#", justify="right")
            table.add_column("Market", overflow="fold")
            table.add_column("Cost", justify="right")
            table.add_column("Outcomes")
            table.add_column("Positions", justify="right")
            for i, row in enumerate(rows, 1):
                table.add_row(str(i), row.get("question", ""), money(row.get("cost_basis")), ", ".join(row.get("outcomes") or []), str(row.get("position_count", 0)))
            console.print(table)
        return

    if args.settlement_preview:
        console.print_json(data=preview_settlement(args.settlement_preview, winning_outcome=args.winning_outcome))
        return

    if args.settle_market:
        try:
            console.print_json(data=settle_market(args.settle_market, winning_outcome=args.winning_outcome, note=args.note or args.reason, resolved_by="cli"))
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.paper_positions:
        markets = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        portfolio = summarize_portfolio(markets)
        data = {"summary": position_control_summary(portfolio), "alerts": position_alerts(portfolio), "positions": portfolio.get("open_positions", []), "events": list_position_events(limit=args.limit)}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Paper Positions")
            table.add_column("#", justify="right")
            table.add_column("Market", overflow="fold")
            table.add_column("Outcome")
            table.add_column("Current", justify="right")
            table.add_column("Value", justify="right")
            table.add_column("Unrealized", justify="right")
            table.add_column("Status")
            table.add_column("Plan")
            for i, pos in enumerate(data["positions"], 1):
                plan = pos.get("exit_plan") if isinstance(pos.get("exit_plan"), dict) else {}
                table.add_row(
                    str(i),
                    pos.get("question", ""),
                    pos.get("outcome", ""),
                    f"{float(pos.get('current_price') or 0):.4f}",
                    money(pos.get("market_value")),
                    signed_money(pos.get("unrealized_pnl")),
                    str(plan.get("status") or pos.get("position_status") or "active"),
                    f"target={plan.get('target_price') or 'none'} stop={plan.get('stop_price') or 'none'}",
                )
            console.print(table)
            console.print_json(data={"summary": data["summary"], "alerts": data["alerts"]})
        return

    if args.position_alerts:
        markets = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        portfolio = summarize_portfolio(markets)
        rows = position_alerts(portfolio)
        if args.json:
            console.print_json(data={"count": len(rows), "items": rows})
        else:
            table = Table(title="Paper Position Lifecycle Alerts")
            table.add_column("#", justify="right")
            table.add_column("Level")
            table.add_column("Type")
            table.add_column("Market", overflow="fold")
            table.add_column("Detail", overflow="fold")
            for i, row in enumerate(rows, 1):
                table.add_row(str(i), row.get("level", ""), row.get("kind", ""), row.get("question", ""), row.get("detail", ""))
            console.print(table)
        return

    if args.set_position_plan:
        try:
            console.print_json(
                data=update_position_plan(
                    args.set_position_plan,
                    outcome=args.outcome,
                    target_price=args.target_price,
                    stop_price=args.stop_price,
                    max_hold_days=args.max_hold_days,
                    status=args.position_status,
                    review_note=args.note or args.reason,
                    updated_by="cli",
                )
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.opportunity_engine:
        markets = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        markets = attach_evidence_probability(markets)
        rows = rank_opportunities(markets, watchlist=load_watchlist(), max_items=args.max_opportunities)
        if args.json:
            console.print_json(data={"summary": opportunity_summary(rows), "items": rows})
        else:
            table = Table(title="Opportunity Engine v1")
            table.add_column("#", justify="right")
            table.add_column("Rank", justify="right")
            table.add_column("Question", overflow="fold")
            table.add_column("Edge", justify="right")
            table.add_column("Evidence", justify="right")
            table.add_column("Risk")
            table.add_column("Stage")
            table.add_column("Action")
            for i, row in enumerate(rows, 1):
                table.add_row(
                    str(i),
                    f"{row.get('rank_score', 0):.1f}",
                    row.get("question", ""),
                    f"{row.get('edge_percent', 0):+.2f}%",
                    f"{row.get('evidence_score', 0):.0f}/100",
                    "OK" if row.get("risk_ok") else "blocked",
                    row.get("workflow_stage", ""),
                    row.get("recommended_action", ""),
                )
            console.print(table)
            console.print_json(data={"summary": opportunity_summary(rows)})
        return

    if args.source_status:
        result = await check_sources_status(category=args.source_category, timeout=args.source_timeout)
        if args.json:
            console.print_json(data=result)
        else:
            table = Table(title="Research Source Availability")
            table.add_column("Source")
            table.add_column("Category")
            table.add_column("OK")
            table.add_column("HTTP")
            table.add_column("Latency")
            table.add_column("Error", overflow="fold")
            for row in result.get("items", []):
                table.add_row(row.get("name", ""), row.get("category", ""), "yes" if row.get("ok") else "no", str(row.get("status_code") or ""), str(row.get("latency_ms") or ""), row.get("error", ""))
            console.print(table)
            console.print_json(data={"count": result.get("count"), "ok_count": result.get("ok_count"), "fail_count": result.get("fail_count")})
        return

    if args.collection_targets:
        market = await client.get_market(args.collection_targets)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_probability(attach_scores([market]))[0]
        console.print_json(data=build_market_collection_targets(scored))
        return


    if args.evidence_probability:
        market = await client.get_market(args.evidence_probability)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_probability(attach_scores([market]))[0]
        console.print_json(data=evidence_adjusted_probability(scored))
        return

    if args.evidence_probabilities:
        markets = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        rows = attach_evidence_probability(markets)
        if args.json:
            console.print_json(data={"items": rows})
        else:
            table = Table(title="Evidence-Adjusted Probability Model")
            table.add_column("#", justify="right")
            table.add_column("Adj Edge", justify="right")
            table.add_column("Question", overflow="fold")
            table.add_column("Market", justify="right")
            table.add_column("Base", justify="right")
            table.add_column("Evidence", justify="right")
            table.add_column("Confidence")
            table.add_column("Signal")
            for i, market in enumerate(rows, 1):
                ep = market.get("evidence_probability", {})
                edge = ep.get("evidence_adjusted_edge_percent")
                table.add_row(str(i), f"{edge:+.2f}%" if edge is not None else "n/a", market.get("question", ""), str(ep.get("market_probability")), str(ep.get("base_model_probability")), str(ep.get("evidence_adjusted_probability")), ep.get("evidence_adjusted_confidence", ""), ep.get("evidence_adjusted_signal", ""))
            console.print(table)
        return

    if args.evidence_score:
        # First try packet filename; otherwise treat value as market id.
        try:
            console.print_json(data={"mode": "packet_evidence_score", "item": score_packet_by_id(args.evidence_score)})
        except Exception:
            console.print_json(data={"mode": "market_evidence_score", "item": score_market_evidence(args.evidence_score)})
        return

    if args.evidence:
        data = {"summary": evidence_summary(limit=args.limit), "items": list_evidence_packets(limit=args.limit)}
        if args.json:
            console.print_json(data=data)
        else:
            table = Table(title="Saved Evidence Packets")
            table.add_column("#", justify="right")
            table.add_column("Created")
            table.add_column("Status")
            table.add_column("Sources", justify="right")
            table.add_column("Market", overflow="fold")
            table.add_column("Packet")
            for i, row in enumerate(data["items"], 1):
                table.add_row(str(i), row.get("created_at", ""), row.get("status", ""), str(row.get("source_count", 0)), row.get("question", ""), row.get("packet_id", ""))
            console.print(table)
            console.print_json(data={"summary": data["summary"]})
        return

    if args.evidence_detail:
        try:
            console.print_json(data=load_evidence_packet(args.evidence_detail))
        except FileNotFoundError:
            console.print("[red]Evidence packet not found.[/red]")
        return

    if args.collect_evidence:
        market = await client.get_market(args.collect_evidence)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_probability(attach_scores([market]))[0]
        packet = create_evidence_packet(scored, created_by="cli", note=args.note or "CLI evidence collection", include_weak_sources=args.include_weak_sources)
        console.print_json(data=packet)
        return

    if args.sources:
        if args.json:
            console.print_json(data={"summary": source_summary(), "items": list_sources(category=args.source_category)})
        else:
            table = Table(title="Research Source Registry")
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Category")
            table.add_column("Role", overflow="fold")
            table.add_column("Key?")
            for source in list_sources(category=args.source_category):
                table.add_row(source.get("id", ""), source.get("name", ""), source.get("category", ""), source.get("role", ""), "yes" if source.get("requires_key") else "no")
            console.print(table)
            console.print_json(data={"summary": source_summary()})
        return

    if args.source_links:
        console.print_json(data={"query": args.source_links, "items": build_source_links(args.source_links, category=args.source_category)})
        return

    if args.source_pack:
        market = await client.get_market(args.source_pack)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_probability(attach_scores([market]))[0]
        console.print_json(data=build_market_source_pack(scored))
        return

    if args.notes:
        summary = notes_summary(limit=args.limit)
        if args.json:
            console.print_json(data={"summary": summary, "items": list(reversed(load_notes()))[:args.limit]})
        else:
            table = Table(title="Local Market Notes")
            table.add_column("#", justify="right")
            table.add_column("Tag")
            table.add_column("Market", overflow="fold")
            table.add_column("Note", overflow="fold")
            table.add_column("Created")
            for i, note in enumerate(summary.get("recent", []), 1):
                table.add_row(str(i), note.get("tag", ""), note.get("question", ""), note.get("text", ""), note.get("created_at", ""))
            console.print(table)
            console.print_json(data={"count": summary.get("count"), "by_tag": summary.get("by_tag")})
        return

    if args.market_notes:
        console.print_json(data={"market_id": args.market_notes, "items": notes_for_market(args.market_notes)})
        return

    if args.add_note:
        market = await client.get_market(args.add_note)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        try:
            console.print_json(data=add_note(market, text=args.note_text, tag=args.note_tag))
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        return

    if args.delete_note:
        ok = delete_note(args.delete_note)
        console.print("[green]Deleted note.[/green]" if ok else "[yellow]No matching note found.[/yellow]")
        return

    if args.alerts:
        previous = load_latest()
        markets = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        movers = calculate_movers(markets, previous)[:50]
        portfolio = summarize_portfolio(markets)
        risk = risk_status(load_portfolio())
        alerts = generate_alerts(markets, movers=movers, portfolio=portfolio, risk=risk, max_items=args.limit)
        if args.json:
            console.print_json(data={"summary": summarize_alerts(alerts), "items": alerts})
        else:
            table = Table(title="Local Paper Alerts")
            table.add_column("#", justify="right")
            table.add_column("Level")
            table.add_column("Kind")
            table.add_column("Title")
            table.add_column("Market", overflow="fold")
            table.add_column("Detail", overflow="fold")
            for i, alert in enumerate(alerts, 1):
                table.add_row(str(i), alert.get("level", ""), alert.get("kind", ""), alert.get("title", ""), alert.get("question") or "", alert.get("detail", ""))
            console.print(table)
            console.print_json(data={"summary": summarize_alerts(alerts)})
        return

    if args.keys:
        console.print_json(data=get_api_key_status())
        return

    if args.strategy:
        console.print_json(data=explain_strategy())
        return

    if args.recommendations:
        markets = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        recs = recommend_paper_trades(markets, min_edge=args.min_edge, min_confidence_score=args.min_confidence, max_recommendations=args.limit, default_stake=args.stake)
        table = Table(title="Paper Strategy Recommendations")
        table.add_column("#", justify="right")
        table.add_column("EV/$100", justify="right")
        table.add_column("Market", overflow="fold")
        table.add_column("Market", justify="right")
        table.add_column("Model", justify="right")
        table.add_column("Confidence")
        table.add_column("Market ID")
        for i, rec in enumerate(recs, 1):
            table.add_row(str(i), f"{rec['expected_value_per_100']:+.2f}", rec.get("question", ""), f"{rec['market_probability']:.2f}", f"{rec['model_probability']:.2f}", f"{rec['confidence']} {rec['confidence_score']}", rec.get("market_id", ""))
        console.print(table)
        return

    if args.backtests:
        console.print_json(data={"items": list_backtests(limit=args.limit)})
        return

    if args.run_backtest:
        console.print_json(data=run_snapshot_backtest(min_edge=args.min_edge, min_confidence_score=args.min_confidence, stake=args.stake, max_trades_per_snapshot=args.max_trades_per_snapshot, save=True))
        return

    if args.probabilities:
        rows = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        table = Table(title="Probability Model v1")
        table.add_column("#", justify="right")
        table.add_column("Edge", justify="right")
        table.add_column("Question", overflow="fold")
        table.add_column("Market", justify="right")
        table.add_column("Model", justify="right")
        table.add_column("Confidence")
        table.add_column("Signal")
        for i, market in enumerate(rows, 1):
            pm = market.get("probability_model", {})
            edge = pm.get("edge_percent")
            table.add_row(str(i), f"{edge:+.2f}%" if edge is not None else "n/a", market.get("question", ""), str(pm.get("market_probability")), str(pm.get("model_probability")), pm.get("confidence", ""), pm.get("signal", ""))
        console.print(table)
        return

    if args.portfolio:
        markets = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        console.print_json(data=summarize_portfolio(markets))
        return

    if args.risk:
        console.print_json(data=risk_status(load_portfolio()))
        return

    if args.risk_check:
        market = await client.get_market(args.risk_check)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_probability(attach_scores([market]))[0]
        price = float((scored.get("probability_model") or {}).get("market_probability") or 0.5)
        console.print_json(data=check_paper_buy(scored, load_portfolio(), stake=args.stake, price=price, outcome=args.outcome))
        return

    if args.paper_analytics:
        try:
            markets = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order="volume24hr")))
        except Exception:
            markets = []
        portfolio = summarize_portfolio(markets)
        console.print_json(data={"analytics": trade_analytics(load_trades(), portfolio), "portfolio": portfolio})
        return

    if args.export_trades:
        out = Path(args.export_trades)
        out.write_text(trades_to_csv(load_trades()))
        console.print(f"[green]Exported paper trades CSV:[/green] {out}")
        return

    if args.trades:
        console.print_json(data={"items": load_trades()})
        return

    if args.reset_paper is not None:
        console.print_json(data=reset_portfolio(cash=args.reset_paper))
        return

    if args.paper_buy:
        market = await client.get_market(args.paper_buy)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_probability(attach_scores([market]))[0]
        console.print_json(data=paper_buy(scored, outcome=args.outcome, stake=args.stake, reason=args.reason or "CLI paper buy"))
        return

    if args.paper_sell:
        market = await client.get_market(args.paper_sell)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_probability(attach_scores([market]))[0]
        console.print_json(data=paper_sell(scored, outcome=args.outcome, reason=args.reason or "CLI paper sell"))
        return

    if args.watchlist:
        rows = load_watchlist()
        table = Table(title="Local Research Watchlist")
        table.add_column("#", justify="right")
        table.add_column("Market ID")
        table.add_column("Question", overflow="fold")
        table.add_column("Note", overflow="fold")
        table.add_column("Updated")
        for i, row in enumerate(rows, 1):
            table.add_row(str(i), str(row.get("market_id", "")), row.get("question", ""), row.get("note", ""), row.get("updated_at", ""))
        console.print(table)
        return

    if args.research:
        market = await client.get_market(args.research)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        scored = attach_scores([market])[0]
        packet = make_research_packet(scored)
        if args.add_watch:
            added = add_to_watchlist(scored, note=args.note or "Research candidate")
            console.print(f"[green]Watchlist updated:[/green] {added.get('market_id')}")
        console.print_json(data=packet)
        return

    if args.remove_watch:
        ok = remove_from_watchlist(args.remove_watch)
        console.print("[green]Removed from watchlist.[/green]" if ok else "[yellow]No matching watchlist item found.[/yellow]")
        return

    if args.book:
        book = await clob.get_order_book(args.book)
        table = Table(title="CLOB Order Book Summary")
        table.add_column("Token", overflow="fold")
        table.add_column("Best Bid", justify="right")
        table.add_column("Best Ask", justify="right")
        table.add_column("Spread", justify="right")
        table.add_column("Midpoint", justify="right")
        table.add_column("Last", justify="right")
        table.add_row(book["token_id"], str(book.get("best_bid")), str(book.get("best_ask")), str(book.get("spread")), str(book.get("midpoint")), str(book.get("last_trade_price")))
        console.print(table)
        depth = Table(title="Top Book Levels")
        depth.add_column("Side")
        depth.add_column("Price", justify="right")
        depth.add_column("Size", justify="right")
        for row in book.get("bids", [])[:8]:
            depth.add_row("bid", f"{row['price']:.4f}", f"{row['size']:.2f}")
        for row in book.get("asks", [])[:8]:
            depth.add_row("ask", f"{row['price']:.4f}", f"{row['size']:.2f}")
        console.print(depth)
        return

    if args.market_books:
        market = await client.get_market(args.market_books)
        if not market:
            console.print("[red]Market not found.[/red]")
            return
        token_ids = market.get("clob_token_ids") or []
        books = await clob.get_books_for_tokens(token_ids)
        table = Table(title=f"CLOB Books for Market {args.market_books}")
        table.add_column("#", justify="right")
        table.add_column("Token", overflow="fold")
        table.add_column("Bid", justify="right")
        table.add_column("Ask", justify="right")
        table.add_column("Spread", justify="right")
        table.add_column("Mid", justify="right")
        table.add_column("Error")
        for i, book in enumerate(books, 1):
            table.add_row(str(i), book.get("token_id", ""), str(book.get("best_bid", "")), str(book.get("best_ask", "")), str(book.get("spread", "")), str(book.get("midpoint", "")), book.get("error", ""))
        console.print(table)
        return

    if args.search:
        data = await client.search(args.search, args.limit)
        console.print_json(data=data)
        return

    if args.snapshots:
        rows = list_snapshots(limit=args.limit)
        table = Table(title="Saved Market Snapshots")
        table.add_column("#", justify="right")
        table.add_column("File")
        table.add_column("Created")
        table.add_column("Markets", justify="right")
        for i, row in enumerate(rows, 1):
            table.add_row(str(i), row.get("filename", ""), row.get("created_at", ""), str(row.get("count", 0)))
        console.print(table)
        latest = latest_snapshot_summary()
        if latest:
            console.print(f"[green]Latest:[/green] {latest['created_at']} · {latest['count']} markets")
        return

    if args.movers:
        previous = load_latest()
        markets = attach_scores(await client.list_markets(limit=args.limit, order=args.sort))
        rows = calculate_movers(markets, previous)
        table = Table(title="Polymarket Movers Since Latest Snapshot")
        table.add_column("#", justify="right")
        table.add_column("Question", overflow="fold")
        table.add_column("24h Vol Δ", justify="right")
        table.add_column("Liquidity Δ", justify="right")
        table.add_column("Price Changes")
        for i, row in enumerate(rows[: args.limit], 1):
            changes = ", ".join([f"{p['outcome']} {p['delta']:+.2f}" for p in row.get("price_changes", [])[:3]])
            table.add_row(str(i), row.get("question") or "", signed_money(row.get("volume_24hr_delta")), signed_money(row.get("liquidity_delta")), changes)
        console.print(table)
        if args.new:
            new_rows = detect_new_markets(markets, previous)
            new_table = Table(title="New Markets Since Latest Snapshot")
            new_table.add_column("#", justify="right")
            new_table.add_column("Score", justify="right")
            new_table.add_column("Question", overflow="fold")
            new_table.add_column("24h Vol", justify="right")
            new_table.add_column("Liquidity", justify="right")
            for i, market in enumerate(new_rows[: args.limit], 1):
                new_table.add_row(str(i), str(market.get("opportunity_score", 0)), market.get("question", ""), money(market.get("volume_24hr")), money(market.get("liquidity")))
            console.print(new_table)
        if not previous:
            console.print("[yellow]No previous snapshot found. Run with --snapshot first.[/yellow]")
        return

    if args.opportunities:
        rows = attach_probability(attach_scores(await client.list_markets(limit=args.limit, order=args.sort)))
        table = Table(title="Polymarket Opportunity Attention Ranking")
        table.add_column("#", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Question", overflow="fold")
        table.add_column("24h Vol", justify="right")
        table.add_column("Liquidity", justify="right")
        table.add_column("Prices")
        table.add_column("Why Analyze", overflow="fold")
        for i, market in enumerate(rows, 1):
            table.add_row(
                str(i),
                str(market.get("opportunity_score", 0)),
                market["question"],
                money(market["volume_24hr"]),
                money(market["liquidity"]),
                price_summary(market["outcomes"]),
                "; ".join(market.get("why_analyze", [])),
            )
        console.print(table)
        summary = summarize_snapshot(rows)
        console.print(f"[cyan]Summary:[/cyan] {summary['count']} markets · 24h volume {money(summary['total_24h_volume'])} · liquidity {money(summary['total_liquidity'])}")
        if args.snapshot:
            info = save_snapshot(rows)
            console.print(f"[green]Saved snapshot:[/green] {info['path']}")
        return

    table = Table(title="Polymarket Gamma API Snapshot")
    table.add_column("#", justify="right")
    table.add_column("Type")
    table.add_column("Title / Question", overflow="fold")
    table.add_column("24h Vol", justify="right")
    table.add_column("Liquidity", justify="right")
    table.add_column("Category")
    table.add_column("Prices")

    if args.markets:
        rows = await client.list_markets(limit=args.limit, order=args.sort)
        for i, market in enumerate(rows, 1):
            table.add_row(str(i), "Market", market["question"], money(market["volume_24hr"]), money(market["liquidity"]), market["category"], price_summary(market["outcomes"]))
    else:
        rows = await client.list_events(limit=args.limit, order=args.sort)
        for i, event in enumerate(rows, 1):
            table.add_row(str(i), "Event", event["title"], money(event["volume_24hr"]), money(event["liquidity"]), event["category"], price_summary(event["markets"][0]["outcomes"]) if event["markets"] else "")

    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Display and rank Polymarket Gamma API data.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--sort", default="volume_24hr", help="Gamma order field, e.g. volume_24hr for events or volume24hr for markets")
    parser.add_argument("--markets", action="store_true", help="Show markets instead of events")
    parser.add_argument("--opportunities", action="store_true", help="Rank markets by attention/opportunity score")
    parser.add_argument("--opportunity-engine", action="store_true", help="Show v0.3.0 opportunity engine ranking")
    parser.add_argument("--trade-tickets", action="store_true", help="List local paper trade tickets")
    parser.add_argument("--playbooks", action="store_true", help="Show v0.4.3 local strategy playbook library")
    parser.add_argument("--active-playbooks", action="store_true", help="Show only active playbooks with --playbooks")
    parser.add_argument("--playbook-board", action="store_true", help="Classify current opportunities against local strategy playbooks")
    parser.add_argument("--playbook-fit", help="Show strategy playbook fit for one market ID")
    parser.add_argument("--playbook-id", default=None, help="Filter/use a specific playbook ID")
    parser.add_argument("--playbook-decisions", action="store_true", help="List local strategy playbook decisions")
    parser.add_argument("--playbook-performance", action="store_true", help="Show v0.4.3 local playbook performance review")
    parser.add_argument("--playbook-performance-detail", help="Show playbook performance details for one playbook ID")
    parser.add_argument("--export-playbook-performance", help="Export playbook performance to a CSV file")
    parser.add_argument("--decision-status-filter", default=None, help="Filter playbook performance by decision status")
    parser.add_argument("--risk-budget", action="store_true", help="Show v0.4.3 local paper risk budget review")
    parser.add_argument("--risk-budget-detail", help="Show risk-budget detail for one market ID")
    parser.add_argument("--risk-budget-market", default=None, help="Filter --risk-budget or --export-risk-budget by market ID")
    parser.add_argument("--export-risk-budget", help="Export paper risk budget review to a CSV file")
    parser.add_argument("--preflight", action="store_true", help="Show v0.4.3 local paper entry preflight gate")
    parser.add_argument("--preflight-ticket", help="Show paper preflight detail for one entry ticket ID")
    parser.add_argument("--preflight-status", default=None, help="Filter --preflight by entry-ticket status")
    parser.add_argument("--strict-playbook-preflight", action="store_true", help="Require a playbook decision for preflight approval")
    parser.add_argument("--export-preflight", help="Export paper preflight review to a CSV file")
    parser.add_argument("--approvals", action="store_true", help="Show v0.4.4 local paper execution approvals")
    parser.add_argument("--approval-detail", help="Show one paper approval record by approval ID")
    parser.add_argument("--approval-ticket", default=None, help="Filter approvals by ticket ID")
    parser.add_argument("--approval-market", default=None, help="Filter approvals by market ID")
    parser.add_argument("--approval-status-filter", default=None, help="Filter approvals by status: approved, blocked, rejected, executed")
    parser.add_argument("--approve-ticket", help="Run preflight and record a local paper execution approval for a ticket ID")
    parser.add_argument("--reject-ticket", help="Reject a local paper entry ticket and record the approval decision")
    parser.add_argument("--approval-note", default="", help="Operator note for --approve-ticket or --reject-ticket")
    parser.add_argument("--strict-approval-preflight", action="store_true", help="Require playbook decision when approving a ticket")
    parser.add_argument("--export-approvals", help="Export paper execution approvals to a CSV file")
    parser.add_argument("--execution-queue", action="store_true", help="Show v0.4.5 local paper execution queue")
    parser.add_argument("--execution-queue-detail", help="Show execution queue detail for one entry ticket ID")
    parser.add_argument("--execution-queue-ticket", default=None, help="Filter execution queue by ticket ID")
    parser.add_argument("--execution-queue-market", default=None, help="Filter execution queue by market ID")
    parser.add_argument("--execution-queue-status", default=None, help="Filter execution queue by status: approved_ready, needs_approval, blocked, stale_approval, rejected, executed")
    parser.add_argument("--strict-execution-queue", action="store_true", help="Require playbook decision while building execution queue preflight")
    parser.add_argument("--export-execution-queue", help="Export the paper execution queue to a CSV file")
    parser.add_argument("--runbook", action="store_true", help="Show v0.4.6 local paper operator runbook")
    parser.add_argument("--runbook-detail", help="Show one paper operator runbook item by item ID")
    parser.add_argument("--runbook-item", default=None, help="Filter --runbook by item ID")
    parser.add_argument("--runbook-scope", default=None, help="Filter runbook by scope: entry_execution, exit_execution, settlement, risk_budget, post_trade_review")
    parser.add_argument("--runbook-status", default=None, help="Filter runbook by effective status: ready, action_required, blocked, review, acknowledged, skipped, completed")
    parser.add_argument("--runbook-market", default=None, help="Filter runbook by market ID")
    parser.add_argument("--include-completed-runbook", action="store_true", help="Include completed/acknowledged/skipped items in --runbook")
    parser.add_argument("--ack-runbook-item", help="Record a local acknowledgement for a runbook item ID")
    parser.add_argument("--runbook-ack-status", default="done", help="Acknowledgement status for --ack-runbook-item: done, needs_followup, skipped")
    parser.add_argument("--export-runbook", help="Export the paper operator runbook to a CSV file")
    parser.add_argument("--paper-ops-briefing", action="store_true", help="Show v0.4.7 daily paper ops briefing")
    parser.add_argument("--briefing-section", default=None, help="Filter paper ops briefing by section: runbook, entry_execution, risk_budget, post_trade_review, playbook_performance, portfolio_health")
    parser.add_argument("--briefing-status", default=None, help="Filter paper ops briefing by status: ready, action_required, blocked, review, watch, ok")
    parser.add_argument("--briefing-market", default=None, help="Filter paper ops briefing by market ID")
    parser.add_argument("--briefing-checkpoints", action="store_true", help="List local paper ops briefing checkpoints")
    parser.add_argument("--record-briefing-checkpoint", action="store_true", help="Record a local paper ops briefing checkpoint")
    parser.add_argument("--briefing-checkpoint-status", default="reviewed", help="Checkpoint status: reviewed, needs_followup, skipped")
    parser.add_argument("--export-briefing", help="Export the paper ops briefing to a CSV file")
    parser.add_argument("--paper-handoffs", action="store_true", help="Show v0.4.9 local paper operator handoff preview and saved packets")
    parser.add_argument("--handoff-detail", help="Show one saved paper operator handoff by handoff ID")
    parser.add_argument("--record-handoff", action="store_true", help="Record a local paper operator handoff packet")
    parser.add_argument("--handoff-status", default="open", help="Saved handoff status: open, handed_off, accepted, needs_followup, archived")
    parser.add_argument("--handoff-status-filter", default=None, help="Filter saved handoff packets by status")
    parser.add_argument("--handoff-section", default=None, help="Filter current handoff preview by briefing section")
    parser.add_argument("--handoff-item-status", default=None, help="Filter current handoff preview by briefing item status")
    parser.add_argument("--handoff-market", default=None, help="Filter handoff preview or saved packets by market ID")
    parser.add_argument("--handoff-incoming", default="", help="Incoming operator label for --record-handoff")
    parser.add_argument("--handoff-outgoing", default="", help="Outgoing operator label for --record-handoff")
    parser.add_argument("--export-handoffs", help="Export saved paper operator handoffs to a CSV file")
    parser.add_argument("--paper-ops-aging", action="store_true", help="Show v0.5.0 paper ops aging/staleness review")
    parser.add_argument("--ops-aging-detail", help="Show paper ops aging detail for one briefing/aging item ID")
    parser.add_argument("--ops-aging-section", default=None, help="Filter paper ops aging by briefing section")
    parser.add_argument("--ops-aging-status", default=None, help="Filter paper ops aging by current briefing status")
    parser.add_argument("--ops-aging-severity", default=None, help="Filter paper ops aging by severity: critical, stale, followup, repeat, fresh, unknown_age")
    parser.add_argument("--ops-aging-market", default=None, help="Filter paper ops aging by market ID")
    parser.add_argument("--ops-aging-min-hours", type=float, default=None, help="Only show aging rows at least this many hours old")
    parser.add_argument("--export-ops-aging", help="Export paper ops aging review to a CSV file")
    parser.add_argument("--paper-ops-closeout", action="store_true", help="Show v0.5.11 read-only end-of-shift paper ops closeout checklist")
    parser.add_argument("--ops-closeout-source", default=None, help="Filter closeout rows by source: briefing, aging, handoff_reconciliation, escalation, escalation_candidate, escalation_review")
    parser.add_argument("--ops-closeout-status", default=None, help="Filter closeout rows by normalized status/review state")
    parser.add_argument("--ops-closeout-market", default=None, help="Filter closeout rows by market ID")
    parser.add_argument("--ops-closeout-handoff-required", action="store_true", help="Only show closeout rows that require handoff/follow-up")
    parser.add_argument("--export-ops-closeout", help="Export paper ops closeout checklist to a CSV file")
    parser.add_argument("--paper-ops-closeout-signoffs", action="store_true", help="Show v0.5.11 local paper ops closeout signoff records and current preview")
    parser.add_argument("--record-ops-closeout-signoff", action="store_true", help="Record a local paper ops closeout signoff snapshot")
    parser.add_argument("--ops-closeout-signoff-detail", help="Show one paper ops closeout signoff by signoff ID")
    parser.add_argument("--ops-closeout-signoff-status", default="", help="Status for --record-ops-closeout-signoff: completed, handed_off, needs_followup, blocked, skipped")
    parser.add_argument("--ops-closeout-signoff-status-filter", default=None, help="Filter saved closeout signoffs by status")
    parser.add_argument("--ops-closeout-signoff-operator", default=None, help="Operator label for closeout signoff record or filter")
    parser.add_argument("--export-ops-closeout-signoffs", help="Export paper ops closeout signoff records to a CSV file")
    parser.add_argument("--paper-ops-escalations", action="store_true", help="Show v0.5.11 local paper ops escalation register and candidates")
    parser.add_argument("--ops-escalation-detail", help="Show one paper ops escalation by escalation ID")
    parser.add_argument("--create-ops-escalation", help="Create a local paper ops escalation from an aging item ID")
    parser.add_argument("--update-ops-escalation", help="Update a local paper ops escalation by escalation ID")
    parser.add_argument("--ops-escalation-status", default="open", help="Escalation status to set: open, investigating, waiting, resolved, dismissed")
    parser.add_argument("--ops-escalation-severity", default="", help="Escalation severity to set: critical, high, medium, low, info")
    parser.add_argument("--ops-escalation-owner", default="", help="Owner label to set on an escalation")
    parser.add_argument("--ops-escalation-status-filter", default=None, help="Filter saved ops escalations by status")
    parser.add_argument("--ops-escalation-severity-filter", default=None, help="Filter saved ops escalations by severity")
    parser.add_argument("--ops-escalation-owner-filter", default=None, help="Filter saved ops escalations by owner")
    parser.add_argument("--ops-escalation-market", default=None, help="Filter saved ops escalations/candidates by market ID")
    parser.add_argument("--export-ops-escalations", help="Export paper ops escalations to a CSV file")
    parser.add_argument("--paper-ops-escalation-review", action="store_true", help="Show v0.5.11 read-only escalation review against current paper ops aging")
    parser.add_argument("--ops-escalation-review-detail", help="Show escalation review detail for one escalation ID")
    parser.add_argument("--ops-escalation-review-state", default=None, help="Filter escalation review by state: active_followup, verify_resolution, deescalation_candidate, closed_but_reappeared, closed_record")
    parser.add_argument("--export-ops-escalation-review", help="Export paper ops escalation review to a CSV file")
    parser.add_argument("--handoff-reconciliation", action="store_true", help="Show v0.4.9 read-only reconciliation between saved handoffs and the current briefing")
    parser.add_argument("--handoff-reconciliation-detail", help="Show handoff reconciliation detail for one saved handoff ID")
    parser.add_argument("--export-handoff-reconciliation", help="Export handoff reconciliation summaries to a CSV file")
    parser.add_argument("--playbook-market", default=None, help="Filter playbook decisions by market ID")
    parser.add_argument("--assign-playbook", help="Log a local strategy playbook decision for a market ID")
    parser.add_argument("--decision-status", default="assigned", help="Status for --assign-playbook, such as assigned, rejected, needs_research, completed")
    parser.add_argument("--review-report", action="store_true", help="Show v0.4.1 paper post-trade review report")
    parser.add_argument("--review-market", help="Show paper review report for one market ID")
    parser.add_argument("--review-status", default=None, help="Filter review report by lifecycle status: open, settled, closed_by_exit, entry_only_closed_unknown, review_only")
    parser.add_argument("--export-review-report", help="Export the paper review report to a CSV file")
    parser.add_argument("--audit-log", action="store_true", help="Show the unified local paper audit ledger")
    parser.add_argument("--audit-market", help="Show the paper audit chain for one market ID")
    parser.add_argument("--audit-category", default=None, help="Filter audit rows by category: entry_ticket, paper_trade, position_lifecycle, exit_ticket, settlement, playbook_decision, execution_approval, operator_runbook, ops_briefing, operator_handoff, operator_escalation")
    parser.add_argument("--export-audit", help="Export the unified paper audit ledger to a CSV file")
    parser.add_argument("--settlements", action="store_true", help="List manual paper settlement records")
    parser.add_argument("--settlement-candidates", action="store_true", help="List open paper positions that can be manually settled")
    parser.add_argument("--settlement-preview", help="Preview manual paper settlement for a market ID")
    parser.add_argument("--settle-market", help="Manually settle all open paper positions for a market ID")
    parser.add_argument("--winning-outcome", default="YES", help="Winning outcome for --settle-market or --settlement-preview")
    parser.add_argument("--paper-positions", action="store_true", help="Show paper positions with local lifecycle plans")
    parser.add_argument("--position-alerts", action="store_true", help="Show local paper position target/stop/review alerts")
    parser.add_argument("--set-position-plan", help="Set local lifecycle plan for an open paper position by market ID")
    parser.add_argument("--exit-tickets", action="store_true", help="List local paper exit tickets")
    parser.add_argument("--create-exit-ticket", help="Create a paper exit ticket for an open paper position by market ID")
    parser.add_argument("--exit-ticket-detail", help="Show a paper exit ticket by ID")
    parser.add_argument("--update-exit-ticket", help="Update a paper exit ticket by ID")
    parser.add_argument("--execute-exit-ticket", help="Execute a simulated paper sell from an approved exit ticket ID")
    parser.add_argument("--exit-ticket-status", default="draft_review", help="Status to use with --update-exit-ticket")
    parser.add_argument("--exit-ticket-status-filter", default=None, help="Filter --exit-tickets by status")
    parser.add_argument("--shares", default=None, help="Shares for --create-exit-ticket; blank means all open shares")
    parser.add_argument("--exit-price", default=None, help="Override exit price for --create-exit-ticket; blank uses market/current price")
    parser.add_argument("--target-price", default=None, help="Target price for --set-position-plan; blank clears")
    parser.add_argument("--stop-price", default=None, help="Stop price for --set-position-plan; blank clears")
    parser.add_argument("--max-hold-days", default=None, help="Review-due day limit for --set-position-plan; blank clears")
    parser.add_argument("--position-status", default="active", help="active, watch, reduce, or exit_planned")
    parser.add_argument("--create-ticket", help="Create a paper trade ticket for a Gamma market ID")
    parser.add_argument("--ticket-detail", help="Show a paper trade ticket by ID")
    parser.add_argument("--update-ticket", help="Update a paper trade ticket by ID")
    parser.add_argument("--ticket-status", default="draft_review", help="Status to use with --update-ticket")
    parser.add_argument("--ticket-status-filter", default=None, help="Filter --trade-tickets by status")
    parser.add_argument("--max-opportunities", type=int, default=50, help="Maximum rows for --opportunity-engine")
    parser.add_argument("--probabilities", action="store_true", help="Show probability model v1 edges")
    parser.add_argument("--strategy", action="store_true", help="Show paper strategy rules")
    parser.add_argument("--recommendations", action="store_true", help="Show paper strategy recommendations")
    parser.add_argument("--run-backtest", action="store_true", help="Run snapshot-to-snapshot paper strategy backtest")
    parser.add_argument("--backtests", action="store_true", help="List saved backtest result files")
    parser.add_argument("--min-edge", type=float, default=0.02, help="Minimum model edge for recommendations/backtest")
    parser.add_argument("--min-confidence", type=float, default=35.0, help="Minimum confidence score for recommendations/backtest")
    parser.add_argument("--max-trades-per-snapshot", type=int, default=5, help="Max backtest trades per snapshot")
    parser.add_argument("--portfolio", action="store_true", help="Show local paper-trading portfolio")
    parser.add_argument("--risk", action="store_true", help="Show paper risk status and configured limits")
    parser.add_argument("--risk-check", help="Run a paper risk pre-check for a market ID")
    parser.add_argument("--trades", action="store_true", help="Show paper-trading journal")
    parser.add_argument("--paper-analytics", action="store_true", help="Show paper-trading performance analytics")
    parser.add_argument("--export-trades", help="Export paper-trading journal to a CSV file")
    parser.add_argument("--alerts", action="store_true", help="Show local paper/risk/model alerts")
    parser.add_argument("--notes", action="store_true", help="Show local market research notes")
    parser.add_argument("--sources", action="store_true", help="Show local research source registry")
    parser.add_argument("--evidence", action="store_true", help="List saved market evidence packets")
    parser.add_argument("--evidence-detail", help="Show saved evidence packet JSON by filename")
    parser.add_argument("--evidence-score", help="Score evidence readiness by packet filename or market ID")
    parser.add_argument("--evidence-probability", help="Show evidence-adjusted probability for a Gamma market ID")
    parser.add_argument("--evidence-probabilities", action="store_true", help="Show evidence-adjusted probabilities for top markets")
    parser.add_argument("--collect-evidence", help="Create a saved evidence packet for a Gamma market ID")
    parser.add_argument("--include-weak-sources", action="store_true", help="Include social/weak-signal links when creating an evidence packet")
    parser.add_argument("--source-status", action="store_true", help="Check live availability of research source home pages")
    parser.add_argument("--source-timeout", type=float, default=4.0, help="Timeout seconds for --source-status")
    parser.add_argument("--collection-targets", help="Generate prioritized data collection targets for a Gamma market ID")
    parser.add_argument("--source-category", default=None, help="Filter source registry/source links by category")
    parser.add_argument("--source-links", help="Generate no-key research source links for a query")
    parser.add_argument("--source-pack", help="Generate a source pack for a Gamma market ID")
    parser.add_argument("--market-notes", help="Show notes for a specific market ID")
    parser.add_argument("--add-note", help="Add a local note to a market ID")
    parser.add_argument("--note-text", default="", help="Text for --add-note")
    parser.add_argument("--note-tag", default="research", help="Tag for --add-note")
    parser.add_argument("--delete-note", help="Delete a local note by note ID")
    # v1.6.0 Scoped backfill and category dataset commands. Operator-controlled; never trade.
    parser.add_argument("--data-scopes", action="store_true", help="List market/category data scopes")
    parser.add_argument("--register-data-scope", action="store_true", help="Register a reusable scoped/category data filter")
    parser.add_argument("--preview-data-scope", action="store_true", help="Preview an existing scope by --scope-id")
    parser.add_argument("--export-data-scopes", help="Export data scopes CSV")
    parser.add_argument("--data-backfills", action="store_true", help="List scoped historical backfill jobs")
    parser.add_argument("--data-backfill-detail", default="", help="Show one scoped backfill job")
    parser.add_argument("--preview-data-backfill", action="store_true", help="Preview scoped backfill size/pagination/dedup plan")
    parser.add_argument("--start-data-backfill", action="store_true", help="Start/record a gated scoped backfill plan")
    parser.add_argument("--pause-data-backfill", default="", help="Pause a scoped backfill job ID")
    parser.add_argument("--cancel-data-backfill", default="", help="Cancel a scoped backfill job ID")
    parser.add_argument("--export-data-backfills", help="Export scoped backfills CSV")
    parser.add_argument("--training-category-datasets", action="store_true", help="List scoped/category training dataset builds")
    parser.add_argument("--preview-training-category-dataset", action="store_true", help="Preview a scoped/category training dataset")
    parser.add_argument("--build-training-category-dataset", action="store_true", help="Build a scoped/category training dataset metadata record")
    parser.add_argument("--export-training-category-datasets", help="Export category datasets CSV")
    parser.add_argument("--scope-id", default="", help="Data scope ID")
    parser.add_argument("--scope-type", default="category", help="Data scope type")
    parser.add_argument("--category", default="", help="Category/theme for scoped datasets")
    parser.add_argument("--keywords", default="", help="Comma-separated scope keywords")
    parser.add_argument("--market-ids", default="", help="Comma-separated market IDs")
    parser.add_argument("--condition-ids", default="", help="Comma-separated condition IDs")
    parser.add_argument("--event-slugs", default="", help="Comma-separated event slugs")
    parser.add_argument("--market-slugs", default="", help="Comma-separated market slugs")
    parser.add_argument("--date-start", default="", help="Scope start date")
    parser.add_argument("--date-end", default="", help="Scope end date")
    parser.add_argument("--resolved-only", action="store_true", help="Scope resolved markets only")
    parser.add_argument("--active-only", action="store_true", help="Scope active markets only")
    parser.add_argument("--min-volume", type=float, default=0.0, help="Scope minimum volume")
    parser.add_argument("--min-liquidity", type=float, default=0.0, help="Scope minimum liquidity")
    parser.add_argument("--max-markets", type=int, default=1000, help="Scope maximum markets")
    parser.add_argument("--max-records", type=int, default=100000, help="Scope/backfill/category dataset maximum records")
    parser.add_argument("--max-rows", type=int, default=0, help="Category dataset or host training maximum rows")
    parser.add_argument("--max-requests", type=int, default=100, help="Backfill max requests")
    parser.add_argument("--max-runtime-seconds", type=int, default=300, help="Backfill max runtime seconds")
    parser.add_argument("--pagination-method", default="offset_limit", help="Backfill pagination method")
    parser.add_argument("--page-size", type=int, default=1000, help="Backfill page size")
    parser.add_argument("--max-pages", type=int, default=10, help="Backfill max pages")
    parser.add_argument("--batch-size", type=int, default=1000, help="Backfill/training batch size")

    # v1.5.0 Internet ingestion + host training jobs. Disabled by default; never trade.
    parser.add_argument("--internet-data-sources", action="store_true", help="List approved internet data source registry rows")
    parser.add_argument("--register-internet-data-source", action="store_true", help="Register disabled-by-default internet source metadata")
    parser.add_argument("--validate-internet-data-source", action="store_true", help="Validate an internet source against gates and allowlists")
    parser.add_argument("--export-internet-data-sources", help="Export internet data source registry CSV")
    parser.add_argument("--preview-internet-data-ingestion", action="store_true", help="Preview internet ingestion without network by default")
    parser.add_argument("--run-internet-data-ingestion", action="store_true", help="Run gated internet ingestion only when env/allowlist/confirmation gates pass")
    parser.add_argument("--internet-ingestion-schedules", action="store_true", help="List disabled-by-default internet ingestion schedules")
    parser.add_argument("--register-internet-ingestion-schedule", action="store_true", help="Register a disabled internet ingestion schedule")
    parser.add_argument("--preview-due-internet-ingestion", action="store_true", help="Preview due ingestion schedules without running them")
    parser.add_argument("--internet-training-workflow", action="store_true", help="Show internet-to-training operator workflow")
    parser.add_argument("--training-host-jobs", action="store_true", help="List host training job registry rows")
    parser.add_argument("--training-job-caps", action="store_true", help="Show configured host training row/runtime/artifact caps")
    parser.add_argument("--training-host-job-detail", help="Show one host training job by ID")
    parser.add_argument("--preview-training-host-job", action="store_true", help="Preview a host training job without starting it")
    parser.add_argument("--start-training-host-job", action="store_true", help="Start a gated approved internal host training job")
    parser.add_argument("--run-dataset-quality-scan", action="store_true", help="Run a gated dataset quality scan host job")
    parser.add_argument("--run-signal-generation-preview", action="store_true", help="Run a gated manual-review-only signal generation preview host job")
    parser.add_argument("--cancel-training-host-job", help="Cancel/mark cancelled a host training job by ID")
    parser.add_argument("--export-training-host-jobs", help="Export host training jobs CSV")
    parser.add_argument("--base-url", default="", help="Internet data source base URL")
    parser.add_argument("--endpoint-path", default="", help="Internet data source endpoint path")
    parser.add_argument("--allowed-domain", default="", help="Internet data source allowed domain")
    parser.add_argument("--query-params", default="", help="Internet data source query params as JSON or query string")
    parser.add_argument("--schedule-id", default="", help="Internet ingestion schedule ID")
    parser.add_argument("--interval-minutes", type=int, default=60, help="Internet ingestion schedule interval")
    parser.add_argument("--max-runs-per-day", type=int, default=24, help="Internet ingestion schedule max runs per day")
    parser.add_argument("--host-training-job-id", default="", help="Host training job ID")
    parser.add_argument("--job-type", default="baseline_training", help="Host training job type")
    parser.add_argument("--training-max-rows", type=int, default=0, help="Optional host training row cap override")
    parser.add_argument("--confirmation", default="", help="Explicit operator confirmation phrase for gated actions")
    # v1.3.0 Data Ingestion + Dataset Builder commands. Local-first; never trade.
    parser.add_argument("--data-status", action="store_true", help="Show local data ingestion status")
    parser.add_argument("--data-sources", action="store_true", help="List data source registry rows")
    parser.add_argument("--register-data-source", action="store_true", help="Register a local-first data source")
    parser.add_argument("--export-data-sources", help="Export data source registry CSV")
    parser.add_argument("--data-ingestion-jobs", action="store_true", help="List data ingestion jobs")
    parser.add_argument("--preview-data-ingestion", action="store_true", help="Preview a data ingestion job without recording raw rows")
    parser.add_argument("--run-data-ingestion", action="store_true", help="Run explicit local data ingestion")
    parser.add_argument("--export-data-ingestion-jobs", help="Export data ingestion jobs CSV")
    parser.add_argument("--data-snapshots", action="store_true", help="List raw snapshot registry rows")
    parser.add_argument("--data-snapshot-detail", help="Show one raw snapshot metadata row")
    parser.add_argument("--export-data-snapshots", help="Export raw snapshot registry CSV")
    parser.add_argument("--data-normalized-records", action="store_true", help="List normalized data records")
    parser.add_argument("--preview-data-normalization", action="store_true", help="Preview normalization for a raw snapshot")
    parser.add_argument("--run-data-normalization", action="store_true", help="Run normalization for a raw snapshot")
    parser.add_argument("--export-data-normalized-records", help="Export normalized data records CSV")
    parser.add_argument("--data-labels", action="store_true", help="List labels from the labeling workbench")
    parser.add_argument("--preview-data-labels", action="store_true", help="Preview label generation")
    parser.add_argument("--generate-data-labels", action="store_true", help="Generate local labels from normalized records")
    parser.add_argument("--review-data-label", action="store_true", help="Review/approve/reject a generated label")
    parser.add_argument("--export-data-labels", help="Export labels CSV")
    parser.add_argument("--training-dataset-builder-status", action="store_true", help="Show dataset builder status")
    parser.add_argument("--preview-training-dataset-build", action="store_true", help="Preview a reproducible Training Lab dataset build")
    parser.add_argument("--build-training-dataset", action="store_true", help="Build a local generated Training Lab dataset")
    parser.add_argument("--training-dataset-builds", action="store_true", help="List dataset build registry rows")
    parser.add_argument("--training-dataset-build-manifest", action="store_true", help="Show a dataset build manifest by --dataset-build-id")
    parser.add_argument("--export-training-dataset-builds", help="Export dataset build registry CSV")
    parser.add_argument("--source-id", default="", help="Data source ID or comma-separated source IDs")
    parser.add_argument("--source-type", default="custom_csv", help="Data source type")
    parser.add_argument("--dataset-build-id", default="", help="Dataset build ID")
    parser.add_argument("--record-id", default="", help="Normalized record ID")
    parser.add_argument("--label-id", default="", help="Label ID")
    parser.add_argument("--label-type", default="price_movement_over_horizon", help="Label type or comma-separated label types")
    parser.add_argument("--label-status", default="label_approved", help="Label review status")
    parser.add_argument("--endpoint-name", default="", help="Optional endpoint name for network source metadata")
    parser.add_argument("--data-mode", default="local_import", help="Data source or ingestion mode")
    parser.add_argument("--horizon", default="1h", help="Labeling horizon/window")
    parser.add_argument("--split-method", default="chronological", help="Dataset builder split method")
    # v1.2.0 Training & Evaluation Lab commands. Offline only; never submit/cancel or touch wallets.
    parser.add_argument("--training-status", action="store_true", help="Show Training & Evaluation Lab status")
    parser.add_argument("--training-datasets", action="store_true", help="List training dataset registry rows")
    parser.add_argument("--training-dataset-detail", help="Show one training dataset by dataset ID")
    parser.add_argument("--register-training-dataset", action="store_true", help="Register local training dataset metadata")
    parser.add_argument("--validate-training-dataset", action="store_true", help="Validate a local dataset without registering it")
    parser.add_argument("--export-training-datasets", help="Export training datasets registry CSV")
    parser.add_argument("--training-features", action="store_true", help="List training feature sets")
    parser.add_argument("--build-training-features-preview", action="store_true", help="Preview a deterministic training feature set")
    parser.add_argument("--register-training-feature-set", action="store_true", help="Register a deterministic training feature set")
    parser.add_argument("--export-training-features", help="Export training feature sets CSV")
    parser.add_argument("--training-runs", action="store_true", help="List local training runs")
    parser.add_argument("--preview-training-run", action="store_true", help="Preview a local baseline training run")
    parser.add_argument("--start-training-run", action="store_true", help="Run a lightweight local baseline training job")
    parser.add_argument("--export-training-runs", help="Export training runs CSV")
    parser.add_argument("--training-models", action="store_true", help="List training model registry")
    parser.add_argument("--register-training-model", action="store_true", help="Register a manual-review-only model artifact row")
    parser.add_argument("--export-training-models", help="Export training model registry CSV")
    parser.add_argument("--training-backtests", action="store_true", help="List offline training backtests")
    parser.add_argument("--preview-training-backtest", action="store_true", help="Preview an offline backtest")
    parser.add_argument("--run-training-backtest", action="store_true", help="Record an offline backtest result")
    parser.add_argument("--export-training-backtests", help="Export training backtests CSV")
    parser.add_argument("--preview-training-signals", action="store_true", help="Preview training-generated manual-review signals")
    parser.add_argument("--queue-training-signals", action="store_true", help="Queue training-generated signals into the strategy signal ledger for manual review")
    parser.add_argument("--dataset-id", default="", help="Training dataset ID")
    parser.add_argument("--feature-set-id", default="", help="Training feature set ID")
    parser.add_argument("--training-run-id", default="", help="Training run ID")
    parser.add_argument("--model-id", default="", help="Training model ID")
    parser.add_argument("--backtest-id", default="", help="Training backtest ID")
    parser.add_argument("--dataset-path", default="", help="Local dataset path for Training Lab commands")
    parser.add_argument("--dataset-type", default="custom_csv", help="Training dataset type")
    parser.add_argument("--name", default="", help="Name for training dataset/feature/run/model rows")
    parser.add_argument("--model-type", default="heuristic_baseline", help="Training model type")
    parser.add_argument("--target", default="", help="Training target column")
    parser.add_argument("--feature-groups", default="market_metadata,spread_liquidity,execution_quality", help="Comma-separated feature groups")
    parser.add_argument("--lookback-window", default="", help="Training feature lookback window")
    parser.add_argument("--prediction-horizon", default="", help="Training prediction horizon")
    parser.add_argument("--json", action="store_true", help="Emit JSON for commands that support table output")
    parser.add_argument("--reset-paper", type=float, nargs="?", const=10000.0, help="Reset paper portfolio to optional cash amount")
    parser.add_argument("--paper-buy", help="Paper buy YES for a market ID")
    parser.add_argument("--paper-sell", help="Paper sell all YES shares for a market ID")
    parser.add_argument("--stake", type=float, default=100.0, help="Paper trade stake")
    parser.add_argument("--outcome", default="YES", help="Paper trade outcome")
    parser.add_argument("--reason", default="", help="Paper trade journal reason")
    parser.add_argument("--snapshot", action="store_true", help="Save current market pull to data/snapshots")
    parser.add_argument("--movers", action="store_true", help="Compare current market pull to latest saved snapshot")
    parser.add_argument("--new", action="store_true", help="When used with --movers, also show markets not present in latest snapshot")
    parser.add_argument("--snapshots", action="store_true", help="List locally saved snapshots")
    parser.add_argument("--search", help="Search Gamma public-search and print raw JSON")
    parser.add_argument("--book", help="Read a public CLOB order book for a token ID")
    parser.add_argument("--market-books", help="Read public CLOB order books for a Gamma market ID")
    parser.add_argument("--research", help="Build a local research packet for a Gamma market ID")
    parser.add_argument("--watchlist", action="store_true", help="List locally watched markets")
    parser.add_argument("--market-data-snapshots", action="store_true", help="Show v0.9.0 local market-data/order-book snapshot records")
    parser.add_argument("--market-data-snapshot-detail", help="Show one market-data snapshot by snapshot ID")
    parser.add_argument("--record-market-data-snapshot", action="store_true", help="Record a local market-data snapshot from --orderbook-json")
    parser.add_argument("--parse-market-data-snapshot-preview", action="store_true", help="Parse and preview market-data metrics from --orderbook-json without saving")
    parser.add_argument("--fetch-market-data-snapshot-preview", action="store_true", help="Show optional public-fetch boundary status without saving")
    parser.add_argument("--fetch-market-data-snapshot-record", action="store_true", help="Attempt explicit public-fetch record boundary; disabled/unimplemented by default")
    parser.add_argument("--export-market-data-snapshots", help="Export market-data snapshots to CSV")
    parser.add_argument("--execution-quality", action="store_true", help="Show v0.9.0 execution-quality simulation records")
    parser.add_argument("--execution-quality-detail", help="Show one execution-quality simulation by simulation ID")
    parser.add_argument("--preview-execution-quality", action="store_true", help="Preview execution quality against a local snapshot without saving")
    parser.add_argument("--record-execution-quality", action="store_true", help="Record a local execution-quality simulation without submitting")
    parser.add_argument("--export-execution-quality", help="Export execution-quality simulations to CSV")
    parser.add_argument("--market-id", default="", help="Market ID for market-data and execution-quality commands")
    parser.add_argument("--condition-id", default="", help="Condition ID for local market-data JSON workflows")
    parser.add_argument("--token-id", default="", help="Token/asset ID for market-data and execution-quality commands")
    parser.add_argument("--side", default="BUY", help="BUY or SELL for execution-quality simulation")
    parser.add_argument("--price", type=float, default=0.5, help="Limit price for execution-quality simulation")
    parser.add_argument("--size", type=float, default=1.0, help="Size/shares for execution-quality simulation")
    parser.add_argument("--order-type", default="limit", help="Order type for execution-quality simulation")
    parser.add_argument("--time-in-force", default="GTC", help="Time in force for execution-quality simulation")
    parser.add_argument("--snapshot-id", default="", help="Snapshot ID for execution-quality simulation")
    parser.add_argument("--orderbook-json", default="{}", help="Order-book JSON object or @path for market-data snapshot commands")
    parser.add_argument("--market-data-status", help="Filter market-data snapshots by status")
    parser.add_argument("--execution-quality-state", help="Filter execution-quality simulations by state")
    parser.add_argument("--max-spread-bps", type=float, default=None, help="Override max spread bps for execution-quality simulation")
    parser.add_argument("--max-slippage-bps", type=float, default=None, help="Override max slippage bps for execution-quality simulation")
    parser.add_argument("--source", default="local_fixture", help="Source label for local market-data snapshots")
    parser.add_argument("--live-config-readiness", action="store_true", help="Show v0.5.11 redacted live configuration readiness fields")
    parser.add_argument("--export-live-config-readiness", help="Export live configuration readiness fields to CSV")
    parser.add_argument("--export-live-config-template", help="Export a blank .env template for future live configuration fields")
    parser.add_argument("--live-adapter-readiness", action="store_true", help="Show v0.6.0 live adapter readiness and capability report")
    parser.add_argument("--export-live-adapter-readiness", help="Export live adapter readiness report to CSV")
    parser.add_argument("--live-adapter-readonly-validations", action="store_true", help="List saved v0.6.0 read-only live adapter validation receipts")
    parser.add_argument("--preview-live-adapter-readonly-validation", action="store_true", help="Preview optional read-only adapter validation without saving")
    parser.add_argument("--record-live-adapter-readonly-validation", action="store_true", help="Record optional read-only adapter validation if explicitly enabled by configuration")
    parser.add_argument("--live-adapter-validation-detail", help="Show one read-only live adapter validation receipt by validation ID")
    parser.add_argument("--live-adapter-validation-status", help="Filter read-only live adapter validation receipts by status")
    parser.add_argument("--export-live-adapter-validations", help="Export read-only live adapter validation receipts to CSV")
    parser.add_argument("--live-adapter-requests", action="store_true", help="Show v0.6.0 live adapter request validation records")
    parser.add_argument("--preview-live-adapter-request", action="store_true", help="Preview adapter request validation for an execution packet without saving")
    parser.add_argument("--record-live-adapter-request", action="store_true", help="Record adapter request validation for an execution packet without submitting")
    parser.add_argument("--live-adapter-request-detail", help="Show one adapter request by request ID or packet ID")
    parser.add_argument("--live-adapter-request-status", help="Filter live adapter request validations by status")
    parser.add_argument("--live-adapter-request-packet-id", help="Execution packet ID used to preview/record/filter adapter request validations")
    parser.add_argument("--export-live-adapter-requests", help="Export live adapter request validations to CSV")
    parser.add_argument("--manual-execution-reviews", action="store_true", help="Show v0.6.0 manual execution boundary review records")
    parser.add_argument("--preview-manual-execution-review", action="store_true", help="Preview manual execution review without saving or submitting")
    parser.add_argument("--record-manual-execution-review", action="store_true", help="Record manual execution review without submitting")
    parser.add_argument("--manual-execution-review-detail", help="Show one manual execution review by review ID")
    parser.add_argument("--manual-execution-review-status", help="Filter manual execution reviews by status")
    parser.add_argument("--manual-execution-review-packet-id", help="Execution packet ID used to preview/record/filter manual execution reviews")
    parser.add_argument("--manual-execution-ack", action="store_true", help="Set the local final acknowledgement flag for manual execution review records")
    parser.add_argument("--export-manual-execution-reviews", help="Export manual execution reviews to CSV")
    parser.add_argument("--live-adapter-operator", default="", help="Operator label for live adapter validation/request/manual review commands")
    parser.add_argument("--live-adapter-note", default="", help="Operator note for live adapter validation/request/manual review commands")
    parser.add_argument("--live-execution-control-readiness", action="store_true", help="Show v0.9.0 manual live execution control-plane readiness")
    parser.add_argument("--export-live-execution-control-readiness", help="Export manual live execution control-plane readiness to CSV")
    parser.add_argument("--live-execution-attempts", action="store_true", help="Show v0.9.0 manual live execution attempt ledger records")
    parser.add_argument("--live-execution-attempt-detail", help="Show one live execution attempt by attempt ID")
    parser.add_argument("--preview-live-manual-submit", action="store_true", help="Preview a final manual submit attempt without saving state")
    parser.add_argument("--record-live-manual-submit", action="store_true", help="Record a final manual submit attempt; fake-local only can simulate a receipt")
    parser.add_argument("--preview-live-manual-cancel", action="store_true", help="Preview a final manual cancel attempt without saving state")
    parser.add_argument("--record-live-manual-cancel", action="store_true", help="Record a final manual cancel attempt; fake-local only can simulate a receipt")
    parser.add_argument("--live-execution-attempt-status", help="Filter live execution attempts by status")
    parser.add_argument("--live-execution-attempt-adapter-mode", help="Filter live execution attempts by adapter mode")
    parser.add_argument("--live-execution-attempt-action", help="Filter live execution attempts by action: submit or cancel")
    parser.add_argument("--export-live-execution-attempts", help="Export live execution attempts to CSV")
    parser.add_argument("--adapter-request-id", help="Adapter request ID used for manual submit preview/attempts")
    parser.add_argument("--packet-id", help="Execution packet ID used for attempt filters")
    parser.add_argument("--intent-id", help="Live order intent ID used for attempt filters")
    parser.add_argument("--operator", default="", help="Operator label for manual live execution control-plane commands")
    parser.add_argument("--final-confirmation", default="", help="Final confirmation phrase for manual submit/cancel attempts; never stored raw")
    parser.add_argument("--adapter-mode", default="", help="Manual adapter mode: blocked, fake_local, or real_live")
    parser.add_argument("--original-attempt-id", default="", help="Original submit attempt ID for manual cancel")
    parser.add_argument("--fake-order-id", default="", help="Fake-local or exchange order ID for manual cancel")
    parser.add_argument("--order-id", default="", help="Alias for fake/exchange order ID for manual cancel")
    parser.add_argument("--cancel-reason", default="", help="Required reason for manual cancel preview/attempt")

    parser.add_argument("--live-trading-status", action="store_true", help="Show consolidated guarded live trading status")
    parser.add_argument("--live-clob-adapter-status", action="store_true", help="Show v1.0.0 CLOB adapter boundary and manual-live SDK readiness status")
    parser.add_argument("--export-live-clob-adapter-status", help="Export live CLOB adapter boundary status to CSV")
    parser.add_argument("--live-clob-adapter-verify", action="store_true", help="Run offline/default-safe CLOB adapter verification report")
    parser.add_argument("--live-clob-adapter-verification-report", action="store_true", help="Show latest/default CLOB adapter verification report")
    parser.add_argument("--export-live-clob-adapter-verification", help="Export CLOB adapter verification report to CSV")
    parser.add_argument("--request-readonly-network", action="store_true", help="Request readonly network check readiness; normal validation still does not network")
    parser.add_argument("--request-real-smoke", action="store_true", help="Request real smoke-test readiness; normal validation still blocks submit/cancel")
    parser.add_argument("--live-readiness-checklist", action="store_true", help="Show operator live readiness checklist")
    parser.add_argument("--export-live-readiness-checklist", help="Export live readiness checklist to CSV")
    parser.add_argument("--operator-runbook", action="store_true", help="Show live operations runbook")
    parser.add_argument("--live-orders", action="store_true", help="Show v0.10.0 local live order ledger events")
    parser.add_argument("--live-order-detail", help="Show one live order event by event ID")
    parser.add_argument("--export-live-orders", help="Export live order ledger events to CSV")
    parser.add_argument("--preview-live-submit", action="store_true", help="Alias for manual submit preview through the live control plane")
    parser.add_argument("--record-live-submit", action="store_true", help="Alias for manual submit attempt through the live control plane")
    parser.add_argument("--preview-live-cancel", action="store_true", help="Alias for manual cancel preview through the live control plane")
    parser.add_argument("--record-live-cancel", action="store_true", help="Alias for manual cancel attempt through the live control plane")
    parser.add_argument("--live-reconciliation", action="store_true", help="Show v0.10.0 read-only live reconciliation scaffold")
    parser.add_argument("--record-live-reconciliation", action="store_true", help="Record/display read-only reconciliation scaffold; no network/cancel/submit")
    parser.add_argument("--export-live-reconciliation", help="Export live reconciliation rows to CSV")
    parser.add_argument("--strategy-signals", action="store_true", help="Show v0.10.0 deterministic strategy signal records")
    parser.add_argument("--strategy-signal-detail", help="Show one strategy signal by signal ID")
    parser.add_argument("--record-strategy-signal", action="store_true", help="Record a deterministic strategy signal")
    parser.add_argument("--validate-strategy-signal", action="store_true", help="Validate a strategy signal without saving")
    parser.add_argument("--strategy-id", default="manual", help="Strategy ID for strategy signal/autonomous filters")
    parser.add_argument("--confidence", type=float, default=0.0, help="Confidence for strategy signal validation/recording")
    parser.add_argument("--rationale", default="", help="Rationale for strategy signal recording")
    parser.add_argument("--expires-at", default="", help="Optional ISO expiration for strategy signal")
    parser.add_argument("--adapter-request-id-for-signal", default="", help="Optional adapter request ID to bind a strategy signal")
    parser.add_argument("--export-strategy-signals", help="Export strategy signals to CSV")
    parser.add_argument("--autonomous-trading-status", action="store_true", help="Show v0.10.0 autonomous trading status")
    parser.add_argument("--preview-autonomous-run", action="store_true", help="Preview an autonomous run without saving or network")
    parser.add_argument("--record-autonomous-run", action="store_true", help="Record an autonomous run decision ledger without real network")
    parser.add_argument("--autonomous-runs", action="store_true", help="Show autonomous run ledger")
    parser.add_argument("--autonomous-run-detail", help="Show one autonomous run by run ID")
    parser.add_argument("--mode", default="off", help="Autonomous mode: off, dry_run, paper_only, fake_adapter, live_guarded")
    parser.add_argument("--export-autonomous-runs", help="Export autonomous run ledger to CSV")

    parser.add_argument("--live-order-intents", action="store_true", help="Show v0.5.11 local non-executing live-order intent previews")
    parser.add_argument("--preview-live-order-intent", action="store_true", help="Preview a live-order intent without saving or executing it")
    parser.add_argument("--record-live-order-intent", action="store_true", help="Record a local live-order intent preview without executing it")
    parser.add_argument("--live-order-intent-detail", help="Show one saved live-order intent preview by ID")
    parser.add_argument("--live-intent-status", help="Filter live-order intents by status")
    parser.add_argument("--live-intent-market", help="Market ID for live-order intent preview/list filtering")
    parser.add_argument("--live-intent-token-id", default="", help="Future CLOB token/asset ID for live-order intent preview")
    parser.add_argument("--live-intent-outcome", default="YES", help="Outcome label for live-order intent preview")
    parser.add_argument("--live-intent-side", default="BUY", help="BUY or SELL for live-order intent preview")
    parser.add_argument("--live-intent-order-type", default="limit", help="limit or marketable_limit for live-order intent preview")
    parser.add_argument("--live-intent-time-in-force", default="GTC", help="GTC, FOK, or FAK for live-order intent preview")
    parser.add_argument("--live-intent-price", type=float, default=0.5, help="Limit price for live-order intent preview")
    parser.add_argument("--live-intent-size", type=float, default=1.0, help="Size/shares for live-order intent preview")
    parser.add_argument("--live-intent-operator", default="local", help="Operator label for live-order intent preview")
    parser.add_argument("--live-intent-note", default="", help="Operator note for live-order intent preview")
    parser.add_argument("--live-intent-source-ticket-id", default="", help="Optional source paper ticket ID for live-order intent preview")
    parser.add_argument("--live-intent-source-approval-id", default="", help="Optional source paper approval ID for live-order intent preview")
    parser.add_argument("--export-live-order-intents", help="Export saved live-order intent previews to CSV")
    parser.add_argument("--live-order-intent-preflight", action="store_true", help="Show v0.5.11 read-only live-intent preflight/governance binding review")
    parser.add_argument("--live-order-intent-preflight-detail", help="Show one live-intent preflight review by intent ID")
    parser.add_argument("--live-preflight-state", help="Filter live-intent preflight by state")
    parser.add_argument("--export-live-order-intent-preflight", help="Export live-intent preflight reviews to CSV")
    parser.add_argument("--live-order-authorizations", action="store_true", help="Show v0.5.11 local non-executing live operator authorization snapshots")
    parser.add_argument("--record-live-order-authorization", help="Record a local authorization/reject/defer snapshot for a saved live-order intent ID")
    parser.add_argument("--live-order-authorization-detail", help="Show one saved live operator authorization by authorization ID")
    parser.add_argument("--live-authorization-decision", default="authorize", help="Decision for --record-live-order-authorization: authorize, reject, or defer")
    parser.add_argument("--live-authorization-decision-filter", help="Filter live authorizations by decision")
    parser.add_argument("--live-authorization-status", help="Filter live authorizations by status")
    parser.add_argument("--live-authorization-intent-id", help="Filter live authorizations by source intent ID")
    parser.add_argument("--live-authorization-ack", action="store_true", help="Acknowledge that authorization snapshots are non-executing and do not submit orders")
    parser.add_argument("--export-live-order-authorizations", help="Export live operator authorization records to CSV")
    parser.add_argument("--live-execution-packets", action="store_true", help="Show v0.5.11 unsigned local live execution packets")
    parser.add_argument("--preview-live-execution-packet", action="store_true", help="Preview an unsigned live execution packet without saving or executing it")
    parser.add_argument("--record-live-execution-packet", action="store_true", help="Record an unsigned live execution packet without signing or submitting it")
    parser.add_argument("--live-execution-packet-detail", help="Show one saved live execution packet by packet ID")
    parser.add_argument("--live-execution-packet-status", help="Filter live execution packets by status")
    parser.add_argument("--live-execution-packet-intent-id", help="Intent ID used to preview/record/filter live execution packets")
    parser.add_argument("--live-execution-packet-authorization-id", help="Authorization ID used to preview/record/filter live execution packets")
    parser.add_argument("--export-live-execution-packets", help="Export unsigned live execution packets to CSV")
    parser.add_argument("--live-dry-run-adapter", action="store_true", help="Show v0.5.11 offline dry-run adapter receipts for execution packets")
    parser.add_argument("--preview-live-dry-run-adapter", action="store_true", help="Preview an offline dry-run adapter receipt without saving or sending network requests")
    parser.add_argument("--record-live-dry-run-adapter", action="store_true", help="Record an offline dry-run adapter receipt without signing or submitting")
    parser.add_argument("--live-dry-run-receipt-detail", help="Show one saved live dry-run adapter receipt by receipt ID")
    parser.add_argument("--live-dry-run-status", help="Filter live dry-run adapter receipts by status")
    parser.add_argument("--live-dry-run-packet-id", help="Execution packet ID used to preview/record/filter dry-run adapter receipts")
    parser.add_argument("--export-live-dry-run-adapter", help="Export live dry-run adapter receipts to CSV")
    parser.add_argument("--live-dry-run-review", action="store_true", help="Show v0.5.11 read-only review of packets against latest dry-run receipts")
    parser.add_argument("--live-dry-run-review-detail", help="Show dry-run review detail for one execution packet ID")
    parser.add_argument("--live-dry-run-review-state", help="Filter dry-run review by state: validated_ready, validated_with_warnings, needs_dry_run_receipt, stale_dry_run_receipt, dry_run_blocked, packet_blocked, invalid")
    parser.add_argument("--export-live-dry-run-review", help="Export live dry-run review rows to CSV")
    parser.add_argument("--keys", action="store_true", help="Show redacted API-key readiness and when keys become necessary")
    parser.add_argument("--add-watch", action="store_true", help="When used with --research, add/update the market in the local watchlist")
    parser.add_argument("--remove-watch", help="Remove a market ID from the local watchlist")
    parser.add_argument("--note", default="", help="Optional note for --add-watch")
    args = parser.parse_args()
    if (args.markets or args.opportunities or args.movers) and args.sort == "volume_24hr":
        args.sort = "volume24hr"
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
