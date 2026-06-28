"""三级健康检查引擎。"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass


@dataclass
class HealthResult:
    server_id: str
    level: int  # 1, 2, 3
    passed: bool
    response_time_ms: int = 0
    message: str = ""


class HealthChecker:
    LEVEL_INTERVALS = {1: 5, 2: 30, 3: 300}  # seconds

    async def check_l1(self, server_id: str, pid: int) -> HealthResult:
        """进程级检查 — 只查进程是否存在。"""
        start = time.monotonic()
        try:
            os.kill(pid, 0)
            passed = True
            msg = "进程存活"
        except (OSError, ProcessLookupError):
            passed = False
            msg = "进程不存在"
        elapsed = int((time.monotonic() - start) * 1000)
        return HealthResult(server_id, 1, passed, elapsed, msg)

    async def check_all(self, process_manager, registry) -> list[HealthResult]:
        """对所有运行中的 Server 执行健康检查。"""
        results = []
        for proc in process_manager.list_running():
            result = await self.check_l1(proc.server_id, proc.pid)
            results.append(result)
            if not result.passed:
                await registry.update_status(proc.server_id, "error")
        return results

    async def monitor_loop(self, process_manager, registry, interval: int = 10):
        """持续监控循环。"""
        while True:
            results = await self.check_all(process_manager, registry)
            for r in results:
                log_msg = f"[{r.level}] {r.server_id}: {'✅' if r.passed else '❌'} {r.message}"
                if not r.passed:
                    log_msg += f" — 正在尝试重启..."
                    print(log_msg)
                    await self._auto_restart(r.server_id, process_manager, registry)
                else:
                    pass  # silent for healthy
            await asyncio.sleep(interval)

    async def _auto_restart(self, server_id: str, process_manager, registry) -> bool:
        """自动重启 Server。"""
        proc = process_manager.get(server_id)
        if proc and proc.restart_count >= 3:
            print(f"  ⚠️ {server_id} 已重启 {proc.restart_count} 次，停止自动恢复")
            return False

        await process_manager.kill(server_id)
        await asyncio.sleep(2)
        return True  # signal caller to re-spawn
