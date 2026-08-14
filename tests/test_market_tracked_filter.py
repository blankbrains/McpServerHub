"""Account-scoped market tracking filter regression tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_hub.api.routes_search import advanced_search
from mcp_hub.db.database import Base
from mcp_hub.db.models import ServerModel, UserServerModel


async def _search(
    *,
    tracked_filter: str | None,
    user_id: str | None,
) -> dict[str, object]:
    return await advanced_search(
        q="",
        category=None,
        tag=None,
        author=None,
        language=None,
        install_type=None,
        security_level=None,
        tracked_filter=tracked_filter,
        min_stars=None,
        sort="name",
        page=1,
        page_size=9,
        user_id=user_id,
    )


async def test_market_tracked_filter_is_exact_and_user_scoped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tracked.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with factory() as session:
            session.add_all(
                [
                    ServerModel(
                        id="@tracked/alpha",
                        name="alpha",
                        display_name="Alpha",
                        market_visible=True,
                    ),
                    ServerModel(
                        id="@tracked/beta",
                        name="beta",
                        display_name="Beta",
                        market_visible=True,
                    ),
                    ServerModel(
                        id="@tracked/gamma",
                        name="gamma",
                        display_name="Gamma",
                        market_visible=True,
                    ),
                    UserServerModel(
                        user_id="alice",
                        server_id="@tracked/alpha",
                        matched=True,
                    ),
                    UserServerModel(
                        user_id="bob",
                        server_id="@tracked/beta",
                        matched=True,
                    ),
                ]
            )
            await session.commit()

        monkeypatch.setattr(
            "mcp_hub.api.routes_search.async_session_factory",
            factory,
        )

        alice_tracked = await _search(tracked_filter="tracked", user_id="alice")
        alice_untracked = await _search(tracked_filter="untracked", user_id="alice")
        bob_tracked = await _search(tracked_filter="tracked", user_id="bob")
    finally:
        await engine.dispose()

    assert alice_tracked["meta"]["total"] == 1  # type: ignore[index]
    assert [row["id"] for row in alice_tracked["data"]] == ["@tracked/alpha"]  # type: ignore[index]
    assert alice_untracked["meta"]["total"] == 2  # type: ignore[index]
    assert [row["id"] for row in alice_untracked["data"]] == [  # type: ignore[index]
        "@tracked/beta",
        "@tracked/gamma",
    ]
    assert bob_tracked["meta"]["total"] == 1  # type: ignore[index]
    assert [row["id"] for row in bob_tracked["data"]] == ["@tracked/beta"]  # type: ignore[index]


async def test_market_rejects_anonymous_account_filtering() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _search(tracked_filter="tracked", user_id=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "登录后才能按追踪状态筛选"
