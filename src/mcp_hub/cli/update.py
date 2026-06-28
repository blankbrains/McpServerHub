"""版本管理命令。"""

from __future__ import annotations

import asyncio
import click
from mcp_hub.core.installer import VersionManager


@click.command("update")
@click.argument("server_name", required=False)
@click.option("--check", is_flag=True, help="只检查不更新")
def update(server_name: str | None, check: bool):
    """检查/执行 Server 更新。"""
    async def _run():
        vm = VersionManager()
        updates = await vm.check_updates()

        if server_name:
            server_id = f"@community/{server_name}" if "/" not in server_name else server_name
            updates = [u for u in updates if u["server_id"] == server_id]

        if not updates:
            click.echo("✅ 所有 Server 都是最新版本")
            return

        for u in updates:
            click.echo(f"📦 {u['server_id']}: {u['current']} → {u['latest']}")
            if not check:
                click.echo("   运行 mcp update 以更新")

    asyncio.run(_run())


@click.command("rollback")
@click.argument("server_name", required=True)
@click.option("--to", "version", help="回滚到指定版本")
def rollback(server_name: str, version: str | None):
    """回滚 Server 版本。"""
    server_id = f"@community/{server_name}" if "/" not in server_name else server_name
    if version:
        click.echo(f"⏪ {server_id} 回滚到 v{version}")
    else:
        click.echo(f"⏪ {server_id} 回滚到上一版本")
