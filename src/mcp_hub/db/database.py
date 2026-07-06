"""数据库引擎 — 同时支持 PostgreSQL（生产）和 SQLite（quickstart）。"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get("MCP_HUB_DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("MCP_HUB_DATABASE_URL 环境变量未设置")

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
                logger.debug("迁移步骤 reviews.parent_id 失败", exc_info=True)

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
            logger.debug("迁移步骤 user_servers.enabled 失败", exc_info=True)

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
            logger.debug("迁移步骤 user_servers.agent 失败", exc_info=True)

    # 添加 usage_stats.user_id 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name='usage_stats' AND column_name='user_id'")
            )
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE usage_stats ADD COLUMN user_id VARCHAR(255) DEFAULT ''"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage_stats(user_id)"))
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(usage_stats)"))
                cols = [row[1] for row in await result.fetchall()]
                if "user_id" not in cols:
                    await conn.execute(text("ALTER TABLE usage_stats ADD COLUMN user_id VARCHAR(255) DEFAULT ''"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage_stats(user_id)"))
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 usage_stats.user_id 失败", exc_info=True)

    # 添加 usage_stats.token_count 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name='usage_stats' AND column_name='token_count'")
            )
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE usage_stats ADD COLUMN token_count INTEGER DEFAULT 0"))
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(usage_stats)"))
                cols = [row[1] for row in await result.fetchall()]
                if "token_count" not in cols:
                    await conn.execute(text("ALTER TABLE usage_stats ADD COLUMN token_count INTEGER DEFAULT 0"))
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 usage_stats.token_count 失败", exc_info=True)

    # 添加 install_history.user_id 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name='install_history' AND column_name='user_id'")
            )
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE install_history ADD COLUMN user_id VARCHAR(255) DEFAULT ''"))
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(install_history)"))
                cols = [row[1] for row in await result.fetchall()]
                if "user_id" not in cols:
                    await conn.execute(text("ALTER TABLE install_history ADD COLUMN user_id VARCHAR(255) DEFAULT ''"))
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 install_history.user_id 失败", exc_info=True)

    # 添加 usage_stats.created_at 索引
    try:
        async with engine.connect() as conn:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_usage_created_at ON usage_stats(created_at)"))
            await conn.commit()
    except Exception:
        logger.debug("迁移步骤 idx_usage_created_at 索引失败", exc_info=True)

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
            logger.debug("迁移步骤 user_servers.group_name 失败", exc_info=True)


    # 创建 notifications 表（如果不存在）
    try:
        async with engine.connect() as conn:
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS notifications ("
                "id SERIAL PRIMARY KEY, "
                "user_id VARCHAR(255) NOT NULL, "
                "type VARCHAR(50) NOT NULL, "
                "title VARCHAR(255) NOT NULL, "
                "message TEXT DEFAULT '', "
                "server_id VARCHAR(255) DEFAULT '', "
                "link VARCHAR(500) DEFAULT '', "
                "is_read BOOLEAN DEFAULT FALSE, "
                "created_at TIMESTAMP DEFAULT NOW()"
                ")"
            ))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notif_user_id ON notifications(user_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(user_id, is_read)"))
            await conn.commit()
    except Exception:
        # SQLite fallback
        try:
            async with engine.connect() as conn:
                await conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS notifications ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "user_id TEXT NOT NULL, "
                    "type TEXT NOT NULL, "
                    "title TEXT NOT NULL, "
                    "message TEXT DEFAULT '', "
                    "server_id TEXT DEFAULT '', "
                    "link TEXT DEFAULT '', "
                    "is_read INTEGER DEFAULT 0, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                ))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notif_user_id ON notifications(user_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(user_id, is_read)"))
                await conn.commit()
        except Exception:
            logger.debug("迁移步骤 notifications 表失败", exc_info=True)


    # 创建 presets 表（如果不存在）
    try:
        async with engine.connect() as conn:
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS presets ("
                "id SERIAL PRIMARY KEY, "
                "user_id VARCHAR(255) NOT NULL, "
                "name VARCHAR(255) NOT NULL, "
                "description TEXT DEFAULT '', "
                "tags VARCHAR(500) DEFAULT '', "
                "servers TEXT NOT NULL, "
                "download_count INTEGER DEFAULT 0, "
                "rating FLOAT DEFAULT 0.0, "
                "created_at TIMESTAMP DEFAULT NOW(), "
                "updated_at TIMESTAMP DEFAULT NOW()"
                ")"
            ))
            await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                await conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS presets ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "user_id TEXT NOT NULL, "
                    "name TEXT NOT NULL, "
                    "description TEXT DEFAULT '', "
                    "tags TEXT DEFAULT '', "
                    "servers TEXT NOT NULL, "
                    "download_count INTEGER DEFAULT 0, "
                    "rating REAL DEFAULT 0.0, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                ))
                await conn.commit()
        except Exception:
            logger.debug("迁移步骤 presets 表失败", exc_info=True)


async def init_db():
    """初始化数据库：创建所有表 + 种子数据。"""
    from mcp_hub.db.models import Base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _run_migrations()

    from mcp_hub.db.seed import seed_database
    await seed_database()
