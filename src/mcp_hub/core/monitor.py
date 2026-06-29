"""MCP Server 质量监控引擎。

基于 HealthLogModel 的历史数据计算:
  - Uptime: 1小时/24小时/7天/30天 可用率
  - 响应时间: 平均/中位数/P99
  - 可靠性评分: 综合 uptime + 响应时间
  - 稳定性榜单: 最可靠 Server 排名

数据来源:
  - HealthChecker 定期运行 L1/L2/L3 检查并记录到 health_logs 表
  - ProcessManager 的 keepalive 心跳也记录为 L2 数据
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, func, select

from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import HealthLogModel
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)

# ── 常量 ───────────────────────────────────────────────────

# 可靠性评分权重
WEIGHT_UPTIME_24H = 0.40    # 24小时 uptime 权重最高
WEIGHT_UPTIME_7D = 0.30     # 7天 uptime
WEIGHT_RESPONSE_TIME = 0.20  # 响应时间
WEIGHT_UPTIME_1H = 0.10     # 当前稳定性

# 时间窗口定义
TIME_WINDOWS: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

# 响应时间评分标准（毫秒）
RESPONSE_TIME_GOOD = 100    # <100ms → 满分
RESPONSE_TIME_OK = 500      # <500ms → 部分扣分
RESPONSE_TIME_SLOW = 2000   # <2000ms → 严重扣分


# ── 数据结构 ───────────────────────────────────────────────


@dataclass
class UptimeStats:
    """某个时间段内的 uptime 统计。"""
    window: str           # 1h, 24h, 7d, 30d
    total_checks: int
    passed_checks: int
    uptime_pct: float     # 0-100
    avg_response_time_ms: float


@dataclass
class ReliabilityReport:
    """Server 的完整可靠性报告。"""
    server_id: str
    reliability_score: int          # 0-100
    uptime_stats: list[UptimeStats] = field(default_factory=list)
    total_checks_recorded: int = 0
    last_check_at: str | None = None
    last_check_status: str | None = None
    recent_errors: list[str] = field(default_factory=list)


@dataclass
class ServerHealthSummary:
    """Server 健康摘要。"""
    server_id: str
    status: str           # healthy / warning / error / unknown
    reliability_score: int
    uptime_24h: float
    avg_response_ms: float
    running: bool = False


# ── 监控引擎 ───────────────────────────────────────────────


class Monitor:
    """质量监控引擎。

    提供 uptime 计算、可靠性评分、健康摘要等功能。
    数据来源: health_logs 表（由 HealthChecker 和 ProcessManager 写入）。
    """

    # ── 记录健康检查结果 ──────────────────────────────────

    @staticmethod
    async def record_check(
        server_id: str,
        check_type: str,
        status: str,
        response_time_ms: int = 0,
        message: str = "",
    ) -> None:
        """记录一次健康检查结果到数据库。

        Args:
            server_id: Server 标识 (如 @anthropic/web-search)
            check_type: 检查级别 (L1_process / L2_connection / L3_functional)
            status: 结果 (ok / warning / error)
            response_time_ms: 响应时间(毫秒)
            message: 附加信息
        """
        try:
            async with async_session_factory() as session:
                log = HealthLogModel(
                    server_id=server_id,
                    check_type=check_type,
                    status=status,
                    response_time_ms=response_time_ms,
                    message=message[:500] if message else "",
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error("monitor.record_failed", server_id=server_id, error=str(e))

    # ── Uptime 计算 ──────────────────────────────────────

    @staticmethod
    async def get_uptime(
        server_id: str,
        windows: list[str] | None = None,
    ) -> list[UptimeStats]:
        """获取 Server 在多个时间窗口内的 uptime。

        Args:
            server_id: Server 标识。
            windows: 时间窗口列表，默认所有。

        Returns:
            每个窗口的 UptimeStats 列表。
        """
        if windows is None:
            windows = list(TIME_WINDOWS.keys())

        results: list[UptimeStats] = []
        now = datetime.now(timezone.utc)

        async with async_session_factory() as session:
            for w in windows:
                delta = TIME_WINDOWS.get(w)
                if not delta:
                    continue

                since = now - delta
                try:
                    rows = await session.execute(
                        select(
                            func.count(HealthLogModel.id),
                            func.sum(
                                case((HealthLogModel.status == "ok", 1), else_=0)
                            ),
                            func.avg(HealthLogModel.response_time_ms),
                        ).where(
                            HealthLogModel.server_id == server_id,
                            HealthLogModel.created_at >= since,
                        )
                    )
                    row = rows.one()
                    total = row[0] or 0
                    passed = row[1] or 0
                    avg_ms = float(row[2] or 0.0)
                except Exception:
                    total = 0
                    passed = 0
                    avg_ms = 0.0

                uptime_pct = (passed / total * 100) if total > 0 else 0.0
                results.append(UptimeStats(
                    window=w,
                    total_checks=total,
                    passed_checks=passed,
                    uptime_pct=round(uptime_pct, 1),
                    avg_response_time_ms=round(avg_ms, 1),
                ))

        return results

    # ── 可靠性评分 ──────────────────────────────────────

    @staticmethod
    async def calculate_reliability(server_id: str) -> ReliabilityReport:
        """计算 Server 的综合可靠性评分 (0-100)。

        评分公式:
          40% × 24h uptime
          30% × 7d uptime
          20% × 响应时间评分
          10% × 1h uptime (当前稳定性)
        """
        uptime_stats = await Monitor.get_uptime(server_id)

        # 构建 uptime 查询
        u24h = next((u for u in uptime_stats if u.window == "24h"), None)
        u7d = next((u for u in uptime_stats if u.window == "7d"), None)
        u1h = next((u for u in uptime_stats if u.window == "1h"), None)

        uptime_24h = u24h.uptime_pct if u24h else 0
        uptime_7d = u7d.uptime_pct if u7d else 0
        uptime_1h = u1h.uptime_pct if u1h else 0

        # 响应时间评分
        avg_ms = (u24h.avg_response_time_ms if u24h else 0)
        response_score = Monitor._score_response_time(avg_ms)

        # 综合评分
        score = (
            uptime_24h * WEIGHT_UPTIME_24H
            + uptime_7d * WEIGHT_UPTIME_7D
            + response_score * WEIGHT_RESPONSE_TIME
            + uptime_1h * WEIGHT_UPTIME_1H
        )
        score = max(0, min(100, round(score)))

        # 获取最近状态
        last_check, total_checks, recent_errors = await Monitor._get_recent_status(
            server_id
        )

        # 如果没有数据，评分为 0
        if total_checks == 0:
            score = 0

        return ReliabilityReport(
            server_id=server_id,
            reliability_score=score,
            uptime_stats=uptime_stats,
            total_checks_recorded=total_checks,
            last_check_at=last_check[0].isoformat() if last_check and last_check[0] else None,
            last_check_status=last_check[1] if last_check else None,
            recent_errors=recent_errors,
        )

    @staticmethod
    def _score_response_time(avg_ms: float) -> float:
        """将平均响应时间转换为 0-100 分。"""
        if avg_ms <= RESPONSE_TIME_GOOD:
            return 100.0
        if avg_ms <= RESPONSE_TIME_OK:
            # 100 → 线性下降至 60
            return 100 - (avg_ms - RESPONSE_TIME_GOOD) / (RESPONSE_TIME_OK - RESPONSE_TIME_GOOD) * 40  # noqa: E501
        if avg_ms <= RESPONSE_TIME_SLOW:
            # 60 → 线性下降至 20
            return 60 - (avg_ms - RESPONSE_TIME_OK) / (RESPONSE_TIME_SLOW - RESPONSE_TIME_OK) * 40
        return max(10.0, 20 - (avg_ms - RESPONSE_TIME_SLOW) / 1000 * 10)

    @staticmethod
    async def _get_recent_status(
        server_id: str,
    ) -> tuple[tuple[str, str] | None, int, list[str]]:
        """获取最近检查状态、总记录数和近期错误。"""
        async with async_session_factory() as session:
            # 总记录数
            count_row = await session.execute(
                select(func.count(HealthLogModel.id)).where(
                    HealthLogModel.server_id == server_id
                )
            )
            total = count_row.scalar() or 0

            # 最近一次检查
            last_row = await session.execute(
                select(
                    HealthLogModel.created_at,
                    HealthLogModel.status,
                )
                .where(HealthLogModel.server_id == server_id)
                .order_by(HealthLogModel.created_at.desc())
                .limit(1)
            )
            last = last_row.fetchone()

            # 最近 5 条错误
            error_rows = await session.execute(
                select(HealthLogModel.message)
                .where(
                    HealthLogModel.server_id == server_id,
                    HealthLogModel.status == "error",
                )
                .order_by(HealthLogModel.created_at.desc())
                .limit(5)
            )
            errors = [row[0] for row in error_rows if row[0]]

            return last, total, errors

    # ── 健康摘要 ─────────────────────────────────────────

    @staticmethod
    async def get_server_health(server_id: str) -> ServerHealthSummary:
        """获取 Server 的快速健康摘要。"""
        from mcp_hub.core.process_manager import get_process_manager

        pm = get_process_manager()
        running = pm.is_running(server_id)
        reliability = await Monitor.calculate_reliability(server_id)

        u24h = next((u for u in reliability.uptime_stats if u.window == "24h"), None)
        uptime_24h = u24h.uptime_pct if u24h else 0
        avg_ms = u24h.avg_response_time_ms if u24h else 0

        if reliability.reliability_score >= 90:
            status = "healthy"
        elif reliability.reliability_score >= 60:
            status = "warning"
        elif reliability.reliability_score > 0:
            status = "error"
        else:
            status = "unknown"

        return ServerHealthSummary(
            server_id=server_id,
            status=status,
            reliability_score=reliability.reliability_score,
            uptime_24h=uptime_24h,
            avg_response_ms=avg_ms,
            running=running,
        )

    # ── 榜单 ─────────────────────────────────────────────

    @staticmethod
    async def get_top_reliable(limit: int = 20) -> list[ServerHealthSummary]:
        """获取最稳定的 Server 榜单（按可靠性评分降序）。"""
        from mcp_hub.core.registry import Registry

        registry = Registry()
        servers, _ = await registry.search(q="", page=1, page_size=limit * 3)

        summaries: list[ServerHealthSummary] = []
        for s in servers:
            sid = s["id"]
            summary = await Monitor.get_server_health(sid)
            if summary.reliability_score > 0:
                summaries.append(summary)

        summaries.sort(key=lambda x: x.reliability_score, reverse=True)
        return summaries[:limit]

    @staticmethod
    async def get_summary_stats() -> dict[str, Any]:
        """获取全局监控统计。"""
        from mcp_hub.core.process_manager import get_process_manager
        from mcp_hub.core.registry import Registry

        registry = Registry()
        pm = get_process_manager()
        installed = await registry.get_installed()
        running = pm.list_running()

        async with async_session_factory() as session:
            total_logs = (
                await session.execute(select(func.count(HealthLogModel.id)))
            ).scalar() or 0

            error_logs_24h = (
                await session.execute(
                    select(func.count(HealthLogModel.id)).where(
                        HealthLogModel.status == "error",
                        HealthLogModel.created_at
                        >= datetime.now(timezone.utc) - timedelta(hours=24),
                    )
                )
            ).scalar() or 0

        return {
            "total_servers": len(installed),
            "running": len(running),
            "total_health_checks": total_logs,
            "errors_last_24h": error_logs_24h,
            "monitored_servers": len([
                s for s in installed if s.get("status") == "running"
            ]),
        }


# ── 辅助函数 ───────────────────────────────────────────────


def _get_case_expression() -> Any:
    """创建 case 表达式用于 SQL count。"""
    return func.sum(
        case((HealthLogModel.status == "ok", 1), else_=0)
    )


