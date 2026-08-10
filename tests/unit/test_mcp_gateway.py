"""MCP Gateway configuration and telemetry regression tests."""

from __future__ import annotations

import asyncio
import io
import json
import sys
import textwrap
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from click.testing import CliRunner

from mcp_hub.cli.daemon import serve
from mcp_hub.core import mcp_gateway
from mcp_hub.core.gateway_config import GatewayServerSpec
from mcp_hub.core.mcp_gateway import ManagedMCP, McpGateway, RemoteMCP
from mcp_hub.exceptions import GatewayError


def _process() -> MagicMock:
    process = MagicMock()
    process.pid = 1234
    process.returncode = None
    process.stdin = MagicMock()
    process.stdout = MagicMock()
    process.stderr = MagicMock()
    process.stderr.readline = AsyncMock(return_value=b"")
    process.wait = AsyncMock(return_value=0)
    process.kill = MagicMock()
    return process


async def test_managed_mcp_initializes_and_calls_real_stdio_process() -> None:
    server_code = textwrap.dedent(
        """
        import json
        import sys

        for line in sys.stdin:
            request = json.loads(line)
            request_id = request.get("id")
            method = request.get("method")
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "test-server", "version": "1.0.0"},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo text",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                }
            elif method == "tools/call":
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": request["params"]["arguments"]["text"],
                        }
                    ]
                }
            else:
                result = {}
            if request_id is not None:
                print(
                    json.dumps(
                        {"jsonrpc": "2.0", "id": request_id, "result": result}
                    ),
                    flush=True,
                )
        """
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "-c",
        server_code,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    managed = ManagedMCP(
        "test-server",
        process,
        process.stdin,
        process.stdout,
    )

    try:
        assert await managed.initialize() is True
        assert [tool["name"] for tool in managed.tools] == ["echo"]
        result = await managed.call_tool("echo", {"text": "roundtrip-ok"})
        assert result["content"][0]["text"] == "roundtrip-ok"
    finally:
        await managed.close()


async def test_gateway_spawns_structured_command_with_only_explicit_server_env(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PATH", "base-path")
    monkeypatch.setenv("HOME", "/home/test-user")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-be-forwarded")
    monkeypatch.delenv("MCP_HUB_REPORT_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_TELEMETRY_TOKEN", raising=False)
    gateway = McpGateway()
    monkeypatch.setenv("MCP_HUB_REPORT_URL", "https://hub.example.test")
    monkeypatch.setenv("MCP_HUB_TELEMETRY_TOKEN", "synthetic-device-token")
    monkeypatch.setenv("MCP_HUB_SECRET", "synthetic-hub-secret")
    monkeypatch.setenv("MCP_HUB_GITHUB_CLIENT_SECRET", "synthetic-oauth-secret")
    monkeypatch.setenv("NPM_TOKEN", "synthetic-npm-token")
    monkeypatch.setenv("PIP_INDEX_URL", "https://user:password@example.test/simple")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/synthetic-ssh-agent")
    spec = GatewayServerSpec(
        server_id="weather",
        command="C:\\Program Files\\nodejs\\npx.cmd",
        args=("-y", "@example/weather", "--label", "New York"),
        env={"WEATHER_API_KEY": "authorized"},
        cwd="D:\\MCP Servers\\weather",
    )
    monkeypatch.setattr(gateway, "_load_server_specs", AsyncMock(return_value=[spec]))
    monkeypatch.setattr(
        gateway,
        "_update_registry_status_safe",
        AsyncMock(),
    )
    create_process = AsyncMock(return_value=_process())
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)
    monkeypatch.setattr(ManagedMCP, "initialize", AsyncMock(return_value=True))

    started = await gateway.start_all_managed()

    assert started == ["weather"]
    positional = create_process.await_args.args
    keyword = create_process.await_args.kwargs
    assert positional == (
        "C:\\Program Files\\nodejs\\npx.cmd",
        "-y",
        "@example/weather",
        "--label",
        "New York",
    )
    assert keyword["cwd"] == "D:\\MCP Servers\\weather"
    assert keyword["env"]["WEATHER_API_KEY"] == "authorized"
    assert keyword["env"]["PATH"] == "base-path"
    assert keyword["env"]["HOME"] == "/home/test-user"
    assert "UNRELATED_SECRET" not in keyword["env"]
    assert "MCP_HUB_REPORT_URL" not in keyword["env"]
    assert "MCP_HUB_TELEMETRY_TOKEN" not in keyword["env"]
    assert "MCP_HUB_SECRET" not in keyword["env"]
    assert "MCP_HUB_GITHUB_CLIENT_SECRET" not in keyword["env"]
    assert "NPM_TOKEN" not in keyword["env"]
    assert "PIP_INDEX_URL" not in keyword["env"]
    assert "SSH_AUTH_SOCK" not in keyword["env"]
    await gateway.shutdown()


def test_server_environment_can_explicitly_authorize_filtered_variable_names(
    monkeypatch,
) -> None:
    monkeypatch.setenv("NPM_TOKEN", "host-token")
    monkeypatch.setenv("MCP_HUB_TELEMETRY_TOKEN", "host-device-token")
    spec = GatewayServerSpec(
        server_id="publisher",
        command="npx",
        env={
            "NPM_TOKEN": "server-scoped-token",
            "MCP_HUB_CUSTOM_SETTING": "server-scoped-setting",
        },
    )

    child_env = spec.process_env(mcp_gateway._filter_gateway_env())

    assert child_env["NPM_TOKEN"] == "server-scoped-token"
    assert child_env["MCP_HUB_CUSTOM_SETTING"] == "server-scoped-setting"
    assert "MCP_HUB_TELEMETRY_TOKEN" not in child_env


async def test_tool_call_records_extended_metrics_without_payloads(monkeypatch) -> None:
    monkeypatch.delenv("MCP_HUB_REPORT_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_TELEMETRY_TOKEN", raising=False)
    gateway = McpGateway()
    reporter = MagicMock()
    reporter.record = AsyncMock()
    gateway._telemetry = reporter
    server = MagicMock()
    server.version = "1.2.3"
    server.transport = "stdio"
    server.call_tool = AsyncMock(
        return_value={"content": [{"type": "text", "text": "sunny"}]}
    )
    gateway._servers["weather"] = server
    monkeypatch.setattr(
        "mcp_hub.core.mcp_gateway._record_call_safe",
        AsyncMock(),
    )

    response = await gateway._route_tool_call(
        7,
        {
            "name": "weather__forecast",
            "arguments": {"city": "Qingdao"},
        },
    )

    assert response is not None and response["id"] == 7
    metrics = reporter.record.await_args.kwargs
    assert metrics["operation"] == "tools/call"
    assert metrics["server_version"] == "1.2.3"
    assert metrics["input_bytes"] > 0
    assert metrics["output_bytes"] > 0
    assert "arguments" not in metrics
    assert "result" not in metrics


async def test_tool_result_is_error_is_recorded_as_failed_call(monkeypatch) -> None:
    monkeypatch.delenv("MCP_HUB_REPORT_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_TELEMETRY_TOKEN", raising=False)
    gateway = McpGateway()
    reporter = MagicMock()
    reporter.record = AsyncMock()
    gateway._telemetry = reporter
    server = MagicMock()
    server.version = "1.2.3"
    server.transport = "stdio"
    server.call_tool = AsyncMock(
        return_value={
            "content": [{"type": "text", "text": "tool rejected the request"}],
            "isError": True,
        }
    )
    gateway._servers["weather"] = server
    record_call = AsyncMock()
    monkeypatch.setattr("mcp_hub.core.mcp_gateway._record_call_safe", record_call)

    response = await gateway._route_tool_call(
        8,
        {
            "name": "weather__forecast",
            "arguments": {"city": "Qingdao"},
        },
    )

    assert response is not None
    assert response["result"]["isError"] is True
    assert record_call.await_args.args[3] == "error"
    metrics = reporter.record.await_args.kwargs
    assert metrics["status"] == "error"
    assert metrics["error_code"] == "tool_result_error"


async def test_resource_only_server_initializes_without_tools() -> None:
    managed = ManagedMCP(
        "resource-server",
        _process(),
        MagicMock(),
        MagicMock(),
    )
    managed.start_reader = AsyncMock()
    managed._send_notification = AsyncMock()
    managed._send_request = AsyncMock(
        side_effect=[
            {
                "capabilities": {"resources": {}},
                "protocolVersion": "2025-06-18",
                "serverInfo": {"name": "resource-server", "version": "3.2.1"},
            },
            GatewayError("tools/list unsupported", server_id="resource-server"),
        ]
    )

    initialized = await managed.initialize()

    assert initialized is True
    assert managed.capabilities == {"resources"}
    assert managed.protocol_version == "2025-06-18"
    assert managed.version == "3.2.1"
    assert managed.tools == []


async def test_heartbeat_records_child_exit_and_refreshes_inventory(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MCP_HUB_REPORT_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_TELEMETRY_TOKEN", raising=False)
    gateway = McpGateway()
    reporter = MagicMock()
    reporter.record = AsyncMock()
    reporter.report_inventory = AsyncMock()
    gateway._telemetry = reporter
    gateway._server_specs = [
        GatewayServerSpec(server_id="weather", command="npx")
    ]
    server = MagicMock()
    server.version = "4.0.0"
    server.transport = "stdio"
    server.exit_code = 9
    server.close = AsyncMock()
    gateway._servers["weather"] = server
    gateway._update_registry_status_safe = AsyncMock()

    await gateway._collect_telemetry_heartbeat()

    lifecycle = reporter.record.await_args_list[1].kwargs
    assert lifecycle["operation"] == "exited"
    assert lifecycle["error_code"] == "exit_code_9"
    assert "weather" not in gateway._servers
    server.close.assert_awaited_once()
    reporter.report_inventory.assert_awaited_once()
    inventory = reporter.report_inventory.await_args.args[0]
    assert inventory[0]["running"] is False


async def test_gateway_starts_remote_server_without_spawning_local_process(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MCP_HUB_REPORT_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_TELEMETRY_TOKEN", raising=False)
    gateway = McpGateway()
    spec = GatewayServerSpec(
        server_id="remote",
        transport="streamable-http",
        url="https://example.test/mcp",
        headers={"Authorization": "Bearer local-only"},
    )
    monkeypatch.setattr(gateway, "_load_server_specs", AsyncMock(return_value=[spec]))
    monkeypatch.setattr(gateway, "_update_registry_status_safe", AsyncMock())
    initialize = AsyncMock(return_value=True)
    monkeypatch.setattr(RemoteMCP, "initialize", initialize)
    create_process = AsyncMock()
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)

    started = await gateway.start_all_managed()

    assert started == ["remote"]
    create_process.assert_not_awaited()
    initialize.assert_awaited_once()
    assert gateway._servers["remote"].transport == "streamable-http"
    await gateway.shutdown()


async def test_remote_mcp_routes_sdk_calls_and_serializes_aliases() -> None:
    class Result:
        def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
            return {
                "content": [{"type": "text", "text": "remote-ok"}],
                "isError": False,
            }

    remote = RemoteMCP(
        GatewayServerSpec(
            server_id="remote",
            transport="streamable-http",
            url="https://example.test/mcp",
        )
    )
    session = MagicMock()
    session.call_tool = AsyncMock(return_value=Result())
    remote._session = session

    result = await remote.call_tool("lookup", {"query": "MCP"})

    assert result["isError"] is False
    assert result["content"][0]["text"] == "remote-ok"
    session.call_tool.assert_awaited_once_with(
        "lookup",
        arguments={"query": "MCP"},
    )


async def test_remote_mcp_initializes_streamable_http_with_local_headers(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeHttpClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["http_client_kwargs"] = kwargs

        async def __aenter__(self) -> FakeHttpClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            captured["http_client_closed"] = True

    @asynccontextmanager
    async def fake_streamable_http_client(
        url: str,
        *,
        http_client: Any,
    ):
        captured["url"] = url
        captured["http_client"] = http_client
        yield object(), object()
        captured["transport_closed"] = True

    class Capabilities:
        def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
            return {"tools": {}, "resources": {}}

    class ToolsResult:
        def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
            return {
                "tools": [
                    {
                        "name": "lookup",
                        "description": "Lookup data",
                        "inputSchema": {"type": "object"},
                    }
                ]
            }

    class FakeSession:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeSession:
            return self

        async def __aexit__(self, *_args: object) -> None:
            captured["session_closed"] = True

        async def initialize(self) -> SimpleNamespace:
            return SimpleNamespace(
                capabilities=Capabilities(),
                server_info=SimpleNamespace(version="2.4.0"),
                protocol_version="2026-07-28",
            )

        async def list_tools(self) -> ToolsResult:
            return ToolsResult()

    monkeypatch.setattr(mcp_gateway.httpx2, "AsyncClient", FakeHttpClient)
    monkeypatch.setattr(
        mcp_gateway,
        "streamable_http_client",
        fake_streamable_http_client,
    )
    monkeypatch.setattr(mcp_gateway, "ClientSession", FakeSession)

    remote = RemoteMCP(
        GatewayServerSpec(
            server_id="remote",
            transport="streamable-http",
            url="https://example.test/mcp",
            headers={"Authorization": "Bearer local-only"},
        )
    )

    assert await remote.initialize() is True
    assert remote.version == "2.4.0"
    assert remote.protocol_version == "2026-07-28"
    assert remote.capabilities == {"resources", "tools"}
    assert remote.tools[0]["name"] == "lookup"
    assert captured["url"] == "https://example.test/mcp"
    assert captured["http_client_kwargs"]["headers"] == {
        "Authorization": "Bearer local-only"
    }

    await remote.close()

    assert captured["session_closed"] is True
    assert captured["transport_closed"] is True
    assert captured["http_client_closed"] is True


async def test_gateway_routes_resource_and_prompt_requests_to_original_values(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MCP_HUB_REPORT_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_TELEMETRY_TOKEN", raising=False)
    gateway = McpGateway()
    reporter = MagicMock()
    reporter.record = AsyncMock()
    gateway._telemetry = reporter
    server = MagicMock()
    server.version = "2.0.0"
    server.transport = "stdio"
    server._send_request = AsyncMock(return_value={"content": [{"text": "ok"}]})
    gateway._servers["@example/content"] = server

    resource_response = await gateway._process_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": "example_content::file:///docs/readme.md"},
        }
    )
    prompt_response = await gateway._process_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "prompts/get",
            "params": {"name": "example_content__review", "arguments": {"tone": "brief"}},
        }
    )

    assert resource_response is not None and resource_response["id"] == 1
    assert prompt_response is not None and prompt_response["id"] == 2
    assert server._send_request.await_args_list[0].args == (
        "resources/read",
        {"uri": "file:///docs/readme.md"},
    )
    assert server._send_request.await_args_list[1].args == (
        "prompts/get",
        {"name": "review", "arguments": {"tone": "brief"}},
    )
    assert reporter.record.await_args_list[0].kwargs["operation"] == "resources/read"
    assert reporter.record.await_args_list[1].kwargs["operation"] == "prompts/get"


async def test_stdio_gateway_flushes_multiple_protocol_responses(monkeypatch) -> None:
    monkeypatch.delenv("MCP_HUB_REPORT_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_TELEMETRY_TOKEN", raising=False)
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}},
    ]
    input_buffer = io.BytesIO(
        b"".join(
            (json.dumps(request) + "\n").encode("utf-8")
            for request in requests
        )
    )
    output_buffer = io.BytesIO()
    monkeypatch.setattr(
        mcp_gateway.sys,
        "stdin",
        SimpleNamespace(buffer=input_buffer),
    )
    monkeypatch.setattr(
        mcp_gateway.sys,
        "stdout",
        SimpleNamespace(buffer=output_buffer),
    )

    await McpGateway().handle_stdio()

    responses = [
        json.loads(line)
        for line in output_buffer.getvalue().decode("utf-8").splitlines()
    ]
    assert [response["id"] for response in responses] == [1, 2]
    assert responses[0]["result"]["serverInfo"]["name"] == "mcp-hub-gateway"
    assert responses[1]["result"] == {}


def test_serve_keeps_diagnostics_out_of_protocol_stdout(monkeypatch) -> None:
    class FakeGateway:
        async def start_all_managed(self) -> list[str]:
            mcp_gateway.logger.info("gateway.test_diagnostic")
            return []

        async def handle_stdio(self) -> None:
            return None

        async def shutdown(self) -> None:
            return None

    monkeypatch.setattr(mcp_gateway, "McpGateway", FakeGateway)

    result = CliRunner().invoke(serve)

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "MCP Hub Gateway" in result.stderr
    assert "gateway.test_diagnostic" in result.stderr
