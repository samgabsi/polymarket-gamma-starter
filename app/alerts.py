from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .risk import check_paper_buy


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _alert(level: str, kind: str, title: str, detail: str, market: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "timestamp": _now(),
        "level": level,
        "kind": kind,
        "title": title,
        "detail": detail,
        "market_id": str(market.get("id")) if market else None,
        "question": market.get("question") if market else None,
        "data": data or {},
    }
    return payload


def generate_alerts(
    markets: list[dict[str, Any]],
    movers: list[dict[str, Any]] | None = None,
    portfolio: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    max_items: int = 50,
) -> list[dict[str, Any]]:
    """Generate deterministic local alerts.

    These are workflow/monitoring alerts, not trade advice and not live orders.
    """
    alerts: list[dict[str, Any]] = []

    if risk:
        current = risk.get("current", {})
        limits = risk.get("limits", {})
        total_exposure = _num(current.get("total_exposure"))
        max_total = _num(limits.get("max_total_exposure"))
        open_positions = int(_num(current.get("open_positions")))
        max_open = int(_num(limits.get("max_open_positions")))
        if max_total and total_exposure >= max_total * 0.8:
            alerts.append(_alert("warning", "risk", "Paper exposure is getting high", f"Paper exposure is ${total_exposure:,.0f} of ${max_total:,.0f} max.", data={"total_exposure": total_exposure, "max_total_exposure": max_total}))
        if max_open and open_positions >= max_open * 0.8:
            alerts.append(_alert("warning", "risk", "Paper position slots are getting full", f"Open paper positions: {open_positions}/{max_open}.", data={"open_positions": open_positions, "max_open_positions": max_open}))

    for pos in (portfolio or {}).get("open_positions", [])[:20]:
        pnl = _num(pos.get("unrealized_pnl"))
        cost = _num(pos.get("cost_basis"))
        pct = (pnl / cost * 100) if cost else 0.0
        if pct >= 20:
            alerts.append(_alert("info", "paper_pnl", "Paper position up more than 20%", f"{pos.get('question')} is up {pct:.1f}% unrealized.", data={"market_id": pos.get("market_id"), "pnl_percent": pct, "unrealized_pnl": pnl}))
        elif pct <= -20:
            alerts.append(_alert("warning", "paper_pnl", "Paper position down more than 20%", f"{pos.get('question')} is down {pct:.1f}% unrealized.", data={"market_id": pos.get("market_id"), "pnl_percent": pct, "unrealized_pnl": pnl}))

    for market in markets:
        pm = market.get("probability_model") or {}
        edge = _num(pm.get("edge"))
        conf_score = _num(pm.get("confidence_score"))
        signal = str(pm.get("signal") or "")
        if edge >= 0.08 and conf_score >= 55:
            alerts.append(_alert("info", "model_edge", "Large positive paper-model edge", f"Model edge {edge * 100:.1f}% with confidence score {conf_score:.0f}. Signal: {signal}.", market, {"edge": edge, "confidence_score": conf_score, "signal": signal}))
        if edge <= -0.08 and conf_score >= 55:
            alerts.append(_alert("warning", "model_edge", "Large negative paper-model edge", f"Model edge {edge * 100:.1f}% with confidence score {conf_score:.0f}. Signal: {signal}.", market, {"edge": edge, "confidence_score": conf_score, "signal": signal}))
        if _num(market.get("volume_24hr")) >= 10000 and _num(market.get("liquidity")) >= 50000:
            alerts.append(_alert("info", "activity", "High-activity liquid market", f"24h volume ${_num(market.get('volume_24hr')):,.0f}; liquidity ${_num(market.get('liquidity')):,.0f}.", market, {"volume_24hr": _num(market.get("volume_24hr")), "liquidity": _num(market.get("liquidity"))}))

    for mover in (movers or [])[:20]:
        vol_delta = _num(mover.get("volume_24hr_delta"))
        liq_delta = _num(mover.get("liquidity_delta"))
        if abs(vol_delta) >= 5000 or abs(liq_delta) >= 10000:
            level = "info" if vol_delta >= 0 or liq_delta >= 0 else "warning"
            alerts.append(_alert(level, "mover", "Large snapshot-to-snapshot movement", f"Volume delta ${vol_delta:+,.0f}; liquidity delta ${liq_delta:+,.0f}.", mover, {"volume_24hr_delta": vol_delta, "liquidity_delta": liq_delta}))

    severity = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (severity.get(a["level"], 9), a["kind"], a.get("question") or ""))
    return alerts[:max_items]


def summarize_alerts(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"critical": 0, "warning": 0, "info": 0}
    by_kind: dict[str, int] = {}
    for alert in alerts:
        counts[alert.get("level", "info")] = counts.get(alert.get("level", "info"), 0) + 1
        kind = str(alert.get("kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {"count": len(alerts), "levels": counts, "by_kind": by_kind}
