from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR
from .risk import check_paper_buy

PAPER_DIR = DATA_DIR / "paper"
PORTFOLIO_PATH = PAPER_DIR / "portfolio.json"
TRADES_PATH = PAPER_DIR / "trades.json"
DEFAULT_CASH = 10000.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _safe_position_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _initial_portfolio() -> dict[str, Any]:
    return {
        "cash": DEFAULT_CASH,
        "starting_cash": DEFAULT_CASH,
        "positions": {},
        "created_at": _now(),
        "updated_at": _now(),
    }


def load_portfolio() -> dict[str, Any]:
    return _read_json(PORTFOLIO_PATH, _initial_portfolio())


def save_portfolio(portfolio: dict[str, Any]) -> dict[str, Any]:
    portfolio["updated_at"] = _now()
    _write_json(PORTFOLIO_PATH, portfolio)
    return portfolio


def load_trades() -> list[dict[str, Any]]:
    rows = _read_json(TRADES_PATH, [])
    return rows if isinstance(rows, list) else []


def save_trades(rows: list[dict[str, Any]]) -> None:
    _write_json(TRADES_PATH, rows)


def reset_portfolio(cash: float = DEFAULT_CASH) -> dict[str, Any]:
    portfolio = _initial_portfolio()
    portfolio["cash"] = float(cash)
    portfolio["starting_cash"] = float(cash)
    save_portfolio(portfolio)
    save_trades([])
    return portfolio


def _position_key(market_id: str, outcome: str) -> str:
    return f"{market_id}:{outcome.upper()}"


def buy(market: dict[str, Any], outcome: str = "YES", price: float | None = None, stake: float = 100.0, reason: str = "manual paper trade") -> dict[str, Any]:
    portfolio = load_portfolio()
    price = float(price if price is not None else _market_price(market, outcome))
    stake = float(stake)
    if price <= 0 or price >= 1:
        raise ValueError("Paper buy price must be between 0 and 1")
    if stake <= 0:
        raise ValueError("Paper stake must be positive")
    if stake > float(portfolio.get("cash", 0.0)):
        raise ValueError("Not enough paper cash")
    risk_result = check_paper_buy(market, portfolio, stake=stake, price=price, outcome=outcome)
    if not risk_result.get("approved"):
        details = "; ".join(item.get("detail", item.get("name", "risk failure")) for item in risk_result.get("blocking_failures", []))
        raise ValueError(f"Paper risk check failed: {details}")

    shares = stake / price
    key = _position_key(str(market.get("id")), outcome)
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(key, {})
    old_shares = float(pos.get("shares", 0.0))
    old_cost = float(pos.get("cost_basis", 0.0))
    new_shares = old_shares + shares
    new_cost = old_cost + stake
    now = _now()
    positions[key] = {
        "market_id": str(market.get("id")),
        "question": market.get("question"),
        "outcome": outcome.upper(),
        "shares": round(new_shares, 8),
        "cost_basis": round(new_cost, 4),
        "avg_price": round(new_cost / new_shares, 4),
        "last_price": round(price, 4),
        "opened_at": pos.get("opened_at") or now,
        "updated_at": now,
        "position_status": pos.get("position_status", "active"),
        "exit_plan": pos.get("exit_plan", {}),
        "plan_updated_at": pos.get("plan_updated_at"),
    }
    portfolio["cash"] = round(float(portfolio.get("cash", 0.0)) - stake, 4)
    save_portfolio(portfolio)

    trade = {
        "id": uuid4().hex,
        "timestamp": _now(),
        "side": "BUY",
        "market_id": str(market.get("id")),
        "question": market.get("question"),
        "outcome": outcome.upper(),
        "price": round(price, 4),
        "stake": round(stake, 4),
        "shares": round(shares, 8),
        "reason": reason,
        "risk": risk_result,
    }
    trades = load_trades()
    trades.append(trade)
    save_trades(trades)
    return {"portfolio": summarize_portfolio(), "trade": trade}


def sell(market: dict[str, Any], outcome: str = "YES", price: float | None = None, shares: float | None = None, reason: str = "manual paper sell") -> dict[str, Any]:
    portfolio = load_portfolio()
    positions = portfolio.setdefault("positions", {})
    key = _position_key(str(market.get("id")), outcome)
    pos = positions.get(key)
    if not pos:
        raise ValueError("No open paper position for that market/outcome")
    price = float(price if price is not None else _market_price(market, outcome))
    if price <= 0 or price >= 1:
        raise ValueError("Paper sell price must be between 0 and 1")
    open_shares = float(pos.get("shares", 0.0))
    sell_shares = float(shares if shares is not None else open_shares)
    if sell_shares <= 0 or sell_shares > open_shares:
        raise ValueError("Invalid share amount")
    proceeds = sell_shares * price
    cost_reduction = float(pos.get("cost_basis", 0.0)) * (sell_shares / open_shares)
    realized_pnl = proceeds - cost_reduction
    remaining = open_shares - sell_shares
    if remaining <= 1e-9:
        positions.pop(key, None)
    else:
        pos["shares"] = round(remaining, 8)
        pos["cost_basis"] = round(float(pos.get("cost_basis", 0.0)) - cost_reduction, 4)
        pos["avg_price"] = round(pos["cost_basis"] / remaining, 4)
        pos["last_price"] = round(price, 4)
        pos["updated_at"] = _now()
    portfolio["cash"] = round(float(portfolio.get("cash", 0.0)) + proceeds, 4)
    save_portfolio(portfolio)
    trade = {
        "id": uuid4().hex,
        "timestamp": _now(),
        "side": "SELL",
        "market_id": str(market.get("id")),
        "question": market.get("question"),
        "outcome": outcome.upper(),
        "price": round(price, 4),
        "shares": round(sell_shares, 8),
        "proceeds": round(proceeds, 4),
        "realized_pnl": round(realized_pnl, 4),
        "reason": reason,
    }
    trades = load_trades()
    trades.append(trade)
    save_trades(trades)
    return {"portfolio": summarize_portfolio(), "trade": trade}


def summarize_portfolio(current_markets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return a render-safe paper portfolio summary.

    Older/dev data files may contain string, blank, or partially corrupt values.
    The positions page renders numeric fields with Jinja format specifiers, so this
    summary normalizes all numeric values instead of allowing one stale local row
    to raise a 500 error. Malformed position containers are treated as empty.
    """
    portfolio = load_portfolio()
    if not isinstance(portfolio, dict):
        portfolio = _initial_portfolio()
    market_index = {str(m.get("id")): m for m in (current_markets or []) if isinstance(m, dict)}
    raw_positions = portfolio.get("positions")
    if not isinstance(raw_positions, dict):
        raw_positions = {}
    positions = []
    total_value = 0.0
    total_cost = 0.0
    for key, raw_pos in raw_positions.items():
        if not isinstance(raw_pos, dict):
            continue
        pos = dict(raw_pos)
        market_id = str(pos.get("market_id") or key).split(":", 1)[0]
        outcome = str(pos.get("outcome") or "YES").upper()
        market = market_index.get(market_id)
        current_price = _market_price(market, outcome) if market else _safe_float(pos.get("last_price"), _safe_float(pos.get("avg_price"), 0.5))
        current_price = min(max(current_price, 0.0), 1.0)
        shares = max(_safe_float(pos.get("shares"), 0.0), 0.0)
        cost = max(_safe_float(pos.get("cost_basis"), 0.0), 0.0)
        avg_price = _safe_float(pos.get("avg_price"), (cost / shares) if shares else current_price)
        last_price = _safe_float(pos.get("last_price"), current_price)
        value = shares * current_price
        pnl = value - cost
        plan = _safe_position_mapping(pos.get("exit_plan"))
        normalized_plan = dict(plan)
        for price_key in ("target_price", "stop_price"):
            if normalized_plan.get(price_key) in (None, ""):
                normalized_plan[price_key] = None
            else:
                normalized_plan[price_key] = round(_safe_float(normalized_plan.get(price_key), 0.0), 4)
        if normalized_plan.get("max_hold_days") in (None, ""):
            normalized_plan["max_hold_days"] = None
        else:
            try:
                normalized_plan["max_hold_days"] = int(normalized_plan.get("max_hold_days"))
            except (TypeError, ValueError):
                normalized_plan["max_hold_days"] = None
        row = dict(pos)
        row.update(
            {
                "market_id": market_id,
                "question": pos.get("question") or market_id,
                "outcome": outcome,
                "shares": round(shares, 8),
                "cost_basis": round(cost, 4),
                "avg_price": round(avg_price, 4),
                "last_price": round(last_price, 4),
                "current_price": round(current_price, 4),
                "market_value": round(value, 4),
                "unrealized_pnl": round(pnl, 4),
                "exit_plan": normalized_plan,
            }
        )
        positions.append(row)
        total_value += value
        total_cost += cost
    cash = _safe_float(portfolio.get("cash"), 0.0)
    starting = _safe_float(portfolio.get("starting_cash"), DEFAULT_CASH)
    equity = cash + total_value
    return {
        "cash": round(cash, 4),
        "starting_cash": round(starting, 4),
        "open_positions": positions,
        "open_position_count": len(positions),
        "open_cost_basis": round(total_cost, 4),
        "open_market_value": round(total_value, 4),
        "equity": round(equity, 4),
        "total_pnl": round(equity - starting, 4),
        "total_return_percent": round(((equity - starting) / starting) * 100, 2) if starting else 0.0,
        "updated_at": portfolio.get("updated_at"),
    }


def _market_price(market: dict[str, Any] | None, outcome: str = "YES") -> float:
    if not isinstance(market, dict):
        return 0.5
    outcomes = market.get("outcomes") or []
    if not isinstance(outcomes, list):
        outcomes = []
    for row in outcomes:
        if isinstance(row, dict) and str(row.get("name", "")).upper() == str(outcome).upper():
            return _safe_float(row.get("price"), 0.5)
    if outcomes and isinstance(outcomes[0], dict):
        return _safe_float(outcomes[0].get("price"), 0.5)
    return 0.5
