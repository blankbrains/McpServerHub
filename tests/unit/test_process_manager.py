"""单元测试 — 进程管理器。

仅测试 ProcessManager 的逻辑层（spawn/kill/list/单例），
通过 mock 避免创建真实子进程。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_hub.core.process_manager import (
    ManagedProcess,
    ProcessManager,
    get_process_manager,
)
from mcp_hub.exceptions import ProcessStartupError, ServerAlreadyRunningError


@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前重置全局单例，避免测试间互相干扰。"""
    import mcp_hub.core.process_manager as pm
    pm._PM_INSTANCE = None
    yield
    pm._PM_INSTANCE = None


@pytest.fixture
async def pm(temp_dir: Path) -> ProcessManager:
    pm = ProcessManager(log_dir=temp_dir)
    yield pm
    await pm.cleanup_all()


# ── 单例 ──────────────────────────────────────────────────


class TestGetProcessManager:
    def test_get_instance(self) -> None:
        """get_process_manager() 应返回同一单例。"""
        p1 = get_process_manager()
        p2 = get_process_manager()
        assert p1 is p2
        assert isinstance(p1, ProcessManager)

    def test_initial_state(self) -> None:
        pm = get_process_manager()
        assert pm._processes == {}


# ── Mock 辅助 ─────────────────────────────────────────────


def _make_mock_process(
    pid: int = 12345,
    returncode: int | None = None,
    stdin_supports: bool = True,
) -> MagicMock:
    """创建一个模拟的子进程对象。"""
    proc = MagicMock()
    proc.pid = pid
    proc.returncode = returncode
    proc.stdin = MagicMock() if stdin_supports else None
    proc.stdin.drain = AsyncMock() if stdin_supports else None
    proc.wait = AsyncMock(return_value=0)
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    return proc


# ── ProcessManager 核心逻辑 ───────────────────────────────


class TestProcessManagerSpawn:
    @patch("asyncio.create_subprocess_exec")
    async def test_spawn_and_get(self, mock_spawn: MagicMock, pm: ProcessManager) -> None:
        """spawn 后 get() 应返回 ManagedProcess。"""
        mock_spawn.return_value = _make_mock_process(pid=10001)
        managed = await pm.spawn("test/server", "echo", ["hello"])
        assert managed.server_id == "test/server"
        assert managed.pid == 10001
        assert managed.process is not None

        # get 验证
        fetched = pm.get("test/server")
        assert fetched is not None
        assert fetched.pid == 10001

    @patch("asyncio.create_subprocess_exec")
    async def test_spawn_process_log_created(self, mock_spawn: MagicMock, pm: ProcessManager, temp_dir: Path) -> None:
        """spawn 后日志文件应被创建。"""
        mock_spawn.return_value = _make_mock_process(pid=20001)
        await pm.spawn("test/server", "echo")
        log_file = temp_dir / "test_server.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "Started" in content

    @patch("asyncio.create_subprocess_exec")
    async def test_spawn_duplicate(self, mock_spawn: MagicMock, pm: ProcessManager) -> None:
        """重复 spawn 同一 server_id 应抛出 ServerAlreadyRunningError。"""
        mock_spawn.return_value = _make_mock_process(pid=30001)
        await pm.spawn("test/server", "echo")
        with pytest.raises(ServerAlreadyRunningError):
            await pm.spawn("test/server", "echo")

    @patch("asyncio.create_subprocess_exec")
    async def test_spawn_immediate_exit(self, mock_spawn: MagicMock, pm: ProcessManager) -> None:
        """进程立即退出应抛出 ProcessStartupError。"""
        mock_spawn.return_value = _make_mock_process(pid=40001, returncode=1)
        with pytest.raises(ProcessStartupError, match="exit code=1"):
            await pm.spawn("test/server", "bad_command")


class TestProcessManagerKill:
    @patch("asyncio.create_subprocess_exec")
    async def test_kill_existing(self, mock_spawn: MagicMock, pm: ProcessManager) -> None:
        """kill 已注册的进程应返回 True 并从 _processes 移除。"""
        mock_spawn.return_value = _make_mock_process(pid=50001)
        await pm.spawn("test/server", "echo")
        result = await pm.kill("test/server")
        assert result is True
        assert pm.get("test/server") is None

    async def test_kill_non_existent(self, pm: ProcessManager) -> None:
        """kill 不存在的 server_id 应返回 False。"""
        result = await pm.kill("nonexistent")
        assert result is False

    @patch("asyncio.create_subprocess_exec")
    async def test_kill_timeout_force_kill(self, mock_spawn: MagicMock, pm: ProcessManager) -> None:
        """kill 超时应调用 kill() 强制终止。"""
        proc_mock = _make_mock_process(pid=60001)
        proc_mock.wait = AsyncMock(side_effect=[asyncio.TimeoutError(), 0])  # First call times out
        mock_spawn.return_value = proc_mock
        await pm.spawn("test/server", "echo")
        result = await pm.kill("test/server", timeout=0.01)
        assert result is True
        proc_mock.kill.assert_called_once()


class TestProcessManagerQuery:
    @patch("asyncio.create_subprocess_exec")
    async def test_list_running(self, mock_spawn: MagicMock, pm: ProcessManager) -> None:
        """list_running 只返回 returncode 为 None 的进程。"""
        mock_spawn.return_value = _make_mock_process(pid=70001)
        await pm.spawn("srv1", "echo")
        running = pm.list_running()
        assert len(running) == 1
        assert running[0].server_id == "srv1"

    @patch("asyncio.create_subprocess_exec")
    async def test_is_running(self, mock_spawn: MagicMock, pm: ProcessManager) -> None:
        """is_running 正确反映运行状态。"""
        mock_spawn.return_value = _make_mock_process(pid=80001)
        await pm.spawn("test/server", "echo")
        assert pm.is_running("test/server") is True
        await pm.kill("test/server")
        assert pm.is_running("test/server") is False

    def test_get_returns_none(self, pm: ProcessManager) -> None:
        """不存在的 server_id 返回 None。"""
        assert pm.get("nonexistent") is None


class TestManagedProcess:
    def test_create(self) -> None:
        mp = ManagedProcess(server_id="@test/srv")
        assert mp.server_id == "@test/srv"
        assert mp.pid is None
        assert mp.restart_count == 0

    def test_with_all_fields(self) -> None:
        mp = ManagedProcess(
            server_id="@test/srv",
            pid=9999,
            restart_count=3,
        )
        assert mp.pid == 9999
        assert mp.restart_count == 3
