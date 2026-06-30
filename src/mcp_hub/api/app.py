"""MCP Hub API 应用 —— 生产入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from mcp_hub import __version__
from mcp_hub.api.routes_auth import router as auth_router
from mcp_hub.api.routes_builder import router as builder_router
from mcp_hub.api.routes_community import router as community_router
from mcp_hub.api.routes_config import router as config_router
from mcp_hub.api.routes_export import router as export_router
from mcp_hub.api.routes_health import router as health_router
from mcp_hub.api.routes_manage import router as manage_router
from mcp_hub.api.routes_market import router as market_router
from mcp_hub.api.routes_publish import router as publish_router
from mcp_hub.api.routes_realtime import router as realtime_router
from mcp_hub.api.routes_search import router as search_router
from mcp_hub.api.routes_security import router as security_router
from mcp_hub.api.routes_token import router as token_router
from mcp_hub.api.routes_monitor import router as monitor_router
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

    # === Exception Handlers (统一响应格式) ===

    def _error_response(code: str, message: str, status: int = 500, details: dict | None = None) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={
                "success": False,
                "error": {"code": code, "message": message, "details": details},
            },
        )

    @app.exception_handler(McpHubError)
    async def mcp_hub_error_handler(_request: Request, exc: McpHubError):
        return _error_response(
            code=exc.code,
            message=str(exc),
            status=exc.http_status,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        errors = exc.errors()
        return _error_response(
            code="VALIDATION_ERROR",
            message=f"请求参数验证失败: {len(errors)} 个错误",
            status=422,
            details={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
        return _error_response(
            code="HTTP_ERROR",
            message=str(exc.detail),
            status=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(_request: Request, exc: Exception):
        logger.error("api.unhandled_error", error=str(exc), type=type(exc).__name__)
        return _error_response(
            code="INTERNAL_ERROR",
            message="服务器内部错误",
            status=500,
        )

    # === API Routes (优先级最高) ===
    app.include_router(market_router, prefix="/api/v1")
    app.include_router(manage_router, prefix="/api/v1")
    app.include_router(community_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(builder_router, prefix="/api/v1")
    app.include_router(publish_router, prefix="/api/v1")
    app.include_router(realtime_router, prefix="/api/v1")
    app.include_router(config_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(export_router, prefix="/api/v1")
    app.include_router(security_router, prefix="/api/v1")
    app.include_router(token_router, prefix="/api/v1")
    app.include_router(monitor_router, prefix="/api/v1")

    # === Web Dashboard SPA ===
    # 使用统一的 SPA 挂载逻辑
    static_dir = Path(__file__).parent.parent / "web" / "static"
    from mcp_hub.web.app import mount_web_dashboard
    mount_web_dashboard(app, static_dir)

    # 没有前端构建时，提供 JSON 根路径
    if not (static_dir / "index.html").exists():
        @app.get("/")
        async def root():
            return {
                "name": "MCP Server Hub",
                "version": __version__,
                "docs": "/docs",
                "api": "/api/v1",
            }

    return app
