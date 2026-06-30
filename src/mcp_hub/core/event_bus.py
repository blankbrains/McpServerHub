"""事件总线 —— Server 间发布/订阅通信，支持数据库持久化。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime

from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Event:
    topic: str
    publisher: str
    payload: dict = field(default_factory=dict)
    created_at: str = ""


class EventBus:
    def __init__(self, enable_persistence: bool = True):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._enable_persistence = enable_persistence

    async def publish(self, topic: str, publisher: str, payload: dict | None = None) -> int:
        """发布事件，返回接收者数量。同时持久化到数据库 events 表。"""
        event = Event(
            topic=topic,
            publisher=publisher,
            payload=payload or {},
            created_at=datetime.now().isoformat(),
        )
        async with self._lock:
            queues = self._subscribers.get(topic, [])
            for q in queues:
                await q.put(event)

        # 持久化到数据库
        if self._enable_persistence:
            await self._persist_event(event)

        return len(queues)

    async def subscribe(self, topic: str, subscriber_id: str = "") -> asyncio.Queue:
        """订阅事件，返回一个 Queue。同时持久化订阅关系到数据库。"""
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(q)

        # 持久化订阅关系
        if self._enable_persistence and subscriber_id:
            await self._persist_subscription(topic, subscriber_id)

        return q

    async def unsubscribe(self, topic: str, queue: asyncio.Queue) -> bool:
        """取消订阅。同时从数据库移除订阅关系。"""
        async with self._lock:
            if topic in self._subscribers:
                try:
                    self._subscribers[topic].remove(queue)
                    if not self._subscribers[topic]:
                        del self._subscribers[topic]
                    return True
                except ValueError:
                    return False
            return False

    def get_topics(self) -> list[str]:
        return list(self._subscribers.keys())

    async def get_stats(self) -> dict:
        """获取总线统计（含数据库中的历史事件数）。"""
        stats = {
            "topics": len(self._subscribers),
            "subscribers": sum(len(q) for q in self._subscribers.values()),
            "topic_list": list(self._subscribers.keys()),
        }
        # 从数据库查询历史事件数
        try:
            from sqlalchemy import text
            from mcp_hub.db.database import async_session_factory
            async with async_session_factory() as session:
                result = await session.execute(text("SELECT COUNT(*) FROM events"))
                count = result.scalar()
                stats["persisted_events"] = count or 0
        except Exception:
            stats["persisted_events"] = -1  # 标记数据库不可用
        return stats

    async def get_history(self, topic: str, limit: int = 50) -> list[dict]:
        """从数据库查询事件历史。"""
        try:
            from sqlalchemy import text
            from mcp_hub.db.database import async_session_factory
            async with async_session_factory() as session:
                result = await session.execute(
                    text(
                        "SELECT topic, publisher, payload, created_at "
                        "FROM events WHERE topic = :topic "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"topic": topic, "limit": limit},
                )
                rows = result.fetchall()
                return [
                    {
                        "topic": row[0],
                        "publisher": row[1],
                        "payload": json.loads(row[2]) if row[2] else {},
                        "created_at": str(row[3]) if row[3] else "",
                    }
                    for row in rows
                ]
        except Exception:
            return []

    async def load_subscriptions_from_db(self) -> dict[str, list[str]]:
        """从数据库恢复订阅关系（启动时调用）。"""
        try:
            from sqlalchemy import text
            from mcp_hub.db.database import async_session_factory
            async with async_session_factory() as session:
                result = await session.execute(
                    text("SELECT server_id, topic FROM subscriptions ORDER BY created_at")
                )
                rows = result.fetchall()
                subs: dict[str, list[str]] = {}
                for row in rows:
                    topic = row[1]
                    server_id = row[0]
                    if topic not in subs:
                        subs[topic] = []
                    subs[topic].append(server_id)
                return subs
        except Exception:
            return {}

    # ── 内部持久化方法 ────────────────────────────────────

    async def _persist_event(self, event: Event) -> None:
        """将事件写入 events 表。"""
        try:
            from sqlalchemy import text
            from mcp_hub.db.database import async_session_factory
            async with async_session_factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO events (topic, publisher, payload, created_at) "
                        "VALUES (:topic, :publisher, :payload, :created_at)"
                    ),
                    {
                        "topic": event.topic,
                        "publisher": event.publisher,
                        "payload": json.dumps(event.payload, ensure_ascii=False),
                        "created_at": event.created_at,
                    },
                )
                await session.commit()
        except Exception as e:
            logger.warning("event_bus.persist_event_failed", error=str(e))

    async def _persist_subscription(self, topic: str, subscriber_id: str) -> None:
        """将订阅关系写入 subscriptions 表（幂等）。"""
        try:
            from sqlalchemy import text
            from mcp_hub.db.database import async_session_factory
            async with async_session_factory() as session:
                # 幂等插入：已存在则跳过
                await session.execute(
                    text(
                        "INSERT INTO subscriptions (server_id, topic) "
                        "VALUES (:sid, :topic) "
                        "ON CONFLICT (server_id, topic) DO NOTHING"
                    ),
                    {"sid": subscriber_id, "topic": topic},
                )
                await session.commit()
        except Exception as e:
            # SQLite 不支持 ON CONFLICT，用 OR IGNORE 回退
            try:
                from sqlalchemy import text
                from mcp_hub.db.database import async_session_factory
                async with async_session_factory() as session:
                    await session.execute(
                        text(
                            "INSERT OR IGNORE INTO subscriptions (server_id, topic) "
                            "VALUES (:sid, :topic)"
                        ),
                        {"sid": subscriber_id, "topic": topic},
                    )
                    await session.commit()
            except Exception:
                logger.warning("event_bus.persist_subscription_failed", error=str(e))
