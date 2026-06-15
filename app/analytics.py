from __future__ import annotations

import csv
from io import StringIO
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def trade_analytics(trades: list[dict[str, Any]], portfolio_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    buys = [t for t in trades if str(t.get("side", "")).upper() == "BUY"]
    sells = [t for t in trades if str(t.get("side", "")).upper() == "SELL"]
    settlements = [t for t in trades if str(t.get("side", "")).upper() == "SETTLE"]
    realized_trades = sells + settlements
    realized = [_safe_float(t.get("realized_pnl")) for t in realized_trades]
    wins = [x for x in realized if x > 0]
    losses = [x for x in realized if x < 0]
    total_staked = sum(_safe_float(t.get("cost"), _safe_float(t.get("stake"))) for t in buys)
    total_proceeds = sum(_safe_float(t.get("proceeds")) for t in realized_trades)
    realized_pnl = sum(realized)
    avg_buy_price = sum(_safe_float(t.get("price")) for t in buys) / len(buys) if buys else 0.0
    avg_sell_price = sum(_safe_float(t.get("price")) for t in sells) / len(sells) if sells else 0.0
    unique_markets = len({str(t.get("market_id")) for t in trades if t.get("market_id") is not None})
    open_unrealized = _safe_float((portfolio_summary or {}).get("total_pnl")) - realized_pnl if portfolio_summary else 0.0
    return {
        "trade_count": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "settlement_count": len(settlements),
        "unique_markets": unique_markets,
        "total_staked": round(total_staked, 4),
        "total_proceeds": round(total_proceeds, 4),
        "realized_pnl": round(realized_pnl, 4),
        "open_unrealized_component": round(open_unrealized, 4),
        "win_count": len(wins),
        "loss_count": len(losses),
        "flat_count": len([x for x in realized if x == 0]),
        "win_rate_percent": round((len(wins) / len(realized)) * 100, 2) if realized else 0.0,
        "avg_win": round(sum(wins) / len(wins), 4) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 4) if losses else 0.0,
        "largest_win": round(max(wins), 4) if wins else 0.0,
        "largest_loss": round(min(losses), 4) if losses else 0.0,
        "avg_buy_price": round(avg_buy_price, 4),
        "avg_sell_price": round(avg_sell_price, 4),
        "last_trade_at": trades[-1].get("timestamp") if trades else None,
    }


def trades_to_csv(trades: list[dict[str, Any]]) -> str:
    fields = [
        "timestamp", "side", "market_id", "question", "outcome", "price", "shares",
        "stake", "cost", "proceeds", "cost_basis", "realized_pnl", "settlement_id", "winning_outcome", "reason", "id",
    ]
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for trade in trades:
        writer.writerow(trade)
    return buf.getvalue()
