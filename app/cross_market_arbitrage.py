from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx

from .clob_client import ClobClient
from .config import APP_VERSION, PROJECT_ROOT, settings
from .gamma_client import GammaClient
from .market_edge import normalize_probability
from .platform_safety import redact_data, redact_text, safety_flags

ARBITRAGE_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "cross_market_arbitrage"
ARBITRAGE_AUDIT_PATH = ARBITRAGE_RUNTIME_DIR / "audit.jsonl"
ARBITRAGE_SCANS_PATH = ARBITRAGE_RUNTIME_DIR / "scans.jsonl"

REVIEW_ONLY_NOTE = (
    "Cross-market arbitrage is detection/review only. Candidates are not guaranteed profits and must be reviewed for fees, "
    "slippage, liquidity, settlement mismatch, timing risk, and venue-specific execution constraints before any action."
)
DATA_STATE_VALUES = ["live", "cached", "sample", "stale", "unavailable"]


@dataclass
class VenueMarket:
    venue: str
    venue_market_id: str
    event_title: str
    market_title: str
    outcome_side: str = "YES"
    yes_no_structure: str = "binary"
    normalized_outcome_label: str = "YES"
    category: str = ""
    close_time: str = ""
    resolution_source: str = ""
    resolution_rules: str = ""
    yes_bid: float | None = None
    yes_ask: float | None = None
    no_bid: float | None = None
    no_ask: float | None = None
    midpoint: float | None = None
    last_trade: float | None = None
    spread: float | None = None
    top_yes_ask_size: float = 0.0
    top_no_ask_size: float = 0.0
    available_depth: float = 0.0
    fees_bps: float = 0.0
    currency: str = "USD"
    min_order_size: float = 1.0
    market_url: str = ""
    api_timestamp: str = ""
    liquidity_score: float = 0.0
    mapping_confidence: float = 1.0
    disabled: bool = False
    status: str = "ok"
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VenueAdapter:
    venue_name = "unsupported"

    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled
        self.last_status: dict[str, Any] = {
            "venue": self.venue_name,
            "enabled": enabled,
            "configured": enabled,
            "live": False,
            "message": "Adapter not implemented.",
        }

    async def fetch_markets(self, limit: int = 25, *, demo: bool = False) -> list[VenueMarket]:
        self.last_status = {
            "venue": self.venue_name,
            "enabled": self.enabled,
            "configured": self.enabled,
            "live": False,
            "message": "Adapter scaffold only; no live requests were made.",
        }
        return []

    def status(self) -> dict[str, Any]:
        return dict(self.last_status)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact_data(row), sort_keys=True, default=str) + "\n")


def _venue_status_detail(status: dict[str, Any], *, demo_requested: bool) -> dict[str, Any]:
    row = dict(status)
    message = str(row.get("message") or "")
    text = message.lower()
    enabled = bool(row.get("enabled"))
    configured = bool(row.get("configured"))
    live = bool(row.get("live"))
    if live:
        feature_status = "working"
        data_state = "live"
        implication = "Live read-only venue data was returned; freshness and venue rules still require manual review."
        next_action = "Review candidate math, data age, fees, liquidity, and resolution rules before any external action."
    elif "placeholder" in text or "scaffold" in text or "not implemented" in text:
        feature_status = "scaffolded"
        data_state = "unavailable"
        implication = "This venue is listed for readiness tracking but contributes no scan data."
        next_action = "Implement and test a real read-only venue adapter before using this venue in scans."
    elif "fixture" in text or "deterministic" in text or demo_requested:
        feature_status = "partial" if enabled else "disabled"
        data_state = "sample"
        implication = "Sample fixture data is suitable for workflow validation only and must not be treated as current market data."
        next_action = "Turn off demo mode and explicitly enable/configure venues before interpreting scan output as live read-only data."
    elif not enabled:
        feature_status = "disabled"
        data_state = "unavailable"
        implication = "The venue is disabled and does not contribute live snapshots."
        next_action = "Enable the venue deliberately and review credentials/configuration before live read-only use."
    elif not configured:
        feature_status = "config_required"
        data_state = "unavailable"
        implication = "The venue is enabled but missing required configuration."
        next_action = "Add the required venue configuration, restart if needed, then rerun the scan."
    elif "unavailable" in text or "error" in text or "fetch" in text:
        feature_status = "error"
        data_state = "unavailable"
        implication = "The venue fetch failed or returned no usable data; absence of candidates is not evidence of no opportunity."
        next_action = "Inspect the redacted venue message and rerun after resolving network/API issues."
    else:
        feature_status = "unavailable"
        data_state = "unavailable"
        implication = "No usable venue data was returned."
        next_action = "Check venue configuration and rerun the scan."
    row.update(
        {
            "status": feature_status,
            "status_class": feature_status,
            "data_state": data_state,
            "data_state_reason": message,
            "operator_implication": implication,
            "next_action": next_action,
            "review_only": True,
            "live_disabled": True,
            "order_submitted": False,
            "trade_approved": False,
            "live_trading_armed": False,
        }
    )
    return row


def _scan_readiness(*, statuses: list[dict[str, Any]], markets: list[VenueMarket], demo_requested: bool, scanner_enabled: bool) -> dict[str, Any]:
    states = {str(status.get("data_state") or "unavailable") for status in statuses}
    if demo_requested or "sample" in states:
        data_state = "sample"
        reason = "Demo fixtures are in use, or the scanner is disabled and fell back to deterministic review fixtures."
    elif "live" in states:
        data_state = "live"
        reason = "At least one configured venue returned live read-only market rows."
    elif "stale" in states:
        data_state = "stale"
        reason = "Only stale venue data is available."
    elif "cached" in states:
        data_state = "cached"
        reason = "Only cached venue data is available."
    elif not markets:
        data_state = "unavailable"
        reason = "No venue returned usable market snapshots."
    else:
        data_state = "unavailable"
        reason = "Venue data state could not be verified."

    if not scanner_enabled:
        scanner_status = "disabled"
        scanner_reason = "ARBITRAGE_SCANNER_ENABLED is false; scans use deterministic sample fixtures unless explicitly configured."
        next_action = "Use demo mode for workflow review, or enable/configure live read-only scanning deliberately."
    elif data_state == "live":
        scanner_status = "working"
        scanner_reason = "Scanner is enabled and at least one venue returned live read-only data."
        next_action = "Review data freshness and each venue status before using a candidate outside this console."
    elif data_state == "sample":
        scanner_status = "partial"
        scanner_reason = "Scanner is enabled but this request used sample/demo mode."
        next_action = "Rerun with demo=false only after reviewing venue configuration."
    elif any(status.get("status") == "error" for status in statuses):
        scanner_status = "error"
        scanner_reason = "One or more enabled venues reported a fetch error."
        next_action = "Resolve venue errors before interpreting candidate absence."
    else:
        scanner_status = "unavailable"
        scanner_reason = "Scanner did not receive usable venue snapshots."
        next_action = "Check venue configuration and rerun the scan."

    return {
        "feature_id": "arbitrage.scanner_review",
        "status": scanner_status,
        "data_state": data_state,
        "data_state_reason": reason,
        "scanner_status_reason": scanner_reason,
        "operator_implication": "Arbitrage output is a review queue candidate set, not an execution instruction or guaranteed-profit claim.",
        "next_action": next_action,
        "review_only": True,
        "safe_review_only": True,
        "live_disabled": True,
        "order_submitted": False,
        "trade_approved": False,
        "live_trading_armed": False,
    }


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _normalize_text(value: Any) -> str:
    text = redact_text(str(value or "")).lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    tokens = [token for token in text.split() if token not in {"will", "the", "and", "for", "with", "from", "this", "that", "market"}]
    return " ".join(tokens)


def _similarity(a: Any, b: Any) -> float:
    left = _normalize_text(a)
    right = _normalize_text(b)
    if not left or not right:
        return 0.0
    direct = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    return round(max(direct, overlap), 4)


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _expiration_similarity(a: Any, b: Any) -> tuple[float, float | None]:
    left = _parse_dt(a)
    right = _parse_dt(b)
    if not left or not right:
        return 0.5, None
    delta_hours = abs((left - right).total_seconds()) / 3600.0
    if delta_hours <= 6:
        return 1.0, round(delta_hours, 2)
    if delta_hours <= 24:
        return 0.85, round(delta_hours, 2)
    if delta_hours <= 72:
        return 0.55, round(delta_hours, 2)
    return 0.15, round(delta_hours, 2)


def _annualized_return(net_margin_pct: float, combined_cost: float, close_time: Any) -> float | None:
    close = _parse_dt(close_time)
    if not close or combined_cost <= 0:
        return None
    days = max((close - datetime.now(timezone.utc)).total_seconds() / 86400.0, 1.0)
    return round((net_margin_pct / max(combined_cost * 100.0, 0.0001)) * (365.0 / days) * 100.0, 2)


def _side_size(market: VenueMarket, side: str) -> float:
    return market.top_yes_ask_size if side == "YES" else market.top_no_ask_size


def _ask(market: VenueMarket, side: str) -> float | None:
    return market.yes_ask if side == "YES" else market.no_ask


def _market_from_gamma_row(row: dict[str, Any]) -> VenueMarket | None:
    outcomes = row.get("outcomes") if isinstance(row.get("outcomes"), list) else []
    yes_price = None
    no_price = None
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        label = str(outcome.get("name") or "").strip().lower()
        price = normalize_probability(outcome.get("price"))
        if label in {"yes", "y"}:
            yes_price = price
        elif label in {"no", "n"}:
            no_price = price
    if yes_price is None and outcomes:
        first = outcomes[0]
        if isinstance(first, dict):
            yes_price = normalize_probability(first.get("price"))
    if no_price is None and yes_price is not None:
        no_price = round(1.0 - yes_price, 6)
    if yes_price is None:
        return None
    spread = 0.02
    yes_bid = max(0.01, yes_price - spread / 2.0)
    yes_ask = min(0.99, yes_price + spread / 2.0)
    no_bid = max(0.01, (no_price or 1.0 - yes_price) - spread / 2.0)
    no_ask = min(0.99, (no_price or 1.0 - yes_price) + spread / 2.0)
    liquidity = _safe_float(row.get("liquidity"), 0.0) or 0.0
    return VenueMarket(
        venue="polymarket",
        venue_market_id=str(row.get("id") or row.get("market_id") or row.get("slug") or ""),
        event_title=str(row.get("event_title") or row.get("event_slug") or ""),
        market_title=str(row.get("question") or row.get("title") or "Untitled Polymarket market"),
        category=str(row.get("category") or ""),
        close_time=str(row.get("end_date") or row.get("close_time") or ""),
        resolution_source=str(row.get("resolution_source") or "Polymarket market rules"),
        resolution_rules=str(row.get("description") or row.get("rules") or ""),
        yes_bid=round(yes_bid, 4),
        yes_ask=round(yes_ask, 4),
        no_bid=round(no_bid, 4),
        no_ask=round(no_ask, 4),
        midpoint=round(yes_price, 4),
        spread=round(yes_ask - yes_bid, 4),
        top_yes_ask_size=max(1.0, min(liquidity / 100.0, 500.0)),
        top_no_ask_size=max(1.0, min(liquidity / 100.0, 500.0)),
        available_depth=max(1.0, min(liquidity / 50.0, 1000.0)),
        fees_bps=0.0,
        market_url=str(row.get("polymarket_url") or row.get("url") or ""),
        api_timestamp=_now(),
        liquidity_score=min(1.0, liquidity / 10000.0),
        mapping_confidence=0.72,
        warnings=["Gamma outcome price used as a conservative top-of-book proxy because CLOB orderbook fetch is disabled."],
        raw=row,
    )


class PolymarketVenueAdapter(VenueAdapter):
    venue_name = "polymarket"

    def __init__(self, *, enabled: bool = True) -> None:
        super().__init__(enabled=enabled)

    async def fetch_markets(self, limit: int = 25, *, demo: bool = False) -> list[VenueMarket]:
        if demo or not bool(getattr(settings, "arbitrage_scanner_enabled", False)):
            self.last_status = {
                "venue": self.venue_name,
                "enabled": True,
                "configured": True,
                "live": False,
                "message": "Using deterministic review fixtures; live Polymarket fetch disabled.",
            }
            return [row for row in demo_venue_markets() if row.venue == "polymarket"][:limit]
        try:
            client = GammaClient()
            rows = await client.list_markets(limit=limit, active=True, closed=False, order="volume24hr")
            markets = [market for market in (_market_from_gamma_row(row) for row in rows) if market is not None]
            if bool(getattr(settings, "arbitrage_fetch_orderbooks", False)):
                markets = await self._attach_clob_books(markets)
            self.last_status = {
                "venue": self.venue_name,
                "enabled": True,
                "configured": True,
                "live": True,
                "message": f"Fetched {len(markets)} Polymarket markets from Gamma/CLOB read paths.",
            }
            return markets
        except Exception as exc:  # noqa: BLE001 - UI should degrade to explicit disabled state
            self.last_status = {
                "venue": self.venue_name,
                "enabled": True,
                "configured": True,
                "live": False,
                "message": f"Polymarket fetch unavailable: {redact_text(str(exc))}",
            }
            return []

    async def _attach_clob_books(self, markets: list[VenueMarket]) -> list[VenueMarket]:
        clob = ClobClient()
        out: list[VenueMarket] = []
        for market in markets:
            token_ids = market.raw.get("clob_token_ids") if isinstance(market.raw, dict) else []
            if not isinstance(token_ids, list) or not token_ids:
                out.append(market)
                continue
            try:
                book = await clob.get_order_book(str(token_ids[0]))
            except Exception:
                out.append(market)
                continue
            if book.get("best_bid") is not None:
                market.yes_bid = _safe_float(book.get("best_bid"), market.yes_bid)
            if book.get("best_ask") is not None:
                market.yes_ask = _safe_float(book.get("best_ask"), market.yes_ask)
            if market.yes_bid is not None:
                market.no_ask = round(1.0 - market.yes_bid, 4)
            if market.yes_ask is not None:
                market.no_bid = round(1.0 - market.yes_ask, 4)
            market.spread = book.get("spread")
            market.midpoint = book.get("midpoint")
            market.top_yes_ask_size = _safe_float(book.get("ask_depth_top10"), market.top_yes_ask_size) or market.top_yes_ask_size
            market.top_no_ask_size = _safe_float(book.get("bid_depth_top10"), market.top_no_ask_size) or market.top_no_ask_size
            market.warnings = []
            out.append(market)
        return out


def _kalshi_best_bid(levels: Any) -> tuple[float | None, float]:
    if not isinstance(levels, list) or not levels:
        return None, 0.0
    parsed: list[tuple[float, float]] = []
    for item in levels:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            price = _safe_float(item[0])
            size = _safe_float(item[1], 0.0) or 0.0
            if price is not None:
                parsed.append((price, size))
    if not parsed:
        return None, 0.0
    price, size = sorted(parsed, key=lambda row: row[0])[-1]
    return round(price, 4), size


def _market_from_kalshi_row(row: dict[str, Any], orderbook: dict[str, Any] | None = None) -> VenueMarket:
    yes_bid = normalize_probability(row.get("yes_bid_dollars") or row.get("yes_bid") or row.get("yes_bid_cents"))
    yes_ask = normalize_probability(row.get("yes_ask_dollars") or row.get("yes_ask") or row.get("yes_ask_cents"))
    no_bid = normalize_probability(row.get("no_bid_dollars") or row.get("no_bid") or row.get("no_bid_cents"))
    no_ask = normalize_probability(row.get("no_ask_dollars") or row.get("no_ask") or row.get("no_ask_cents"))
    yes_size = 0.0
    no_size = 0.0
    if orderbook:
        book = orderbook.get("orderbook_fp") if isinstance(orderbook.get("orderbook_fp"), dict) else orderbook.get("orderbook", {})
        ob_yes_bid, yes_size = _kalshi_best_bid(book.get("yes_dollars") or book.get("yes") or [])
        ob_no_bid, no_size = _kalshi_best_bid(book.get("no_dollars") or book.get("no") or [])
        yes_bid = ob_yes_bid if ob_yes_bid is not None else yes_bid
        no_bid = ob_no_bid if ob_no_bid is not None else no_bid
        if no_bid is not None:
            yes_ask = round(1.0 - no_bid, 4)
        if yes_bid is not None:
            no_ask = round(1.0 - yes_bid, 4)
    if yes_ask is None and no_bid is not None:
        yes_ask = round(1.0 - no_bid, 4)
    if no_ask is None and yes_bid is not None:
        no_ask = round(1.0 - yes_bid, 4)
    midpoint = normalize_probability(row.get("last_price_dollars") or row.get("last_price") or row.get("price"))
    if midpoint is None and yes_bid is not None and yes_ask is not None:
        midpoint = round((yes_bid + yes_ask) / 2.0, 4)
    spread = round(yes_ask - yes_bid, 4) if yes_bid is not None and yes_ask is not None else None
    ticker = str(row.get("ticker") or row.get("market_ticker") or "")
    event_ticker = str(row.get("event_ticker") or row.get("series_ticker") or "")
    return VenueMarket(
        venue="kalshi",
        venue_market_id=ticker,
        event_title=str(row.get("event_title") or row.get("series_title") or event_ticker),
        market_title=str(row.get("title") or row.get("subtitle") or row.get("market_title") or ticker),
        category=str(row.get("category") or ""),
        close_time=str(row.get("close_time") or row.get("expiration_time") or row.get("expected_expiration_time") or ""),
        resolution_source=str(row.get("settlement_source") or row.get("rules_source") or "Kalshi market rules"),
        resolution_rules=str(row.get("rules_primary") or row.get("settlement_rules") or row.get("description") or ""),
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=no_bid,
        no_ask=no_ask,
        midpoint=midpoint,
        last_trade=normalize_probability(row.get("last_price_dollars") or row.get("last_price")),
        spread=spread,
        top_yes_ask_size=no_size,
        top_no_ask_size=yes_size,
        available_depth=max(yes_size, no_size, _safe_float(row.get("open_interest"), 0.0) or 0.0),
        fees_bps=_safe_float(row.get("fee_bps"), 0.0) or 0.0,
        currency="USD",
        min_order_size=1.0,
        market_url=str(row.get("market_url") or (f"https://kalshi.com/markets/{ticker}" if ticker else "")),
        api_timestamp=_now(),
        liquidity_score=min(1.0, max(yes_size, no_size) / 100.0),
        mapping_confidence=0.82,
        raw=row,
    )


class KalshiVenueAdapter(VenueAdapter):
    venue_name = "kalshi"

    def __init__(self, *, enabled: bool | None = None) -> None:
        super().__init__(enabled=bool(getattr(settings, "kalshi_enabled", False) if enabled is None else enabled))
        self.base_url = (getattr(settings, "kalshi_demo_api_base_url", "") if getattr(settings, "kalshi_use_demo", False) else getattr(settings, "kalshi_api_base_url", "")).rstrip("/")

    async def fetch_markets(self, limit: int = 25, *, demo: bool = False) -> list[VenueMarket]:
        if demo:
            self.last_status = {
                "venue": self.venue_name,
                "enabled": self.enabled,
                "configured": True,
                "live": False,
                "message": "Using deterministic Kalshi review fixtures.",
                "credentials_configured": bool(getattr(settings, "kalshi_api_key_id", None)),
            }
            return [row for row in demo_venue_markets() if row.venue == "kalshi"][:limit]
        if not self.enabled:
            self.last_status = {
                "venue": self.venue_name,
                "enabled": False,
                "configured": False,
                "live": False,
                "message": "Kalshi adapter disabled. Set KALSHI_ENABLED=true to request public market data.",
                "credentials_configured": bool(getattr(settings, "kalshi_api_key_id", None)),
            }
            return []
        try:
            async with httpx.AsyncClient(timeout=float(getattr(settings, "kalshi_timeout_seconds", 8)), headers={"User-Agent": f"polymarket-op-console/{APP_VERSION}"}) as client:
                response = await client.get(f"{self.base_url}/markets", params={"status": "open", "limit": limit})
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("markets") if isinstance(payload, dict) else payload
                if not isinstance(rows, list):
                    rows = []
                markets: list[VenueMarket] = []
                for row in rows[:limit]:
                    if not isinstance(row, dict):
                        continue
                    orderbook = None
                    ticker = str(row.get("ticker") or "")
                    if ticker and bool(getattr(settings, "arbitrage_fetch_orderbooks", False)):
                        try:
                            ob_response = await client.get(f"{self.base_url}/markets/{ticker}/orderbook", params={"depth": 5})
                            if ob_response.status_code == 200:
                                orderbook = ob_response.json()
                        except Exception:
                            orderbook = None
                    markets.append(_market_from_kalshi_row(row, orderbook))
            self.last_status = {
                "venue": self.venue_name,
                "enabled": True,
                "configured": True,
                "live": True,
                "message": f"Fetched {len(markets)} Kalshi public market rows.",
                "credentials_configured": bool(getattr(settings, "kalshi_api_key_id", None)),
            }
            return markets
        except Exception as exc:  # noqa: BLE001
            self.last_status = {
                "venue": self.venue_name,
                "enabled": True,
                "configured": True,
                "live": False,
                "message": f"Kalshi fetch unavailable: {redact_text(str(exc))}",
                "credentials_configured": bool(getattr(settings, "kalshi_api_key_id", None)),
            }
            return []


class DisabledCompetitorAdapter(VenueAdapter):
    def __init__(self, venue_name: str) -> None:
        super().__init__(enabled=False)
        self.venue_name = venue_name
        self.last_status = {
            "venue": venue_name,
            "enabled": False,
            "configured": False,
            "live": False,
            "message": "Placeholder adapter only. This venue is not implemented and is excluded from scans.",
        }


class AdapterRegistry:
    def __init__(self, adapters: list[VenueAdapter]) -> None:
        self.adapters = adapters

    async def fetch_all(self, limit_per_venue: int = 25, *, demo: bool = False) -> tuple[list[VenueMarket], list[dict[str, Any]]]:
        markets: list[VenueMarket] = []
        statuses: list[dict[str, Any]] = []
        for adapter in self.adapters:
            fetched = await adapter.fetch_markets(limit_per_venue, demo=demo)
            markets.extend(fetched)
            statuses.append(adapter.status())
        return markets, statuses


def build_adapter_registry() -> AdapterRegistry:
    adapters: list[VenueAdapter] = [PolymarketVenueAdapter(enabled=True), KalshiVenueAdapter()]
    for venue in getattr(settings, "arbitrage_competitor_venues", []):
        adapters.append(DisabledCompetitorAdapter(venue))
    return AdapterRegistry(adapters)


def demo_venue_markets() -> list[VenueMarket]:
    close = "2026-07-19T00:00:00+00:00"
    return [
        VenueMarket(
            venue="polymarket",
            venue_market_id="pm_france_2026_world_cup",
            event_title="2026 FIFA World Cup",
            market_title="Will France win the 2026 FIFA World Cup?",
            category="sports",
            close_time=close,
            resolution_source="FIFA official result",
            resolution_rules="Resolves Yes if France wins the 2026 FIFA World Cup final.",
            yes_bid=0.19,
            yes_ask=0.20,
            no_bid=0.79,
            no_ask=0.80,
            midpoint=0.195,
            spread=0.01,
            top_yes_ask_size=150.0,
            top_no_ask_size=160.0,
            available_depth=150.0,
            market_url="https://polymarket.com/search?query=France%202026%20World%20Cup",
            api_timestamp=_now(),
            liquidity_score=0.85,
            mapping_confidence=0.95,
            raw={"fixture": True},
        ),
        VenueMarket(
            venue="kalshi",
            venue_market_id="KXWORLDCP-FRANCE",
            event_title="2026 FIFA World Cup winner",
            market_title="Will France win the 2026 FIFA World Cup?",
            category="sports",
            close_time=close,
            resolution_source="FIFA official result",
            resolution_rules="Resolves Yes if France wins the 2026 FIFA World Cup final.",
            yes_bid=0.23,
            yes_ask=0.24,
            no_bid=0.75,
            no_ask=0.76,
            midpoint=0.235,
            spread=0.01,
            top_yes_ask_size=100.0,
            top_no_ask_size=90.0,
            available_depth=90.0,
            fees_bps=7.0,
            market_url="https://kalshi.com/markets/KXWORLDCP-FRANCE",
            api_timestamp=_now(),
            liquidity_score=0.78,
            mapping_confidence=0.92,
            raw={"fixture": True},
        ),
        VenueMarket(
            venue="kalshi",
            venue_market_id="KXWORLDCP-FRANCE-GROUP",
            event_title="2026 FIFA World Cup group stage",
            market_title="Will France win its 2026 World Cup group?",
            category="sports",
            close_time="2026-06-30T00:00:00+00:00",
            resolution_source="FIFA official group table",
            resolution_rules="Resolves Yes if France finishes first in its group, not if it wins the tournament.",
            yes_bid=0.51,
            yes_ask=0.53,
            no_bid=0.47,
            no_ask=0.49,
            midpoint=0.52,
            spread=0.02,
            top_yes_ask_size=80.0,
            top_no_ask_size=80.0,
            available_depth=80.0,
            fees_bps=7.0,
            market_url="https://kalshi.com/markets/KXWORLDCP-FRANCE-GROUP",
            api_timestamp=_now(),
            liquidity_score=0.7,
            mapping_confidence=0.45,
            raw={"fixture": True},
        ),
    ]


def score_market_equivalence(a: VenueMarket, b: VenueMarket) -> dict[str, Any]:
    title_similarity = _similarity(a.market_title, b.market_title)
    outcome_similarity = _similarity(a.normalized_outcome_label, b.normalized_outcome_label)
    category_similarity = _similarity(a.category, b.category) if a.category or b.category else 0.7
    expiration_similarity, close_delta_hours = _expiration_similarity(a.close_time, b.close_time)
    resolution_similarity = max(_similarity(a.resolution_source, b.resolution_source), _similarity(a.resolution_rules, b.resolution_rules))
    venue_confidence = min(a.mapping_confidence, b.mapping_confidence)
    mismatch_flags: list[str] = []
    if close_delta_hours is not None and close_delta_hours > 24:
        mismatch_flags.append("close_dates_differ_materially")
    if resolution_similarity < 0.45:
        mismatch_flags.append("resolution_rule_mismatch")
    combined_title = f"{a.market_title} {b.market_title}".lower()
    if any(term in combined_title for term in ["group", "runoff", "conditional", "overtime"]) and title_similarity < 0.82:
        mismatch_flags.append("conditional_or_scope_mismatch")
    if a.yes_no_structure != b.yes_no_structure:
        mismatch_flags.append("yes_no_structure_mismatch")
    score = (
        title_similarity * 0.38
        + outcome_similarity * 0.12
        + expiration_similarity * 0.18
        + resolution_similarity * 0.20
        + category_similarity * 0.05
        + venue_confidence * 0.07
    )
    mismatch_risk = min(1.0, len(mismatch_flags) * 0.22 + (1.0 - resolution_similarity) * 0.35 + (1.0 - title_similarity) * 0.20)
    return {
        "title_similarity": round(title_similarity, 4),
        "outcome_similarity": round(outcome_similarity, 4),
        "expiration_similarity": round(expiration_similarity, 4),
        "expiration_delta_hours": close_delta_hours,
        "resolution_rule_similarity": round(resolution_similarity, 4),
        "category_similarity": round(category_similarity, 4),
        "venue_confidence": round(venue_confidence, 4),
        "equivalence_score": round(max(0.0, min(score, 1.0)), 4),
        "resolution_mismatch_risk": round(mismatch_risk, 4),
        "mismatch_flags": mismatch_flags,
        "deterministic_first": True,
        "ai_semantic_match_used": False,
    }


def generate_candidate_pairs(markets: list[VenueMarket], *, min_title_similarity: float = 0.35) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for idx, left in enumerate(markets):
        for right in markets[idx + 1 :]:
            if left.venue == right.venue:
                continue
            match = score_market_equivalence(left, right)
            if match["title_similarity"] >= min_title_similarity:
                pairs.append({"market_a": left, "market_b": right, "match": match})
    return sorted(pairs, key=lambda item: item["match"]["equivalence_score"], reverse=True)


def _classification(net_margin_pct: float, size: float, match: dict[str, Any], fees_pct: float, slippage_pct: float) -> str:
    min_margin = float(getattr(settings, "arbitrage_min_net_margin_pct", 1.0))
    min_confidence = float(getattr(settings, "arbitrage_min_confidence", 0.72))
    min_liquidity = float(getattr(settings, "arbitrage_min_liquidity", 10.0))
    max_resolution_risk = float(getattr(settings, "arbitrage_max_resolution_mismatch_risk", 0.35))
    if match["resolution_mismatch_risk"] > max_resolution_risk or "resolution_rule_mismatch" in match["mismatch_flags"]:
        return "resolution_mismatch_risk"
    if match["equivalence_score"] < 0.50 or "conditional_or_scope_mismatch" in match["mismatch_flags"]:
        return "semantic_mismatch_risk"
    if net_margin_pct <= 0:
        return "reject"
    if match["equivalence_score"] < min_confidence:
        return "watchlist_only"
    if size < min_liquidity:
        return "liquidity_limited_candidate"
    if net_margin_pct < min_margin:
        return "watchlist_only"
    if fees_pct + slippage_pct >= max(net_margin_pct * 0.5, 0.01):
        return "fee_sensitive_candidate"
    return "clean_arbitrage_candidate"


def calculate_arbitrage_for_pair(market_a: VenueMarket, market_b: VenueMarket, match: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    match = match or score_market_equivalence(market_a, market_b)
    directions = [
        ("buy_yes_a_buy_no_b", "YES", market_a, "NO", market_b),
        ("buy_no_a_buy_yes_b", "NO", market_a, "YES", market_b),
    ]
    opportunities: list[dict[str, Any]] = []
    for label, side_a, leg_a, side_b, leg_b in directions:
        ask_a = _ask(leg_a, side_a)
        ask_b = _ask(leg_b, side_b)
        if ask_a is None or ask_b is None:
            continue
        combined_cost = ask_a + ask_b
        gross_margin_pct = (1.0 - combined_cost) * 100.0
        fee_pct = combined_cost * ((leg_a.fees_bps + leg_b.fees_bps) / 100.0)
        slippage_pct = combined_cost * (float(getattr(settings, "arbitrage_default_slippage_bps", 50.0)) / 100.0)
        net_margin_pct = gross_margin_pct - fee_pct - slippage_pct
        size = min(_side_size(leg_a, side_a), _side_size(leg_b, side_b))
        liquidity_factor = min(1.0, size / max(float(getattr(settings, "arbitrage_min_liquidity", 10.0)), 1.0))
        confidence_adjusted_score = max(0.0, net_margin_pct) * match["equivalence_score"] * liquidity_factor
        classification = _classification(net_margin_pct, size, match, fee_pct, slippage_pct)
        opportunity_id = "arb_" + _hash([leg_a.venue_market_id, leg_b.venue_market_id, label, round(net_margin_pct, 4)])
        opportunities.append(
            safety_flags(
                {
                    "version": APP_VERSION,
                    "opportunity_id": opportunity_id,
                    "venue_pair": f"{leg_a.venue}/{leg_b.venue}",
                    "direction": label,
                    "legs": [
                        {"venue": leg_a.venue, "venue_market_id": leg_a.venue_market_id, "side": side_a, "ask": ask_a, "market_url": leg_a.market_url},
                        {"venue": leg_b.venue, "venue_market_id": leg_b.venue_market_id, "side": side_b, "ask": ask_b, "market_url": leg_b.market_url},
                    ],
                    "market_a": leg_a.to_dict(),
                    "market_b": leg_b.to_dict(),
                    "equivalence": match,
                    "combined_cost": round(combined_cost, 4),
                    "gross_arbitrage_margin_pct": round(gross_margin_pct, 3),
                    "estimated_fees_pct": round(fee_pct, 3),
                    "estimated_slippage_pct": round(slippage_pct, 3),
                    "net_arbitrage_margin_pct": round(net_margin_pct, 3),
                    "top_of_book_available_size": round(size, 4),
                    "depth_adjusted_executable_size": round(size * max(0.0, min(match["equivalence_score"], 1.0)), 4),
                    "expected_annualized_return_pct": _annualized_return(net_margin_pct, combined_cost, leg_a.close_time or leg_b.close_time),
                    "max_suggested_stake": round(size * combined_cost, 2),
                    "worst_case_loss_if_not_equivalent": round(size * combined_cost, 2),
                    "confidence_adjusted_opportunity_score": round(confidence_adjusted_score, 3),
                    "classification": classification,
                    "recommended_action": "operator_review_required" if classification != "reject" else "reject",
                    "requires_manual_approval": True,
                    "review_only": True,
                    "not_guaranteed_profit": True,
                    "order_submitted": False,
                    "order_cancelled": False,
                    "trade_approved": False,
                    "live_trading_armed": False,
                    "no_live_mutation": True,
                }
            )
        )
    return sorted(opportunities, key=lambda row: row["confidence_adjusted_opportunity_score"], reverse=True)


def arbitrage_settings_summary() -> dict[str, Any]:
    return safety_flags(
        {
            "version": APP_VERSION,
            "arbitrage_scanner_enabled": bool(getattr(settings, "arbitrage_scanner_enabled", False)),
            "arbitrage_review_only": bool(getattr(settings, "arbitrage_review_only", True)),
            "arbitrage_fetch_orderbooks": bool(getattr(settings, "arbitrage_fetch_orderbooks", False)),
            "arbitrage_min_net_margin_pct": float(getattr(settings, "arbitrage_min_net_margin_pct", 1.0)),
            "arbitrage_min_confidence": float(getattr(settings, "arbitrage_min_confidence", 0.72)),
            "arbitrage_max_stale_seconds": int(getattr(settings, "arbitrage_max_stale_seconds", 300)),
            "arbitrage_max_resolution_mismatch_risk": float(getattr(settings, "arbitrage_max_resolution_mismatch_risk", 0.35)),
            "arbitrage_scan_interval_seconds": int(getattr(settings, "arbitrage_scan_interval_seconds", 300)),
            "arbitrage_default_slippage_bps": float(getattr(settings, "arbitrage_default_slippage_bps", 50.0)),
            "arbitrage_min_liquidity": float(getattr(settings, "arbitrage_min_liquidity", 10.0)),
            "kalshi_enabled": bool(getattr(settings, "kalshi_enabled", False)),
            "kalshi_api_base_url": getattr(settings, "kalshi_api_base_url", ""),
            "kalshi_api_key_configured": bool(getattr(settings, "kalshi_api_key_id", None)),
            "kalshi_private_key_path_configured": bool(getattr(settings, "kalshi_private_key_path", "")),
            "kalshi_secret_values_returned": False,
            "competitor_venues": list(getattr(settings, "arbitrage_competitor_venues", [])),
            "review_only_note": REVIEW_ONLY_NOTE,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "live_trading_armed": False,
        }
    )


async def scan_cross_market_arbitrage(
    *,
    limit_per_venue: int = 25,
    min_net_margin_pct: float | None = None,
    min_confidence: float | None = None,
    demo: bool = False,
    write: bool = False,
    source_route: str = "/api/v3/arbitrage/scan",
    operator: str = "",
    reason: str = "",
) -> dict[str, Any]:
    registry = build_adapter_registry()
    scanner_enabled = bool(getattr(settings, "arbitrage_scanner_enabled", False))
    effective_demo = demo or not scanner_enabled
    markets, statuses = await registry.fetch_all(limit_per_venue=limit_per_venue, demo=effective_demo)
    venue_statuses = [_venue_status_detail(status, demo_requested=effective_demo) for status in statuses]
    readiness = _scan_readiness(statuses=venue_statuses, markets=markets, demo_requested=effective_demo, scanner_enabled=scanner_enabled)
    pairs = generate_candidate_pairs(markets)
    opportunities: list[dict[str, Any]] = []
    for pair in pairs:
        opportunities.extend(calculate_arbitrage_for_pair(pair["market_a"], pair["market_b"], pair["match"]))
    effective_min_margin = float(min_net_margin_pct if min_net_margin_pct is not None else getattr(settings, "arbitrage_min_net_margin_pct", 1.0))
    effective_min_confidence = float(min_confidence if min_confidence is not None else getattr(settings, "arbitrage_min_confidence", 0.72))
    filtered = [
        item
        for item in opportunities
        if item["net_arbitrage_margin_pct"] >= effective_min_margin or item["classification"] in {"resolution_mismatch_risk", "semantic_mismatch_risk", "fee_sensitive_candidate", "liquidity_limited_candidate"}
    ]
    filtered.sort(key=lambda row: (row["classification"] == "clean_arbitrage_candidate", row["confidence_adjusted_opportunity_score"]), reverse=True)
    scan_id = _record_id("arb_scan")
    payload = safety_flags(
        {
            "version": APP_VERSION,
            "scan_id": scan_id,
            "created_at": _now(),
            "mode": "demo_fixture" if effective_demo else "configured_live_read_only",
            "scanner_status": readiness["status"],
            "scanner_status_reason": readiness["scanner_status_reason"],
            "data_state": readiness["data_state"],
            "data_state_reason": readiness["data_state_reason"],
            "data_state_values": DATA_STATE_VALUES,
            "sample_data": readiness["data_state"] == "sample",
            "persisted": bool(write),
            "scanner_readiness": readiness,
            "settings": arbitrage_settings_summary(),
            "venue_statuses": venue_statuses,
            "configured_venues": [status["venue"] for status in venue_statuses],
            "market_snapshot_count": len(markets),
            "candidate_pair_count": len(pairs),
            "opportunity_count": len(filtered),
            "items": filtered,
            "all_opportunity_count": len(opportunities),
            "filters": {"min_net_margin_pct": effective_min_margin, "min_confidence": effective_min_confidence},
            "review_only": True,
            "not_guaranteed_profit": True,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "live_trading_armed": False,
            "no_live_mutation": True,
        }
    )
    if write:
        _write_jsonl(ARBITRAGE_SCANS_PATH, payload)
        _write_jsonl(
            ARBITRAGE_AUDIT_PATH,
            {
                "audit_id": _record_id("arb_audit"),
                "timestamp": payload["created_at"],
                "created_at": payload["created_at"],
                "feature_area": "cross_market_arbitrage",
                "action": "arbitrage_scan_recorded",
                "action_type": "scan_snapshot_recorded",
                "target_id": scan_id,
                "target_name": "Cross-market arbitrage scan snapshot",
                "previous_state": "unpersisted_scan_preview",
                "new_state": "persisted_scan_snapshot",
                "reason": redact_text(reason or "Operator requested a local scan snapshot record."),
                "source_route": source_route,
                "source_component": "cross_market_arbitrage.scan",
                "scan_id": scan_id,
                "venue_snapshot_count": len(markets),
                "matched_pair_count": len(pairs),
                "opportunity_count": len(filtered),
                "scanner_status": payload["scanner_status"],
                "data_state": payload["data_state"],
                "data_freshness": payload["data_state"],
                "sample_data": payload["sample_data"],
                "operator": redact_text(operator) if operator else "",
                "review_only": True,
                "safe_review_only": True,
                "live_disabled": True,
                "order_submitted": False,
                "order_cancelled": False,
                "trade_approved": False,
                "live_trading_armed": False,
            },
        )
    return payload


def record_operator_action(opportunity_id: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    safe_action = str(action or "review_requested").strip().lower().replace(" ", "_")
    if safe_action not in {"review_requested", "rejected", "ignored", "watchlist"}:
        safe_action = "review_requested"
    row = safety_flags(
        {
            "audit_id": _record_id("arb_action"),
            "timestamp": _now(),
            "feature_area": "cross_market_arbitrage",
            "action": safe_action,
            "action_type": "candidate_review_decision",
            "opportunity_id": redact_text(opportunity_id),
            "target_id": redact_text(opportunity_id),
            "target_name": redact_text((payload or {}).get("target_name") or (payload or {}).get("market_title") or opportunity_id),
            "previous_state": redact_text((payload or {}).get("previous_state") or "candidate_visible_in_scan"),
            "new_state": safe_action,
            "reason": redact_text((payload or {}).get("reason") or (payload or {}).get("operator_note") or f"Operator marked candidate as {safe_action}.")[:1000],
            "operator_note": redact_text((payload or {}).get("operator_note") or (payload or {}).get("note") or "")[:1000],
            "created_at": _now(),
            "decision_status": safe_action,
            "source_route": redact_text((payload or {}).get("source_route") or "/v3/arbitrage"),
            "source_component": redact_text((payload or {}).get("source_component") or "cross_market_arbitrage.review_form"),
            "scan_id": redact_text((payload or {}).get("scan_id") or ""),
            "operator": redact_text((payload or {}).get("operator") or ""),
            "data_state": redact_text((payload or {}).get("data_state") or "unavailable"),
            "data_freshness": redact_text((payload or {}).get("data_freshness") or (payload or {}).get("data_state") or "unavailable"),
            "requires_manual_approval": True,
            "review_only": True,
            "safe_review_only": True,
            "live_disabled": True,
            "not_guaranteed_profit": True,
            "order_submitted": False,
            "order_cancelled": False,
            "trade_approved": False,
            "live_trading_armed": False,
            "no_live_mutation": True,
        }
    )
    _write_jsonl(ARBITRAGE_AUDIT_PATH, row)
    return {"ok": True, "item": row, "review_only": True, "order_submitted": False, "order_cancelled": False, "live_trading_armed": False}
