from pathlib import Path

import pytest

from mcp_hub.core.config_manager import get_config_for_agent


@pytest.mark.parametrize(
    ("agent", "config_path", "server_key", "requires_stdio_type"),
    [
        (
            "claude-code",
            Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
            "mcpServers",
            False,
        ),
        (
            "vscode-copilot",
            Path.home() / ".copilot" / "mcp-config.json",
            "servers",
            True,
        ),
        (
            "windsurf",
            Path.home() / ".codeium" / "windsurf" / "mcp_config.json",
            "mcpServers",
            False,
        ),
    ],
)
def test_get_config_for_agent_uses_agent_specific_mcp_format(
    agent: str,
    config_path: Path,
    server_key: str,
    requires_stdio_type: bool,
) -> None:
    result = get_config_for_agent(
        server_name="example-server",
        command="npx -y @example/mcp-server --mode readonly",
        agent=agent,
    )

    server_config = result["config_content"][server_key]["example-server"]

    assert result["config_path"] == str(config_path)
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
