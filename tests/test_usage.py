"""Usage API regression tests."""

from __future__ import annotations

from sqlalchemy import delete, select

from mcp_hub.api.routes_usage import get_usage_stats, record_usage
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import Base, UsageStatsModel


async def _prepare_usage_table() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await session.execute(delete(UsageStatsModel))
        await session.commit()


async def test_record_usage_uses_authenticated_identity() -> None:
    await _prepare_usage_table()

    result = await record_usage(
        {
            "server_id": "@example/weather",
            "tool_name": "forecast",
            "user_id": "other-user",
        },
        user_id="current-user",
    )

    assert result["success"] is True
    async with async_session_factory() as session:
        stored = await session.scalar(select(UsageStatsModel))
    assert stored is not None
    assert stored.user_id == "current-user"


async def test_usage_stats_are_scoped_to_authenticated_user() -> None:
    await _prepare_usage_table()

    async with async_session_factory() as session:
        session.add_all(
            [
                UsageStatsModel(
                    server_id="@example/weather",
                    user_id="current-user",
                    status="ok",
                    duration_ms=100,
                    token_count=10,
                ),
                UsageStatsModel(
                    server_id="@example/weather",
                    user_id="current-user",
                    status="error",
                    duration_ms=300,
                    token_count=5,
                ),
                UsageStatsModel(
                    server_id="@example/weather",
                    user_id="other-user",
                    status="ok",
                    duration_ms=1,
                    token_count=999,
                ),
            ]
        )
        await session.commit()

    result = await get_usage_stats(days=30, user_id="current-user")

    assert result["success"] is True
    assert result["data"]["total_servers"] == 1
    stats = result["data"]["stats"][0]
    assert stats["total_calls"] == 2
    assert stats["total_tokens"] == 15
    assert stats["ok_count"] == 1
    assert stats["error_count"] == 1
    assert stats["success_rate"] == 50.0
