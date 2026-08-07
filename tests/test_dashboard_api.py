"""仪表盘数据隔离和配置下载回归测试。"""

from __future__ import annotations

import json

from sqlalchemy import delete

from mcp_hub.api.routes_config import download_config
from mcp_hub.api.routes_monitor import monitor_dashboard
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import Base, ServerModel, UsageStatsModel, UserServerModel

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
            delete(UsageStatsModel).where(UsageStatsModel.server_id.in_(server_ids))
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
                UserServerModel(user_id="dashboard-bob", server_id=_BOB_SERVER),
                UsageStatsModel(
                    user_id="dashboard-alice",
                    server_id=_ALICE_SERVER,
                    tool_name="search",
                    status="ok",
                ),
                UsageStatsModel(
                    user_id="dashboard-bob",
                    server_id=_ALICE_SERVER,
                    tool_name="search",
                    status="ok",
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

    assert set(alice_servers) == {_ALICE_SERVER}
    assert alice_servers[_ALICE_SERVER]["call_count_7d"] == 1
    assert _ALICE_SERVER not in anonymous_ids
    assert _BOB_SERVER not in anonymous_ids
    assert _CUSTOM_SERVER not in anonymous_ids
    assert _PUBLIC_SERVER in anonymous_ids


async def test_config_download_contains_only_current_users_servers() -> None:
    await _prepare_dashboard_data()

    response = await download_config(user_id="dashboard-alice")
    config = json.loads(response.body)

    assert response.status_code == 200
    assert "alice-private" in config["mcpServers"]
    assert "bob-private" not in config["mcpServers"]
    assert "public-installed" not in config["mcpServers"]
