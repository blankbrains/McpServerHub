"""MCP 协议网关 — Hub 作为单个 stdio 入口聚合所有子 Server。

Agent（Claude Code / Codex / Cursor）通过 stdio 连接 Hub Gateway，
Gateway 将请求路由到对应的 MCP Server 子进程，并记录每次调用。

工作方式:
  1. Agent 通过 stdio 连接 Hub Gateway
  2. Gateway 为每个已安装且已启用的 Server 启动子进程
  3. Agent 发送 tools/list → Gateway 聚合所有 Server 的 tools
  4. Agent 发送 tools/call → Gateway 路由到对应 Server
  5. 每次 tools/call 自动记录到 usage_stats 表（server_id/tool/duration）
  6. 使用设备遥测令牌将脱敏指标可靠上报到远程 Hub
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time as _time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

import httpx2
from mcp import ClientSession, types
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

from mcp_hub import __version__
from mcp_hub.core.gateway_config import (
    GatewayServerSpec,
    get_gateway_config_path,
    load_gateway_config,
    split_legacy_command,
)
from mcp_hub.core.process_env import filter_process_environment
from mcp_hub.core.protocol import (
    SUPPORTED_PROTOCOL_VERSIONS,
    ProtocolState,
    negotiate_protocol,
    supports_server_method,
)
from mcp_hub.core.registry import Registry
from mcp_hub.core.telemetry import (
    TelemetryReporter,
    classify_error,
    estimate_payload_bytes,
    estimate_payload_tokens,
)
from mcp_hub.exceptions import GatewayError
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)


def _filter_gateway_env() -> dict[str, str]:
    """保留基础运行环境，不把 Hub 或包管理器凭证隐式传给子进程。"""
    return filter_process_environment()


async def _drain_stderr(server_id: str, stderr_stream: asyncio.StreamReader) -> None:
    """后台任务：持续读取子进程 stderr 防止管道阻塞。"""
    try:
        while True:
            line = await stderr_stream.readline()
            if not line:
                break
            logger.debug(
                "gateway.stderr",
                server_id=server_id,
                line=line.decode(errors="replace").rstrip()[:200],
            )
    except Exception:
        pass


# ── 调用记录 ────────────────────────────────────────────────


async def _record_call_safe(
    server_id: str,
    tool_name: str,
    duration_ms: int = 0,
    status: str = "ok",
    user_id: str = "",
    token_count: int = 0,
) -> None:
    """异步写入自托管本地统计；远程上报统一由设备遥测处理。"""
    caller_user_id = user_id or "local-gateway"
    try:
        from sqlalchemy import text

        from mcp_hub.db.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO usage_stats "
                    "(server_id, user_id, tool_name, status, duration_ms, token_count) "
                    "VALUES (:sid, :uid, :tool, :status, :dur, :tokens)"
                ),
                {
                    "sid": server_id,
                    "uid": caller_user_id,
                    "tool": tool_name,
                    "status": status,
                    "dur": duration_ms,
                    "tokens": token_count,
                },
            )
            await session.commit()
    except Exception as e:
        logger.warning("gateway.record_call_failed", server_id=server_id, error=str(e))


# ── ManagedMCP: 单个子 Server 连接 ──────────────────────────


@dataclass
class _PendingReq:
    future: asyncio.Future[Any]
    sent_at: float


class ManagedMCP:
    """管理一个子 MCP Server 的 stdio 连接。

    使用后台 reader 读取 stdout，按 req_id 分发响应，避免竞态。
    """

    def __init__(
        self,
        server_id: str,
        process: asyncio.subprocess.Process,
        stdin: asyncio.StreamWriter,
        stdout: asyncio.StreamReader,
        *,
        version: str = "",
        transport: str = "stdio",
        on_notification: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.server_id = server_id
        self.process = process
        self.stdin = stdin
        self.stdout = stdout
        self.version = version
        self.transport = transport
        self.protocol_version = ""
        self.tools: list[dict[str, Any]] = []
        self.capabilities: set[str] = set()
        self._request_id = 0
        self._pending: dict[int, _PendingReq] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._shutdown = False
        self._on_notification = on_notification

    def _fail_pending(self, message: str) -> None:
        """Fail outstanding requests immediately when the child stream is unusable."""
        for pending in self._pending.values():
            if not pending.future.done():
                pending.future.set_exception(
                    GatewayError(message, server_id=self.server_id)
                )
        self._pending.clear()

    async def start_reader(self) -> None:
        """启动后台 stdout reader。"""
        async def _reader() -> None:
            while not self._shutdown:
                try:
                    line = await asyncio.wait_for(
                        self.stdout.readline(),
                        timeout=3600,
                    )
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(
                        "gateway.server_read_failed",
                        server_id=self.server_id,
                        error=type(exc).__name__,
                    )
                    self._fail_pending("MCP Server stdout 读取失败")
                    break
                if not line:
                    logger.warning("gateway.server_eof", server_id=self.server_id)
                    self._fail_pending("MCP Server 已关闭 stdout")
                    break
                try:
                    msg = json.loads(line.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if "id" not in msg:
                    method = msg.get("method")
                    params = msg.get("params", {})
                    if (
                        self._on_notification is not None
                        and isinstance(method, str)
                        and isinstance(params, dict)
                    ):
                        try:
                            await self._on_notification(method, params)
                        except Exception as exc:
                            logger.debug(
                                "gateway.child_notification_failed",
                                server_id=self.server_id,
                                method=method,
                                error=type(exc).__name__,
                            )
                    continue
                req_id = msg["id"]
                pending = self._pending.pop(req_id, None)
                if pending:
                    if "result" in msg:
                        pending.future.set_result(msg["result"])
                    elif "error" in msg:
                        pending.future.set_exception(
                            GatewayError(
                                msg["error"].get("message", str(msg["error"])),
                                server_id=self.server_id,
                                details={"raw_error": msg["error"]},
                            )
                        )
                    else:
                        pending.future.set_result(msg)

        self._reader_task = asyncio.create_task(_reader())

    async def initialize(self) -> bool:
        """初始化子 Server，获取工具列表。"""
        await self.start_reader()
        result: Any | None = None
        for protocol_version in (
            types.LATEST_PROTOCOL_VERSION,
            "2025-06-18",
            "2024-11-05",
        ):
            try:
                result = await self._send_request(
                    "initialize",
                    {
                        "protocolVersion": protocol_version,
                        "capabilities": {},
                        "clientInfo": {"name": "mcp-hub", "version": __version__},
                    },
                )
                if result is not None:
                    break
            except Exception as exc:
                logger.debug(
                    "gateway.initialize_protocol_rejected",
                    server_id=self.server_id,
                    protocol_version=protocol_version,
                    error=str(exc),
                )
        if result is None:
            return False
        if isinstance(result, dict):
            reported_protocol = result.get("protocolVersion")
            if isinstance(reported_protocol, str):
                self.protocol_version = reported_protocol[:32]
            raw_capabilities = result.get("capabilities", {})
            if isinstance(raw_capabilities, dict):
                self.capabilities = {
                    str(name)
                    for name, value in raw_capabilities.items()
                    if value is not None
                }
            server_info = result.get("serverInfo", {})
            if isinstance(server_info, dict) and not self.version:
                reported_version = server_info.get("version")
                if isinstance(reported_version, str):
                    self.version = reported_version[:50]

        # Send initialized notification
        await self._send_notification("notifications/initialized", {})

        # tools/list
        try:
            result = await self._send_request("tools/list", {})
            if result and "tools" in result:
                self.tools = result["tools"]
        except Exception as exc:
            logger.debug(
                "gateway.tools_list_unavailable",
                server_id=self.server_id,
                error=str(exc),
            )
        return True

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """调用工具，返回结果或抛出异常。"""
        return await self._send_request("tools/call", {"name": tool_name, "arguments": arguments})

    @property
    def exit_code(self) -> int | None:
        """Return a completed local process exit code, otherwise None."""
        return self.process.returncode

    @property
    def pid(self) -> int | None:
        return self.process.pid

    def is_running(self) -> bool:
        return self.process.returncode is None and not self._shutdown

    async def health_ping(self) -> None:
        """Local process health is determined by its process state and resource sample."""
        return None

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float = 60.0,
    ) -> Any | None:
        """发送 JSON-RPC 请求，等待 reader 回调。"""
        self._request_id += 1
        req_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = _PendingReq(future=future, sent_at=_time.time())

        try:
            self.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode())
            await self.stdin.drain()
        except (BrokenPipeError, OSError) as e:
            self._pending.pop(req_id, None)
            raise GatewayError(f"写入失败: {e}", server_id=self.server_id) from e

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.CancelledError:
            self._pending.pop(req_id, None)
            profile = negotiate_protocol(self.protocol_version)
            if profile is not None and profile.supports_cancellation:
                with contextlib.suppress(Exception):
                    await self._send_notification(
                        "notifications/cancelled",
                        {
                            "requestId": req_id,
                            "reason": "Cancelled by MCP Hub Gateway client",
                        },
                    )
            raise
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            logger.warning("gateway.timeout", server_id=self.server_id, method=method)
            return None

    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """发送 JSON-RPC 通知（无 id，无响应）。"""
        try:
            msg = {"jsonrpc": "2.0", "method": method, "params": params}
            self.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode())
            await self.stdin.drain()
        except (BrokenPipeError, ConnectionError, OSError) as exc:
            raise GatewayError(
                f"发送通知失败: {exc}",
                server_id=self.server_id,
            ) from exc

    async def close(self) -> None:
        """关闭子进程连接。"""
        self._shutdown = True
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None
        self._fail_pending("MCP Server 连接已关闭")
        if self.process and self.process.returncode is None:
            try:
                self.process.kill()
                await self.process.wait()
            except ProcessLookupError:
                pass


class RemoteMCP:
    """Official MCP SDK client connection for Streamable HTTP and legacy SSE."""

    def __init__(
        self,
        spec: GatewayServerSpec,
        *,
        on_notification: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.server_id = spec.server_id
        self.version = spec.version
        self.transport = spec.transport
        self.protocol_version = ""
        self.url = spec.url
        self.headers = spec.resolved_headers(dict(os.environ))
        self.tools: list[dict[str, Any]] = []
        self.capabilities: set[str] = set()
        self._session: ClientSession | None = None
        self._stack: contextlib.AsyncExitStack | None = None
        self._shutdown = False
        self._on_notification = on_notification

    @staticmethod
    def _dump_result(result: Any) -> dict[str, Any]:
        if hasattr(result, "model_dump"):
            dumped = result.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            )
            if isinstance(dumped, dict):
                return dumped
        if isinstance(result, dict):
            return result
        raise GatewayError("MCP SDK returned an unsupported result type")

    async def _handle_server_message(self, message: Any) -> None:
        """Relay supported SDK notifications without exposing transport details."""
        if isinstance(message, Exception):
            logger.debug(
                "gateway.remote_notification_error",
                server_id=self.server_id,
                error=classify_error(message),
            )
            return
        if self._on_notification is None:
            return
        try:
            payload = self._dump_result(message)
            method = payload.get("method")
            params = payload.get("params", {})
            if isinstance(method, str) and isinstance(params, dict):
                await self._on_notification(method, params)
        except Exception as exc:
            logger.debug(
                "gateway.remote_notification_failed",
                server_id=self.server_id,
                error=type(exc).__name__,
            )

    @staticmethod
    def _pagination(params: dict[str, Any]) -> types.PaginatedRequestParams | None:
        cursor = params.get("cursor")
        return types.PaginatedRequestParams(cursor=cursor) if isinstance(cursor, str) else None

    async def initialize(self) -> bool:
        stack = contextlib.AsyncExitStack()
        try:
            if self.transport == "streamable-http":
                http_client = await stack.enter_async_context(
                    httpx2.AsyncClient(
                        headers=self.headers,
                        follow_redirects=True,
                        timeout=httpx2.Timeout(30.0, read=300.0),
                    )
                )
                read_stream, write_stream = await stack.enter_async_context(
                    streamable_http_client(
                        self.url,
                        http_client=http_client,
                    )
                )
            elif self.transport == "sse":
                read_stream, write_stream = await stack.enter_async_context(
                    sse_client(
                        self.url,
                        headers=self.headers,
                    )
                )
            else:
                raise GatewayError(
                    f"Unsupported remote MCP transport: {self.transport}",
                    server_id=self.server_id,
                )

            session = await stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                    client_info=types.Implementation(
                        name="mcp-hub",
                        version=__version__,
                    ),
                    message_handler=self._handle_server_message,
                )
            )
            result = await asyncio.wait_for(session.initialize(), timeout=60)
            capability_data = result.capabilities.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            )
            self.capabilities = {
                str(name)
                for name, value in capability_data.items()
                if value is not None
            }
            if not self.version:
                self.version = result.server_info.version[:50]
            self.protocol_version = result.protocol_version[:32]

            try:
                tools_result = await asyncio.wait_for(session.list_tools(), timeout=30)
                self.tools = self._dump_result(tools_result).get("tools", [])
            except Exception as exc:
                logger.debug(
                    "gateway.remote_tools_list_unavailable",
                    server_id=self.server_id,
                    error=str(exc),
                )
            self._session = session
            self._stack = stack
            return True
        except Exception as exc:
            logger.warning(
                "gateway.remote_initialize_failed",
                server_id=self.server_id,
                transport=self.transport,
                error=classify_error(exc),
            )
            await stack.aclose()
            return False

    def _require_session(self) -> ClientSession:
        if self._session is None or self._shutdown:
            raise GatewayError("Remote MCP Server is not connected", server_id=self.server_id)
        return self._session

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        session = self._require_session()

        async def _request() -> Any:
            if method == "tools/list":
                return await session.list_tools(params=self._pagination(params))
            if method == "tools/call":
                arguments = params.get("arguments")
                if arguments is not None and not isinstance(arguments, dict):
                    raise GatewayError(
                        "tools/call arguments must be an object",
                        server_id=self.server_id,
                    )
                return await session.call_tool(
                    str(params.get("name", "")),
                    arguments=arguments,
                )
            if method == "resources/list":
                return await session.list_resources(params=self._pagination(params))
            if method == "resources/templates/list":
                return await session.list_resource_templates(
                    params=self._pagination(params)
                )
            if method == "resources/read":
                return await session.read_resource(str(params.get("uri", "")))
            if method == "prompts/list":
                return await session.list_prompts(params=self._pagination(params))
            if method == "prompts/get":
                raw_arguments = params.get("arguments")
                if raw_arguments is not None and not isinstance(raw_arguments, dict):
                    raise GatewayError(
                        "prompts/get arguments must be an object",
                        server_id=self.server_id,
                    )
                arguments = (
                    {str(key): str(value) for key, value in raw_arguments.items()}
                    if isinstance(raw_arguments, dict)
                    else None
                )
                return await session.get_prompt(
                    str(params.get("name", "")),
                    arguments=arguments,
                )
            if method == "ping":
                return await session.send_ping()
            raise GatewayError(
                f"Unsupported MCP request: {method}",
                server_id=self.server_id,
            )

        try:
            return self._dump_result(
                await asyncio.wait_for(_request(), timeout=timeout)
            )
        except asyncio.TimeoutError as exc:
            raise GatewayError(
                f"Remote MCP request timed out: {method}",
                server_id=self.server_id,
            ) from exc

    @property
    def exit_code(self) -> int | None:
        return None

    @property
    def pid(self) -> int | None:
        return None

    def is_running(self) -> bool:
        return self._session is not None and not self._shutdown

    async def health_ping(self) -> None:
        await self._send_request("ping", {}, timeout=10)

    async def close(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._session = None
        stack = self._stack
        self._stack = None
        if stack is not None:
            await stack.aclose()


# ── McpGateway: 聚合网关 ──────────────────────────────────────


class McpGateway:
    """MCP 协议网关 — 聚合所有已安装且已启用的 Server。"""

    def __init__(self) -> None:
        self._servers: dict[str, ManagedMCP | RemoteMCP] = {}
        self._telemetry = TelemetryReporter.from_environment()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._configuration_errors: list[dict[str, str]] = []
        self._server_specs: list[GatewayServerSpec] = []
        self._protocol_state = ProtocolState()
        self._request_tasks: dict[Any, asyncio.Task[None]] = {}
        self._stdout_writer: Any | None = None
        self._stdout_lock = asyncio.Lock()

    @property
    def configuration_errors(self) -> list[dict[str, str]]:
        """Return a copy of non-fatal configuration errors for local diagnostics."""
        return list(self._configuration_errors)

    async def _record_telemetry(
        self,
        event_type: str,
        *,
        server_id: str = "",
        tool_name: str = "",
        status: str = "ok",
        duration_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        input_bytes: int = 0,
        output_bytes: int = 0,
        cpu_percent: float | None = None,
        memory_bytes: int | None = None,
        process_uptime_seconds: int | None = None,
        operation: str = "",
        error_code: str = "",
        server_version: str = "",
        transport: str = "stdio",
    ) -> None:
        """记录最小化遥测，任意故障都不得影响网关协议处理。"""
        if self._telemetry is None:
            return
        try:
            await self._telemetry.record(
                event_type,
                server_id=server_id,
                tool_name=tool_name,
                status=status,
                duration_ms=duration_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
                cpu_percent=cpu_percent,
                memory_bytes=memory_bytes,
                process_uptime_seconds=process_uptime_seconds,
                operation=operation,
                error_code=error_code,
                server_version=server_version,
                transport=transport,
            )
        except Exception as exc:
            logger.debug("gateway.telemetry_record_failed", error=str(exc))

    def _start_telemetry_heartbeat(self) -> None:
        """定期采样子进程资源，采样失败不影响 MCP Server。"""
        if self._telemetry is None or self._heartbeat_task is not None:
            return

        async def _heartbeat() -> None:
            while True:
                try:
                    await asyncio.sleep(60)
                    await self._collect_telemetry_heartbeat()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.debug("gateway.telemetry_heartbeat_failed", error=str(exc))

        self._heartbeat_task = asyncio.create_task(_heartbeat())

    async def _collect_telemetry_heartbeat(self) -> None:
        """Record one Gateway heartbeat and sample every live child process."""
        await self._record_telemetry("heartbeat")
        import psutil

        inventory_changed = False
        for server_id, server in list(self._servers.items()):
            exit_code = server.exit_code
            if exit_code is not None:
                await self._record_telemetry(
                    "server_lifecycle",
                    server_id=server_id,
                    status="error",
                    operation="exited",
                    error_code=f"exit_code_{exit_code}",
                    server_version=server.version,
                    transport=server.transport,
                )
                await self._update_registry_status_safe(server_id, "error")
                self._servers.pop(server_id, None)
                await server.close()
                inventory_changed = True
                continue
            if server.transport != "stdio":
                try:
                    await server.health_ping()
                except Exception as exc:
                    await self._record_telemetry(
                        "server_lifecycle",
                        server_id=server_id,
                        status="error",
                        operation="connection_lost",
                        error_code=classify_error(exc),
                        server_version=server.version,
                        transport=server.transport,
                    )
                    await self._update_registry_status_safe(server_id, "error")
                    self._servers.pop(server_id, None)
                    await server.close()
                    inventory_changed = True
                continue

            pid = server.pid
            if pid is None:
                continue
            try:
                process = psutil.Process(pid)
                await self._record_telemetry(
                    "resource_sample",
                    server_id=server_id,
                    cpu_percent=process.cpu_percent(interval=None),
                    memory_bytes=process.memory_info().rss,
                    process_uptime_seconds=max(
                        0,
                        int(_time.time() - process.create_time()),
                    ),
                    operation="process_sample",
                    server_version=server.version,
                    transport=server.transport,
                )
            except (psutil.Error, OSError):
                continue
        if inventory_changed:
            await self._report_inventory_snapshot()

    def _server_notification_handler(
        self,
        server_id: str,
    ) -> Callable[[str, dict[str, Any]], Awaitable[None]]:
        """Bind one child identity to the Gateway notification relay."""

        async def _handle(method: str, params: dict[str, Any]) -> None:
            await self._relay_server_notification(server_id, method, params)

        return _handle

    async def start_all_managed(self) -> list[str]:
        """启动所有已安装且已启用的 MCP Server 并初始化。

        只启动 user_servers 中 enabled=True 的 Server，
        跳过已禁用的 Server。
        """
        specs = await self._load_server_specs()
        self._server_specs = list(specs)
        started = []

        for spec in specs:
            if not spec.enabled:
                logger.info("gateway.skip_disabled", server_id=spec.server_id)
                continue

            sid = spec.server_id
            started_at = _time.perf_counter()
            try:
                managed: ManagedMCP | RemoteMCP
                if spec.transport == "stdio":
                    proc = await asyncio.create_subprocess_exec(
                        spec.executable,
                        *spec.args,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=spec.process_env(_filter_gateway_env()),
                        cwd=spec.cwd,
                    )
                    if proc.stdin is None or proc.stdout is None:
                        raise GatewayError(
                            "MCP Server stdio 管道创建失败",
                            server_id=sid,
                        )
                    if proc.stderr is not None:
                        asyncio.ensure_future(_drain_stderr(sid, proc.stderr))
                    managed = ManagedMCP(
                        sid,
                        proc,
                        proc.stdin,
                        proc.stdout,
                        version=spec.version,
                        transport=spec.transport,
                        on_notification=self._server_notification_handler(sid),
                    )
                else:
                    managed = RemoteMCP(
                        spec,
                        on_notification=self._server_notification_handler(sid),
                    )
                ok = await managed.initialize()
                startup_duration_ms = int((_time.perf_counter() - started_at) * 1000)
                if ok:
                    self._servers[sid] = managed
                    started.append(sid)
                    await self._update_registry_status_safe(sid, "running")
                    logger.info(
                        "gateway.server_started",
                        server_id=sid,
                        transport=spec.transport,
                        tools=len(managed.tools),
                    )
                    await self._record_telemetry(
                        "server_lifecycle",
                        server_id=sid,
                        duration_ms=startup_duration_ms,
                        operation="started",
                        server_version=spec.version,
                        transport=spec.transport,
                    )
                else:
                    logger.warning("gateway.server_init_failed", server_id=sid)
                    self._configuration_errors.append(
                        {
                            "server_id": sid,
                            "error": "MCP Server initialization failed",
                            "error_code": "initialization_failed",
                        }
                    )
                    await self._record_telemetry(
                        "server_lifecycle",
                        server_id=sid,
                        status="error",
                        duration_ms=startup_duration_ms,
                        operation="initialization_failed",
                        error_code="initialization_failed",
                        server_version=spec.version,
                        transport=spec.transport,
                    )
                    await managed.close()
            except Exception as exc:
                logger.warning("gateway.spawn_failed", server_id=sid, error=str(exc))
                self._configuration_errors.append(
                    {
                        "server_id": sid,
                        "error": str(exc),
                        "error_code": classify_error(exc),
                    }
                )
                await self._record_telemetry(
                    "server_lifecycle",
                    server_id=sid,
                    status="error",
                    duration_ms=int((_time.perf_counter() - started_at) * 1000),
                    operation="spawn_failed",
                    error_code=classify_error(exc),
                    server_version=spec.version,
                    transport=spec.transport,
                )

        await self._report_inventory_snapshot()

        self._start_telemetry_heartbeat()
        return started

    async def _report_inventory_snapshot(self) -> None:
        """Report redacted configuration plus observed runtime capabilities."""
        if self._telemetry is None:
            return
        entries: list[dict[str, Any]] = []
        for spec in self._server_specs:
            entry = spec.inventory_entry()
            managed = self._servers.get(spec.server_id)
            entry.update(
                {
                    "server_version": managed.version if managed else spec.version,
                    "protocol_version": managed.protocol_version if managed else "",
                    "capabilities": sorted(managed.capabilities) if managed else [],
                    "tool_count": len(managed.tools) if managed else 0,
                    "running": managed.is_running() if managed else False,
                }
            )
            entries.append(entry)
        await self._telemetry.report_inventory(
            entries,
            self._configuration_errors,
            source="gateway",
        )

    async def _load_server_specs(self) -> list[GatewayServerSpec]:
        """Load canonical local configuration, with Registry as a legacy fallback."""
        config_path = get_gateway_config_path()
        specs, errors = load_gateway_config(config_path)
        self._configuration_errors.extend(errors)
        if config_path.exists():
            logger.info(
                "gateway.config_loaded",
                path=str(config_path),
                servers=len(specs),
                errors=len(errors),
            )
            return specs

        logger.info("gateway.config_missing_using_registry", path=str(config_path))
        return await self._load_registry_specs()

    async def _load_registry_specs(self) -> list[GatewayServerSpec]:
        """Build structured process specs from legacy local Registry records."""
        enabled_sids: set[str] = set()
        try:
            from sqlalchemy import select

            from mcp_hub.db.database import async_session_factory
            from mcp_hub.db.models import UserServerModel

            async with async_session_factory() as session:
                result = await session.execute(
                    select(UserServerModel.server_id).where(UserServerModel.enabled == True)  # noqa: E712
                )
                for row in result.fetchall():
                    enabled_sids.add(row[0])
        except Exception as e:
            logger.warning("gateway.enabled_query_failed", error=str(e))
            enabled_sids = set()

        registry = Registry()
        installed = await registry.get_installed()
        specs: list[GatewayServerSpec] = []
        for server in installed:
            sid = server["id"]
            status = server.get("status", "")
            if status not in ("running", "stopped"):
                continue
            if enabled_sids and sid not in enabled_sids:
                logger.info("gateway.skip_disabled", server_id=sid)
                continue

            cmd = server.get("install_command", "")
            if not cmd:
                continue
            try:
                command, args = split_legacy_command(cmd)
                from mcp_hub.core.config_manager import ConfigManager

                env = await ConfigManager().list_all_config(sid)
                specs.append(
                    GatewayServerSpec(
                        server_id=sid,
                        command=command,
                        args=args,
                        env=env,
                        version=str(
                            server.get("current_version")
                            or server.get("version")
                            or server.get("latest_version")
                            or ""
                        ),
                    )
                )
            except ValueError as exc:
                logger.warning("gateway.invalid_legacy_command", server_id=sid, error=str(exc))
                self._configuration_errors.append({"server_id": sid, "error": str(exc)})
        return specs

    @staticmethod
    async def _update_registry_status_safe(server_id: str, status: str) -> None:
        """Keep legacy status data fresh without making it a Gateway dependency."""
        try:
            await Registry().update_status(server_id, status)
        except Exception as exc:
            logger.debug(
                "gateway.registry_status_update_failed",
                server_id=server_id,
                status=status,
                error=str(exc),
            )

    async def handle_stdio(self) -> None:
        """处理来自 Agent 的 stdio JSON-RPC 请求（阻塞循环）。"""
        loop = asyncio.get_event_loop()
        self._stdout_writer = sys.stdout.buffer

        try:
            while True:
                line = await loop.run_in_executor(None, sys.stdin.buffer.readline)
                if not line:
                    break

                try:
                    request = json.loads(line.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                if not isinstance(request, dict):
                    continue

                # Notifications never receive a response.
                if "id" not in request:
                    self._handle_notification(request)
                    continue

                req_id = request["id"]
                if not self._is_valid_request_id(req_id):
                    await self._write_protocol_message(
                        self._error(None, -32600, "Invalid request id")
                    )
                    continue
                if req_id in self._request_tasks:
                    await self._write_protocol_message(
                        self._error(req_id, -32600, "Duplicate request id")
                    )
                    continue
                task = asyncio.create_task(self._serve_request(request))
                self._request_tasks[req_id] = task
                task.add_done_callback(partial(self._clear_request_task, req_id))
        except asyncio.CancelledError:
            pending = list(self._request_tasks.values())
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            raise
        finally:
            pending = list(self._request_tasks.values())
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            self._request_tasks.clear()
            self._stdout_writer = None

    @staticmethod
    def _is_valid_request_id(request_id: Any) -> bool:
        """Accept only JSON-RPC scalar request identifiers."""
        return request_id is None or (
            isinstance(request_id, (str, int, float))
            and not isinstance(request_id, bool)
        )

    def _clear_request_task(
        self,
        request_id: Any,
        completed: asyncio.Future[None],
    ) -> None:
        """Forget a completed task without removing a newer duplicate guard."""
        if self._request_tasks.get(request_id) is completed:
            self._request_tasks.pop(request_id, None)

    async def _serve_request(self, request: dict[str, Any]) -> None:
        """Process one client request so a cancellation can interrupt only that request."""
        try:
            response = await self._process_request(request)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            response = self._error(
                request.get("id"),
                -32603,
                f"Gateway request failed: {type(exc).__name__}",
            )
        if response is not None:
            await self._write_protocol_message(response)

    async def _write_protocol_message(self, message: dict[str, Any]) -> None:
        """Serialize protocol output so background requests cannot interleave JSON lines."""
        if self._stdout_writer is None:
            return
        async with self._stdout_lock:
            if self._stdout_writer is None:
                return
            self._stdout_writer.write(
                (json.dumps(message, ensure_ascii=False) + "\n").encode()
            )
            self._stdout_writer.flush()

    def _handle_notification(self, request: dict[str, Any]) -> None:
        """处理 JSON-RPC 通知（无需响应）。"""
        method = request.get("method", "")
        if method == "notifications/initialized":
            return
        if method != "notifications/cancelled":
            return
        params = request.get("params", {})
        if not isinstance(params, dict):
            return
        request_id = params.get("requestId")
        task = self._request_tasks.get(request_id)
        if task is not None and not task.done():
            task.cancel()

    async def _relay_server_notification(
        self,
        _server_id: str,
        method: str,
        _params: dict[str, Any],
    ) -> None:
        """Forward aggregate-safe child notifications after modern negotiation."""
        profile = self._protocol_state.profile
        if profile is None or not profile.supports_list_change_notifications:
            return
        if method not in {
            "notifications/tools/list_changed",
            "notifications/resources/list_changed",
            "notifications/prompts/list_changed",
        }:
            return
        await self._write_protocol_message(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": {},
            }
        )

    async def _process_request(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any] | None:
        """处理 JSON-RPC 请求。"""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})
        if not isinstance(params, dict):
            return self._error(req_id, -32602, "Request params must be an object")

        if method == "initialize":
            requested_protocol = params.get("protocolVersion")
            protocol_version = (
                requested_protocol
                if isinstance(requested_protocol, str) and requested_protocol
                else types.LATEST_PROTOCOL_VERSION
            )
            profile = negotiate_protocol(protocol_version)
            if profile is None:
                return self._error(
                    req_id,
                    -32022,
                    "Unsupported protocol version",
                    data={
                        "supported": list(SUPPORTED_PROTOCOL_VERSIONS),
                        "requested": protocol_version,
                    },
                )
            self._protocol_state = ProtocolState(profile=profile, initialized=True)
            list_changed = profile.supports_list_change_notifications
            return self._respond(
                req_id,
                {
                    "protocolVersion": profile.version,
                    "capabilities": {
                        "tools": {"listChanged": True} if list_changed else {},
                        "resources": {"listChanged": True} if list_changed else {},
                        "prompts": {"listChanged": True} if list_changed else {},
                    },
                    "serverInfo": {"name": "mcp-hub-gateway", "version": __version__},
                },
            )

        if method == "notifications/initialized":
            return None

        if method == "ping":
            return self._respond(req_id, {})

        if method == "tools/list":
            all_tools: list[dict[str, Any]] = []
            for sid, server in self._servers.items():
                if not supports_server_method(server, method):
                    continue
                prefix = sid.replace("@", "").replace("/", "_")
                for tool in server.tools:
                    t = dict(tool)
                    t["name"] = f"{prefix}__{t['name']}"
                    if "description" not in t:
                        t["description"] = ""
                    t["description"] = f"[{sid}] {t.get('description', '')}"
                    all_tools.append(t)
            return self._respond(req_id, {"tools": all_tools})

        if method == "tools/call":
            return await self._route_tool_call(req_id, params)

        if method == "resources/list":
            all_res = []
            for sid, server in self._servers.items():
                if not supports_server_method(server, method):
                    continue
                try:
                    r = await server._send_request("resources/list", {}, timeout=10)
                    if r and "resources" in r:
                        prefix = self._server_prefix(sid)
                        for res in r["resources"]:
                            item = dict(res)
                            item["uri"] = f"{prefix}::{res.get('uri', '')}"
                            item["name"] = f"[{sid}] {res.get('name', res.get('uri', ''))}"
                            all_res.append(item)
                except Exception:
                    pass
            return self._respond(req_id, {"resources": all_res})

        if method == "resources/templates/list":
            templates = []
            for sid, server in self._servers.items():
                if not supports_server_method(server, method):
                    continue
                try:
                    result = await server._send_request(
                        "resources/templates/list",
                        {},
                        timeout=10,
                    )
                    if result and "resourceTemplates" in result:
                        prefix = self._server_prefix(sid)
                        for template in result["resourceTemplates"]:
                            item = dict(template)
                            item["uriTemplate"] = (
                                f"{prefix}::{template.get('uriTemplate', '')}"
                            )
                            item["name"] = (
                                f"[{sid}] "
                                f"{template.get('name', template.get('uriTemplate', ''))}"
                            )
                            templates.append(item)
                except Exception:
                    pass
            return self._respond(req_id, {"resourceTemplates": templates})

        if method == "resources/read":
            return await self._route_prefixed_request(
                req_id,
                method,
                params,
                field="uri",
                separator="::",
            )

        if method == "prompts/list":
            all_prompts = []
            for sid, server in self._servers.items():
                if not supports_server_method(server, method):
                    continue
                try:
                    r = await server._send_request("prompts/list", {}, timeout=10)
                    if r and "prompts" in r:
                        prefix = self._server_prefix(sid)
                        for prompt in r["prompts"]:
                            item = dict(prompt)
                            item["name"] = f"{prefix}__{prompt.get('name', '')}"
                            item["description"] = (
                                f"[{sid}] {prompt.get('description', '')}"
                            )
                            all_prompts.append(item)
                except Exception:
                    pass
            return self._respond(req_id, {"prompts": all_prompts})

        if method == "prompts/get":
            return await self._route_prefixed_request(
                req_id,
                method,
                params,
                field="name",
                separator="__",
            )

        if method.startswith("tasks/"):
            return self._error(
                req_id,
                -32601,
                "MCP task requests are not supported by this Gateway",
            )

        # 未知方法
        return self._error(req_id, -32601, f"Method not found: {method}")

    @staticmethod
    def _server_prefix(server_id: str) -> str:
        return server_id.replace("@", "").replace("/", "_")

    def _find_server_by_prefix(
        self,
        prefix: str,
    ) -> tuple[str, ManagedMCP | RemoteMCP] | None:
        for server_id, server in self._servers.items():
            if self._server_prefix(server_id) == prefix:
                return server_id, server
        return None

    async def _route_prefixed_request(
        self,
        req_id: Any,
        method: str,
        params: dict[str, Any],
        *,
        field: str,
        separator: str,
    ) -> dict[str, Any]:
        """Route a prefixed resource or prompt request and record minimal metrics."""
        external_value = params.get(field, "")
        if not isinstance(external_value, str) or separator not in external_value:
            return self._error(req_id, -32602, f"Invalid {field} format")
        prefix, child_value = external_value.split(separator, 1)
        target = self._find_server_by_prefix(prefix)
        if target is None:
            return self._error(req_id, -32602, f"Server not found: {prefix}")

        server_id, server = target
        if not supports_server_method(server, method):
            return self._error(
                req_id,
                -32601,
                f"{server_id} does not advertise support for {method}",
            )
        child_params = {**params, field: child_value}
        started_at = _time.perf_counter()
        input_tokens = estimate_payload_tokens(child_params)
        input_bytes = estimate_payload_bytes(child_params)
        try:
            result = await server._send_request(method, child_params)
            duration_ms = int((_time.perf_counter() - started_at) * 1000)
            if result is None:
                await self._record_telemetry(
                    "protocol_call",
                    server_id=server_id,
                    status="error",
                    duration_ms=duration_ms,
                    input_tokens=input_tokens,
                    input_bytes=input_bytes,
                    operation=method,
                    error_code="no_response",
                    server_version=server.version,
                    transport=server.transport,
                )
                return self._error(req_id, -32603, f"{server_id}: 无响应")
            await self._record_telemetry(
                "protocol_call",
                server_id=server_id,
                duration_ms=duration_ms,
                input_tokens=input_tokens,
                output_tokens=estimate_payload_tokens(result),
                input_bytes=input_bytes,
                output_bytes=estimate_payload_bytes(result),
                operation=method,
                server_version=server.version,
                transport=server.transport,
            )
            return self._respond(req_id, result)
        except Exception as exc:
            await self._record_telemetry(
                "protocol_call",
                server_id=server_id,
                status="error",
                duration_ms=int((_time.perf_counter() - started_at) * 1000),
                input_tokens=input_tokens,
                input_bytes=input_bytes,
                operation=method,
                error_code=classify_error(exc),
                server_version=server.version,
                transport=server.transport,
            )
            return self._error(req_id, -32603, f"{server_id}: {exc}")

    async def _route_tool_call(
        self,
        req_id: Any,
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """路由 tools/call 到目标 Server 并记录。"""
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        # 解析 server_prefix__tool_name
        parts = name.split("__", 1)
        if len(parts) != 2:
            return self._error(req_id, -32602, f"Invalid tool name format: {name}")

        server_prefix, tool_name = parts

        # 查找目标 Server
        target = None
        for sid, server in self._servers.items():
            if self._server_prefix(sid) == server_prefix:
                target = (sid, server)
                break

        if not target:
            # 尝试直接匹配 server_id
            for sid, server in self._servers.items():
                if sid == name or self._server_prefix(sid) == name:
                    target = (sid, server)
                    break

        if not target:
            return self._error(req_id, -32602, f"Server not found: {server_prefix}")

        server_id, server = target

        if not supports_server_method(server, "tools/call"):
            return self._error(
                req_id,
                -32601,
                f"{server_id} does not advertise support for tools/call",
            )

        # 执行调用 + 计时
        t0 = _time.time()
        input_tokens = estimate_payload_tokens(arguments)
        input_bytes = estimate_payload_bytes(arguments)
        try:
            result = await server.call_tool(tool_name, arguments)
            dur_ms = int((_time.time() - t0) * 1000)
            if result is None:
                await _record_call_safe(
                    server_id,
                    tool_name,
                    dur_ms,
                    "error",
                    token_count=input_tokens,
                )
                await self._record_telemetry(
                    "tool_call",
                    server_id=server_id,
                    tool_name=tool_name,
                    status="error",
                    duration_ms=dur_ms,
                    input_tokens=input_tokens,
                    input_bytes=input_bytes,
                    operation="tools/call",
                    error_code="no_response",
                    server_version=server.version,
                    transport=server.transport,
                )
                return self._error(req_id, -32603, f"{server_id}: 无响应")
            output_tokens = estimate_payload_tokens(result)
            output_bytes = estimate_payload_bytes(result)
            result_is_error = isinstance(result, dict) and result.get("isError") is True
            status = "error" if result_is_error else "ok"
            await _record_call_safe(
                server_id,
                tool_name,
                dur_ms,
                status,
                token_count=input_tokens + output_tokens,
            )
            await self._record_telemetry(
                "tool_call",
                server_id=server_id,
                tool_name=tool_name,
                status=status,
                duration_ms=dur_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
                operation="tools/call",
                error_code="tool_result_error" if result_is_error else "",
                server_version=server.version,
                transport=server.transport,
            )
            return self._respond(req_id, result)
        except Exception as e:
            dur_ms = int((_time.time() - t0) * 1000)
            await _record_call_safe(
                server_id,
                tool_name,
                dur_ms,
                "error",
                token_count=input_tokens,
            )
            await self._record_telemetry(
                "tool_call",
                server_id=server_id,
                tool_name=tool_name,
                status="error",
                duration_ms=dur_ms,
                input_tokens=input_tokens,
                input_bytes=input_bytes,
                operation="tools/call",
                error_code=classify_error(e),
                server_version=server.version,
                transport=server.transport,
            )
            return self._error(req_id, -32603, f"{server_id}: {e}")

    async def shutdown(self) -> None:
        """关闭所有子 Server。"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
        for _sid, server in list(self._servers.items()):
            await self._record_telemetry(
                "server_lifecycle",
                server_id=_sid,
                status="warning",
                operation="stopped",
                server_version=server.version,
                transport=server.transport,
            )
            await server.close()
        self._servers.clear()
        if self._telemetry:
            await self._report_inventory_snapshot()
            await self._telemetry.close()

    @staticmethod
    def _respond(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _error(
        req_id: Any,
        code: int,
        message: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": req_id, "error": error}
