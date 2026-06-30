"""CLI event 命令测试。"""
from __future__ import annotations

from click.testing import CliRunner

from mcp_hub.cli.app import cli


def test_event_history_command_registered():
    """event history 命令应注册到 CLI。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["event", "history", "--help"])
    assert result.exit_code == 0
    assert "查看事件历史" in result.output
    assert "--limit" in result.output


def test_event_history_no_data():
    """event history 不再显示"开发中"。"""
    runner = CliRunner()
    result = runner.invoke(cli, ["event", "history"])
    # 不应显示旧的 stub 提示
    assert "开发中" not in result.output
