"""CLI manage 命令测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from click.testing import CliRunner

from mcp_hub.cli.app import cli
from mcp_hub.cli.manage import _spawn_configured_server


def test_start_all_help():
    """start --help 应显示 all 支持信息。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["start", "--help"])
    assert result.exit_code == 0
    assert "启动" in result.output
    assert "all" in result.output


def test_stop_all_help():
    """stop --help 应显示 all 支持信息。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["stop", "--help"])
    assert result.exit_code == 0
    assert "停止" in result.output


def test_status_help():
    """status --help 应该正常。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--help"])
    assert result.exit_code == 0


async def test_spawn_configured_server_preserves_quotes_and_server_env(monkeypatch) -> None:
    process_manager = MagicMock()
    process_manager.spawn = AsyncMock()
    monkeypatch.setattr(
        "mcp_hub.cli.manage.ConfigManager.list_all_config",
        AsyncMock(return_value={"API_KEY": "secret"}),
    )

    await _spawn_configured_server(
        process_manager,
        "@example/weather",
        'npx -y @example/weather --label "New York"',
    )

    process_manager.spawn.assert_awaited_once_with(
        "@example/weather",
        "npx",
        ["-y", "@example/weather", "--label", "New York"],
        env={"API_KEY": "secret"},
    )
