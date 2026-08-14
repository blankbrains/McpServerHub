"""Safe, source-owned catalog synchronization."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mcp_hub.core.registry_sources.base import RegistryEntry, RegistrySource
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import (
    RegistrySourceEntryModel,
    RegistrySourceStateModel,
    ServerModel,
)

_SYNC_OVERLAP = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.utcnow()


def _catalog_server_id(entry: RegistryEntry) -> str:
    return f"@mcp-registry/{entry.upstream_id}"


def _entry_tags(entry: RegistryEntry) -> str:
    tags = ["mcp-registry", entry.source]
    if entry.package_type:
        tags.append(entry.package_type)
    if entry.transport:
        tags.append(entry.transport)
    return json.dumps(tags)


def _is_visible(entry: RegistryEntry) -> bool:
    return entry.lifecycle_status != "deleted"


class RegistrySourceSynchronizer:
    """Synchronize one Registry source without overwriting user-owned data."""

    def __init__(
        self,
        source: RegistrySource,
        *,
        session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self.source = source
        self.session_factory = session_factory
        self.now = now

    async def sync(self, client: httpx.AsyncClient) -> dict[str, int | str]:
        """Fetch first, then atomically persist source-owned fields and watermark."""
        state = await self._record_attempt()
        watermark = (
            state.last_success_at - _SYNC_OVERLAP if state and state.last_success_at else None
        )
        try:
            entries = await self.source.fetch_entries(client, updated_since=watermark)
        except Exception as exc:
            await self._record_failure(str(exc))
            raise

        async with self.session_factory() as session:
            state = await session.get(RegistrySourceStateModel, self.source.source_name)
            if state is None:
                state = RegistrySourceStateModel(source=self.source.source_name)
                session.add(state)

            created = 0
            updated = 0
            hidden = 0
            for entry in entries:
                did_create, did_hide = await self._upsert_entry(session, entry)
                created += int(did_create)
                updated += int(not did_create)
                hidden += int(did_hide)

            state.last_success_at = self.now()
            state.last_attempt_at = state.last_success_at
            state.last_error = ""
            state.last_entry_count = len(entries)
            await session.commit()

        return {
            "source": self.source.source_name,
            "entries": len(entries),
            "created": created,
            "updated": updated,
            "hidden": hidden,
        }

    async def _record_attempt(self) -> RegistrySourceStateModel | None:
        async with self.session_factory() as session:
            state = await session.get(RegistrySourceStateModel, self.source.source_name)
            if state is None:
                state = RegistrySourceStateModel(source=self.source.source_name)
                session.add(state)
            state.last_attempt_at = self.now()
            await session.commit()
            return state

    async def _record_failure(self, error: str) -> None:
        async with self.session_factory() as session:
            state = await session.get(RegistrySourceStateModel, self.source.source_name)
            if state is None:
                state = RegistrySourceStateModel(source=self.source.source_name)
                session.add(state)
            state.last_attempt_at = self.now()
            state.last_error = error[:500]
            await session.commit()

    async def _upsert_entry(
        self,
        session: AsyncSession,
        entry: RegistryEntry,
    ) -> tuple[bool, bool]:
        if entry.source != self.source.source_name:
            raise ValueError("Registry entry source does not match the synchronizer")

        source_entry_result = await session.execute(
            select(RegistrySourceEntryModel).where(
                RegistrySourceEntryModel.source == entry.source,
                RegistrySourceEntryModel.upstream_id == entry.upstream_id,
            )
        )
        source_entry = source_entry_result.scalar_one_or_none()
        server_id = source_entry.server_id if source_entry else _catalog_server_id(entry)
        server = await session.get(ServerModel, server_id)

        if server is not None and (
            server.catalog_source not in ("", entry.source)
            or (
                server.catalog_source == ""
                and server.catalog_source_id not in ("", entry.upstream_id)
            )
        ):
            raise ValueError(f"Catalog server ID collision for {server_id}")

        created = server is None
        if server is None:
            server = ServerModel(
                id=server_id,
                name=entry.name,
                display_name=entry.display_name,
                description=entry.description,
                author=entry.upstream_id.split("/", 1)[0],
                categories=json.dumps(["tools"]),
                tags=_entry_tags(entry),
                install_type=entry.install_type,
                install_package=entry.package_identifier,
                install_command=entry.install_command,
                config_template=json.dumps(entry.config_template),
                homepage=entry.homepage or entry.repository_url,
                current_version="",
                latest_version=entry.version,
                catalog_source=entry.source,
                catalog_source_id=entry.upstream_id,
                catalog_status=entry.lifecycle_status,
                market_visible=_is_visible(entry),
                security_level="unreviewed",
                network_access=bool(entry.transport),
            )
            session.add(server)
        else:
            self._update_source_owned_server_fields(server, entry)

        if source_entry is None:
            source_entry = RegistrySourceEntryModel(
                source=entry.source,
                upstream_id=entry.upstream_id,
                server_id=server_id,
            )
            session.add(source_entry)
        self._update_source_entry_fields(source_entry, entry)
        return created, not _is_visible(entry)

    @staticmethod
    def _update_source_owned_server_fields(server: ServerModel, entry: RegistryEntry) -> None:
        """Only update values that belong to the source, never user/admin signals."""
        server.name = entry.name
        server.display_name = entry.display_name
        server.description = entry.description
        server.author = entry.upstream_id.split("/", 1)[0]
        server.tags = _entry_tags(entry)
        server.install_type = entry.install_type
        server.install_package = entry.package_identifier
        server.install_command = entry.install_command
        server.config_template = json.dumps(entry.config_template)
        server.homepage = entry.homepage or entry.repository_url
        server.latest_version = entry.version
        server.catalog_source = entry.source
        server.catalog_source_id = entry.upstream_id
        server.catalog_status = entry.lifecycle_status
        # Upstream lifecycle can hide a Server, but an administrator block must
        # remain authoritative across later registry refreshes.
        server.market_visible = (
            _is_visible(entry) and server.security_level != "blocked"
        )
        server.network_access = bool(entry.transport)

    def _update_source_entry_fields(
        self,
        source_entry: RegistrySourceEntryModel,
        entry: RegistryEntry,
    ) -> None:
        source_entry.upstream_version = entry.version
        source_entry.package_type = entry.package_type
        source_entry.package_identifier = entry.package_identifier
        source_entry.package_version = entry.package_version
        source_entry.repository_url = entry.repository_url
        source_entry.transport = entry.transport
        source_entry.endpoint_url = entry.endpoint_url
        source_entry.lifecycle_status = entry.lifecycle_status
        source_entry.lifecycle_message = entry.lifecycle_message
        source_entry.published_at = entry.published_at
        source_entry.upstream_updated_at = entry.updated_at
        source_entry.last_synced_at = self.now()
