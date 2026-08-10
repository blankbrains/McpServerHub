"""MCP Hub CLI 主入口。"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from typing import TextIO

import click

from mcp_hub import __version__


def _configure_cli_stream(stream: TextIO) -> None:
    """Keep legacy Windows consoles from crashing on unencodable UI symbols."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="replace")


_configure_cli_stream(sys.stdout)
_configure_cli_stream(sys.stderr)


@dataclass(frozen=True)
class LazyCommand:
    module: str
    attribute: str
    help: str


COMMANDS: dict[str, LazyCommand] = {
    "agent": LazyCommand("mcp_hub.cli.agent", "agent", "配置、检查和迁移本地 Agent Gateway。"),
    "analyze": LazyCommand("mcp_hub.cli.token", "analyze", "估算 MCP Server 工具定义 Token。"),
    "compare": LazyCommand("mcp_hub.cli.search", "compare", "并排比较 MCP Server。"),
    "config": LazyCommand("mcp_hub.cli.config", "config", "管理配置、草稿和 Gateway 同步。"),
    "create": LazyCommand("mcp_hub.cli.create", "create", "创建 MCP Server 项目。"),
    "daemon": LazyCommand("mcp_hub.cli.daemon", "daemon", "管理 Hub 后台服务。"),
    "event": LazyCommand("mcp_hub.cli.event", "event", "管理事件订阅。"),
    "favorite": LazyCommand("mcp_hub.cli.community", "favorite", "收藏或取消收藏 Server。"),
    "favorites": LazyCommand("mcp_hub.cli.community", "favorites", "列出收藏的 Server。"),
    "hub-install": LazyCommand("mcp_hub.cli.hub_install", "hub_install", "安装 Hub 集成。"),
    "info": LazyCommand("mcp_hub.cli.search", "info", "查看 Server 详情。"),
    "init": LazyCommand("mcp_hub.cli.init_cmd", "init_cmd", "一键初始化完整 Hub 配置。"),
    "install": LazyCommand("mcp_hub.cli.install", "install", "安装自托管 MCP Server。"),
    "list": LazyCommand("mcp_hub.cli.install", "list_servers", "列出已安装 Server。"),
    "login": LazyCommand("mcp_hub.cli.auth", "login", "使用 GitHub 登录。"),
    "logout": LazyCommand("mcp_hub.cli.auth", "logout", "退出当前登录。"),
    "logs": LazyCommand("mcp_hub.cli.logs", "logs", "查看自托管 Server 日志。"),
    "monitor": LazyCommand("mcp_hub.cli.monitor", "monitor", "监控自托管 Server。"),
    "most-downloaded": LazyCommand(
        "mcp_hub.cli.trending", "most_downloaded", "查看采用次数最多的 Server。"
    ),
    "my-servers": LazyCommand("mcp_hub.cli.publish", "my_servers", "查看自己发布的 Server。"),
    "new-releases": LazyCommand("mcp_hub.cli.trending", "new_releases", "查看最新 Server。"),
    "optimize": LazyCommand("mcp_hub.cli.token", "optimize", "生成工具定义优化建议。"),
    "prompt-install": LazyCommand(
        "mcp_hub.cli.prompt_install", "prompt_install", "生成 Agent 安装提示。"
    ),
    "publish": LazyCommand("mcp_hub.cli.publish", "publish", "发布 MCP Server。"),
    "quickstart": LazyCommand(
        "mcp_hub.cli.quickstart", "quickstart", "使用本地 SQLite 快速启动 Hub。"
    ),
    "rate": LazyCommand("mcp_hub.cli.community", "rate", "为 Server 评分。"),
    "registry-sync": LazyCommand(
        "mcp_hub.cli.registry_sync", "registry_sync", "同步市场注册表。"
    ),
    "reliability": LazyCommand("mcp_hub.cli.monitor", "reliability", "查看可靠性统计。"),
    "restart": LazyCommand("mcp_hub.cli.manage", "restart", "重启自托管 Server。"),
    "review": LazyCommand("mcp_hub.cli.community", "review", "提交 Server 评价。"),
    "rollback": LazyCommand("mcp_hub.cli.update", "rollback", "回滚 Server 版本。"),
    "search": LazyCommand("mcp_hub.cli.search", "search", "搜索 MCP Server 市场。"),
    "security": LazyCommand("mcp_hub.cli.security", "security", "扫描 Server 安全风险。"),
    "serve": LazyCommand("mcp_hub.cli.daemon", "serve", "启动本地 MCP Gateway。"),
    "start": LazyCommand("mcp_hub.cli.manage", "start", "启动自托管 Server。"),
    "stats": LazyCommand("mcp_hub.cli.publish", "stats", "查看发布统计。"),
    "status": LazyCommand("mcp_hub.cli.manage", "status_cmd", "查看自托管 Server 状态。"),
    "stop": LazyCommand("mcp_hub.cli.manage", "stop", "停止自托管 Server。"),
    "top-rated": LazyCommand("mcp_hub.cli.trending", "top_rated", "查看高评分 Server。"),
    "trending": LazyCommand("mcp_hub.cli.trending", "trending", "查看热门 Server。"),
    "uninstall": LazyCommand("mcp_hub.cli.install", "uninstall", "卸载自托管 Server。"),
    "unpublish": LazyCommand("mcp_hub.cli.publish", "unpublish", "下架已发布 Server。"),
    "update": LazyCommand("mcp_hub.cli.update", "update", "更新已安装 Server。"),
    "upgrade": LazyCommand("mcp_hub.cli.update", "upgrade", "升级已安装 Server。"),
    "version-history": LazyCommand(
        "mcp_hub.cli.update", "version_history", "查看 Server 版本历史。"
    ),
    "whoami": LazyCommand("mcp_hub.cli.auth", "whoami", "查看当前登录用户。"),
}


class LazyGroup(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        del ctx
        return sorted(COMMANDS)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        del ctx
        command_spec = COMMANDS.get(cmd_name)
        if command_spec is None:
            return None
        module = importlib.import_module(command_spec.module)
        command = getattr(module, command_spec.attribute)
        if not isinstance(command, click.Command):
            raise TypeError(
                f"{command_spec.module}.{command_spec.attribute} is not a Click command"
            )
        return command

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        del ctx
        rows = [(name, COMMANDS[name].help) for name in sorted(COMMANDS)]
        if rows:
            with formatter.section("Commands"):
                formatter.write_dl(rows)


@click.group(cls=LazyGroup)
@click.version_option(version=__version__, prog_name="mcp-hub")
def cli() -> None:
    """MCP Server Hub —— 发现 · 配置 · 代理 · 监控 · 发布 MCP Server"""


if __name__ == "__main__":
    cli()
