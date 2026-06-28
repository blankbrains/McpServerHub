"""mcp init 命令测试。"""

from __future__ import annotations

from click.testing import CliRunner
from mcp_hub.cli.app import cli


def test_init_command_registered():
    """init 命令应被注册到 CLI。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert "init" in result.output
    assert "一键初始化" in result.output


def test_init_command_with_force():
    """init --help 应显示选项。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--help"])
    assert result.exit_code == 0
    assert "--force" in result.output
    assert "--db-url" in result.output
