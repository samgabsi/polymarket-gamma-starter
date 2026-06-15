from __future__ import annotations

import os
import platform
import socket
from pathlib import Path
from typing import Any

from .config import APP_VERSION, PROJECT_ROOT, DATA_DIR, settings
from .auth import USERS_PATH, SECRET_PATH, users_exist, list_users_public

SENSITIVE_NAMES = {
    "OPENAI_API_KEY", "NEWS_API_KEY", "POLY_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY",
    "POLY_ADDRESS", "POLYMARKET_WALLET_ADDRESS", "POLY_API_KEY", "POLYMARKET_CLOB_API_KEY",
    "CLOB_API_KEY", "POLY_SECRET", "POLYMARKET_CLOB_SECRET", "CLOB_SECRET",
    "POLY_PASSPHRASE", "POLYMARKET_CLOB_PASSPHRASE", "CLOB_PASSPHRASE",
}

CONFIG_KEYS = [
    "HOST", "PORT", "APP_RELOAD", "ALLOWED_HOSTS", "SECURITY_HEADERS_ENABLED",
    "SESSION_COOKIE_SECURE", "SESSION_COOKIE_SAMESITE", "APP_MODE", "READ_ONLY",
    "LIVE_TRADING_ENABLED", "GAMMA_BASE_URL", "CLOB_BASE_URL", "REQUEST_TIMEOUT_SECONDS",
    "DEFAULT_LIMIT", "PAPER_MAX_STAKE_PER_TRADE", "PAPER_MAX_MARKET_EXPOSURE",
    "PAPER_MAX_TOTAL_EXPOSURE", "PAPER_MAX_OPEN_POSITIONS", "PAPER_MIN_LIQUIDITY",
    "PAPER_MIN_VOLUME_24HR", "PAPER_BLOCK_EXTREME_PRICES", "PAPER_MIN_PRICE",
    "PAPER_MAX_PRICE", "OPENAI_API_KEY", "NEWS_API_KEY", "LIVE_DRY_RUN_ONLY",
    "LIVE_REQUIRE_MANUAL_APPROVAL", "LIVE_PRETRADE_CHECKS_ENABLED", "LIVE_AUDIT_REQUIRED",
    "LIVE_MAX_ORDER_NOTIONAL", "LIVE_MAX_MARKET_NOTIONAL", "LIVE_MAX_DAILY_NOTIONAL",
    "LIVE_MAX_OPEN_ORDERS", "LIVE_ALLOWED_MARKET_IDS", "POLYMARKET_LIVE_MODE",
    "POLYMARKET_LIVE_NETWORK_READONLY", "POLYMARKET_LIVE_ENABLE_SUBMIT",
    "POLYMARKET_LIVE_ENABLE_CANCEL", "POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH",
    "POLYMARKET_LIVE_KILL_SWITCH", "POLYMARKET_LIVE_REQUIRE_DRY_RUN_RECEIPT",
    "POLYMARKET_LIVE_READONLY_TIMEOUT_SECONDS", "POLYMARKET_CLOB_HOST",
    "POLYMARKET_CHAIN_ID", "POLYMARKET_SIGNATURE_TYPE",
    "POLYMARKET_FUNDER_ADDRESS", "POLY_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY",
    "POLY_ADDRESS", "POLYMARKET_WALLET_ADDRESS", "POLY_API_KEY", "POLYMARKET_CLOB_API_KEY",
    "CLOB_API_KEY", "POLY_SECRET", "POLYMARKET_CLOB_SECRET", "CLOB_SECRET",
    "POLY_PASSPHRASE", "POLYMARKET_CLOB_PASSPHRASE", "CLOB_PASSPHRASE",
]


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def _lan_ips() -> list[str]:
    ips: set[str] = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
            ip = item[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if not ip.startswith("127."):
            ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def runtime_config() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in CONFIG_KEYS:
        raw = os.getenv(key)
        rows.append({
            "key": key,
            "value": _mask(raw) if key in SENSITIVE_NAMES else raw,
            "set": raw is not None and raw != "",
            "sensitive": key in SENSITIVE_NAMES,
        })
    return rows


def deployment_status() -> dict[str, Any]:
    lan_ips = _lan_ips()
    users = list_users_public() if users_exist() else []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            warnings.append(detail)

    check("Admin initialized", users_exist(), "Initial admin user has not been created yet.")
    check("At least one active admin", any(u.get("role") == "admin" and u.get("status") == "active" for u in users), "No active admin account is available.")
    check("Session secret exists", SECRET_PATH.exists(), "Session secret has not been generated yet.")
    check("User database path writable", os.access(DATA_DIR, os.W_OK), f"Data directory is not writable: {DATA_DIR}")
    check("Security headers enabled", settings.security_headers_enabled, "Security headers are disabled.")
    if settings.host in {"0.0.0.0", "::"}:
        check("LAN bind active", True, "Server is listening on all interfaces for LAN access.")
        check("Authentication enabled for LAN", users_exist(), "LAN access is enabled before admin setup is complete.")
    else:
        check("LAN bind active", False, "Server is not bound to 0.0.0.0; LAN devices may not reach it.")
    if "*" in settings.allowed_hosts:
        warnings.append("ALLOWED_HOSTS is '*'. This is convenient for LAN testing but should be restricted for stable deployments.")
    if not settings.session_cookie_secure:
        warnings.append("SESSION_COOKIE_SECURE is false. This is normal for http:// LAN testing; set true behind HTTPS.")

    return {
        "version": APP_VERSION,
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(DATA_DIR),
        "users_path": str(USERS_PATH),
        "host": settings.host,
        "port": settings.port,
        "allowed_hosts": settings.allowed_hosts,
        "lan_ips": lan_ips,
        "urls": {
            "local": f"http://127.0.0.1:{settings.port}",
            "lan": [f"http://{ip}:{settings.port}" for ip in lan_ips],
        },
        "platform": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "checks": checks,
        "warnings": warnings,
        "config": runtime_config(),
    }
