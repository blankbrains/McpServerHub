"""单元测试 — 健康检查。"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_hub.core.health_check import HealthChecker, HealthResult
from mcp_hub.core.process_manager import ManagedProcess


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


class TestHealthCheckCompatibility:
    async def test_l1_missing_pid_is_unhealthy(self, checker: HealthChecker) -> None:
        result = await checker.check_l1("missing-pid", None)

        assert result.passed is False
        assert result.message == "进程不存在"

    async def test_l2_uses_python_310_compatible_timeout(
        self,
        checker: HealthChecker,
    ) -> None:
        stdin = MagicMock(spec=asyncio.StreamWriter)
        stdin.drain = AsyncMock(return_value=None)

        result = await checker.check_l2("stdio-server", stdin)

        assert result.passed is True
        stdin.write.assert_called_once()
        stdin.drain.assert_awaited_once()


class TestAutoRestart:
    async def test_prepare_restart_preserves_spawn_configuration(
        self,
        checker: HealthChecker,
    ) -> None:
        process_manager = MagicMock()
        process_manager.get.return_value = ManagedProcess(
            server_id="weather",
            restart_count=1,
            spawn_command="npx",
            spawn_args=["-y", "weather-mcp"],
            spawn_env={"WEATHER_API_KEY": "test-secret"},
            spawn_cwd="/srv/weather",
        )
        process_manager.kill = AsyncMock(return_value=True)

        restart_source = await checker._prepare_auto_restart(
            "weather",
            process_manager,
            MagicMock(),
        )

        assert restart_source is not None
        assert restart_source.restart_count == 2
        assert restart_source.spawn_args == ["-y", "weather-mcp"]
        assert restart_source.spawn_env == {"WEATHER_API_KEY": "test-secret"}
        assert restart_source.spawn_cwd == "/srv/weather"
        process_manager.kill.assert_awaited_once_with("weather")

    async def test_prepare_restart_stops_after_three_attempts(
        self,
        checker: HealthChecker,
    ) -> None:
        process_manager = MagicMock()
        process_manager.get.return_value = ManagedProcess(
            server_id="weather",
            restart_count=3,
            spawn_command="npx",
        )
        process_manager.kill = AsyncMock()

        restart_source = await checker._prepare_auto_restart(
            "weather",
            process_manager,
            MagicMock(),
        )

        assert restart_source is None
        process_manager.kill.assert_not_awaited()
