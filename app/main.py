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
from .paper_trading import buy as paper_buy, sell as paper_sell, reset_portfolio, summarize_portfolio, load_trades, load_portfolio
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
    build_live_v2_readiness,
    build_live_v2_settings_sections,
    build_live_v2_status,
    build_live_v2_ticket_preview,
    cancel_live_v2_order,
    emergency_live_v2_action,
    get_live_v2_open_orders,
    get_live_v2_orderbook,
    get_live_v2_positions,
    list_audit_records as list_live_v2_audit_records,
    reconcile_live_v2_orders,
    search_live_v2_markets,
    submit_live_v2_order,
    validate_live_v2_settings_payload,
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

app = FastAPI(title="Polymarket Gamma Starter", version=APP_VERSION_SHORT)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
templates.env.globals.update(console_globals())
templates.env.filters["status_tone"] = status_tone
templates.env.filters["compact_id"] = compact_id
client = GammaClient()
clob = ClobClient()



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
async def api_live_v2_audit(limit: int = 200):
    rows = list_live_v2_audit_records(limit=limit)
    return {"items": rows, "count": len(rows)}


@app.get("/api/v2/live/audit.csv", response_class=PlainTextResponse)
async def api_live_v2_audit_csv():
    return live_v2_audit_to_csv(list_live_v2_audit_records(limit=10000))


@app.get("/api/v2/live/audit.md", response_class=PlainTextResponse)
async def api_live_v2_audit_markdown():
    return live_v2_audit_to_markdown(list_live_v2_audit_records(limit=500))


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
    markets = attach_probability(attach_scores(raw_markets))
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
        },
    )




@app.get("/operator", response_class=HTMLResponse)
async def operator_dashboard(request: Request, limit: int = Query(default=75, ge=10, le=200)):
    previous = load_latest()
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
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
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
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


@app.get("/opportunities", response_class=HTMLResponse)
async def opportunities_page(request: Request, limit: int = Query(default=100, ge=10, le=200)):
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
    markets = attach_evidence_probability(markets)
    rows = rank_opportunities(markets, watchlist=load_watchlist(), max_items=50)
    return templates.TemplateResponse(
        "opportunities.html",
        {
            "request": request,
            "user": current_user(request),
            "limit": limit,
            "opportunities": rows,
            "summary": opportunity_summary(rows),
        },
    )


@app.get("/api/opportunities/engine")
async def opportunity_engine_api(limit: int = Query(default=100, ge=10, le=200), max_items: int = Query(default=50, ge=1, le=100)):
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
    markets = attach_evidence_probability(markets)
    rows = rank_opportunities(markets, watchlist=load_watchlist(), max_items=max_items)
    return {
        "source": "gamma+local_evidence+paper_risk",
        "mode": "opportunity_engine_v1",
        "note": "Research and paper-trading candidate ranking only. No live trading.",
        "summary": opportunity_summary(rows),
        "items": rows,
    }


@app.get("/markets/{market_id}", response_class=HTMLResponse)
async def market_detail(request: Request, market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = attach_probability(attach_scores([market]))[0]
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
    scored = attach_probability(attach_scores([market]))[0]
    return {"source": "local", "mode": "evidence_adjusted_probability", "item": evidence_adjusted_probability(scored)}


@app.get("/api/evidence-probabilities")
async def evidence_probabilities_api(limit: int = Query(default=settings.default_limit, ge=1, le=100)):
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
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
    scored = attach_probability(attach_scores([market]))[0]
    return {"source": "local", "item": create_manual_evidence_packet(scored, created_by=user.get("username", "admin"), note=note, include_weak_sources=include_weak_sources)}


@app.post("/markets/{market_id}/evidence-packet")
async def create_market_evidence_packet_page(market_id: str, include_weak_sources: bool = Form(default=False), note: str = Form(default=""), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = attach_probability(attach_scores([market]))[0]
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
    scored = attach_probability(attach_scores([market]))[0]
    return {"source": "local", "item": build_market_source_pack(scored)}


@app.get("/api/sources/status")
async def sources_status_api(category: str | None = Query(default=None), timeout: float = Query(default=4.0, ge=1.0, le=10.0)):
    return {"source": "local", "mode": "live_availability_check", "result": await check_sources_status(category=category, timeout=timeout)}


@app.get("/api/markets/{market_id}/collection-targets")
async def market_collection_targets_api(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = attach_probability(attach_scores([market]))[0]
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
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit)))
    return {"source": "gamma", "summary": summarize_snapshot(markets), "items": markets}


@app.get("/api/markets/opportunities")
async def opportunities(limit: int = Query(default=settings.default_limit, ge=1, le=100)):
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit)))
    return {"source": "gamma", "note": "Probability model v1 is for paper trading only, not financial advice.", "items": markets}


@app.get("/api/markets/{market_id}")
async def market_api(market_id: str):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return {"source": "gamma", "item": attach_probability(attach_scores([market]))[0]}


@app.post("/api/snapshots")
async def create_snapshot(limit: int = Query(default=100, ge=1, le=500), user: dict = Depends(require_admin)):
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit)))
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
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit)))
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
    scored = attach_probability(attach_scores([market]))[0]
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
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
    return {"source": "local", "note": "Deterministic probability model v1 for paper trading only.", "items": markets}




@app.get("/api/alerts")
async def alerts_api(limit: int = Query(default=100, ge=1, le=500)):
    previous = load_latest()
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
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
    markets = attach_probability(attach_scores(await client.list_markets(limit=100, order="volume24hr")))
    portfolio = summarize_portfolio(markets)
    trades = load_trades()
    return {"source": "local", "mode": "paper_only", "analytics": trade_analytics(trades, portfolio), "portfolio": portfolio}


@app.get("/api/paper/trades.csv", response_class=PlainTextResponse)
async def paper_trades_csv():
    return PlainTextResponse(trades_to_csv(load_trades()), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=paper_trades.csv"})

@app.get("/api/portfolio")
async def portfolio_api(limit: int = Query(default=100, ge=1, le=500)):
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
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
        markets = attach_probability(attach_scores(await client.list_markets(limit=min(limit, 200), order="volume24hr")))
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
        markets = attach_probability(attach_scores(await client.list_markets(limit=min(limit, 200), order="volume24hr")))
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
        markets = attach_probability(attach_scores(await client.list_markets(limit=min(limit, 200), order="volume24hr")))
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
    scored = attach_probability(attach_scores([market]))[0]
    try:
        return paper_buy(scored, outcome=outcome, stake=stake, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/paper/sell/{market_id}")
async def paper_sell_api(market_id: str, outcome: str = Query(default="YES"), shares: float | None = Query(default=None), reason: str = Query(default="manual paper sell"), user: dict = Depends(require_admin)):
    market = await client.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    scored = attach_probability(attach_scores([market]))[0]
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
        markets = attach_probability(attach_scores(await client.list_markets(limit=min(limit, 100), order="volume24hr")))
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
    scored = attach_probability(attach_scores([market]))[0]
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
    scored = attach_probability(attach_scores([market]))[0]
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
        return attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
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
    scored = attach_probability(attach_scores([market]))[0]
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
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
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
from .review_queue import build_review_queue


async def _ranked_opportunities(limit: int = 50) -> list[dict]:
    """Build ranked, evidence-adjusted opportunities from live Gamma data.

    This keeps review/readiness/ticket workflows on the same data path as the
    visible opportunity engine instead of relying on older placeholder helpers.
    """
    markets = attach_probability(attach_scores(await client.list_markets(limit=limit, order="volume24hr")))
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
async def api_review_queue(limit: int = 25):
    theses = _load_json_file_safe(_data_path("theses.json"), [])
    thesis_ids = sorted({str(t.get("market_id", "")) for t in theses if t.get("market_id")})
    thesis_score_items = score_all_market_theses(thesis_ids, theses)
    thesis_score_map = {str(item["market_id"]): item for item in thesis_score_items}
    try:
        opportunities = await _ranked_opportunities(limit=limit)
    except Exception:
        opportunities = []
    return {"items": build_review_queue(opportunities, thesis_score_map, limit=limit)}

@app.get("/review-queue")
async def review_queue_page(request: Request, limit: int = 25):
    data = await api_review_queue(limit=limit)
    return templates.TemplateResponse("review_queue_v031.html", {"request": request, "items": data["items"], "limit": limit})

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
        scored = attach_evidence_probability(attach_probability(attach_scores([market])))
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
        scored = attach_evidence_probability(attach_probability(attach_scores([market])))
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
