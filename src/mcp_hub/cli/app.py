"""MCP Hub CLI 主入口。"""

from __future__ import annotations

import click

from mcp_hub import __version__


@click.group()
@click.version_option(version=__version__, prog_name="mcp-hub")
def cli():
    """MCP Server Hub —— 发现 · 安装 · 管理 · 发布 MCP Server"""


# Import and register all subcommands
from mcp_hub.cli.search import search, info, compare
from mcp_hub.cli.install import install, uninstall, list_servers
from mcp_hub.cli.manage import start, stop, restart, status_cmd
from mcp_hub.cli.logs import logs
from mcp_hub.cli.update import update, rollback
from mcp_hub.cli.config import config
from mcp_hub.cli.daemon import daemon, serve
from mcp_hub.cli.init_cmd import init_cmd
from mcp_hub.cli.publish import publish, my_servers, unpublish, stats
from mcp_hub.cli.community import rate, review, favorite, favorites
from mcp_hub.cli.trending import trending, top_rated, most_downloaded, new_releases
from mcp_hub.cli.event import event
from mcp_hub.cli.auth import login, logout, whoami


cli.add_command(search)
cli.add_command(info)
cli.add_command(compare)
cli.add_command(install)
cli.add_command(uninstall)
cli.add_command(list_servers)
cli.add_command(start)
cli.add_command(stop)
cli.add_command(restart)
cli.add_command(status_cmd)
cli.add_command(logs)
cli.add_command(update)
cli.add_command(rollback)
cli.add_command(config)
cli.add_command(daemon)
cli.add_command(serve)
cli.add_command(init_cmd)
cli.add_command(publish)
cli.add_command(my_servers)
cli.add_command(unpublish)
cli.add_command(stats)
cli.add_command(rate)
cli.add_command(review)
cli.add_command(favorite)
cli.add_command(favorites)
cli.add_command(trending)
cli.add_command(top_rated)
cli.add_command(most_downloaded)
cli.add_command(new_releases)
cli.add_command(event)
cli.add_command(login)
cli.add_command(logout)
cli.add_command(whoami)


if __name__ == "__main__":
    cli()
