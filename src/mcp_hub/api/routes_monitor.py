"""监控大屏 API — 聚合所有 Server 的运行状态、资源位置、性能指标。"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from mcp_hub.core.monitor import Monitor
from mcp_hub.core.process_manager import get_process_manager
from mcp_hub.core.registry import Registry
from mcp_hub.core.token_analyzer import TokenAnalyzer
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import HealthLogModel, UsageStatsModel

router = APIRouter(tags=["monitor"])


@router.get("/monitor/dashboard")
async def monitor_dashboard():
    """聚合所有 Server 的监控数据，供可视化大屏使用。"""
    registry = Registry()
    pm = get_process_manager()
    monitor = Monitor()
    analyzer = TokenAnalyzer()

    # 1. 获取所有 Server（包含已安装、未安装、用户自定义的）
    servers = await registry.get_all()

    # 2. 从 user_servers 表读取用户追踪的 Server ID 和启用状态
    tracked_info: dict[str, bool] = {}  # server_id → enabled
    try:
        async with async_session_factory() as session:
            from mcp_hub.db.models import UserServerModel
            result = await session.execute(
                select(UserServerModel.server_id, UserServerModel.enabled)
            )
            for row in result.fetchall():
                tracked_info[row[0]] = row[1] if row[1] is not None else True
    except Exception:
        pass

    # 3. 过滤：展示用户相关的 Server
    #    - 已安装/运行中的
    #    - 自定义的（@custom/）
    #    - 在 user_servers 追踪列表中且已启用的
    relevant = [
        s for s in servers
        if s.get("status") != "not_installed"
        or s["id"].startswith("@custom/")
        or (s["id"] in tracked_info and tracked_info[s["id"]] is not False)
    ]
    # 如果没有任何相关 Server，展示最近添加的 10 个（新用户引导）
    if not relevant:
        relevant = servers[:10]

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
                uptime_seconds = int(datetime.utcnow().timestamp() - proc.started_at)

        # 可靠性评分
        reliability = await monitor.calculate_reliability(sid)
        score = reliability.reliability_score

        # Token 消耗分析
        tokens = 0
        try:
            report = await analyzer.analyze_server(sid, [])
            tokens = report.total_tokens if report else 0
        except Exception:
            pass
        total_tokens_all += tokens

        # 调用次数（基于 usage_stats 真实调用计数）
        calls = 0
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(func.count(UsageStatsModel.id))
                    .where(
                        UsageStatsModel.server_id == sid,
                        UsageStatsModel.created_at >= datetime.utcnow() - timedelta(days=7),
                    )
                )
                calls = result.scalar() or 0
        except Exception:
            pass
        total_calls_all += calls

        items.append({
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
        })

    # 3. 聚合统计
    running_count = len(pm.list_running())
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
        "avg_reliability": round(
            sum(i["reliability_score"] for i in items) / len(items), 1
        ) if items else 0,
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
