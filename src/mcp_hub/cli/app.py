"""MCP Hub CLI 主入口。"""

from __future__ import annotations

import click

from mcp_hub import __version__


@click.group()
@click.version_option(version=__version__, prog_name="mcp-hub")
def cli():
    """MCP Server Hub —— 发现 · 安装 · 管理 · 发布 MCP Server"""


# Import and register all subcommands
from mcp_hub.cli.auth import login, logout, whoami  # noqa: E402
from mcp_hub.cli.community import favorite, favorites, rate, review  # noqa: E402
from mcp_hub.cli.config import config  # noqa: E402
from mcp_hub.cli.daemon import daemon, serve  # noqa: E402
from mcp_hub.cli.event import event  # noqa: E402
from mcp_hub.cli.hub_install import hub_install  # noqa: E402
from mcp_hub.cli.init_cmd import init_cmd  # noqa: E402
from mcp_hub.cli.install import install, list_servers, uninstall  # noqa: E402
from mcp_hub.cli.logs import logs  # noqa: E402
from mcp_hub.cli.manage import restart, start, status_cmd, stop  # noqa: E402
from mcp_hub.cli.prompt_install import prompt_install  # noqa: E402
from mcp_hub.cli.publish import my_servers, publish, stats, unpublish  # noqa: E402
from mcp_hub.cli.quickstart import quickstart  # noqa: E402
from mcp_hub.cli.registry_sync import registry_sync  # noqa: E402
from mcp_hub.cli.search import compare, info, search  # noqa: E402
from mcp_hub.cli.trending import most_downloaded, new_releases, top_rated, trending  # noqa: E402
from mcp_hub.cli.update import rollback, update, upgrade, version_history  # noqa: E402

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
cli.add_command(upgrade)
cli.add_command(rollback)
cli.add_command(version_history)
cli.add_command(config)
cli.add_command(daemon)
cli.add_command(serve)
cli.add_command(init_cmd)
cli.add_command(quickstart)
cli.add_command(registry_sync)
cli.add_command(hub_install)
cli.add_command(prompt_install)
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
