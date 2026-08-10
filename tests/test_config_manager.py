import pytest

from mcp_hub.core.config_manager import get_config_for_agent


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
