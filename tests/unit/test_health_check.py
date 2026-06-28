"""单元测试 — 健康检查。"""

from __future__ import annotations

import os

import pytest

from mcp_hub.core.health_check import HealthChecker, HealthResult


@pytest.fixture
def checker() -> HealthChecker:
    return HealthChecker()


class TestHealthCheckL1:
    async def test_l1_alive_process(self, checker: HealthChecker) -> None:
        """测试 L1 对当前 Python 进程的检查 — 应该存活。"""
        result = await checker.check_l1("test", os.getpid())
        assert result.passed is True
        assert result.level == 1
        assert result.response_time_ms >= 0
        assert "存活" in result.message

    async def test_l1_dead_process(self, checker: HealthChecker) -> None:
        """测试 L1 对不存在进程的检查 — 应该失败。"""
        result = await checker.check_l1("dead", 999999)
        assert result.passed is False
        assert result.level == 1

    async def test_l1_result_structure(self, checker: HealthChecker) -> None:
        """验证 HealthResult 结构。"""
        result = await checker.check_l1("test", os.getpid())
        assert isinstance(result, HealthResult)
        assert result.server_id == "test"
        assert result.level == 1
        assert isinstance(result.passed, bool)
        assert isinstance(result.response_time_ms, int)
        assert isinstance(result.message, str)


class TestHealthCheckIntervals:
    def test_interval_values(self) -> None:
        """验证三级检查间隔。"""
        assert HealthChecker.LEVEL_INTERVALS == {1: 5, 2: 30, 3: 300}


class TestHealthResult:
    def test_dataclass_creation(self) -> None:
        r = HealthResult("srv1", 2, True, 42, "ok")
        assert r.server_id == "srv1"
        assert r.level == 2
        assert r.passed is True
        assert r.response_time_ms == 42
        assert r.message == "ok"

    def test_dataclass_defaults(self) -> None:
        r = HealthResult("srv1", 1, False)
        assert r.response_time_ms == 0
        assert r.message == ""
