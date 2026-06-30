"""安装命令 — Rich 增强版 + 安全预扫描。"""

from __future__ import annotations

import asyncio
import json

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from mcp_hub.core.installer import Installer
from mcp_hub.core.registry import Registry
from mcp_hub.core.security_scanner import SecurityScanner
from mcp_hub.models.server import InstallConfig, ServerMeta

console = Console()


@click.command("install")
@click.argument("server_ids", required=True, nargs=-1)
@click.option("--json", "json_output", is_flag=True)
@click.option("--force", is_flag=True, help="跳过安全检查")
@click.option("--dry-run", "dry_run", is_flag=True, help="预览模式（只检查不安装）")
def install(server_ids: tuple[str], json_output: bool, force: bool, dry_run: bool):
    """安装 MCP Server（安装前自动安全扫描，支持多参数）。"""
    async def _install_one(sid: str) -> dict:
        registry = Registry()
        server_data = await registry.get_by_id(sid)
        if not server_data:
            return {"server_id": sid, "success": False, "error": "未找到"}

        # ── 安全预扫描 ──
        if not force:
            console.print(f"[dim]🔍 正在扫描 {sid} 安全性...[/dim]")
            scanner = SecurityScanner()
            report = await scanner.scan(server_data)

            if report.score < 40:
                high_issues = [f for f in report.findings if f.severity in ("critical", "high")]
                console.print(Panel.fit(
                    f"[bold red]🔴 安全评分: {report.score}/100[/bold red]\n"
                    + "\n".join(f"  • {f.title}" for f in high_issues),
                    title=f"⛔ {sid} 安装已阻止",
                    border_style="red",
                ))
                return {"server_id": sid, "success": False, "error": f"安全评分 {report.score}/100"}
            elif report.score < 70:
                console.print(Panel.fit(
                    f"[bold yellow]🟡 安全评分: {report.score}/100 — {report.level}[/bold]",
                    title=f"⚡ {sid} 安全提醒",
                    border_style="yellow",
                ))
                if not click.confirm("继续安装?", default=False):
                    return {"server_id": sid, "success": False, "error": "用户取消"}
            else:
                console.print(f"[green]🟢 {sid} 安全评分: {report.score}/100 — 安全[/green]")

        # ── 预览模式 ──
        if dry_run:
            console.print(f"\n[cyan]🔍 预览安装 {sid}[/cyan]")
            console.print(f"   安装命令: {server_data.get('install_command', 'N/A')}")
            console.print(f"   版本: {server_data.get('latest_version', server_data.get('version', '?'))}")
            console.print(f"   类型: {server_data.get('install_type', '?')}")
            console.print(f"[dim]   运行 mcp install {sid} 来安装[/dim]")
            return {"server_id": sid, "success": True, "dry_run": True}

        # ── 执行安装 ──
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
            progress.add_task(f"📦 正在安装 {sid}...", total=None)
            installer = Installer()
            result = await installer.install(meta)

        if result["success"]:
            registry2 = Registry()
            await registry2.update_status(sid, "stopped")
            await registry2.increment_download(sid)
            return {"server_id": sid, "success": True, "detail": result.get("detail", "")}
        return {"server_id": sid, "success": False, "error": result.get("error", "安装失败")}

    async def _run():
        results = []
        for sid in server_ids:
            server_id = f"@community/{sid}" if "/" not in sid else sid
            r = await _install_one(server_id)
            results.append(r)

        if json_output:
            from rich import print_json
            print_json(json.dumps(results))
            return

        ok = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]
        dry_run_results = [r for r in results if r.get("dry_run")]

        if dry_run_results:
            console.print(f"\n[cyan]✅ 预览完成: {len(dry_run_results)} 个 Server[/cyan]")
            return

        if ok:
            for r in ok:
                console.print(f"[green]✅ {r['server_id']} 安装成功！[/green]")
            console.print(f"[green]✅ 成功安装 {len(ok)}/{len(results)} 个 Server[/green]")
        if failed:
            for r in failed:
                console.print(f"[red]❌ {r['server_id']} 失败: {r.get('error', '')}[/red]")
            if len(failed) == len(results):
                console.print("[red]全部安装失败，请检查 Server 名称是否正确[/red]")

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
            icon = {
                "running": "🟢", "stopped": "⏹", "error": "🔴", "not_installed": "📥"
            }.get(status, "❓")
            click.echo(f"  {icon} {s['id']}  v{s.get('current_version', s.get('version', '?'))}")
            click.echo(f"     {s.get('description', '')[:60]}")
    asyncio.run(_run())
