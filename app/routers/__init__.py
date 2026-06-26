"""Modular FastAPI routers introduced for v4.3 platform extraction."""

from .platform import create_platform_router
from .v3_core import create_v3_core_router
from .ai import create_ai_router

__all__ = ["create_platform_router", "create_v3_core_router", "create_ai_router"]
