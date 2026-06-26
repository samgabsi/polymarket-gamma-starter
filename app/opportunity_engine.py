from __future__ import annotations

from typing import Any

from .evidence_scoring import score_market_evidence
from .risk import check_paper_buy
from .paper_trading import load_portfolio


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _market_id(market: dict[str, Any]) -> str:
    return str(market.get("id") or market.get("market_id") or "")


def _question(market: dict[str, Any]) -> str:
    return str(market.get("question") or market.get("title") or "Untitled market")


def _confidence_band(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 65:
        return "medium-high"
    if score >= 50:
        return "medium"
    if score >= 35:
        return "low-medium"
    return "low"


def _workflow_stage(evidence_score: float, edge_percent: float, risk_ok: bool, watched: bool) -> str:
    if evidence_score < 25:
        return "Research needed"
    if evidence_score < 55:
        return "Evidence gathering"
    if abs(edge_percent) < 2.0:
        return "Watch"
    if not risk_ok:
        return "Risk blocked"
    if watched:
        return "Ready for paper review"
    return "Add to watchlist"


def rank_opportunities(
    markets: list[dict[str, Any]],
    *,
    watchlist: list[dict[str, Any]] | None = None,
    max_items: int = 50,
    default_stake: float = 100.0,
) -> list[dict[str, Any]]:
    """Build an explainable opportunity ranking from existing local signals.

    Inputs are intentionally local/read-only: Gamma market data, deterministic
    probability model output, local evidence packets, watchlist, and paper-risk
    constraints. No wallet, no orders, no paid AI keys.
    """
    watched_ids = {str(row.get("market_id") or row.get("id") or "") for row in (watchlist or [])}
    portfolio = load_portfolio()
    rows: list[dict[str, Any]] = []

    for market in markets:
        market_id = _market_id(market)
        pm = market.get("probability_model") or {}
        ep = market.get("evidence_probability") or {}
        edge_recommendation = market.get("market_edge_recommendation") or {}
        evidence = score_market_evidence(market_id)
        evidence_score = _num(evidence.get("score"))

        market_probability = ep.get("market_probability", pm.get("market_probability"))
        model_probability = ep.get("evidence_adjusted_probability", pm.get("model_probability"))
        edge = ep.get("evidence_adjusted_edge", pm.get("edge"))
        edge_percent = _num(ep.get("evidence_adjusted_edge_percent", pm.get("edge_percent")))
        confidence_score = _num(ep.get("evidence_adjusted_confidence_score", pm.get("confidence_score")))

        opportunity_score = _num(market.get("opportunity_score"))
        volume_24hr = _num(market.get("volume_24hr"))
        liquidity = _num(market.get("liquidity"))
        tradability = _num((market.get("score_components") or {}).get("tradability_score"))
        watched = market_id in watched_ids

        price = _num(market_probability, 0.5)
        risk_check = check_paper_buy(market, portfolio, stake=default_stake, price=price or 0.5, outcome="YES")
        risk_ok = bool(risk_check.get("ok"))

        liquidity_score = min(100.0, liquidity / 2500.0)
        volume_score = min(100.0, volume_24hr / 1000.0)
        abs_edge_score = min(100.0, abs(edge_percent) * 12.0)
        evidence_component = min(100.0, evidence_score)
        confidence_component = min(100.0, confidence_score)
        risk_component = 100.0 if risk_ok else 25.0
        watch_component = 8.0 if watched else 0.0

        composite = (
            abs_edge_score * 0.28
            + confidence_component * 0.22
            + evidence_component * 0.18
            + liquidity_score * 0.12
            + volume_score * 0.10
            + min(100.0, opportunity_score) * 0.06
            + risk_component * 0.04
            + watch_component
        )

        if edge is None or market_probability is None or model_probability is None:
            action = "research_only"
        elif edge_percent >= 3 and confidence_score >= 45 and risk_ok:
            action = "paper_buy_candidate"
        elif edge_percent <= -3:
            action = "avoid_or_review_yes"
        elif evidence_score < 55:
            action = "collect_evidence"
        else:
            action = "watch"

        reasons: list[str] = []
        if abs(edge_percent) >= 3:
            reasons.append(f"edge {edge_percent:+.2f}%")
        if evidence_score >= 55:
            reasons.append(f"evidence {evidence_score:.0f}/100")
        elif evidence_score > 0:
            reasons.append(f"evidence incomplete {evidence_score:.0f}/100")
        else:
            reasons.append("no evidence packet yet")
        if liquidity >= 10000:
            reasons.append("usable liquidity")
        if volume_24hr >= 5000:
            reasons.append("active 24h volume")
        if watched:
            reasons.append("watchlisted")
        if not risk_ok:
            reasons.append("paper risk check blocks new exposure")

        rows.append(
            {
                "market_id": market_id,
                "question": _question(market),
                "category": market.get("category") or "",
                "market_probability": market_probability,
                "model_probability": model_probability,
                "edge": edge,
                "edge_percent": round(edge_percent, 2),
                "confidence_score": round(confidence_score, 1),
                "confidence": ep.get("evidence_adjusted_confidence") or pm.get("confidence") or _confidence_band(confidence_score),
                "evidence_score": round(evidence_score, 1),
                "evidence_readiness": evidence.get("readiness") or "not_started",
                "risk_ok": risk_ok,
                "risk_reasons": risk_check.get("reasons") or [],
                "opportunity_score": round(opportunity_score, 1),
                "tradability_score": round(tradability, 1),
                "volume_24hr": volume_24hr,
                "liquidity": liquidity,
                "rank_score": round(composite, 1),
                "workflow_stage": _workflow_stage(evidence_score, edge_percent, risk_ok, watched),
                "recommended_action": action,
                "recommended_side": edge_recommendation.get("recommended_side", "INSUFFICIENT DATA"),
                "side_badge": edge_recommendation.get("side_badge", "INSUFFICIENT DATA"),
                "market_edge_recommendation": edge_recommendation,
                "family_rank_label": edge_recommendation.get("group_rank_label", "No family detected"),
                "model_fair_source": edge_recommendation.get("model_fair_source", "unavailable"),
                "yes_edge_pp": edge_recommendation.get("yes_edge_pp"),
                "no_edge_pp": edge_recommendation.get("no_edge_pp"),
                "watched": watched,
                "reason_codes": reasons,
                "url": market.get("polymarket_url") or market.get("polymarket_search_url") or market.get("url"),
            }
        )

    return sorted(rows, key=lambda r: (r["rank_score"], abs(_num(r.get("edge_percent"))), r.get("liquidity") or 0), reverse=True)[:max_items]


def opportunity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts: dict[str, int] = {}
    stage_counts: dict[str, int] = {}
    for row in rows:
        action_counts[row.get("recommended_action", "unknown")] = action_counts.get(row.get("recommended_action", "unknown"), 0) + 1
        stage_counts[row.get("workflow_stage", "unknown")] = stage_counts.get(row.get("workflow_stage", "unknown"), 0) + 1
    paper_candidates = [r for r in rows if r.get("recommended_action") == "paper_buy_candidate"]
    return {
        "count": len(rows),
        "paper_candidate_count": len(paper_candidates),
        "max_rank_score": max([_num(r.get("rank_score")) for r in rows], default=0.0),
        "avg_evidence_score": round(sum(_num(r.get("evidence_score")) for r in rows) / len(rows), 1) if rows else 0.0,
        "action_counts": action_counts,
        "stage_counts": stage_counts,
        "note": "Opportunity engine is local/paper-only and ranks markets for research review, not live execution.",
    }
