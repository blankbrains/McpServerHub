"""遥测设备、事件入库和本地离线队列回归测试。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete

from mcp_hub.api.routes_telemetry import (
    DeviceCreateRequest,
    TelemetryBatchRequest,
    TelemetryEventInput,
    create_telemetry_device,
    get_telemetry_identity,
    get_telemetry_agents,
    get_telemetry_servers,
    get_telemetry_summary,
    ingest_telemetry_events,
    revoke_telemetry_device,
)
from mcp_hub.cli.agent import agent
from mcp_hub.core.telemetry import TelemetrySpool
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import Base, TelemetryDeviceModel, TelemetryEventModel


async def _prepare_telemetry_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await session.execute(delete(TelemetryEventModel))
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

    assert first["data"] == {"saved": 1, "duplicates": 0}
    assert second["data"] == {"saved": 0, "duplicates": 1}
    assert summary["data"]["total_calls"] == 1
    assert summary["data"]["total_tokens"] == 20
    assert other_summary["data"]["total_calls"] == 0
    assert servers["data"]["servers"][0]["server_id"] == "@example/weather"


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
    claude_identity = await get_telemetry_identity(
        f"Bearer {claude['data']['token']}"
    )
    codex_identity = await get_telemetry_identity(
        f"Bearer {codex['data']['token']}"
    )

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
