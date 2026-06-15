from __future__ import annotations

import csv
from collections import Counter, defaultdict
from io import StringIO
from typing import Any

from .paper_trading import load_trades
from .trade_tickets import list_trade_tickets
from .paper_exit_tickets import list_exit_tickets
from .paper_settlement import list_settlements
from .paper_positions import list_position_events
from .paper_playbooks import list_playbook_decisions
from .paper_approvals import list_execution_approvals
from .paper_runbook import list_runbook_acknowledgements
from .market_data import list_execution_quality_simulations, list_market_snapshots


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _market_title(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return str(value)
    return str(row.get("market_id") or row.get("id") or "")


def _event(
    *,
    timestamp: Any,
    category: str,
    event_type: str,
    source: str,
    source_id: Any = "",
    market_id: Any = "",
    question: Any = "",
    outcome: Any = "",
    status: Any = "",
    amount: Any = None,
    pnl: Any = None,
    title: str = "",
    detail: str = "",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": _text(timestamp),
        "category": category,
        "event_type": event_type,
        "source": source,
        "source_id": _text(source_id),
        "market_id": _text(market_id),
        "question": _text(question),
        "outcome": _text(outcome).upper() if outcome else "",
        "status": _text(status),
        "amount": round(_safe_float(amount), 4) if amount is not None else None,
        "pnl": round(_safe_float(pnl), 4) if pnl is not None else None,
        "title": title,
        "detail": detail,
        "data": data or {},
    }


def _trade_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in load_trades():
        side = str(trade.get("side") or "").upper()
        if side == "BUY":
            amount = _safe_float(trade.get("cost"), _safe_float(trade.get("stake")))
            title = "Paper buy recorded"
            detail = f"Bought {trade.get('outcome', 'YES')} with simulated stake ${amount:,.2f}."
            category = "paper_trade"
        elif side == "SELL":
            amount = _safe_float(trade.get("proceeds"))
            title = "Paper sell recorded"
            detail = f"Sold {trade.get('outcome', 'YES')} for simulated proceeds ${amount:,.2f}."
            category = "paper_trade"
        elif side == "SETTLE":
            amount = _safe_float(trade.get("proceeds"))
            title = "Settlement trade row recorded"
            detail = f"Settlement credited simulated payout ${amount:,.2f}."
            category = "settlement"
        else:
            amount = _safe_float(trade.get("cost"), _safe_float(trade.get("proceeds")))
            title = "Paper trade row recorded"
            detail = str(trade.get("reason") or side or "Paper trade journal row.")
            category = "paper_trade"
        rows.append(
            _event(
                timestamp=trade.get("timestamp"),
                category=category,
                event_type=f"TRADE_{side or 'UNKNOWN'}",
                source="trades",
                source_id=trade.get("id"),
                market_id=trade.get("market_id"),
                question=trade.get("question"),
                outcome=trade.get("outcome"),
                amount=amount,
                pnl=trade.get("realized_pnl"),
                title=title,
                detail=str(trade.get("reason") or detail),
                data=trade,
            )
        )
    return rows


def _entry_ticket_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticket in list_trade_tickets(limit=10000):
        status = str(ticket.get("status") or "")
        rows.append(
            _event(
                timestamp=ticket.get("updated_at") or ticket.get("created_at"),
                category="entry_ticket",
                event_type="ENTRY_TICKET",
                source="trade_tickets",
                source_id=ticket.get("ticket_id"),
                market_id=ticket.get("market_id"),
                question=_market_title(ticket, "title", "question"),
                outcome=ticket.get("outcome"),
                status=status,
                amount=ticket.get("stake"),
                title=f"Entry ticket {status or 'recorded'}",
                detail=str(ticket.get("operator_note") or ticket.get("operator_decision") or "Paper entry review ticket."),
                data=ticket,
            )
        )
    return rows


def _exit_ticket_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticket in list_exit_tickets(limit=10000):
        status = str(ticket.get("status") or "")
        rows.append(
            _event(
                timestamp=ticket.get("updated_at") or ticket.get("created_at"),
                category="exit_ticket",
                event_type="EXIT_TICKET",
                source="exit_tickets",
                source_id=ticket.get("ticket_id"),
                market_id=ticket.get("market_id"),
                question=_market_title(ticket, "title", "question"),
                outcome=ticket.get("outcome"),
                status=status,
                amount=ticket.get("estimated_proceeds"),
                pnl=ticket.get("estimated_realized_pnl"),
                title=f"Exit ticket {status or 'recorded'}",
                detail=str(ticket.get("exit_reason") or ticket.get("operator_note") or ticket.get("operator_decision") or "Paper exit review ticket."),
                data=ticket,
            )
        )
    return rows


def _settlement_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for settlement in list_settlements(limit=10000):
        rows.append(
            _event(
                timestamp=settlement.get("settled_at"),
                category="settlement",
                event_type="SETTLEMENT",
                source="settlements",
                source_id=settlement.get("settlement_id"),
                market_id=settlement.get("market_id"),
                question=settlement.get("market_id"),
                outcome=settlement.get("winning_outcome"),
                status="settled",
                amount=settlement.get("total_payout"),
                pnl=settlement.get("total_realized_pnl"),
                title="Manual paper settlement recorded",
                detail=str(settlement.get("note") or "Local simulated settlement accounting."),
                data=settlement,
            )
        )
    return rows


def _position_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list_position_events(limit=10000):
        plan = item.get("plan") if isinstance(item.get("plan"), dict) else {}
        status = str(plan.get("status") or item.get("status") or "")
        rows.append(
            _event(
                timestamp=item.get("timestamp"),
                category="position_lifecycle",
                event_type=str(item.get("type") or "POSITION_EVENT"),
                source="position_events",
                source_id=item.get("event_id"),
                market_id=item.get("market_id"),
                question=item.get("question"),
                outcome=item.get("outcome"),
                status=status,
                title="Position lifecycle plan updated" if str(item.get("type")) == "PLAN_UPDATE" else "Position lifecycle event",
                detail=str(plan.get("review_note") or item.get("detail") or "Local paper position lifecycle event."),
                data=item,
            )
        )
    return rows


def _playbook_decision_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in list_playbook_decisions(limit=10000):
        rows.append(
            _event(
                timestamp=decision.get("updated_at") or decision.get("created_at"),
                category="playbook_decision",
                event_type="PLAYBOOK_DECISION",
                source="playbook_decisions",
                source_id=decision.get("decision_id"),
                market_id=decision.get("market_id"),
                question=(decision.get("fit_snapshot") or {}).get("title") or decision.get("market_id"),
                status=decision.get("status"),
                title=f"Playbook decision: {decision.get('playbook_name') or decision.get('playbook_id')}",
                detail=str(decision.get("note") or "Local paper strategy playbook decision."),
                data=decision,
            )
        )
    return rows


def _approval_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for approval in list_execution_approvals(limit=10000):
        status = str(approval.get("status") or "")
        rows.append(
            _event(
                timestamp=approval.get("created_at"),
                category="execution_approval",
                event_type="EXECUTION_APPROVAL",
                source="execution_approvals",
                source_id=approval.get("approval_id"),
                market_id=approval.get("market_id"),
                question=approval.get("title") or approval.get("market_id"),
                outcome=approval.get("outcome"),
                status=status,
                amount=approval.get("stake"),
                title=f"Paper execution approval {status or 'recorded'}",
                detail=str(approval.get("note") or approval.get("reason") or approval.get("blocker_summary") or "Local paper execution approval record."),
                data=approval,
            )
        )
    return rows


def _runbook_acknowledgement_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ack in list_runbook_acknowledgements(limit=10000):
        status = str(ack.get("status") or "")
        snapshot = ack.get("item_snapshot") if isinstance(ack.get("item_snapshot"), dict) else {}
        rows.append(
            _event(
                timestamp=ack.get("created_at"),
                category="operator_runbook",
                event_type="RUNBOOK_ACKNOWLEDGEMENT",
                source="operator_runbook",
                source_id=ack.get("ack_id"),
                market_id=ack.get("market_id") or snapshot.get("market_id"),
                question=snapshot.get("question") or snapshot.get("title") or ack.get("market_id"),
                status=status,
                title=f"Runbook item {status or 'acknowledged'}",
                detail=str(ack.get("note") or ack.get("recommended_action_at_ack") or ack.get("item_id") or "Local paper runbook acknowledgement."),
                data=ack,
            )
        )
    return rows


def _briefing_checkpoint_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .paper_briefing import list_briefing_checkpoints
    except Exception:
        return rows
    for checkpoint in list_briefing_checkpoints(limit=10000):
        status = str(checkpoint.get("status") or "")
        summary = checkpoint.get("summary_snapshot") if isinstance(checkpoint.get("summary_snapshot"), dict) else {}
        rows.append(
            _event(
                timestamp=checkpoint.get("created_at"),
                category="ops_briefing",
                event_type="BRIEFING_CHECKPOINT",
                source="paper_ops_briefing",
                source_id=checkpoint.get("checkpoint_id"),
                status=status,
                amount=summary.get("ready_entry_stake"),
                title=f"Paper ops briefing checkpoint {status or 'recorded'}",
                detail=str(checkpoint.get("note") or f"Items={checkpoint.get('item_count_snapshot', 0)}, blocked={checkpoint.get('blocked_snapshot', 0)}, action_required={checkpoint.get('action_required_snapshot', 0)}"),
                data=checkpoint,
            )
        )
    return rows


def _operator_handoff_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .paper_handoff import list_operator_handoffs
    except Exception:
        return rows
    for handoff in list_operator_handoffs(limit=10000):
        status = str(handoff.get("status") or "")
        rows.append(
            _event(
                timestamp=handoff.get("created_at"),
                category="operator_handoff",
                event_type="OPERATOR_HANDOFF",
                source="operator_handoffs",
                source_id=handoff.get("handoff_id"),
                status=status,
                amount=handoff.get("ready_entry_stake_snapshot"),
                title=f"Paper operator handoff {status or 'recorded'}",
                detail=str(handoff.get("note") or f"Unresolved={handoff.get('unresolved_count_snapshot', 0)}, blocked={handoff.get('blocked_snapshot', 0)}, action_required={handoff.get('action_required_snapshot', 0)}"),
                data=handoff,
            )
        )
    return rows


def _ops_escalation_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .paper_ops_escalations import list_ops_escalations
    except Exception:
        return rows
    for escalation in list_ops_escalations(limit=10000):
        status = str(escalation.get("status") or "")
        rows.append(
            _event(
                timestamp=escalation.get("updated_at") or escalation.get("created_at"),
                category="operator_escalation",
                event_type="OPS_ESCALATION",
                source="paper_ops_escalations",
                source_id=escalation.get("escalation_id"),
                market_id=escalation.get("market_id"),
                question=escalation.get("question") or escalation.get("title"),
                status=status,
                title=f"Paper ops escalation {status or 'recorded'}",
                detail=str(escalation.get("note") or escalation.get("recommended_action_at_escalation") or "Local paper ops escalation record."),
                data=escalation,
            )
        )
    return rows


def _ops_closeout_signoff_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .paper_ops_closeout_signoffs import list_ops_closeout_signoffs
    except Exception:
        return rows
    for signoff in list_ops_closeout_signoffs(limit=10000):
        status = str(signoff.get("status") or "")
        rows.append(
            _event(
                timestamp=signoff.get("created_at"),
                category="ops_closeout_signoff",
                event_type="OPS_CLOSEOUT_SIGNOFF",
                source="paper_ops_closeout_signoffs",
                source_id=signoff.get("signoff_id"),
                market_id=signoff.get("market_filter"),
                question="Paper ops closeout signoff",
                status=status,
                title=f"Paper ops closeout signoff {status or 'recorded'}",
                detail=str(signoff.get("note") or signoff.get("closure_gate") or f"Closeout={signoff.get('closeout_status_snapshot', '')}, handoff_required={signoff.get('handoff_required_count_snapshot', 0)}"),
                data=signoff,
            )
        )
    return rows


def _live_order_intent_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_order_intents import list_live_order_intents
    except Exception:
        return rows
    for intent in list_live_order_intents(limit=10000):
        status = str(intent.get("status") or "")
        rows.append(
            _event(
                timestamp=intent.get("created_at"),
                category="live_order_intent",
                event_type="LIVE_ORDER_INTENT_PREVIEW",
                source="live_order_intents",
                source_id=intent.get("intent_id"),
                market_id=intent.get("market_id"),
                question=intent.get("market_id"),
                outcome=intent.get("outcome"),
                status=status,
                amount=intent.get("notional"),
                title=f"Live order intent preview {status or 'recorded'}",
                detail=str(intent.get("note") or intent.get("next_required_action") or "Local non-executing live-order intent preview."),
                data=intent,
            )
        )
    return rows



def _live_order_preflight_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_order_preflight import list_live_order_preflights
    except Exception:
        return rows
    for review in list_live_order_preflights(limit=10000):
        state = str(review.get("state") or "")
        rows.append(
            _event(
                timestamp=review.get("generated_at"),
                category="live_order_preflight",
                event_type="LIVE_ORDER_INTENT_PREFLIGHT",
                source="live_order_preflight",
                source_id=review.get("review_id"),
                market_id=review.get("market_id"),
                question=review.get("market_id"),
                outcome=review.get("outcome"),
                status=state,
                amount=review.get("notional"),
                title=f"Live order intent preflight {state or 'reviewed'}",
                detail=str(review.get("next_required_action") or "Local non-executing live-intent preflight review."),
                data=review,
            )
        )
    return rows



def _live_order_authorization_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_order_authorizations import list_live_order_authorizations
    except Exception:
        return rows
    for authorization in list_live_order_authorizations(limit=10000):
        status = str(authorization.get("status") or "")
        rows.append(
            _event(
                timestamp=authorization.get("created_at"),
                category="live_order_authorization",
                event_type="LIVE_ORDER_OPERATOR_AUTHORIZATION",
                source="live_order_authorizations",
                source_id=authorization.get("authorization_id"),
                market_id=authorization.get("market_id"),
                question=authorization.get("market_id"),
                outcome=authorization.get("outcome"),
                status=status,
                amount=authorization.get("notional"),
                title=f"Live operator authorization {status or 'recorded'}",
                detail=str(authorization.get("note") or authorization.get("next_required_action") or "Local non-executing live authorization snapshot."),
                data=authorization,
            )
        )
    return rows


def _live_execution_packet_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_execution_packets import list_live_execution_packets
    except Exception:
        return rows
    for packet in list_live_execution_packets(limit=10000):
        status = str(packet.get("status") or "")
        rows.append(
            _event(
                timestamp=packet.get("created_at"),
                category="live_execution_packet",
                event_type="LIVE_EXECUTION_PACKET",
                source="live_execution_packets",
                source_id=packet.get("packet_id"),
                market_id=packet.get("market_id"),
                question=packet.get("market_id"),
                outcome=packet.get("outcome"),
                status=status,
                amount=packet.get("notional"),
                title=f"Live execution packet {status or 'recorded'}",
                detail=str(packet.get("note") or packet.get("next_required_action") or "Unsigned local live execution packet."),
                data=packet,
            )
        )
    return rows



def _live_dry_run_adapter_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_dry_run_adapter import list_live_dry_run_receipts
    except Exception:
        return rows
    for receipt in list_live_dry_run_receipts(limit=10000):
        status = str(receipt.get("status") or "")
        rows.append(
            _event(
                timestamp=receipt.get("created_at"),
                category="live_dry_run_adapter",
                event_type="LIVE_DRY_RUN_ADAPTER",
                source="live_dry_run_adapter",
                source_id=receipt.get("receipt_id"),
                market_id=receipt.get("market_id"),
                question=receipt.get("market_id"),
                outcome=receipt.get("outcome"),
                status=status,
                amount=receipt.get("notional"),
                title=f"Live dry-run adapter {status or 'recorded'}",
                detail=str(receipt.get("note") or receipt.get("next_required_action") or "Offline dry-run adapter receipt."),
                data=receipt,
            )
        )
    return rows


def _live_adapter_readiness_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_adapter import build_live_adapter_readiness
    except Exception:
        return rows
    report = build_live_adapter_readiness()
    status = str(report.get("overall_status") or "")
    rows.append(
        _event(
            timestamp=report.get("generated_at"),
            category="live_adapter_readiness",
            event_type="LIVE_ADAPTER_READINESS",
            source="live_adapter",
            source_id="current",
            status=status,
            title=f"Live adapter readiness {status or 'reported'}",
            detail=str(report.get("recommended_next_action") or "Redacted live adapter readiness report."),
            data=report,
        )
    )
    return rows


def _live_adapter_readonly_validation_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_adapter import list_live_adapter_readonly_validations
    except Exception:
        return rows
    for validation in list_live_adapter_readonly_validations(limit=10000):
        status = str(validation.get("status") or "")
        rows.append(
            _event(
                timestamp=validation.get("created_at"),
                category="live_adapter_readonly_validation",
                event_type="LIVE_ADAPTER_READONLY_VALIDATION",
                source="live_adapter",
                source_id=validation.get("validation_id"),
                status=status,
                title=f"Live adapter read-only validation {status or 'recorded'}",
                detail=str(validation.get("note") or validation.get("next_required_action") or "Optional read-only adapter validation receipt."),
                data=validation,
            )
        )
    return rows


def _live_adapter_request_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_adapter import list_live_adapter_requests
    except Exception:
        return rows
    for request in list_live_adapter_requests(limit=10000):
        status = str(request.get("status") or "")
        rows.append(
            _event(
                timestamp=request.get("created_at"),
                category="live_adapter_request",
                event_type="LIVE_ADAPTER_REQUEST",
                source="live_adapter_requests",
                source_id=request.get("request_id"),
                market_id=request.get("market_id"),
                question=request.get("market_id"),
                outcome=request.get("outcome"),
                status=status,
                amount=request.get("notional"),
                title=f"Live adapter request {status or 'recorded'}",
                detail=str(request.get("note") or request.get("next_required_action") or "Local adapter request validation record."),
                data=request,
            )
        )
    return rows


def _manual_execution_review_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_adapter import list_manual_execution_reviews
    except Exception:
        return rows
    for review in list_manual_execution_reviews(limit=10000):
        status = str(review.get("status") or "")
        rows.append(
            _event(
                timestamp=review.get("created_at"),
                category="manual_execution_review",
                event_type="MANUAL_EXECUTION_REVIEW",
                source="manual_execution_reviews",
                source_id=review.get("review_id"),
                market_id=review.get("market_id"),
                question=review.get("market_id"),
                outcome=review.get("outcome"),
                status=status,
                amount=review.get("notional"),
                title=f"Manual execution review {status or 'recorded'}",
                detail=str(review.get("note") or review.get("next_required_action") or "Local manual execution boundary review."),
                data=review,
            )
        )
    return rows


def _live_execution_control_readiness_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_execution_control import build_live_execution_control_readiness
    except Exception:
        return rows
    report = build_live_execution_control_readiness()
    status = str(report.get("overall_status") or "")
    rows.append(
        _event(
            timestamp=report.get("generated_at"),
            category="live_execution_control_readiness",
            event_type="LIVE_EXECUTION_CONTROL_READINESS",
            source="live_execution_control",
            source_id="current",
            status=status,
            title=f"Live execution control readiness {status or 'reported'}",
            detail=str(report.get("recommended_next_action") or "Manual live execution control-plane readiness report."),
            data=report,
        )
    )
    return rows


def _live_execution_preview_status(attempt: dict[str, Any]) -> str:
    status = str(attempt.get("status") or "")
    if status in {"submitted_fake_adapter_only", "cancelled_fake_adapter_only"}:
        return "fake_adapter_validated"
    return status


def _live_execution_attempt_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_execution_control import list_live_execution_attempts
    except Exception:
        return rows
    for attempt in list_live_execution_attempts(limit=10000):
        status = str(attempt.get("status") or "")
        action = str(attempt.get("action") or "")
        preview_status = _live_execution_preview_status(attempt)
        preview_category = "live_manual_cancel_preview" if action == "cancel" else "live_manual_submit_preview"
        preview_event_type = "LIVE_MANUAL_CANCEL_PREVIEW" if action == "cancel" else "LIVE_MANUAL_SUBMIT_PREVIEW"
        rows.append(
            _event(
                timestamp=attempt.get("created_at"),
                category=preview_category,
                event_type=preview_event_type,
                source="live_execution_preview",
                source_id=f"{attempt.get('attempt_id')}:preview",
                market_id=attempt.get("market_id"),
                question=attempt.get("market_id"),
                outcome=attempt.get("side"),
                status=preview_status,
                amount=attempt.get("notional"),
                title=f"Live manual {action or 'submit'} preview {preview_status or 'recorded'}",
                detail="Derived from the saved manual execution attempt. Preview records do not contain raw confirmation phrases or secrets.",
                data={
                    "attempt_id": attempt.get("attempt_id"),
                    "action": action,
                    "adapter_mode": attempt.get("adapter_mode"),
                    "adapter_request_id": attempt.get("adapter_request_id"),
                    "packet_id": attempt.get("packet_id"),
                    "authorization_id": attempt.get("authorization_id"),
                    "dry_run_receipt_id": attempt.get("dry_run_receipt_id"),
                    "preview_status": preview_status,
                    "blockers": attempt.get("blockers") or [],
                    "warnings": attempt.get("warnings") or [],
                    "secret_values_returned": False,
                },
            )
        )
        category = "live_manual_cancel_attempt" if action == "cancel" else "live_manual_submit_attempt"
        event_type = "LIVE_MANUAL_CANCEL_ATTEMPT" if action == "cancel" else "LIVE_MANUAL_SUBMIT_ATTEMPT"
        rows.append(
            _event(
                timestamp=attempt.get("created_at"),
                category=category,
                event_type=event_type,
                source="live_execution_attempts",
                source_id=attempt.get("attempt_id"),
                market_id=attempt.get("market_id"),
                question=attempt.get("market_id"),
                outcome=attempt.get("side"),
                status=status,
                amount=attempt.get("notional"),
                title=f"Live manual {action or 'submit'} attempt {status or 'recorded'}",
                detail=str(attempt.get("recommended_next_action") or "Manual live execution attempt record."),
                data=attempt,
            )
        )
        if attempt.get("fake_adapter_used") and (attempt.get("fake_submit_receipt_id") or attempt.get("fake_cancel_receipt_id")):
            rows.append(
                _event(
                    timestamp=attempt.get("created_at"),
                    category="live_fake_adapter_receipt",
                    event_type="LIVE_FAKE_ADAPTER_RECEIPT",
                    source="live_execution_attempts",
                    source_id=attempt.get("fake_submit_receipt_id") or attempt.get("fake_cancel_receipt_id"),
                    market_id=attempt.get("market_id"),
                    question=attempt.get("market_id"),
                    outcome=attempt.get("side"),
                    status=status,
                    amount=attempt.get("notional"),
                    title="Fake-local adapter receipt recorded",
                    detail="Fake adapter receipt only; no exchange order was submitted or cancelled.",
                    data=attempt,
                )
            )
    return rows


def _market_data_snapshot_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for snapshot in list_market_snapshots(limit=10000):
        rows.append(
            _event(
                timestamp=snapshot.get("created_at"),
                category="market_data_snapshot",
                event_type="MARKET_DATA_SNAPSHOT",
                source="market_data_snapshots",
                source_id=snapshot.get("snapshot_id"),
                market_id=snapshot.get("market_id"),
                question=snapshot.get("question") or snapshot.get("market_id"),
                outcome=snapshot.get("token_id"),
                status=snapshot.get("status"),
                title=f"Market-data snapshot {snapshot.get('status') or 'recorded'}",
                detail=f"spread={snapshot.get('spread_bps') or 0} bps; depth={snapshot.get('total_bid_depth') or 0}/{snapshot.get('total_ask_depth') or 0}; hash={snapshot.get('raw_public_fields_hash') or ''}",
                data={
                    "snapshot_id": snapshot.get("snapshot_id"),
                    "status": snapshot.get("status"),
                    "market_id": snapshot.get("market_id"),
                    "token_id": snapshot.get("token_id"),
                    "spread_bps": snapshot.get("spread_bps"),
                    "total_bid_depth": snapshot.get("total_bid_depth"),
                    "total_ask_depth": snapshot.get("total_ask_depth"),
                    "warnings": snapshot.get("warnings") or [],
                    "blockers": snapshot.get("blockers") or [],
                    "raw_public_fields_hash": snapshot.get("raw_public_fields_hash"),
                    "secret_values_returned": False,
                },
            )
        )
    return rows


def _execution_quality_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for simulation in list_execution_quality_simulations(limit=10000):
        rows.append(
            _event(
                timestamp=simulation.get("created_at"),
                category="execution_quality_simulation",
                event_type="EXECUTION_QUALITY_SIMULATION",
                source="execution_quality_simulations",
                source_id=simulation.get("simulation_id"),
                market_id=simulation.get("market_id"),
                question=simulation.get("market_id"),
                outcome=simulation.get("side"),
                status=simulation.get("state"),
                amount=simulation.get("estimated_notional"),
                title=f"Execution-quality simulation {simulation.get('state') or 'recorded'}",
                detail=str(simulation.get("recommended_action") or "Local execution-quality estimate."),
                data={
                    "simulation_id": simulation.get("simulation_id"),
                    "snapshot_id": simulation.get("snapshot_id"),
                    "state": simulation.get("state"),
                    "simulation_hash": simulation.get("simulation_hash"),
                    "estimated_average_fill_price": simulation.get("estimated_average_fill_price"),
                    "estimated_unfilled_size": simulation.get("estimated_unfilled_size"),
                    "estimated_slippage_bps": simulation.get("estimated_slippage_bps"),
                    "warnings": simulation.get("warnings") or [],
                    "blockers": simulation.get("blockers") or [],
                    "secret_values_returned": False,
                    "network_attempted": False,
                },
            )
        )
    return rows


def _live_trading_bridge_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from .live_trading import build_live_trading_status, list_live_order_events, list_strategy_signals, list_autonomous_runs
        from .live_clob_adapter import build_clob_adapter_status
    except Exception:
        return rows
    clob_status = build_clob_adapter_status()
    rows.append(
        _event(
            timestamp=clob_status.get("generated_at"),
            category="live_clob_adapter_status",
            event_type="LIVE_CLOB_ADAPTER_STATUS",
            source="live_clob_adapter",
            source_id=clob_status.get("overall_status"),
            status=clob_status.get("overall_status"),
            title="Live CLOB adapter boundary generated",
            detail=clob_status.get("recommended_next_action", "Fail-closed CLOB adapter boundary generated."),
            data={"blockers": clob_status.get("blockers", []), "warnings": clob_status.get("warnings", []), "network_attempted": clob_status.get("network_attempted"), "secret_values_returned": False},
        )
    )
    status = build_live_trading_status()
    rows.append(
        _event(
            timestamp=status.get("generated_at"),
            category="live_trading_status",
            event_type="LIVE_TRADING_STATUS",
            source="live_trading",
            source_id=status.get("overall_status"),
            status=status.get("overall_status"),
            title="Live trading status generated",
            detail=status.get("recommended_next_action", "Guarded live trading status generated."),
            data={"blockers": status.get("blockers", []), "warnings": status.get("warnings", []), "secret_values_returned": False},
        )
    )
    for event in list_live_order_events(limit=10000):
        rows.append(
            _event(
                timestamp=event.get("created_at"),
                category="live_order_event",
                event_type=str(event.get("event_type") or "LIVE_ORDER_EVENT").upper(),
                source="live_orders",
                source_id=event.get("order_event_id"),
                market_id=event.get("market_id"),
                outcome=event.get("side"),
                status=event.get("adapter_status"),
                amount=event.get("notional"),
                title="Live order ledger event",
                detail="Local live/fake/blocked order event recorded without exposing secrets.",
                data=event,
            )
        )
    for signal in list_strategy_signals(limit=10000):
        rows.append(
            _event(
                timestamp=signal.get("created_at"),
                category="strategy_signal",
                event_type="STRATEGY_SIGNAL_RECORDED",
                source="strategy_signals",
                source_id=signal.get("signal_id"),
                market_id=signal.get("market_id"),
                outcome=signal.get("side"),
                status=signal.get("status"),
                amount=signal.get("notional"),
                title="Strategy signal recorded",
                detail=f"Strategy {signal.get('strategy_id')} signal status: {signal.get('status')}",
                data=signal,
            )
        )
    for run in list_autonomous_runs(limit=10000):
        rows.append(
            _event(
                timestamp=run.get("created_at"),
                category="autonomous_run",
                event_type="AUTONOMOUS_RUN_RECORDED",
                source="autonomous_runs",
                source_id=run.get("run_id"),
                status=run.get("mode"),
                amount=run.get("notional_attempted"),
                title="Autonomous run recorded",
                detail=f"Autonomous run mode {run.get('mode')} considered {run.get('signals_considered')} signal(s).",
                data={"summary": run.get("summary", {}), "real_network_attempted": run.get("real_network_attempted"), "real_orders_submitted": run.get("real_orders_submitted")},
            )
        )
    return rows


def build_audit_events(
    *,
    limit: int = 250,
    market_id: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    events = []
    events.extend(_trade_events())
    events.extend(_entry_ticket_events())
    events.extend(_exit_ticket_events())
    events.extend(_settlement_events())
    events.extend(_position_events())
    events.extend(_playbook_decision_events())
    events.extend(_approval_events())
    events.extend(_runbook_acknowledgement_events())
    events.extend(_briefing_checkpoint_events())
    events.extend(_operator_handoff_events())
    events.extend(_ops_escalation_events())
    events.extend(_ops_closeout_signoff_events())
    events.extend(_live_order_intent_events())
    events.extend(_live_order_preflight_events())
    events.extend(_live_order_authorization_events())
    events.extend(_live_execution_packet_events())
    events.extend(_live_dry_run_adapter_events())
    events.extend(_live_adapter_readiness_events())
    events.extend(_live_adapter_readonly_validation_events())
    events.extend(_live_adapter_request_events())
    events.extend(_manual_execution_review_events())
    events.extend(_live_execution_control_readiness_events())
    events.extend(_live_execution_attempt_events())
    events.extend(_market_data_snapshot_events())
    events.extend(_execution_quality_events())
    events.extend(_live_trading_bridge_events())
    try:
        from .training_lab import list_training_audit
        for item in list_training_audit(limit=10000):
            events.append(_event(
                timestamp=item.get("timestamp"),
                category="training_lab",
                event_type=item.get("event_type", "TRAINING_EVENT"),
                source=item.get("source", "training_lab"),
                source_id=item.get("source_id", ""),
                status="recorded",
                title="Training Lab event",
                detail=item.get("detail", "Offline Training Lab audit event."),
                data=item,
            ))
    except Exception:
        pass

    if market_id:
        mid = str(market_id)
        events = [row for row in events if str(row.get("market_id")) == mid]
    if category:
        cat = str(category).strip().lower()
        events = [row for row in events if str(row.get("category", "")).lower() == cat]

    events.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=True)
    return events[: max(0, int(limit))]


def summarize_audit(events: list[dict[str, Any]]) -> dict[str, Any]:
    categories = Counter(str(row.get("category") or "unknown") for row in events)
    event_types = Counter(str(row.get("event_type") or "unknown") for row in events)
    markets = {str(row.get("market_id")) for row in events if row.get("market_id")}
    realized_pnl = sum(_safe_float(row.get("pnl")) for row in events if row.get("pnl") is not None and row.get("event_type") in {"TRADE_SELL", "TRADE_SETTLE"})
    estimated_exit_pnl = sum(_safe_float(row.get("pnl")) for row in events if row.get("pnl") is not None and row.get("event_type") == "EXIT_TICKET" and str(row.get("status")) != "paper_executed")
    settlement_record_pnl = sum(_safe_float(row.get("pnl")) for row in events if row.get("pnl") is not None and row.get("event_type") == "SETTLEMENT")
    amount = sum(_safe_float(row.get("amount")) for row in events if row.get("amount") is not None)
    by_market: dict[str, dict[str, Any]] = defaultdict(lambda: {"market_id": "", "question": "", "event_count": 0, "last_event_at": "", "realized_or_estimated_pnl": 0.0})
    for row in events:
        mid = str(row.get("market_id") or "")
        if not mid:
            continue
        item = by_market[mid]
        item["market_id"] = mid
        if row.get("question"):
            item["question"] = row.get("question")
        item["event_count"] += 1
        if not item["last_event_at"] or str(row.get("timestamp") or "") > str(item["last_event_at"]):
            item["last_event_at"] = row.get("timestamp") or ""
        if row.get("event_type") in {"TRADE_SELL", "TRADE_SETTLE"} or (row.get("event_type") == "EXIT_TICKET" and str(row.get("status")) != "paper_executed"):
            item["realized_or_estimated_pnl"] = round(_safe_float(item["realized_or_estimated_pnl"]) + _safe_float(row.get("pnl")), 4)

    return {
        "count": len(events),
        "market_count": len(markets),
        "category_counts": dict(sorted(categories.items())),
        "event_type_counts": dict(sorted(event_types.items())),
        "total_amount_reference": round(amount, 4),
        "realized_pnl": round(realized_pnl, 4),
        "estimated_exit_pnl": round(estimated_exit_pnl, 4),
        "settlement_record_pnl": round(settlement_record_pnl, 4),
        "realized_or_estimated_pnl": round(realized_pnl + estimated_exit_pnl, 4),
        "last_event_at": events[0].get("timestamp") if events else None,
        "markets": sorted(by_market.values(), key=lambda row: (str(row.get("last_event_at") or ""), row.get("event_count", 0)), reverse=True)[:25],
        "guardrail": "Audit rows are local paper/workflow/live-readiness records. They do not represent live orders, wallet activity, or exchange settlement.",
    }


def build_market_audit(market_id: str, *, limit: int = 250) -> dict[str, Any]:
    events = build_audit_events(limit=limit, market_id=market_id)
    return {"market_id": str(market_id), "summary": summarize_audit(events), "items": events}


def audit_to_csv(events: list[dict[str, Any]]) -> str:
    fields = [
        "timestamp",
        "category",
        "event_type",
        "source",
        "source_id",
        "market_id",
        "question",
        "outcome",
        "status",
        "amount",
        "pnl",
        "title",
        "detail",
    ]
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for event in events:
        writer.writerow(event)
    return buf.getvalue()
