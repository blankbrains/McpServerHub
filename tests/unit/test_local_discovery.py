"""Local MCP configuration discovery regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from mcp_hub.core.local_discovery import LocalAgentDiscovery


async def test_discovery_reports_non_object_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / "mcp.json"
    config_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    discovery = LocalAgentDiscovery(
        {
            "test-agent": {
                "name": "Test Agent",
                "paths": [config_path],
                "format": "json",
                "server_key": "mcpServers",
            }
        }
    )

    result = await discovery.discover_all()

    assert result.total_agents_found == 1
    assert result.agents[0].paths_found == [str(config_path)]
    assert result.agents[0].server_names == []
    assert result.agents[0].error == "配置文件 JSON 解析失败: 配置文件根节点必须是对象"


async def test_discovery_deduplicates_servers_across_candidate_paths(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(
        json.dumps({"mcpServers": {"weather": {"command": "first"}}}),
        encoding="utf-8",
    )
    second_path.write_text(
        json.dumps({"mcpServers": {"weather": {"command": "second"}}}),
        encoding="utf-8",
    )
    discovery = LocalAgentDiscovery(
        {
            "test-agent": {
                "name": "Test Agent",
                "paths": [first_path, second_path],
                "format": "json",
                "server_key": "mcpServers",
            }
        }
    )

    result = await discovery.discover_all()

    assert result.agents[0].server_names == ["weather"]
    assert result.agents[0].server_details["weather"]["command"] == "second"
