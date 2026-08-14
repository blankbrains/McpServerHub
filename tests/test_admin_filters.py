"""Admin list filter and sorting regression tests."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, event
from starlette.routing import Match

from mcp_hub.api.routes_admin import (
    _csv_cell,
    admin_categories,
    admin_overview,
    admin_reviews,
    admin_servers,
    admin_set_security,
    admin_toggle_server,
    admin_top_servers,
    admin_top_users,
    admin_update_role,
    admin_user_detail,
    admin_users,
)
from mcp_hub.api.routes_admin import (
    router as admin_router,
)
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import (
    Base,
    ReviewModel,
    ServerModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UsageStatsModel,
    UserModel,
    UserServerModel,
)

_NOW = datetime.now(timezone.utc).replace(tzinfo=None)


async def _prepare_admin_filter_data() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        user_ids = ["admin-filter-admin", "admin-filter-user"]
        server_ids = [
            "@admin-filter/verified",
            "@admin-filter/blocked",
            "@admin-filter/tools",
        ]
        await session.execute(
            delete(UsageStatsModel).where(UsageStatsModel.server_id.in_(server_ids))
        )
        await session.execute(
            delete(ReviewModel).where(ReviewModel.server_id.in_(server_ids))
        )
        await session.execute(
            delete(UserServerModel).where(UserServerModel.server_id.in_(server_ids))
        )
        await session.execute(delete(ServerModel).where(ServerModel.id.in_(server_ids)))
        await session.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))
        session.add_all(
            [
                UserModel(id="admin-filter-admin", display_name="Admin", role="admin"),
                UserModel(id="admin-filter-user", display_name="User", role="user"),
                ServerModel(
                    id="@admin-filter/verified",
                    name="verified",
                    security_level="verified",
                    install_command="npx verified",
                    categories='["developer-tools"]',
                ),
                ServerModel(
                    id="@admin-filter/blocked",
                    name="blocked",
                    security_level="blocked",
                    install_command="npx blocked",
                ),
                ServerModel(
                    id="@admin-filter/tools",
                    name="tools",
                    security_level="reviewed",
                    install_command="npx tools",
                    categories='["tools"]',
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
                    token_count=100,
                ),
                UserServerModel(
                    user_id="admin-filter-user",
                    server_id="@admin-filter/verified",
                ),
            ]
        )
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

    installs = await admin_servers(
        sort="installs",
        page=1,
        page_size=20,
        admin_user="test-admin",
    )
    install_ids = [server["server_id"] for server in installs["data"]]
    assert install_ids.index("@admin-filter/verified") < install_ids.index("@admin-filter/blocked")


async def test_admin_categories_use_market_category_ids() -> None:
    await _prepare_admin_filter_data()

    result = await admin_categories(admin_user="test-admin")
    categories = {category["id"]: category for category in result["data"]}

    assert "developer" not in categories
    assert categories["developer-tools"]["count"] >= 1
    assert categories["tools"]["count"] >= 1


async def test_admin_category_filter_matches_exact_json_item() -> None:
    await _prepare_admin_filter_data()

    tools = await admin_servers(
        category="tools",
        page=1,
        page_size=20,
        admin_user="test-admin",
    )
    developer_tools = await admin_servers(
        category="developer-tools",
        page=1,
        page_size=20,
        admin_user="test-admin",
    )

    assert [server["server_id"] for server in tools["data"]] == [
        "@admin-filter/tools"
    ]
    assert [server["server_id"] for server in developer_tools["data"]] == [
        "@admin-filter/verified"
    ]


async def test_admin_analytics_respects_metric_selection() -> None:
    await _prepare_admin_filter_data()

    by_tokens = await admin_top_servers(
        metric="tokens",
        days=7,
        limit=10,
        admin_user="test-admin",
    )
    by_installs = await admin_top_servers(
        metric="installs",
        days=7,
        limit=10,
        admin_user="test-admin",
    )
    users_by_tokens = await admin_top_users(
        metric="tokens",
        days=7,
        limit=10,
        admin_user="test-admin",
    )

    assert by_tokens["data"][0]["server_id"] == "@admin-filter/verified"
    assert by_installs["data"][0]["server_id"] == "@admin-filter/verified"
    assert by_installs["data"][0]["installs"] == 1
    assert users_by_tokens["data"][0]["user_id"] == "admin-filter-user"


async def test_admin_analytics_rejects_unknown_metrics() -> None:
    assert (
        await admin_top_servers(metric="unknown", admin_user="test-admin")
    ) == {"success": False, "error": "metric 必须是 calls、tokens 或 installs"}
    assert (
        await admin_top_users(metric="unknown", admin_user="test-admin")
    ) == {"success": False, "error": "metric 必须是 calls 或 tokens"}


async def test_admin_lists_reject_unknown_sort_values() -> None:
    assert await admin_users(sort="unknown", admin_user="test-admin") == {
        "success": False,
        "error": "sort 必须是 calls、installs 或 created",
    }
    assert await admin_servers(sort="unknown", admin_user="test-admin") == {
        "success": False,
        "error": "sort 必须是 installs、calls 或 rating",
    }


def test_admin_csv_cells_escape_spreadsheet_formulas() -> None:
    assert _csv_cell("=HYPERLINK(\"https://example.test\")").startswith("'=")
    assert _csv_cell("+SUM(1,1)").startswith("'+")
    assert _csv_cell("normal") == "normal"
    assert _csv_cell(None) == ""


async def test_admin_blocking_server_removes_it_from_market() -> None:
    await _prepare_admin_filter_data()

    blocked = await admin_toggle_server(
        server_id="@admin-filter/verified",
        data={"action": "block"},
        admin_user="test-admin",
    )
    assert blocked["success"] is True

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/verified")
        assert server is not None
        assert server.security_level == "blocked"
        assert server.market_visible is False

    restored = await admin_toggle_server(
        server_id="@admin-filter/verified",
        data={"action": "unblock"},
        admin_user="test-admin",
    )
    assert restored["success"] is True

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/verified")
        assert server is not None
        assert server.security_level == "reviewed"
        assert server.market_visible is True


async def test_admin_security_update_rejects_missing_server() -> None:
    result = await admin_set_security(
        server_id="@admin-filter/missing",
        data={"level": "reviewed"},
        admin_user="test-admin",
    )
    assert result == {"success": False, "error": "Server 不存在"}


async def test_admin_security_block_hides_server_from_market() -> None:
    await _prepare_admin_filter_data()

    result = await admin_set_security(
        server_id="@admin-filter/verified",
        data={"level": "blocked"},
        admin_user="test-admin",
    )
    assert result["success"] is True

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/verified")
        assert server is not None
        assert server.security_level == "blocked"
        assert server.market_visible is False


async def test_admin_security_update_restores_active_server_visibility() -> None:
    await _prepare_admin_filter_data()

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/blocked")
        assert server is not None
        server.market_visible = False
        await session.commit()

    result = await admin_set_security(
        server_id="@admin-filter/blocked",
        data={"level": "reviewed"},
        admin_user="test-admin",
    )
    assert result["success"] is True

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/blocked")
        assert server is not None
        assert server.security_level == "reviewed"
        assert server.market_visible is True


async def test_admin_security_update_keeps_upstream_deleted_server_hidden() -> None:
    await _prepare_admin_filter_data()

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/blocked")
        assert server is not None
        server.catalog_status = "deleted"
        server.market_visible = False
        await session.commit()

    result = await admin_set_security(
        server_id="@admin-filter/blocked",
        data={"level": "reviewed"},
        admin_user="test-admin",
    )
    assert result["success"] is True

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/blocked")
        assert server is not None
        assert server.security_level == "reviewed"
        assert server.market_visible is False


async def test_admin_unblock_keeps_upstream_deleted_server_hidden() -> None:
    await _prepare_admin_filter_data()

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/blocked")
        assert server is not None
        server.catalog_status = "deleted"
        server.market_visible = False
        await session.commit()

    result = await admin_toggle_server(
        server_id="@admin-filter/blocked",
        data={"action": "unblock"},
        admin_user="test-admin",
    )
    assert result["success"] is True
    assert "上游目录已删除" in result["message"]

    async with async_session_factory() as session:
        server = await session.get(ServerModel, "@admin-filter/blocked")
        assert server is not None
        assert server.security_level == "reviewed"
        assert server.market_visible is False


async def test_admin_reviews_return_complete_content() -> None:
    await _prepare_admin_filter_data()
    content = "管理员需要读取完整评价。" * 40

    async with async_session_factory() as session:
        await session.execute(
            delete(ReviewModel).where(
                ReviewModel.server_id == "@admin-filter/verified",
                ReviewModel.user_id == "admin-filter-user",
            )
        )
        session.add(
            ReviewModel(
                server_id="@admin-filter/verified",
                user_id="admin-filter-user",
                rating=1,
                content=content,
            )
        )
        await session.commit()

    result = await admin_reviews(admin_user="test-admin")
    review = next(
        item
        for item in result["data"]
        if item["server_id"] == "@admin-filter/verified"
        and item["user_id"] == "admin-filter-user"
    )
    assert review["content"] == content


async def test_admin_server_list_and_categories_do_not_query_per_row() -> None:
    await _prepare_admin_filter_data()

    statements: list[str] = []

    def record_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        statements.clear()
        await admin_servers(
            admin_user="test-admin",
            page=1,
            page_size=1,
        )
        one_row_count = len(statements)

        statements.clear()
        await admin_servers(
            admin_user="test-admin",
            page=1,
            page_size=20,
        )
        all_rows_count = len(statements)

        statements.clear()
        await admin_categories(admin_user="test-admin")
        category_count = len(statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record_statement)

    assert one_row_count == 2
    assert all_rows_count == one_row_count
    assert category_count == 1


async def test_admin_cannot_demote_self_or_last_admin() -> None:
    await _prepare_admin_filter_data()

    self_change = await admin_update_role(
        user_id="admin-filter-admin",
        data={"role": "user"},
        admin_user="admin-filter-admin",
    )
    assert self_change == {"success": False, "error": "不能降级当前登录的管理员账号"}

    last_admin_change = await admin_update_role(
        user_id="admin-filter-admin",
        data={"role": "user"},
        admin_user="test-admin",
    )
    assert last_admin_change == {"success": False, "error": "平台至少需要保留一名管理员"}


async def test_admin_telemetry_is_authoritative_and_user_detail_includes_devices() -> None:
    await _prepare_admin_filter_data()
    user_id = "admin-filter-user"
    server_id = "@admin-filter/verified"
    event_id = "admin-filter-telemetry-event"
    device_id = "admin-filter-device"

    async with async_session_factory() as session:
        await session.execute(
            delete(TelemetryInventoryModel).where(
                TelemetryInventoryModel.device_id == device_id
            )
        )
        await session.execute(
            delete(TelemetryEventModel).where(TelemetryEventModel.id == event_id)
        )
        await session.execute(
            delete(TelemetryDeviceModel).where(TelemetryDeviceModel.id == device_id)
        )
        session.add(
            TelemetryDeviceModel(
                id=device_id,
                user_id=user_id,
                name="Codex Laptop",
                agent_type="codex",
                token_hash="admin-filter-device-token".ljust(64, "x"),
                gateway_first_seen_at=_NOW,
                gateway_last_seen_at=_NOW,
                first_call_at=_NOW,
            )
        )
        session.add(
            TelemetryEventModel(
                id=event_id,
                user_id=user_id,
                device_id=device_id,
                event_type="tool_call",
                server_id=server_id,
                tool_name="run",
                status="ok",
                input_tokens=12,
                output_tokens=8,
                occurred_at=_NOW,
            )
        )
        session.add(
            TelemetryInventoryModel(
                user_id=user_id,
                device_id=device_id,
                server_name=server_id,
                config_hash="b" * 64,
                discovered_at=_NOW,
                last_seen_at=_NOW,
            )
        )
        await session.commit()

    overview = await admin_overview(admin_user="test-admin")
    assert overview["data"]["stats"]["total_calls"] == 4
    assert overview["data"]["stats"]["total_tokens"] == 120
    assert overview["data"]["stats"]["total_devices"] >= 1
    assert overview["data"]["stats"]["online_devices"] >= 1

    detail = await admin_user_detail(user_id=user_id, admin_user="test-admin")
    assert detail["data"]["stats"]["device_count"] == 1
    assert detail["data"]["stats"]["online_device_count"] == 1
    assert detail["data"]["devices"][0]["name"] == "Codex Laptop"
    assert detail["data"]["devices"][0]["server_count"] == 1


def _first_matching_admin_route(path: str) -> str:
    scope = {
        "type": "http",
        "path": path,
        "method": "GET",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
    }
    for route in admin_router.routes:
        match, _ = route.matches(scope)
        if match is Match.FULL:
            return route.name
    raise AssertionError(f"no admin route matched {path}")


def test_admin_nested_routes_are_not_shadowed_by_path_details() -> None:
    assert _first_matching_admin_route("/admin/users/alice/servers") == "admin_user_servers"
    assert _first_matching_admin_route("/admin/users/alice/usage/daily") == "admin_user_daily"
    assert (
        _first_matching_admin_route("/admin/servers/@example/tool/users")
        == "admin_server_users"
    )
    assert (
        _first_matching_admin_route("/admin/servers/@example/tool/usage/daily")
        == "admin_server_daily"
    )
