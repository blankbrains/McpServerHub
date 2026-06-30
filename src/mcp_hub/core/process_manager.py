"""子进程生命周期管理 — 全局单例。"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mcp_hub.exceptions import ProcessStartupError, ServerAlreadyRunningError
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ManagedProcess:
    server_id: str
    pid: int | None = None
    process: asyncio.subprocess.Process | None = None
    started_at: float | None = None
    restart_count: int = 0
    log_file: Path | None = None
    log_fd: int | None = None  # log file descriptor (closed on kill)
    last_keepalive_ok: float | None = None  # timestamp of last successful keepalive ping


# 全局进程管理器单例
_PM_INSTANCE: ProcessManager | None = None


def get_process_manager() -> ProcessManager:
    """获取全局进程管理器（API 和 CLI 共享同一个实例）。"""
    global _PM_INSTANCE
    if _PM_INSTANCE is None:
        _PM_INSTANCE = ProcessManager()
    return _PM_INSTANCE


class ProcessManager:
    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or Path.home() / ".config" / "mcp-hub" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._processes: dict[str, ManagedProcess] = {}
        self._lock = asyncio.Lock()

    async def spawn(
        self,
        server_id: str,
        command: str,
        args: list[str] | None = None,
    ) -> ManagedProcess:
        async with self._lock:
            if server_id in self._processes:
                proc = self._processes[server_id]
                if proc.process and proc.process.returncode is None:
                    raise ServerAlreadyRunningError(server_id, proc.pid)

            log_file = self.log_dir / f"{server_id.replace('/', '_').replace('@', '')}.log"
            log_fd = open(log_file, "a", encoding="utf-8")  # noqa: SIM115
            log_fd.write(f"\n--- {datetime.now().isoformat()} Started ---\n")
            log_fd.flush()

            cmd_list = command.split()
            full_cmd = cmd_list[0]
            full_args = cmd_list[1:] + (args or [])

            process = await asyncio.create_subprocess_exec(
                full_cmd,
                *full_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=log_fd,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ},
            )

            managed = ManagedProcess(
                server_id=server_id,
                pid=process.pid,
                process=process,
                started_at=asyncio.get_event_loop().time(),
                log_file=log_file,
                log_fd=log_fd.fileno(),
            )
            self._processes[server_id] = managed
            logger.info(
                "process.spawned",
                server_id=server_id,
                pid=process.pid,
                command=full_cmd,
            )

            # Small delay to check if process died immediately
            await asyncio.sleep(0.5)
            if process.returncode is not None and process.returncode != 0:
                error_msg = log_file.read_text().splitlines()[-5:] if log_file.exists() else []
                logger.error(
                    "process.startup_failed",
                    server_id=server_id,
                    exit_code=process.returncode,
                    stderr=''.join(error_msg)[:500],
                )
                raise ProcessStartupError(server_id, process.returncode, ''.join(error_msg))

            # Start keep-alive pings for stdio-based MCP servers
            self._start_keepalive(server_id)

            return managed

    def _start_keepalive(self, server_id: str) -> None:
        """定期发送 keep-alive 保持 stdio MCP Server 存活。"""
        import asyncio
        async def _ping():
            try:
                while True:
                    proc = self._processes.get(server_id)
                    if not proc or not proc.process or proc.process.returncode is not None:
                        break
                    # Send JSON-RPC ping via stdin
                    if proc.process.stdin:
                        try:
                            proc.process.stdin.write(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
                            await proc.process.stdin.drain()
                            proc.last_keepalive_ok = asyncio.get_event_loop().time()
                        except (BrokenPipeError, OSError):
                            break
                    await asyncio.sleep(10)
            except Exception:
                pass

        task = asyncio.ensure_future(_ping())
        # Store task to prevent garbage collection
        self._keepalive_tasks = getattr(self, "_keepalive_tasks", {})
        self._keepalive_tasks[server_id] = task

    async def kill(self, server_id: str, timeout: float = 5.0) -> bool:
        """优雅关闭进程。"""
        async with self._lock:
            proc = self._processes.get(server_id)
            if not proc or not proc.process:
                return False

            pid = proc.process.pid
            if pid is None:
                return False

            try:
                proc.process.terminate()
                try:
                    await asyncio.wait_for(proc.process.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    proc.process.kill()
                    await proc.process.wait()
            except ProcessLookupError:
                pass
            finally:
                self._processes.pop(server_id, None)
                logger.info("process.killed", server_id=server_id, pid=pid)

            if proc.log_file:
                try:
                    with open(proc.log_file, "a", encoding="utf-8") as f:
                        f.write(f"--- {datetime.now().isoformat()} Stopped ---\n")
                except OSError:
                    pass
            # Close the log file descriptor if still open
            if proc.log_fd is not None:
                try:
                    os.close(proc.log_fd)
                except OSError:
                    pass
                proc.log_fd = None
            return True

    def get(self, server_id: str) -> ManagedProcess | None:
        return self._processes.get(server_id)

    def list_running(self) -> list[ManagedProcess]:
        return [
            p for p in self._processes.values()
            if p.process and p.process.returncode is None
        ]

    def is_running(self, server_id: str) -> bool:
        proc = self._processes.get(server_id)
        return bool(proc and proc.process and proc.process.returncode is None)

    async def cleanup_all(self) -> None:
        """关闭所有日志文件描述符并清理进程（测试用）。"""
        async with self._lock:
            for proc in list(self._processes.values()):
                if proc.log_fd is not None:
                    try:
                        os.close(proc.log_fd)
                    except OSError:
                        pass
                    proc.log_fd = None
                if proc.process and proc.process.returncode is None:
                    try:
                        proc.process.terminate()
                    except ProcessLookupError:
                        pass
            self._processes.clear()
