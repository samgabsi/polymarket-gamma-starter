from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_VERSION = "2.1.0-real"
APP_VERSION_SHORT = "2.1.0"
APP_DIR = PROJECT_ROOT / "app"
DATA_DIR = PROJECT_ROOT / "data"

load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    gamma_base_url: str = os.getenv("GAMMA_BASE_URL", "https://gamma-api.polymarket.com")
    clob_base_url: str = os.getenv("CLOB_BASE_URL", "https://clob.polymarket.com")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    default_limit: int = int(os.getenv("DEFAULT_LIMIT", "20"))
    snapshot_dir: Path = Path(os.getenv("SNAPSHOT_DIR", str(DATA_DIR / "snapshots")))
    latest_path: Path = Path(os.getenv("LATEST_PATH", str(DATA_DIR / "latest_markets.json")))
    app_mode: str = os.getenv("APP_MODE", "read_only")
    read_only: bool = os.getenv("READ_ONLY", "true").lower() in {"1", "true", "yes", "on"}
    live_trading_enabled: bool = os.getenv("LIVE_TRADING_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

    # Server binding. Use 0.0.0.0 to allow other LAN devices to reach the app.
    host: str = os.getenv("HOST", os.getenv("APP_HOST", "0.0.0.0"))
    port: int = int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))
    reload: bool = os.getenv("APP_RELOAD", "true").lower() in {"1", "true", "yes", "on"}

    # LAN/security controls. ALLOWED_HOSTS="*" is convenient for LAN testing.
    # For a fixed LAN deployment, set this to comma-separated hostnames/IPs,
    # for example: 127.0.0.1,localhost,192.168.1.50
    allowed_hosts: list[str] = [item.strip() for item in os.getenv("ALLOWED_HOSTS", "*").split(",") if item.strip()]
    security_headers_enabled: bool = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    session_cookie_secure: bool = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
    session_cookie_same_site: str = os.getenv("SESSION_COOKIE_SAMESITE", "lax")

    # Paper-trading risk limits. These apply only to local simulation.
    paper_max_stake_per_trade: float = float(os.getenv("PAPER_MAX_STAKE_PER_TRADE", "250"))
    paper_max_market_exposure: float = float(os.getenv("PAPER_MAX_MARKET_EXPOSURE", "500"))
    paper_max_total_exposure: float = float(os.getenv("PAPER_MAX_TOTAL_EXPOSURE", "2500"))
    paper_max_open_positions: int = int(os.getenv("PAPER_MAX_OPEN_POSITIONS", "20"))
    paper_min_liquidity: float = float(os.getenv("PAPER_MIN_LIQUIDITY", "1000"))
    paper_min_volume_24hr: float = float(os.getenv("PAPER_MIN_VOLUME_24HR", "10"))
    paper_block_extreme_prices: bool = os.getenv("PAPER_BLOCK_EXTREME_PRICES", "true").lower() in {"1", "true", "yes", "on"}
    paper_min_price: float = float(os.getenv("PAPER_MIN_PRICE", "0.02"))
    paper_max_price: float = float(os.getenv("PAPER_MAX_PRICE", "0.98"))

    # Optional future integrations. These are intentionally not required for the current read-only app.
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    news_api_key: str | None = os.getenv("NEWS_API_KEY")

    # Staged live-trading readiness fields. These are read/redacted only in this package.
    # Backward-compatible POLY_* names are preserved; POLYMARKET_* / CLOB_* aliases are accepted.
    poly_private_key: str | None = os.getenv("POLY_PRIVATE_KEY") or os.getenv("POLYMARKET_PRIVATE_KEY")
    poly_address: str | None = os.getenv("POLY_ADDRESS") or os.getenv("POLYMARKET_WALLET_ADDRESS")
    poly_api_key: str | None = os.getenv("POLY_API_KEY") or os.getenv("POLYMARKET_CLOB_API_KEY") or os.getenv("CLOB_API_KEY")
    poly_secret: str | None = os.getenv("POLY_SECRET") or os.getenv("POLYMARKET_CLOB_SECRET") or os.getenv("CLOB_SECRET")
    poly_passphrase: str | None = os.getenv("POLY_PASSPHRASE") or os.getenv("POLYMARKET_CLOB_PASSPHRASE") or os.getenv("CLOB_PASSPHRASE")
    polymarket_funder_address: str | None = os.getenv("POLYMARKET_FUNDER_ADDRESS")
    polymarket_chain_id: str = os.getenv("POLYMARKET_CHAIN_ID", "137")
    polymarket_signature_type: str = os.getenv("POLYMARKET_SIGNATURE_TYPE", "")
    polymarket_clob_host: str = os.getenv("POLYMARKET_CLOB_HOST", clob_base_url)
    live_dry_run_only: bool = os.getenv("LIVE_DRY_RUN_ONLY", "true").lower() in {"1", "true", "yes", "on"}
    live_require_manual_approval: bool = os.getenv("LIVE_REQUIRE_MANUAL_APPROVAL", "true").lower() in {"1", "true", "yes", "on"}
    live_pretrade_checks_enabled: bool = os.getenv("LIVE_PRETRADE_CHECKS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    live_audit_required: bool = os.getenv("LIVE_AUDIT_REQUIRED", "true").lower() in {"1", "true", "yes", "on"}
    live_max_order_notional: float = float(os.getenv("LIVE_MAX_ORDER_NOTIONAL", "0"))
    live_max_market_notional: float = float(os.getenv("LIVE_MAX_MARKET_NOTIONAL", "0"))
    live_max_daily_notional: float = float(os.getenv("LIVE_MAX_DAILY_NOTIONAL", "0"))
    live_max_open_orders: int = int(os.getenv("LIVE_MAX_OPEN_ORDERS", "0"))
    live_allowed_market_ids: list[str] = [item.strip() for item in os.getenv("LIVE_ALLOWED_MARKET_IDS", "").split(",") if item.strip()]

    # v2.1.0-real live trading control plane. Defaults are safe/fail-closed.
    polymarket_v2_trading_mode: str = os.getenv("POLYMARKET_V2_TRADING_MODE", "research_only")
    polymarket_v2_require_approval: bool = os.getenv("POLYMARKET_V2_REQUIRE_APPROVAL", "true").lower() in {"1", "true", "yes", "on"}
    polymarket_v2_confirmation_phrase: str = os.getenv("POLYMARKET_V2_CONFIRMATION_PHRASE", "LIVE ORDER APPROVED")
    polymarket_v2_force_read_only: bool = os.getenv("POLYMARKET_V2_FORCE_READ_ONLY", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_v2_allow_market_orders: bool = os.getenv("POLYMARKET_V2_ALLOW_MARKET_ORDERS", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_v2_allow_limit_orders: bool = os.getenv("POLYMARKET_V2_ALLOW_LIMIT_ORDERS", "true").lower() in {"1", "true", "yes", "on"}
    polymarket_v2_default_slippage_bps: float = float(os.getenv("POLYMARKET_V2_DEFAULT_SLIPPAGE_BPS", "150"))
    polymarket_v2_max_total_exposure: float = float(os.getenv("POLYMARKET_V2_MAX_TOTAL_EXPOSURE", "0"))
    polymarket_v2_sdk_family: str = os.getenv("POLYMARKET_V2_SDK_FAMILY", "official_unified_python_sdk_then_clob_fallback")
    polymarket_data_api_base_url: str = os.getenv("POLYMARKET_DATA_API_BASE_URL", "https://data-api.polymarket.com")

    # Live adapter boundary controls. Defaults are fail-closed; v1.0.0 enables manual submit/cancel only after every gate passes.
    polymarket_live_mode: bool = os.getenv("POLYMARKET_LIVE_MODE", os.getenv("LIVE_TRADING_ENABLED", "false")).lower() in {"1", "true", "yes", "on"}
    polymarket_live_network_readonly: bool = os.getenv("POLYMARKET_LIVE_NETWORK_READONLY", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_enable_submit: bool = os.getenv("POLYMARKET_LIVE_ENABLE_SUBMIT", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_enable_cancel: bool = os.getenv("POLYMARKET_LIVE_ENABLE_CANCEL", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_require_manual_auth: bool = os.getenv("POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH", os.getenv("LIVE_REQUIRE_MANUAL_APPROVAL", "true")).lower() in {"1", "true", "yes", "on"}
    polymarket_live_kill_switch: bool = os.getenv("POLYMARKET_LIVE_KILL_SWITCH", "true").lower() in {"1", "true", "yes", "on"}
    polymarket_live_require_dry_run_receipt: bool = os.getenv("POLYMARKET_LIVE_REQUIRE_DRY_RUN_RECEIPT", "true").lower() in {"1", "true", "yes", "on"}
    polymarket_live_readonly_timeout_seconds: float = float(os.getenv("POLYMARKET_LIVE_READONLY_TIMEOUT_SECONDS", "4"))

    # v0.9.0 manual live execution control plane. Fake-local simulation is also default-off.
    polymarket_live_manual_submit_enabled: bool = os.getenv("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_manual_cancel_enabled: bool = os.getenv("POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_fake_adapter_enabled: bool = os.getenv("POLYMARKET_LIVE_FAKE_ADAPTER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_final_confirmation_phrase: str = os.getenv("POLYMARKET_LIVE_FINAL_CONFIRMATION_PHRASE", "")
    polymarket_live_authorization_max_age_minutes: int = int(float(os.getenv("POLYMARKET_LIVE_AUTHORIZATION_MAX_AGE_MINUTES", "60")))
    polymarket_live_dry_run_max_age_minutes: int = int(float(os.getenv("POLYMARKET_LIVE_DRY_RUN_MAX_AGE_MINUTES", "60")))
    polymarket_live_adapter_request_max_age_minutes: int = int(float(os.getenv("POLYMARKET_LIVE_ADAPTER_REQUEST_MAX_AGE_MINUTES", "60")))

    # v0.9.0 market-data intelligence and execution-quality simulator. Public fetch is disabled by default.
    market_data_require_for_live: bool = os.getenv("POLYMARKET_MARKET_DATA_REQUIRE_FOR_LIVE", "true").lower() in {"1", "true", "yes", "on"}
    market_data_max_age_seconds: int = int(float(os.getenv("POLYMARKET_MARKET_DATA_MAX_AGE_SECONDS", "300")))
    market_data_max_spread_bps: float = float(os.getenv("POLYMARKET_MARKET_DATA_MAX_SPREAD_BPS", "250"))
    market_data_max_slippage_bps: float = float(os.getenv("POLYMARKET_MARKET_DATA_MAX_SLIPPAGE_BPS", "150"))
    market_data_min_top_depth: float = float(os.getenv("POLYMARKET_MARKET_DATA_MIN_TOP_DEPTH", "10"))
    market_data_min_total_depth: float = float(os.getenv("POLYMARKET_MARKET_DATA_MIN_TOTAL_DEPTH", "50"))
    market_data_public_fetch_enabled: bool = os.getenv("POLYMARKET_MARKET_DATA_PUBLIC_FETCH_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    market_data_timeout_seconds: float = float(os.getenv("POLYMARKET_MARKET_DATA_TIMEOUT_SECONDS", "4"))

    # v1.0.0 guarded live/manual adapter bridge controls. Defaults are fail-closed.
    polymarket_live_allow_real_network: bool = os.getenv("POLYMARKET_LIVE_ALLOW_REAL_NETWORK", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_enable_autonomous: bool = os.getenv("POLYMARKET_LIVE_ENABLE_AUTONOMOUS", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_emergency_cancel_enabled: bool = os.getenv("POLYMARKET_LIVE_EMERGENCY_CANCEL_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_live_real_adapter_experimental: bool = os.getenv("POLYMARKET_LIVE_REAL_ADAPTER_EXPERIMENTAL", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_run_real_live_tests: bool = os.getenv("POLYMARKET_RUN_REAL_LIVE_TESTS", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_real_live_test_confirmation: str = os.getenv("POLYMARKET_REAL_LIVE_TEST_CONFIRMATION", "")
    polymarket_live_market_allowlist: list[str] = [item.strip() for item in os.getenv("POLYMARKET_LIVE_MARKET_ALLOWLIST", os.getenv("LIVE_ALLOWED_MARKET_IDS", "")).split(",") if item.strip()]
    polymarket_live_token_allowlist: list[str] = [item.strip() for item in os.getenv("POLYMARKET_LIVE_TOKEN_ALLOWLIST", "").split(",") if item.strip()]
    polymarket_live_max_position_notional: float = float(os.getenv("POLYMARKET_LIVE_MAX_POSITION_NOTIONAL", "0"))
    polymarket_live_max_daily_loss: float = float(os.getenv("POLYMARKET_LIVE_MAX_DAILY_LOSS", "0"))
    polymarket_autonomous_max_orders_per_run: int = int(float(os.getenv("POLYMARKET_AUTONOMOUS_MAX_ORDERS_PER_RUN", "0")))
    polymarket_autonomous_max_orders_per_day: int = int(float(os.getenv("POLYMARKET_AUTONOMOUS_MAX_ORDERS_PER_DAY", "0")))
    polymarket_autonomous_min_signal_confidence: float = float(os.getenv("POLYMARKET_AUTONOMOUS_MIN_SIGNAL_CONFIDENCE", "0"))
    polymarket_autonomous_require_market_data: bool = os.getenv("POLYMARKET_AUTONOMOUS_REQUIRE_MARKET_DATA", "true").lower() in {"1", "true", "yes", "on"}
    polymarket_autonomous_require_execution_quality: bool = os.getenv("POLYMARKET_AUTONOMOUS_REQUIRE_EXECUTION_QUALITY", "true").lower() in {"1", "true", "yes", "on"}
    polymarket_autonomous_require_paper_approval: bool = os.getenv("POLYMARKET_AUTONOMOUS_REQUIRE_PAPER_APPROVAL", "true").lower() in {"1", "true", "yes", "on"}
    polymarket_autonomous_strategy_allowlist: list[str] = [item.strip() for item in os.getenv("POLYMARKET_AUTONOMOUS_STRATEGY_ALLOWLIST", "").split(",") if item.strip()]
    polymarket_autonomous_dry_run_by_default: bool = os.getenv("POLYMARKET_AUTONOMOUS_DRY_RUN_BY_DEFAULT", "true").lower() in {"1", "true", "yes", "on"}
    polymarket_autonomous_scheduler_enabled: bool = os.getenv("POLYMARKET_AUTONOMOUS_SCHEDULER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_autonomous_scheduler_interval_seconds: int = int(float(os.getenv("POLYMARKET_AUTONOMOUS_SCHEDULER_INTERVAL_SECONDS", "0")))
    polymarket_autonomous_scheduler_dry_run_only: bool = os.getenv("POLYMARKET_AUTONOMOUS_SCHEDULER_DRY_RUN_ONLY", "true").lower() in {"1", "true", "yes", "on"}

    # v1.3.0 data ingestion and dataset builder. Network ingestion and schedulers are disabled by default.
    polymarket_data_allow_network: bool = os.getenv("POLYMARKET_DATA_ALLOW_NETWORK", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_data_ingestion_scheduler_enabled: bool = os.getenv("POLYMARKET_DATA_INGESTION_SCHEDULER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    polymarket_data_ingestion_max_rows: int = int(float(os.getenv("POLYMARKET_DATA_INGESTION_MAX_ROWS", "100000")))
    polymarket_data_default_split_method: str = os.getenv("POLYMARKET_DATA_DEFAULT_SPLIT_METHOD", "chronological")


settings = Settings()
