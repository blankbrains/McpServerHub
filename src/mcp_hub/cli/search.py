"""发现市场命令 — Rich 增强版。"""

from __future__ import annotations

import asyncio
import json

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mcp_hub.core.registry import Registry

console = Console()


@click.command("search")
@click.argument("query", required=False, default="")
@click.option("-c", "--category", help="按分类筛选")
@click.option("--tag", help="按标签筛选")
@click.option("--sort", type=click.Choice(["hot", "rating", "downloads", "new"]), default="hot")
@click.option("--page", default=1, type=int)
@click.option("--json-output", "json", is_flag=True, help="JSON 格式输出")
def search(query: str, category: str | None, tag: str | None, sort: str, page: int, json: bool):
    """搜索 MCP Server。"""
    async def _run():
        registry = Registry()
        results, total = await registry.search(
            q=query, category=category, tag=tag, sort=sort,
            page=page, page_size=20,
        )

        if json:
            console.print_json(json.dumps({"success": True, "data": results, "meta": {"total": total}}))
            return

        if not results:
            console.print("[yellow]😕 未找到匹配的 Server[/yellow]")
            return

        table = Table(title=f"🔍 找到 {total} 个 MCP Server", header_style="bold cyan")
        table.add_column("Server", style="cyan", no_wrap=True)
        table.add_column("评分", justify="center")
        table.add_column("下载", justify="right")
        table.add_column("分类")
        table.add_column("状态", justify="center")

        for s in results:
            stars = "⭐" * min(int(s.get("rating", 0)), 5) + "☆" * max(5 - min(int(s.get("rating", 0)), 5), 0)
            status = s.get("status", "not_installed")
            status_icon = {"running": "🟢", "stopped": "⏹", "error": "🔴", "not_installed": "📥"}.get(status, "❓")
            cats = ", ".join(s.get("categories", [])[:2])
            table.add_row(
                s["id"],
                f"{stars} {s.get('rating', 0)}",
                str(s.get("download_count", 0)),
                cats,
                status_icon,
            )

        console.print(table)

    asyncio.run(_run())


@click.command("info")
@click.argument("server_id", required=True)
@click.option("--json", "json_output", is_flag=True)
def info(server_id: str, json_output: bool):
    """查看 Server 详情。"""
    async def _run():
        registry = Registry()
        s = await registry.get_by_id(server_id)
        if not s:
            console.print(f"[red]❌ Server '{server_id}' 未找到[/red]")
            return

        if json_output:
            console.print_json(json.dumps({"success": True, "data": s}))
            return

        status_icon = {"running": "🟢 运行中", "stopped": "⏹ 已停止", "error": "🔴 异常", "not_installed": "📥 未安装"}.get(
            s.get("status", ""), s.get("status", "未知")
        )
        stars = "⭐" * min(int(s.get("rating", 0)), 5)
        security = {"verified": "🔒 安全认证", "reviewed": "⚪ 已审查", "unreviewed": "⚠️ 未审查"}.get(
            s.get("security_level", ""), s.get("security_level", "")
        )

        info_text = Text()
        info_text.append(f"\n📦 {s['id']}", style="bold cyan")
        info_text.append(f"  v{s.get('version', '?')}\n", style="dim")
        info_text.append(f"\n   {s.get('description', '')}\n\n")
        info_text.append(f"   {stars}  {s.get('rating', 0)}  ({s.get('review_count', 0)} 评价)\n")
        info_text.append(f"   📥 {s.get('download_count', 0)} 次下载\n")
        info_text.append(f"   📂 {', '.join(s.get('categories', []))}\n")
        info_text.append(f"   🏷️ {', '.join(s.get('tags', []))}\n")
        info_text.append(f"   🔗 {s.get('homepage', '')}\n")
        info_text.append(f"   📄 {s.get('license', 'MIT')}\n")
        info_text.append(f"   {security}\n")
        info_text.append(f"   📌 {status_icon}\n")

        console.print(Panel(info_text, title="Server 详情", border_style="cyan"))

    asyncio.run(_run())


@click.command("compare")
@click.argument("server_a", required=True)
@click.argument("server_b", required=True)
def compare(server_a: str, server_b: str):
    """对比两个 Server。"""
    async def _run():
        registry = Registry()
        a = await registry.get_by_id(server_a)
        b = await registry.get_by_id(server_b)
        if not a:
            console.print(f"[red]❌ '{server_a}' 未找到[/red]")
            return
        if not b:
            console.print(f"[red]❌ '{server_b}' 未找到[/red]")
            return

        table = Table(title="Server 对比", header_style="bold")
        table.add_column("属性", style="cyan")
        table.add_column(f"📦 {a['id']}", style="green")
        table.add_column(f"📦 {b['id']}", style="yellow")

        for key in ["version", "rating", "review_count", "download_count", "security_level", "license"]:
            table.add_row(key, str(a.get(key, "")), str(b.get(key, "")))

        console.print(table)

    asyncio.run(_run())
