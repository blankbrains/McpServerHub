"""MCP Hub API 应用 —— 生产入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mcp_hub import __version__
from mcp_hub.api.routes_auth import router as auth_router
from mcp_hub.api.routes_builder import router as builder_router
from mcp_hub.api.routes_community import router as community_router
from mcp_hub.api.routes_config import router as config_router
from mcp_hub.api.routes_export import router as export_router
from mcp_hub.api.routes_health import router as health_router
from mcp_hub.api.routes_manage import router as manage_router
from mcp_hub.api.routes_market import router as market_router
from mcp_hub.api.routes_realtime import router as realtime_router
from mcp_hub.api.routes_search import router as search_router
from mcp_hub.api.routes_security import router as security_router
from mcp_hub.api.routes_token import router as token_router
from mcp_hub.config import get_settings
from mcp_hub.exceptions import McpHubError
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("db.initializing")
    try:
        from mcp_hub.db.database import init_db
        await init_db()
        logger.info("db.initialized")
    except Exception as e:
        logger.error("db.init_failed", error=str(e))
        raise
    yield
    logger.info("app.shutting_down")


def create_app(dev: bool = False) -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="MCP Server Hub",
        version=__version__,
        description="MCP 生态的一站式管理平台 —— 发现 · 安装 · 管理 · 发布 · 社区",
        lifespan=lifespan,
        docs_url="/docs" if dev else None,
        redoc_url="/redoc" if dev else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # === Exception Handler ===
    @app.exception_handler(McpHubError)
    async def mcp_hub_error_handler(_request: Request, exc: McpHubError):
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "details": exc.details,
                },
            },
        )

    # === API Routes (优先级最高) ===
    app.include_router(market_router, prefix="/api/v1")
    app.include_router(manage_router, prefix="/api/v1")
    app.include_router(community_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(builder_router, prefix="/api/v1")
    app.include_router(realtime_router, prefix="/api/v1")
    app.include_router(config_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(export_router, prefix="/api/v1")
    app.include_router(security_router, prefix="/api/v1")
    app.include_router(token_router, prefix="/api/v1")

    # === Web Dashboard SPA ===
    # 所有非 API 路径都返回 index.html，让 React Router 处理
    static_dir = Path(__file__).parent.parent / "web" / "static"
    index_html = static_dir / "index.html" if static_dir.exists() else None

    if index_html and index_html.exists():
        # 挂载 assets 静态资源
        app.mount(
            "/assets",
            StaticFiles(directory=str(static_dir / "assets")),
            name="web_assets",
        )

        # 根目录静态文件
        _static_root_files = {}
        for _f in ["favicon.svg", "favicon.ico", "logo.svg"]:
            _p = static_dir / _f
            if _p.exists():
                _static_root_files[_f] = _p

        @app.get("/favicon.svg")
        async def favicon_svg():
            if "favicon.svg" in _static_root_files:
                return FileResponse(str(_static_root_files["favicon.svg"]))
            return FileResponse(str(index_html))

        @app.get("/logo.svg")
        async def logo_svg():
            if "logo.svg" in _static_root_files:
                return FileResponse(str(_static_root_files["logo.svg"]))
            return FileResponse(str(index_html))

        @app.api_route("/{path:path}", methods=["GET"])
        async def serve_spa(path: str):
            # 根静态文件
            if path in _static_root_files:
                return FileResponse(str(_static_root_files[path]))
            # SPA 回退
            return FileResponse(str(index_html))

    else:
        # 没有前端时返回 JSON
        @app.get("/")
        async def root():
            return {
                "name": "MCP Server Hub",
                "version": __version__,
                "docs": "/docs",
                "api": "/api/v1",
            }

    return app
