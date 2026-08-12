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
        "setup_completed_at",
        "gateway_first_seen_at",
        "gateway_last_seen_at",
        "first_call_at",
        "last_event_at",
        "last_queue_depth",
        "last_error_code",
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


async def test_sqlite_migration_adds_alert_lifecycle_without_colliding_notifications(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'alerts.db'}")
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE notifications ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id TEXT NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL, "
                "message TEXT DEFAULT '', server_id TEXT DEFAULT '', link TEXT DEFAULT '', "
                "is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO notifications (user_id, type, title) VALUES "
                "('alice', 'system', 'First'), ('alice', 'system', 'Second')"
            )
        )

    monkeypatch.setattr(database_module, "engine", engine)
    try:
        await database_module._run_migrations()
        await database_module._run_migrations()
        async with engine.connect() as connection:
            columns = {
                column["name"]
                for column in await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_columns(
                        "notifications"
                    )
                )
            }
            rows = (
                await connection.execute(
                    text(
                        "SELECT alert_key, status, occurrence_count "
                        "FROM notifications ORDER BY id"
                    )
                )
            ).fetchall()
            preferences_exists = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).has_table(
                    "alert_preferences"
                )
            )
    finally:
        await engine.dispose()

    assert {
        "alert_rule",
        "alert_key",
        "severity",
        "status",
        "occurrence_count",
        "first_seen_at",
        "last_seen_at",
        "resolved_at",
        "observed_value",
    } <= columns
    assert rows == [(None, "active", 1), (None, "active", 1)]
    assert preferences_exists is True


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


async def test_sqlite_migration_backfills_existing_device_connection_milestones(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'connection.db'}")
    legacy_schema = (
        "CREATE TABLE reviews (id INTEGER PRIMARY KEY)",
        "CREATE TABLE user_servers (id INTEGER PRIMARY KEY)",
        "CREATE TABLE usage_stats (id INTEGER PRIMARY KEY, created_at TIMESTAMP)",
        "CREATE TABLE install_history (id INTEGER PRIMARY KEY)",
        "CREATE TABLE telemetry_devices (id TEXT PRIMARY KEY)",
        (
            "CREATE TABLE telemetry_events ("
            "id TEXT PRIMARY KEY, device_id TEXT, event_type TEXT, "
            "occurred_at TIMESTAMP, received_at TIMESTAMP, "
            "queue_depth INTEGER, error_code TEXT)"
        ),
        "CREATE TABLE telemetry_inventory (id INTEGER PRIMARY KEY)",
    )
    async with engine.begin() as connection:
        for statement in legacy_schema:
            await connection.execute(text(statement))
        await connection.execute(
            text("INSERT INTO telemetry_devices (id) VALUES ('existing-device')")
        )
        await connection.execute(
            text(
                "INSERT INTO telemetry_events "
                "(id, device_id, event_type, occurred_at, received_at, "
                "queue_depth, error_code) VALUES "
                "('heartbeat', 'existing-device', 'heartbeat', "
                "'2026-08-11 08:00:00', '2026-08-11 08:00:01', 3, ''), "
                "('tool-call', 'existing-device', 'tool_call', "
                "'2026-08-11 08:01:00', '2026-08-11 08:01:01', 0, 'timeout')"
            )
        )

    monkeypatch.setattr(database_module, "engine", engine)
    try:
        await database_module._run_migrations()
        await database_module._run_migrations()
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT gateway_first_seen_at, gateway_last_seen_at, "
                        "first_call_at, last_event_at, last_queue_depth, "
                        "last_error_code FROM telemetry_devices "
                        "WHERE id = 'existing-device'"
                    )
                )
            ).one()
    finally:
        await engine.dispose()

    assert str(row.gateway_first_seen_at).startswith("2026-08-11 08:00:00")
    assert str(row.gateway_last_seen_at).startswith("2026-08-11 08:01:00")
    assert str(row.first_call_at).startswith("2026-08-11 08:01:00")
    assert str(row.last_event_at).startswith("2026-08-11 08:01:00")
    assert row.last_queue_depth == 0
    assert row.last_error_code == "timeout"


async def test_sqlite_migration_adds_registry_source_columns_idempotently(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}")
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE servers ("
                "id TEXT PRIMARY KEY, name TEXT NOT NULL, "
                "description TEXT DEFAULT '')"
            )
        )

    monkeypatch.setattr(database_module, "engine", engine)
    try:
        await database_module._run_migrations()
        await database_module._run_migrations()
        async with engine.connect() as connection:
            columns = {
                column["name"]
                for column in await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_columns("servers")
                )
            }
            registry_tables = {
                table
                for table in await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_table_names()
                )
                if table in {"registry_source_states", "registry_source_entries"}
            }
    finally:
        await engine.dispose()

    assert {
        "catalog_source",
        "catalog_source_id",
        "catalog_status",
        "market_visible",
    } <= columns
    assert registry_tables == {"registry_source_states", "registry_source_entries"}
