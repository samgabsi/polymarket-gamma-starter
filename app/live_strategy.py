from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .live_v2 import record_audit, redact_data, redact_text

STRATEGY_DIR = DATA_DIR / "live_v2" / "strategy"
STRATEGY_EVENTS_PATH = STRATEGY_DIR / "strategy_events.jsonl"

COLLECTIONS = {"theses", "evidence", "watchlist", "scorecards", "reviews"}
THESIS_STATUSES = {"draft", "watching", "ready_for_ticket", "ticket_created", "active", "closed", "invalidated", "archived"}
EVIDENCE_DIRECTIONS = {"supports", "weakly_supports", "neutral", "weakly_contradicts", "contradicts"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _number(value: Any, default: float = 0.0, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        result = float(value)
    except Exception:
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _int(value: Any, default: int = 0, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(float(value))
    except Exception:
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _tags(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").split(",")
    return sorted({redact_text(item).strip() for item in raw if redact_text(item).strip()})


def _source_links(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").split("\n")
    return [redact_text(item).strip() for item in raw if redact_text(item).strip()]


def _safe_status(value: Any, allowed: set[str], default: str) -> str:
    candidate = _text(value, default).lower().replace(" ", "_").replace("-", "_")
    return candidate if candidate in allowed else default


def _base_payload(payload: dict[str, Any], *, object_type: str, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    now = _now()
    return {
        "id": _text(payload.get("id"), existing.get("id") or f"{object_type}_{uuid4().hex[:12]}"),
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "app_version": APP_VERSION,
        "market_id": redact_text(payload.get("market_id", existing.get("market_id", ""))),
        "market_slug": redact_text(payload.get("market_slug", existing.get("market_slug", ""))),
        "market_title": redact_text(payload.get("market_title", existing.get("market_title", ""))),
        "outcome": redact_text(payload.get("outcome", existing.get("outcome", ""))),
        "token_id": redact_text(payload.get("token_id", existing.get("token_id", ""))),
        "operator_notes": redact_text(payload.get("operator_notes", payload.get("notes", existing.get("operator_notes", "")))),
        "tags": _tags(payload.get("tags", existing.get("tags", []))),
        "source_links": _source_links(payload.get("source_links", existing.get("source_links", []))),
        "audit_metadata": {"source": "live_strategy_v2_4", "secret_values_returned": False},
    }


def _event(action: str, collection: str, item: dict[str, Any]) -> dict[str, Any]:
    return redact_data({
        "event_id": f"strategy_evt_{uuid4().hex[:12]}",
        "timestamp": _now(),
        "app_version": APP_VERSION,
        "action": action,
        "collection": collection,
        "item_id": item.get("id", ""),
        "item": item,
        "secret_values_returned": False,
    })


def _append_event(action: str, collection: str, item: dict[str, Any]) -> dict[str, Any]:
    if collection not in COLLECTIONS:
        raise ValueError(f"Unsupported strategy collection: {collection}")
    _ensure_dir()
    event = _event(action, collection, item)
    with STRATEGY_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    record_audit(
        f"strategy_{action}",
        "recorded",
        details={"collection": collection, "item_id": item.get("id", ""), "market_id": item.get("market_id", ""), "secret_values_returned": False},
    )
    return event


def _read_events() -> list[dict[str, Any]]:
    if not STRATEGY_EVENTS_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in STRATEGY_EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(redact_data(json.loads(line)))
        except json.JSONDecodeError:
            continue
    return rows


def list_strategy_events(limit: int = 500) -> list[dict[str, Any]]:
    return list(reversed(_read_events()))[: max(1, min(int(limit or 500), 5000))]


def _latest_by_collection(collection: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in _read_events():
        if event.get("collection") != collection:
            continue
        item = event.get("item") or {}
        if not isinstance(item, dict) or not item.get("id"):
            continue
        latest[str(item["id"])] = item
    return sorted(latest.values(), key=lambda item: item.get("updated_at", ""), reverse=True)


def get_strategy_item(collection: str, item_id: str) -> dict[str, Any] | None:
    for item in _latest_by_collection(collection):
        if item.get("id") == item_id:
            return item
    return None


def _score_recommendation(total: float, blockers: list[str], warnings: list[str]) -> str:
    if blockers:
        return "Blocked by risk settings"
    if total >= 48 and not warnings:
        return "Ready to draft ticket"
    if total >= 40:
        return "Ready for paper rehearsal"
    if total >= 28:
        return "Watchlist only"
    if total >= 18:
        return "Add more evidence"
    return "Continue researching"


def _normalize_scorecard(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    base = _base_payload(payload, object_type="scorecard", existing=existing)
    categories = [
        "liquidity", "spread", "market_clarity", "information_quality", "evidence_strength",
        "counter_evidence_strength", "catalyst_clarity", "time_to_resolution", "risk_reward",
        "operator_confidence", "execution_readiness", "downside_risk", "ambiguity_risk",
    ]
    scores = existing.get("scores", {}) if isinstance(existing.get("scores"), dict) else {}
    for key in categories:
        scores[key] = _int(payload.get(key, payload.get("scores", {}).get(key, scores.get(key, 0)) if isinstance(payload.get("scores"), dict) else scores.get(key, 0)), 0, minimum=0, maximum=5)
    total = sum(int(v) for v in scores.values())
    blockers = [redact_text(item) for item in (payload.get("blockers") or existing.get("blockers") or [])] if isinstance(payload.get("blockers") or existing.get("blockers"), list) else _source_links(payload.get("blockers", existing.get("blockers", "")))
    warnings = [redact_text(item) for item in (payload.get("warnings") or existing.get("warnings") or [])] if isinstance(payload.get("warnings") or existing.get("warnings"), list) else _source_links(payload.get("warnings", existing.get("warnings", "")))
    base.update({
        "thesis_id": redact_text(payload.get("thesis_id", existing.get("thesis_id", ""))),
        "scores": scores,
        "total_score": total,
        "weighted_score": round(total / (len(categories) * 5) * 100, 2),
        "strengths": _source_links(payload.get("strengths", existing.get("strengths", ""))),
        "weaknesses": _source_links(payload.get("weaknesses", existing.get("weaknesses", ""))),
        "blockers": blockers,
        "warnings": warnings,
        "recommended_next_action": redact_text(payload.get("recommended_next_action", "")) or _score_recommendation(total, blockers, warnings),
        "status": _safe_status(payload.get("status", existing.get("status", "draft")), {"draft", "watching", "ready_for_ticket", "paper_rehearsal", "archived"}, "draft"),
        "secret_values_returned": False,
    })
    return redact_data(base)


def _normalize_thesis(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    base = _base_payload(payload, object_type="thesis", existing=existing)
    base.update({
        "thesis_summary": redact_text(payload.get("thesis_summary", payload.get("summary", existing.get("thesis_summary", "")))),
        "probability_estimate": _number(payload.get("probability_estimate", existing.get("probability_estimate", 0.0)), 0.0, minimum=0.0, maximum=1.0),
        "confidence_level": _safe_status(payload.get("confidence_level", existing.get("confidence_level", "medium")), {"low", "medium", "high"}, "medium"),
        "key_evidence": _source_links(payload.get("key_evidence", existing.get("key_evidence", []))),
        "counter_evidence": _source_links(payload.get("counter_evidence", existing.get("counter_evidence", []))),
        "assumptions": _source_links(payload.get("assumptions", existing.get("assumptions", []))),
        "risk_factors": _source_links(payload.get("risk_factors", existing.get("risk_factors", []))),
        "catalysts": _source_links(payload.get("catalysts", existing.get("catalysts", []))),
        "time_horizon": redact_text(payload.get("time_horizon", existing.get("time_horizon", ""))),
        "entry_criteria": redact_text(payload.get("entry_criteria", existing.get("entry_criteria", ""))),
        "exit_criteria": redact_text(payload.get("exit_criteria", existing.get("exit_criteria", ""))),
        "invalidation_criteria": redact_text(payload.get("invalidation_criteria", existing.get("invalidation_criteria", ""))),
        "maximum_acceptable_exposure": _number(payload.get("maximum_acceptable_exposure", existing.get("maximum_acceptable_exposure", 0.0)), 0.0, minimum=0.0),
        "status": _safe_status(payload.get("status", existing.get("status", "draft")), THESIS_STATUSES, "draft"),
        "secret_values_returned": False,
    })
    return redact_data(base)


def _normalize_evidence(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    base = _base_payload(payload, object_type="evidence", existing=existing)
    base.update({
        "thesis_id": redact_text(payload.get("thesis_id", existing.get("thesis_id", ""))),
        "title": redact_text(payload.get("title", existing.get("title", "Untitled evidence"))),
        "source_url": redact_text(payload.get("source_url", existing.get("source_url", ""))),
        "source_type": redact_text(payload.get("source_type", existing.get("source_type", "manual_note"))),
        "date_observed": redact_text(payload.get("date_observed", existing.get("date_observed", _now()[:10]))),
        "relevance_score": _int(payload.get("relevance_score", existing.get("relevance_score", 0)), 0, minimum=0, maximum=5),
        "credibility_score": _int(payload.get("credibility_score", existing.get("credibility_score", 0)), 0, minimum=0, maximum=5),
        "direction": _safe_status(payload.get("direction", existing.get("direction", "neutral")), EVIDENCE_DIRECTIONS, "neutral"),
        "notes": redact_text(payload.get("notes", existing.get("notes", ""))),
        "stale": bool(payload.get("stale", existing.get("stale", False))),
        "status": _safe_status(payload.get("status", existing.get("status", "active")), {"active", "stale", "archived"}, "active"),
        "secret_values_returned": False,
    })
    return redact_data(base)


def _normalize_watchlist(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    base = _base_payload(payload, object_type="watch", existing=existing)
    base.update({
        "thesis_id": redact_text(payload.get("thesis_id", existing.get("thesis_id", ""))),
        "reason_for_watching": redact_text(payload.get("reason_for_watching", payload.get("reason", existing.get("reason_for_watching", "")))),
        "target_entry_price": _number(payload.get("target_entry_price", existing.get("target_entry_price", 0.0)), 0.0, minimum=0.0, maximum=1.0),
        "target_exit_price": _number(payload.get("target_exit_price", existing.get("target_exit_price", 0.0)), 0.0, minimum=0.0, maximum=1.0),
        "invalidation_condition": redact_text(payload.get("invalidation_condition", existing.get("invalidation_condition", ""))),
        "priority": _safe_status(payload.get("priority", existing.get("priority", "medium")), {"low", "medium", "high", "urgent"}, "medium"),
        "status": _safe_status(payload.get("status", existing.get("status", "watching")), {"watching", "ready_for_review", "ticket_created", "archived"}, "watching"),
        "last_reviewed_at": redact_text(payload.get("last_reviewed_at", existing.get("last_reviewed_at", _now()))),
        "secret_values_returned": False,
    })
    return redact_data(base)


def _normalize_review(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    base = _base_payload(payload, object_type="review", existing=existing)
    base.update({
        "thesis_id": redact_text(payload.get("thesis_id", existing.get("thesis_id", ""))),
        "ticket_id": redact_text(payload.get("ticket_id", existing.get("ticket_id", ""))),
        "order_id": redact_text(payload.get("order_id", existing.get("order_id", ""))),
        "original_probability_estimate": _number(payload.get("original_probability_estimate", existing.get("original_probability_estimate", 0.0)), 0.0, minimum=0.0, maximum=1.0),
        "actual_action_taken": redact_text(payload.get("actual_action_taken", existing.get("actual_action_taken", ""))),
        "fill_cancel_status": redact_text(payload.get("fill_cancel_status", existing.get("fill_cancel_status", "unknown"))),
        "what_went_right": redact_text(payload.get("what_went_right", existing.get("what_went_right", ""))),
        "what_went_wrong": redact_text(payload.get("what_went_wrong", existing.get("what_went_wrong", ""))),
        "thesis_validity": _safe_status(payload.get("thesis_validity", existing.get("thesis_validity", "unknown")), {"valid", "partially_valid", "invalid", "unknown"}, "unknown"),
        "execution_followed_plan": bool(payload.get("execution_followed_plan", existing.get("execution_followed_plan", False))),
        "risk_rules_followed": bool(payload.get("risk_rules_followed", existing.get("risk_rules_followed", False))),
        "lesson_learned": redact_text(payload.get("lesson_learned", existing.get("lesson_learned", ""))),
        "follow_up_action": redact_text(payload.get("follow_up_action", existing.get("follow_up_action", ""))),
        "status": _safe_status(payload.get("status", existing.get("status", "draft")), {"draft", "complete", "archived"}, "draft"),
        "secret_values_returned": False,
    })
    return redact_data(base)


def create_thesis(payload: dict[str, Any]) -> dict[str, Any]:
    item = _normalize_thesis(payload)
    event = _append_event("thesis_created", "theses", item)
    return {"ok": True, "item": item, "event": event, "secret_values_returned": False}


def update_thesis(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    existing = get_strategy_item("theses", item_id)
    if not existing:
        return {"ok": False, "status": "not_found", "item_id": item_id, "secret_values_returned": False}
    item = _normalize_thesis({**payload, "id": item_id}, existing)
    event = _append_event("thesis_edited", "theses", item)
    return {"ok": True, "item": item, "event": event, "secret_values_returned": False}


def archive_thesis(item_id: str) -> dict[str, Any]:
    return update_thesis(item_id, {"status": "archived"}) | {"action": "thesis_archived"}


def create_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    item = _normalize_evidence(payload)
    event = _append_event("evidence_added", "evidence", item)
    return {"ok": True, "item": item, "event": event, "secret_values_returned": False}


def create_watchlist_item(payload: dict[str, Any]) -> dict[str, Any]:
    item = _normalize_watchlist(payload)
    event = _append_event("watchlist_item_created", "watchlist", item)
    return {"ok": True, "item": item, "event": event, "secret_values_returned": False}


def create_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    item = _normalize_scorecard(payload)
    event = _append_event("scorecard_created", "scorecards", item)
    return {"ok": True, "item": item, "event": event, "secret_values_returned": False}


def create_review(payload: dict[str, Any]) -> dict[str, Any]:
    item = _normalize_review(payload)
    event = _append_event("post_trade_review_created", "reviews", item)
    return {"ok": True, "item": item, "event": event, "secret_values_returned": False}


def list_theses(status: str = "", limit: int = 200) -> dict[str, Any]:
    items = _latest_by_collection("theses")
    if status:
        items = [item for item in items if item.get("status") == status]
    items = items[: max(1, min(int(limit or 200), 1000))]
    return {"items": items, "count": len(items), "version": APP_VERSION, "secret_values_returned": False}


def list_evidence(thesis_id: str = "", limit: int = 200) -> dict[str, Any]:
    items = _latest_by_collection("evidence")
    if thesis_id:
        items = [item for item in items if item.get("thesis_id") == thesis_id]
    return {"items": items[: max(1, min(int(limit or 200), 1000))], "count": len(items), "version": APP_VERSION, "secret_values_returned": False}


def list_watchlist(status: str = "", limit: int = 200) -> dict[str, Any]:
    items = _latest_by_collection("watchlist")
    if status:
        items = [item for item in items if item.get("status") == status]
    return {"items": items[: max(1, min(int(limit or 200), 1000))], "count": len(items), "version": APP_VERSION, "secret_values_returned": False}


def list_scorecards(thesis_id: str = "", limit: int = 200) -> dict[str, Any]:
    items = _latest_by_collection("scorecards")
    if thesis_id:
        items = [item for item in items if item.get("thesis_id") == thesis_id]
    return {"items": items[: max(1, min(int(limit or 200), 1000))], "count": len(items), "version": APP_VERSION, "secret_values_returned": False}


def list_reviews(thesis_id: str = "", limit: int = 200) -> dict[str, Any]:
    items = _latest_by_collection("reviews")
    if thesis_id:
        items = [item for item in items if item.get("thesis_id") == thesis_id]
    return {"items": items[: max(1, min(int(limit or 200), 1000))], "count": len(items), "version": APP_VERSION, "secret_values_returned": False}


def build_strategy_workspace(limit: int = 100) -> dict[str, Any]:
    theses = _latest_by_collection("theses")
    evidence = _latest_by_collection("evidence")
    watchlist = _latest_by_collection("watchlist")
    scorecards = _latest_by_collection("scorecards")
    reviews = _latest_by_collection("reviews")
    active_theses = [item for item in theses if item.get("status") not in {"archived", "closed", "invalidated"}]
    ready_theses = [item for item in theses if item.get("status") == "ready_for_ticket"]
    stale_evidence = [item for item in evidence if item.get("stale") or item.get("status") == "stale"]
    summary = {
        "theses": len(theses),
        "active_theses": len(active_theses),
        "ready_for_ticket": len(ready_theses),
        "evidence": len(evidence),
        "watchlist": len(watchlist),
        "scorecards": len(scorecards),
        "reviews": len(reviews),
        "stale_evidence": len(stale_evidence),
    }
    next_action = "Create a thesis or add evidence before drafting a ticket."
    if ready_theses:
        next_action = "Review ready theses, then create a ticket draft without submitting an order."
    elif watchlist:
        next_action = "Review watchlist targets and promote one market into a structured thesis."
    elif evidence:
        next_action = "Link evidence to a thesis and score the market before ticket drafting."
    return redact_data({
        "version": APP_VERSION,
        "generated_at": _now(),
        "summary": summary,
        "next_action": next_action,
        "theses": theses[:limit],
        "evidence": evidence[:limit],
        "watchlist": watchlist[:limit],
        "scorecards": scorecards[:limit],
        "reviews": reviews[:limit],
        "recent_events": list_strategy_events(limit=25),
        "safety_statement": "Strategy objects are research artifacts only. A thesis, score, or watchlist item never submits or arms a live order.",
        "secret_values_returned": False,
    })


def build_ticket_from_thesis(item_id: str) -> dict[str, Any]:
    thesis = get_strategy_item("theses", item_id)
    if not thesis:
        return {"ok": False, "status": "not_found", "item_id": item_id, "network_attempted": False, "order_submitted": False, "secret_values_returned": False}
    evidence_count = len([item for item in _latest_by_collection("evidence") if item.get("thesis_id") == item_id])
    scorecards = [item for item in _latest_by_collection("scorecards") if item.get("thesis_id") == item_id]
    scorecard_summary = scorecards[0] if scorecards else {}
    ticket = redact_data({
        "market_id": thesis.get("market_id", ""),
        "market_title": thesis.get("market_title", ""),
        "token_id": thesis.get("token_id", ""),
        "outcome": thesis.get("outcome", ""),
        "side": "BUY",
        "order_type": "GTC",
        "price": "",
        "size": "",
        "note": f"Thesis {item_id}: {thesis.get('thesis_summary', '')}",
        "strategy_ref": item_id,
        "linked_evidence_count": evidence_count,
        "scorecard_summary": scorecard_summary,
        "entry_criteria": thesis.get("entry_criteria", ""),
        "exit_criteria": thesis.get("exit_criteria", ""),
        "invalidation_criteria": thesis.get("invalidation_criteria", ""),
        "strategy_warnings": ["Ticket was created from a thesis draft only. No order was submitted.", "All live submit gates still apply."],
    })
    event = _append_event("ticket_created_from_thesis", "theses", {**thesis, "status": "ticket_created", "updated_at": _now()})
    return {"ok": True, "status": "draft_only", "ticket": ticket, "event": event, "network_attempted": False, "order_submitted": False, "secret_values_returned": False}


def strategy_export_json() -> dict[str, Any]:
    return build_strategy_workspace(limit=10000)


def strategy_export_markdown() -> str:
    workspace = strategy_export_json()
    lines = [
        f"# Strategy / Playbook Export — {APP_VERSION}",
        "",
        f"Generated: {workspace.get('generated_at')}",
        "",
        workspace.get("safety_statement", "Strategy data is not an order."),
        "",
        "## Summary",
        "",
    ]
    for key, value in workspace.get("summary", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Active Theses", "", "| ID | Status | Market | Outcome | Probability | Confidence | Summary |", "|---|---|---|---|---:|---|---|"])
    for item in workspace.get("theses", []):
        lines.append("| {id} | {status} | {market} | {outcome} | {prob} | {confidence} | {summary} |".format(
            id=_text(item.get("id")), status=_text(item.get("status")), market=_text(item.get("market_title") or item.get("market_id")).replace("|", "\\|"), outcome=_text(item.get("outcome")).replace("|", "\\|"), prob=item.get("probability_estimate", 0), confidence=_text(item.get("confidence_level")), summary=_text(item.get("thesis_summary")).replace("|", "\\|")[:240],
        ))
    lines.extend(["", "## Watchlist", "", "| ID | Priority | Status | Market | Target Entry | Invalidation |", "|---|---|---|---|---:|---|"])
    for item in workspace.get("watchlist", []):
        lines.append("| {id} | {priority} | {status} | {market} | {entry} | {invalid} |".format(
            id=_text(item.get("id")), priority=_text(item.get("priority")), status=_text(item.get("status")), market=_text(item.get("market_title") or item.get("market_id")).replace("|", "\\|"), entry=item.get("target_entry_price", 0), invalid=_text(item.get("invalidation_condition")).replace("|", "\\|")[:160],
        ))
    lines.extend(["", "## Scorecards", "", "| ID | Thesis | Total | Weighted | Next Action |", "|---|---|---:|---:|---|"])
    for item in workspace.get("scorecards", []):
        lines.append("| {id} | {thesis} | {total} | {weighted} | {next_action} |".format(
            id=_text(item.get("id")),
            thesis=_text(item.get("thesis_id")),
            total=item.get("total_score", 0),
            weighted=item.get("weighted_score", 0),
            next_action=_text(item.get("recommended_next_action")).replace("|", "\\|"),
        ))
    lines.extend(["", "Secret values are redacted. This export is a research/playbook report only and does not approve, place, or cancel orders.", ""])
    return "\n".join(lines)


def _csv_for(items: list[dict[str, Any]], fields: list[str]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in item.items()})
    return out.getvalue()


def strategy_csv(collection: str) -> str:
    items = _latest_by_collection(collection)
    common = ["id", "created_at", "updated_at", "app_version", "market_id", "market_title", "outcome", "status", "tags"]
    if collection == "evidence":
        return _csv_for(items, common + ["thesis_id", "title", "source_url", "source_type", "relevance_score", "credibility_score", "direction", "stale"])
    if collection == "watchlist":
        return _csv_for(items, common + ["thesis_id", "priority", "target_entry_price", "target_exit_price", "invalidation_condition", "last_reviewed_at"])
    if collection == "scorecards":
        return _csv_for(items, common + ["thesis_id", "total_score", "weighted_score", "recommended_next_action"])
    return _csv_for(items, common)
