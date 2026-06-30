"""CLI manage 命令测试。"""
from __future__ import annotations

from click.testing import CliRunner

from mcp_hub.cli.app import cli


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
