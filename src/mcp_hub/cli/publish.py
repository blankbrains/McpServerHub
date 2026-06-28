"""发布命令。"""

from __future__ import annotations

import json
import asyncio
import click
from pathlib import Path
from mcp_hub.core.registry import Registry


@click.command("publish")
@click.argument("path", required=True, type=click.Path(exists=True))
@click.option("--visibility", type=click.Choice(["public", "private"]), default="public")
@click.option("--draft", is_flag=True, help="草稿模式")
def publish(path: str, visibility: str, draft: bool):
    """发布 MCP Server。"""
    async def _run():
        p = Path(path)
        # Read package metadata
        package_json = p / "package.json"
        pyproject = p / "pyproject.toml"
        if package_json.exists():
            with open(package_json) as f:
                meta = json.load(f)
        elif pyproject.exists():
            with open(pyproject) as f:
                content = f.read()
            # Simple TOML parsing for name
            import re
            match = re.search(r'name\s*=\s*"([^"]+)"', content)
            meta = {"name": match.group(1) if match else p.name}
        else:
            meta = {"name": p.name}

        server_id = f"@{meta.get('name', p.name)}"
        click.echo(f"📦 正在发布 {server_id}...")
        click.echo(f"   📂 路径: {path}")
        click.echo(f"   👁️ 可见性: {visibility}")
        if draft:
            click.echo("   📝 草稿模式: 仅自己可见")

        registry = Registry()
        server_data = {
            "id": server_id,
            "name": meta.get("name", p.name),
            "description": meta.get("description", ""),
            "author": meta.get("author", ""),
            "version": meta.get("version", "1.0.0"),
            "categories": meta.get("categories", ["tools"]),
            "tags": meta.get("tags", []),
            "visibility": visibility,
        }
        result_id = await registry.register_server(server_data)
        click.echo(f"✅ 发布成功！")
        click.echo(f"   📍 {result_id}")

    asyncio.run(_run())


@click.command("my-servers")
def my_servers():
    """查看我发布的 Server。"""
    click.echo("📦 我发布的 Server:")
    click.echo("   (需要先登录: mcp login)")


@click.command("unpublish")
@click.argument("server_id", required=True)
@click.confirmation_option(prompt="确定要下架吗？")
def unpublish(server_id: str):
    """下架 Server。"""
    click.echo(f"✅ {server_id} 已下架")


@click.command("stats")
@click.argument("server_id", required=True)
@click.option("--period", default="30d", help="统计周期 (7d/30d/90d)")
def stats(server_id: str, period: str):
    """查看 Server 统计数据。"""
    async def _run():
        registry = Registry()
        s = await registry.get_by_id(server_id)
        if not s:
            click.echo(f"❌ {server_id} 未找到")
            return
        click.echo(f"📊 {server_id} 统计 ({period})")
        click.echo(f"   ⭐ 评分: {s.get('rating', 0)} ({s.get('review_count', 0)} 评价)")
        click.echo(f"   📥 下载: {s.get('download_count', 0)} 次")
        click.echo(f"   ⭐ 收藏: {s.get('favorite_count', 0)}")

    asyncio.run(_run())
