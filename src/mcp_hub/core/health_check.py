"""三级健康检查引擎。

L1 (每 5s):  进程级检查 — os.kill(pid, 0) 确认进程存活
L2 (每 30s): 连接级检查 — 向 stdin 写入 JSON-RPC ping，确认 pipe 未断开
L3 (每 5min): 功能级检查 — 确认 keepalive 仍在正常工作
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp_hub.logging_config import get_logger

if TYPE_CHECKING:
    from mcp_hub.core.process_manager import ProcessManager
    from mcp_hub.core.registry import Registry

logger = get_logger(__name__)

# 三级检查间隔（秒）
LEVEL_INTERVALS = {1: 5, 2: 30, 3: 300}


@dataclass
class HealthResult:
    server_id: str
    level: int  # 1, 2, 3
    passed: bool
    response_time_ms: int = 0
    message: str = ""


class HealthChecker:
    """三级健康检查器。

    使用方式:
        checker = HealthChecker()
        asyncio.create_task(checker.monitor_loop(pm, registry))
    """

    LEVEL_INTERVALS = LEVEL_INTERVALS

    def __init__(self) -> None:
        self._last_check: dict[str, dict[int, float]] = {}  # server_id -> {level: timestamp}

    # ── L1: 进程级检查 ──────────────────────────────────────

    async def check_l1(self, server_id: str, pid: int) -> HealthResult:
        """进程级检查 — 只查进程是否存在（最轻量）。"""
        start = time.monotonic()
        try:
            os.kill(pid, 0)  # 不发送信号，只检查进程权限
            passed = True
            msg = "进程存活"
        except (OSError, ProcessLookupError):
            passed = False
            msg = "进程不存在"
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return HealthResult(server_id, 1, passed, elapsed_ms, msg)

    # ── L2: 连接级检查 ──────────────────────────────────────

    async def check_l2(self, server_id: str, stdin) -> HealthResult:
        """连接级检查 — 尝试写入 JSON-RPC ping 到 stdin。

        如果 stdin pipe 已经断开（BrokenPipeError），说明连接级异常。
        写入成功说明 MCP Server 的 stdin 通道仍然畅通。
        """
        start = time.monotonic()
        try:
            async with asyncio.timeout(5.0):
                stdin.write(
                    b'{"jsonrpc":"2.0","id":999,"method":"ping","params":{"_health":"l2"}}\n'
                )
                await stdin.drain()
                passed = True
                msg = "连接正常（stdin 通道畅通）"
        except asyncio.TimeoutError:
            passed = False
            msg = "连接超时（stdin 写入阻塞超过 5s）"
        except (BrokenPipeError, OSError, ConnectionResetError) as e:
            passed = False
            msg = f"连接断开: {type(e).__name__}"
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return HealthResult(server_id, 2, passed, elapsed_ms, msg)

    # ── L3: 功能级检查 ──────────────────────────────────────

    async def check_l3(
        self,
        server_id: str,
        managed_process,  # ManagedProcess
    ) -> HealthResult:
        """功能级检查 — 确认 keepalive ping 仍在正常工作。

        ProcessManager 每 10 秒发送一次 keepalive ping。
        如果最后一次成功的时间戳在 30 秒内，认为功能正常。
        这避开了需要读取 stdout 的问题（stdout 已重定向到日志文件）。
        """
        start = time.monotonic()
        last_ok = getattr(managed_process, "last_keepalive_ok", None)
        now = asyncio.get_event_loop().time()

        if last_ok is not None and (now - last_ok) < 30.0:
            passed = True
            msg = f"功能正常（keepalive 活跃，距上次成功 {now - last_ok:.0f}s）"
        elif last_ok is not None:
            passed = False
            msg = f"功能异常（距上次 keepalive {now - last_ok:.0f}s 超过阈值）"
        else:
            passed = False
            msg = "功能未知（尚未收到 keepalive 响应）"

        elapsed_ms = int((time.monotonic() - start) * 1000)
        return HealthResult(server_id, 3, passed, elapsed_ms, msg)

    # ── 批量检查 ────────────────────────────────────────────

    async def check_all(
        self,
        process_manager: ProcessManager,
        registry: Registry,
    ) -> list[HealthResult]:
        """对所有运行中的 Server 执行完整三级健康检查。"""
        results: list[HealthResult] = []
        now = asyncio.get_event_loop().time()

        for proc in process_manager.list_running():
            sid = proc.server_id
            if sid not in self._last_check:
                self._last_check[sid] = {}

            # L1: 每次都跑（最轻量）
            l1 = await self.check_l1(sid, proc.pid)
            results.append(l1)
            if not l1.passed:
                await registry.update_status(sid, "error")
                continue  # L1 失败，L2/L3 没意义

            # L2: 按间隔执行
            last_l2 = self._last_check[sid].get(2, 0.0)
            if now - last_l2 >= LEVEL_INTERVALS[2]:
                if proc.process and proc.process.stdin:
                    l2 = await self.check_l2(sid, proc.process.stdin)
                    results.append(l2)
                    self._last_check[sid][2] = now
                    if not l2.passed:
                        await registry.update_status(sid, "error")

            # L3: 按间隔执行
            last_l3 = self._last_check[sid].get(3, 0.0)
            if now - last_l3 >= LEVEL_INTERVALS[3]:
                l3 = await self.check_l3(sid, proc)
                results.append(l3)
                self._last_check[sid][3] = now
                if not l3.passed:
                    logger.warning(
                        "health_check.l3_failed",
                        server_id=sid,
                        message=l3.message,
                    )

        return results

    # ── 持续监控 ─────────────────────────────────────────────

    async def monitor_loop(
        self,
        process_manager: ProcessManager,
        registry: Registry,
        interval: int = 5,
    ) -> None:
        """持续监控循环（永不退出）。

        每 interval 秒运行一次 check_all，对失败的 Server 触发自动恢复。
        """
        logger.info(
            "health_check.monitor_started",
            interval=interval,
            l1_interval=LEVEL_INTERVALS[1],
            l2_interval=LEVEL_INTERVALS[2],
            l3_interval=LEVEL_INTERVALS[3],
        )
        while True:
            try:
                results = await self.check_all(process_manager, registry)
                for r in results:
                    if not r.passed:
                        logger.warning(
                            "health_check.failed",
                            server_id=r.server_id,
                            level=r.level,
                            message=r.message,
                        )
                        await self._auto_restart(
                            r.server_id, process_manager, registry
                        )
            except Exception as e:
                logger.error(
                    "health_check.monitor_error",
                    error=str(e),
                )
            await asyncio.sleep(interval)

    # ── 自动恢复 ─────────────────────────────────────────────

    async def _auto_restart(
        self,
        server_id: str,
        process_manager: ProcessManager,
        registry: Registry,
    ) -> bool:
        """自动重启失败的 Server（最多 3 次）。"""
        proc = process_manager.get(server_id)
        if proc and proc.restart_count >= 3:
            logger.error(
                "health_check.max_restarts_exceeded",
                server_id=server_id,
                restart_count=proc.restart_count,
            )
            return False

        logger.info(
            "health_check.auto_restart",
            server_id=server_id,
            restart_count=proc.restart_count if proc else 0,
        )
        await process_manager.kill(server_id)
        await asyncio.sleep(2)
        return True  # 通知调用方重新 spawn
