"""远程使用统计上报 API — 接受来自用户本地 MCP 网关的调用数据。

用户本地运行 `mcp serve` 时，网关会将每次 MCP tool call
的统计数据通过 HTTP POST 上报到 Hub 服务器。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from mcp_hub.api.dependencies import get_current_user
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import UsageStatsModel
from mcp_hub.logging_config import get_logger

router = APIRouter(tags=["usage"])
logger = get_logger(__name__)


@router.post("/usage/record")
async def record_usage(
    data: dict,
    user_id: str = Depends(get_current_user),
):
    """记录一次 MCP 工具调用。

    由用户本地运行的 `mcp serve` 网关 HTTP 上报。
    请求体:
    {
        "server_id": "@anthropic/web-search",
        "tool_name": "search",
        "status": "ok",          // ok | error
        "duration_ms": 234       // 响应时间（毫秒）
    }
    可批量上报:
    {
        "records": [
            { "server_id": "...", "tool_name": "...", "status": "ok", "duration_ms": 123 },
            ...
        ]
    }
    """
    records = data.get("records", [])

    # 支持单条记录
    if not records and data.get("server_id"):
        records = [data]

    if not records:
        return {"success": False, "error": "需要 server_id 或 records 数组"}

    saved = 0
    try:
        async with async_session_factory() as session:
            for rec in records:
                sid = rec.get("server_id", "")
                if not sid:
                    continue
                session.add(
                    UsageStatsModel(
                        server_id=sid,
                        user_id=user_id,
                        tool_name=rec.get("tool_name", ""),
                        status=rec.get("status", "ok"),
                        duration_ms=rec.get("duration_ms", 0),
                        token_count=rec.get("token_count", 0),
                    )
                )
                saved += 1
            await session.commit()
    except Exception as e:
        logger.error("usage.record_failed", error=str(e), records_count=len(records))
        return {"success": False, "error": f"记录失败: {str(e)}"}

    # 对 error 记录自动创建告警通知
    error_servers: set[str] = set()
    for rec in records:
        if rec.get("status") == "error":
            sid = rec.get("server_id", "")
            if sid and sid not in error_servers:
                error_servers.add(sid)
                try:
                    from mcp_hub.api.routes_notifications import create_notification

                    await create_notification(
                        user_id=user_id,
                        notif_type="alert",
                        title=f"Server 调用异常: {sid.split('/')[-1]}",
                        message=(
                            f"工具 {rec.get('tool_name', 'unknown')} 调用失败，"
                            f"耗时 {rec.get('duration_ms', 0)}ms"
                        ),
                        server_id=sid,
                        link=f"/servers/{sid}",
                    )
                except Exception:
                    logger.warning("创建告警通知失败", server_id=sid, exc_info=True)

    logger.info("usage.recorded", saved=saved, user=user_id)
    return {
        "success": True,
        "data": {"saved": saved},
        "message": f"已记录 {saved} 条调用数据",
    }


@router.get("/usage/stats")
async def get_usage_stats(
    server_id: str = "",
    user_id: str = Depends(get_current_user),
    days: int = Query(7, ge=1, le=365),
):
    """查询当前用户的使用统计。

    Query params:
    - server_id: 可选，不传则返回所有 Server 的统计
    - days: 统计天数 (default 7)
    """
    from datetime import datetime, timedelta

    from sqlalchemy import case, func, select

    async with async_session_factory() as session:
        filters = [
            UsageStatsModel.created_at >= datetime.utcnow() - timedelta(days=days),
            UsageStatsModel.user_id == user_id,
        ]
        if server_id:
            filters.append(UsageStatsModel.server_id == server_id)

        result = await session.execute(
            select(
                UsageStatsModel.server_id,
                func.count().label("total_calls"),
                func.avg(UsageStatsModel.duration_ms).label("avg_duration_ms"),
                func.sum(UsageStatsModel.token_count).label("total_tokens"),
                func.sum(case((UsageStatsModel.status == "ok", 1), else_=0)).label("ok_count"),
                func.sum(case((UsageStatsModel.status == "error", 1), else_=0)).label(
                    "error_count"
                ),
            )
            .where(*filters)
            .group_by(UsageStatsModel.server_id)
            .order_by(func.count().desc())
            .limit(50)
        )

        rows = result.fetchall()
        stats = []
        for row in rows:
            total = row[1] or 0
            ok = row[4] or 0
            stats.append(
                {
                    "server_id": row[0],
                    "total_calls": total,
                    "avg_duration_ms": round(row[2] or 0, 1),
                    "total_tokens": row[3] or 0,
                    "ok_count": ok,
                    "error_count": row[5] or 0,
                    "success_rate": round(ok / total * 100, 1) if total > 0 else 0,
                }
            )

    return {
        "success": True,
        "data": {"days": days, "stats": stats, "total_servers": len(stats)},
    }
