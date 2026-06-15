from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR, settings

MARKET_DATA_DIR = DATA_DIR / "market_data"
MARKET_SNAPSHOTS_PATH = MARKET_DATA_DIR / "market_snapshots.json"
EXECUTION_QUALITY_PATH = MARKET_DATA_DIR / "execution_quality_simulations.json"

QUALITY_PASS_STATES = {"quality_pass", "quality_pass_with_warnings"}
QUALITY_BLOCK_STATES = {
    "blocked_by_stale_snapshot",
    "blocked_by_closed_market",
    "blocked_by_not_accepting_orders",
    "blocked_by_wide_spread",
    "blocked_by_insufficient_depth",
    "blocked_by_slippage",
    "blocked_by_invalid_order",
    "invalid_snapshot",
}

SIDE_VALUES = {"BUY", "SELL"}


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


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "open", "active"}


def _decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    if value is None or value == "":
        return default
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default
    if not number.is_finite():
        return default
    return number


def _dec(value: Any, default: str = "0") -> Decimal:
    return _decimal(value, Decimal(default)) or Decimal(default)


def _q(value: Decimal | None, places: str = "0.000001") -> float:
    if value is None:
        return 0.0
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _stable_hash(material: Any) -> str:
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_dt(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(value: Any, *, now: datetime | None = None) -> float | None:
    parsed = _parse_dt(value)
    if not parsed:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - parsed).total_seconds())


def _json_payload(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    parsed = json.loads(value or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("orderbook JSON must decode to an object")
    return parsed


def _levels(raw: Any, *, descending: bool) -> list[dict[str, Decimal]]:
    levels: list[dict[str, Decimal]] = []
    if isinstance(raw, dict):
        raw = raw.get("levels") or raw.get("orders") or raw.get("prices") or []
    if not isinstance(raw, list):
        return levels
    for item in raw:
        if isinstance(item, dict):
            price = _decimal(item.get("price") or item.get("p") or item.get("px"))
            size = _decimal(item.get("size") or item.get("quantity") or item.get("qty") or item.get("shares") or item.get("amount"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            price = _decimal(item[0])
            size = _decimal(item[1])
        else:
            continue
        if price is None or size is None or price <= 0 or size <= 0:
            continue
        levels.append({"price": price, "size": size})
    levels.sort(key=lambda row: row["price"], reverse=descending)
    return levels


def _depth_within(levels: list[dict[str, Decimal]], reference: Decimal, pct: Decimal, *, side: str) -> Decimal:
    if reference <= 0:
        return Decimal("0")
    if side == "bid":
        floor = reference * (Decimal("1") - pct)
        return sum((row["size"] for row in levels if row["price"] >= floor), Decimal("0"))
    ceiling = reference * (Decimal("1") + pct)
    return sum((row["size"] for row in levels if row["price"] <= ceiling), Decimal("0"))


def _simulate_levels(
    levels: list[dict[str, Decimal]],
    *,
    side: str,
    limit_price: Decimal,
    size: Decimal,
) -> dict[str, Decimal]:
    remaining = size
    filled = Decimal("0")
    notional = Decimal("0")
    for level in levels:
        price = level["price"]
        if side == "BUY" and price > limit_price:
            break
        if side == "SELL" and price < limit_price:
            break
        take = min(remaining, level["size"])
        if take <= 0:
            continue
        filled += take
        notional += take * price
        remaining -= take
        if remaining <= 0:
            break
    avg = notional / filled if filled > 0 else Decimal("0")
    return {"filled_size": filled, "unfilled_size": max(remaining, Decimal("0")), "avg_fill_price": avg, "notional": notional}


def parse_orderbook_metrics(payload: str | dict[str, Any]) -> dict[str, Any]:
    data = _json_payload(payload)
    book = data.get("orderbook") if isinstance(data.get("orderbook"), dict) else data
    bids = _levels(book.get("bids") or book.get("buy") or book.get("BUY") or [], descending=True)
    asks = _levels(book.get("asks") or book.get("sell") or book.get("SELL") or [], descending=False)
    best_bid = bids[0]["price"] if bids else None
    best_ask = asks[0]["price"] if asks else None
    warnings: list[str] = []
    blockers: list[str] = []
    if not bids or not asks:
        blockers.append("order book must include at least one valid bid and one valid ask.")
    if best_bid is not None and best_ask is not None and best_bid >= best_ask:
        blockers.append("best bid must be below best ask.")
    midpoint = (best_bid + best_ask) / Decimal("2") if best_bid is not None and best_ask is not None and best_bid < best_ask else None
    spread = best_ask - best_bid if midpoint is not None else None
    spread_bps = (spread / midpoint * Decimal("10000")) if spread is not None and midpoint and midpoint > 0 else None
    if spread_bps is not None and spread_bps > Decimal(str(settings.market_data_max_spread_bps)):
        warnings.append(f"spread {spread_bps.quantize(Decimal('0.01'))} bps exceeds configured threshold.")
    total_bid_depth = sum((row["size"] for row in bids), Decimal("0"))
    total_ask_depth = sum((row["size"] for row in asks), Decimal("0"))
    top_bid_size = bids[0]["size"] if bids else Decimal("0")
    top_ask_size = asks[0]["size"] if asks else Decimal("0")
    reference = midpoint or best_bid or best_ask or Decimal("0")
    return {
        "bids": [{"price": _q(row["price"]), "size": _q(row["size"])} for row in bids],
        "asks": [{"price": _q(row["price"]), "size": _q(row["size"])} for row in asks],
        "best_bid": _q(best_bid) if best_bid is not None else None,
        "best_ask": _q(best_ask) if best_ask is not None else None,
        "midpoint": _q(midpoint) if midpoint is not None else None,
        "spread": _q(spread) if spread is not None else None,
        "spread_bps": _q(spread_bps, "0.01") if spread_bps is not None else None,
        "top_bid_size": _q(top_bid_size),
        "top_ask_size": _q(top_ask_size),
        "bid_depth_1pct": _q(_depth_within(bids, reference, Decimal("0.01"), side="bid")),
        "ask_depth_1pct": _q(_depth_within(asks, reference, Decimal("0.01"), side="ask")),
        "bid_depth_5pct": _q(_depth_within(bids, reference, Decimal("0.05"), side="bid")),
        "ask_depth_5pct": _q(_depth_within(asks, reference, Decimal("0.05"), side="ask")),
        "total_bid_depth": _q(total_bid_depth),
        "total_ask_depth": _q(total_ask_depth),
        "warnings": warnings,
        "blockers": blockers,
        "status": "invalid_book" if blockers else "wide_spread" if warnings else "liquid",
    }


def build_market_snapshot(
    payload: str | dict[str, Any],
    *,
    source: str = "local_fixture",
    snapshot_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    data = _json_payload(payload)
    metrics = parse_orderbook_metrics(data)
    now = created_at or _text(data.get("created_at")) or _now()
    active = _bool(data.get("active"), True)
    closed = _bool(data.get("closed"), False)
    accepting_orders = _bool(data.get("accepting_orders", data.get("acceptingOrders")), active and not closed)
    resolution_status = _text(data.get("resolution_status") or data.get("resolutionStatus") or ("closed" if closed else "unresolved"))
    warnings = list(metrics.get("warnings") or [])
    blockers = list(metrics.get("blockers") or [])
    if not active:
        blockers.append("market is not active.")
    if closed:
        blockers.append("market is closed.")
    if not accepting_orders:
        blockers.append("market is not accepting orders.")
    if metrics.get("total_bid_depth", 0) < settings.market_data_min_total_depth:
        warnings.append("total bid depth is below configured threshold.")
    if metrics.get("total_ask_depth", 0) < settings.market_data_min_total_depth:
        warnings.append("total ask depth is below configured threshold.")
    status = "invalid_book" if metrics.get("status") == "invalid_book" else "closed" if closed else "not_accepting_orders" if not accepting_orders else "wide_spread" if metrics.get("status") == "wide_spread" else "thin" if warnings else "liquid"
    raw_public = {
        key: data.get(key)
        for key in [
            "market_id",
            "condition_id",
            "token_id",
            "question",
            "slug",
            "active",
            "closed",
            "accepting_orders",
            "resolution_status",
            "last_trade_price",
            "yes_price",
            "no_price",
            "orderbook",
            "bids",
            "asks",
        ]
    }
    snapshot = {
        "snapshot_id": snapshot_id or f"mds_{uuid4().hex[:12]}",
        "version": "0.9.0-market-data-snapshot-v1",
        "created_at": now,
        "source": _text(source or data.get("source") or "local_fixture"),
        "market_id": _text(data.get("market_id") or data.get("marketId") or data.get("condition_id") or data.get("conditionId")),
        "condition_id": _text(data.get("condition_id") or data.get("conditionId")),
        "token_id": _text(data.get("token_id") or data.get("tokenId") or data.get("asset_id") or data.get("assetId")),
        "question": _text(data.get("question") or data.get("title")),
        "slug": _text(data.get("slug")),
        "active": active,
        "closed": closed,
        "accepting_orders": accepting_orders,
        "resolution_status": resolution_status,
        "best_bid": metrics.get("best_bid"),
        "best_ask": metrics.get("best_ask"),
        "midpoint": metrics.get("midpoint"),
        "spread": metrics.get("spread"),
        "spread_bps": metrics.get("spread_bps"),
        "last_trade_price": _q(_decimal(data.get("last_trade_price") or data.get("lastTradePrice"))),
        "yes_price": _q(_decimal(data.get("yes_price") or data.get("yesPrice"))),
        "no_price": _q(_decimal(data.get("no_price") or data.get("noPrice"))),
        "top_bid_size": metrics.get("top_bid_size"),
        "top_ask_size": metrics.get("top_ask_size"),
        "bid_depth_1pct": metrics.get("bid_depth_1pct"),
        "ask_depth_1pct": metrics.get("ask_depth_1pct"),
        "bid_depth_5pct": metrics.get("bid_depth_5pct"),
        "ask_depth_5pct": metrics.get("ask_depth_5pct"),
        "total_bid_depth": metrics.get("total_bid_depth"),
        "total_ask_depth": metrics.get("total_ask_depth"),
        "tick_size": _q(_decimal(data.get("tick_size") or data.get("tickSize"), Decimal("0.01"))),
        "min_order_size": _q(_decimal(data.get("min_order_size") or data.get("minOrderSize"), Decimal("1"))),
        "fee_rate": _q(_decimal(data.get("fee_rate") or data.get("feeRate"), Decimal("0"))),
        "bids": metrics.get("bids", [])[:50],
        "asks": metrics.get("asks", [])[:50],
        "raw_public_fields_hash": _stable_hash(raw_public),
        "status": status,
        "warnings": warnings,
        "blockers": blockers,
        "secret_values_returned": False,
        "network_attempted": False,
        "guardrail": "Local market-data snapshot only. It contains public/fixture market data, no credentials, and never submits or cancels orders.",
    }
    return snapshot


def load_market_snapshots() -> list[dict[str, Any]]:
    rows = _read_json(MARKET_SNAPSHOTS_PATH, [])
    return rows if isinstance(rows, list) else []


def save_market_snapshots(rows: list[dict[str, Any]]) -> None:
    _write_json(MARKET_SNAPSHOTS_PATH, rows)


def record_market_snapshot(payload: str | dict[str, Any], *, source: str = "local_fixture") -> dict[str, Any]:
    item = build_market_snapshot(payload, source=source)
    rows = load_market_snapshots()
    rows.append(item)
    save_market_snapshots(rows)
    return item


def list_market_snapshots(
    *,
    limit: int = 100,
    market_id: str | None = None,
    token_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_market_snapshots()))
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted or _text(row.get("condition_id")) == wanted]
    if token_id:
        wanted = _text(token_id)
        rows = [row for row in rows if _text(row.get("token_id")) == wanted]
    if status:
        wanted = _text(status)
        rows = [row for row in rows if _text(row.get("status")) == wanted]
    return rows[: max(0, int(limit))]


def get_market_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    wanted = _text(snapshot_id)
    for row in load_market_snapshots():
        if _text(row.get("snapshot_id")) == wanted:
            return row
    return None


def latest_market_snapshot(*, market_id: str = "", token_id: str = "") -> dict[str, Any] | None:
    for row in list_market_snapshots(limit=10000):
        if token_id and _text(row.get("token_id")) == _text(token_id):
            return row
        if market_id and _text(row.get("market_id")) == _text(market_id):
            return row
        if market_id and _text(row.get("condition_id")) == _text(market_id):
            return row
    return None


def _snapshot_age_status(snapshot: dict[str, Any] | None, max_age_seconds: int) -> tuple[bool, float | None]:
    if not snapshot:
        return True, None
    age = _age_seconds(snapshot.get("created_at"))
    if age is None:
        return True, None
    return age > max_age_seconds, age


def build_execution_quality_simulation(
    *,
    side: str,
    token_id: str = "",
    price: float | str = 0,
    size: float | str = 0,
    order_type: str = "limit",
    time_in_force: str = "GTC",
    snapshot_id: str = "",
    market_id: str = "",
    max_slippage_bps: float | None = None,
    max_spread_bps: float | None = None,
    max_unfilled: float = 0,
    source_ticket_id: str = "",
    source_intent_id: str = "",
    simulation_id: str | None = None,
    created_at: str | None = None,
    record: bool = False,
) -> dict[str, Any]:
    normalized_side = _text(side or "BUY", "BUY").upper()
    limit_price = _dec(price)
    order_size = _dec(size)
    max_slippage = Decimal(str(max_slippage_bps if max_slippage_bps is not None else settings.market_data_max_slippage_bps))
    max_spread = Decimal(str(max_spread_bps if max_spread_bps is not None else settings.market_data_max_spread_bps))
    max_unfilled_dec = _dec(max_unfilled)
    snapshot = get_market_snapshot(snapshot_id) if snapshot_id else latest_market_snapshot(market_id=market_id, token_id=token_id)
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str, *, severity: str = "blocker") -> None:
        checks.append({"name": name, "passed": bool(passed), "severity": severity, "blocking": severity == "blocker" and not passed, "detail": detail})
        if severity == "blocker" and not passed:
            blockers.append(detail)
        elif severity == "warning" and (not passed or detail):
            warnings.append(detail)

    check("side_valid", normalized_side in SIDE_VALUES, "side must be BUY or SELL.")
    check("price_valid", limit_price > 0 and limit_price < 1, "price must be greater than 0 and less than 1.")
    check("size_valid", order_size > 0, "size must be greater than 0.")
    check("snapshot_present", bool(snapshot), "market-data snapshot is required for execution-quality simulation.")

    if not snapshot:
        state = "invalid_snapshot" if blockers else "blocked_by_stale_snapshot"
        return _finalize_simulation(
            simulation_id=simulation_id,
            created_at=created_at,
            state=state,
            snapshot={},
            side=normalized_side,
            token_id=token_id,
            market_id=market_id,
            price=limit_price,
            size=order_size,
            order_type=order_type,
            time_in_force=time_in_force,
            blockers=blockers,
            warnings=warnings,
            checks=checks,
            source_ticket_id=source_ticket_id,
            source_intent_id=source_intent_id,
            record=record,
        )

    market_id = market_id or _text(snapshot.get("market_id"))
    token_id = token_id or _text(snapshot.get("token_id"))
    is_stale, age = _snapshot_age_status(snapshot, int(settings.market_data_max_age_seconds))
    check("snapshot_fresh", not is_stale, f"snapshot age {round(age or 0, 2)}s exceeds max {settings.market_data_max_age_seconds}s.")
    check("market_open", not bool(snapshot.get("closed")), "market is closed.")
    check("accepting_orders", bool(snapshot.get("accepting_orders")), "market is not accepting orders.")
    check("snapshot_book_valid", _text(snapshot.get("status")) != "invalid_book", "snapshot order book is invalid.")
    spread = _dec(snapshot.get("spread_bps"))
    check("spread_within_threshold", spread <= max_spread, f"spread {spread:g} bps exceeds max {max_spread:g} bps.")
    levels = _levels(snapshot.get("asks") if normalized_side == "BUY" else snapshot.get("bids"), descending=normalized_side == "SELL")
    fill = _simulate_levels(levels, side=normalized_side, limit_price=limit_price, size=order_size)
    midpoint = _dec(snapshot.get("midpoint"))
    avg = fill["avg_fill_price"]
    filled = fill["filled_size"]
    unfilled = fill["unfilled_size"]
    notional = fill["notional"]
    top_depth = _dec(snapshot.get("top_ask_size") if normalized_side == "BUY" else snapshot.get("top_bid_size"))
    total_depth = _dec(snapshot.get("total_ask_depth") if normalized_side == "BUY" else snapshot.get("total_bid_depth"))
    check("top_depth_threshold", top_depth >= Decimal(str(settings.market_data_min_top_depth)), f"top-of-book depth {top_depth:g} is below minimum {settings.market_data_min_top_depth:g}.", severity="warning")
    check("total_depth_threshold", total_depth >= Decimal(str(settings.market_data_min_total_depth)), f"total executable-side depth {total_depth:g} is below minimum {settings.market_data_min_total_depth:g}.", severity="warning")
    check("depth_sufficient", unfilled <= max_unfilled_dec, f"unfilled size {unfilled:g} exceeds max {max_unfilled_dec:g}.")
    if midpoint > 0 and filled > 0:
        raw_slippage = ((avg - midpoint) / midpoint * Decimal("10000")) if normalized_side == "BUY" else ((midpoint - avg) / midpoint * Decimal("10000"))
        slippage_bps = max(raw_slippage, Decimal("0"))
    else:
        slippage_bps = Decimal("0")
    check("slippage_within_threshold", slippage_bps <= max_slippage, f"estimated slippage {slippage_bps.quantize(Decimal('0.01'))} bps exceeds max {max_slippage:g} bps.")

    if not blockers and warnings:
        state = "quality_pass_with_warnings"
    elif not blockers:
        state = "quality_pass"
    elif any("closed" in item for item in blockers):
        state = "blocked_by_closed_market"
    elif any("not accepting" in item for item in blockers):
        state = "blocked_by_not_accepting_orders"
    elif any("spread" in item for item in blockers):
        state = "blocked_by_wide_spread"
    elif any("unfilled" in item for item in blockers):
        state = "blocked_by_insufficient_depth"
    elif any("slippage" in item for item in blockers):
        state = "blocked_by_slippage"
    elif any("snapshot age" in item for item in blockers):
        state = "blocked_by_stale_snapshot"
    else:
        state = "blocked_by_invalid_order"

    return _finalize_simulation(
        simulation_id=simulation_id,
        created_at=created_at,
        state=state,
        snapshot=snapshot,
        side=normalized_side,
        token_id=token_id,
        market_id=market_id,
        price=limit_price,
        size=order_size,
        order_type=order_type,
        time_in_force=time_in_force,
        blockers=blockers,
        warnings=warnings,
        checks=checks,
        source_ticket_id=source_ticket_id,
        source_intent_id=source_intent_id,
        record=record,
        fill=fill,
        slippage_bps=slippage_bps,
        top_depth=top_depth,
        total_depth=total_depth,
        snapshot_age_seconds=age,
    )


def _finalize_simulation(
    *,
    simulation_id: str | None,
    created_at: str | None,
    state: str,
    snapshot: dict[str, Any],
    side: str,
    token_id: str,
    market_id: str,
    price: Decimal,
    size: Decimal,
    order_type: str,
    time_in_force: str,
    blockers: list[str],
    warnings: list[str],
    checks: list[dict[str, Any]],
    source_ticket_id: str,
    source_intent_id: str,
    record: bool,
    fill: dict[str, Decimal] | None = None,
    slippage_bps: Decimal = Decimal("0"),
    top_depth: Decimal = Decimal("0"),
    total_depth: Decimal = Decimal("0"),
    snapshot_age_seconds: float | None = None,
) -> dict[str, Any]:
    fill = fill or {"filled_size": Decimal("0"), "unfilled_size": size, "avg_fill_price": Decimal("0"), "notional": Decimal("0")}
    liquidity_score = 0
    if size > 0:
        liquidity_score = int(max(0, min(100, (total_depth / size) * Decimal("25"))))
    spread_bps = _dec(snapshot.get("spread_bps")) if snapshot else Decimal("0")
    spread_score = int(max(0, min(100, Decimal("100") - (spread_bps / Decimal("10")))))
    item = {
        "simulation_id": simulation_id or f"eqs_{uuid4().hex[:12]}",
        "version": "0.9.0-execution-quality-v1",
        "created_at": created_at or _now(),
        "recorded": bool(record),
        "state": state,
        "market_id": _text(market_id or snapshot.get("market_id")),
        "condition_id": _text(snapshot.get("condition_id")),
        "token_id": _text(token_id or snapshot.get("token_id")),
        "snapshot_id": _text(snapshot.get("snapshot_id")),
        "snapshot_created_at": _text(snapshot.get("created_at")),
        "snapshot_age_seconds": round(snapshot_age_seconds, 3) if snapshot_age_seconds is not None else None,
        "snapshot_status": _text(snapshot.get("status") or "missing"),
        "side": side,
        "order_type": _text(order_type or "limit"),
        "time_in_force": _text(time_in_force or "GTC"),
        "limit_price": _q(price),
        "size": _q(size),
        "estimated_fill_quantity": _q(fill["filled_size"]),
        "estimated_average_fill_price": _q(fill["avg_fill_price"]),
        "estimated_notional": _q(fill["notional"]),
        "estimated_unfilled_size": _q(fill["unfilled_size"]),
        "estimated_slippage_bps": _q(slippage_bps, "0.01"),
        "top_of_book_depth": _q(top_depth),
        "total_executable_depth": _q(total_depth),
        "best_bid": snapshot.get("best_bid"),
        "best_ask": snapshot.get("best_ask"),
        "midpoint": snapshot.get("midpoint"),
        "spread_bps": snapshot.get("spread_bps"),
        "liquidity_score": liquidity_score,
        "spread_score": spread_score,
        "stale_data": state == "blocked_by_stale_snapshot",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "source_ticket_id": _text(source_ticket_id),
        "source_intent_id": _text(source_intent_id),
        "execution_allowed": False,
        "network_attempted": False,
        "secret_values_returned": False,
        "recommended_action": _quality_action(state),
        "guardrail": "Execution quality is a local estimate only. It is not a fill guarantee and never submits, cancels, signs, or touches wallets.",
    }
    item["simulation_hash"] = _stable_hash({
        "snapshot_id": item.get("snapshot_id"),
        "state": item.get("state"),
        "side": item.get("side"),
        "limit_price": item.get("limit_price"),
        "size": item.get("size"),
        "fill": item.get("estimated_fill_quantity"),
        "avg": item.get("estimated_average_fill_price"),
        "unfilled": item.get("estimated_unfilled_size"),
        "blockers": item.get("blockers"),
        "warnings": item.get("warnings"),
    })
    return item


def _quality_action(state: str) -> str:
    if state == "quality_pass":
        return "Market-data quality passes local thresholds; continue human review. This is not a fill guarantee."
    if state == "quality_pass_with_warnings":
        return "Review market-data warnings before any further paper/live-readiness workflow."
    if state == "blocked_by_stale_snapshot":
        return "Refresh or record a newer market-data snapshot before manual review."
    if state == "blocked_by_closed_market":
        return "Do not proceed; market is closed."
    if state == "blocked_by_not_accepting_orders":
        return "Do not proceed; market is not accepting orders."
    if state == "blocked_by_wide_spread":
        return "Do not proceed without resizing or waiting for tighter spread."
    if state == "blocked_by_insufficient_depth":
        return "Resize order or wait for more depth before manual review."
    if state == "blocked_by_slippage":
        return "Resize or improve limit price before manual review."
    return "Correct invalid order or snapshot fields."


def record_execution_quality_simulation(**kwargs: Any) -> dict[str, Any]:
    item = build_execution_quality_simulation(**kwargs, record=True)
    rows = load_execution_quality_simulations()
    rows.append(item)
    save_execution_quality_simulations(rows)
    return item


def load_execution_quality_simulations() -> list[dict[str, Any]]:
    rows = _read_json(EXECUTION_QUALITY_PATH, [])
    return rows if isinstance(rows, list) else []


def save_execution_quality_simulations(rows: list[dict[str, Any]]) -> None:
    _write_json(EXECUTION_QUALITY_PATH, rows)


def list_execution_quality_simulations(
    *,
    limit: int = 100,
    state: str | None = None,
    market_id: str | None = None,
    token_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = list(reversed(load_execution_quality_simulations()))
    if state:
        wanted = _text(state)
        rows = [row for row in rows if _text(row.get("state")) == wanted]
    if market_id:
        wanted = _text(market_id)
        rows = [row for row in rows if _text(row.get("market_id")) == wanted]
    if token_id:
        wanted = _text(token_id)
        rows = [row for row in rows if _text(row.get("token_id")) == wanted]
    return rows[: max(0, int(limit))]


def get_execution_quality_simulation(simulation_id: str) -> dict[str, Any] | None:
    wanted = _text(simulation_id)
    for row in load_execution_quality_simulations():
        if _text(row.get("simulation_id")) == wanted:
            return row
    return None


def summarize_market_data(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load_market_snapshots()
    statuses = Counter(_text(row.get("status") or "unknown") for row in rows)
    stale = 0
    for row in rows:
        is_stale, _age = _snapshot_age_status(row, int(settings.market_data_max_age_seconds))
        stale += 1 if is_stale else 0
    return {
        "count": len(rows),
        "by_status": dict(sorted(statuses.items())),
        "liquid": statuses.get("liquid", 0),
        "thin": statuses.get("thin", 0),
        "wide_spread": statuses.get("wide_spread", 0),
        "closed": statuses.get("closed", 0),
        "not_accepting_orders": statuses.get("not_accepting_orders", 0),
        "invalid_book": statuses.get("invalid_book", 0),
        "stale": stale,
        "public_fetch_enabled": bool(settings.market_data_public_fetch_enabled),
        "guardrail": "Market-data snapshots are local public/fixture records. They never include secrets or execute trades.",
    }


def summarize_execution_quality(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load_execution_quality_simulations()
    states = Counter(_text(row.get("state") or "unknown") for row in rows)
    return {
        "count": len(rows),
        "by_state": dict(sorted(states.items())),
        "quality_pass": states.get("quality_pass", 0),
        "quality_pass_with_warnings": states.get("quality_pass_with_warnings", 0),
        "blocked_by_stale_snapshot": states.get("blocked_by_stale_snapshot", 0),
        "blocked_by_closed_market": states.get("blocked_by_closed_market", 0),
        "blocked_by_wide_spread": states.get("blocked_by_wide_spread", 0),
        "blocked_by_insufficient_depth": states.get("blocked_by_insufficient_depth", 0),
        "blocked_by_slippage": states.get("blocked_by_slippage", 0),
        "blocked_total": sum(states.get(state, 0) for state in QUALITY_BLOCK_STATES),
        "network_attempted": False,
        "execution_allowed": False,
        "note": "Execution-quality simulations are estimates only and are not fill guarantees.",
    }


def build_market_data_board(*, limit: int = 100, market_id: str | None = None, token_id: str | None = None, status: str | None = None) -> dict[str, Any]:
    rows = list_market_snapshots(limit=limit, market_id=market_id, token_id=token_id, status=status)
    return {
        "version": "0.9.0-market-data-board-v1",
        "mode": "market_data_intelligence_v090",
        "generated_at": _now(),
        "summary": summarize_market_data(rows),
        "items": rows,
        "filters": {"market_id": market_id or "", "token_id": token_id or "", "status": status or ""},
        "fetch_boundary": public_fetch_status(),
        "guardrail": "Read-only market-data intelligence. Public fetch is disabled by default and no trade action is available.",
    }


def build_execution_quality_board(*, limit: int = 100, state: str | None = None, market_id: str | None = None, token_id: str | None = None) -> dict[str, Any]:
    rows = list_execution_quality_simulations(limit=limit, state=state, market_id=market_id, token_id=token_id)
    return {
        "version": "0.9.0-execution-quality-board-v1",
        "mode": "execution_quality_simulator_v090",
        "generated_at": _now(),
        "summary": summarize_execution_quality(rows),
        "items": rows,
        "filters": {"state": state or "", "market_id": market_id or "", "token_id": token_id or ""},
        "guardrail": "Execution-quality simulations are local estimates only. They never guarantee fills or submit orders.",
    }


def market_data_alerts(board: dict[str, Any] | None = None, quality_board: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    board = board or build_market_data_board(limit=100)
    quality_board = quality_board or build_execution_quality_board(limit=100)
    ms = board.get("summary", {})
    qs = quality_board.get("summary", {})
    alerts: list[dict[str, Any]] = []
    if ms.get("stale"):
        alerts.append(_alert("warning", "market_data_stale", "Market-data snapshots stale", f"{ms.get('stale')} saved snapshot(s) exceed the configured age threshold.", {"stale": ms.get("stale")}, "/market-data"))
    if ms.get("wide_spread"):
        alerts.append(_alert("warning", "market_data_wide_spread", "Wide spread snapshots exist", f"{ms.get('wide_spread')} snapshot(s) exceed spread thresholds.", {"wide_spread": ms.get("wide_spread")}, "/market-data"))
    if ms.get("closed") or ms.get("not_accepting_orders"):
        alerts.append(_alert("warning", "market_data_closed", "Closed or non-accepting markets in snapshots", "At least one saved snapshot is closed or not accepting orders.", {"closed": ms.get("closed"), "not_accepting": ms.get("not_accepting_orders")}, "/market-data"))
    if qs.get("blocked_total"):
        alerts.append(_alert("warning", "execution_quality_blocked", "Execution-quality blockers exist", f"{qs.get('blocked_total')} recorded simulation(s) are blocked by stale data, spread, depth, slippage, or market status.", {"blocked_total": qs.get("blocked_total")}, "/execution-quality"))
    if not ms.get("count"):
        alerts.append(_alert("info", "market_data_missing", "No market-data snapshots recorded", "Record a local fixture snapshot before relying on execution-quality checks.", {}, "/market-data"))
    return alerts[:8]


def _alert(level: str, kind: str, title: str, detail: str, data: dict[str, Any], link: str) -> dict[str, Any]:
    return {"timestamp": _now(), "level": level, "kind": kind, "title": title, "detail": detail, "market_id": None, "question": None, "source": "market_data_intelligence_v090", "link": link, "data": data}


def public_fetch_status() -> dict[str, Any]:
    if not settings.market_data_public_fetch_enabled:
        status = "public_fetch_disabled"
    else:
        status = "public_fetch_unimplemented"
    return {
        "status": status,
        "enabled": bool(settings.market_data_public_fetch_enabled),
        "timeout_seconds": settings.market_data_timeout_seconds,
        "network_attempted": False,
        "secret_values_returned": False,
        "note": "Public order-book fetch is disabled by default. This build supports local fixtures/manual JSON first and does not fake network success.",
    }


def fetch_market_data_preview(*, market_id: str = "", token_id: str = "") -> dict[str, Any]:
    return {
        "version": "0.9.0-market-data-fetch-preview-v1",
        "created_at": _now(),
        "market_id": _text(market_id),
        "token_id": _text(token_id),
        **public_fetch_status(),
        "snapshot_preview": None,
        "guardrail": "Fetch preview is read-only and never authenticated. No network is attempted unless future code explicitly implements the enabled fetch path.",
    }


def market_snapshots_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "snapshot_id", "created_at", "source", "market_id", "condition_id", "token_id", "active", "closed", "accepting_orders", "resolution_status", "status", "best_bid", "best_ask", "midpoint", "spread", "spread_bps", "top_bid_size", "top_ask_size", "bid_depth_1pct", "ask_depth_1pct", "bid_depth_5pct", "ask_depth_5pct", "total_bid_depth", "total_ask_depth", "warning_count", "blocker_count", "warnings", "blockers", "raw_public_fields_hash"
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        item = dict(row)
        item["warning_count"] = len(item.get("warnings") or [])
        item["blocker_count"] = len(item.get("blockers") or [])
        item["warnings"] = " | ".join(str(x) for x in item.get("warnings") or [])
        item["blockers"] = " | ".join(str(x) for x in item.get("blockers") or [])
        writer.writerow({key: item.get(key, "") for key in fields})
    return output.getvalue()


def execution_quality_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "simulation_id", "created_at", "state", "market_id", "token_id", "snapshot_id", "snapshot_age_seconds", "side", "order_type", "time_in_force", "limit_price", "size", "estimated_fill_quantity", "estimated_average_fill_price", "estimated_notional", "estimated_unfilled_size", "estimated_slippage_bps", "top_of_book_depth", "total_executable_depth", "liquidity_score", "spread_score", "blocker_count", "warning_count", "blockers", "warnings", "source_ticket_id", "source_intent_id", "simulation_hash"
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        item = dict(row)
        item["blockers"] = " | ".join(str(x) for x in item.get("blockers") or [])
        item["warnings"] = " | ".join(str(x) for x in item.get("warnings") or [])
        writer.writerow({key: item.get(key, "") for key in fields})
    return output.getvalue()
