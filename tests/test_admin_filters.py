"""Admin list filter and sorting regression tests."""

from __future__ import annotations

from sqlalchemy import delete

from mcp_hub.api.routes_admin import admin_servers, admin_users
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import Base, ServerModel, UsageStatsModel, UserModel


async def _prepare_admin_filter_data() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        user_ids = ["admin-filter-admin", "admin-filter-user"]
        server_ids = ["@admin-filter/verified", "@admin-filter/blocked"]
        await session.execute(
            delete(UsageStatsModel).where(
                UsageStatsModel.server_id.in_(server_ids)
            )
        )
        await session.execute(delete(ServerModel).where(ServerModel.id.in_(server_ids)))
        await session.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))
        session.add_all([
            UserModel(id="admin-filter-admin", display_name="Admin", role="admin"),
            UserModel(id="admin-filter-user", display_name="User", role="user"),
            ServerModel(
                id="@admin-filter/verified",
                name="verified",
                security_level="verified",
                install_command="npx verified",
            ),
            ServerModel(
                id="@admin-filter/blocked",
                name="blocked",
                security_level="blocked",
                install_command="npx blocked",
            ),
            UsageStatsModel(
                user_id="admin-filter-user",
                server_id="@admin-filter/blocked",
                tool_name="run",
                status="ok",
            ),
            UsageStatsModel(
                user_id="admin-filter-user",
                server_id="@admin-filter/blocked",
                tool_name="run",
                status="ok",
            ),
            UsageStatsModel(
                user_id="admin-filter-user",
                server_id="@admin-filter/verified",
                tool_name="run",
                status="ok",
            ),
        ])
        await session.commit()


async def test_admin_users_filters_by_role() -> None:
    await _prepare_admin_filter_data()

    result = await admin_users(
        admin_user="test-admin",
        role="admin",
        page=1,
        page_size=20,
    )

    returned_ids = {user["user_id"] for user in result["data"]}
    assert "admin-filter-admin" in returned_ids
    assert "admin-filter-user" not in returned_ids


async def test_admin_servers_filters_security_and_sorts_by_calls() -> None:
    await _prepare_admin_filter_data()

    blocked = await admin_servers(
        admin_user="test-admin",
        security_level="blocked",
        page=1,
        page_size=20,
    )
    calls = await admin_servers(
        admin_user="test-admin",
        sort="calls",
        page=1,
        page_size=20,
    )

    assert [server["server_id"] for server in blocked["data"]] == ["@admin-filter/blocked"]
    ids = [server["server_id"] for server in calls["data"]]
    assert ids.index("@admin-filter/blocked") < ids.index("@admin-filter/verified")
