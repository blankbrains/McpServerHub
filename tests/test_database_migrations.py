"""Regression tests for SQLite upgrades and seed result reporting."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mcp_hub.db import database as database_module
from mcp_hub.db import seed as seed_module
from mcp_hub.db.models import ServerModel


async def test_sqlite_migrations_add_all_legacy_columns(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}")
    legacy_schema = (
        "CREATE TABLE reviews (id INTEGER PRIMARY KEY)",
        "CREATE TABLE user_servers (id INTEGER PRIMARY KEY)",
        "CREATE TABLE usage_stats (id INTEGER PRIMARY KEY, created_at TIMESTAMP)",
        "CREATE TABLE install_history (id INTEGER PRIMARY KEY)",
        "CREATE TABLE telemetry_devices (id TEXT PRIMARY KEY)",
        "CREATE TABLE telemetry_events (id TEXT PRIMARY KEY)",
        "CREATE TABLE telemetry_inventory (id INTEGER PRIMARY KEY)",
    )
    async with engine.begin() as connection:
        for statement in legacy_schema:
            await connection.execute(text(statement))

    monkeypatch.setattr(database_module, "engine", engine)
    try:
        await database_module._run_migrations()

        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: {
                    table: {
                        column["name"]
                        for column in inspect(sync_connection).get_columns(table)
                    }
                    for table in (
                        "reviews",
                        "user_servers",
                        "usage_stats",
                        "install_history",
                        "telemetry_devices",
                        "telemetry_events",
                        "telemetry_inventory",
                    )
                }
            )
    finally:
        await engine.dispose()

    assert "parent_id" in columns["reviews"]
    assert {"enabled", "agent", "group_name"} <= columns["user_servers"]
    assert {"user_id", "token_count", "source_event_id"} <= columns["usage_stats"]
    assert "user_id" in columns["install_history"]
    assert "agent_type" in columns["telemetry_devices"]
    assert {
        "gateway_version",
        "runtime_version",
        "platform",
        "architecture",
    } <= columns["telemetry_devices"]
    assert {
        "session_id",
        "operation",
        "error_code",
        "input_bytes",
        "output_bytes",
        "process_uptime_seconds",
        "queue_depth",
        "server_version",
        "transport",
    } <= columns["telemetry_events"]
    assert {
        "server_version",
        "protocol_version",
        "capabilities",
        "tool_count",
        "running",
        "header_keys",
    } <= columns["telemetry_inventory"]


async def test_seed_database_returns_inserted_count(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(ServerModel.__table__.create)

    monkeypatch.setattr(seed_module, "async_session_factory", factory)
    try:
        first = await seed_module.seed_database()
        second = await seed_module.seed_database()
    finally:
        await engine.dispose()

    assert first == len(seed_module.REAL_MCP_SERVERS)
    assert second == 0


async def test_sqlite_migration_backfills_tool_call_usage_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'projection.db'}")
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE usage_stats ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "server_id TEXT NOT NULL, user_id TEXT, tool_name TEXT, "
                "status TEXT, duration_ms INTEGER, token_count INTEGER, "
                "created_at TIMESTAMP)"
            )
        )
        await connection.execute(
            text(
                "CREATE TABLE telemetry_events ("
                "id TEXT PRIMARY KEY, event_type TEXT NOT NULL, "
                "server_id TEXT, user_id TEXT NOT NULL, tool_name TEXT, "
                "status TEXT, duration_ms INTEGER, input_tokens INTEGER, "
                "output_tokens INTEGER, occurred_at TIMESTAMP)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO telemetry_events "
                "(id, event_type, server_id, user_id, tool_name, status, "
                "duration_ms, input_tokens, output_tokens, occurred_at) "
                "VALUES "
                "('tool-event', 'tool_call', '@example/weather', 'alice', "
                "'forecast', 'ok', 120, 12, 8, CURRENT_TIMESTAMP), "
                "('heartbeat-event', 'heartbeat', '', 'alice', '', "
                "'ok', 0, 0, 0, CURRENT_TIMESTAMP)"
            )
        )

    monkeypatch.setattr(database_module, "engine", engine)
    try:
        await database_module._run_migrations()
        await database_module._run_migrations()
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT source_event_id, server_id, user_id, token_count "
                        "FROM usage_stats"
                    )
                )
            ).fetchall()
    finally:
        await engine.dispose()

    assert rows == [("tool-event", "@example/weather", "alice", 20)]
