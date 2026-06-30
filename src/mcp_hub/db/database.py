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


async def _run_migrations():
    """运行数据库迁移：添加缺失的列到已有表。"""
    from sqlalchemy import text
    from mcp_hub.db.models import ReviewModel

    # 检查并添加 reviews.parent_id 列
    async with engine.connect() as conn:
        try:
            # PostgreSQL
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name='reviews' AND column_name='parent_id'")
            )
            if not result.fetchone():
                await conn.execute(
                    text("ALTER TABLE reviews ADD COLUMN parent_id INTEGER "
                         "REFERENCES reviews(id) ON DELETE CASCADE")
                )
                await conn.commit()
                import structlog
                structlog.get_logger().info("migration.added_parent_id")
        except Exception:
            # SQLite fallback
            try:
                result = await conn.execute(
                    text("PRAGMA table_info(reviews)")
                )
                cols = [row[1] for row in await result.fetchall()]
                if "parent_id" not in cols:
                    await conn.execute(
                        text("ALTER TABLE reviews ADD COLUMN parent_id INTEGER")
                    )
                    await conn.commit()
            except Exception:
                pass  # 表可能已存在该列

    # 添加 user_servers.enabled 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name='user_servers' AND column_name='enabled'")
            )
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE user_servers ADD COLUMN enabled BOOLEAN DEFAULT TRUE"))
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(user_servers)"))
                cols = [row[1] for row in await result.fetchall()]
                if "enabled" not in cols:
                    await conn.execute(text("ALTER TABLE user_servers ADD COLUMN enabled BOOLEAN DEFAULT TRUE"))
                    await conn.commit()
        except Exception:
            pass

    # 添加 user_servers.agent 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name='user_servers' AND column_name='agent'")
            )
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE user_servers ADD COLUMN agent VARCHAR(50) DEFAULT ''"))
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(user_servers)"))
                cols = [row[1] for row in await result.fetchall()]
                if "agent" not in cols:
                    await conn.execute(text("ALTER TABLE user_servers ADD COLUMN agent VARCHAR(50) DEFAULT ''"))
                    await conn.commit()
        except Exception:
            pass

    # 添加 user_servers.group_name 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name='user_servers' AND column_name='group_name'")
            )
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE user_servers ADD COLUMN group_name VARCHAR(100) DEFAULT ''"))
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(user_servers)"))
                cols = [row[1] for row in await result.fetchall()]
                if "group_name" not in cols:
                    await conn.execute(text("ALTER TABLE user_servers ADD COLUMN group_name VARCHAR(100) DEFAULT ''"))
                    await conn.commit()
        except Exception:
            pass


async def init_db():
    """初始化数据库：创建所有表 + 种子数据。"""
    from mcp_hub.db.models import Base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _run_migrations()

    from mcp_hub.db.seed import seed_database
    await seed_database()
