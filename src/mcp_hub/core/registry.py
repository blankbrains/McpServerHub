"""MCP Server 注册与索引管理。"""

from __future__ import annotations

from typing import Any

from mcp_hub.db.repositories import ServerRepository
from mcp_hub.db.database import async_session_factory


class Registry:
    """Server 注册与搜索服务。"""

    async def search(
        self,
        q: str = "",
        category: str | None = None,
        tag: str | None = None,
        sort: str = "hot",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            return await repo.search(q, category, tag, sort, page, page_size)

    async def get_by_id(self, server_id: str) -> dict | None:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            return await repo.get_by_id(server_id)

    async def get_installed(self) -> list[dict]:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            return await repo.get_installed()

    async def update_status(self, server_id: str, status: str) -> bool:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            return await repo.update_status(server_id, status)

    async def increment_download(self, server_id: str) -> None:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            await repo.increment_download(server_id)

    async def get_trending(self, limit: int = 20) -> list[dict]:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            return await repo.get_trending(limit)

    async def get_top_rated(self, limit: int = 20) -> list[dict]:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            return await repo.get_top_rated(limit)

    async def get_new_releases(self, limit: int = 20) -> list[dict]:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            return await repo.get_new_releases(limit)

    async def register_server(self, server_data: dict) -> str:
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            return await repo.register_server(server_data)
