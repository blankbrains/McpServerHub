"""事件总线 —— Server 间发布/订阅通信。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    topic: str
    publisher: str
    payload: dict = field(default_factory=dict)
    created_at: str = ""


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, publisher: str, payload: dict | None = None) -> int:
        """发布事件，返回接收者数量。"""
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
            return len(queues)

    async def subscribe(self, topic: str) -> asyncio.Queue:
        """订阅事件，返回一个 Queue。"""
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(q)
        return q

    async def unsubscribe(self, topic: str, queue: asyncio.Queue) -> bool:
        """取消订阅。"""
        async with self._lock:
            if topic in self._subscribers:
                try:
                    self._subscribers[topic].remove(queue)
                    return True
                except ValueError:
                    return False
            return False

    def get_topics(self) -> list[str]:
        return list(self._subscribers.keys())

    async def get_stats(self) -> dict:
        """获取总线统计。"""
        return {
            "topics": len(self._subscribers),
            "subscribers": sum(len(q) for q in self._subscribers.values()),
            "topic_list": list(self._subscribers.keys()),
        }
