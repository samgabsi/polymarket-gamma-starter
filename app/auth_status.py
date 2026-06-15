from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .config import APP_VERSION, settings


@dataclass(frozen=True)
class ApiCredential:
    name: str
    env_vars: list[str]
    required_when: str
    status: str
    note: str


def _present(value: str | None) -> bool:
    return bool(value and value.strip() and not value.strip().startswith("CHANGE_ME"))


def get_api_key_status() -> dict[str, Any]:
    """Return a safe, redacted report of current API-key readiness.

    No secret values are returned. This module is intentionally informational only.
    The app remains read-only unless a later version adds an execution layer.
    """
    has_private_key = _present(settings.poly_private_key)
    has_l2 = all(
        _present(v)
        for v in [
            settings.poly_address,
            settings.poly_api_key,
            settings.poly_secret,
            settings.poly_passphrase,
        ]
    )
    has_openai = _present(settings.openai_api_key)
    has_news = _present(settings.news_api_key)

    rows = [
        ApiCredential(
            name="Gamma API",
            env_vars=[],
            required_when="Already in use: public market/event discovery.",
            status="not_required",
            note="No key needed.",
        ),
        ApiCredential(
            name="CLOB read-only endpoints",
            env_vars=[],
            required_when="Already in use: public order books, prices, spreads.",
            status="not_required",
            note="No key needed for public market data.",
        ),
        ApiCredential(
            name="Data API public analytics",
            env_vars=[],
            required_when="Next analytics phase: profiles, public activity, leaderboards, open interest.",
            status="not_required",
            note="No key needed for public Data API endpoints.",
        ),
        ApiCredential(
            name="OpenAI API",
            env_vars=["OPENAI_API_KEY"],
            required_when="Research summarization/probability-assist phase.",
            status="configured" if has_openai else "optional_missing",
            note="Only needed once local research packets become LLM-generated analysis.",
        ),
        ApiCredential(
            name="News/search provider",
            env_vars=["NEWS_API_KEY"],
            required_when="Automated news ingestion phase.",
            status="configured" if has_news else "optional_missing",
            note="Placeholder; choose provider later. Current version uses manual source links.",
        ),
        ApiCredential(
            name="CLOB L1 wallet signing",
            env_vars=["POLY_PRIVATE_KEY"],
            required_when="Future credential derivation/signing phase only.",
            status="configured" if has_private_key else "future_missing",
            note="Secret presence is redacted. This build does not derive credentials, sign, or submit orders.",
        ),
        ApiCredential(
            name="CLOB L2 API credentials",
            env_vars=["POLY_ADDRESS", "POLY_API_KEY", "POLY_SECRET", "POLY_PASSPHRASE"],
            required_when="Future authenticated CLOB order-management endpoints.",
            status="configured" if has_l2 else "future_missing",
            note="Fields are available for local population, but this build only reports readiness and never uses them to trade.",
        ),
    ]

    return {
        "mode": settings.app_mode,
        "read_only": settings.read_only,
        "live_trading_enabled": settings.live_trading_enabled,
        "safe_to_run_without_keys": True,
        "message": f"{APP_VERSION} exposes redacted live-readiness and adapter-boundary fields only. It does not sign, place, cancel, or automate live orders.",
        "items": [asdict(r) for r in rows],
    }
