"""健康检查 API。"""

from __future__ import annotations

from fastapi import APIRouter
from mcp_hub.core.registry import Registry
from mcp_hub.core.process_manager import get_process_manager

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
    all_servers = await registry.search(page=1, page_size=1)
    total_available = all_servers[1] if len(all_servers) == 2 else 0
    running = len(pm.list_running())

    return {
        "success": True,
        "data": {
            "total_available": total_available,
            "total_installed": len(installed),
            "running": running,
            "stopped": len(installed) - running,
        },
    }
