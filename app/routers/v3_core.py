from __future__ import annotations

from fastapi import APIRouter

from ..live_v3 import design_system_status, navigation_groups, ux_release_status


def create_v3_core_router() -> APIRouter:
    """Small low-risk v3 API router extracted in v4.3."""

    router = APIRouter(tags=["v3-core"])

    @router.get("/api/v3/ux/status")
    async def api_v3_ux_status():
        return ux_release_status()

    @router.get("/api/v3/ux/design-system")
    async def api_v3_ux_design_system():
        return design_system_status()

    @router.get("/api/v3/ux/navigation")
    async def api_v3_ux_navigation():
        return navigation_groups()

    return router
