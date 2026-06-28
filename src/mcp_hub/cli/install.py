"""安装命令 — Rich 增强版。"""

from __future__ import annotations

import asyncio
import json

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from mcp_hub.core.installer import Installer
from mcp_hub.core.registry import Registry
from mcp_hub.models.server import InstallConfig, ServerMeta

console = Console()


@click.command("install")
@click.argument("server_id", required=True)
@click.option("--json", "json_output", is_flag=True)
def install(server_id: str, json_output: bool):
    """安装 MCP Server。"""
    async def _run():
        registry = Registry()
        server_data = await registry.get_by_id(server_id)
        if not server_data:
            console.print(f"[red]❌ Server '{server_id}' 未找到[/red]")
            console.print("   提示: 先用 [bold]mcp search[/bold] 搜索可用的 Server")
            return

        meta = ServerMeta(
            name=server_data["id"],
            version=server_data.get("latest_version", server_data.get("version", "1.0.0")),
            description=server_data.get("description", ""),
            install=InstallConfig(
                type=server_data.get("install_type", "pip"),
                package=server_data.get("install_package", ""),
                command=server_data.get("install_command", ""),
            ),
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"📦 正在安装 {server_id}...", total=None)
            installer = Installer()
            result = await installer.install(meta)

        if result["success"]:
            await registry.update_status(server_id, "stopped")
            await registry.increment_download(server_id)
            if json_output:
                console.print_json(json.dumps(result))
            else:
                console.print(f"[green]✅ 安装成功！{result.get('detail', '')}[/green]")
                if result.get("config_written"):
                    console.print("   📝 已自动配置到 [bold]mcp.json[/bold]")
                display_name = server_id.split("/")[-1]
                console.print(f"   ▶️  运行 [bold]mcp start {display_name}[/bold] 启动")
        else:
            console.print(f"[red]❌ 安装失败: {result.get('error', '未知错误')}[/red]")

    asyncio.run(_run())


@click.command("uninstall")
@click.argument("server_id", required=True)
@click.confirmation_option(prompt="确定要卸载吗？")
def uninstall(server_id: str):
    """卸载 MCP Server。"""
    import asyncio
    async def _run():
        registry = Registry()
        await registry.update_status(server_id, "not_installed")
        click.echo(f"✅ {server_id} 已卸载")
    asyncio.run(_run())


@click.command("list")
def list_servers():
    """列出已安装的 Server。"""
    import asyncio
    async def _run():
        registry = Registry()
        servers = await registry.get_installed()
        if not servers:
            click.echo("📭 还没有安装任何 Server")
            click.echo("   提示: 使用 mcp search 搜索，然后 mcp install <server> 安装")
            return

        click.echo(f"\n📦 已安装 {len(servers)} 个 Server:\n")
        for s in servers:
            status = s.get("status", "unknown")
            icon = {"running": "🟢", "stopped": "⏹", "error": "🔴", "not_installed": "📥"}.get(status, "❓")
            click.echo(f"  {icon} {s['id']}  v{s.get('current_version', s.get('version', '?'))}")
            click.echo(f"     {s.get('description', '')[:60]}")
    asyncio.run(_run())
