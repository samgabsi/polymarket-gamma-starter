from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import APP_VERSION, DATA_DIR
from .live_v2 import record_audit
from .platform_safety import redact_data, safety_flags

PAPER_AUTOMATION_DIR = DATA_DIR / "paper_automation"
PAPER_ACCOUNT_PATH = PAPER_AUTOMATION_DIR / "account.json"
PAPER_ORDERS_PATH = PAPER_AUTOMATION_DIR / "orders.jsonl"
PAPER_FILLS_PATH = PAPER_AUTOMATION_DIR / "fills.jsonl"
PAPER_POSITIONS_PATH = PAPER_AUTOMATION_DIR / "positions.json"
PAPER_DECISIONS_PATH = PAPER_AUTOMATION_DIR / "decisions.jsonl"
PAPER_RUNS_PATH = PAPER_AUTOMATION_DIR / "runs.jsonl"
PAPER_AUDIT_PATH = PAPER_AUTOMATION_DIR / "audit.jsonl"


TRUE_VALUES = {"1", "true", "yes", "on"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(key: str, default: str = "false") -> bool:
    return str(os.getenv(key, default)).strip().lower() in TRUE_VALUES


def _env_float(key: str, default: float) -> float:
    try:
        value = float(str(os.getenv(key, str(default))).strip())
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        value = int(float(str(os.getenv(key, str(default))).strip()))
        return value
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _ensure_dir() -> None:
    PAPER_AUTOMATION_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact_data(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")


def _append_jsonl(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = redact_data(row)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(clean, sort_keys=True, default=str) + "\n")
    return clean


def _read_jsonl(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            row = {"timestamp": "", "status": "unreadable", "reason": "Unreadable paper automation JSONL row."}
        if isinstance(row, dict):
            rows.append(redact_data(row))
        if len(rows) >= max(1, min(int(limit or 100), 2000)):
            break
    return rows


@dataclass(frozen=True)
class PaperTradingConfig:
    enabled: bool
    automation_enabled: bool
    require_operator_start: bool
    starting_balance: float
    max_order_notional: float
    max_market_notional: float
    max_daily_notional: float
    max_open_positions: int
    max_trades_per_run: int
    max_trades_per_day: int
    min_edge_pct: float
    min_confidence: float
    max_spread_bps: float
    max_slippage_bps: float
    require_fresh_data: bool
    max_data_age_seconds: int
    allow_ai_signals: bool
    allow_arbitrage_signals: bool
    allow_manual_watchlist_signals: bool
    fill_model: str
    fees_bps: float
    scheduler_enabled: bool
    scheduler_interval_seconds: int
    log_decisions: bool
    audit_required: bool
    allow_sample_candidates: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(
            {
                "paper_only": True,
                "live_execution_used": False,
                "can_place_real_orders": False,
                "can_cancel_real_orders": False,
                "live_trading_enabled_by_paper_config": False,
                "secret_values_returned": False,
                "app_version": APP_VERSION,
            }
        )
        return redact_data(data)


def get_paper_config() -> PaperTradingConfig:
    fill_model = _safe_text(os.getenv("PAPER_TRADING_FILL_MODEL", "conservative"), "conservative").lower()
    if fill_model not in {"top_of_book", "midpoint", "conservative", "adverse"}:
        fill_model = "conservative"
    return PaperTradingConfig(
        enabled=_env_bool("PAPER_TRADING_ENABLED", "false"),
        automation_enabled=_env_bool("PAPER_TRADING_AUTOMATION_ENABLED", "false"),
        require_operator_start=_env_bool("PAPER_TRADING_REQUIRE_OPERATOR_START", "true"),
        starting_balance=max(0.0, _env_float("PAPER_TRADING_STARTING_BALANCE", 1000.0)),
        max_order_notional=max(0.0, _env_float("PAPER_TRADING_MAX_ORDER_NOTIONAL", 25.0)),
        max_market_notional=max(0.0, _env_float("PAPER_TRADING_MAX_MARKET_NOTIONAL", 100.0)),
        max_daily_notional=max(0.0, _env_float("PAPER_TRADING_MAX_DAILY_NOTIONAL", 250.0)),
        max_open_positions=max(0, _env_int("PAPER_TRADING_MAX_OPEN_POSITIONS", 10)),
        max_trades_per_run=max(0, _env_int("PAPER_TRADING_MAX_TRADES_PER_RUN", 3)),
        max_trades_per_day=max(0, _env_int("PAPER_TRADING_MAX_TRADES_PER_DAY", 20)),
        min_edge_pct=max(0.0, _env_float("PAPER_TRADING_MIN_EDGE_PCT", 2.0)),
        min_confidence=min(max(0.0, _env_float("PAPER_TRADING_MIN_CONFIDENCE", 0.70)), 1.0),
        max_spread_bps=max(0.0, _env_float("PAPER_TRADING_MAX_SPREAD_BPS", 250.0)),
        max_slippage_bps=max(0.0, _env_float("PAPER_TRADING_MAX_SLIPPAGE_BPS", 150.0)),
        require_fresh_data=_env_bool("PAPER_TRADING_REQUIRE_FRESH_DATA", "true"),
        max_data_age_seconds=max(1, _env_int("PAPER_TRADING_MAX_DATA_AGE_SECONDS", 300)),
        allow_ai_signals=_env_bool("PAPER_TRADING_ALLOW_AI_SIGNALS", "true"),
        allow_arbitrage_signals=_env_bool("PAPER_TRADING_ALLOW_ARBITRAGE_SIGNALS", "true"),
        allow_manual_watchlist_signals=_env_bool("PAPER_TRADING_ALLOW_MANUAL_WATCHLIST_SIGNALS", "true"),
        fill_model=fill_model,
        fees_bps=max(0.0, _env_float("PAPER_TRADING_FEES_BPS", 0.0)),
        scheduler_enabled=_env_bool("PAPER_TRADING_SCHEDULER_ENABLED", "false"),
        scheduler_interval_seconds=max(30, _env_int("PAPER_TRADING_SCHEDULER_INTERVAL_SECONDS", 300)),
        log_decisions=_env_bool("PAPER_TRADING_LOG_DECISIONS", "true"),
        audit_required=_env_bool("PAPER_TRADING_AUDIT_REQUIRED", "true"),
        allow_sample_candidates=_env_bool("PAPER_TRADING_ALLOW_SAMPLE_CANDIDATES", "true"),
    )


def _initial_account(config: PaperTradingConfig | None = None) -> dict[str, Any]:
    cfg = config or get_paper_config()
    return {
        "app_version": APP_VERSION,
        "created_at": _now(),
        "updated_at": _now(),
        "starting_balance": round(cfg.starting_balance, 4),
        "available_cash": round(cfg.starting_balance, 4),
        "reserved_cash": 0.0,
        "total_exposure": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "equity": round(cfg.starting_balance, 4),
        "max_drawdown": 0.0,
        "daily_paper_trades": 0,
        "daily_paper_notional": 0.0,
        "last_reset_at": _now(),
        "paper_only": True,
        "live_execution_used": False,
        "can_place_real_orders": False,
        "can_cancel_real_orders": False,
        "secret_values_returned": False,
    }


def load_paper_account() -> dict[str, Any]:
    account = _read_json(PAPER_ACCOUNT_PATH, {})
    if not isinstance(account, dict) or not account:
        account = _initial_account()
        _write_json(PAPER_ACCOUNT_PATH, account)
    account.setdefault("paper_only", True)
    account.setdefault("live_execution_used", False)
    account.setdefault("can_place_real_orders", False)
    account.setdefault("can_cancel_real_orders", False)
    account.setdefault("secret_values_returned", False)
    return redact_data(account)


def save_paper_account(account: dict[str, Any]) -> dict[str, Any]:
    account = dict(account)
    account.update({"updated_at": _now(), "paper_only": True, "live_execution_used": False, "can_place_real_orders": False, "can_cancel_real_orders": False, "secret_values_returned": False})
    _write_json(PAPER_ACCOUNT_PATH, account)
    return redact_data(account)


def load_positions() -> dict[str, dict[str, Any]]:
    rows = _read_json(PAPER_POSITIONS_PATH, {})
    return rows if isinstance(rows, dict) else {}


def save_positions(rows: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    _write_json(PAPER_POSITIONS_PATH, rows)
    return redact_data(rows)


def list_paper_orders(limit: int = 100) -> dict[str, Any]:
    return _envelope("paper_orders", _read_jsonl(PAPER_ORDERS_PATH, limit=limit))


def list_paper_fills(limit: int = 100) -> dict[str, Any]:
    return _envelope("paper_fills", _read_jsonl(PAPER_FILLS_PATH, limit=limit))


def list_paper_decisions(limit: int = 100) -> dict[str, Any]:
    return _envelope("paper_decisions", _read_jsonl(PAPER_DECISIONS_PATH, limit=limit))


def list_paper_runs(limit: int = 50) -> dict[str, Any]:
    return _envelope("paper_runs", _read_jsonl(PAPER_RUNS_PATH, limit=limit))


def list_paper_audit(limit: int = 100) -> dict[str, Any]:
    return _envelope("paper_audit", _read_jsonl(PAPER_AUDIT_PATH, limit=limit))


def list_paper_positions(limit: int = 100) -> dict[str, Any]:
    positions = list(load_positions().values())
    positions.sort(key=lambda row: str(row.get("last_updated") or row.get("updated_at") or ""), reverse=True)
    return _envelope("paper_positions", positions[: max(1, min(int(limit or 100), 2000))])


def _envelope(kind: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return redact_data(
        {
            "app_version": APP_VERSION,
            "kind": kind,
            "items": items,
            "count": len(items),
            "paper_only": True,
            "live_execution_used": False,
            "can_place_real_orders": False,
            "can_cancel_real_orders": False,
            "secret_values_returned": False,
            **safety_flags({"paper_trading_surface": True}),
        }
    )


def _audit(action: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {
        "audit_id": f"paper_audit_{uuid4().hex[:12]}",
        "timestamp": _now(),
        "app_version": APP_VERSION,
        "feature_area": "paper_trading",
        "action_type": action,
        "status": status,
        "details": details or {},
        "paper_only": True,
        "live_execution_used": False,
        "real_order_submitted": False,
        "real_order_cancelled": False,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "can_place_real_orders": False,
        "can_cancel_real_orders": False,
        "secret_values_returned": False,
    }
    saved = _append_jsonl(PAPER_AUDIT_PATH, row)
    try:
        record_audit(
            f"paper_trading_{action}",
            status,
            details={**(details or {}), "paper_only": True, "live_execution_used": False, "real_order_submitted": False, "real_order_cancelled": False},
            network_attempted=False,
        )
    except Exception:
        pass
    return saved


def reset_paper_account(starting_balance: float | None = None, *, reason: str = "operator reset") -> dict[str, Any]:
    cfg = get_paper_config()
    if starting_balance is not None and starting_balance > 0:
        cfg = replace(cfg, starting_balance=float(starting_balance))
    _ensure_dir()
    account = _initial_account(cfg)
    save_paper_account(account)
    save_positions({})
    # Keep historical JSONL rows for audit, but record the reset boundary.
    _audit("reset_performed", "ok", {"reason": reason, "starting_balance": account["starting_balance"]})
    return build_paper_status()


def _position_key(market_id: str, side: str) -> str:
    return f"{market_id}:{side.upper()}"


def _today_prefix() -> str:
    return _now()[:10]


def _today_orders() -> list[dict[str, Any]]:
    prefix = _today_prefix()
    return [row for row in _read_jsonl(PAPER_ORDERS_PATH, limit=5000) if str(row.get("timestamp", "")).startswith(prefix) and row.get("status") == "simulated_filled"]


def _derive_price(candidate: dict[str, Any], side: str, fill_model: str) -> float:
    side = side.upper()
    if side == "NO":
        no_ask = _safe_float(candidate.get("no_ask_price"), 0.0)
        if no_ask > 0:
            return no_ask
        yes_bid = _safe_float(candidate.get("yes_bid_price"), 0.0)
        if yes_bid > 0:
            return 1.0 - yes_bid
    ask = _safe_float(candidate.get("ask_price"), 0.0)
    bid = _safe_float(candidate.get("bid_price"), 0.0)
    midpoint = _safe_float(candidate.get("midpoint"), 0.0)
    raw = _safe_float(candidate.get("price"), 0.0)
    if fill_model in {"top_of_book", "conservative", "adverse"} and ask > 0:
        return ask
    if fill_model == "midpoint" and midpoint > 0:
        return midpoint
    if bid > 0 and ask > 0:
        return (bid + ask) / 2 if fill_model == "midpoint" else ask
    return raw or midpoint or 0.5


def _candidate_sample() -> list[dict[str, Any]]:
    return [
        {
            "signal_id": "sample-ai-edge-v416",
            "candidate_source": "sample_ai_edge_fixture",
            "strategy_name": "deterministic_edge_threshold",
            "market_id": "paper-sample-market-001",
            "market_title": "SAMPLE paper-only market for automation smoke testing",
            "side": "YES",
            "action": "buy",
            "price": 0.42,
            "ask_price": 0.43,
            "bid_price": 0.41,
            "size": 10.0,
            "notional": 10.0,
            "model_probability": 0.49,
            "market_probability": 0.43,
            "ai_adjusted_probability": 0.50,
            "edge_pct": 6.0,
            "confidence": 0.82,
            "spread_bps": 200,
            "slippage_bps": 50,
            "data_age_seconds": 0,
            "data_state": "sample",
            "data_freshness": "sample_fixture_paper_only",
            "evidence_quality": "sample_fixture",
            "resolution_mismatch_risk": 0.0,
            "semantic_mismatch_risk": 0.0,
            "reason": "Paper-only sample candidate used when no live/local candidate feed is supplied.",
        }
    ]


def _normalize_candidates(candidates: Any, config: PaperTradingConfig) -> list[dict[str, Any]]:
    if isinstance(candidates, dict):
        raw = candidates.get("candidates") or candidates.get("items") or []
    else:
        raw = candidates
    rows = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    if not rows and config.allow_sample_candidates:
        rows = _candidate_sample()
    normalized: list[dict[str, Any]] = []
    for row in rows:
        side = _safe_text(row.get("side") or row.get("outcome") or row.get("recommended_side"), "YES").upper()
        if side not in {"YES", "NO"}:
            side = "YES"
        source = _safe_text(row.get("candidate_source") or row.get("source") or row.get("signal_source"), "manual")
        normalized.append(
            redact_data(
                {
                    **row,
                    "signal_id": _safe_text(row.get("signal_id") or row.get("id"), f"signal_{uuid4().hex[:10]}"),
                    "candidate_source": source,
                    "strategy_name": _safe_text(row.get("strategy_name"), "deterministic_edge_threshold"),
                    "market_id": _safe_text(row.get("market_id") or row.get("id"), "unknown-market"),
                    "market_title": _safe_text(row.get("market_title") or row.get("question") or row.get("title"), "Untitled paper candidate"),
                    "side": side,
                    "action": _safe_text(row.get("action") or row.get("intended_action"), "buy").lower(),
                    "edge_pct": _safe_float(row.get("edge_pct") if row.get("edge_pct") is not None else row.get("edge"), 0.0),
                    "confidence": min(max(_safe_float(row.get("confidence"), 0.0), 0.0), 1.0),
                    "spread_bps": max(0.0, _safe_float(row.get("spread_bps"), 0.0)),
                    "slippage_bps": max(0.0, _safe_float(row.get("slippage_bps"), config.max_slippage_bps)),
                    "data_age_seconds": max(0, _safe_int(row.get("data_age_seconds"), 0)),
                    "data_state": _safe_text(row.get("data_state"), "unknown").lower(),
                    "resolution_mismatch_risk": min(max(_safe_float(row.get("resolution_mismatch_risk"), 0.0), 0.0), 1.0),
                    "semantic_mismatch_risk": min(max(_safe_float(row.get("semantic_mismatch_risk"), 0.0), 0.0), 1.0),
                    "paper_only": True,
                    "live_execution_used": False,
                }
            )
        )
    return normalized


def _market_exposure(positions: dict[str, dict[str, Any]], market_id: str) -> float:
    exposure = 0.0
    for row in positions.values():
        if str(row.get("market_id")) == str(market_id):
            exposure += _safe_float(row.get("cost_basis"), 0.0)
    return exposure


def _risk_checks(candidate: dict[str, Any], config: PaperTradingConfig, account: dict[str, Any], positions: dict[str, dict[str, Any]], accepted_this_run: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    source = _safe_text(candidate.get("candidate_source"), "manual").lower()
    if "ai" in source and not config.allow_ai_signals:
        reasons.append("AI signals are disabled by PAPER_TRADING_ALLOW_AI_SIGNALS=false.")
    if "arbitrage" in source and not config.allow_arbitrage_signals:
        reasons.append("Arbitrage signals are disabled by PAPER_TRADING_ALLOW_ARBITRAGE_SIGNALS=false.")
    if "watchlist" in source and not config.allow_manual_watchlist_signals:
        reasons.append("Manual watchlist signals are disabled by PAPER_TRADING_ALLOW_MANUAL_WATCHLIST_SIGNALS=false.")
    if _safe_float(candidate.get("edge_pct"), 0.0) < config.min_edge_pct:
        reasons.append(f"Edge {_safe_float(candidate.get('edge_pct'), 0.0):.2f}% is below minimum {config.min_edge_pct:.2f}%.")
    if _safe_float(candidate.get("confidence"), 0.0) < config.min_confidence:
        reasons.append(f"Confidence {_safe_float(candidate.get('confidence'), 0.0):.2f} is below minimum {config.min_confidence:.2f}.")
    if config.require_fresh_data:
        data_state = _safe_text(candidate.get("data_state"), "unknown").lower()
        if data_state in {"stale", "unavailable", "error"}:
            reasons.append(f"Data state {data_state} is not fresh enough for automated paper trading.")
        if _safe_int(candidate.get("data_age_seconds"), 0) > config.max_data_age_seconds:
            reasons.append(f"Data age {_safe_int(candidate.get('data_age_seconds'), 0)}s exceeds {config.max_data_age_seconds}s.")
    if _safe_float(candidate.get("spread_bps"), 0.0) > config.max_spread_bps:
        reasons.append(f"Spread {_safe_float(candidate.get('spread_bps'), 0.0):.1f} bps exceeds max {config.max_spread_bps:.1f} bps.")
    if _safe_float(candidate.get("slippage_bps"), 0.0) > config.max_slippage_bps:
        reasons.append(f"Slippage {_safe_float(candidate.get('slippage_bps'), 0.0):.1f} bps exceeds max {config.max_slippage_bps:.1f} bps.")
    if _safe_float(candidate.get("resolution_mismatch_risk"), 0.0) >= 0.50:
        reasons.append("Resolution mismatch risk is too high for automation.")
    if _safe_float(candidate.get("semantic_mismatch_risk"), 0.0) >= 0.50:
        reasons.append("Semantic mismatch risk is too high for automation.")
    if _safe_text(candidate.get("evidence_quality"), "").lower() in {"weak", "stale", "contradictory"}:
        reasons.append("AI evidence quality is weak/stale/contradictory.")
    notional = _safe_float(candidate.get("notional"), config.max_order_notional)
    if notional <= 0:
        reasons.append("Order notional must be positive.")
    if config.max_order_notional <= 0 or notional > config.max_order_notional:
        reasons.append(f"Notional {notional:.2f} exceeds per-order max {config.max_order_notional:.2f}.")
    if notional > _safe_float(account.get("available_cash"), 0.0):
        reasons.append("Paper account has insufficient available cash.")
    if config.max_trades_per_run <= 0 or accepted_this_run >= config.max_trades_per_run:
        reasons.append("Per-run paper trade limit reached.")
    today = _today_orders()
    if len(today) >= config.max_trades_per_day:
        reasons.append("Daily paper trade count limit reached.")
    today_notional = sum(_safe_float(row.get("notional"), 0.0) for row in today)
    if today_notional + notional > config.max_daily_notional:
        reasons.append("Daily paper notional limit reached.")
    if len(positions) >= config.max_open_positions and _position_key(_safe_text(candidate.get("market_id")), _safe_text(candidate.get("side"), "YES")) not in positions:
        reasons.append("Max open paper positions reached.")
    if _market_exposure(positions, _safe_text(candidate.get("market_id"))) + notional > config.max_market_notional:
        reasons.append("Market paper exposure limit reached.")
    return (not reasons), reasons


def _decision_row(run_id: str, candidate: dict[str, Any], final_action: str, reason: str, risk_checks: list[str], order_id: str = "") -> dict[str, Any]:
    row = {
        "decision_id": f"paper_decision_{uuid4().hex[:12]}",
        "run_id": run_id,
        "timestamp": _now(),
        "candidate_source": candidate.get("candidate_source"),
        "strategy_name": candidate.get("strategy_name"),
        "signal_id": candidate.get("signal_id"),
        "market_id": candidate.get("market_id"),
        "market_title": candidate.get("market_title"),
        "side": candidate.get("side"),
        "signal_score": candidate.get("signal_score", candidate.get("confidence")),
        "model_probability": candidate.get("model_probability"),
        "market_probability": candidate.get("market_probability"),
        "ai_adjusted_probability": candidate.get("ai_adjusted_probability"),
        "edge_pct": candidate.get("edge_pct"),
        "confidence": candidate.get("confidence"),
        "reason": reason,
        "risk_checks_passed": not risk_checks,
        "risk_checks_failed": risk_checks,
        "final_action": final_action,
        "order_id": order_id,
        "data_state": candidate.get("data_state"),
        "data_freshness": candidate.get("data_freshness"),
        "paper_only": True,
        "live_execution_used": False,
        "real_order_submitted": False,
        "real_order_cancelled": False,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
    }
    _append_jsonl(PAPER_DECISIONS_PATH, row)
    _audit("candidate_considered", final_action, {"decision_id": row["decision_id"], "market_id": row["market_id"], "reason": reason, "risk_checks_failed": risk_checks, "paper_only": True})
    return redact_data(row)


def _simulate_fill(run_id: str, candidate: dict[str, Any], config: PaperTradingConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    account = load_paper_account()
    positions = load_positions()
    side = _safe_text(candidate.get("side"), "YES").upper()
    notional = min(_safe_float(candidate.get("notional"), config.max_order_notional), config.max_order_notional)
    base_price = _derive_price(candidate, side, config.fill_model)
    slippage_bps = min(_safe_float(candidate.get("slippage_bps"), config.max_slippage_bps), config.max_slippage_bps)
    fill_price = min(max(base_price * (1.0 + (slippage_bps / 10000.0)), 0.0001), 0.9999)
    fee = notional * (config.fees_bps / 10000.0)
    quantity = notional / fill_price if fill_price else 0.0
    order_id = f"paper_order_{uuid4().hex[:12]}"
    fill_id = f"paper_fill_{uuid4().hex[:12]}"
    timestamp = _now()
    order = {
        "id": order_id,
        "order_id": order_id,
        "run_id": run_id,
        "timestamp": timestamp,
        "market_id": candidate.get("market_id"),
        "market_title": candidate.get("market_title"),
        "outcome": side,
        "side": side,
        "intended_action": "buy",
        "price": round(base_price, 4),
        "size": round(quantity, 8),
        "notional": round(notional, 4),
        "source_signal_id": candidate.get("signal_id"),
        "strategy_name": candidate.get("strategy_name"),
        "status": "simulated_filled",
        "rejection_reason": "",
        "simulated_fill_price": round(fill_price, 4),
        "simulated_slippage_bps": round(slippage_bps, 4),
        "simulated_fees": round(fee, 4),
        "data_freshness_state": candidate.get("data_state"),
        "data_freshness": candidate.get("data_freshness"),
        "paper_only": True,
        "live_execution_used": False,
        "real_order_submitted": False,
        "real_order_cancelled": False,
        "can_place_real_orders": False,
        "can_cancel_real_orders": False,
        "secret_values_returned": False,
    }
    fill = {
        "id": fill_id,
        "fill_id": fill_id,
        "order_id": order_id,
        "run_id": run_id,
        "timestamp": timestamp,
        "market_id": candidate.get("market_id"),
        "side": side,
        "price": round(fill_price, 4),
        "size": round(quantity, 8),
        "notional": round(notional, 4),
        "fee": round(fee, 4),
        "slippage_bps": round(slippage_bps, 4),
        "fill_model_used": config.fill_model,
        "paper_only": True,
        "live_execution_used": False,
        "real_order_submitted": False,
        "real_order_cancelled": False,
        "secret_values_returned": False,
    }
    cash_before = _safe_float(account.get("available_cash"), config.starting_balance)
    account["available_cash"] = round(cash_before - notional - fee, 4)
    account["daily_paper_trades"] = _safe_int(account.get("daily_paper_trades"), 0) + 1
    account["daily_paper_notional"] = round(_safe_float(account.get("daily_paper_notional"), 0.0) + notional, 4)
    key = _position_key(_safe_text(candidate.get("market_id")), side)
    existing = positions.get(key, {}) if isinstance(positions.get(key), dict) else {}
    old_qty = _safe_float(existing.get("quantity"), 0.0)
    old_cost = _safe_float(existing.get("cost_basis"), 0.0)
    new_qty = old_qty + quantity
    new_cost = old_cost + notional + fee
    current_price = fill_price
    position = {
        "position_id": key,
        "market_id": candidate.get("market_id"),
        "market_title": candidate.get("market_title"),
        "outcome": side,
        "side": side,
        "quantity": round(new_qty, 8),
        "average_price": round(new_cost / new_qty, 4) if new_qty else 0.0,
        "current_estimated_price": round(current_price, 4),
        "cost_basis": round(new_cost, 4),
        "market_value": round(new_qty * current_price, 4),
        "unrealized_pnl": round((new_qty * current_price) - new_cost, 4),
        "realized_pnl": _safe_float(existing.get("realized_pnl"), 0.0),
        "last_updated": timestamp,
        "data_freshness_state": candidate.get("data_state"),
        "data_freshness": candidate.get("data_freshness"),
        "paper_only": True,
        "live_execution_used": False,
        "secret_values_returned": False,
    }
    positions[key] = position
    save_positions(positions)
    total_exposure = sum(_safe_float(row.get("cost_basis"), 0.0) for row in positions.values() if isinstance(row, dict))
    unrealized = sum(_safe_float(row.get("unrealized_pnl"), 0.0) for row in positions.values() if isinstance(row, dict))
    account["total_exposure"] = round(total_exposure, 4)
    account["unrealized_pnl"] = round(unrealized, 4)
    account["equity"] = round(_safe_float(account.get("available_cash"), 0.0) + total_exposure + unrealized, 4)
    account["max_drawdown"] = min(_safe_float(account.get("max_drawdown"), 0.0), round(account["equity"] - _safe_float(account.get("starting_balance"), config.starting_balance), 4))
    save_paper_account(account)
    _append_jsonl(PAPER_ORDERS_PATH, order)
    _append_jsonl(PAPER_FILLS_PATH, fill)
    _audit("paper_order_created", "ok", {"order_id": order_id, "market_id": candidate.get("market_id"), "notional": notional, "paper_only": True})
    _audit("paper_fill_simulated", "ok", {"fill_id": fill_id, "order_id": order_id, "fill_price": fill_price, "live_execution_used": False})
    _audit("position_updated", "ok", {"position_id": key, "quantity": position["quantity"], "unrealized_pnl": position["unrealized_pnl"]})
    return order, fill


def run_paper_strategy_once(candidates: Any = None, *, source_route: str = "/api/v3/paper/run-once", source_component: str = "paper_strategy_runner.api") -> dict[str, Any]:
    config = get_paper_config()
    run_id = f"paper_run_{uuid4().hex[:12]}"
    start = _now()
    base_summary: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": start,
        "app_version": APP_VERSION,
        "automation_enabled": config.automation_enabled,
        "paper_trading_enabled": config.enabled,
        "paper_only": True,
        "live_execution_used": False,
        "can_place_real_orders": False,
        "can_cancel_real_orders": False,
        "real_order_submitted": False,
        "real_order_cancelled": False,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "review_only_live_disabled": True,
        "safety_posture": "automated paper trading only; no real orders or cancellations are possible from this runner",
        "source_route": source_route,
        "source_component": source_component,
        "secret_values_returned": False,
    }
    _audit("run_started", "ok", base_summary)
    if not config.enabled:
        summary = {**base_summary, "ok": False, "status": "disabled", "disabled_reason": "PAPER_TRADING_ENABLED is false.", "candidates_considered": 0, "paper_trades_placed": 0, "skipped_count": 0, "rejected_count": 0, "watchlisted_count": 0, "total_simulated_notional": 0.0, "risk_rejections": ["paper_trading_disabled"], "errors": [], "data_freshness_state": "unavailable"}
        _append_jsonl(PAPER_RUNS_PATH, summary)
        _audit("run_completed", "disabled", summary)
        return redact_data(summary)
    if not config.automation_enabled:
        summary = {**base_summary, "ok": False, "status": "disabled", "disabled_reason": "PAPER_TRADING_AUTOMATION_ENABLED is false.", "candidates_considered": 0, "paper_trades_placed": 0, "skipped_count": 0, "rejected_count": 0, "watchlisted_count": 0, "total_simulated_notional": 0.0, "risk_rejections": ["paper_automation_disabled"], "errors": [], "data_freshness_state": "unavailable"}
        _append_jsonl(PAPER_RUNS_PATH, summary)
        _audit("run_completed", "disabled", summary)
        return redact_data(summary)

    account = load_paper_account()
    positions = load_positions()
    normalized = _normalize_candidates(candidates, config)
    decisions: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    errors: list[str] = []
    accepted_this_run = 0
    rejected_count = 0
    skipped_count = 0
    for candidate in normalized:
        try:
            risk_ok, risk_reasons = _risk_checks(candidate, config, account, positions, accepted_this_run)
            if not risk_ok:
                rejected_count += 1
                decisions.append(_decision_row(run_id, candidate, "reject", "; ".join(risk_reasons), risk_reasons))
                continue
            order, fill = _simulate_fill(run_id, candidate, config)
            account = load_paper_account()
            positions = load_positions()
            accepted_this_run += 1
            orders.append(order)
            fills.append(fill)
            decisions.append(_decision_row(run_id, candidate, "paper_trade", "Risk checks passed and simulated fill was recorded.", [], order_id=order["order_id"]))
        except Exception as exc:
            skipped_count += 1
            msg = f"paper strategy error: {type(exc).__name__}"
            errors.append(msg)
            decisions.append(_decision_row(run_id, candidate, "skip", msg, [msg]))
    data_states = sorted({_safe_text(row.get("data_state"), "unknown") for row in normalized})
    summary = {
        **base_summary,
        "ok": True,
        "status": "completed",
        "completed_at": _now(),
        "candidates_considered": len(normalized),
        "paper_trades_placed": len(orders),
        "skipped_count": skipped_count,
        "rejected_count": rejected_count,
        "watchlisted_count": 0,
        "total_simulated_notional": round(sum(_safe_float(order.get("notional"), 0.0) for order in orders), 4),
        "risk_rejections": [reason for decision in decisions for reason in decision.get("risk_checks_failed", [])],
        "errors": errors,
        "data_freshness_state": ",".join(data_states) if data_states else "unavailable",
        "decisions": decisions,
        "orders": orders,
        "fills": fills,
        "account": load_paper_account(),
        "positions": list(load_positions().values()),
    }
    _append_jsonl(PAPER_RUNS_PATH, summary)
    _audit("run_completed", "ok", {"run_id": run_id, "paper_trades_placed": len(orders), "candidates_considered": len(normalized), "errors": errors})
    return redact_data(summary)


def cancel_paper_order(order_id: str, *, reason: str = "operator cancelled paper order") -> dict[str, Any]:
    # Filled orders remain immutable; this records an explicit paper-only cancellation request for open/proposed orders.
    row = {
        "order_id": _safe_text(order_id),
        "timestamp": _now(),
        "status": "cancelled_paper_request_recorded",
        "reason": reason,
        "paper_only": True,
        "live_execution_used": False,
        "real_order_cancelled": False,
        "order_cancelled": False,
        "secret_values_returned": False,
    }
    _audit("paper_order_cancel_requested", "ok", row)
    return redact_data({"ok": True, **row, **safety_flags({"paper_trading_surface": True})})


def build_paper_status() -> dict[str, Any]:
    config = get_paper_config()
    account = load_paper_account()
    orders = _read_jsonl(PAPER_ORDERS_PATH, limit=500)
    fills = _read_jsonl(PAPER_FILLS_PATH, limit=500)
    decisions = _read_jsonl(PAPER_DECISIONS_PATH, limit=500)
    positions = list(load_positions().values())
    last_run = _read_jsonl(PAPER_RUNS_PATH, limit=1)
    enabled_reason = "Paper trading and automation are enabled." if config.enabled and config.automation_enabled else "Set PAPER_TRADING_ENABLED=true and PAPER_TRADING_AUTOMATION_ENABLED=true to run automated paper cycles."
    status = "working" if config.enabled else "disabled"
    automation_status = "working" if config.enabled and config.automation_enabled else ("disabled" if not config.automation_enabled else "config_required")
    payload = {
        "app_version": APP_VERSION,
        "status": status,
        "automation_status": automation_status,
        "enabled_reason": enabled_reason,
        "config": config.to_dict(),
        "account": account,
        "orders_count": len(orders),
        "fills_count": len(fills),
        "decisions_count": len(decisions),
        "open_position_count": len(positions),
        "positions": positions,
        "recent_orders": orders[:10],
        "recent_fills": fills[:10],
        "recent_decisions": decisions[:20],
        "last_run": last_run[0] if last_run else {},
        "scheduler_status": "enabled" if config.scheduler_enabled else "disabled",
        "paper_broker_status": "working" if config.enabled else "disabled",
        "paper_ledger_status": "working",
        "risk_controls_status": "working",
        "data_state": "cached" if orders or fills or decisions else "unavailable",
        "safety_posture": "Paper trading only. No real orders will be placed, cancelled, signed, or armed by this subsystem.",
        "paper_only": True,
        "live_execution_used": False,
        "can_place_real_orders": False,
        "can_cancel_real_orders": False,
        "real_order_submitted": False,
        "real_order_cancelled": False,
        "order_submitted": False,
        "order_cancelled": False,
        "live_trading_armed": False,
        "secret_values_returned": False,
        **safety_flags({"paper_trading_surface": True}),
    }
    return redact_data(payload)
