from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import settings


@dataclass(frozen=True)
class RiskLimits:
    max_stake_per_trade: float = settings.paper_max_stake_per_trade
    max_market_exposure: float = settings.paper_max_market_exposure
    max_total_exposure: float = settings.paper_max_total_exposure
    max_open_positions: int = settings.paper_max_open_positions
    min_liquidity: float = settings.paper_min_liquidity
    min_volume_24hr: float = settings.paper_min_volume_24hr
    block_extreme_prices: bool = settings.paper_block_extreme_prices
    min_price: float = settings.paper_min_price
    max_price: float = settings.paper_max_price


def _market_id(market: dict[str, Any]) -> str:
    return str(market.get("id", ""))


def _market_liquidity(market: dict[str, Any]) -> float:
    try:
        return float(market.get("liquidity") or 0.0)
    except Exception:
        return 0.0


def _market_volume_24hr(market: dict[str, Any]) -> float:
    try:
        return float(market.get("volume_24hr") or market.get("volume24hr") or 0.0)
    except Exception:
        return 0.0


def market_exposure(portfolio: dict[str, Any], market_id: str) -> float:
    total = 0.0
    for pos in (portfolio.get("positions") or {}).values():
        if str(pos.get("market_id")) == str(market_id):
            total += float(pos.get("cost_basis") or 0.0)
    return round(total, 4)


def total_exposure(portfolio: dict[str, Any]) -> float:
    total = 0.0
    for pos in (portfolio.get("positions") or {}).values():
        total += float(pos.get("cost_basis") or 0.0)
    return round(total, 4)


def open_position_count(portfolio: dict[str, Any]) -> int:
    return len(portfolio.get("positions") or {})


def check_paper_buy(
    market: dict[str, Any],
    portfolio: dict[str, Any],
    stake: float,
    price: float,
    outcome: str = "YES",
    limits: RiskLimits | None = None,
) -> dict[str, Any]:
    limits = limits or RiskLimits()
    stake = float(stake)
    price = float(price)
    market_id = _market_id(market)
    current_market_exposure = market_exposure(portfolio, market_id)
    current_total_exposure = total_exposure(portfolio)
    current_open_positions = open_position_count(portfolio)
    key = f"{market_id}:{str(outcome).upper()}"
    already_open = key in (portfolio.get("positions") or {})

    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str, severity: str = "block") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail, "severity": severity})

    add("positive_stake", stake > 0, f"stake={stake:.2f}")
    add("cash_available", stake <= float(portfolio.get("cash", 0.0)), f"cash={float(portfolio.get('cash', 0.0)):.2f}, stake={stake:.2f}")
    add("max_stake_per_trade", stake <= limits.max_stake_per_trade, f"stake={stake:.2f}, limit={limits.max_stake_per_trade:.2f}")
    add("max_market_exposure", current_market_exposure + stake <= limits.max_market_exposure, f"after={current_market_exposure + stake:.2f}, limit={limits.max_market_exposure:.2f}")
    add("max_total_exposure", current_total_exposure + stake <= limits.max_total_exposure, f"after={current_total_exposure + stake:.2f}, limit={limits.max_total_exposure:.2f}")
    add("max_open_positions", already_open or current_open_positions < limits.max_open_positions, f"open={current_open_positions}, limit={limits.max_open_positions}")
    add("min_liquidity", _market_liquidity(market) >= limits.min_liquidity, f"liquidity={_market_liquidity(market):.2f}, min={limits.min_liquidity:.2f}", severity="warn")
    add("min_volume_24hr", _market_volume_24hr(market) >= limits.min_volume_24hr, f"24h_volume={_market_volume_24hr(market):.2f}, min={limits.min_volume_24hr:.2f}", severity="warn")
    if limits.block_extreme_prices:
        add("price_bounds", limits.min_price <= price <= limits.max_price, f"price={price:.4f}, bounds={limits.min_price:.2f}-{limits.max_price:.2f}")
    else:
        add("price_bounds", True, "extreme-price blocking disabled", severity="info")

    blocking_failures = [c for c in checks if not c["passed"] and c["severity"] == "block"]
    warnings = [c for c in checks if not c["passed"] and c["severity"] == "warn"]
    return {
        "approved": not blocking_failures,
        "warnings_present": bool(warnings),
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "checks": checks,
        "limits": risk_limits_payload(limits),
        "exposure_before": {
            "market": current_market_exposure,
            "total": current_total_exposure,
            "open_positions": current_open_positions,
        },
        "exposure_after": {
            "market": round(current_market_exposure + stake, 4),
            "total": round(current_total_exposure + stake, 4),
            "open_positions": current_open_positions if already_open else current_open_positions + 1,
        },
    }


def risk_limits_payload(limits: RiskLimits | None = None) -> dict[str, Any]:
    limits = limits or RiskLimits()
    return {
        "max_stake_per_trade": limits.max_stake_per_trade,
        "max_market_exposure": limits.max_market_exposure,
        "max_total_exposure": limits.max_total_exposure,
        "max_open_positions": limits.max_open_positions,
        "min_liquidity": limits.min_liquidity,
        "min_volume_24hr": limits.min_volume_24hr,
        "block_extreme_prices": limits.block_extreme_prices,
        "min_price": limits.min_price,
        "max_price": limits.max_price,
    }


def risk_status(portfolio: dict[str, Any]) -> dict[str, Any]:
    limits = RiskLimits()
    exposure = total_exposure(portfolio)
    open_count = open_position_count(portfolio)
    return {
        "mode": "paper_only",
        "note": "Risk checks are enforced for local paper trades only. No live trading exists in this app.",
        "limits": risk_limits_payload(limits),
        "current": {
            "cash": round(float(portfolio.get("cash", 0.0)), 4),
            "total_exposure": exposure,
            "open_positions": open_count,
            "exposure_remaining": round(max(limits.max_total_exposure - exposure, 0.0), 4),
            "position_slots_remaining": max(limits.max_open_positions - open_count, 0),
        },
    }
