from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .config import settings


def _host_without_port(host_header: str | None) -> str:
    if not host_header:
        return ""
    host = host_header.strip()
    if host.startswith("[") and "]" in host:
        return host[1:host.index("]")]
    return host.split(":", 1)[0].strip().lower()


def host_allowed(host: str, allowed_hosts: Iterable[str] | None = None) -> bool:
    allowed = list(allowed_hosts if allowed_hosts is not None else settings.allowed_hosts)
    if not allowed or "*" in allowed:
        return True
    host = host.lower().strip()
    normalized = {item.lower().strip() for item in allowed}
    return host in normalized


async def host_guard_middleware(request: Request, call_next):
    host = _host_without_port(request.headers.get("host"))
    if not host_allowed(host):
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Host not allowed", "host": host}, status_code=400)
        return PlainTextResponse("Host not allowed", status_code=400)
    return await call_next(request)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    if settings.security_headers_enabled:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def network_status() -> dict:
    return {
        "host": settings.host,
        "port": settings.port,
        "lan_enabled": settings.host in {"0.0.0.0", "::"} or not settings.host.startswith("127."),
        "allowed_hosts": settings.allowed_hosts,
        "security_headers_enabled": settings.security_headers_enabled,
        "session_cookie_secure": settings.session_cookie_secure,
        "session_cookie_same_site": settings.session_cookie_same_site,
        "notes": [
            "Use HOST=127.0.0.1 to disable LAN access.",
            "Set ALLOWED_HOSTS to a comma-separated list when deploying on a stable LAN IP.",
            "Keep SESSION_COOKIE_SECURE=false for plain HTTP LAN testing; set true behind HTTPS.",
        ],
    }
