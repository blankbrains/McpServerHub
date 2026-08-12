"""Adapter contract placeholder for future community catalog imports."""

from __future__ import annotations

from datetime import datetime

import httpx

from mcp_hub.core.registry_sources.base import RegistryEntry


class CommunityRegistrySource:
    """A non-network source reserved for reviewed community catalog imports."""

    source_name = "community"

    async def fetch_entries(
        self,
        client: httpx.AsyncClient,
        *,
        updated_since: datetime | None = None,
    ) -> list[RegistryEntry]:
        del client, updated_since
        return []
