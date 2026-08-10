"""MCP Gateway configuration and telemetry regression tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from mcp_hub.core.gateway_config import GatewayServerSpec
from mcp_hub.core.mcp_gateway import ManagedMCP, McpGateway


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


async def test_gateway_spawns_structured_command_with_only_explicit_server_env(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PATH", "base-path")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-be-forwarded")
    monkeypatch.delenv("MCP_HUB_REPORT_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_TELEMETRY_TOKEN", raising=False)
    gateway = McpGateway()
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
    assert "UNRELATED_SECRET" not in keyword["env"]
    await gateway.shutdown()


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
