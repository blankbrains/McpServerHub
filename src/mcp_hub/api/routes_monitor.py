"""监控大屏 API — 聚合所有 Server 的运行状态、资源位置、性能指标。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from mcp_hub.api.dependencies import get_optional_user
from mcp_hub.core.monitor import Monitor
from mcp_hub.core.process_manager import get_process_manager
from mcp_hub.core.registry import Registry
from mcp_hub.core.token_analyzer import TokenAnalyzer
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import UsageStatsModel, UserServerModel
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["monitor"])


@router.get("/monitor/dashboard")
async def monitor_dashboard(user_id: str | None = Depends(get_optional_user)):
    """聚合所有 Server 的监控数据，供可视化大屏使用。"""
    registry = Registry()
    pm = get_process_manager()
    monitor = Monitor()
    analyzer = TokenAnalyzer()

    # 1. 获取所有 Server（包含已安装、未安装、用户自定义的）
    servers = await registry.get_all()

    # 2. 已登录用户仅加载自己的追踪记录。匿名访问只能查看服务端已安装项，
    #    避免将其他用户的配置关系或自定义 Server 暴露到公共接口。
    tracked_info: dict[str, bool] = {}  # server_id → enabled
    if user_id:
        async with async_session_factory() as session:
            result = await session.execute(
                select(UserServerModel.server_id, UserServerModel.enabled).where(
                    UserServerModel.user_id == user_id
                )
            )
            for row in result.fetchall():
                tracked_info[row[0]] = row[1] if row[1] is not None else True

    server_by_id = {server["id"]: server for server in servers}
    if user_id:
        relevant = [
            server_by_id[server_id] for server_id in tracked_info if server_id in server_by_id
        ]
    else:
        relevant = [
            server
            for server in servers
            if server.get("status") != "not_installed" and not server["id"].startswith("@custom/")
        ]

    # 3. 构建每个 Server 的详情
    items = []
    total_calls_all = 0
    total_tokens_all = 0

    for s in relevant:
        sid = s["id"]
        proc = pm.get(sid)
        running = pm.is_running(sid)

        # 进程信息
        location = ""
        pid = None
        uptime_seconds = 0
        if proc:
            pid = proc.pid
            if proc.log_file:
                location = str(proc.log_file.parent)
            if proc.started_at:
                uptime_seconds = int(datetime.now(timezone.utc).timestamp() - proc.started_at)

        # 可靠性评分
        reliability = await monitor.calculate_reliability(sid)
        score = reliability.reliability_score

        # Token 消耗分析（analyze_server 是同步方法，需要 server dict）
        tokens = 0
        try:
            report = analyzer.analyze_server(s)
            tokens = report.total_tokens if report else 0
        except Exception as e:
            logger.warning("monitor.token_analysis_failed", server_id=sid, error=str(e))
        total_tokens_all += tokens

        # 调用次数（基于 usage_stats 真实调用计数）
        calls = 0
        try:
            filters = [
                UsageStatsModel.server_id == sid,
                UsageStatsModel.created_at
                >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7),
            ]
            if user_id:
                filters.append(UsageStatsModel.user_id == user_id)
            async with async_session_factory() as session:
                result = await session.execute(
                    select(func.count(UsageStatsModel.id)).where(*filters)
                )
                calls = result.scalar() or 0
        except Exception:
            logger.warning("获取调用次数统计失败", server_id=sid, exc_info=True)
        total_calls_all += calls

        items.append(
            {
                "server_id": sid,
                "name": s.get("name", sid.split("/")[-1]),
                "description": s.get("description", ""),
                "status": s.get("status", "unknown"),
                "running": running,
                "enabled": tracked_info.get(sid, True),
                "pid": pid,
                "location": location or "N/A",
                "uptime_seconds": uptime_seconds,
                "reliability_score": score,
                "total_checks": reliability.total_checks_recorded,
                "last_check_status": reliability.last_check_status,
                "token_consumption": tokens,
                "call_count_7d": calls,
                "rating": s.get("rating", 0),
                "version": s.get("version", "?"),
                "security_level": s.get("security_level", "unreviewed"),
                "install_command": s.get("install_command", ""),
            }
        )

    # 3. 聚合统计
    running_count = sum(1 for item in items if item["running"])
    error_count = sum(1 for i in items if i["status"] == "error")
    stopped_count = sum(1 for i in items if i["status"] == "stopped")
    healthy_count = sum(1 for i in items if i["last_check_status"] == "ok")

    summary = {
        "total_servers": len(relevant),
        "running": running_count,
        "stopped": stopped_count,
        "error": error_count,
        "healthy": healthy_count,
        "total_calls_7d": total_calls_all,
        "total_token_consumption": total_tokens_all,
        "avg_reliability": round(sum(i["reliability_score"] for i in items) / len(items), 1)
        if items
        else 0,
    }

    # 按可靠性排序
    items.sort(key=lambda x: x["reliability_score"], reverse=True)

    return {
        "success": True,
        "data": {
            "summary": summary,
            "servers": items,
        },
    }
