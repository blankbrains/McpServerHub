"""排行榜命令。"""

from __future__ import annotations

import asyncio

import click

from mcp_hub.core.registry import Registry


@click.command("trending")
@click.option("--category", help="按分类筛选")
@click.option("--json", "json_output", is_flag=True)
def trending(_category: str | None, json_output: bool):
    """热门趋势榜。"""
    import json
    async def _run():
        registry = Registry()
        results = await registry.get_trending()
        if json_output:
            click.echo(json.dumps({"success": True, "data": results}, ensure_ascii=False))
            return
        click.echo("\n🔥 热门趋势:\n")
        for i, s in enumerate(results[:10], 1):
            click.echo(f"  {i}. {s['id']}  ⭐{s.get('rating', 0)}  📥{s.get('download_count', 0)}")
    asyncio.run(_run())


@click.command("top-rated")
def top_rated():
    """评分最高榜。"""
    async def _run():
        registry = Registry()
        results = await registry.get_top_rated()
        click.echo("\n⭐ 评分最高:\n")
        for i, s in enumerate(results[:10], 1):
            stars = "⭐" * int(s.get("rating", 0))
            click.echo(f"  {i}. {stars} {s['id']}  ({s.get('rating', 0)})")
    asyncio.run(_run())


@click.command("most-downloaded")
def most_downloaded():
    """下载最多榜。"""
    async def _run():
        registry = Registry()
        results = await registry.get_trending()
        click.echo("\n📥 下载最多:\n")
        for i, s in enumerate(results[:10], 1):
            click.echo(f"  {i}. {s['id']}  📥{s.get('download_count', 0)}")
    asyncio.run(_run())


@click.command("new-releases")
def new_releases():
    """最新发布榜。"""
    async def _run():
        registry = Registry()
        results = await registry.get_new_releases()
        click.echo("\n🆕 最新发布:\n")
        for i, s in enumerate(results[:10], 1):
            click.echo(f"  {i}. {s['id']}  v{s.get('version', '?')}")
    asyncio.run(_run())
