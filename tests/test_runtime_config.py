from __future__ import annotations

from mcp_hub.core.config_manager import get_config_for_agent
from mcp_hub.exceptions import ConfigError
from mcp_hub.runtime_config import (
    has_runnable_server_config,
    is_install_only_command,
    is_legacy_inferred_github_command,
)


def test_install_only_commands_are_not_treated_as_mcp_runtime_commands() -> None:
    for command in (
        "pip install example-mcp",
        "python -m pip install example-mcp",
        "npm install -g example-mcp",
        "go install github.com/example/mcp-server@latest",
    ):
        assert is_install_only_command(command)
        assert not has_runnable_server_config(command)


def test_direct_runtime_commands_and_structured_remotes_remain_exportable() -> None:
    assert has_runnable_server_config("npx -y @example/mcp-server")
    assert has_runnable_server_config("uvx example-mcp")
    assert has_runnable_server_config(
        "",
        {"type": "streamable-http", "url": "https://example.test/mcp"},
    )


def test_install_only_command_cannot_be_written_into_agent_configuration() -> None:
    try:
        get_config_for_agent(
            "example-mcp",
            "go install github.com/example/mcp-server@latest",
        )
    except ConfigError as error:
        assert "只有安装说明" in str(error)
    else:
        raise AssertionError("installation-only command was exported as runtime config")


def test_legacy_github_install_guess_is_identified_without_touching_other_commands() -> None:
    assert is_legacy_inferred_github_command(
        "@github/github/github-mcp-server",
        "github/github-mcp-server",
        "go install github/github-mcp-server@latest",
    )
    assert not is_legacy_inferred_github_command(
        "@github/github/github-mcp-server",
        "github/github-mcp-server",
        "mcp-server --stdio",
    )
