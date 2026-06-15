from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR
from .paper_trading import load_portfolio, save_portfolio, load_trades, save_trades, summarize_portfolio

SETTLEMENTS_PATH = DATA_DIR / "paper" / "settlements.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _norm_outcome(value: Any) -> str:
    text = str(value or "YES").strip().upper()
    if not text:
        return "YES"
    return text


def load_settlements() -> list[dict[str, Any]]:
    rows = _read_json(SETTLEMENTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_settlements(rows: list[dict[str, Any]]) -> None:
    _write_json(SETTLEMENTS_PATH, rows)


def list_settlements(limit: int = 100, market_id: str | None = None) -> list[dict[str, Any]]:
    rows = list(reversed(load_settlements()))
    if market_id:
        rows = [row for row in rows if str(row.get("market_id")) == str(market_id)]
    return rows[:limit]


def settlement_summary(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load_settlements()
    total_realized = sum(_safe_float(row.get("total_realized_pnl")) for row in rows)
    total_payout = sum(_safe_float(row.get("total_payout")) for row in rows)
    closed_positions = sum(int(_safe_float(row.get("closed_position_count"))) for row in rows)
    return {
        "count": len(rows),
        "closed_position_count": closed_positions,
        "total_payout": round(total_payout, 4),
        "total_realized_pnl": round(total_realized, 4),
        "last_settlement_at": rows[0].get("settled_at") if rows else None,
        "note": "Manual paper settlements close local simulated positions only. They do not interact with Polymarket or a wallet.",
    }


def settlement_candidates(limit: int = 100) -> list[dict[str, Any]]:
    portfolio = load_portfolio()
    grouped: dict[str, dict[str, Any]] = {}
    for pos in (portfolio.get("positions") or {}).values():
        market_id = str(pos.get("market_id") or "")
        if not market_id:
            continue
        row = grouped.setdefault(
            market_id,
            {
                "market_id": market_id,
                "question": pos.get("question") or market_id,
                "outcomes": [],
                "position_count": 0,
                "cost_basis": 0.0,
                "shares": 0.0,
                "last_updated_at": pos.get("updated_at"),
            },
        )
        row["position_count"] += 1
        row["cost_basis"] += _safe_float(pos.get("cost_basis"))
        row["shares"] += _safe_float(pos.get("shares"))
        outcome = _norm_outcome(pos.get("outcome"))
        if outcome not in row["outcomes"]:
            row["outcomes"].append(outcome)
        if str(pos.get("updated_at") or "") > str(row.get("last_updated_at") or ""):
            row["last_updated_at"] = pos.get("updated_at")
    rows = []
    for row in grouped.values():
        row["cost_basis"] = round(row["cost_basis"], 4)
        row["shares"] = round(row["shares"], 8)
        rows.append(row)
    rows.sort(key=lambda item: (item.get("cost_basis", 0.0), item.get("last_updated_at") or ""), reverse=True)
    return rows[:limit]


def preview_settlement(market_id: str, winning_outcome: str = "YES") -> dict[str, Any]:
    winning = _norm_outcome(winning_outcome)
    portfolio = load_portfolio()
    positions = portfolio.get("positions") or {}
    matched = [pos for pos in positions.values() if str(pos.get("market_id")) == str(market_id)]
    rows: list[dict[str, Any]] = []
    total_cost = 0.0
    total_payout = 0.0
    for pos in matched:
        outcome = _norm_outcome(pos.get("outcome"))
        shares = _safe_float(pos.get("shares"))
        cost_basis = _safe_float(pos.get("cost_basis"))
        payout_price = 1.0 if outcome == winning else 0.0
        payout = shares * payout_price
        realized = payout - cost_basis
        rows.append(
            {
                "market_id": str(pos.get("market_id")),
                "question": pos.get("question"),
                "outcome": outcome,
                "shares": round(shares, 8),
                "cost_basis": round(cost_basis, 4),
                "payout_price": payout_price,
                "payout": round(payout, 4),
                "realized_pnl": round(realized, 4),
            }
        )
        total_cost += cost_basis
        total_payout += payout
    return {
        "market_id": str(market_id),
        "winning_outcome": winning,
        "open_position_count": len(matched),
        "total_cost_basis": round(total_cost, 4),
        "total_payout": round(total_payout, 4),
        "total_realized_pnl": round(total_payout - total_cost, 4),
        "positions": rows,
        "settlement_rule": "winning outcome pays 1.0; all other outcomes pay 0.0",
    }


def settle_market(
    market_id: str,
    *,
    winning_outcome: str = "YES",
    note: str = "",
    resolved_by: str = "local",
) -> dict[str, Any]:
    winning = _norm_outcome(winning_outcome)
    portfolio = load_portfolio()
    positions = portfolio.setdefault("positions", {})
    matching_keys = [key for key, pos in positions.items() if str(pos.get("market_id")) == str(market_id)]
    if not matching_keys:
        raise ValueError("No open paper positions for that market.")

    settlement_id = f"ps_{uuid4().hex[:12]}"
    settled_at = _now()
    settlement_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    total_cost = 0.0
    total_payout = 0.0

    for key in matching_keys:
        pos = positions.pop(key)
        outcome = _norm_outcome(pos.get("outcome"))
        shares = _safe_float(pos.get("shares"))
        cost_basis = _safe_float(pos.get("cost_basis"))
        payout_price = 1.0 if outcome == winning else 0.0
        payout = shares * payout_price
        realized = payout - cost_basis
        question = pos.get("question") or str(market_id)
        row = {
            "market_id": str(market_id),
            "question": question,
            "outcome": outcome,
            "shares": round(shares, 8),
            "cost_basis": round(cost_basis, 4),
            "avg_price": round(_safe_float(pos.get("avg_price")), 4),
            "payout_price": payout_price,
            "payout": round(payout, 4),
            "realized_pnl": round(realized, 4),
        }
        settlement_rows.append(row)
        trade_rows.append(
            {
                "id": uuid4().hex,
                "timestamp": settled_at,
                "side": "SETTLE",
                "market_id": str(market_id),
                "question": question,
                "outcome": outcome,
                "price": payout_price,
                "shares": round(shares, 8),
                "proceeds": round(payout, 4),
                "cost_basis": round(cost_basis, 4),
                "realized_pnl": round(realized, 4),
                "reason": f"manual paper settlement {settlement_id}: {note}".strip(),
                "settlement_id": settlement_id,
                "winning_outcome": winning,
            }
        )
        total_cost += cost_basis
        total_payout += payout

    portfolio["cash"] = round(_safe_float(portfolio.get("cash")) + total_payout, 4)
    save_portfolio(portfolio)

    trades = load_trades()
    trades.extend(trade_rows)
    save_trades(trades)

    record = {
        "settlement_id": settlement_id,
        "settled_at": settled_at,
        "market_id": str(market_id),
        "winning_outcome": winning,
        "note": note,
        "resolved_by": resolved_by,
        "closed_position_count": len(settlement_rows),
        "total_cost_basis": round(total_cost, 4),
        "total_payout": round(total_payout, 4),
        "total_realized_pnl": round(total_payout - total_cost, 4),
        "positions": settlement_rows,
        "trade_ids": [row["id"] for row in trade_rows],
        "mode": "paper_only_manual_settlement",
        "guardrail": "This closed local simulated positions only. No live trade, order, wallet, or Polymarket settlement occurred.",
    }
    settlements = load_settlements()
    settlements.append(record)
    save_settlements(settlements)
    return {"settlement": record, "trades": trade_rows, "portfolio": summarize_portfolio()}
