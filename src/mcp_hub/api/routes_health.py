"""健康检查 API。"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select, func

from mcp_hub.core.registry import Registry
from mcp_hub.core.process_manager import get_process_manager
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import ServerModel

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Hub 自身健康检查。"""
    return {
        "success": True,
        "status": "healthy",
        "version": "0.1.0",
    }


@router.get("/health/servers")
async def servers_health():
    """全局 Server 健康摘要。"""
    registry = Registry()
    pm = get_process_manager()
    installed = await registry.get_installed()

    # 直接从 DB 获取总计数
    async with async_session_factory() as session:
        total = (await session.execute(select(func.count(ServerModel.id)))).scalar() or 0

    running = len(pm.list_running())

    return {
        "success": True,
        "data": {
            "total_available": total,
            "total_installed": len(installed),
            "running": running,
            "stopped": len(installed) - running,
        },
    }
