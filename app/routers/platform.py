from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from .. import platform_api, platform_diagnostics, platform_migrations, platform_plugins, platform_routes, platform_storage
from ..platform_route_registry import route_ownership_registry


def create_platform_router(
    *,
    templates: Jinja2Templates,
    context_factory: Callable[[Request, str], dict[str, Any]],
    app_provider: Callable[[], Any],
) -> APIRouter:
    """Build the extracted v4 platform router without importing app.main."""

    router = APIRouter(tags=["v4-platform"])

    @router.get("/v3/platform", response_class=HTMLResponse)
    @router.get("/v3/platform/health", response_class=HTMLResponse)
    @router.get("/v3/platform/routes", response_class=HTMLResponse)
    @router.get("/v3/platform/schema", response_class=HTMLResponse)
    @router.get("/v3/platform/plugins", response_class=HTMLResponse)
    @router.get("/v3/platform/storage", response_class=HTMLResponse)
    @router.get("/v3/platform/migrations", response_class=HTMLResponse)
    @router.get("/v3/platform/migrations/plan", response_class=HTMLResponse)
    @router.get("/v3/platform/migrations/storage-map", response_class=HTMLResponse)
    @router.get("/v3/platform/diagnostics", response_class=HTMLResponse)
    @router.get("/v3/platform/exports", response_class=HTMLResponse)
    @router.get("/v3/platform/settings", response_class=HTMLResponse)
    async def v3_platform_page(request: Request):
        return templates.TemplateResponse("live_v3_dashboard.html", context_factory(request, "platform"))

    @router.get("/api/v3/platform/summary")
    async def api_v3_platform_summary():
        return platform_diagnostics.platform_summary(app_provider())

    @router.get("/api/v3/platform/health")
    async def api_v3_platform_health():
        return platform_diagnostics.health_summary(app_provider())

    @router.get("/api/v3/platform/routes")
    async def api_v3_platform_routes():
        return platform_routes.route_inventory(app_provider())

    @router.get("/api/v3/platform/route-registry")
    async def api_v3_platform_route_registry():
        return route_ownership_registry(app_provider())

    @router.get("/api/v3/platform/routes/export.json", response_class=PlainTextResponse)
    async def api_v3_platform_routes_export_json():
        return PlainTextResponse(json.dumps(platform_routes.export_route_boundary_json(app_provider()), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/platform/routes/export.md", response_class=PlainTextResponse)
    async def api_v3_platform_routes_export_md():
        return PlainTextResponse(platform_routes.export_route_boundary_markdown(app_provider()), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/platform/schema")
    async def api_v3_platform_schema():
        return platform_api.summarize_api_schema_consistency(app_provider())

    @router.get("/api/v3/platform/schema/families")
    async def api_v3_platform_schema_families():
        return platform_api.list_api_families()

    @router.get("/api/v3/platform/schema/envelopes")
    async def api_v3_platform_schema_envelopes():
        return platform_api.list_response_envelopes()

    @router.get("/api/v3/platform/schema/objects")
    async def api_v3_platform_schema_objects():
        return platform_api.list_known_schema_objects()

    @router.get("/api/v3/platform/schema/export.json", response_class=PlainTextResponse)
    async def api_v3_platform_schema_export_json():
        return PlainTextResponse(json.dumps(platform_api.export_schema_inventory_json(app_provider()), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/platform/schema/export.md", response_class=PlainTextResponse)
    async def api_v3_platform_schema_export_md():
        return PlainTextResponse(platform_api.export_schema_inventory_markdown(app_provider()), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/platform/plugins")
    async def api_v3_platform_plugins():
        return platform_plugins.load_plugin_manifests()

    @router.get("/api/v3/platform/storage")
    async def api_v3_platform_storage():
        return platform_storage.storage_summary()

    @router.get("/api/v3/platform/storage/export.json", response_class=PlainTextResponse)
    async def api_v3_platform_storage_export_json():
        return PlainTextResponse(json.dumps(platform_migrations.export_storage_compatibility_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/platform/storage/export.md", response_class=PlainTextResponse)
    async def api_v3_platform_storage_export_md():
        return PlainTextResponse(platform_migrations.export_storage_compatibility_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/platform/migrations/summary")
    async def api_v3_platform_migrations_summary():
        return platform_migrations.migration_summary()

    @router.get("/api/v3/platform/migrations/plan")
    async def api_v3_platform_migrations_plan():
        return platform_migrations.migration_plan()

    @router.get("/api/v3/platform/migrations/storage-map")
    async def api_v3_platform_migrations_storage_map():
        return platform_migrations.storage_map()

    @router.get("/api/v3/platform/migrations/export.json", response_class=PlainTextResponse)
    async def api_v3_platform_migrations_export_json():
        return PlainTextResponse(json.dumps(platform_migrations.export_migration_plan_json(), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/platform/migrations/export.md", response_class=PlainTextResponse)
    async def api_v3_platform_migrations_export_md():
        return PlainTextResponse(platform_migrations.export_migration_plan_markdown(), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/platform/diagnostics")
    async def api_v3_platform_diagnostics():
        return platform_diagnostics.diagnostics_summary(app_provider())

    @router.get("/api/v3/platform/export.json", response_class=PlainTextResponse)
    async def api_v3_platform_export_json():
        return PlainTextResponse(json.dumps(platform_diagnostics.export_json(app_provider()), indent=2, sort_keys=True, default=str), media_type="application/json; charset=utf-8")

    @router.get("/api/v3/platform/export.md", response_class=PlainTextResponse)
    async def api_v3_platform_export_md():
        return PlainTextResponse(platform_diagnostics.export_markdown(app_provider()), media_type="text/markdown; charset=utf-8")

    @router.get("/api/v3/platform/settings")
    async def api_v3_platform_settings_get():
        return platform_diagnostics.build_settings()

    @router.post("/api/v3/platform/settings")
    async def api_v3_platform_settings_post(payload: dict[str, Any] = Body(default_factory=dict)):
        return platform_diagnostics.update_settings(payload)

    return router
