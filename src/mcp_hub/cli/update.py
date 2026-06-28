"""版本管理命令 — 真实更新 + 回滚。"""

from __future__ import annotations

import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from mcp_hub.core.installer import VersionManager

console = Console()


@click.command("update")
@click.argument("server_name", required=False)
@click.option("--check", is_flag=True, help="只检查不更新")
def update(server_name: str | None, check: bool):
    """检查/执行 MCP Server 版本更新。"""
    async def _run():
        vm = VersionManager()
        console.print("[bold]🔍 正在检查版本更新...[/bold]")

        updates = await vm.check_updates()

        if server_name:
            sid = f"@community/{server_name}" if "/" not in server_name else server_name
            updates = [u for u in updates if u["server_id"] == sid]

        if not updates:
            console.print("[green]✅ 所有 Server 都是最新版本[/green]")
            return

        table = Table(title=f"📦 找到 {len(updates)} 个更新")
        table.add_column("Server", style="cyan")
        table.add_column("当前版本")
        table.add_column("最新版本")
        for u in updates:
            table.add_row(u["server_id"], f"v{u['current']}", f"v{u['latest']}")
        console.print(table)

        if not check:
            console.print("\n[yellow]运行 mcp update <server> 执行更新[/yellow]")
            for u in updates:
                console.print(f"  mcp update {u['server_id'].split('/')[-1]}")

    asyncio.run(_run())


@click.command("upgrade")
@click.argument("server_name", required=True)
def upgrade(server_name: str):
    """升级指定 Server 到最新版本。"""
    async def _run():
        sid = f"@community/{server_name}" if "/" not in server_name else server_name
        vm = VersionManager()

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
            p.add_task(f"📦 正在升级 {sid}...", total=None)
            result = await vm.update_server(sid)

        if result["success"]:
            console.print(f"[green]✅ {sid} 升级成功！[/green]")
            if result.get("detail"):
                console.print(f"   {result['detail']}")
        else:
            console.print(f"[yellow]⚠️  {result.get('message', '升级失败')}[/yellow]")

    asyncio.run(_run())


@click.command("rollback")
@click.argument("server_name", required=True)
@click.option("--to", "version", help="回滚到指定版本")
def rollback(server_name: str, version: str | None):
    """回滚 Server 到上一版本或指定版本。"""
    async def _run():
        sid = f"@community/{server_name}" if "/" not in server_name else server_name
        vm = VersionManager()

        if version:
            console.print(f"[yellow]⏪ 正在回滚 {sid} 到 v{version}...[/yellow]")
        else:
            console.print(f"[yellow]⏪ 正在回滚 {sid} 到上一版本...[/yellow]")

        result = await vm.rollback_server(sid, version)

        if result["success"]:
            console.print(f"[green]✅ {result['message']}[/green]")
        else:
            console.print(f"[red]❌ {result['message']}[/red]")

    asyncio.run(_run())


@click.command("version-history")
@click.argument("server_name", required=True)
def version_history(server_name: str):
    """查看 Server 的版本历史。"""
    import asyncio
    from mcp_hub.db.database import async_session_factory
    from sqlalchemy import text

    async def _run():
        sid = f"@community/{server_name}" if "/" not in server_name else server_name
        async with async_session_factory() as session:
            rows = await session.execute(
                text("SELECT version, action, status, created_at FROM install_history WHERE server_id = :sid ORDER BY created_at DESC LIMIT 20"),
                {"sid": sid},
            )
            records = rows.fetchall()

        if not records:
            console.print(f"[yellow]📭 {sid} 暂无版本历史[/yellow]")
            return

        table = Table(title=f"📋 {sid} 版本历史")
        table.add_column("版本", style="cyan")
        table.add_column("操作")
        table.add_column("时间")
        for r in records:
            icon = {"install": "📥", "update": "⬆️", "rollback": "⏪"}.get(r[1], "❓")
            table.add_row(f"v{r[0]}", f"{icon} {r[1]}", str(r[3])[:19] if r[3] else "-")
        console.print(table)

    asyncio.run(_run())
