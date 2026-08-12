"""Tests for safe parsing and cursor pagination of the official MCP Registry."""

from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest

from mcp_hub.core.registry_sources.official_mcp import OfficialMcpRegistrySource


def _official_server(
    name: str,
    *,
    remote: bool = False,
    deleted: bool = False,
) -> dict[str, object]:
    server: dict[str, object] = {
        "name": name,
        "title": "Example MCP",
        "description": "A registry supplied test server",
        "version": "1.2.3",
        "websiteUrl": "https://example.test/docs",
        "repository": {"url": "https://github.com/example/mcp"},
    }
    if remote:
        server["remotes"] = [
            {
                "type": "streamable-http",
                "url": "https://api.example.test/mcp",
                "headers": [{"name": "Authorization", "value": "not-for-export"}],
            }
        ]
    else:
        server["packages"] = [
            {
                "registryType": "npm",
                "identifier": "@example/mcp",
                "version": "1.2.3",
                "transport": {"type": "stdio"},
            }
        ]
    return {
        "server": server,
        "_meta": {
            "io.modelcontextprotocol.registry/official": {
                "status": "deleted" if deleted else "active",
                "publishedAt": "2026-08-01T12:00:00Z",
                "updatedAt": "2026-08-02T12:00:00Z",
            }
        },
    }


async def test_official_source_follows_cursor_and_uses_incremental_watermark() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params.get("cursor") == "page-two":
            payload = {"servers": [_official_server("example.test/second")], "metadata": {}}
        else:
            payload = {
                "servers": [_official_server("example.test/first")],
                "metadata": {"nextCursor": "page-two"},
            }
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        entries = await OfficialMcpRegistrySource().fetch_entries(
            client,
            updated_since=datetime(2026, 8, 2, 10, 0, 0),
        )

    assert [entry.upstream_id for entry in entries] == ["example.test/first", "example.test/second"]
    assert len(requests) == 2
    assert requests[0].url.path == "/v0.1/servers"
    assert requests[0].url.params["version"] == "latest"
    assert requests[0].url.params["limit"] == "100"
    assert requests[0].url.params["updated_since"] == "2026-08-02T10:00:00Z"
    assert "cursor" not in requests[0].url.params
    assert requests[1].url.params["cursor"] == "page-two"


async def test_official_source_rejects_unbounded_pagination() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "servers": [_official_server(f"example.test/{len(requests)}")],
                "metadata": {"nextCursor": f"page-{len(requests)}"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="exceeded 2 pages"):
            await OfficialMcpRegistrySource(max_pages=2).fetch_entries(client)

    assert len(requests) == 2


@pytest.mark.parametrize(
    ("payload", "expected_count"),
    [
        ({"servers": [_official_server("example.test/remote", remote=True)], "metadata": {}}, 1),
        (
            {
                "servers": [
                    {
                        "server": {
                            "name": "example.test/unsafe",
                            "remotes": [{"type": "streamable-http", "url": "https://api.example/{key}"}],
                        }
                    }
                ],
                "metadata": {},
            },
            1,
        ),
        (
            {
                "servers": [
                    {
                        "server": {
                            "name": "example.test/query",
                            "remotes": [
                                {
                                    "type": "streamable-http",
                                    "url": "https://api.example.test/mcp?token=unsafe",
                                }
                            ],
                        }
                    }
                ],
                "metadata": {},
            },
            1,
        ),
        ({"servers": [{"server": {"name": "not a valid id"}}], "metadata": {}}, 0),
    ],
)
async def test_official_source_keeps_only_safe_connection_material(
    payload: dict[str, object],
    expected_count: int,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(payload))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        entries = await OfficialMcpRegistrySource().fetch_entries(client)

    assert len(entries) == expected_count
    if not entries:
        return
    entry = entries[0]
    assert "Authorization" not in entry.config_template
    assert "not-for-export" not in json.dumps(entry.config_template)
    if entry.upstream_id == "example.test/remote":
        assert entry.install_command == ""
        assert entry.config_template == {
            "type": "streamable-http",
            "url": "https://api.example.test/mcp",
        }
    else:
        assert entry.config_template == {}
