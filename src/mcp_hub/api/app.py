"""MCP Hub API 应用 —— 生产入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mcp_hub import __version__
from mcp_hub.config import get_settings
from mcp_hub.api.routes_market import router as market_router
from mcp_hub.api.routes_manage import router as manage_router
from mcp_hub.api.routes_community import router as community_router
from mcp_hub.api.routes_health import router as health_router
from mcp_hub.api.routes_auth import router as auth_router
from mcp_hub.api.routes_realtime import router as realtime_router

logger = logging.getLogger("mcp_hub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    logger.info("Initializing database...")
    try:
        from mcp_hub.db.database import init_db
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    yield
    logger.info("Shutting down...")


def create_app(dev: bool = False) -> FastAPI:
    """创建 FastAPI 应用（生产入口）。"""
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

    # Routes
    app.include_router(market_router, prefix="/api/v1")
    app.include_router(manage_router, prefix="/api/v1")
    app.include_router(community_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(realtime_router, prefix="/api/v1")

    # Web static files
    static_dir = Path(__file__).parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="web")

    @app.get("/")
    async def root():
        return {
            "name": "MCP Server Hub",
            "version": __version__,
            "docs": "/docs",
            "api": "/api/v1",
        }

    return app
