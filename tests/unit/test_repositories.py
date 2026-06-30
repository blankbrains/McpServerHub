"""单元测试 — Repository 层（数据库访问对象）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from mcp_hub.db.repositories import (
    ReviewRepository,
    ServerRepository,
    UserRepository,
)


# ── 数据库 fixture ────────────────────────────────────────


@pytest.fixture
async def db_session(temp_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """创建临时 SQLite + 覆盖 async_session_factory + 建表。"""
    db_url = f"sqlite+aiosqlite:///{temp_dir}/test_repo.db"
    monkeypatch.setenv("MCP_HUB_DATABASE_URL", db_url)

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from mcp_hub.db.database import Base

    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("mcp_hub.db.database.async_session_factory", factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield factory

    await engine.dispose()


@pytest.fixture
async def seeded_session(db_session):
    """预置 seed data 的 session factory。"""
    factory = db_session
    async with factory() as session:
        repo = ServerRepository(session)
        for s in _SEED_SERVERS:
            await repo.register_server(s)
        await session.commit()
    return factory


_SEED_SERVERS = [
    {
        "id": "@alpha/search",
        "name": "search",
        "description": "搜索工具",
        "author": "alpha",
        "categories": ["browser", "search"],
        "tags": ["web"],
        "rating": 4.5,
        "download_count": 1000,
        "status": "running",
        "security_level": "verified",
    },
    {
        "id": "@beta/db",
        "name": "db",
        "description": "数据库查询",
        "author": "beta",
        "categories": ["database"],
        "tags": ["sql"],
        "rating": 4.0,
        "download_count": 500,
        "status": "stopped",
        "security_level": "reviewed",
    },
    {
        "id": "@gamma/tools",
        "name": "tools",
        "description": "文件工具",
        "author": "gamma",
        "categories": ["tools"],
        "tags": ["file"],
        "rating": 3.5,
        "download_count": 100,
        "status": "not_installed",
        "security_level": "unreviewed",
    },
]


# ═══════════════════════════════════════════════════════════
# ServerRepository
# ═══════════════════════════════════════════════════════════


class TestServerRepositorySearch:
    async def test_search_basic(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results, total = await repo.search(q="")
        assert total == 3
        assert len(results) == 3

    async def test_search_with_query(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results, total = await repo.search(q="search")
        assert total >= 1
        assert results[0]["id"] == "@alpha/search"

    async def test_search_with_category(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results, total = await repo.search(q="", category="database")
        assert total >= 1
        assert results[0]["id"] == "@beta/db"

    async def test_search_with_tag(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results, total = await repo.search(q="", tag="web")
        assert total >= 1
        assert results[0]["id"] == "@alpha/search"

    async def test_search_pagination(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results_page1, total = await repo.search(q="", page=1, page_size=2)
            results_page2, _ = await repo.search(q="", page=2, page_size=2)
        assert len(results_page1) == 2
        assert len(results_page2) == 1
        assert total == 3

    async def test_search_sort_hot(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results, _ = await repo.search(q="", sort="hot")
        assert results[0]["download_count"] >= results[-1]["download_count"]

    async def test_search_sort_rating(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results, _ = await repo.search(q="", sort="rating")
        assert results[0]["rating"] >= results[-1]["rating"]


class TestServerRepositoryCRUD:
    async def test_get_by_id(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            result = await repo.get_by_id("@alpha/search")
        assert result is not None
        assert result["id"] == "@alpha/search"
        assert result["author"] == "alpha"
        assert isinstance(result["categories"], list)
        assert "browser" in result["categories"]

    async def test_get_by_id_not_found(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            result = await repo.get_by_id("@nonexistent/xxx")
        assert result is None

    async def test_get_installed(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            installed = await repo.get_installed()
        assert len(installed) == 2  # running + stopped
        ids = [s["id"] for s in installed]
        assert "@gamma/tools" not in ids

    async def test_update_status(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            ok = await repo.update_status("@beta/db", "running")
        assert ok is True
        async with seeded_session() as session:
            repo = ServerRepository(session)
            result = await repo.get_by_id("@beta/db")
        assert result is not None
        assert result["status"] == "running"

    async def test_update_status_not_found(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            ok = await repo.update_status("@nonexistent/xxx", "running")
        assert ok is False

    async def test_increment_download(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            await repo.increment_download("@gamma/tools")
        async with seeded_session() as session:
            repo = ServerRepository(session)
            result = await repo.get_by_id("@gamma/tools")
        assert result is not None
        assert result["download_count"] == 101


class TestServerRepositoryRegister:
    async def test_register_new(self, db_session) -> None:
        async with db_session() as session:
            repo = ServerRepository(session)
            sid = await repo.register_server({
                "id": "@new/test",
                "name": "test",
                "description": "新 Server",
            })
        assert sid == "@new/test"
        async with db_session() as session:
            repo = ServerRepository(session)
            result = await repo.get_by_id("@new/test")
        assert result is not None

    async def test_register_update_existing(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            sid = await repo.register_server({
                "id": "@alpha/search",
                "name": "search",
                "description": "已更新描述",
            })
        assert sid == "@alpha/search"
        async with seeded_session() as session:
            repo = ServerRepository(session)
            result = await repo.get_by_id("@alpha/search")
        assert result is not None
        assert result["description"] == "已更新描述"

    async def test_get_by_author(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results = await repo.get_by_author("alpha")
        assert len(results) >= 1
        assert results[0]["author"] == "alpha"

    async def test_get_by_author_not_found(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            results = await repo.get_by_author("unknown")
        assert results == []

    async def test_delete_server(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            ok = await repo.delete_server("@gamma/tools")
        assert ok is True
        async with seeded_session() as session:
            repo = ServerRepository(session)
            result = await repo.get_by_id("@gamma/tools")
        assert result is None

    async def test_delete_server_not_found(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ServerRepository(session)
            ok = await repo.delete_server("@nonexistent/xxx")
        assert ok is False


# ═══════════════════════════════════════════════════════════
# ReviewRepository
# ═══════════════════════════════════════════════════════════


class TestReviewRepository:
    async def test_rate_new(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            result = await repo.rate(
                server_id="@alpha/search",
                user_id="user1",
                rating=5,
                content="非常好用",
            )
        assert isinstance(result, dict)
        assert result["rating"] > 0

    async def test_rate_update(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            await repo.rate("@alpha/search", "user1", 5, "初评")
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            result = await repo.rate("@alpha/search", "user1", 3, "更新评价")
        assert result["rating"] == 3.0  # single review avg

    async def test_rate_with_parent(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            parent_result = await repo.rate("@alpha/search", "user1", 4, "原评价")
            reply_result = await repo.rate(
                "@alpha/search", "user2", 5, "回复",
                parent_id=1,
            )
        assert reply_result.get("parent_id") == 1

    async def test_get_reviews(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            for i in range(3):
                await repo.rate("@alpha/search", f"user{i}", 4 + i, f"评价{i}")
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            reviews = await repo.get_reviews("@alpha/search")
        assert len(reviews) == 3

    async def test_get_review(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            # rate returns dict, but get_review returns ReviewModel
            await repo.rate("@alpha/search", "user1", 5, "test")
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            reviews = await repo.get_reviews("@alpha/search")
        assert len(reviews) >= 1
        found = reviews[0]
        assert found["content"] == "test"

    async def test_delete_review_by_author(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            await repo.rate("@alpha/search", "user1", 4, "待删")
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            reviews = await repo.get_reviews("@alpha/search")
            if reviews:
                rid = reviews[0]["id"]
                result = await repo.delete_review(rid, user_id="user1", user_role="user")
                assert result["success"] is True

    async def test_can_delete_review_admin(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            # Create a review first
            await repo.rate("@alpha/search", "user1", 4, "test")
            reviews = await repo.get_reviews("@alpha/search")
            if reviews:
                review_id = reviews[0]["id"]
                # get the ReviewModel by get_review
                review_model = await repo.get_review(review_id)
                assert review_model is not None
                can, msg = await repo.can_delete_review(review_model, user_id="admin", user_role="admin")
                assert can is True

    async def test_get_reviews_empty(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = ReviewRepository(session)
            reviews = await repo.get_reviews("@gamma/tools")
        assert reviews == []


# ═══════════════════════════════════════════════════════════
# UserRepository
# ═══════════════════════════════════════════════════════════


class TestUserRepository:
    async def test_get_or_create_new(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = UserRepository(session)
            user = await repo.get_or_create({"id": "newuser", "name": "新用户"})
        assert user["id"] == "newuser"
        assert user["display_name"] == "新用户"

    async def test_get_or_create_existing(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = UserRepository(session)
            await repo.get_or_create({"id": "user1", "name": "用户1"})
            user = await repo.get_or_create({"id": "user1", "name": "用户1"})
        assert user["id"] == "user1"

    async def test_favorite_toggle(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = UserRepository(session)
            await repo.get_or_create({"id": "user1", "name": "用户1"})
            ok = await repo.favorite("user1", "@alpha/search")
        assert ok is True

    async def test_get_favorites(self, seeded_session) -> None:
        async with seeded_session() as session:
            repo = UserRepository(session)
            await repo.get_or_create({"id": "user1", "name": "用户1"})
            await repo.favorite("user1", "@alpha/search")
            await repo.favorite("user1", "@beta/db")
        async with seeded_session() as session:
            repo = UserRepository(session)
            favorites = await repo.get_favorites("user1")
        assert len(favorites) == 2
