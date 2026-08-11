import json

import pytest

from mcp_hub.core.config_manager import ConfigManager, get_config_for_agent

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib


@pytest.mark.parametrize(
    ("agent", "config_path", "server_key", "requires_stdio_type"),
    [
        (
            "claude-code",
            "~/.claude.json",
            "mcpServers",
            False,
        ),
        (
            "codex",
            "~/.codex/config.toml",
            "mcp_servers",
            False,
        ),
        (
            "vscode-copilot",
            ".vscode/mcp.json",
            "servers",
            True,
        ),
        (
            "windsurf",
            "~/.codeium/windsurf/mcp_config.json",
            "mcpServers",
            False,
        ),
    ],
)
def test_get_config_for_agent_uses_agent_specific_mcp_format(
    agent: str,
    config_path: str,
    server_key: str,
    requires_stdio_type: bool,
) -> None:
    result = get_config_for_agent(
        server_name="example-server",
        command="npx -y @example/mcp-server --mode readonly",
        agent=agent,
    )

    server_config = result["config_content"][server_key]["example-server"]

    assert result["config_path"] == config_path
    assert result["config_format"] == ("toml" if agent == "codex" else "json")
    assert server_config["command"] == "npx"
    assert server_config["args"] == [
        "-y",
        "@example/mcp-server",
        "--mode",
        "readonly",
    ]
    assert ("type" in server_config) is requires_stdio_type
    if requires_stdio_type:
        assert server_config["type"] == "stdio"
    if agent == "codex":
        assert '[mcp_servers.example-server]' in result["config_text"]
        assert 'command = "npx"' in result["config_text"]
    else:
        assert f'"{server_key}"' in result["config_text"]


@pytest.mark.parametrize(
    ("agent", "server_key", "config_format"),
    [
        ("cursor", "mcpServers", "json"),
        ("codex", "mcp_servers", "toml"),
    ],
)
async def test_list_config_serializes_environment_variables(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    agent: str,
    server_key: str,
    config_format: str,
) -> None:
    from mcp_hub.core.registry import Registry

    async def get_by_id(_registry: Registry, server_id: str) -> dict[str, str]:
        return {
            "id": server_id,
            "install_command": "npx -y @example/mcp-server",
        }

    monkeypatch.setattr(Registry, "get_by_id", get_by_id)
    manager = ConfigManager(tmp_path)
    server_id = "@example/example-server"

    assert await manager.set_config(server_id, "EXAMPLE_TOKEN", "redacted-test-value")
    result = await manager.list_config(server_id, agent)

    server_config = result["config_content"][server_key]["example-server"]
    serialized = (
        tomllib.loads(result["config_text"])
        if config_format == "toml"
        else json.loads(result["config_text"])
    )

    assert server_config["env"] == {"EXAMPLE_TOKEN": "redacted-test-value"}
    assert serialized[server_key]["example-server"]["env"] == server_config["env"]
