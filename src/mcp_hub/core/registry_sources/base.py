"""Contracts shared by catalog registry sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx


@dataclass(frozen=True)
class RegistryEntry:
    """Safe, source-owned catalog metadata for one upstream MCP Server."""

    source: str
    upstream_id: str
    name: str
    display_name: str
    description: str
    version: str
    package_type: str
    package_identifier: str
    package_version: str
    install_type: str
    install_command: str
    repository_url: str
    homepage: str
    transport: str
    endpoint_url: str
    config_template: dict[str, str]
    lifecycle_status: str
    lifecycle_message: str
    published_at: datetime | None
    updated_at: datetime | None


class RegistrySource(Protocol):
    """A source adapter that can incrementally enumerate catalog entries."""

    source_name: str

    async def fetch_entries(
        self,
        client: httpx.AsyncClient,
        *,
        updated_since: datetime | None = None,
    ) -> list[RegistryEntry]:
        """Fetch a complete, validated change set or raise without partial results."""
