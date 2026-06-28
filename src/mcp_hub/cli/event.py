"""事件总线命令。"""

from __future__ import annotations

import json
import asyncio
import click
from mcp_hub.core.event_bus import EventBus


_bus = EventBus()


@click.group("event")
def event():
    """事件总线管理。"""


@event.command("publish")
@click.argument("topic", required=True)
@click.argument("payload", required=False)
def publish_event(topic: str, payload: str | None):
    """发布事件。"""
    async def _run():
        data = json.loads(payload) if payload else {}
        count = await _bus.publish(topic, "cli", data)
        click.echo(f"📢 事件 '{topic}' 已发布，{count} 个接收者")
    asyncio.run(_run())


@event.command("subscribe")
@click.argument("topic", required=True)
def subscribe_event(topic: str):
    """订阅事件。"""
    async def _run():
        q = await _bus.subscribe(topic)
        click.echo(f"👂 正在监听 '{topic}' (按 Ctrl+C 停止)...")
        try:
            while True:
                evt = await q.get()
                click.echo(f"  📨 {evt.topic}: {json.dumps(evt.payload, ensure_ascii=False)}")
        except KeyboardInterrupt:
            click.echo("\n⏹ 已停止监听")
    asyncio.run(_run())


@event.command("list")
def list_events():
    """查看事件订阅。"""
    topics = _bus.get_topics()
    if not topics:
        click.echo("📭 暂无事件主题")
    else:
        click.echo("📋 事件主题:")
        for t in topics:
            click.echo(f"  • {t}")


@event.command("history")
@click.argument("topic", required=False)
def event_history(topic: str | None):
    """查看事件历史。"""
    click.echo("📋 事件历史 (开发中)")
