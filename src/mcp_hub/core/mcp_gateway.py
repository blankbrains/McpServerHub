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
from dataclasses import dataclass
from typing import Any

from mcp_hub import __version__
from mcp_hub.core.gateway_config import (
    GatewayServerSpec,
    get_gateway_config_path,
    load_gateway_config,
    split_legacy_command,
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


# 子进程环境变量安全白名单前缀
_GATEWAY_SAFE_ENV_PREFIXES = (
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "LC_",
    "TZ",
    "MCP_HUB_",
    "NODE",
    "NPM",
    "PYTHON",
    "PIP",
    "VIRTUAL_ENV",
    "CONDA_",
    "SHELL",
    "TERM",
    "DISPLAY",
    "XDG_",
    "DBUS_",
    "SSH_",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "APPDATA",
    "PROGRAMFILES",
    "PROGRAMDATA",
    "COMPUTERNAME",
    "HOSTNAME",
    "LOGNAME",
    "PWD",
    "OLDPWD",
    "COLORTERM",
    "EDITOR",
    "VISUAL",
    "PAGER",
)


def _filter_gateway_env() -> dict[str, str]:
    """过滤环境变量，仅保留白名单前缀的变量。"""
    result: dict[str, str] = {}
    for k, v in os.environ.items():
        upper_k = k.upper()
        for prefix in _GATEWAY_SAFE_ENV_PREFIXES:
            if upper_k.startswith(prefix):
                result[k] = v
                break
    return result


async def _drain_stderr(server_id: str, stderr_stream) -> None:
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
    future: asyncio.Future
    sent_at: float


class ManagedMCP:
    """管理一个子 MCP Server 的 stdio 连接。

    使用后台 reader 读取 stdout，按 req_id 分发响应，避免竞态。
    """

    def __init__(
        self,
        server_id: str,
        process,
        stdin,
        stdout,
        *,
        version: str = "",
        transport: str = "stdio",
    ):
        self.server_id = server_id
        self.process = process
        self.stdin = stdin
        self.stdout = stdout
        self.version = version
        self.transport = transport
        self.tools: list[dict] = []
        self._request_id = 0
        self._pending: dict[int, _PendingReq] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._shutdown = False

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
                # 通知（无 id）直接忽略
                if "id" not in msg:
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
        # initialize
        try:
            result = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-hub", "version": __version__},
                },
            )
            if result is None:
                return False
        except Exception:
            return False

        # Send initialized notification
        await self._send_notification("notifications/initialized", {})

        # tools/list
        try:
            result = await self._send_request("tools/list", {})
            if result and "tools" in result:
                self.tools = result["tools"]
                return True
        except Exception:
            pass
        return False

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """调用工具，返回结果或抛出异常。"""
        return await self._send_request("tools/call", {"name": tool_name, "arguments": arguments})

    async def _send_request(self, method: str, params: dict, timeout: float = 60.0) -> Any | None:
        """发送 JSON-RPC 请求，等待 reader 回调。"""
        self._request_id += 1
        req_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = _PendingReq(future=future, sent_at=_time.time())

        try:
            self.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode())
            await self.stdin.drain()
        except (BrokenPipeError, OSError) as e:
            self._pending.pop(req_id, None)
            raise GatewayError(f"写入失败: {e}", server_id=self.server_id) from e

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            logger.warning("gateway.timeout", server_id=self.server_id, method=method)
            return None

    async def _send_notification(self, method: str, params: dict) -> None:
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


# ── McpGateway: 聚合网关 ──────────────────────────────────────


class McpGateway:
    """MCP 协议网关 — 聚合所有已安装且已启用的 Server。"""

    def __init__(self):
        self._servers: dict[str, ManagedMCP] = {}
        self._telemetry = TelemetryReporter.from_environment()
        self._heartbeat_task: asyncio.Task | None = None
        self._configuration_errors: list[dict[str, str]] = []

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
                    await self._record_telemetry("heartbeat")
                    import psutil

                    for server_id, server in list(self._servers.items()):
                        pid = server.process.pid if server.process else None
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
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.debug("gateway.telemetry_heartbeat_failed", error=str(exc))

        self._heartbeat_task = asyncio.create_task(_heartbeat())

    async def start_all_managed(self) -> list[str]:
        """启动所有已安装且已启用的 MCP Server 并初始化。

        只启动 user_servers 中 enabled=True 的 Server，
        跳过已禁用的 Server。
        """
        specs = await self._load_server_specs()
        started = []

        for spec in specs:
            if not spec.enabled:
                logger.info("gateway.skip_disabled", server_id=spec.server_id)
                continue

            sid = spec.server_id
            started_at = _time.perf_counter()
            try:
                proc = await asyncio.create_subprocess_exec(
                    spec.executable,
                    *spec.args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=spec.process_env(_filter_gateway_env()),
                    cwd=spec.cwd,
                )
                asyncio.ensure_future(_drain_stderr(sid, proc.stderr))
                mcp = ManagedMCP(
                    sid,
                    proc,
                    proc.stdin,
                    proc.stdout,
                    version=spec.version,
                    transport=spec.transport,
                )
                ok = await mcp.initialize()
                startup_duration_ms = int((_time.perf_counter() - started_at) * 1000)
                if ok:
                    self._servers[sid] = mcp
                    started.append(sid)
                    await self._update_registry_status_safe(sid, "running")
                    logger.info("gateway.server_started", server_id=sid, tools=len(mcp.tools))
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
                    await mcp.close()
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

        if self._telemetry is not None:
            await self._telemetry.report_inventory(
                [spec.inventory_entry() for spec in specs],
                self._configuration_errors,
            )

        self._start_telemetry_heartbeat()
        return started

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

    async def handle_stdio(self):
        """处理来自 Agent 的 stdio JSON-RPC 请求（阻塞循环）。"""
        loop = asyncio.get_event_loop()
        stdout_w = sys.stdout.buffer

        while True:
            line = await loop.run_in_executor(None, sys.stdin.buffer.readline)
            if not line:
                break

            try:
                request = json.loads(line.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # 通知（无需响应）
            if "id" not in request:
                self._handle_notification(request)
                continue

            response = await self._process_request(request)
            if response is not None:
                stdout_w.write((json.dumps(response, ensure_ascii=False) + "\n").encode())
                stdout_w.flush()

    def _handle_notification(self, request: dict) -> None:
        """处理 JSON-RPC 通知（无需响应）。"""
        method = request.get("method", "")
        if method == "notifications/initialized":
            pass  # Agent 初始化完成通知

    async def _process_request(self, request: dict) -> dict | None:
        """处理 JSON-RPC 请求。"""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._respond(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                    "serverInfo": {"name": "mcp-hub-gateway", "version": "0.2.0"},
                },
            )

        if method == "notifications/initialized":
            return None

        if method == "ping":
            return self._respond(req_id, {})

        if method == "tools/list":
            all_tools: list[dict] = []
            for sid, server in self._servers.items():
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

        # 未知方法
        return self._error(req_id, -32601, f"Method not found: {method}")

    @staticmethod
    def _server_prefix(server_id: str) -> str:
        return server_id.replace("@", "").replace("/", "_")

    def _find_server_by_prefix(self, prefix: str) -> tuple[str, ManagedMCP] | None:
        for server_id, server in self._servers.items():
            if self._server_prefix(server_id) == prefix:
                return server_id, server
        return None

    async def _route_prefixed_request(
        self,
        req_id: Any,
        method: str,
        params: dict,
        *,
        field: str,
        separator: str,
    ) -> dict:
        """Route a prefixed resource or prompt request and record minimal metrics."""
        external_value = params.get(field, "")
        if not isinstance(external_value, str) or separator not in external_value:
            return self._error(req_id, -32602, f"Invalid {field} format")
        prefix, child_value = external_value.split(separator, 1)
        target = self._find_server_by_prefix(prefix)
        if target is None:
            return self._error(req_id, -32602, f"Server not found: {prefix}")

        server_id, server = target
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

    async def _route_tool_call(self, req_id, params: dict) -> dict | None:
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
            await _record_call_safe(
                server_id,
                tool_name,
                dur_ms,
                "ok",
                token_count=input_tokens + output_tokens,
            )
            await self._record_telemetry(
                "tool_call",
                server_id=server_id,
                tool_name=tool_name,
                duration_ms=dur_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
                operation="tools/call",
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

    async def shutdown(self):
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
            await self._telemetry.close()

    @staticmethod
    def _respond(req_id, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _error(req_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
