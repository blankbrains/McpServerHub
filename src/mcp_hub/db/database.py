"""数据库引擎 — 同时支持 PostgreSQL（生产）和 SQLite（quickstart）。"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("MCP_HUB_DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("MCP_HUB_DATABASE_URL 环境变量未设置")

# Automatically select driver based on URL
if DATABASE_URL.startswith("sqlite"):
    _connect_args: dict[str, Any] = {"check_same_thread": False}
    _pool: dict[str, Any] = {"poolclass": NullPool}  # SQLite doesn't need pool
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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（async generator for FastAPI dependencies）。"""
    async with get_session() as session:
        yield session


async def _run_migrations() -> None:
    """运行数据库迁移：添加缺失的列到已有表。"""
    from sqlalchemy import text

    # 检查并添加 reviews.parent_id 列
    async with engine.connect() as conn:
        try:
            # PostgreSQL
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='reviews' AND column_name='parent_id'"
                )
            )
            if not result.fetchone():
                await conn.execute(
                    text(
                        "ALTER TABLE reviews ADD COLUMN parent_id INTEGER "
                        "REFERENCES reviews(id) ON DELETE CASCADE"
                    )
                )
                await conn.commit()
                import structlog

                structlog.get_logger().info("migration.added_parent_id")
        except Exception:
            # SQLite fallback
            try:
                result = await conn.execute(text("PRAGMA table_info(reviews)"))
                cols = [row[1] for row in result.fetchall()]
                if "parent_id" not in cols:
                    await conn.execute(text("ALTER TABLE reviews ADD COLUMN parent_id INTEGER"))
                    await conn.commit()
            except Exception:
                logger.debug("迁移步骤 reviews.parent_id 失败", exc_info=True)

    # 添加 user_servers.enabled 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='user_servers' AND column_name='enabled'"
                )
            )
            if not result.fetchone():
                await conn.execute(
                    text("ALTER TABLE user_servers ADD COLUMN enabled BOOLEAN DEFAULT TRUE")
                )
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(user_servers)"))
                cols = [row[1] for row in result.fetchall()]
                if "enabled" not in cols:
                    await conn.execute(
                        text("ALTER TABLE user_servers ADD COLUMN enabled BOOLEAN DEFAULT TRUE")
                    )
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 user_servers.enabled 失败", exc_info=True)

    # 添加 user_servers.agent 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='user_servers' AND column_name='agent'"
                )
            )
            if not result.fetchone():
                await conn.execute(
                    text("ALTER TABLE user_servers ADD COLUMN agent VARCHAR(50) DEFAULT ''")
                )
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(user_servers)"))
                cols = [row[1] for row in result.fetchall()]
                if "agent" not in cols:
                    await conn.execute(
                        text("ALTER TABLE user_servers ADD COLUMN agent VARCHAR(50) DEFAULT ''")
                    )
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 user_servers.agent 失败", exc_info=True)

    # 添加 usage_stats.user_id 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='usage_stats' AND column_name='user_id'"
                )
            )
            if not result.fetchone():
                await conn.execute(
                    text("ALTER TABLE usage_stats ADD COLUMN user_id VARCHAR(255) DEFAULT ''")
                )
                await conn.execute(
                    text("CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage_stats(user_id)")
                )
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(usage_stats)"))
                cols = [row[1] for row in result.fetchall()]
                if "user_id" not in cols:
                    await conn.execute(
                        text("ALTER TABLE usage_stats ADD COLUMN user_id VARCHAR(255) DEFAULT ''")
                    )
                    await conn.execute(
                        text("CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage_stats(user_id)")
                    )
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 usage_stats.user_id 失败", exc_info=True)

    # 添加 usage_stats.token_count 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='usage_stats' AND column_name='token_count'"
                )
            )
            if not result.fetchone():
                await conn.execute(
                    text("ALTER TABLE usage_stats ADD COLUMN token_count INTEGER DEFAULT 0")
                )
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(usage_stats)"))
                cols = [row[1] for row in result.fetchall()]
                if "token_count" not in cols:
                    await conn.execute(
                        text("ALTER TABLE usage_stats ADD COLUMN token_count INTEGER DEFAULT 0")
                    )
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 usage_stats.token_count 失败", exc_info=True)

    # 添加 install_history.user_id 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='install_history' AND column_name='user_id'"
                )
            )
            if not result.fetchone():
                await conn.execute(
                    text("ALTER TABLE install_history ADD COLUMN user_id VARCHAR(255) DEFAULT ''")
                )
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(install_history)"))
                cols = [row[1] for row in result.fetchall()]
                if "user_id" not in cols:
                    await conn.execute(
                        text(
                            "ALTER TABLE install_history ADD COLUMN user_id VARCHAR(255) DEFAULT ''"
                        )
                    )
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 install_history.user_id 失败", exc_info=True)

    # 添加 usage_stats.created_at 索引
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_usage_created_at ON usage_stats(created_at)")
            )
            await conn.commit()
    except Exception:
        logger.debug("迁移步骤 idx_usage_created_at 索引失败", exc_info=True)

    # 添加 user_servers.group_name 列
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='user_servers' AND column_name='group_name'"
                )
            )
            if not result.fetchone():
                await conn.execute(
                    text("ALTER TABLE user_servers ADD COLUMN group_name VARCHAR(100) DEFAULT ''")
                )
                await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(user_servers)"))
                cols = [row[1] for row in result.fetchall()]
                if "group_name" not in cols:
                    await conn.execute(
                        text(
                            "ALTER TABLE user_servers ADD COLUMN group_name VARCHAR(100) DEFAULT ''"
                        )
                    )
                    await conn.commit()
        except Exception:
            logger.debug("迁移步骤 user_servers.group_name 失败", exc_info=True)

    # 创建 notifications 表（如果不存在）
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text(
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
                )
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_notif_user_id ON notifications(user_id)")
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(user_id, is_read)")
            )
            await conn.commit()
    except Exception:
        # SQLite fallback
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    text(
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
                    )
                )
                await conn.execute(
                    text("CREATE INDEX IF NOT EXISTS idx_notif_user_id ON notifications(user_id)")
                )
                await conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_notif_read "
                        "ON notifications(user_id, is_read)"
                    )
                )
                await conn.commit()
        except Exception:
            logger.debug("迁移步骤 notifications 表失败", exc_info=True)

    # Extend notifications with alert lifecycle fields and create preferences.
    try:
        async with engine.begin() as conn:
            notification_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("notifications")
                }
            )
            notification_column_sql = {
                "alert_rule": "VARCHAR(64) DEFAULT ''",
                "alert_key": "VARCHAR(96)",
                "severity": "VARCHAR(20) DEFAULT 'warning'",
                "status": "VARCHAR(20) DEFAULT 'active'",
                "occurrence_count": "INTEGER DEFAULT 1",
                "first_seen_at": "TIMESTAMP",
                "last_seen_at": "TIMESTAMP",
                "resolved_at": "TIMESTAMP",
                "observed_value": "VARCHAR(255) DEFAULT ''",
            }
            for column_name, column_sql in notification_column_sql.items():
                if column_name not in notification_columns:
                    await conn.execute(
                        text(
                            f"ALTER TABLE notifications ADD COLUMN "
                            f"{column_name} {column_sql}"
                        )
                    )
            await conn.execute(
                text("UPDATE notifications SET alert_key = NULL WHERE alert_key = ''")
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_notifications_user_alert_key "
                    "ON notifications(user_id, alert_key) "
                    "WHERE alert_key IS NOT NULL"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_notifications_status "
                    "ON notifications(user_id, status)"
                )
            )
    except Exception:
        logger.debug("迁移步骤 notifications 告警字段失败", exc_info=True)

    try:
        async with engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                create_preferences_sql = (
                    "CREATE TABLE IF NOT EXISTS alert_preferences ("
                    "id SERIAL PRIMARY KEY, "
                    "user_id VARCHAR(255) NOT NULL, "
                    "rule VARCHAR(64) NOT NULL, "
                    "enabled BOOLEAN NOT NULL DEFAULT TRUE, "
                    "threshold DOUBLE PRECISION NOT NULL, "
                    "updated_at TIMESTAMP DEFAULT NOW(), "
                    "UNIQUE(user_id, rule)"
                    ")"
                )
            else:
                create_preferences_sql = (
                    "CREATE TABLE IF NOT EXISTS alert_preferences ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "user_id TEXT NOT NULL, "
                    "rule TEXT NOT NULL, "
                    "enabled INTEGER NOT NULL DEFAULT 1, "
                    "threshold REAL NOT NULL, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    "UNIQUE(user_id, rule)"
                    ")"
                )
            await conn.execute(text(create_preferences_sql))
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_alert_preferences_user_id "
                    "ON alert_preferences(user_id)"
                )
            )
    except Exception:
        logger.debug("迁移步骤 alert_preferences 表失败", exc_info=True)

    # 创建 presets 表（如果不存在）
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text(
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
                )
            )
            await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    text(
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
                    )
                )
                await conn.commit()
        except Exception:
            logger.debug("迁移步骤 presets 表失败", exc_info=True)

    # 为已存在的遥测设备增加 Agent 类型。历史设备默认归为 generic。
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='telemetry_devices' AND column_name='agent_type'"
                )
            )
            if not result.fetchone():
                await conn.execute(
                    text(
                        "ALTER TABLE telemetry_devices "
                        "ADD COLUMN agent_type VARCHAR(32) NOT NULL DEFAULT 'generic'"
                    )
                )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_telemetry_devices_agent_type "
                    "ON telemetry_devices(agent_type)"
                )
            )
            await conn.commit()
    except Exception:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA table_info(telemetry_devices)"))
                columns = [row[1] for row in result.fetchall()]
                if "agent_type" not in columns:
                    await conn.execute(
                        text(
                            "ALTER TABLE telemetry_devices "
                            "ADD COLUMN agent_type TEXT NOT NULL DEFAULT 'generic'"
                        )
                    )
                await conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS "
                        "ix_telemetry_devices_agent_type "
                        "ON telemetry_devices(agent_type)"
                    )
                )
                await conn.commit()
        except Exception:
            logger.debug(
                "迁移步骤 telemetry_devices.agent_type 失败",
                exc_info=True,
            )

    # 扩展遥测事件字段。新安装由 metadata.create_all 创建，旧数据库在此增量加列。
    telemetry_columns = {
        "session_id": "VARCHAR(64) DEFAULT ''",
        "operation": "VARCHAR(64) DEFAULT ''",
        "error_code": "VARCHAR(64) DEFAULT ''",
        "input_bytes": "INTEGER DEFAULT 0",
        "output_bytes": "INTEGER DEFAULT 0",
        "process_uptime_seconds": "INTEGER",
        "queue_depth": "INTEGER",
        "server_version": "VARCHAR(50) DEFAULT ''",
        "transport": "VARCHAR(32) DEFAULT 'stdio'",
    }
    try:
        async with engine.begin() as conn:
            existing_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("telemetry_events")
                }
            )
            for column_name, column_sql in telemetry_columns.items():
                if column_name not in existing_columns:
                    await conn.execute(
                        text(
                            f"ALTER TABLE telemetry_events "
                            f"ADD COLUMN {column_name} {column_sql}"
                        )
                    )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_telemetry_events_session_id "
                    "ON telemetry_events(session_id)"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_telemetry_events_error_code "
                    "ON telemetry_events(error_code)"
                )
            )
    except Exception:
        logger.debug("迁移步骤 telemetry_events 扩展字段失败", exc_info=True)

    telemetry_device_columns = {
        "gateway_version": "VARCHAR(50) NOT NULL DEFAULT ''",
        "runtime_version": "VARCHAR(50) NOT NULL DEFAULT ''",
        "platform": "VARCHAR(50) NOT NULL DEFAULT ''",
        "architecture": "VARCHAR(50) NOT NULL DEFAULT ''",
        "setup_completed_at": "TIMESTAMP",
        "gateway_first_seen_at": "TIMESTAMP",
        "gateway_last_seen_at": "TIMESTAMP",
        "first_call_at": "TIMESTAMP",
        "last_event_at": "TIMESTAMP",
        "last_queue_depth": "INTEGER",
        "last_error_code": "VARCHAR(64) NOT NULL DEFAULT ''",
    }
    telemetry_inventory_columns = {
        "server_version": "VARCHAR(50) DEFAULT ''",
        "protocol_version": "VARCHAR(32) DEFAULT ''",
        "capabilities": "TEXT DEFAULT '[]'",
        "tool_count": "INTEGER DEFAULT 0",
        "running": "BOOLEAN DEFAULT FALSE",
        "header_keys": "TEXT DEFAULT '[]'",
    }
    try:
        async with engine.begin() as conn:
            device_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("telemetry_devices")
                }
            )
            for column_name, column_sql in telemetry_device_columns.items():
                if column_name not in device_columns:
                    await conn.execute(
                        text(
                            f"ALTER TABLE telemetry_devices "
                            f"ADD COLUMN {column_name} {column_sql}"
                        )
                    )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_telemetry_devices_gateway_last_seen_at "
                    "ON telemetry_devices(gateway_last_seen_at)"
                )
            )

            inventory_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("telemetry_inventory")
                }
            )
            for column_name, column_sql in telemetry_inventory_columns.items():
                if column_name not in inventory_columns:
                    await conn.execute(
                        text(
                            f"ALTER TABLE telemetry_inventory "
                            f"ADD COLUMN {column_name} {column_sql}"
                        )
                    )
    except Exception:
        logger.debug("迁移步骤遥测设备与清单扩展字段失败", exc_info=True)

    # Existing Gateway events are sufficient to reconstruct connection milestones.
    try:
        async with engine.begin() as conn:
            device_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("telemetry_devices")
                }
            )
            event_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("telemetry_events")
                }
            )
            required_device_columns = {
                "id",
                "gateway_first_seen_at",
                "gateway_last_seen_at",
                "first_call_at",
                "last_event_at",
                "last_queue_depth",
                "last_error_code",
            }
            required_event_columns = {
                "device_id",
                "event_type",
                "occurred_at",
                "queue_depth",
                "error_code",
            }
            if required_device_columns <= device_columns and (
                required_event_columns <= event_columns
            ):
                await conn.execute(
                    text(
                        "UPDATE telemetry_devices SET "
                        "gateway_first_seen_at = COALESCE("
                        "gateway_first_seen_at, ("
                        "SELECT MIN(event.occurred_at) "
                        "FROM telemetry_events AS event "
                        "WHERE event.device_id = telemetry_devices.id"
                        ")), "
                        "gateway_last_seen_at = COALESCE("
                        "gateway_last_seen_at, ("
                        "SELECT MAX(event.occurred_at) "
                        "FROM telemetry_events AS event "
                        "WHERE event.device_id = telemetry_devices.id"
                        ")), "
                        "first_call_at = COALESCE(first_call_at, ("
                        "SELECT MIN(event.occurred_at) "
                        "FROM telemetry_events AS event "
                        "WHERE event.device_id = telemetry_devices.id "
                        "AND event.event_type = 'tool_call'"
                        ")), "
                        "last_event_at = COALESCE(last_event_at, ("
                        "SELECT MAX(event.occurred_at) "
                        "FROM telemetry_events AS event "
                        "WHERE event.device_id = telemetry_devices.id"
                        ")), "
                        "last_queue_depth = COALESCE(last_queue_depth, ("
                        "SELECT event.queue_depth "
                        "FROM telemetry_events AS event "
                        "WHERE event.device_id = telemetry_devices.id "
                        "AND event.queue_depth IS NOT NULL "
                        "ORDER BY event.occurred_at DESC LIMIT 1"
                        ")), "
                        "last_error_code = CASE "
                        "WHEN COALESCE(last_error_code, '') <> '' "
                        "THEN last_error_code ELSE COALESCE(("
                        "SELECT event.error_code "
                        "FROM telemetry_events AS event "
                        "WHERE event.device_id = telemetry_devices.id "
                        "AND COALESCE(event.error_code, '') <> '' "
                        "ORDER BY event.occurred_at DESC LIMIT 1"
                        "), '') END"
                    )
                )
    except Exception:
        logger.debug("迁移步骤遥测设备接入状态回填失败", exc_info=True)

    # 将真实 tool_call 遥测幂等投影到兼容的 usage_stats 分析表。
    # 旧版个人中心和管理员统计仍读取该表，因此需要保留历史兼容性。
    try:
        async with engine.begin() as conn:
            usage_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("usage_stats")
                }
            )
            if "source_event_id" not in usage_columns:
                await conn.execute(
                    text(
                        "ALTER TABLE usage_stats "
                        "ADD COLUMN source_event_id VARCHAR(64)"
                    )
                )
                usage_columns.add("source_event_id")
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_usage_stats_source_event_id "
                    "ON usage_stats(source_event_id)"
                )
            )

            telemetry_event_columns = await conn.run_sync(
                lambda sync_conn: {
                    column["name"]
                    for column in inspect(sync_conn).get_columns("telemetry_events")
                }
            )
            required_usage_columns = {
                "server_id",
                "user_id",
                "tool_name",
                "status",
                "duration_ms",
                "token_count",
                "created_at",
                "source_event_id",
            }
            required_event_columns = {
                "id",
                "event_type",
                "server_id",
                "user_id",
                "tool_name",
                "status",
                "duration_ms",
                "input_tokens",
                "output_tokens",
                "occurred_at",
            }
            if required_usage_columns <= usage_columns and (
                required_event_columns <= telemetry_event_columns
            ):
                await conn.execute(
                    text(
                        "INSERT INTO usage_stats "
                        "(server_id, user_id, tool_name, status, duration_ms, "
                        "token_count, created_at, source_event_id) "
                        "SELECT COALESCE(event.server_id, ''), event.user_id, "
                        "COALESCE(event.tool_name, ''), "
                        "COALESCE(event.status, 'ok'), "
                        "COALESCE(event.duration_ms, 0), "
                        "COALESCE(event.input_tokens, 0) + "
                        "COALESCE(event.output_tokens, 0), "
                        "event.occurred_at, event.id "
                        "FROM telemetry_events AS event "
                        "WHERE event.event_type = 'tool_call' "
                        "AND NOT EXISTS ("
                        "SELECT 1 FROM usage_stats AS usage "
                        "WHERE usage.source_event_id = event.id"
                        ")"
                    )
                )
    except Exception:
        logger.debug("迁移步骤 telemetry_events -> usage_stats 投影失败", exc_info=True)


async def init_db() -> None:
    """初始化数据库：创建所有表 + 种子数据。"""
    import mcp_hub.db.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _run_migrations()

    from mcp_hub.db.seed import seed_database

    await seed_database()
