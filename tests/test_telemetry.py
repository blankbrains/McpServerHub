"""遥测设备、事件入库和本地离线队列回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete

from mcp_hub.api.routes_admin import admin_overview
from mcp_hub.api.routes_telemetry import (
    DeviceCreateRequest,
    InventorySnapshotRequest,
    TelemetryBatchRequest,
    TelemetryEventInput,
    create_telemetry_device,
    get_telemetry_agents,
    get_telemetry_errors,
    get_telemetry_identity,
    get_telemetry_inventory,
    get_telemetry_lifecycle,
    get_telemetry_operations,
    get_telemetry_resources,
    get_telemetry_servers,
    get_telemetry_summary,
    get_telemetry_timeseries,
    get_telemetry_tools,
    ingest_telemetry_events,
    ingest_telemetry_inventory,
    revoke_telemetry_device,
)
from mcp_hub.api.routes_usage import get_usage_stats
from mcp_hub.cli.agent import agent
from mcp_hub.core import telemetry
from mcp_hub.core.telemetry import (
    AGENT_TYPE_ENV,
    REPORT_URL_ENV,
    SPOOL_FILENAME,
    STATE_DIR_ENV,
    TELEMETRY_TOKEN_ENV,
    TelemetryReporter,
    TelemetrySpool,
    get_agent_state_dir,
)
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import (
    Base,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UsageStatsModel,
)


async def _prepare_telemetry_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await session.execute(delete(UsageStatsModel))
        await session.execute(delete(TelemetryEventModel))
        await session.execute(delete(TelemetryInventoryModel))
        await session.execute(delete(TelemetryDeviceModel))
        await session.commit()


def _event(event_id: str, server_id: str = "@example/weather") -> TelemetryEventInput:
    return TelemetryEventInput(
        event_id=event_id,
        event_type="tool_call",
        server_id=server_id,
        tool_name="forecast",
        status="ok",
        duration_ms=120,
        input_tokens=12,
        output_tokens=8,
        input_bytes=120,
        output_bytes=80,
        session_id="session-00000001",
        operation="tools/call",
        occurred_at=datetime.now(timezone.utc),
    )


async def test_telemetry_events_are_idempotent_and_user_scoped() -> None:
    await _prepare_telemetry_tables()
    created = await create_telemetry_device(DeviceCreateRequest(name="Developer laptop"), "alice")
    assert created["data"]["device"]["agent_type"] == "generic"
    identity = await get_telemetry_identity(f"Bearer {created['data']['token']}")
    payload = TelemetryBatchRequest(events=[_event("event-id-00000001")])

    first = await ingest_telemetry_events(payload, identity)
    second = await ingest_telemetry_events(payload, identity)
    summary = await get_telemetry_summary(days=7, user_id="alice")
    other_summary = await get_telemetry_summary(days=7, user_id="bob")
    servers = await get_telemetry_servers(days=7, user_id="alice")
    legacy_projection = await get_usage_stats(days=7, user_id="alice")
    admin_projection = await admin_overview(admin_user="admin")

    assert first["data"] == {"saved": 1, "duplicates": 0}
    assert second["data"] == {"saved": 0, "duplicates": 1}
    assert summary["data"]["total_calls"] == 1
    assert summary["data"]["total_tokens"] == 20
    assert summary["data"]["total_bytes"] == 200
    assert summary["data"]["active_sessions"] == 1
    assert summary["data"]["p95_duration_ms"] == 120
    assert other_summary["data"]["total_calls"] == 0
    assert servers["data"]["servers"][0]["server_id"] == "@example/weather"
    assert legacy_projection["data"]["stats"][0]["total_calls"] == 1
    assert legacy_projection["data"]["stats"][0]["total_tokens"] == 20
    assert admin_projection["data"]["stats"]["total_calls"] == 1
    assert admin_projection["data"]["stats"]["total_tokens"] == 20


async def test_telemetry_isolated_and_aggregated_by_agent_type() -> None:
    await _prepare_telemetry_tables()
    claude = await create_telemetry_device(
        DeviceCreateRequest(name="Claude desktop", agent_type="claude-code"),
        "alice",
    )
    codex = await create_telemetry_device(
        DeviceCreateRequest(name="Codex workstation", agent_type="codex"),
        "alice",
    )
    assert claude["data"]["device"]["agent_type"] == "claude-code"
    assert codex["data"]["device"]["agent_type"] == "codex"
    claude_identity = await get_telemetry_identity(f"Bearer {claude['data']['token']}")
    codex_identity = await get_telemetry_identity(f"Bearer {codex['data']['token']}")

    await ingest_telemetry_events(
        TelemetryBatchRequest(events=[_event("agent-event-000001", "@example/claude")]),
        claude_identity,
    )
    await ingest_telemetry_events(
        TelemetryBatchRequest(events=[_event("agent-event-000002", "@example/codex")]),
        codex_identity,
    )

    claude_summary = await get_telemetry_summary(
        days=7,
        agent_type="claude-code",
        user_id="alice",
    )
    codex_servers = await get_telemetry_servers(
        days=7,
        agent_type="codex",
        user_id="alice",
    )
    agents = await get_telemetry_agents(days=7, user_id="alice")
    agent_rows = {row["agent_type"]: row for row in agents["data"]["agents"]}

    assert claude_summary["data"]["total_calls"] == 1
    assert claude_summary["data"]["active_servers"] == 1
    assert [server["server_id"] for server in codex_servers["data"]["servers"]] == [
        "@example/codex"
    ]
    assert agent_rows["claude-code"]["total_calls"] == 1
    assert agent_rows["codex"]["total_calls"] == 1
    assert agent_rows["claude-code"]["device_count"] == 1


async def test_telemetry_agent_filter_rejects_unknown_agent_type() -> None:
    await _prepare_telemetry_tables()

    with pytest.raises(HTTPException) as exc_info:
        await get_telemetry_summary(
            days=7,
            agent_type="unsupported-agent",
            user_id="alice",
        )

    assert exc_info.value.status_code == 422


async def test_revoked_device_token_cannot_upload_events() -> None:
    await _prepare_telemetry_tables()
    created = await create_telemetry_device(DeviceCreateRequest(name="CI agent"), "alice")
    device_id = created["data"]["device"]["id"]
    token = created["data"]["token"]

    await revoke_telemetry_device(device_id, "alice")
    with pytest.raises(HTTPException, match="无效或已撤销"):
        await get_telemetry_identity(f"Bearer {token}")


def test_telemetry_schema_rejects_raw_tool_payloads() -> None:
    with pytest.raises(ValidationError):
        TelemetryEventInput(
            event_id="event-id-00000002",
            event_type="tool_call",
            occurred_at=datetime.now(timezone.utc),
            arguments={"api_key": "secret"},
        )


def test_telemetry_spool_keeps_only_metrics(tmp_path) -> None:
    spool = TelemetrySpool(tmp_path)
    try:
        spool.enqueue(
            {
                "event_id": "event-id-00000003",
                "event_type": "tool_call",
                "server_id": "@example/weather",
                "tool_name": "forecast",
                "input_tokens": 12,
                "output_tokens": 8,
            }
        )
        queued = spool.peek()
    finally:
        spool.close()

    assert queued[0]["input_tokens"] == 12
    assert "arguments" not in queued[0]
    assert "response" not in queued[0]


def test_agent_state_dir_uses_environment_agent_type(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(STATE_DIR_ENV, raising=False)
    monkeypatch.setenv(AGENT_TYPE_ENV, "codex")
    monkeypatch.setattr(telemetry.Path, "home", staticmethod(lambda: tmp_path))

    assert get_agent_state_dir() == tmp_path / ".config" / "mcp-hub" / "codex"


def test_reporter_uses_agent_specific_default_queue(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(STATE_DIR_ENV, raising=False)
    monkeypatch.setenv(AGENT_TYPE_ENV, "claude-code")
    monkeypatch.setenv(REPORT_URL_ENV, "https://hub.example.test")
    monkeypatch.setenv(TELEMETRY_TOKEN_ENV, "mcpht_test-token")
    monkeypatch.setattr(telemetry.Path, "home", staticmethod(lambda: tmp_path))

    reporter = TelemetryReporter.from_environment()
    assert reporter is not None
    try:
        assert reporter.spool.path == (
            tmp_path / ".config" / "mcp-hub" / "claude-code" / SPOOL_FILENAME
        )
    finally:
        reporter.spool.close()


def test_invalid_environment_agent_type_falls_back_to_generic(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(STATE_DIR_ENV, raising=False)
    monkeypatch.setenv(AGENT_TYPE_ENV, "not-supported")
    monkeypatch.setattr(telemetry.Path, "home", staticmethod(lambda: tmp_path))

    assert get_agent_state_dir().name == "generic"


def test_agent_config_outputs_gateway_environment(tmp_path) -> None:
    from click.testing import CliRunner

    result = CliRunner().invoke(
        agent,
        [
            "config",
            "--agent",
            "codex",
            "--hub-url",
            "https://hub.example.test",
            "--telemetry-token",
            "mcpht_test-token",
            "--state-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "MCP_HUB_TELEMETRY_TOKEN" in result.output
    assert "MCP_HUB_AGENT_TYPE" in result.output
    assert "codex" in result.output
    assert "https://hub.example.test" in result.output


async def test_telemetry_exposes_tool_trend_resource_and_error_aggregates() -> None:
    await _prepare_telemetry_tables()
    created = await create_telemetry_device(DeviceCreateRequest(name="Workstation"), "alice")
    identity = await get_telemetry_identity(f"Bearer {created['data']['token']}")
    failed = _event("aggregate-event-0001")
    failed.status = "error"
    failed.error_code = "timeout"
    resource = TelemetryEventInput(
        event_id="aggregate-resource-0001",
        event_type="resource_sample",
        session_id="session-00000001",
        server_id="@example/weather",
        operation="process_sample",
        cpu_percent=25.5,
        memory_bytes=128 * 1024 * 1024,
        process_uptime_seconds=3600,
        occurred_at=datetime.now(timezone.utc),
    )
    await ingest_telemetry_events(
        TelemetryBatchRequest(
            events=[
                _event("aggregate-event-0002"),
                failed,
                resource,
                TelemetryEventInput(
                    event_id="aggregate-protocol-001",
                    event_type="protocol_call",
                    session_id="session-00000001",
                    server_id="@example/weather",
                    operation="resources/read",
                    duration_ms=80,
                    input_bytes=30,
                    output_bytes=100,
                    occurred_at=datetime.now(timezone.utc),
                ),
            ]
        ),
        identity,
    )

    tools = await get_telemetry_tools(days=7, user_id="alice")
    timeseries = await get_telemetry_timeseries(days=7, user_id="alice")
    resources = await get_telemetry_resources(days=7, user_id="alice")
    errors = await get_telemetry_errors(days=7, user_id="alice")
    operations = await get_telemetry_operations(days=7, user_id="alice")

    assert tools["data"]["tools"][0]["total_calls"] == 2
    assert tools["data"]["tools"][0]["success_rate"] == 50.0
    assert timeseries["data"]["points"][0]["error_calls"] == 1
    assert resources["data"]["resources"][0]["max_memory_bytes"] == 128 * 1024 * 1024
    assert resources["data"]["resources"][0]["process_uptime_seconds"] == 3600
    assert errors["data"]["errors"][0]["error_code"] == "timeout"
    assert {row["operation"] for row in operations["data"]["operations"]} == {
        "tools/call",
        "resources/read",
    }


async def test_inventory_is_device_scoped_redacted_and_detects_conflicts() -> None:
    await _prepare_telemetry_tables()
    claude = await create_telemetry_device(
        DeviceCreateRequest(name="Laptop", agent_type="claude-code"),
        "alice",
    )
    codex = await create_telemetry_device(
        DeviceCreateRequest(name="Desktop", agent_type="codex"),
        "alice",
    )
    claude_identity = await get_telemetry_identity(f"Bearer {claude['data']['token']}")
    codex_identity = await get_telemetry_identity(f"Bearer {codex['data']['token']}")
    reported_at = datetime.now(timezone.utc)

    await ingest_telemetry_inventory(
        InventorySnapshotRequest(
            event_id="inventory-event-0001",
            gateway_version="0.2.0",
            runtime_version="3.10.14",
            platform="linux",
            architecture="x86_64",
            reported_at=reported_at,
            servers=[
                {
                    "server_name": "weather",
                    "transport": "stdio",
                    "command_name": "npx",
                    "env_keys": ["WEATHER_API_KEY"],
                    "header_keys": [],
                    "config_hash": "a" * 64,
                    "server_version": "1.0.0",
                    "protocol_version": "2026-07-28",
                    "capabilities": ["tools", "resources"],
                    "tool_count": 7,
                    "running": True,
                    "enabled": True,
                }
            ],
        ),
        claude_identity,
    )
    await ingest_telemetry_inventory(
        InventorySnapshotRequest(
            event_id="inventory-event-0002",
            reported_at=reported_at,
            servers=[
                {
                    "server_name": "weather",
                    "transport": "stdio",
                    "command_name": "uvx",
                    "env_keys": ["WEATHER_API_KEY"],
                    "header_keys": [],
                    "config_hash": "b" * 64,
                    "enabled": True,
                },
                {
                    "server_name": "database",
                    "transport": "streamable-http",
                    "command_name": "",
                    "env_keys": ["DATABASE_URL"],
                    "header_keys": ["Authorization"],
                    "config_hash": "c" * 64,
                    "enabled": False,
                },
            ],
        ),
        codex_identity,
    )

    inventory = await get_telemetry_inventory(user_id="alice")
    other_inventory = await get_telemetry_inventory(user_id="bob")
    serialized = str(inventory)

    assert inventory["data"]["total_devices"] == 2
    assert inventory["data"]["total_unique_servers"] == 2
    assert inventory["data"]["conflicts"][0]["server_name"] == "weather"
    claude_device = next(
        device
        for device in inventory["data"]["devices"]
        if device["agent_type"] == "claude-code"
    )
    assert claude_device["gateway_version"] == "0.2.0"
    assert claude_device["runtime_version"] == "3.10.14"
    assert claude_device["platform"] == "linux"
    assert claude_device["architecture"] == "x86_64"
    assert claude_device["servers"][0]["server_version"] == "1.0.0"
    assert claude_device["servers"][0]["protocol_version"] == "2026-07-28"
    assert claude_device["servers"][0]["capabilities"] == ["resources", "tools"]
    assert claude_device["servers"][0]["tool_count"] == 7
    assert claude_device["servers"][0]["running"] is True
    assert "WEATHER_API_KEY" in serialized
    assert "Authorization" in serialized
    assert "Bearer " not in serialized
    assert "secret" not in serialized
    assert other_inventory["data"]["total_devices"] == 0


async def test_new_inventory_snapshot_marks_removed_servers_inactive() -> None:
    await _prepare_telemetry_tables()
    created = await create_telemetry_device(DeviceCreateRequest(name="Laptop"), "alice")
    identity = await get_telemetry_identity(f"Bearer {created['data']['token']}")
    reported_at = datetime.now(timezone.utc)
    server = {
        "server_name": "weather",
        "command_name": "npx",
        "env_keys": [],
        "config_hash": "d" * 64,
    }

    await ingest_telemetry_inventory(
        InventorySnapshotRequest(
            event_id="inventory-replace-0001",
            reported_at=reported_at,
            servers=[server],
        ),
        identity,
    )
    await ingest_telemetry_inventory(
        InventorySnapshotRequest(
            event_id="inventory-replace-0002",
            reported_at=reported_at,
            servers=[],
        ),
        identity,
    )

    inventory = await get_telemetry_inventory(user_id="alice")
    assert inventory["data"]["total_unique_servers"] == 0


async def test_summary_reports_online_devices_queue_depth_and_lifecycle() -> None:
    await _prepare_telemetry_tables()
    created = await create_telemetry_device(DeviceCreateRequest(name="Laptop"), "alice")
    identity = await get_telemetry_identity(f"Bearer {created['data']['token']}")
    now = datetime.now(timezone.utc)
    await ingest_telemetry_events(
        TelemetryBatchRequest(
            events=[
                TelemetryEventInput(
                    event_id="queue-heartbeat-0001",
                    event_type="heartbeat",
                    session_id="session-queue-0001",
                    queue_depth=4,
                    occurred_at=now,
                ),
                TelemetryEventInput(
                    event_id="lifecycle-exit-0001",
                    event_type="server_lifecycle",
                    session_id="session-queue-0001",
                    server_id="weather",
                    operation="exited",
                    status="error",
                    error_code="exit_code_9",
                    server_version="1.0.0",
                    queue_depth=0,
                    occurred_at=now + timedelta(seconds=1),
                ),
            ]
        ),
        identity,
    )

    summary = await get_telemetry_summary(days=7, user_id="alice")
    lifecycle = await get_telemetry_lifecycle(days=7, user_id="alice")

    assert summary["data"]["active_devices"] == 1
    assert summary["data"]["current_queue_depth"] == 0
    assert summary["data"]["max_queue_depth"] == 4
    assert lifecycle["data"]["events"][0] == {
        "server_id": "weather",
        "operation": "exited",
        "status": "error",
        "duration_ms": 0,
        "error_code": "exit_code_9",
        "server_version": "1.0.0",
        "occurred_at": (now + timedelta(seconds=1)).replace(tzinfo=None).isoformat(),
    }
