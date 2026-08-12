"""Regression tests for provenance-preserving Registry synchronization."""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_hub.core.registry_sources.base import RegistryEntry
from mcp_hub.core.registry_sources.sync import RegistrySourceSynchronizer
from mcp_hub.db.database import Base
from mcp_hub.db.models import (
    FavoriteModel,
    RegistrySourceEntryModel,
    RegistrySourceStateModel,
    ReviewModel,
    ServerModel,
    UserServerModel,
)
from mcp_hub.db.repositories import ServerRepository


def _entry(
    *,
    version: str = "1.0.0",
    lifecycle_status: str = "active",
    remote: bool = False,
) -> RegistryEntry:
    return RegistryEntry(
        source="test-source",
        upstream_id="example.test/demo",
        name="demo",
        display_name="Demo MCP",
        description="Registry supplied description",
        version=version,
        package_type="" if remote else "npm",
        package_identifier="" if remote else "@example/demo",
        package_version="" if remote else version,
        install_type="" if remote else "npx",
        install_command="" if remote else f"npx -y @example/demo@{version}",
        repository_url="https://github.com/example/demo",
        homepage="https://example.test/demo",
        transport="streamable-http" if remote else "",
        endpoint_url="https://api.example.test/mcp" if remote else "",
        config_template=(
            {"type": "streamable-http", "url": "https://api.example.test/mcp"} if remote else {}
        ),
        lifecycle_status=lifecycle_status,
        lifecycle_message="",
        published_at=datetime(2026, 8, 1, 0, 0, 0),
        updated_at=datetime(2026, 8, 2, 0, 0, 0),
    )


class _Source:
    source_name = "test-source"

    def __init__(self, entries: list[RegistryEntry], error: Exception | None = None) -> None:
        self.entries = entries
        self.error = error
        self.watermarks: list[datetime | None] = []

    async def fetch_entries(
        self,
        client: httpx.AsyncClient,
        *,
        updated_since: datetime | None = None,
    ) -> list[RegistryEntry]:
        del client
        self.watermarks.append(updated_since)
        if self.error:
            raise self.error
        return self.entries


@pytest.fixture
async def registry_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


async def _sync(
    factory: async_sessionmaker[AsyncSession],
    source: _Source,
    now: datetime,
) -> dict[str, int | str]:
    transport = httpx.MockTransport(lambda _request: httpx.Response(500))
    async with httpx.AsyncClient(transport=transport) as client:
        return await RegistrySourceSynchronizer(
            source,
            session_factory=factory,
            now=lambda: now,
        ).sync(client)


async def test_sync_is_idempotent_and_preserves_admin_security_decision(registry_factory) -> None:
    source = _Source([_entry()])
    first = await _sync(registry_factory, source, datetime(2026, 8, 3, 0, 0, 0))
    second = await _sync(registry_factory, source, datetime(2026, 8, 3, 1, 0, 0))

    assert first == {
        "source": "test-source",
        "entries": 1,
        "created": 1,
        "updated": 0,
        "hidden": 0,
    }
    assert second["created"] == 0

    async with registry_factory() as session:
        server = await session.get(ServerModel, "@mcp-registry/example.test/demo")
        assert server is not None
        server.security_level = "blocked"
        await session.commit()

    await _sync(
        registry_factory,
        _Source([_entry(version="1.1.0")]),
        datetime(2026, 8, 3, 2, 0, 0),
    )

    async with registry_factory() as session:
        servers = (await session.execute(select(ServerModel))).scalars().all()
        source_entries = (
            await session.execute(select(RegistrySourceEntryModel))
        ).scalars().all()
        assert len(servers) == 1
        assert len(source_entries) == 1
        assert servers[0].latest_version == "1.1.0"
        assert servers[0].security_level == "blocked"


async def test_deleted_upstream_entry_hides_catalog_but_preserves_user_relationships(
    registry_factory,
) -> None:
    await _sync(registry_factory, _Source([_entry()]), datetime(2026, 8, 3, 0, 0, 0))
    server_id = "@mcp-registry/example.test/demo"
    async with registry_factory() as session:
        session.add_all(
            [
                UserServerModel(user_id="alice", server_id=server_id, enabled=True),
                FavoriteModel(user_id="alice", server_id=server_id),
                ReviewModel(user_id="alice", server_id=server_id, rating=5, content="keep"),
            ]
        )
        await session.commit()

    await _sync(
        registry_factory,
        _Source([_entry(lifecycle_status="deleted")]),
        datetime(2026, 8, 3, 1, 0, 0),
    )

    async with registry_factory() as session:
        repo = ServerRepository(session)
        assert await repo.get_by_id(server_id) is None
        retained = await repo.get_by_id(server_id, include_hidden=True)
        assert retained is not None
        assert retained["catalog_status"] == "deleted"
        assert retained["registry"]["source"] == "test-source"
        assert retained["registry"]["upstream_id"] == "example.test/demo"
        assert retained["registry"]["status"] == "deleted"
        assert "endpoint_url" not in retained["registry"]
        assert (
            await session.execute(
                select(UserServerModel).where(UserServerModel.server_id == server_id)
            )
        ).scalar_one_or_none() is not None
        assert (
            await session.execute(select(FavoriteModel).where(FavoriteModel.server_id == server_id))
        ).scalar_one_or_none() is not None
        assert (
            await session.execute(select(ReviewModel).where(ReviewModel.server_id == server_id))
        ).scalar_one_or_none() is not None


async def test_failed_sync_does_not_advance_watermark(registry_factory) -> None:
    success_source = _Source([_entry()])
    success_at = datetime(2026, 8, 3, 0, 0, 0)
    await _sync(registry_factory, success_source, success_at)

    with pytest.raises(RuntimeError, match="registry unavailable"):
        await _sync(
            registry_factory,
            _Source([], RuntimeError("registry unavailable")),
            success_at + timedelta(hours=1),
        )

    follow_up = _Source([_entry(version="1.0.1")])
    await _sync(registry_factory, follow_up, success_at + timedelta(hours=2))

    assert follow_up.watermarks == [success_at - timedelta(minutes=5)]
    async with registry_factory() as session:
        state = await session.get(RegistrySourceStateModel, "test-source")
        assert state is not None
        assert state.last_success_at == success_at + timedelta(hours=2)
        assert state.last_error == ""
