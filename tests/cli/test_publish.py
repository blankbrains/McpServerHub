"""CLI publish 命令测试。"""
from __future__ import annotations

from click.testing import CliRunner

from mcp_hub.cli.app import cli


def test_my_servers_command_registered():
    """my-servers 命令应注册到 CLI。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["my-servers", "--help"])
    assert result.exit_code == 0
    assert "查看我发布的 Server" in result.output
    assert "AUTHOR" in result.output


def test_my_servers_no_author():
    """未指定 author 时输出提示。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["my-servers"])
    assert "请指定发布者名称" in result.output


def test_unpublish_command_registered():
    """unpublish 命令应注册到 CLI。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["unpublish", "--help"])
    assert result.exit_code == 0
    assert "下架 Server" in result.output


def test_stats_command_with_history():
    """stats --help 应显示 --history 选项。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["stats", "--help"])
    assert result.exit_code == 0
    assert "--history" in result.output
