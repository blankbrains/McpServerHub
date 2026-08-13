"""仪表盘数据隔离和配置下载回归测试。"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from mcp_hub import __version__
from mcp_hub.api.routes_config import download_config, generate_config
from mcp_hub.api.routes_export import export_config, export_telemetry_report
from mcp_hub.api.routes_export import router as export_router
from mcp_hub.api.routes_manage import download_all_config
from mcp_hub.api.routes_monitor import monitor_dashboard
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import (
    Base,
    ServerModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UserServerModel,
)

_ALICE_SERVER = "@test-dashboard/alice-private"
_BOB_SERVER = "@test-dashboard/bob-private"
_PUBLIC_SERVER = "@test-dashboard/public-installed"
_CUSTOM_SERVER = "@custom/dashboard-private"


async def _prepare_dashboard_data() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        server_ids = [_ALICE_SERVER, _BOB_SERVER, _PUBLIC_SERVER, _CUSTOM_SERVER]
        await session.execute(
            delete(TelemetryEventModel).where(TelemetryEventModel.server_id.in_(server_ids))
        )
        await session.execute(
            delete(TelemetryInventoryModel).where(
                TelemetryInventoryModel.server_name.in_(server_ids)
            )
        )
        await session.execute(
            delete(TelemetryDeviceModel).where(
                TelemetryDeviceModel.id.in_(["dashboard-alice-device", "dashboard-bob-device"])
            )
        )
        await session.execute(
            delete(UserServerModel).where(UserServerModel.server_id.in_(server_ids))
        )
        await session.execute(delete(ServerModel).where(ServerModel.id.in_(server_ids)))
        session.add_all(
            [
                ServerModel(
                    id=_ALICE_SERVER,
                    name="alice-private",
                    description="Alice private server",
                    install_command="npx alice-private",
                    status="not_installed",
                ),
                ServerModel(
                    id=_BOB_SERVER,
                    name="bob-private",
                    description="Bob private server",
                    install_command="npx bob-private",
                    status="not_installed",
                ),
                ServerModel(
                    id=_PUBLIC_SERVER,
                    name="public-installed",
                    description="Self-hosted server",
                    install_command="npx public-installed",
                    status="running",
                ),
                ServerModel(
                    id=_CUSTOM_SERVER,
                    name="dashboard-private",
                    description="Private custom server",
                    install_command="npx dashboard-private",
                    status="running",
                ),
                UserServerModel(user_id="dashboard-alice", server_id=_ALICE_SERVER),
                UserServerModel(
                    user_id="dashboard-alice",
                    server_id=_PUBLIC_SERVER,
                    enabled=False,
                ),
                UserServerModel(user_id="dashboard-bob", server_id=_BOB_SERVER),
                TelemetryDeviceModel(
                    id="dashboard-alice-device",
                    user_id="dashboard-alice",
                    name="Alice Codex",
                    agent_type="codex",
                    token_hash="a" * 64,
                    last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
                TelemetryDeviceModel(
                    id="dashboard-bob-device",
                    user_id="dashboard-bob",
                    name="Bob Codex",
                    agent_type="codex",
                    token_hash="b" * 64,
                    last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
                TelemetryInventoryModel(
                    user_id="dashboard-alice",
                    device_id="dashboard-alice-device",
                    server_name=_ALICE_SERVER,
                    config_hash="c" * 64,
                    running=True,
                    discovered_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
                TelemetryEventModel(
                    id="dashboard-alice-event",
                    user_id="dashboard-alice",
                    device_id="dashboard-alice-device",
                    event_type="tool_call",
                    server_id=_ALICE_SERVER,
                    tool_name="search",
                    status="ok",
                    input_tokens=3,
                    output_tokens=2,
                    occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
                TelemetryEventModel(
                    id="dashboard-bob-event",
                    user_id="dashboard-bob",
                    device_id="dashboard-bob-device",
                    event_type="tool_call",
                    server_id=_ALICE_SERVER,
                    tool_name="search",
                    status="ok",
                    input_tokens=100,
                    output_tokens=100,
                    occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
            ]
        )
        await session.commit()


async def test_monitor_dashboard_scopes_tracked_servers_and_usage_to_current_user() -> None:
    await _prepare_dashboard_data()

    alice_result = await monitor_dashboard(user_id="dashboard-alice")
    anonymous_result = await monitor_dashboard(user_id=None)

    alice_servers = {server["server_id"]: server for server in alice_result["data"]["servers"]}
    anonymous_ids = {server["server_id"] for server in anonymous_result["data"]["servers"]}

    assert set(alice_servers) == {_ALICE_SERVER, _PUBLIC_SERVER}
    assert alice_servers[_ALICE_SERVER]["call_count_7d"] == 1
    assert alice_servers[_ALICE_SERVER]["token_consumption"] == 5
    assert alice_servers[_ALICE_SERVER]["status"] == "running"
    assert alice_servers[_PUBLIC_SERVER]["enabled"] is False
    assert alice_servers[_PUBLIC_SERVER]["status"] == "not_connected"
    assert _ALICE_SERVER not in anonymous_ids
    assert _BOB_SERVER not in anonymous_ids
    assert _CUSTOM_SERVER not in anonymous_ids
    assert _PUBLIC_SERVER not in anonymous_ids


async def test_config_download_contains_only_current_users_servers() -> None:
    await _prepare_dashboard_data()

    response = await download_config(user_id="dashboard-alice")
    config = json.loads(response.body)

    assert response.status_code == 200
    assert "alice-private" in config["mcpServers"]
    assert "public-installed" not in config["mcpServers"]
    assert "bob-private" not in config["mcpServers"]


def test_config_export_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.get("/api/v1/export/config")

    assert response.status_code == 401


def test_telemetry_report_export_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.get("/api/v1/export/telemetry-report")

    assert response.status_code == 401


async def test_config_export_is_user_scoped_and_does_not_create_temp_files(
    monkeypatch,
) -> None:
    await _prepare_dashboard_data()

    def fail_temp_file(*_args, **_kwargs):
        raise AssertionError("configuration export must not create persistent temporary files")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail_temp_file)
    response = await export_config(share=True, user_id="dashboard-alice")
    config = json.loads(response.body)

    assert response.status_code == 200
    assert set(config["mcpServers"]) == {"alice-private"}
    assert config["_meta"] == {
        "exported_by": "mcp-hub",
        "version": __version__,
        "server_count": 1,
    }


async def test_telemetry_report_export_is_user_scoped_and_redacted(
    monkeypatch,
) -> None:
    await _prepare_dashboard_data()

    def fail_temp_file(*_args, **_kwargs):
        raise AssertionError("telemetry report export must not create persistent temporary files")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail_temp_file)
    response = await export_telemetry_report(days=7, user_id="dashboard-alice")
    report = json.loads(response.body)
    serialized = json.dumps(report, ensure_ascii=False)

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="mcp-hub-telemetry-report-7d.json"'
    )
    assert report["report_type"] == "mcp_hub_account_telemetry"
    assert report["summary"]["total_calls"] == 1
    assert report["summary"]["total_tokens"] == 5
    assert report["servers"] == [
        {
            "server_id": _ALICE_SERVER,
            "total_calls": 1,
            "ok_calls": 1,
            "error_calls": 0,
            "success_rate": 100.0,
            "avg_duration_ms": 0.0,
            "total_tokens": 5,
            "last_call_at": report["servers"][0]["last_call_at"],
        }
    ]
    assert report["agents"][0]["agent_type"] == "codex"
    assert "dashboard-bob" not in serialized
    assert "dashboard-alice-device" not in serialized
    data_only = {
        key: value
        for key, value in report.items()
        if key != "privacy"
    }
    serialized_data = json.dumps(data_only, ensure_ascii=False)
    for forbidden in (
        "device_id",
        "device_name",
        "session_id",
        "tool_name",
        "input_bytes",
        "output_bytes",
    ):
        assert f'"{forbidden}"' not in serialized_data


async def test_admin_config_downloads_do_not_create_temp_files(monkeypatch) -> None:
    await _prepare_dashboard_data()

    def fail_temp_file(*_args, **_kwargs):
        raise AssertionError("configuration downloads must not create persistent temporary files")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail_temp_file)
    generated = await generate_config(_admin_id="admin")
    installed = await download_all_config(_admin_id="admin")

    assert generated.status_code == 200
    assert installed.status_code == 200
    assert "public-installed" in json.loads(generated.body)["mcpServers"]
    assert "public-installed" in json.loads(installed.body)["mcpServers"]
