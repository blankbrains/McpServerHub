"""Adapter contract placeholder for future local catalog imports."""

from __future__ import annotations

from datetime import datetime

import httpx

from mcp_hub.core.registry_sources.base import RegistryEntry


class LocalRegistrySource:
    """A non-network source reserved for explicit local catalog imports."""

    source_name = "local"

    async def fetch_entries(
        self,
        client: httpx.AsyncClient,
        *,
        updated_since: datetime | None = None,
    ) -> list[RegistryEntry]:
        del client, updated_since
        return []
