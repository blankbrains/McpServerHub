"""发布命令。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

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
        click.echo("✅ 发布成功！")
        click.echo(f"   📍 {result_id}")

    asyncio.run(_run())


@click.command("my-servers")
@click.argument("author", required=False, default="")
def my_servers(author: str):
    """查看我发布的 Server。"""
    async def _run():
        if not author:
            click.echo("📦 请指定发布者名称, 例如: mcp my-servers anthropic")
            click.echo("   或先登录 (mcp login) 后使用")
            return
        registry = Registry()
        servers = await registry.get_by_author(author)
        if not servers:
            click.echo(f"📭 '{author}' 还没有发布 Server")
            return
        click.echo(f"📦 '{author}' 发布的 Server ({len(servers)}):")
        for s in servers:
            click.echo(f"  • {s['id']}  v{s.get('version', '?')}  "
                       f"⭐{s.get('rating', 0)}  \U0001f4e5{s.get('download_count', 0)}")
    asyncio.run(_run())


@click.command("unpublish")
@click.argument("server_id", required=True)
@click.confirmation_option(prompt="确定要下架吗？")
def unpublish(server_id: str):
    """下架 Server。"""
    async def _run():
        registry = Registry()
        success = await registry.unpublish_server(server_id)
        if success:
            click.echo(f"✅ {server_id} 已下架")
        else:
            click.echo(f"❌ {server_id} 未找到")
    asyncio.run(_run())


@click.command("stats")
@click.argument("server_id", required=True)
@click.option("--period", default="30d", help="统计周期 (7d/30d/90d)")
@click.option("--history", is_flag=True, help="显示操作历史")
def stats(server_id: str, period: str, history: bool):
    """查看 Server 统计数据。"""
    async def _run():
        registry = Registry()
        s = await registry.get_by_id(server_id)
        if not s:
            click.echo(f"❌ {server_id} 未找到")
            return
        click.echo(f"\U0001f4ca {server_id} 统计 ({period})")
        click.echo(f"   ⭐ 评分: {s.get('rating', 0)} ({s.get('review_count', 0)} 评价)")
        click.echo(f"   \U0001f4e5 下载: {s.get('download_count', 0)} 次")
        click.echo(f"   ⭐ 收藏: {s.get('favorite_count', 0)}")

        if history:
            from mcp_hub.db.database import async_session_factory
            from mcp_hub.db.models import InstallHistoryModel
            from sqlalchemy import select
            async with async_session_factory() as session:
                result = await session.execute(
                    select(InstallHistoryModel)
                    .where(InstallHistoryModel.server_id == server_id)
                    .order_by(InstallHistoryModel.created_at.desc())
                    .limit(10)
                )
                records = result.scalars().all()
            if records:
                click.echo(f"\n\U0001f4cb 最近操作 ({len(records)} 条):")
                for r in records:
                    click.echo(f"   [{r.created_at.strftime('%m-%d %H:%M')}] "
                               f"{r.action} v{r.version}")
            else:
                click.echo("   \U0001f4ed 暂无操作记录")
    asyncio.run(_run())
