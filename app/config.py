from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_VERSION = "4.17.0-real"
APP_VERSION_SHORT = "4.17.0"
APP_DIR = PROJECT_ROOT / "app"
DATA_DIR = PROJECT_ROOT / "data"

load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


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

    # v4.17 automated paper trading. Defaults are fail-closed for automation and always paper-only.
    paper_trading_enabled: bool = _env_bool("PAPER_TRADING_ENABLED", "false")
    paper_trading_automation_enabled: bool = _env_bool("PAPER_TRADING_AUTOMATION_ENABLED", "false")
    paper_trading_require_operator_start: bool = _env_bool("PAPER_TRADING_REQUIRE_OPERATOR_START", "true")
    paper_trading_starting_balance: float = float(os.getenv("PAPER_TRADING_STARTING_BALANCE", "1000"))
    paper_trading_max_order_notional: float = float(os.getenv("PAPER_TRADING_MAX_ORDER_NOTIONAL", "25"))
    paper_trading_max_market_notional: float = float(os.getenv("PAPER_TRADING_MAX_MARKET_NOTIONAL", "100"))
    paper_trading_max_daily_notional: float = float(os.getenv("PAPER_TRADING_MAX_DAILY_NOTIONAL", "250"))
    paper_trading_max_open_positions: int = int(float(os.getenv("PAPER_TRADING_MAX_OPEN_POSITIONS", "10")))
    paper_trading_max_trades_per_run: int = int(float(os.getenv("PAPER_TRADING_MAX_TRADES_PER_RUN", "3")))
    paper_trading_max_trades_per_day: int = int(float(os.getenv("PAPER_TRADING_MAX_TRADES_PER_DAY", "20")))
    paper_trading_min_edge_pct: float = float(os.getenv("PAPER_TRADING_MIN_EDGE_PCT", "2.0"))
    paper_trading_min_confidence: float = float(os.getenv("PAPER_TRADING_MIN_CONFIDENCE", "0.70"))
    paper_trading_max_spread_bps: float = float(os.getenv("PAPER_TRADING_MAX_SPREAD_BPS", "250"))
    paper_trading_max_slippage_bps: float = float(os.getenv("PAPER_TRADING_MAX_SLIPPAGE_BPS", "150"))
    paper_trading_require_fresh_data: bool = _env_bool("PAPER_TRADING_REQUIRE_FRESH_DATA", "true")
    paper_trading_max_data_age_seconds: int = int(float(os.getenv("PAPER_TRADING_MAX_DATA_AGE_SECONDS", "300")))
    paper_trading_allow_ai_signals: bool = _env_bool("PAPER_TRADING_ALLOW_AI_SIGNALS", "true")
    paper_trading_allow_arbitrage_signals: bool = _env_bool("PAPER_TRADING_ALLOW_ARBITRAGE_SIGNALS", "true")
    paper_trading_allow_manual_watchlist_signals: bool = _env_bool("PAPER_TRADING_ALLOW_MANUAL_WATCHLIST_SIGNALS", "true")
    paper_trading_fill_model: str = os.getenv("PAPER_TRADING_FILL_MODEL", "conservative")
    paper_trading_fees_bps: float = float(os.getenv("PAPER_TRADING_FEES_BPS", "0"))
    paper_trading_scheduler_enabled: bool = _env_bool("PAPER_TRADING_SCHEDULER_ENABLED", "false")
    paper_trading_scheduler_interval_seconds: int = int(float(os.getenv("PAPER_TRADING_SCHEDULER_INTERVAL_SECONDS", "300")))
    paper_trading_log_decisions: bool = _env_bool("PAPER_TRADING_LOG_DECISIONS", "true")
    paper_trading_audit_required: bool = _env_bool("PAPER_TRADING_AUDIT_REQUIRED", "true")
    paper_trading_allow_sample_candidates: bool = _env_bool("PAPER_TRADING_ALLOW_SAMPLE_CANDIDATES", "true")

    # v4.4 multi-provider AI assistance. Defaults are safe/fail-closed: disabled, mock provider, dry-run, redacted, no network.
    ai_enable: bool = _env_bool("AI_ENABLE", "false")
    ai_provider: str = os.getenv("AI_PROVIDER", "mock")
    ai_dry_run_only: bool = _env_bool("AI_DRY_RUN_ONLY", "true")
    ai_require_operator_approval: bool = _env_bool("AI_REQUIRE_OPERATOR_APPROVAL", "true")
    ai_redact_before_send: bool = _env_bool("AI_REDACT_BEFORE_SEND", "true")
    ai_allow_network: bool = _env_bool("AI_ALLOW_NETWORK", "false")
    ai_allow_runtime_data: bool = _env_bool("AI_ALLOW_RUNTIME_DATA", "false")
    ai_allow_market_data: bool = _env_bool("AI_ALLOW_MARKET_DATA", "false")
    ai_allow_task_data: bool = _env_bool("AI_ALLOW_TASK_DATA", "false")
    ai_allow_docs_data: bool = _env_bool("AI_ALLOW_DOCS_DATA", "false")
    ai_allow_platform_diagnostics: bool = _env_bool("AI_ALLOW_PLATFORM_DIAGNOSTICS", "false")
    ai_allow_migration_reports: bool = _env_bool("AI_ALLOW_MIGRATION_REPORTS", "false")
    ai_log_prompt_hashes_only: bool = _env_bool("AI_LOG_PROMPT_HASHES_ONLY", "true")
    ai_store_raw_prompts: bool = _env_bool("AI_STORE_RAW_PROMPTS", "false")
    ai_store_raw_responses: bool = _env_bool("AI_STORE_RAW_RESPONSES", "false")
    ai_audit_enabled: bool = _env_bool("AI_AUDIT_ENABLED", "true")
    ai_max_input_chars: int = int(float(os.getenv("AI_MAX_INPUT_CHARS", "12000")))
    ai_max_output_tokens: int = int(float(os.getenv("AI_MAX_OUTPUT_TOKENS", "2500")))
    ai_timeout_seconds: float = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))

    # v4.4 AI Edge Research. Defaults are research-only, mock, dry-run, approval-gated, and web-search disabled.
    ai_edge_enable: bool = _env_bool("AI_EDGE_ENABLE", "false")
    ai_edge_provider: str = os.getenv("AI_EDGE_PROVIDER", "mock")
    ai_edge_dry_run_only: bool = _env_bool("AI_EDGE_DRY_RUN_ONLY", "true")
    ai_edge_require_operator_approval: bool = _env_bool("AI_EDGE_REQUIRE_OPERATOR_APPROVAL", "true")
    ai_edge_allow_web_search: bool = _env_bool("AI_EDGE_ALLOW_WEB_SEARCH", "false")
    ai_edge_allow_market_context: bool = _env_bool("AI_EDGE_ALLOW_MARKET_CONTEXT", "false")
    ai_edge_allow_runtime_data: bool = _env_bool("AI_EDGE_ALLOW_RUNTIME_DATA", "false")
    ai_edge_allow_source_urls: bool = _env_bool("AI_EDGE_ALLOW_SOURCE_URLS", "true")
    ai_edge_allow_model_probability_drafts: bool = _env_bool("AI_EDGE_ALLOW_MODEL_PROBABILITY_DRAFTS", "true")
    ai_edge_allow_market_implied_comparison: bool = _env_bool("AI_EDGE_ALLOW_MARKET_IMPLIED_COMPARISON", "false")
    ai_edge_allow_calibration_tracking: bool = _env_bool("AI_EDGE_ALLOW_CALIBRATION_TRACKING", "true")
    ai_edge_redact_before_send: bool = _env_bool("AI_EDGE_REDACT_BEFORE_SEND", "true")
    ai_edge_store_raw_prompts: bool = _env_bool("AI_EDGE_STORE_RAW_PROMPTS", "false")
    ai_edge_store_raw_responses: bool = _env_bool("AI_EDGE_STORE_RAW_RESPONSES", "false")
    ai_edge_log_prompt_hashes_only: bool = _env_bool("AI_EDGE_LOG_PROMPT_HASHES_ONLY", "true")
    ai_edge_max_input_chars: int = int(float(os.getenv("AI_EDGE_MAX_INPUT_CHARS", "12000")))
    ai_edge_max_output_tokens: int = int(float(os.getenv("AI_EDGE_MAX_OUTPUT_TOKENS", "2500")))
    ai_edge_timeout_seconds: float = float(os.getenv("AI_EDGE_TIMEOUT_SECONDS", "90"))

    # v4.6 market-edge recommendation clarity. Defaults are review-only, approximate, and fail toward HOLD/review.
    edge_min_yes_pp: float = float(os.getenv("EDGE_MIN_YES_PP", "2.0"))
    edge_min_no_pp: float = float(os.getenv("EDGE_MIN_NO_PP", "2.0"))
    edge_min_liquidity: str = os.getenv("EDGE_MIN_LIQUIDITY", "")
    edge_min_volume_24h: str = os.getenv("EDGE_MIN_VOLUME_24H", "")
    edge_require_fresh_data: bool = _env_bool("EDGE_REQUIRE_FRESH_DATA", "true")
    edge_max_data_age_minutes: str = os.getenv("EDGE_MAX_DATA_AGE_MINUTES", "")
    edge_show_favorite_rank: bool = _env_bool("EDGE_SHOW_FAVORITE_RANK", "true")
    edge_show_family_groups: bool = _env_bool("EDGE_SHOW_FAMILY_GROUPS", "true")
    edge_show_ai_edge_actions: bool = _env_bool("EDGE_SHOW_AI_EDGE_ACTIONS", "true")
    edge_default_recommendation_mode: str = os.getenv("EDGE_DEFAULT_RECOMMENDATION_MODE", "review_only")

    # v4.6 opportunity review workbench. Defaults are review-only and store local runtime records outside release packages.
    opportunity_review_enabled: bool = _env_bool("OPPORTUNITY_REVIEW_ENABLED", "true")
    opportunity_notes_enabled: bool = _env_bool("OPPORTUNITY_NOTES_ENABLED", "true")
    opportunity_review_store: str = os.getenv("OPPORTUNITY_REVIEW_STORE", "runtime/opportunity_reviews")
    edge_detail_pages_enabled: bool = _env_bool("EDGE_DETAIL_PAGES_ENABLED", "true")
    edge_family_pages_enabled: bool = _env_bool("EDGE_FAMILY_PAGES_ENABLED", "true")
    ai_edge_packet_lifecycle_enabled: bool = _env_bool("AI_EDGE_PACKET_LIFECYCLE_ENABLED", "true")
    ai_edge_review_only: bool = _env_bool("AI_EDGE_REVIEW_ONLY", "true")
    watchlist_review_only: bool = _env_bool("WATCHLIST_REVIEW_ONLY", "true")
    paper_review_draft_only: bool = _env_bool("PAPER_REVIEW_DRAFT_ONLY", "true")

    # v4.15 evidence-weighted odds adjustment controls. Defaults intentionally keep behavior close to the old 2.5 pp safety posture.
    ai_odds_adjustment_enabled: bool = _env_bool("AI_ODDS_ADJUSTMENT_ENABLED", os.getenv("AI_NEWS_ODDS_ENABLED", "true"))
    ai_odds_adjustment_mode: str = os.getenv("AI_ODDS_ADJUSTMENT_MODE", "conservative").strip().lower()
    ai_default_max_adjustment_pct: float = float(os.getenv("AI_DEFAULT_MAX_ADJUSTMENT_PCT", "2.5"))
    ai_balanced_max_adjustment_pct: float = float(os.getenv("AI_BALANCED_MAX_ADJUSTMENT_PCT", "7.5"))
    ai_aggressive_max_adjustment_pct: float = float(os.getenv("AI_AGGRESSIVE_MAX_ADJUSTMENT_PCT", "15.0"))
    ai_absolute_hard_cap_pct: float = float(os.getenv("AI_ABSOLUTE_HARD_CAP_PCT", "25.0"))
    ai_require_extra_evidence_above_pct: float = float(os.getenv("AI_REQUIRE_EXTRA_EVIDENCE_ABOVE_PCT", "5.0"))
    ai_require_operator_confirm_above_pct: float = float(os.getenv("AI_REQUIRE_OPERATOR_CONFIRM_ABOVE_PCT", "10.0"))
    ai_allow_cap_exceed_with_evidence: bool = _env_bool("AI_ALLOW_CAP_EXCEED_WITH_EVIDENCE", "false")

    # v4.7 AI News Odds Adjustment Engine. Defaults are review-only; web search and local LLM are disabled unless explicitly configured.
    ai_news_odds_enabled: bool = _env_bool("AI_NEWS_ODDS_ENABLED", "true")
    ai_news_odds_web_search_enabled: bool = _env_bool("AI_NEWS_ODDS_WEB_SEARCH_ENABLED", "false")
    ai_news_odds_manual_evidence_enabled: bool = _env_bool("AI_NEWS_ODDS_MANUAL_EVIDENCE_ENABLED", "true")
    ai_news_odds_local_llm_enabled: bool = _env_bool("AI_NEWS_ODDS_LOCAL_LLM_ENABLED", "false")
    ai_news_odds_review_only: bool = _env_bool("AI_NEWS_ODDS_REVIEW_ONLY", "true")
    ai_news_odds_require_human_accept: bool = _env_bool("AI_NEWS_ODDS_REQUIRE_HUMAN_ACCEPT", "true")
    ai_news_odds_can_place_orders: bool = _env_bool("AI_NEWS_ODDS_CAN_PLACE_ORDERS", "false")
    ai_news_odds_can_cancel_orders: bool = _env_bool("AI_NEWS_ODDS_CAN_CANCEL_ORDERS", "false")
    ai_news_odds_can_arm_live: bool = _env_bool("AI_NEWS_ODDS_CAN_ARM_LIVE", "false")
    ai_news_odds_max_adjustment_pp: float = float(os.getenv("AI_NEWS_ODDS_MAX_ADJUSTMENT_PP", "8.0"))
    ai_news_odds_max_cluster_adjustment_pp: float = float(os.getenv("AI_NEWS_ODDS_MAX_CLUSTER_ADJUSTMENT_PP", "3.0"))
    ai_news_odds_max_low_confidence_adjustment_pp: float = float(os.getenv("AI_NEWS_ODDS_MAX_LOW_CONFIDENCE_ADJUSTMENT_PP", "1.0"))
    ai_news_odds_max_no_primary_source_adjustment_pp: float = float(os.getenv("AI_NEWS_ODDS_MAX_NO_PRIMARY_SOURCE_ADJUSTMENT_PP", "4.0"))
    ai_news_odds_contradiction_penalty: bool = _env_bool("AI_NEWS_ODDS_CONTRADICTION_PENALTY", "true")
    ai_news_odds_duplicate_penalty: bool = _env_bool("AI_NEWS_ODDS_DUPLICATE_PENALTY", "true")
    ai_news_odds_min_independent_sources_for_medium: int = int(float(os.getenv("AI_NEWS_ODDS_MIN_INDEPENDENT_SOURCES_FOR_MEDIUM", "2")))
    ai_news_odds_min_high_cred_sources_for_high: int = int(float(os.getenv("AI_NEWS_ODDS_MIN_HIGH_CRED_SOURCES_FOR_HIGH", "1")))
    ai_news_odds_store: str = os.getenv("AI_NEWS_ODDS_STORE", "runtime/ai_news_odds")
    ai_news_odds_audit_store: str = os.getenv("AI_NEWS_ODDS_AUDIT_STORE", "runtime/ai_news_odds_audit")
    ai_news_source_weight_primary: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_PRIMARY", "1.00"))
    ai_news_source_weight_government: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_GOVERNMENT", "0.95"))
    ai_news_source_weight_regulator: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_REGULATOR", "0.95"))
    ai_news_source_weight_wire: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_WIRE", "0.85"))
    ai_news_source_weight_major_news: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_MAJOR_NEWS", "0.80"))
    ai_news_source_weight_specialist: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_SPECIALIST", "0.70"))
    ai_news_source_weight_local: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_LOCAL", "0.55"))
    ai_news_source_weight_blog: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_BLOG", "0.40"))
    ai_news_source_weight_social: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_SOCIAL", "0.30"))
    ai_news_source_weight_forum: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_FORUM", "0.20"))
    ai_news_source_weight_unknown: float = float(os.getenv("AI_NEWS_SOURCE_WEIGHT_UNKNOWN", "0.25"))

    # v4.15 cross-market arbitrage scanner. Detection is review-only and disabled by default.
    kalshi_enabled: bool = _env_bool("KALSHI_ENABLED", "false")
    kalshi_api_base_url: str = os.getenv("KALSHI_API_BASE_URL", "https://external-api.kalshi.com/trade-api/v2")
    kalshi_demo_api_base_url: str = os.getenv("KALSHI_DEMO_API_BASE_URL", "https://external-api.demo.kalshi.co/trade-api/v2")
    kalshi_use_demo: bool = _env_bool("KALSHI_USE_DEMO", "false")
    kalshi_api_key_id: str | None = os.getenv("KALSHI_API_KEY_ID") or os.getenv("KALSHI_ACCESS_KEY")
    kalshi_private_key_path: str = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    kalshi_timeout_seconds: float = float(os.getenv("KALSHI_TIMEOUT_SECONDS", "8"))

    arbitrage_scanner_enabled: bool = _env_bool("ARBITRAGE_SCANNER_ENABLED", "false")
    arbitrage_review_only: bool = _env_bool("ARBITRAGE_REVIEW_ONLY", "true")
    arbitrage_fetch_orderbooks: bool = _env_bool("ARBITRAGE_FETCH_ORDERBOOKS", "false")
    arbitrage_min_net_margin_pct: float = float(os.getenv("ARBITRAGE_MIN_NET_MARGIN_PCT", "1.0"))
    arbitrage_min_confidence: float = float(os.getenv("ARBITRAGE_MIN_CONFIDENCE", "0.72"))
    arbitrage_max_stale_seconds: int = int(float(os.getenv("ARBITRAGE_MAX_STALE_SECONDS", "300")))
    arbitrage_max_resolution_mismatch_risk: float = float(os.getenv("ARBITRAGE_MAX_RESOLUTION_MISMATCH_RISK", "0.35"))
    arbitrage_scan_interval_seconds: int = int(float(os.getenv("ARBITRAGE_SCAN_INTERVAL_SECONDS", "300")))
    arbitrage_default_slippage_bps: float = float(os.getenv("ARBITRAGE_DEFAULT_SLIPPAGE_BPS", "50"))
    arbitrage_min_liquidity: float = float(os.getenv("ARBITRAGE_MIN_LIQUIDITY", "10"))
    arbitrage_competitor_venues: list[str] = [item.strip() for item in os.getenv("ARBITRAGE_COMPETITOR_VENUES", "").split(",") if item.strip()]

    # OpenAI / ChatGPT cloud provider. These are intentionally not required for the current read-only app.
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_project_id: str | None = os.getenv("OPENAI_PROJECT_ID")
    openai_org_id: str | None = os.getenv("OPENAI_ORG_ID")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model_review: str = os.getenv("OPENAI_MODEL_REVIEW", "gpt-5.5")
    openai_model_fast: str = os.getenv("OPENAI_MODEL_FAST", "gpt-5.4-mini")
    openai_model_low_cost: str = os.getenv("OPENAI_MODEL_LOW_COST", "gpt-5.4-nano")
    openai_enable_api: bool = _env_bool("OPENAI_ENABLE_API", "false")
    openai_enable_responses_api: bool = _env_bool("OPENAI_ENABLE_RESPONSES_API", "false")
    openai_enable_structured_outputs: bool = _env_bool("OPENAI_ENABLE_STRUCTURED_OUTPUTS", "true")
    openai_enable_tool_calling: bool = _env_bool("OPENAI_ENABLE_TOOL_CALLING", "false")
    openai_enable_remote_mcp: bool = _env_bool("OPENAI_ENABLE_REMOTE_MCP", "false")
    openai_enable_web_search: bool = _env_bool("OPENAI_ENABLE_WEB_SEARCH", "false")
    openai_web_search_require_operator_confirmation: bool = _env_bool("OPENAI_WEB_SEARCH_REQUIRE_OPERATOR_CONFIRMATION", "true")
    openai_web_search_max_queries: int = int(float(os.getenv("OPENAI_WEB_SEARCH_MAX_QUERIES", "5")))
    openai_web_search_max_sources: int = int(float(os.getenv("OPENAI_WEB_SEARCH_MAX_SOURCES", "12")))
    openai_web_search_require_citations: bool = _env_bool("OPENAI_WEB_SEARCH_REQUIRE_CITATIONS", "true")
    openai_web_search_recency_required: bool = _env_bool("OPENAI_WEB_SEARCH_RECENCY_REQUIRED", "true")
    openai_web_search_allow_market_research: bool = _env_bool("OPENAI_WEB_SEARCH_ALLOW_MARKET_RESEARCH", "true")
    openai_web_search_allow_private_data: bool = _env_bool("OPENAI_WEB_SEARCH_ALLOW_PRIVATE_DATA", "false")
    openai_enable_file_search: bool = _env_bool("OPENAI_ENABLE_FILE_SEARCH", "false")
    openai_enable_code_interpreter: bool = _env_bool("OPENAI_ENABLE_CODE_INTERPRETER", "false")
    openai_allow_sending_runtime_data: bool = _env_bool("OPENAI_ALLOW_SENDING_RUNTIME_DATA", "false")
    openai_allow_sending_market_data: bool = _env_bool("OPENAI_ALLOW_SENDING_MARKET_DATA", "false")
    openai_allow_sending_tasks: bool = _env_bool("OPENAI_ALLOW_SENDING_TASKS", "false")
    openai_allow_sending_docs: bool = _env_bool("OPENAI_ALLOW_SENDING_DOCS", "false")
    openai_allow_sending_platform_diagnostics: bool = _env_bool("OPENAI_ALLOW_SENDING_PLATFORM_DIAGNOSTICS", "false")
    openai_allow_sending_migration_reports: bool = _env_bool("OPENAI_ALLOW_SENDING_MIGRATION_REPORTS", "false")
    openai_redact_before_send: bool = _env_bool("OPENAI_REDACT_BEFORE_SEND", "true")
    openai_require_operator_approval: bool = _env_bool("OPENAI_REQUIRE_OPERATOR_APPROVAL", "true")
    openai_max_input_chars: int = int(float(os.getenv("OPENAI_MAX_INPUT_CHARS", "12000")))
    openai_max_output_tokens: int = int(float(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "2000")))
    openai_timeout_seconds: float = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
    openai_dry_run_only: bool = _env_bool("OPENAI_DRY_RUN_ONLY", "true")
    openai_log_prompt_hashes_only: bool = _env_bool("OPENAI_LOG_PROMPT_HASHES_ONLY", "true")
    openai_audit_enabled: bool = _env_bool("OPENAI_AUDIT_ENABLED", "true")
    chatgpt_connector_blueprint_enabled: bool = _env_bool("CHATGPT_CONNECTOR_BLUEPRINT_ENABLED", "true")
    chatgpt_mcp_server_enabled: bool = _env_bool("CHATGPT_MCP_SERVER_ENABLED", "false")
    chatgpt_mcp_require_auth: bool = _env_bool("CHATGPT_MCP_REQUIRE_AUTH", "true")
    chatgpt_mcp_read_only: bool = _env_bool("CHATGPT_MCP_READ_ONLY", "true")

    # Local LLM runtime provider. Defaults are disabled, localhost-required, and no-network unless explicitly enabled.
    local_llm_enable: bool = _env_bool("LOCAL_LLM_ENABLE", "false")
    local_llm_provider: str = os.getenv("LOCAL_LLM_PROVIDER", "ollama")
    local_llm_base_url: str = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    local_llm_model: str = os.getenv("LOCAL_LLM_MODEL", "qwen3:8b")
    local_llm_openai_compatible: bool = _env_bool("LOCAL_LLM_OPENAI_COMPATIBLE", "true")
    local_llm_require_localhost: bool = _env_bool("LOCAL_LLM_REQUIRE_LOCALHOST", "true")
    local_llm_allow_network: bool = _env_bool("LOCAL_LLM_ALLOW_NETWORK", "false")
    local_llm_allow_runtime_data: bool = _env_bool("LOCAL_LLM_ALLOW_RUNTIME_DATA", "false")
    local_llm_timeout_seconds: float = float(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "90"))
    local_llm_max_input_chars: int = int(float(os.getenv("LOCAL_LLM_MAX_INPUT_CHARS", "8000")))
    local_llm_max_output_tokens: int = int(float(os.getenv("LOCAL_LLM_MAX_OUTPUT_TOKENS", "2000")))
    local_llm_enable_edge_review: bool = _env_bool("LOCAL_LLM_ENABLE_EDGE_REVIEW", "false")
    local_llm_edge_requires_app_evidence: bool = _env_bool("LOCAL_LLM_EDGE_REQUIRES_APP_EVIDENCE", "true")
    local_llm_edge_can_search_web: bool = _env_bool("LOCAL_LLM_EDGE_CAN_SEARCH_WEB", "false")
    local_llm_edge_model: str = os.getenv("LOCAL_LLM_EDGE_MODEL", "qwen3:8b")
    local_llm_edge_max_input_chars: int = int(float(os.getenv("LOCAL_LLM_EDGE_MAX_INPUT_CHARS", "8000")))
    local_llm_edge_timeout_seconds: float = float(os.getenv("LOCAL_LLM_EDGE_TIMEOUT_SECONDS", "90"))
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    llama_cpp_base_url: str = os.getenv("LLAMA_CPP_BASE_URL", "http://127.0.0.1:8080/v1")
    llama_cpp_model: str = os.getenv("LLAMA_CPP_MODEL", "local-model")
    lm_studio_base_url: str = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    lm_studio_model: str = os.getenv("LM_STUDIO_MODEL", "local-model")

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

    # v4.4.0-real live trading control plane. Defaults are safe/fail-closed.
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
