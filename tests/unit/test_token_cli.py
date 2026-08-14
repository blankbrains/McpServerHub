"""Token analysis CLI regression tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from click.testing import CliRunner

import mcp_hub.cli.token as token_cli


def test_deep_analysis_uses_gateway_probe_and_reports_live_tools(monkeypatch) -> None:
    server_id = "@community/demo"
    server = {
        "id": server_id,
        "description": "Demo MCP Server",
        "tool_definitions": [],
    }

    class FakeRegistry:
        async def get_by_id(self, requested_id: str) -> dict[str, object] | None:
            assert requested_id == server_id
            return server

    class FakeGateway:
        last_instance: FakeGateway | None = None

        def __init__(self) -> None:
            self.inspect_server_tools = AsyncMock(
                return_value=[
                    {
                        "name": "echo",
                        "description": "Echo text",
                        "inputSchema": {"type": "object"},
                    }
                ]
            )
            FakeGateway.last_instance = self

    monkeypatch.setattr(token_cli, "Registry", FakeRegistry)
    monkeypatch.setattr(token_cli, "McpGateway", FakeGateway)

    result = CliRunner().invoke(
        token_cli.analyze,
        [server_id, "--deep", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["server_id"] == server_id
    assert payload["estimated"] is False
    assert payload["tools"][0]["name"] == "echo"
    assert FakeGateway.last_instance is not None
    FakeGateway.last_instance.inspect_server_tools.assert_awaited_once_with(server_id)
