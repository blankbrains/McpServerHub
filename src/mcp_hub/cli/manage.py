"""进程管理命令。"""

from __future__ import annotations

import asyncio

import click

from mcp_hub.core.process_manager import ProcessManager
from mcp_hub.core.registry import Registry


@click.command("start")
@click.argument("server_name", required=False)
def start(server_name: str | None):
    """启动 Server (支持 all: 启动所有已安装但未运行的)。"""
    async def _run():
        registry = Registry()
        pm = ProcessManager()

        if not server_name:
            click.echo("⚠️ 请指定要启动的 Server 名称, 或使用 mcp start all")
            return

        if server_name == "all":
            servers = await registry.get_installed()
            started = 0
            for s in servers:
                sid = s["id"]
                if pm.is_running(sid):
                    continue
                command = s.get("install_command", "")
                if not command:
                    continue
                parts = command.split()
                try:
                    await pm.spawn(sid, parts[0], parts[1:])
                    await registry.update_status(sid, "running")
                    started += 1
                    click.echo(f"  ✅ {sid} 已启动")
                except Exception as e:
                    click.echo(f"  ❌ {sid} 启动失败: {e}")
            click.echo(f"✅ 已启动 {started} 个 Server")
            return

        server_id = f"@community/{server_name}" if "/" not in server_name else server_name
        server = await registry.get_by_id(server_id)
        if not server:
            click.echo(f"❌ Server '{server_id}' 未找到")
            return

        command = server.get("install_command", "")
        if not command:
            click.echo(f"❌ {server_id} 没有安装命令")
            return

        parts = command.split()
        await pm.spawn(server_id, parts[0], parts[1:])
        await registry.update_status(server_id, "running")
        click.echo(f"✅ {server_id} 已启动")

    asyncio.run(_run())


@click.command("stop")
@click.argument("server_name", required=False)
def stop(server_name: str | None):
    """停止 Server (支持 all: 停止所有运行中的)。"""
    async def _run():
        registry = Registry()
        pm = ProcessManager()

        if not server_name:
            click.echo("⚠️ 请指定要停止的 Server 名称, 或使用 mcp stop all")
            return

        if server_name == "all":
            running = pm.list_running()
            if not running:
                click.echo("📭 没有运行中的 Server")
                return
            for proc in running:
                await pm.kill(proc.server_id)
                await registry.update_status(proc.server_id, "stopped")
                click.echo(f"  ⏹ {proc.server_id} 已停止")
            click.echo(f"✅ 已停止 {len(running)} 个 Server")
            return

        server_id = f"@community/{server_name}" if "/" not in server_name else server_name
        await pm.kill(server_id)
        await registry.update_status(server_id, "stopped")
        click.echo(f"⏹ {server_id} 已停止")

    asyncio.run(_run())


@click.command("restart")
@click.argument("server_name", required=True)
def restart(server_name: str):
    """重启 Server。"""
    async def _run():
        registry = Registry()
        pm = ProcessManager()
        server_id = f"@community/{server_name}" if "/" not in server_name else server_name

        await pm.kill(server_id)
        server = await registry.get_by_id(server_id)
        if server and server.get("install_command"):
            parts = server["install_command"].split()
            await pm.spawn(server_id, parts[0], parts[1:])
            await registry.update_status(server_id, "running")
            click.echo(f"🔄 {server_id} 已重启")

    asyncio.run(_run())


@click.command("status")
@click.argument("server_name", required=False)
def status_cmd(server_name: str | None):
    """查看 Server 状态。"""
    from rich.console import Console
    from rich.table import Table
    _console = Console()

    async def _run():
        registry = Registry()
        pm = ProcessManager()

        if server_name:
            server_id = f"@community/{server_name}" if "/" not in server_name else server_name
            server = await registry.get_by_id(server_id)
            if not server:
                _console.print(f"[red]❌ {server_id} 未找到[/red]")
                return

            running = pm.is_running(server_id)
            status = server.get("status", "not_installed")
            icon = {
                "running": "🟢", "stopped": "⏹", "error": "🔴", "not_installed": "📥"
            }.get(status, "❓")
            _console.print(f"{icon} [bold]{server_id}[/bold]")
            _console.print(f"   状态: {status}")
            _console.print(f"   版本: v{server.get('version', '?')}")
            if running:
                proc = pm.get(server_id)
                _console.print(f"   PID: {proc.pid}")
        else:
            servers = await registry.get_installed()
            if not servers:
                _console.print("[yellow]📭 还没有安装任何 Server[/yellow]")
                return

            running_count = len(pm.list_running())

            summary_title = (
                f"📊 总览: {running_count} 运行 / {len(servers)} 已安装"
            )
            table = Table(title=summary_title, header_style="bold cyan")
            table.add_column("状态", justify="center")
            table.add_column("Server ID", style="cyan")
            table.add_column("版本")
            table.add_column("操作")

            for s in servers:
                sid = s["id"]
                running = pm.is_running(sid)
                status_icon = "🟢" if running else "🔴" if s.get("status") == "error" else "⏹"
                ver = s.get("current_version", s.get("version", "?")) or "?"
                table.add_row(status_icon, sid, f"v{ver}", "mcp start/stop")

            _console.print(table)

            # 检查可用更新（不阻塞主流程）
            try:
                from mcp_hub.core.version_manager import VersionManager
                vm = VersionManager()
                updates = await vm.check_updates()
                if updates:
                    _console.print(f"\n[yellow]⚠️  {len(updates)} 个 Server 有可用更新。"
                                   f"运行 [bold]mcp update[/bold] 查看详情[/yellow]")
            except Exception:
                pass  # 网络错误不阻塞 status

    asyncio.run(_run())
