"""单元测试 — Registry（ServerRepository 代理层）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from mcp_hub.core.registry import Registry


@pytest.fixture
async def db_session(temp_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """创建临时 SQLite + 覆盖 async_session_factory + seed data。"""
    db_url = f"sqlite+aiosqlite:///{temp_dir}/test_registry.db"
    monkeypatch.setenv("MCP_HUB_DATABASE_URL", db_url)

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from mcp_hub.db.database import Base

    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # Patch both the database module AND the registry module's reference
    monkeypatch.setattr("mcp_hub.db.database.async_session_factory", factory)
    monkeypatch.setattr("mcp_hub.core.registry.async_session_factory", factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Inject seed data
    from mcp_hub.db.repositories import ServerRepository
    async with factory() as session:
        repo = ServerRepository(session)
        for s in _SEED_SERVERS:
            await repo.register_server(s)
        await session.commit()

    yield factory

    await engine.dispose()


_SEED_SERVERS = [
    {
        "id": "@anthropic/web-search",
        "name": "web-search",
        "description": "让 Agent 搜索网络",
        "author": "anthropic",
        "categories": ["browser"],
        "tags": ["web", "search"],
        "rating": 4.8,
        "review_count": 10,
        "download_count": 12000,
        "status": "running",
        "install_type": "uvx",
        "install_command": "uvx mcp-server-web-search",
    },
    {
        "id": "@community/sql-query",
        "name": "sql-query",
        "description": "自然语言查询数据库",
        "author": "community",
        "categories": ["database"],
        "tags": ["sql", "database"],
        "rating": 4.2,
        "review_count": 5,
        "download_count": 8000,
        "status": "stopped",
        "install_type": "pip",
        "install_command": "pip install mcp-server-sql-query",
    },
    {
        "id": "@community/noop-server",
        "name": "noop-server",
        "description": "未安装的测试 Server",
        "author": "community",
        "categories": ["tools"],
        "tags": ["test"],
        "rating": 3.0,
        "download_count": 100,
        "status": "not_installed",
    },
]


@pytest.fixture
def registry() -> Registry:
    return Registry()


# ── 搜索 ──────────────────────────────────────────────────


class TestRegistrySearch:
    async def test_search_basic(self, registry: Registry, db_session) -> None:
        """空查询返回所有结果。"""
        results, total = await registry.search(q="")
        assert total >= 2
        assert len(results) >= 2

    async def test_search_with_query(self, registry: Registry, db_session) -> None:
        """按关键词搜索。"""
        results, total = await registry.search(q="web")
        assert total >= 1
        assert any("web" in r["id"] for r in results)

    async def test_search_with_category(self, registry: Registry, db_session) -> None:
        """按分类筛选。"""
        results, total = await registry.search(q="", category="database")
        assert total >= 1
        assert all("database" in r.get("categories", []) for r in results)

    async def test_search_pagination(self, registry: Registry, db_session) -> None:
        """分页正确。"""
        results, total = await registry.search(q="", page=1, page_size=2)
        assert len(results) <= 2
        assert total >= 2


class TestRegistryGetById:
    async def test_get_by_id_found(self, registry: Registry, db_session) -> None:
        """按 ID 查询应返回正确结果。"""
        result = await registry.get_by_id("@anthropic/web-search")
        assert result is not None
        assert result["id"] == "@anthropic/web-search"
        assert result["rating"] == 4.8

    async def test_get_by_id_not_found(self, registry: Registry, db_session) -> None:
        """不存在的 ID 返回 None。"""
        result = await registry.get_by_id("@unknown/server")
        assert result is None


class TestRegistryStatus:
    async def test_get_installed(self, registry: Registry, db_session) -> None:
        """只返回 status != not_installed 的 Server。"""
        installed = await registry.get_installed()
        assert len(installed) >= 2  # running + stopped
        ids = [s["id"] for s in installed]
        assert "@community/noop-server" not in ids

    async def test_update_status(self, registry: Registry, db_session) -> None:
        """update_status 应改变状态。"""
        ok = await registry.update_status("@community/sql-query", "running")
        assert ok is True
        result = await registry.get_by_id("@community/sql-query")
        assert result is not None
        assert result["status"] == "running"


class TestRegistryCounters:
    async def test_increment_download(self, registry: Registry, db_session) -> None:
        """download_count 应原子 +1。"""
        before = await registry.get_by_id("@community/noop-server")
        assert before is not None
        old = before["download_count"]
        await registry.increment_download("@community/noop-server")
        after = await registry.get_by_id("@community/noop-server")
        assert after is not None
        assert after["download_count"] == old + 1


class TestRegistryLists:
    async def test_get_trending(self, registry: Registry, db_session) -> None:
        """热门按 download_count 降序。"""
        results = await registry.get_trending(limit=10)
        assert len(results) >= 1
        if len(results) >= 2:
            assert results[0]["download_count"] >= results[1]["download_count"]

    async def test_get_top_rated(self, registry: Registry, db_session) -> None:
        """评分最高按 rating 降序。"""
        results = await registry.get_top_rated(limit=10)
        assert len(results) >= 1
        if len(results) >= 2:
            assert results[0]["rating"] >= results[1]["rating"]

    async def test_get_new_releases(self, registry: Registry, db_session) -> None:
        """最新发布按 created_at 降序。"""
        results = await registry.get_new_releases(limit=10)
        assert len(results) >= 1


class TestRegistryRegister:
    async def test_register_server_new(self, registry: Registry, db_session) -> None:
        """注册新 Server 返回其 ID。"""
        sid = await registry.register_server({
            "id": "@test/new-server",
            "name": "new-server",
            "description": "全新 Server",
            "author": "test",
        })
        assert sid == "@test/new-server"
        result = await registry.get_by_id("@test/new-server")
        assert result is not None
        assert result["description"] == "全新 Server"

    async def test_register_server_update(self, registry: Registry, db_session) -> None:
        """注册已存在的 ID 应更新字段。"""
        sid = await registry.register_server({
            "id": "@anthropic/web-search",
            "name": "web-search",
            "description": "更新后的描述",
        })
        assert sid == "@anthropic/web-search"
        result = await registry.get_by_id("@anthropic/web-search")
        assert result is not None
        assert result["description"] == "更新后的描述"
