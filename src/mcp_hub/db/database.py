"""PostgreSQL 异步数据库引擎 — 生产配置。"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get(
    "MCP_HUB_DATABASE_URL",
    "postgresql+asyncpg://mcp_hub:mcp_hub_prod_2026@localhost:5432/mcp_hub",
)

# Production connection pool settings
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（上下文管理器）。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db():
    """获取异步数据库会话（async generator for FastAPI dependencies）。"""
    async with get_session() as session:
        yield session


async def init_db():
    """初始化数据库：创建所有表。"""
    from mcp_hub.db.models import Base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default data
    from mcp_hub.db.seed import seed_database
    await seed_database()
