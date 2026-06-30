"""CLI install 命令测试。"""
from __future__ import annotations

from click.testing import CliRunner

from mcp_hub.cli.app import cli


def test_install_command_registered():
    """install 命令应注册到 CLI。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["install", "--help"])
    assert result.exit_code == 0
    assert "安装" in result.output


def test_install_with_dry_run_flag():
    """install --help 应显示 --dry-run 选项。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["install", "--help"])
    assert "--dry-run" in result.output
    assert "预览模式" in result.output


def test_install_with_force_flag():
    """install --help 应显示 --force 选项。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["install", "--help"])
    assert "--force" in result.output


def test_install_no_args_shows_help():
    """不带参数运行 install 应提示用法。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["install"])
    assert result.exit_code != 0 or "Usage" in result.output or "SERVER_IDS" in result.output
