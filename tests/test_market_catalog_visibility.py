"""Market endpoints must hide deleted upstream catalog records consistently."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_hub.api.routes_market import get_categories
from mcp_hub.db.database import Base
from mcp_hub.db.models import ServerModel


async def test_market_categories_exclude_hidden_catalog_records(monkeypatch, tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'market.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with factory() as session:
            session.add_all(
                [
                    ServerModel(
                        id="@visible/browser",
                        name="browser",
                        categories='["browser"]',
                        market_visible=True,
                    ),
                    ServerModel(
                        id="@hidden/security",
                        name="security",
                        categories='["security"]',
                        market_visible=False,
                    ),
                ]
            )
            await session.commit()

        monkeypatch.setattr("mcp_hub.db.database.async_session_factory", factory)
        result = await get_categories()
    finally:
        await engine.dispose()

    categories = result["data"]
    assert {"id": "browser", "name": "浏览器 & 搜索", "icon": "🌐", "count": 1} in categories
    assert not any(category["id"] == "security" for category in categories)
