from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, settings
from .probability import attach_probability
from .scoring import attach_scores
from .strategy import recommend_paper_trades

BACKTEST_DIR = DATA_DIR / "backtests"
BACKTEST_DIR.mkdir(parents=True, exist_ok=True)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_snapshot(path: Path) -> dict[str, Any] | None:
    import json

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _market_price(market: dict[str, Any], outcome: str = "YES") -> float | None:
    outcomes = market.get("outcomes") or []
    for row in outcomes:
        if isinstance(row, dict) and str(row.get("name", "")).upper() == outcome.upper():
            try:
                return float(row.get("price"))
            except (TypeError, ValueError):
                return None
    if outcomes and isinstance(outcomes[0], dict):
        try:
            return float(outcomes[0].get("price"))
        except (TypeError, ValueError):
            return None
    return None


def list_backtests(limit: int = 20) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(BACKTEST_DIR.glob("*.json"), reverse=True)[:limit]:
        payload = _load_snapshot(path) or {}
        rows.append(
            {
                "filename": path.name,
                "path": str(path),
                "created_at": payload.get("created_at"),
                "snapshot_count": payload.get("snapshot_count"),
                "trade_count": payload.get("trade_count"),
                "total_pnl": payload.get("total_pnl"),
                "total_return_percent": payload.get("total_return_percent"),
            }
        )
    return rows


def run_snapshot_backtest(
    min_edge: float = 0.02,
    min_confidence_score: float = 35.0,
    stake: float = 100.0,
    max_trades_per_snapshot: int = 5,
    max_price: float = 0.95,
    save: bool = True,
) -> dict[str, Any]:
    """Replay saved snapshots using the current deterministic paper strategy.

    The backtest is intentionally simple: a recommendation in snapshot N is entered at
    that snapshot's price and marked at snapshot N+1's price. This is a sanity check,
    not a production-grade backtester.
    """
    paths = sorted(settings.snapshot_dir.glob("*.json"))
    snapshots = [p for p in (_load_snapshot(path) for path in paths) if p and (p.get("markets") or p.get("items"))]
    if len(snapshots) < 2:
        return {
            "ok": False,
            "message": "Need at least two saved snapshots. Use ?save=true on the dashboard or POST /api/snapshots, wait, then save another snapshot.",
            "snapshot_count": len(snapshots),
            "trade_count": 0,
            "trades": [],
        }

    trades: list[dict[str, Any]] = []
    for idx in range(len(snapshots) - 1):
        current = snapshots[idx]
        nxt = snapshots[idx + 1]
        current_markets = attach_probability(attach_scores(current.get("markets") or current.get("items") or []))
        next_index = {str(row.get("id")): row for row in (nxt.get("markets") or nxt.get("items") or [])}
        recs = recommend_paper_trades(
            current_markets,
            min_edge=min_edge,
            min_confidence_score=min_confidence_score,
            max_price=max_price,
            max_recommendations=max_trades_per_snapshot,
            default_stake=stake,
        )
        for rec in recs:
            market_id = str(rec.get("market_id"))
            entry_price = float(rec.get("market_probability") or 0)
            next_market = next_index.get(market_id)
            exit_price = _market_price(next_market or {}, rec.get("outcome", "YES")) if next_market else None
            if not exit_price or entry_price <= 0:
                continue
            shares = stake / entry_price
            exit_value = shares * exit_price
            pnl = exit_value - stake
            trades.append(
                {
                    "market_id": market_id,
                    "question": rec.get("question"),
                    "snapshot_in": current.get("created_at"),
                    "snapshot_out": nxt.get("created_at"),
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "stake": round(stake, 2),
                    "shares": round(shares, 6),
                    "pnl": round(pnl, 4),
                    "return_percent": round((pnl / stake) * 100.0, 2),
                    "edge_percent": rec.get("edge_percent"),
                    "confidence": rec.get("confidence"),
                    "reason_codes": rec.get("reason_codes") or [],
                }
            )

    total_staked = sum(float(t["stake"]) for t in trades)
    total_pnl = sum(float(t["pnl"]) for t in trades)
    wins = sum(1 for t in trades if float(t["pnl"]) > 0)
    losses = sum(1 for t in trades if float(t["pnl"]) < 0)
    result = {
        "ok": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message": "Snapshot-to-snapshot sanity backtest. Not financial advice and not a guarantee of execution.",
        "parameters": {
            "min_edge": min_edge,
            "min_confidence_score": min_confidence_score,
            "stake": stake,
            "max_trades_per_snapshot": max_trades_per_snapshot,
            "max_price": max_price,
        },
        "snapshot_count": len(snapshots),
        "trade_count": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate_percent": round((wins / len(trades)) * 100.0, 2) if trades else 0.0,
        "total_staked": round(total_staked, 2),
        "total_pnl": round(total_pnl, 4),
        "total_return_percent": round((total_pnl / total_staked) * 100.0, 2) if total_staked else 0.0,
        "trades": trades,
    }
    if save:
        import json

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = BACKTEST_DIR / f"backtest_{stamp}.json"
        out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        result["saved_path"] = str(out)
    return result
