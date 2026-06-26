from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_VERSION, PROJECT_ROOT, settings
from .market_edge import (
    FAVORITE_VS_EDGE_EXPLAINER,
    RECOMMENDATION_SAFETY_NOTE,
    build_market_recommendation_row,
    edge_recommendation_legend,
    enrich_markets_with_recommendations,
    group_related_markets,
    rank_market_family,
)
from .platform_safety import redact_data, redact_text, safety_flags, secret_scan
from . import ai_news_odds

REVIEW_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "opportunity_reviews"
REVIEW_RECORDS_PATH = REVIEW_RUNTIME_DIR / "review_records.jsonl"
OPERATOR_NOTES_PATH = REVIEW_RUNTIME_DIR / "operator_notes.jsonl"

REVIEW_STATUSES = [
    "UNREVIEWED",
    "WATCHING",
    "AI_REVIEW_REQUESTED",
    "AI_REVIEWED",
    "NEEDS_MORE_EVIDENCE",
    "PAPER_REVIEW",
    "REJECTED",
    "ARCHIVED",
]

AI_EDGE_PACKET_LIFECYCLE_STATES = [
    "DRAFT",
    "EVIDENCE_ATTACHED",
    "AI_ANALYZED",
    "OPERATOR_REVIEWED",
    "NEEDS_MORE_EVIDENCE",
    "ARCHIVED",
    "EXPORTED",
]

REVIEW_ONLY_NOTE = (
    "Opportunity review records, watchlist states, paper-review queue states, and AI Edge packets are research/review-only. "
    "They do not approve trades, place orders, cancel orders, arm live trading, disable read-only mode, or bypass backend gates."
)

DATA_STATE_VALUES = ["live", "cached", "sample", "stale", "unavailable"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_runtime_dir() -> None:
    REVIEW_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _record_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _market_key(market: dict[str, Any] | str) -> str:
    if isinstance(market, str):
        return redact_text(market).strip()
    return str(
        market.get("id")
        or market.get("market_id")
        or market.get("conditionId")
        or market.get("condition_id")
        or market.get("slug")
        or market.get("market_slug")
        or market.get("question")
        or market.get("title")
        or ""
    )


def _market_title(market: dict[str, Any]) -> str:
    return str(market.get("question") or market.get("title") or market.get("market_title") or "Untitled market")


def normalize_data_state(value: Any, default: str = "cached") -> str:
    text = str(value or default or "cached").strip().lower().replace(" ", "_").replace("-", "_")
    if text in DATA_STATE_VALUES:
        return text
    if text in {"demo", "fixture", "fixtures", "demo_fixture", "safe_demo_fixture"}:
        return "sample"
    if text in {"local", "runtime", "stored", "review_record"}:
        return "cached"
    return default if default in DATA_STATE_VALUES else "cached"


def _is_demo_fixture_market(market: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(market.get("id") or ""),
            str(market.get("market_id") or ""),
            str(market.get("slug") or ""),
            str(market.get("category") or ""),
            str(market.get("source") or ""),
        ]
    ).lower()
    return bool(market.get("demo_fixture")) or "demo_fixture" in text or text.startswith("demo_")


def _market_data_state(market: dict[str, Any], default: str = "cached") -> str:
    if _is_demo_fixture_market(market):
        return "sample"
    explicit = market.get("data_state") or market.get("data_freshness_state")
    if explicit:
        return normalize_data_state(explicit, default=default)
    age = market.get("data_age_minutes")
    try:
        if age is not None and float(age) > 240:
            return "stale"
    except (TypeError, ValueError):
        pass
    if market.get("active") is False and not market.get("closed"):
        return "unavailable"
    return default


def _market_data_freshness(market: dict[str, Any], data_state: str) -> str:
    if data_state == "sample":
        return "sample_fixture"
    age = market.get("data_age_minutes")
    try:
        return f"{float(age):.0f}_minutes_old"
    except (TypeError, ValueError):
        return data_state


def _workbench_source_context(opportunities: list[dict[str, Any]], *, requested_demo: bool | None = None) -> dict[str, Any]:
    states = [_market_data_state(row) for row in opportunities]
    counts = {state: states.count(state) for state in DATA_STATE_VALUES if state in states}
    if not states:
        data_state = "unavailable"
    elif len(counts) == 1:
        data_state = states[0]
    elif "live" in counts:
        data_state = "live"
    elif "cached" in counts:
        data_state = "cached"
    elif "sample" in counts:
        data_state = "sample"
    else:
        data_state = states[0]
    requested = bool(requested_demo)
    if data_state == "sample" and requested:
        reason = "Demo fixtures were explicitly requested; rows are deterministic sample data for review workflow validation."
        source_state = "demo_fixture"
        resolved_mode = "demo_fixtures"
    elif data_state == "sample":
        reason = "Configured/public market data was unavailable or empty, so deterministic fixtures are shown and labelled sample."
        source_state = "demo_fixture_fallback"
        resolved_mode = "sample_fallback"
    elif data_state == "live":
        reason = "Rows came from configured read-only market data helpers; review actions still persist local records only."
        source_state = "configured_read_only_source"
        resolved_mode = "configured_source"
    elif data_state == "stale":
        reason = "Rows came from configured/local sources but include stale freshness metadata."
        source_state = "configured_or_cached_source"
        resolved_mode = "configured_source"
    elif data_state == "cached":
        reason = "Rows came from configured/local read helpers or cached enrichment; verify freshness before relying on them."
        source_state = "configured_or_cached_source"
        resolved_mode = "configured_source"
    else:
        reason = "No usable opportunity rows were available for this request."
        source_state = "unavailable"
        resolved_mode = "unavailable"
    return {
        "requested_demo": requested,
        "requested_data_mode": "demo_fixtures" if requested else "configured_source",
        "resolved_data_mode": resolved_mode,
        "source_state": source_state,
        "data_state": data_state,
        "data_state_counts": counts,
        "data_state_reason": reason,
        "operator_implication": "Review actions record local operator decisions only; they never approve or execute trades.",
        "next_action": "Use the data-mode selector to switch sources, then save notes or status decisions with source metadata.",
        "safe_review_only": True,
        "live_disabled": True,
    }


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_runtime_dir()
    safe = redact_data(row)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe, sort_keys=True, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(redact_data(parsed))
        except json.JSONDecodeError:
            rows.append({"record_id": _record_id("invalid_review"), "status": "invalid_json", "secret_values_returned": False})
    return rows


def _latest_by_market(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("market_id_or_slug") or row.get("market_id") or "")
        if key:
            latest[key] = row
    return latest


def normalize_review_status(status: Any) -> str:
    text = str(status or "UNREVIEWED").strip().upper().replace("-", "_").replace(" ", "_")
    return text if text in REVIEW_STATUSES else "UNREVIEWED"


def demo_markets() -> list[dict[str, Any]]:
    """Safe deterministic fixtures used only when live/public data is unavailable or tests request demo rows."""
    base = [
        ("demo_france_world_cup", "Will France win the 2026 FIFA World Cup?", 0.18, 0.205, 52000, 26000),
        ("demo_brazil_world_cup", "Will Brazil win the 2026 FIFA World Cup?", 0.16, 0.185, 41000, 22000),
        ("demo_germany_world_cup", "Will Germany win the 2026 FIFA World Cup?", 0.12, 0.10, 35000, 18500),
        ("demo_weather_nyc", "Will it rain in New York tomorrow?", 0.40, 0.405, 5000, 6000),
    ]
    rows: list[dict[str, Any]] = []
    for market_id, question, yes_price, model_fair, volume, liquidity in base:
        rows.append(
            {
                "id": market_id,
                "market_id": market_id,
                "slug": market_id.replace("_", "-"),
                "question": question,
                "category": "demo_fixture",
                "active": True,
                "closed": False,
                "enable_order_book": True,
                "accepting_orders": False,
                "volume_24hr": float(volume),
                "volume": float(volume * 4),
                "liquidity": float(liquidity),
                "outcomes": [{"name": "YES", "price": yes_price}, {"name": "NO", "price": round(1 - yes_price, 4)}],
                "probability_model": {
                    "market_probability": yes_price,
                    "model_probability": model_fair,
                    "edge": round(model_fair - yes_price, 4),
                    "edge_percent": round((model_fair - yes_price) * 100, 2),
                    "confidence": "medium",
                    "confidence_score": 62.0,
                    "signal": "fixture_review_only",
                },
                "model_probability": model_fair,
                "market_probability": yes_price,
                "model_edge": round(model_fair - yes_price, 4),
                "opportunity_score": 72.0,
                "score_breakdown": {"volume_score": 60.0, "liquidity_score": 55.0, "tradability_score": 90.0},
                "data_age_minutes": 1,
                "url": f"https://polymarket.com/search?query={question.replace(' ', '+')}",
                "polymarket_url": f"https://polymarket.com/search?query={question.replace(' ', '+')}",
                "polymarket_url_label": "Demo search link",
                "polymarket_url_confidence": "demo",
                "demo_fixture": True,
            }
        )
    return enrich_markets_with_recommendations(rows)


def list_review_records(limit: int = 500, include_archived: bool = True) -> dict[str, Any]:
    latest = list(_latest_by_market(_read_jsonl(REVIEW_RECORDS_PATH)).values())
    if not include_archived:
        latest = [row for row in latest if normalize_review_status(row.get("review_status")) != "ARCHIVED"]
    latest.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    capped = latest[: max(1, min(int(limit or 500), 5000))]
    return safety_flags(
        {
            "version": APP_VERSION,
            "storage_path": "runtime/opportunity_reviews/review_records.jsonl",
            "runtime_records_excluded_from_release_zip": True,
            "count": len(capped),
            "total_count": len(latest),
            "items": capped,
            "review_statuses": REVIEW_STATUSES,
            "review_only": True,
        }
    )


def get_review_record(market_id_or_slug: str, market: dict[str, Any] | None = None) -> dict[str, Any]:
    safe_id = _market_key(market_id_or_slug)
    record = _latest_by_market(_read_jsonl(REVIEW_RECORDS_PATH)).get(safe_id)
    if record:
        return safety_flags({"ok": True, "item": record, "found": True, "review_only": True})
    title = _market_title(market or {}) if market else ""
    data_state = _market_data_state(market or {}, default="unavailable" if not market else "cached")
    default = {
        "record_id": _record_id("opp_review"),
        "market_id_or_slug": safe_id,
        "market_id": safe_id,
        "market_title": redact_text(title),
        "review_status": "UNREVIEWED",
        "operator_notes": "",
        "tags": [],
        "data_state": data_state,
        "data_freshness": _market_data_freshness(market or {}, data_state),
        "last_action_source_route": "",
        "last_action_source_component": "",
        "created_at": "",
        "updated_at": "",
        "ai_edge_packet_id": "",
        "family_id": "",
        "audit_history": [],
        "review_only": True,
        "safety_note": REVIEW_ONLY_NOTE,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
    }
    return safety_flags({"ok": True, "item": default, "found": False, "review_only": True})


def upsert_review_record(
    market_id_or_slug: str,
    *,
    market_title: str = "",
    review_status: str | None = None,
    operator_notes: str | None = None,
    recommendation_snapshot: dict[str, Any] | None = None,
    ai_edge_packet_id: str = "",
    family_id: str = "",
    tags: list[str] | None = None,
    action: str = "review_update",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    safe_id = _market_key(market_id_or_slug)
    current = get_review_record(safe_id).get("item", {})
    now = _now()
    notes_text = redact_text(operator_notes) if operator_notes is not None else str(current.get("operator_notes") or "")
    previous_status = normalize_review_status(current.get("review_status") or "UNREVIEWED")
    status = normalize_review_status(review_status or current.get("review_status") or "UNREVIEWED")
    market_title_text = redact_text(market_title or current.get("market_title") or "")[:300]
    source_route = redact_text(payload.get("source_route") or payload.get("return_to") or current.get("last_action_source_route") or "")[:240]
    source_component = redact_text(payload.get("source_component") or current.get("last_action_source_component") or "opportunity_review")[:160]
    requested_action = redact_text(payload.get("action") or action)[:120]
    reason = redact_text(payload.get("reason") or payload.get("operator_reason") or payload.get("operator_notes") or f"Operator review action {action}")[:600]
    data_state = normalize_data_state(payload.get("data_state") or payload.get("data_freshness") or current.get("data_state") or "cached")
    data_freshness = redact_text(payload.get("data_freshness") or current.get("data_freshness") or data_state)[:120]
    secret_check = secret_scan({"operator_notes": notes_text, "tags": tags or [], "reason": reason, "source_route": source_route})
    if secret_check.get("ok") is not True:
        return safety_flags({"ok": False, "error": "secret_like_content_rejected", "secret_scan": secret_check, "review_only": True})
    action_type = "notes" if action == "operator_notes_updated" else ("status" if action.startswith("status:") else "review_update")
    audit_event = {
        "event_id": _record_id("opp_audit"),
        "at": now,
        "feature_area": "opportunity_review",
        "action_type": action_type,
        "action": redact_text(action)[:120],
        "requested_action": requested_action,
        "target_id": safe_id,
        "target_name": market_title_text,
        "previous_state": previous_status,
        "new_state": status,
        "review_status": status,
        "state_changed": previous_status != status,
        "reason": reason,
        "source_route": source_route,
        "source_component": source_component,
        "data_state": data_state,
        "data_freshness": data_freshness,
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
    }
    record = {
        "record_id": current.get("record_id") or _record_id("opp_review"),
        "market_id_or_slug": safe_id,
        "market_id": safe_id,
        "market_title": market_title_text,
        "review_status": status,
        "previous_review_status": previous_status,
        "operator_notes": notes_text[:5000],
        "created_at": current.get("created_at") or now,
        "updated_at": now,
        "last_recommendation_snapshot": redact_data(recommendation_snapshot or current.get("last_recommendation_snapshot") or {}),
        "ai_edge_packet_id": redact_text(ai_edge_packet_id or current.get("ai_edge_packet_id") or ""),
        "family_id": redact_text(family_id or current.get("family_id") or ""),
        "tags": [redact_text(tag)[:80] for tag in (tags if tags is not None else current.get("tags") or [])][:20],
        "data_state": data_state,
        "data_freshness": data_freshness,
        "last_action": redact_text(action)[:120],
        "last_action_type": action_type,
        "last_action_reason": reason,
        "last_action_source_route": source_route,
        "last_action_source_component": source_component,
        "operator_implication": "Local opportunity review state changed only; no trade was approved or submitted.",
        "next_action": "Open the market detail, inspect AI/news evidence, or continue paper-review workflow as needed.",
        "safety_acknowledgement_text": "Review-only; not trade approval; no live mutation.",
        "audit_history": list(current.get("audit_history") or [])[-20:] + [audit_event],
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "safety_note": REVIEW_ONLY_NOTE,
        "order_submitted": False,
        "order_cancelled": False,
        "trade_approved": False,
        "live_trading_armed": False,
        "no_live_mutation": True,
        "not_financial_advice": True,
        "secret_values_returned": False,
    }
    _write_jsonl(REVIEW_RECORDS_PATH, record)
    if operator_notes is not None:
        _write_jsonl(
            OPERATOR_NOTES_PATH,
            {
                "note_id": _record_id("opp_note"),
                "market_id_or_slug": safe_id,
                "market_title": record["market_title"],
                "operator_notes": notes_text[:5000],
                "created_at": now,
                "review_status": status,
                "data_state": data_state,
                "data_freshness": data_freshness,
                "source_route": source_route,
                "source_component": source_component,
                "review_only": True,
                "safe_review_only": True,
                "live_disabled": True,
                "secret_values_returned": False,
            },
        )
    return safety_flags({"ok": True, "item": record, "review_only": True})


def update_review_notes(market_id_or_slug: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return upsert_review_record(
        market_id_or_slug,
        market_title=str(payload.get("market_title") or ""),
        operator_notes=str(payload.get("operator_notes") or payload.get("notes") or ""),
        review_status=payload.get("review_status"),
        tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
        action="operator_notes_updated",
        payload=payload,
    )


def update_review_status(market_id_or_slug: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    requested = payload.get("review_status") or payload.get("status") or payload.get("action") or "UNREVIEWED"
    action_map = {
        "add_to_watchlist": "WATCHING",
        "watch": "WATCHING",
        "send_to_paper_review": "PAPER_REVIEW",
        "paper_review": "PAPER_REVIEW",
        "reject": "REJECTED",
        "archive": "ARCHIVED",
        "needs_more_evidence": "NEEDS_MORE_EVIDENCE",
        "ai_review_requested": "AI_REVIEW_REQUESTED",
        "ai_reviewed": "AI_REVIEWED",
    }
    normalized = action_map.get(str(requested).strip().lower(), normalize_review_status(requested))
    return upsert_review_record(
        market_id_or_slug,
        market_title=str(payload.get("market_title") or ""),
        review_status=normalized,
        recommendation_snapshot=payload.get("recommendation_snapshot") if isinstance(payload.get("recommendation_snapshot"), dict) else None,
        ai_edge_packet_id=str(payload.get("ai_edge_packet_id") or ""),
        family_id=str(payload.get("family_id") or ""),
        tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
        action=f"status:{normalized}",
        payload=payload,
    )


def list_operator_notes(market_id_or_slug: str | None = None, limit: int = 100) -> dict[str, Any]:
    rows = _read_jsonl(OPERATOR_NOTES_PATH)
    if market_id_or_slug:
        safe_id = _market_key(market_id_or_slug)
        rows = [row for row in rows if str(row.get("market_id_or_slug") or "") == safe_id]
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    capped = rows[: max(1, min(int(limit or 100), 1000))]
    return safety_flags({"version": APP_VERSION, "count": len(capped), "items": capped, "review_only": True})


def build_packet_lifecycle_summary(packet: dict[str, Any] | None = None, *, current_recommendation: dict[str, Any] | None = None, operator_notes_count: int = 0) -> dict[str, Any]:
    packet = packet or {}
    evidence_count = len(packet.get("evidence_sources") or []) if isinstance(packet.get("evidence_sources"), list) else 0
    status = str(packet.get("status") or "draft").upper()
    archived = bool(packet.get("archived") or status == "ARCHIVED")
    if archived:
        lifecycle = "ARCHIVED"
    elif status in {"OPERATOR_REVIEWED", "NEEDS_MORE_EVIDENCE", "EXPORTED"}:
        lifecycle = status
    elif packet.get("ai_model_called"):
        lifecycle = "AI_ANALYZED"
    elif evidence_count > 0:
        lifecycle = "EVIDENCE_ATTACHED"
    else:
        lifecycle = "DRAFT"
    return safety_flags(
        {
            "packet_id": packet.get("packet_id") or "",
            "market_id": packet.get("market_id") or "",
            "market_title": packet.get("market_title") or packet.get("title") or "",
            "created_at": packet.get("created_at") or "",
            "updated_at": packet.get("updated_at") or "",
            "provider": packet.get("provider") or "mock",
            "evidence_count": evidence_count,
            "calibration_references": packet.get("calibration_tracking") or {},
            "model_fair_source": (current_recommendation or {}).get("model_fair_source") or "AI Edge packet probability draft",
            "recommended_side_at_packet_creation": packet.get("recommended_side") or (current_recommendation or {}).get("recommended_side") or "INSUFFICIENT DATA",
            "current_recommended_side": (current_recommendation or {}).get("recommended_side") or "INSUFFICIENT DATA",
            "operator_notes_count": operator_notes_count,
            "review_status": lifecycle,
            "lifecycle_state": lifecycle,
            "lifecycle_states": AI_EDGE_PACKET_LIFECYCLE_STATES,
            "draft_review_only": True,
            "no_live_mutation_confirmation": True,
        }
    )


def _format_price(value: Any) -> str:
    try:
        if value is None:
            return "unavailable"
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "unavailable"


def build_opportunity_workbench(opportunities: list[dict[str, Any]], packets: list[dict[str, Any]] | None = None, *, limit: int = 50, requested_demo: bool | None = None, source_route: str = "/v3/opportunities") -> dict[str, Any]:
    packets = packets or []
    source_context = _workbench_source_context(opportunities, requested_demo=requested_demo)
    packet_by_market: dict[str, dict[str, Any]] = {}
    for packet in packets:
        key = str(packet.get("market_id") or packet.get("market_slug") or "")
        if key and key not in packet_by_market:
            packet_by_market[key] = packet
    review_records = _latest_by_market(_read_jsonl(REVIEW_RECORDS_PATH))
    rows: list[dict[str, Any]] = []
    for index, opp in enumerate(opportunities[: max(1, min(int(limit or 50), 500))], start=1):
        market_id = str(opp.get("market_id") or opp.get("id") or opp.get("slug") or "")
        edge = opp.get("market_edge_recommendation") or {}
        record = review_records.get(market_id) or get_review_record(market_id, {"question": opp.get("question")}).get("item", {})
        packet = packet_by_market.get(market_id, {})
        notes = list_operator_notes(market_id, limit=50).get("items", [])
        lifecycle = build_packet_lifecycle_summary(packet, current_recommendation=edge, operator_notes_count=len(notes))
        data_state = _market_data_state(opp, default=source_context["data_state"])
        data_freshness = _market_data_freshness(opp, data_state)
        rows.append(
            {
                "rank": index,
                "review_status": normalize_review_status(record.get("review_status")),
                "market_id": market_id,
                "market_title": opp.get("question") or opp.get("market_title") or "Untitled market",
                "family_id": edge.get("family_id") or opp.get("market_family_id") or "",
                "family_rank": edge.get("group_rank_label") or opp.get("family_rank_label") or "No family detected",
                "recommended_side": edge.get("recommended_side") or opp.get("recommended_side") or "INSUFFICIENT DATA",
                "side_badge": edge.get("side_badge") or opp.get("side_badge") or "INSUFFICIENT DATA",
                "yes_price": edge.get("market_yes_price") or opp.get("market_probability"),
                "no_price": edge.get("market_no_price"),
                "model_fair_yes": edge.get("model_fair_yes") or opp.get("model_probability"),
                "model_fair_source": edge.get("model_fair_source") or opp.get("model_fair_source") or "unavailable",
                "yes_edge_pp": edge.get("yes_edge_pp") if edge else opp.get("yes_edge_pp"),
                "no_edge_pp": edge.get("no_edge_pp") if edge else opp.get("no_edge_pp"),
                "confidence": edge.get("confidence_label") or opp.get("confidence") or "low",
                "data_quality": "; ".join(edge.get("data_quality_warnings") or []) or "No blocking data-quality warning recorded.",
                "ai_edge_packet_id": packet.get("packet_id") or record.get("ai_edge_packet_id") or "",
                "ai_edge_lifecycle": lifecycle.get("lifecycle_state"),
                "news_odds_status": opp.get("news_odds_status") or "not researched",
                "news_adjusted_fair_yes": opp.get("news_adjusted_fair_yes"),
                "news_confidence": opp.get("news_confidence") or "unavailable",
                "news_top_source": opp.get("news_top_source") or "manual evidence or web search required",
                "news_contradiction_warning": opp.get("news_contradiction_warning") or "",
                "news_last_researched_at": opp.get("news_last_researched_at") or "",
                "operator_notes": record.get("operator_notes") or "",
                "data_state": data_state,
                "data_freshness": data_freshness,
                "review_source": "demo_fixture" if data_state == "sample" else source_context["source_state"],
                "source_route": source_route,
                "source_component": "opportunity_workbench",
                "operator_implication": "Local review status only; no order submission, cancellation, or trade approval.",
                "next_action": "Open detail, save notes, or submit a review status decision.",
                "safe_review_only": True,
                "live_disabled": True,
                "order_submitted": False,
                "order_cancelled": False,
                "trade_approved": False,
                "live_trading_armed": False,
                "detail_href": f"/v3/markets/{market_id}" if market_id else "/v3/opportunities",
                "legacy_detail_href": f"/markets/{market_id}" if market_id else "/opportunities",
                "ai_edge_analyze_href": f"/v3/ai/edge/market/{market_id}" if market_id else "/v3/ai/edge",
                "ai_edge_packet_href": f"/v3/ai/edge/packet/{packet.get('packet_id')}" if packet.get("packet_id") else f"/api/v3/ai/edge/market/{market_id}/packet",
                "family_href": f"/v3/markets/family/{edge.get('family_id')}" if edge.get("family_id") else "",
                "news_odds_href": f"/v3/markets/{market_id}/news-odds" if market_id else "/v3/ai/news-odds",
                "news_odds_plan_api_href": f"/api/v3/ai/news-odds/market/{market_id}/plan",
                "news_odds_adjust_api_href": f"/api/v3/ai/news-odds/market/{market_id}/adjust",
                "notes_api_href": f"/api/v3/opportunities/review/{market_id}/notes",
                "status_api_href": f"/api/v3/opportunities/review/{market_id}/status",
                "why": edge.get("explanation") or opp.get("reason_codes") or "Review-only candidate; inspect detail before any workflow decision.",
                "safety_note": REVIEW_ONLY_NOTE,
            }
        )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["review_status"]] = counts.get(row["review_status"], 0) + 1
    return safety_flags(
        {
            "version": APP_VERSION,
            "title": "Opportunity Review Workbench",
            "review_only": True,
            "count": len(rows),
            "items": rows,
            "review_status_counts": counts,
            "review_statuses": REVIEW_STATUSES,
            "ai_edge_lifecycle_states": AI_EDGE_PACKET_LIFECYCLE_STATES,
            "review_only_note": REVIEW_ONLY_NOTE,
            "data_state_values": DATA_STATE_VALUES,
            "data_state": source_context["data_state"],
            "data_state_counts": source_context["data_state_counts"],
            "data_state_reason": source_context["data_state_reason"],
            "requested_demo": source_context["requested_demo"],
            "requested_data_mode": source_context["requested_data_mode"],
            "resolved_data_mode": source_context["resolved_data_mode"],
            "source_state": source_context["source_state"],
            "operator_implication": source_context["operator_implication"],
            "next_action": source_context["next_action"],
            "safe_review_only": True,
            "live_disabled": True,
            "data_mode_options": [
                {"value": "true", "label": "Demo fixtures", "data_state": "sample"},
                {"value": "false", "label": "Configured local/live source", "data_state": "cached"},
            ],
            "favorite_vs_edge": FAVORITE_VS_EDGE_EXPLAINER,
            "edge_legend": edge_recommendation_legend(),
            "formatted_columns": ["Review Status", "Market", "Family / Rank", "Recommended Side", "YES Price", "NO Price", "Model Fair", "YES Edge", "NO Edge", "Confidence", "Data Quality", "News Odds", "AI Edge Packet", "Operator Notes", "Actions"],
        }
    )


def build_market_detail_context(market: dict[str, Any], packets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    enriched = enrich_markets_with_recommendations([dict(market)])[0]
    edge = enriched.get("market_edge_recommendation") or build_market_recommendation_row(enriched)
    market_id = _market_key(enriched)
    record = get_review_record(market_id, enriched).get("item", {})
    notes = list_operator_notes(market_id, limit=50).get("items", [])
    packets = packets or []
    market_packets = [packet for packet in packets if str(packet.get("market_id") or packet.get("market_slug") or "") == str(market_id)]
    packet = market_packets[0] if market_packets else {}
    lifecycle = build_packet_lifecycle_summary(packet, current_recommendation=edge, operator_notes_count=len(notes))
    news_preview = ai_news_odds.build_news_odds_adjustment_packet(enriched, [], edge)
    news_preview["explanation"] = ai_news_odds.explain_news_odds_adjustment(news_preview)
    data_state = _market_data_state(enriched)
    data_freshness = _market_data_freshness(enriched, data_state)
    return safety_flags(
        {
            "version": APP_VERSION,
            "market": enriched,
            "market_id": market_id,
            "market_title": _market_title(enriched),
            "review_only": True,
            "edge": edge,
            "review_record": record,
            "operator_notes": notes,
            "ai_edge_packets": market_packets,
            "ai_edge_packet_lifecycle": lifecycle,
            "news_odds_adjustment": news_preview,
            "news_odds_summary_href": f"/v3/markets/{market_id}/news-odds",
            "news_odds_plan_href": f"/api/v3/ai/news-odds/market/{market_id}/plan",
            "news_odds_adjust_href": f"/api/v3/ai/news-odds/market/{market_id}/adjust",
            "data_state": data_state,
            "data_freshness": data_freshness,
            "source_state": "demo_fixture" if data_state == "sample" else "configured_or_cached_source",
            "data_state_reason": "This market is a deterministic sample fixture." if data_state == "sample" else "This market came from configured/local read helpers; verify freshness before relying on it.",
            "operator_implication": "Market detail actions record local review metadata only and do not mutate live trading state.",
            "safe_review_only": True,
            "live_disabled": True,
            "favorite_vs_edge": FAVORITE_VS_EDGE_EXPLAINER,
            "review_only_note": REVIEW_ONLY_NOTE,
            "detail_actions": [
                {"label": "Analyze with AI Edge", "href": f"/v3/ai/edge/market/{market_id}", "method": "GET", "review_only": True},
                {"label": "Plan News Odds Search", "href": f"/api/v3/ai/news-odds/market/{market_id}/plan", "method": "POST", "review_only": True},
                {"label": "Open News Odds Panel", "href": f"/v3/markets/{market_id}/news-odds", "method": "GET", "review_only": True},
                {"label": "Open AI Edge Packet", "href": f"/api/v3/ai/edge/market/{market_id}/packet", "method": "GET", "review_only": True},
                {"label": "Compare Family", "href": f"/v3/markets/family/{edge.get('family_id')}", "method": "GET", "review_only": True} if edge.get("family_id") else {"label": "Compare Family", "href": "", "method": "GET", "review_only": True, "disabled": True},
                {"label": "Add/Edit Operator Notes", "href": f"/api/v3/opportunities/review/{market_id}/notes", "method": "POST", "review_only": True},
                {"label": "Add to Watchlist", "href": f"/api/v3/opportunities/review/{market_id}/status", "method": "POST", "review_only": True, "status": "WATCHING"},
                {"label": "Send to Paper Review", "href": f"/api/v3/opportunities/review/{market_id}/status", "method": "POST", "review_only": True, "status": "PAPER_REVIEW"},
                {"label": "Reject Opportunity", "href": f"/api/v3/opportunities/review/{market_id}/status", "method": "POST", "review_only": True, "status": "REJECTED"},
                {"label": "Archive Review", "href": f"/api/v3/opportunities/review/{market_id}/status", "method": "POST", "review_only": True, "status": "ARCHIVED"},
            ],
        }
    )


def build_family_comparison(markets: list[dict[str, Any]], family_id: str) -> dict[str, Any]:
    enriched = enrich_markets_with_recommendations([dict(market) for market in markets])
    rows = []
    for market in enriched:
        edge = market.get("market_edge_recommendation") or {}
        if str(edge.get("family_id") or "") != str(family_id):
            continue
        rows.append({"market": market, "edge": edge})
    if not rows:
        rankings = rank_market_family(enriched)
        known_family_ids = sorted({str(row.get("family_id") or "") for row in rankings if row.get("family_id")})
        return safety_flags(
            {
                "version": APP_VERSION,
                "family_id": redact_text(family_id),
                "family_title": "Family not detected",
                "review_only": True,
                "detection_confidence": "unavailable",
                "items": [],
                "known_family_ids": known_family_ids,
                "warning": "No conservative family grouping matched this identifier. Family comparison was not forced.",
                "favorite_vs_edge": FAVORITE_VS_EDGE_EXPLAINER,
                "review_only_note": REVIEW_ONLY_NOTE,
            }
        )
    rows.sort(key=lambda row: row["edge"].get("rank_by_market_yes_price") or 999)
    edge_sorted = sorted(rows, key=lambda row: (row["edge"].get("yes_edge_pp") if row["edge"].get("yes_edge_pp") is not None else -999), reverse=True)
    no_edge_sorted = sorted(rows, key=lambda row: (row["edge"].get("no_edge_pp") if row["edge"].get("no_edge_pp") is not None else -999), reverse=True)
    family_title = rows[0]["edge"].get("family_title") or family_id
    items = []
    for row in rows:
        market = row["market"]
        edge = row["edge"]
        items.append(
            {
                "market_id": _market_key(market),
                "market_title": _market_title(market),
                "rank_by_market_yes_price": edge.get("rank_by_market_yes_price"),
                "rank_by_model_fair_yes": edge.get("rank_by_model_fair_yes"),
                "is_market_favorite": edge.get("is_market_favorite"),
                "is_model_favorite": edge.get("is_model_favorite"),
                "market_yes_price": edge.get("market_yes_price"),
                "model_fair_yes": edge.get("model_fair_yes"),
                "yes_edge_pp": edge.get("yes_edge_pp"),
                "no_edge_pp": edge.get("no_edge_pp"),
                "recommended_side": edge.get("recommended_side"),
                "side_badge": edge.get("side_badge"),
                "detail_href": f"/v3/markets/{_market_key(market)}",
                "news_odds_href": f"/v3/markets/{_market_key(market)}/news-odds",
                "news_adjusted_fair_yes": market.get("news_adjusted_fair_yes"),
                "news_confidence": market.get("news_confidence") or "unavailable",
                "why": edge.get("explanation"),
            }
        )
    return safety_flags(
        {
            "version": APP_VERSION,
            "family_id": redact_text(family_id),
            "family_title": family_title,
            "review_only": True,
            "detection_confidence": "conservative-title-pattern",
            "family_size": len(items),
            "items": items,
            "market_price_ranking": sorted(items, key=lambda row: row.get("rank_by_market_yes_price") or 999),
            "model_fair_ranking": sorted(items, key=lambda row: row.get("rank_by_model_fair_yes") or 999),
            "edge_ranking": sorted(items, key=lambda row: row.get("yes_edge_pp") if row.get("yes_edge_pp") is not None else -999, reverse=True),
            "favorite_by_market_price": next((item for item in items if item.get("is_market_favorite")), items[0] if items else {}),
            "favorite_by_model_fair": next((item for item in items if item.get("is_model_favorite")), items[0] if items else {}),
            "best_draft_yes_edge": {"market_id": _market_key(edge_sorted[0]["market"]), "yes_edge_pp": edge_sorted[0]["edge"].get("yes_edge_pp")} if edge_sorted else {},
            "best_draft_no_edge": {"market_id": _market_key(no_edge_sorted[0]["market"]), "no_edge_pp": no_edge_sorted[0]["edge"].get("no_edge_pp")} if no_edge_sorted else {},
            "no_clear_edge_markets": [item for item in items if item.get("recommended_side") in {"HOLD", "NO CLEAR EDGE", "INSUFFICIENT DATA"}],
            "news_odds_href": f"/v3/markets/family/{family_id}/news-odds",
            "news_odds_summary": "Family news analysis is review-only. Family normalization is not applied unless the family is clearly complete and mutually exclusive.",
            "warnings": ["Family grouping is conservative; incomplete groups may omit related markets.", "Favorite does not equal best wager.", "Family normalization not applied when grouping is incomplete."],
            "favorite_vs_edge": FAVORITE_VS_EDGE_EXPLAINER,
            "review_only_note": REVIEW_ONLY_NOTE,
            "formatted_price_example": _format_price(items[0].get("market_yes_price")) if items else "unavailable",
        }
    )


def opportunity_review_settings() -> dict[str, Any]:
    return safety_flags(
        {
            "version": APP_VERSION,
            "opportunity_review_enabled": bool(getattr(settings, "opportunity_review_enabled", True)),
            "opportunity_notes_enabled": bool(getattr(settings, "opportunity_notes_enabled", True)),
            "opportunity_review_store": str(getattr(settings, "opportunity_review_store", "runtime/opportunity_reviews")),
            "edge_detail_pages_enabled": bool(getattr(settings, "edge_detail_pages_enabled", True)),
            "edge_family_pages_enabled": bool(getattr(settings, "edge_family_pages_enabled", True)),
            "ai_edge_packet_lifecycle_enabled": bool(getattr(settings, "ai_edge_packet_lifecycle_enabled", True)),
            "ai_edge_review_only": bool(getattr(settings, "ai_edge_review_only", True)),
            "watchlist_review_only": bool(getattr(settings, "watchlist_review_only", True)),
            "paper_review_draft_only": bool(getattr(settings, "paper_review_draft_only", True)),
            "runtime_records_excluded_from_release_zip": True,
            "review_statuses": REVIEW_STATUSES,
            "data_state_values": DATA_STATE_VALUES,
            "review_actions_preserve_data_state": True,
            "audit_history_includes_source_route": True,
            "audit_history_includes_previous_new_state": True,
            "audit_history_includes_live_disabled": True,
            "ai_edge_packet_lifecycle_states": AI_EDGE_PACKET_LIFECYCLE_STATES,
            "review_only_note": REVIEW_ONLY_NOTE,
        }
    )
