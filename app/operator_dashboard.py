from __future__ import annotations

from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _market_id(market: dict) -> str:
    return str(market.get("id") or market.get("market_id") or "")


def _question(market: dict) -> str:
    return str(market.get("question") or market.get("title") or "Untitled market")


def build_operator_brief(
    *,
    markets: list[dict],
    movers: list[dict],
    alerts: list[dict],
    recommendations: list[dict],
    portfolio: dict,
    risk: dict,
    watchlist: list[dict],
    evidence_markets: list[dict],
    max_items: int = 12,
) -> dict:
    """Build a single operator-facing briefing from the existing local modules.

    This intentionally does not introduce external keys, live trading, or network-side
    automation. It just composes the current Gamma/CLOB/local evidence/probability/
    paper-trading data into a usable daily workflow.
    """
    watch_ids = {str(item.get("market_id")) for item in watchlist}

    research_candidates: list[dict] = []
    for market in markets:
        pm = market.get("probability_model") or {}
        score = _as_float(market.get("opportunity_score"))
        volume = _as_float(market.get("volume_24hr"))
        liquidity = _as_float(market.get("liquidity"))
        edge_percent = _as_float(pm.get("edge_percent"))
        if _market_id(market) in watch_ids or score >= 65 or abs(edge_percent) >= 3 or volume >= 10000:
            research_candidates.append(
                {
                    "market_id": _market_id(market),
                    "question": _question(market),
                    "opportunity_score": round(score, 2),
                    "volume_24hr": volume,
                    "liquidity": liquidity,
                    "edge_percent": edge_percent,
                    "confidence": pm.get("confidence") or "unknown",
                    "reason": _research_reason(market, watch_ids),
                    "watched": _market_id(market) in watch_ids,
                }
            )
    research_candidates.sort(key=lambda x: (x["watched"], x["opportunity_score"], x["volume_24hr"]), reverse=True)

    evidence_gaps: list[dict] = []
    for market in evidence_markets:
        ep = market.get("evidence_probability") or {}
        packet_count = int(ep.get("evidence_packet_count") or 0)
        readiness = ep.get("evidence_readiness") or ep.get("evidence_adjusted_confidence") or "unknown"
        edge = ep.get("evidence_adjusted_edge_percent")
        if packet_count == 0 or readiness in {"none", "low", "weak", "unknown"}:
            evidence_gaps.append(
                {
                    "market_id": _market_id(market),
                    "question": _question(market),
                    "packet_count": packet_count,
                    "readiness": readiness,
                    "edge_percent": edge,
                    "next_step": "Create evidence packet" if packet_count == 0 else "Add stronger sources/notes",
                }
            )
    evidence_gaps = evidence_gaps[:max_items]

    action_queue = []
    for alert in alerts[:max_items]:
        action_queue.append(
            {
                "priority": _alert_priority(alert),
                "kind": alert.get("kind", "alert"),
                "title": alert.get("title", "Alert"),
                "detail": alert.get("detail", ""),
                "market_id": alert.get("market_id"),
                "question": alert.get("question"),
            }
        )
    for rec in recommendations[:max_items]:
        action_queue.append(
            {
                "priority": 70,
                "kind": "paper_candidate",
                "title": "Paper candidate",
                "detail": f"EV/$100 {rec.get('expected_value_per_100'):+.2f} · edge {rec.get('edge_percent', 0):+.2f}%" if isinstance(rec.get("expected_value_per_100"), (int, float)) else "Paper recommendation",
                "market_id": rec.get("market_id"),
                "question": rec.get("question"),
            }
        )
    action_queue.sort(key=lambda x: x["priority"], reverse=True)

    risk_current = risk.get("current", {}) if isinstance(risk, dict) else {}
    risk_limits = risk.get("limits", {}) if isinstance(risk, dict) else {}
    operator_health = _operator_health(risk_current, risk_limits, alerts)

    return {
        "mode": "operator_brief_v1",
        "note": "Local/paper-only briefing. No wallet, no live orders, no external AI keys required.",
        "health": operator_health,
        "counts": {
            "markets_scanned": len(markets),
            "watchlist": len(watchlist),
            "alerts": len(alerts),
            "paper_recommendations": len(recommendations),
            "research_candidates": len(research_candidates),
            "evidence_gaps": len(evidence_gaps),
            "open_positions": int(portfolio.get("open_position_count") or 0),
        },
        "portfolio": {
            "cash": _as_float(portfolio.get("cash")),
            "equity": _as_float(portfolio.get("equity")),
            "total_return_percent": _as_float(portfolio.get("total_return_percent")),
            "open_position_count": int(portfolio.get("open_position_count") or 0),
        },
        "risk": {
            "total_exposure": _as_float(risk_current.get("total_exposure")),
            "exposure_remaining": _as_float(risk_current.get("exposure_remaining")),
            "open_positions": int(risk_current.get("open_positions") or 0),
            "max_open_positions": int(risk_limits.get("max_open_positions") or 0),
        },
        "action_queue": action_queue[:max_items],
        "research_candidates": research_candidates[:max_items],
        "evidence_gaps": evidence_gaps,
        "paper_recommendations": recommendations[:max_items],
        "movers": movers[:max_items],
    }


def _research_reason(market: dict, watch_ids: set[str]) -> str:
    reasons = []
    if _market_id(market) in watch_ids:
        reasons.append("watchlist")
    if _as_float(market.get("opportunity_score")) >= 65:
        reasons.append("high opportunity score")
    if _as_float(market.get("volume_24hr")) >= 10000:
        reasons.append("high 24h volume")
    pm = market.get("probability_model") or {}
    if abs(_as_float(pm.get("edge_percent"))) >= 3:
        reasons.append("model/market gap")
    return ", ".join(reasons) if reasons else "baseline candidate"


def _alert_priority(alert: dict) -> int:
    level = str(alert.get("level") or "info").lower()
    if level in {"critical", "danger"}:
        return 100
    if level in {"warning", "warn"}:
        return 80
    return 55


def _operator_health(risk_current: dict, risk_limits: dict, alerts: list[dict]) -> dict:
    warning_count = sum(1 for alert in alerts if str(alert.get("level") or "").lower() in {"warning", "critical", "danger"})
    max_positions = int(risk_limits.get("max_open_positions") or 0)
    open_positions = int(risk_current.get("open_positions") or 0)
    exposure_remaining = _as_float(risk_current.get("exposure_remaining"))
    if warning_count >= 3 or (max_positions and open_positions >= max_positions) or exposure_remaining <= 0:
        return {"status": "attention", "message": "Review risk/alerts before adding more paper exposure."}
    if warning_count:
        return {"status": "watch", "message": "Some workflow warnings exist; review action queue."}
    return {"status": "ok", "message": "Operator dashboard is clear for research and paper-only review."}
