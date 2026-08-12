"""Adapter for the public Model Context Protocol official Registry API."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from mcp_hub.core.registry_sources.base import RegistryEntry

_OFFICIAL_METADATA_KEY = "io.modelcontextprotocol.registry/official"
_UPSTREAM_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+$")
_NPM_PACKAGE_PATTERN = re.compile(
    r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$",
    re.IGNORECASE,
)
_SAFE_TRANSPORTS = {"streamable-http", "sse"}
_PAGE_SIZE = 100
_MAX_PAGES = 500


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _format_timestamp(value: datetime) -> str:
    normalized = value.replace(tzinfo=timezone.utc)
    return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    url = value.strip()
    if not url or any(token in url for token in ("{", "}", "${")):
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        return ""
    return url


def _transport_type(raw: object) -> str:
    value: object
    if isinstance(raw, str):
        value = raw
    elif isinstance(raw, dict):
        value = raw.get("type", raw.get("transport", ""))
    else:
        value = ""
    return str(value).strip().lower().replace("_", "-")


def _safe_npm_install(packages: object) -> tuple[str, str, str, str]:
    """Return only a complete, stdio npm install instruction."""
    if not isinstance(packages, list):
        return "", "", "", ""
    for raw_package in packages:
        if not isinstance(raw_package, dict):
            continue
        if str(raw_package.get("registryType", "")).strip().lower() != "npm":
            continue
        identifier = str(raw_package.get("identifier", "")).strip()
        version = str(raw_package.get("version", "")).strip()
        transport = _transport_type(raw_package.get("transport"))
        runtime_arguments = raw_package.get("runtimeArguments")
        package_arguments = raw_package.get("packageArguments")
        if (
            not identifier
            or not _NPM_PACKAGE_PATTERN.fullmatch(identifier)
            or not version
            or transport != "stdio"
            or runtime_arguments
            or package_arguments
        ):
            continue
        package_spec = f"{identifier}@{version}"
        return "npm", identifier, version, f"npx -y {package_spec}"
    return "", "", "", ""


def _safe_remote_config(remotes: object) -> tuple[str, str, dict[str, str]]:
    """Choose one public, fixed remote endpoint without forwarding auth metadata."""
    if not isinstance(remotes, list):
        return "", "", {}
    for raw_remote in remotes:
        if not isinstance(raw_remote, dict):
            continue
        transport = _transport_type(raw_remote.get("type", raw_remote.get("transport")))
        url = _safe_url(raw_remote.get("url"))
        if transport in _SAFE_TRANSPORTS and url:
            return transport, url, {"type": transport, "url": url}
    return "", "", {}


def _entry_from_payload(raw: object) -> RegistryEntry | None:
    if not isinstance(raw, dict):
        return None
    server = raw.get("server")
    if not isinstance(server, dict):
        return None

    upstream_id = str(server.get("name", "")).strip()
    if not _UPSTREAM_ID_PATTERN.fullmatch(upstream_id):
        return None
    if len(f"@mcp-registry/{upstream_id}") > 255:
        return None

    title = str(server.get("title", "")).strip()
    name = upstream_id.rsplit("/", 1)[-1]
    display_name = title[:255] if title else name
    description = str(server.get("description", "")).strip()[:10_000]
    version = str(server.get("version", "")).strip()[:50]

    repository = server.get("repository")
    repository_url = _safe_url(repository.get("url")) if isinstance(repository, dict) else ""
    homepage = _safe_url(server.get("websiteUrl"))
    package_type, package_identifier, package_version, install_command = _safe_npm_install(
        server.get("packages")
    )
    transport, endpoint_url, config_template = _safe_remote_config(server.get("remotes"))

    metadata = raw.get("_meta")
    official_metadata = (
        metadata.get(_OFFICIAL_METADATA_KEY, {}) if isinstance(metadata, dict) else {}
    )
    if not isinstance(official_metadata, dict):
        official_metadata = {}
    lifecycle_status = str(official_metadata.get("status", "active")).strip().lower()
    if lifecycle_status not in {"active", "deprecated", "deleted"}:
        lifecycle_status = "active"

    return RegistryEntry(
        source=OfficialMcpRegistrySource.source_name,
        upstream_id=upstream_id,
        name=name,
        display_name=display_name,
        description=description,
        version=version,
        package_type=package_type,
        package_identifier=package_identifier,
        package_version=package_version,
        install_type="npx" if install_command else "",
        install_command=install_command,
        repository_url=repository_url,
        homepage=homepage,
        transport=transport,
        endpoint_url=endpoint_url,
        config_template=config_template,
        lifecycle_status=lifecycle_status,
        lifecycle_message=str(official_metadata.get("statusMessage", "")).strip()[:500],
        published_at=_parse_timestamp(official_metadata.get("publishedAt")),
        updated_at=_parse_timestamp(official_metadata.get("updatedAt")),
    )


class OfficialMcpRegistrySource:
    """Fetch the official Registry with bounded cursor pagination."""

    source_name = "official_mcp"

    def __init__(
        self,
        base_url: str = "https://registry.modelcontextprotocol.io",
        *,
        max_pages: int = _MAX_PAGES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_pages = max_pages

    async def fetch_entries(
        self,
        client: httpx.AsyncClient,
        *,
        updated_since: datetime | None = None,
    ) -> list[RegistryEntry]:
        cursor: str | None = None
        entries: list[RegistryEntry] = []
        seen_upstream_ids: set[str] = set()

        for _page in range(self.max_pages):
            params: dict[str, str] = {
                "version": "latest",
                "limit": str(_PAGE_SIZE),
            }
            if cursor:
                params["cursor"] = cursor
            if updated_since:
                params["updated_since"] = _format_timestamp(updated_since)

            response = await client.get(
                f"{self.base_url}/v0.1/servers",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Official MCP Registry returned a non-object response")

            raw_servers = payload.get("servers", [])
            if not isinstance(raw_servers, list):
                raise ValueError("Official MCP Registry returned an invalid server list")
            for raw_server in raw_servers:
                entry = _entry_from_payload(raw_server)
                if entry and entry.upstream_id not in seen_upstream_ids:
                    entries.append(entry)
                    seen_upstream_ids.add(entry.upstream_id)

            metadata = payload.get("metadata", {})
            next_cursor = metadata.get("nextCursor") if isinstance(metadata, dict) else None
            if not isinstance(next_cursor, str) or not next_cursor:
                return entries
            if next_cursor == cursor:
                raise ValueError("Official MCP Registry returned a repeated pagination cursor")
            cursor = next_cursor

        raise ValueError(f"Official MCP Registry exceeded {self.max_pages} pages")
