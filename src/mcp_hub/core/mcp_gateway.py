"""MCP 协议网关 — Hub 作为单个 stdio 入口聚合所有子 Server。

工作方式：
  1. Agent（如 Claude Code）通过 stdio 连接 Hub
  2. Hub 维护所有已安装 MCP Server 的子进程连接
  3. Agent 发送 tools/list → Hub 聚合返回所有 Server 的 tools
  4. Agent 发送 tools/call → Hub 路由到对应 Server，返回结果
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from mcp_hub.core.registry import Registry
from mcp_hub.exceptions import GatewayError


class ManagedMCP:
    """管理一个子 MCP Server 的 stdio 连接。"""

    def __init__(self, server_id: str, process, stdin, stdout):
        self.server_id = server_id
        self.process = process
        self.stdin = stdin
        self.stdout = stdout
        self.tools: list[dict] = []
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}

    async def initialize(self) -> bool:
        """初始化子 Server，获取工具列表。"""
        # 发送 initialize 请求
        success = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-hub", "version": "0.1.0"},
        })
        if not success:
            return False

        # 获取 tools/list
        result = await self._send_request("tools/list", {})
        if result and "tools" in result:
            self.tools = result["tools"]
            return True
        return False

    async def _send_request(self, method: str, params: dict) -> Any | None:
        """发送 JSON-RPC 请求并等待响应。"""
        self._request_id += 1
        req_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        try:
            self.stdin.write((json.dumps(request) + "\n").encode())
            await self.stdin.drain()

            # 读取响应（超时 30 秒）
            while True:
                line = await asyncio.wait_for(self.stdout.readline(), timeout=30)
                if not line:
                    return None
                response = json.loads(line.decode())
                if "id" in response and response["id"] == req_id:
                    if "result" in response:
                        return response["result"]
                    elif "error" in response:
                        raise GatewayError(
                            response["error"].get("message", str(response["error"])),
                            server_id=self.server_id,
                            details={"raw_error": response["error"]},
                        )
                    return response

        except asyncio.TimeoutError:
            return None
        except Exception as e:
            future.set_exception(e)
            return None
        finally:
            self._pending.pop(req_id, None)

    async def close(self):
        """关闭子进程连接。"""
        if self.process and self.process.returncode is None:
            self.process.kill()
            await self.process.wait()


class McpGateway:
    """MCP 协议网关 — 聚合所有已安装 Server。"""

    def __init__(self):
        self._servers: dict[str, ManagedMCP] = {}

    async def start_all_managed(self) -> list[str]:
        """启动所有已安装的 MCP Server 并初始化。"""
        registry = Registry()
        installed = await registry.get_installed()
        started = []

        for server in installed:
            if server.get("status") == "running" or server.get("status") == "stopped":
                sid = server["id"]
                cmd = server.get("install_command", "")
                if cmd:
                    try:
                        parts = cmd.split()
                        proc = await asyncio.create_subprocess_exec(
                            parts[0],
                            *parts[1:],
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        mcp = ManagedMCP(sid, proc, proc.stdin, proc.stdout)
                        ok = await mcp.initialize()
                        if ok:
                            self._servers[sid] = mcp
                            started.append(sid)
                            # 更新 DB 状态
                            await registry.update_status(sid, "running")
                    except Exception as e:
                        print(f"  [warn] {sid}: {e}", file=sys.stderr)

        return started

    async def handle_stdio(self):
        """处理来自 Agent 的 stdio JSON-RPC 请求。"""
        stdin = sys.stdin.buffer
        stdout = sys.stdout.buffer

        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, stdin.readline)
            if not line:
                break

            try:
                request = json.loads(line.decode())
            except json.JSONDecodeError:
                continue

            response = await self._process_request(request)
            if response:
                stdout.write((json.dumps(response) + "\n").encode())
                await stdout.drain()

    async def _process_request(self, request: dict) -> dict | None:
        """处理 JSON-RPC 请求。"""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                    },
                    "serverInfo": {
                        "name": "mcp-hub",
                        "version": "0.1.0",
                    },
                },
            }

        elif method == "notifications/initialized":
            return None

        elif method == "tools/list":
            all_tools = []
            for sid, server in self._servers.items():
                prefix = sid.replace("@", "").replace("/", "_")
                for tool in server.tools:
                    prefixed = dict(tool)
                    prefixed["name"] = f"{prefix}__{tool['name']}"
                    prefixed["description"] = f"[{sid}] {tool.get('description', '')}"
                    all_tools.append(prefixed)

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": all_tools},
            }

        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})

            # 从名字解析目标 Server
            # 格式: server-prefix__tool-name
            parts = name.split("__", 1)
            if len(parts) != 2:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Invalid tool name: {name}"},
                }

            server_prefix, tool_name = parts
            # 找到对应的 Server
            target_sid = None
            for sid in self._servers:
                if sid.replace("@", "").replace("/", "_") == server_prefix:
                    target_sid = sid
                    break

            if not target_sid or target_sid not in self._servers:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Server not found: {server_prefix}"},
                }

            server = self._servers[target_sid]
            result = await server._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })
            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": f"{target_sid} 无响应"},
                }

            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        elif method == "resources/list":
            # Aggregate resources from all servers
            all_resources = []
            for sid, server in self._servers.items():
                result = await server._send_request("resources/list", {})
                if result and "resources" in result:
                    prefix = sid.replace("@", "").replace("/", "_")
                    for r in result["resources"]:
                        r["uri"] = f"{prefix}://{r.get('uri', '')}"
                        r["description"] = f"[{sid}] {r.get('description', '')}"
                        all_resources.append(r)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": all_resources}}

        elif method == "prompts/list":
            all_prompts = []
            for sid, server in self._servers.items():
                result = await server._send_request("prompts/list", {})
                if result and "prompts" in result:
                    all_prompts.extend(result["prompts"])
            return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": all_prompts}}

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    async def shutdown(self):
        """关闭所有子 Server。"""
        for sid, server in list(self._servers.items()):
            await server.close()
        self._servers.clear()
