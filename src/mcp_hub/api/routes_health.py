"""健康检查与质量监控 API。"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from mcp_hub.core.monitor import Monitor
from mcp_hub.core.process_manager import get_process_manager
from mcp_hub.core.registry import Registry
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import ServerModel
from mcp_hub.exceptions import ServerNotFoundError

router = APIRouter(tags=["health"])


# ── Hub 自身健康 ──────────────────────────────────────────


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

    async with async_session_factory() as session:
        total = (await session.execute(
            select(func.count(ServerModel.id))
        )).scalar() or 0

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


# ── 监控 API ──────────────────────────────────────────────


@router.get("/health/uptime/{server_id:path}")
async def get_uptime(server_id: str):
    """获取 Server 的 Uptime 统计。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    uptime_stats = await Monitor.get_uptime(server_id)
    return {
        "success": True,
        "data": [
            {
                "window": u.window,
                "total_checks": u.total_checks,
                "passed_checks": u.passed_checks,
                "uptime_pct": u.uptime_pct,
                "avg_response_time_ms": u.avg_response_time_ms,
            }
            for u in uptime_stats
        ],
    }


@router.get("/health/reliability/{server_id:path}")
async def get_reliability(server_id: str):
    """获取 Server 的可靠性评分。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    report = await Monitor.calculate_reliability(server_id)
    return {
        "success": True,
        "data": {
            "server_id": report.server_id,
            "reliability_score": report.reliability_score,
            "total_checks": report.total_checks_recorded,
            "last_check_at": report.last_check_at,
            "last_check_status": report.last_check_status,
            "uptime_stats": [
                {
                    "window": u.window,
                    "uptime_pct": u.uptime_pct,
                    "avg_response_time_ms": u.avg_response_time_ms,
                }
                for u in report.uptime_stats
            ],
        },
    }


@router.get("/health/reliability/top")
async def get_top_reliable(limit: int = 20):
    """获取最稳定 Server 排行榜。"""
    top = await Monitor.get_top_reliable(limit=limit)
    return {
        "success": True,
        "data": [
            {
                "server_id": s.server_id,
                "status": s.status,
                "reliability_score": s.reliability_score,
                "uptime_24h": s.uptime_24h,
                "avg_response_ms": s.avg_response_ms,
                "running": s.running,
            }
            for s in top
        ],
    }


@router.get("/health/summary")
async def get_monitor_summary():
    """获取全局监控统计。"""
    stats = await Monitor.get_summary_stats()
    return {"success": True, "data": stats}


@router.post("/health/check/{server_id:path}")
async def trigger_health_check(server_id: str):
    """手动触发一次健康检查并记录。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    from mcp_hub.core.process_manager import get_process_manager

    pm = get_process_manager()
    proc = pm.get(server_id)

    if not proc or not proc.process or proc.process.returncode is not None:
        await Monitor.record_check(server_id, "L1_process", "error", message="进程未运行")
        return {
            "success": True,
            "data": {"server_id": server_id, "status": "error", "message": "进程未运行"},
        }

    # L1 检查
    import os
    try:
        os.kill(proc.pid, 0)
        await Monitor.record_check(server_id, "L1_process", "ok", message="进程存活")
        return {
            "success": True,
            "data": {"server_id": server_id, "status": "ok", "level": "L1"},
        }
    except (OSError, ProcessLookupError):
        await Monitor.record_check(server_id, "L1_process", "error", message="进程不存在")
        return {
            "success": True,
            "data": {"server_id": server_id, "status": "error", "message": "进程不存在"},
        }
