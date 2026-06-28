"""社区命令。"""

from __future__ import annotations

import asyncio
import click

from mcp_hub.db.repositories import ReviewRepository, UserRepository
from mcp_hub.db.database import async_session_factory


@click.command("rate")
@click.argument("server_id", required=True)
@click.argument("rating", required=True, type=int)
def rate(server_id: str, rating: int):
    """给 Server 评分 (1-5)。"""
    if rating < 1 or rating > 5:
        click.echo("❌ 评分范围: 1-5")
        return

    async def _run():
        async with async_session_factory() as session:
            repo = ReviewRepository(session)
            await repo.rate(server_id, "local-user", rating)
        click.echo(f"✅ {server_id} 评分: {rating}⭐")

    asyncio.run(_run())


@click.command("review")
@click.argument("server_id", required=True)
@click.argument("content", required=False)
def review(server_id: str, content: str | None):
    """写/看评价。"""
    if content:
        async def _run():
            async with async_session_factory() as session:
                repo = ReviewRepository(session)
                await repo.rate(server_id, "local-user", 5, content)
            click.echo("✅ 评价已提交")
        asyncio.run(_run())
    else:
        async def _run():
            async with async_session_factory() as session:
                repo = ReviewRepository(session)
                reviews = await repo.get_reviews(server_id)
            if not reviews:
                click.echo("📭 暂无评价")
                return
            click.echo(f"\n💬 {server_id} 的评价:\n")
            for r in reviews:
                stars = "⭐" * r["rating"] + "☆" * (5 - r["rating"])
                click.echo(f"  {stars} {r.get('content', '')[:100]}")
        asyncio.run(_run())


@click.command("favorite")
@click.argument("server_id", required=True)
def favorite(server_id: str):
    """收藏 Server。"""
    async def _run():
        async with async_session_factory() as session:
            repo = UserRepository(session)
            is_fav = await repo.favorite("local-user", server_id)
        if is_fav:
            click.echo(f"✅ {server_id} 已收藏")
        else:
            click.echo(f"✅ {server_id} 已取消收藏")
    asyncio.run(_run())


@click.command("favorites")
def favorites():
    """查看收藏列表。"""
    async def _run():
        async with async_session_factory() as session:
            repo = UserRepository(session)
            favs = await repo.get_favorites("local-user")
        if not favs:
            click.echo("📭 还没有收藏任何 Server")
            return
        click.echo(f"\n⭐ 收藏 ({len(favs)}):\n")
        for s in favs:
            click.echo(f"  ⭐ {s['id']} — {s.get('description', '')[:60]}")
    asyncio.run(_run())
