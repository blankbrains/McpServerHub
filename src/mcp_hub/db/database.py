"""数据库引擎 — 同时支持 PostgreSQL（生产）和 SQLite（quickstart）。"""

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
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get("MCP_HUB_DATABASE_URL")

# Automatically select driver based on URL
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    _pool = {"poolclass": NullPool}  # SQLite doesn't need pool
else:
    _connect_args = {}
    _pool = {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True, "pool_recycle": 3600}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    **_pool,
    connect_args=_connect_args,
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
    """初始化数据库：创建所有表 + 种子数据。"""
    from mcp_hub.db.models import Base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from mcp_hub.db.seed import seed_database
    await seed_database()
