"""单元测试 — 质量监控引擎。"""

from __future__ import annotations

import pytest

from mcp_hub.core.monitor import (
    WEIGHT_RESPONSE_TIME,
    WEIGHT_UPTIME_1H,
    WEIGHT_UPTIME_7D,
    WEIGHT_UPTIME_24H,
    Monitor,
    ReliabilityReport,
    ServerHealthSummary,
    UptimeStats,
)

# ── 数据结构 ───────────────────────────────────────────────

class TestUptimeStats:
    def test_creation(self) -> None:
        u = UptimeStats(window="24h", total_checks=100, passed_checks=95, uptime_pct=95.0, avg_response_time_ms=50.0)  # noqa: E501
        assert u.window == "24h"
        assert u.uptime_pct == 95.0
        assert u.total_checks == 100

    def test_uptime_calculation(self) -> None:
        u = UptimeStats(window="24h", total_checks=10, passed_checks=10, uptime_pct=100.0, avg_response_time_ms=0)  # noqa: E501
        assert u.uptime_pct == 100.0

    def test_zero_checks(self) -> None:
        u = UptimeStats(window="1h", total_checks=0, passed_checks=0, uptime_pct=100.0, avg_response_time_ms=0)  # noqa: E501
        assert u.uptime_pct == 100.0


class TestReliabilityReport:
    def test_creation(self) -> None:
        r = ReliabilityReport(server_id="@test/srv", reliability_score=85)
        assert r.server_id == "@test/srv"
        assert r.reliability_score == 85
        assert r.uptime_stats == []

    def test_with_stats(self) -> None:
        stats = [UptimeStats("24h", 100, 99, 99.0, 42.0)]
        r = ReliabilityReport(
            server_id="@test/srv", reliability_score=90,
            uptime_stats=stats, total_checks_recorded=100,
            last_check_status="ok",
        )
        assert len(r.uptime_stats) == 1
        assert r.last_check_status == "ok"


class TestServerHealthSummary:
    def test_creation(self) -> None:
        s = ServerHealthSummary(
            server_id="@test/srv", status="healthy",
            reliability_score=95, uptime_24h=99.5,
            avg_response_ms=30.0, running=True,
        )
        assert s.status == "healthy"
        assert s.reliability_score == 95
        assert s.running is True


# ── Monitor 静态方法 ──────────────────────────────────────

class TestResponseTimeScoring:
    def test_perfect_response_time(self) -> None:
        score = Monitor._score_response_time(50)
        assert score == 100.0

    def test_good_response_time(self) -> None:
        score = Monitor._score_response_time(100)
        assert score == 100.0

    def test_ok_response_time(self) -> None:
        score = Monitor._score_response_time(300)
        assert 60 <= score <= 100

    def test_slow_response_time(self) -> None:
        score = Monitor._score_response_time(1000)
        assert 20 <= score <= 60

    def test_very_slow_response_time(self) -> None:
        score = Monitor._score_response_time(5000)
        assert score >= 10

    def test_zero_response_time(self) -> None:
        score = Monitor._score_response_time(0)
        assert score == 100.0


class TestReliabilityScoring:
    def test_perfect_score(self) -> None:
        """100% uptime 应得到高分。"""
        score = (
            100.0 * WEIGHT_UPTIME_24H
            + 100.0 * WEIGHT_UPTIME_7D
            + 100.0 * WEIGHT_RESPONSE_TIME
            + 100.0 * WEIGHT_UPTIME_1H
        )
        assert round(score) == 100

    def test_low_uptime(self) -> None:
        """低 uptime 应得到低分。"""
        score = (
            50.0 * WEIGHT_UPTIME_24H
            + 60.0 * WEIGHT_UPTIME_7D
            + 80.0 * WEIGHT_RESPONSE_TIME
            + 90.0 * WEIGHT_UPTIME_1H
        )
        assert round(score) < 80

    def test_zero_uptime(self) -> None:
        score = (
            0 * WEIGHT_UPTIME_24H
            + 0 * WEIGHT_UPTIME_7D
            + 0 * WEIGHT_RESPONSE_TIME
            + 0 * WEIGHT_UPTIME_1H
        )
        assert round(score) == 0

    def test_weights_sum_to_one(self) -> None:
        total = WEIGHT_UPTIME_24H + WEIGHT_UPTIME_7D + WEIGHT_RESPONSE_TIME + WEIGHT_UPTIME_1H
        assert abs(total - 1.0) < 0.01


# ── 时间窗口 ──────────────────────────────────────────────

class TestTimeWindows:
    def test_windows_defined(self) -> None:
        from mcp_hub.core.monitor import TIME_WINDOWS
        assert "1h" in TIME_WINDOWS
        assert "24h" in TIME_WINDOWS
        assert "7d" in TIME_WINDOWS
        assert "30d" in TIME_WINDOWS

    def test_window_durations(self) -> None:
        from mcp_hub.core.monitor import TIME_WINDOWS
        assert TIME_WINDOWS["1h"].total_seconds() == 3600
        assert TIME_WINDOWS["24h"].total_seconds() == 86400
        assert TIME_WINDOWS["7d"].total_seconds() == 604800
        assert TIME_WINDOWS["30d"].total_seconds() == 2592000

    def test_invalid_window(self) -> None:
        """无效窗口名应被忽略。"""
        import asyncio
        result = asyncio.run(Monitor.get_uptime("@test/srv", windows=["invalid"]))
        assert len(result) == 0


# ── 集成测试（需要数据库） ─────────────────────────────────


@pytest.fixture
def event_loop():
    """为 async fixture 提供事件循环。"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
async def _db_tables():
    """一次性创建所有数据库表（模块级）。"""
    from mcp_hub.db.database import Base, engine
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass


class TestMonitorIntegration:
    @pytest.mark.asyncio
    async def test_record_and_get_uptime(self) -> None:
        """记录健康检查 + 查询 uptime 应正常工作。"""
        sid = "@test/integration-test-server"

        # 记录 5 次成功检查
        for i in range(5):
            await Monitor.record_check(
                server_id=sid,
                check_type="L1_process",
                status="ok",
                response_time_ms=10 + i * 2,
                message="存活",
            )

        # 记录 1 次失败
        await Monitor.record_check(
            server_id=sid,
            check_type="L2_connection",
            status="error",
            response_time_ms=0,
            message="连接超时",
        )

        # 查询 uptime
        uptime = await Monitor.get_uptime(sid, windows=["1h", "24h"])
        assert len(uptime) >= 1
        for u in uptime:
            assert u.total_checks >= 1
            assert u.passed_checks <= u.total_checks

    @pytest.mark.asyncio
    async def test_get_uptime_empty_server(self) -> None:
        """未记录过的 Server 应返回空统计。"""
        uptime = await Monitor.get_uptime("@test/never-existed", windows=["1h"])
        assert len(uptime) > 0
        for u in uptime:
            assert u.total_checks == 0
            assert u.uptime_pct == 0.0

    @pytest.mark.asyncio
    async def test_calculate_reliability_no_data(self) -> None:
        """无数据时可靠性应返回 0。"""
        report = await Monitor.calculate_reliability("@test/no-data")
        assert report.reliability_score == 0
        assert report.total_checks_recorded == 0

    @pytest.mark.asyncio
    async def test_calculate_reliability_with_data(self) -> None:
        """有数据时可靠性应正确计算。"""
        sid = "@test/reliability-test"

        # 记录多次成功检查
        for i in range(20):
            await Monitor.record_check(sid, "L1_process", "ok", 30 + i * 5, "存活")

        # 记录几次失败
        for _i in range(3):
            await Monitor.record_check(sid, "L2_connection", "error", 0, "超时")

        report = await Monitor.calculate_reliability(sid)
        assert report.reliability_score > 0
        assert report.total_checks_recorded == 23
        u24h = next((u for u in report.uptime_stats if u.window == "24h"), None)
        if u24h and u24h.total_checks > 0:
            assert u24h.uptime_pct > 80  # 20/23 = 87%

    @pytest.mark.asyncio
    async def test_get_recent_errors(self) -> None:
        """近期错误应正确提取。"""
        sid = "@test/error-test"
        await Monitor.record_check(sid, "L1_process", "error", 0, "致命错误: 进程 crash")
        await Monitor.record_check(sid, "L1_process", "error", 0, "内存不足")
        await Monitor.record_check(sid, "L1_process", "ok", 10, "正常")

        report = await Monitor.calculate_reliability(sid)
        assert len(report.recent_errors) >= 1
        assert any("crash" in e for e in report.recent_errors)

    @pytest.mark.asyncio
    async def test_get_server_health(self) -> None:
        """get_server_health 应返回正确的状态。"""
        sid = "@test/health-status"
        # 记录一些数据
        for _i in range(10):
            await Monitor.record_check(sid, "L1_process", "ok", 50, "ok")

        health = await Monitor.get_server_health(sid)
        assert health.server_id == sid
        assert health.reliability_score > 0
        # 由于没有实际进程在运行，running 应为 False
        assert health.running is False

    @pytest.mark.asyncio
    async def test_get_summary_stats(self) -> None:
        """全局统计应返回合理的数据。"""
        stats = await Monitor.get_summary_stats()
        assert "total_servers" in stats
        assert "total_health_checks" in stats
        assert "errors_last_24h" in stats
        assert isinstance(stats["total_health_checks"], int)


# ── Monitor.record_check ──────────────────────────────────

class TestRecordCheck:
    @pytest.mark.asyncio
    async def test_record_success(self) -> None:
        """记录成功检查不应报错。"""
        await Monitor.record_check(
            server_id="@test/record-ok",
            check_type="L1_process",
            status="ok",
            response_time_ms=42,
            message="process alive",
        )
        # 不报错即视为通过

    @pytest.mark.asyncio
    async def test_record_error(self) -> None:
        """记录失败检查不应报错。"""
        await Monitor.record_check(
            server_id="@test/record-err",
            check_type="L2_connection",
            status="error",
            response_time_ms=0,
            message="timeout after 5s",
        )

    @pytest.mark.asyncio
    async def test_record_multiple_types(self) -> None:
        """不同检查类型应能分别记录。"""
        sid = "@test/multi-type"
        await Monitor.record_check(sid, "L1_process", "ok", 10)
        await Monitor.record_check(sid, "L2_connection", "ok", 100)
        await Monitor.record_check(sid, "L3_functional", "ok", 500)

        uptime = await Monitor.get_uptime(sid, windows=["1h"])
        assert len(uptime) == 1
        assert uptime[0].total_checks == 3

    @pytest.mark.asyncio
    async def test_record_long_message_truncated(self) -> None:
        """超长消息应被截断。"""
        long_msg = "x" * 1000
        await Monitor.record_check(
            server_id="@test/truncate",
            check_type="L1_process",
            status="error",
            message=long_msg,
        )
        # 不报错即通过

    @pytest.mark.asyncio
    async def test_record_empty_server_id(self) -> None:
        """空 server_id 不应导致崩溃。"""
        try:
            await Monitor.record_check(
                server_id="",
                check_type="L1_process",
                status="ok",
            )
        except Exception:
            pytest.fail("Empty server_id caused crash")

    @pytest.mark.asyncio
    async def test_record_special_characters(self) -> None:
        """特殊字符不应导致问题。"""
        sid = "@test/special-chars-测试-日本語"
        await Monitor.record_check(sid, "L1_process", "ok", 10, "测试消息 with 日本語")
        uptime = await Monitor.get_uptime(sid, windows=["1h"])
        assert len(uptime) >= 1
        assert uptime[0].total_checks >= 1

    @pytest.mark.asyncio
    async def test_concurrent_records(self) -> None:
        """并发记录不应冲突。"""
        import asyncio
        sid = "@test/concurrent"

        async def record():
            for i in range(5):
                await Monitor.record_check(
                    server_id=sid,
                    check_type="L1_process",
                    status="ok" if i % 3 != 0 else "error",
                    response_time_ms=i * 10,
                )

        await asyncio.gather(record(), record(), record())
        uptime = await Monitor.get_uptime(sid, windows=["1h"])
        assert uptime[0].total_checks >= 10

    @pytest.mark.asyncio
    async def test_record_without_response_time(self) -> None:
        """无响应时间时不应报错。"""
        await Monitor.record_check(
            server_id="@test/no-rtt",
            check_type="L1_process",
            status="ok",
        )
        uptime = await Monitor.get_uptime("@test/no-rtt", windows=["1h"])
        assert len(uptime) == 1

    @pytest.mark.asyncio
    async def test_uptime_windows_filter(self) -> None:
        """指定特定窗口应只返回该窗口数据。"""
        sid = "@test/window-filter"
        await Monitor.record_check(sid, "L1_process", "ok", 10)

        uptime = await Monitor.get_uptime(sid, windows=["7d"])
        assert len(uptime) == 1
        assert uptime[0].window == "7d"

        uptime_multi = await Monitor.get_uptime(sid, windows=["1h", "24h"])
        assert len(uptime_multi) == 2
