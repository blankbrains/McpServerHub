"""End-to-end Agent verification and guided repair regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
from click.testing import CliRunner

from mcp_hub.cli.agent import agent
from mcp_hub.core import agent_verify
from mcp_hub.core.gateway_config import GatewayServerSpec, write_gateway_config
from mcp_hub.core.telemetry import TelemetrySpool


def _gateway_entry(
    state_dir: Path,
    *,
    token: str = "mcpht_test-token",
) -> dict[str, object]:
    return {
        "command": "mcp-hub",
        "args": ["serve"],
        "env": {
            "MCP_HUB_REPORT_URL": "https://hub.example.test",
            "MCP_HUB_TELEMETRY_TOKEN": token,
            "MCP_HUB_AGENT_TYPE": "cursor",
            "MCP_HUB_AGENT_STATE_DIR": str(state_dir),
            "MCP_HUB_GATEWAY_CONFIG": str(state_dir / "gateway.json"),
        },
    }


def _write_ready_local_config(
    tmp_path: Path,
    *,
    servers: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    write_gateway_config(
        [
            GatewayServerSpec(
                server_id="remote",
                transport="streamable-http",
                url="https://example.test/mcp",
            )
        ],
        state_dir / "gateway.json",
    )
    source = tmp_path / "mcp.json"
    source.write_text(
        json.dumps(
            {
                "mcpServers": servers
                if servers is not None
                else {"mcp-hub": _gateway_entry(state_dir)}
            }
        ),
        encoding="utf-8",
    )
    return source, state_dir


def _online_response(
    *,
    state: str = "connected",
    queue_depth: int = 0,
) -> list[tuple[int, dict[str, object]]]:
    return [
        (
            200,
            {
                "success": True,
                "status": "healthy",
                "version": "0.2.0",
            },
        ),
        (
            200,
            {
                "success": True,
                "data": {
                    "valid": True,
                    "revoked": False,
                    "online": True,
                    "state": state,
                    "label": "已完成接入",
                    "reason": "Gateway 在线，并且已经收到真实 MCP 工具调用。",
                    "gateway_version": "0.2.0",
                    "gateway_last_seen_at": "2026-08-11T08:00:00",
                    "first_call_at": "2026-08-11T08:01:00",
                    "queue_depth": queue_depth,
                    "server_count": 1,
                    "configuration_error_count": 0,
                },
            },
        ),
    ]


def _mock_online(
    monkeypatch,
    responses: list[tuple[int, dict[str, object]]] | None = None,
) -> AsyncMock:
    if responses is None:
        health, token = _online_response()

        async def _request(_method: str, url: str, **_kwargs: object):
            return token if url.endswith("/telemetry/token/validate") else health

        request = AsyncMock(side_effect=_request)
    else:
        request = AsyncMock(side_effect=responses)
    monkeypatch.setattr(agent_verify, "_request_json", request)
    monkeypatch.setattr(agent_verify.shutil, "which", lambda _command: "mcp-hub")
    return request


def _invoke_verify(
    source: Path,
    state_dir: Path,
    *extra: str,
) -> object:
    return CliRunner().invoke(
        agent,
        [
            "verify",
            "--agent",
            "cursor",
            "--source-config",
            str(source),
            "--state-dir",
            str(state_dir),
            *extra,
        ],
    )


def test_agent_verify_json_reports_complete_connection(monkeypatch, tmp_path) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    _mock_online(monkeypatch)

    result = _invoke_verify(source, state_dir, "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ready"] is True
    assert payload["agent_type"] == "cursor"
    assert payload["summary"]["errors"] == 0
    assert payload["summary"]["warnings"] == 0
    assert payload["remote"]["state"] == "connected"
    assert "mcpht_test-token" not in result.output


def test_agent_verify_human_output_is_actionable(monkeypatch, tmp_path) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    _mock_online(monkeypatch)

    result = _invoke_verify(source, state_dir)

    assert result.exit_code == 0, result.output
    assert "Agent 配置" in result.output
    assert "Gateway 在线" in result.output
    assert "首次工具调用" in result.output
    assert "接入验证完成" in result.output


def test_agent_verify_distinguishes_network_failure_from_invalid_token(
    monkeypatch,
    tmp_path,
) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    monkeypatch.setattr(agent_verify.shutil, "which", lambda _command: "mcp-hub")
    monkeypatch.setattr(
        agent_verify,
        "_request_json",
        AsyncMock(side_effect=httpx.ConnectError("network unavailable")),
    )

    result = _invoke_verify(source, state_dir, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    codes = {check["code"] for check in payload["checks"]}
    assert "hub_unreachable" in codes
    assert "telemetry_token_invalid" not in codes


def test_agent_verify_reports_missing_gateway_entry_without_modifying_config(
    monkeypatch,
    tmp_path,
) -> None:
    source, state_dir = _write_ready_local_config(
        tmp_path,
        servers={
            "weather": {
                "command": "uvx",
                "args": ["weather"],
            }
        },
    )
    original = source.read_bytes()
    _mock_online(monkeypatch)

    result = _invoke_verify(
        source,
        state_dir,
        "--hub-url",
        "https://hub.example.test",
        "--telemetry-token",
        "mcpht_test-token",
        "--json",
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "gateway_entry_missing" in {
        check["code"] for check in payload["checks"]
    }
    assert source.read_bytes() == original
    assert not list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))


def test_agent_verify_fix_requires_confirmation_in_json_mode(
    monkeypatch,
    tmp_path,
) -> None:
    state_dir = tmp_path / "state"
    entry = _gateway_entry(state_dir)
    source, state_dir = _write_ready_local_config(
        tmp_path,
        servers={
            "mcp-hub": entry,
            "mcp-hub-gateway": entry,
        },
    )
    original = source.read_bytes()
    _mock_online(monkeypatch)

    result = _invoke_verify(source, state_dir, "--json", "--fix")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["confirmation_required"] is True
    assert payload["planned_fixes"][0]["code"] == "normalize_gateway_entry"
    assert source.read_bytes() == original


def test_agent_verify_fix_backs_up_and_removes_equivalent_duplicate(
    monkeypatch,
    tmp_path,
) -> None:
    state_dir = tmp_path / "state"
    entry = _gateway_entry(state_dir)
    source, state_dir = _write_ready_local_config(
        tmp_path,
        servers={
            "mcp-hub": entry,
            "mcp-hub-gateway": entry,
        },
    )
    _mock_online(monkeypatch)

    result = _invoke_verify(source, state_dir, "--json", "--fix", "--yes")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ready"] is True
    assert payload["applied_fixes"][0]["code"] == "normalize_gateway_entry"
    migrated = json.loads(source.read_text(encoding="utf-8"))
    assert set(migrated["mcpServers"]) == {"mcp-hub"}
    backups = list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))
    assert len(backups) == 1
    original = json.loads(backups[0].read_text(encoding="utf-8"))
    assert set(original["mcpServers"]) == {"mcp-hub", "mcp-hub-gateway"}


def test_agent_verify_reports_invalid_token_from_server(monkeypatch, tmp_path) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    _mock_online(
        monkeypatch,
        [
            (200, {"success": True, "status": "healthy", "version": "0.2.0"}),
            (401, {"detail": "设备遥测令牌无效"}),
        ],
    )

    result = _invoke_verify(source, state_dir, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "telemetry_token_invalid" in {
        check["code"] for check in payload["checks"]
    }


def test_agent_verify_reports_waiting_restart_and_first_call_missing(
    monkeypatch,
    tmp_path,
) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    _mock_online(
        monkeypatch,
        [
            (200, {"success": True, "status": "healthy", "version": "0.2.0"}),
            (
                200,
                {
                    "success": True,
                    "data": {
                        "valid": True,
                        "revoked": False,
                        "online": False,
                        "state": "waiting_restart",
                        "reason": "本地配置已经迁移，但尚未收到 Gateway 会话。",
                        "gateway_version": "0.2.0",
                        "queue_depth": 0,
                        "server_count": 1,
                        "configuration_error_count": 0,
                    },
                },
            ),
        ],
    )

    result = _invoke_verify(source, state_dir, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    codes = {check["code"] for check in payload["checks"]}
    assert "gateway_not_seen" in codes
    assert "first_call_missing" in codes


def test_agent_verify_reports_revoked_device(monkeypatch, tmp_path) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    _mock_online(
        monkeypatch,
        [
            (200, {"success": True, "status": "healthy", "version": "0.2.0"}),
            (
                200,
                {
                    "success": True,
                    "data": {
                        "valid": False,
                        "revoked": True,
                        "online": False,
                        "state": "revoked",
                        "label": "已撤销",
                    },
                },
            ),
        ],
    )

    result = _invoke_verify(source, state_dir, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "device_revoked" in {
        check["code"] for check in payload["checks"]
    }


def test_agent_verify_reports_remote_queue_backlog(monkeypatch, tmp_path) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    _mock_online(monkeypatch, _online_response(state="data_backlog", queue_depth=6))

    result = _invoke_verify(source, state_dir, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    queue_checks = [
        check for check in payload["checks"] if check["code"] == "queue_backlog"
    ]
    assert queue_checks
    assert queue_checks[0]["fixable"] is False
    assert payload["planned_fixes"] == []
    assert payload["remote"]["queue_depth"] == 6


def test_agent_verify_rejects_malformed_token_validation_payload(
    monkeypatch,
    tmp_path,
) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    _mock_online(
        monkeypatch,
        [
            (200, {"success": True, "status": "healthy", "version": "0.2.0"}),
            (
                200,
                {
                    "success": True,
                    "data": {
                        "valid": True,
                        "revoked": False,
                        "queue_depth": "not-a-number",
                    },
                },
            ),
        ],
    )

    result = _invoke_verify(source, state_dir, "--json")

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    payload = json.loads(result.output)
    assert "token_validation_failed" in {
        check["code"] for check in payload["checks"]
    }


def test_agent_verify_reports_version_incompatibility(monkeypatch, tmp_path) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    responses = _online_response()
    responses[0][1]["version"] = "0.3.0"
    _mock_online(monkeypatch, responses)

    result = _invoke_verify(source, state_dir, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "version_incompatible" in {
        check["code"] for check in payload["checks"]
    }


def test_agent_verify_fix_retries_queue_without_marking_gateway_uploader(
    monkeypatch,
    tmp_path,
) -> None:
    source, state_dir = _write_ready_local_config(tmp_path)
    spool = TelemetrySpool(state_dir)
    try:
        spool.enqueue(
            {
                "event_id": "verify-queued-event",
                "event_type": "heartbeat",
                "occurred_at": "2026-08-11T08:00:00+00:00",
            }
        )
    finally:
        spool.close()
    _mock_online(monkeypatch)
    sources: list[str] = []

    class FakeReporter:
        def __init__(
            self,
            _hub_url: str,
            _token: str,
            reporter_state_dir: Path,
            *,
            source: str,
        ) -> None:
            sources.append(source)
            self.spool = TelemetrySpool(reporter_state_dir)

        async def flush(self) -> None:
            _endpoint, batch = self.spool.peek_batch()
            self.spool.remove([str(entry["queue_id"]) for entry in batch])

    monkeypatch.setattr(agent_verify, "TelemetryReporter", FakeReporter)

    result = _invoke_verify(source, state_dir, "--json", "--fix", "--yes")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ready"] is True
    assert sources == ["verify"]
    assert payload["applied_fixes"][0]["code"] == "retry_telemetry_queue"
    reopened = TelemetrySpool(state_dir)
    try:
        assert reopened.count() == 0
    finally:
        reopened.close()
    assert not list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))


def test_agent_verify_fix_normalizes_known_legacy_command(
    monkeypatch,
    tmp_path,
) -> None:
    state_dir = tmp_path / "state"
    entry = _gateway_entry(state_dir)
    entry["command"] = "mcp-hub-gateway"
    entry["args"] = []
    source, state_dir = _write_ready_local_config(
        tmp_path,
        servers={"mcp-hub-gateway": entry},
    )
    _mock_online(monkeypatch)

    result = _invoke_verify(source, state_dir, "--json", "--fix", "--yes")

    assert result.exit_code == 0, result.output
    migrated = json.loads(source.read_text(encoding="utf-8"))
    assert set(migrated["mcpServers"]) == {"mcp-hub"}
    assert migrated["mcpServers"]["mcp-hub"]["command"] == "mcp-hub"
    assert migrated["mcpServers"]["mcp-hub"]["args"] == ["serve"]
    assert len(list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))) == 1


def test_agent_verify_fix_fills_only_deterministic_gateway_environment(
    monkeypatch,
    tmp_path,
) -> None:
    state_dir = tmp_path / "state"
    entry = _gateway_entry(state_dir)
    entry["env"] = {}
    source, state_dir = _write_ready_local_config(
        tmp_path,
        servers={"mcp-hub": entry},
    )
    _mock_online(monkeypatch)

    result = _invoke_verify(
        source,
        state_dir,
        "--hub-url",
        "https://hub.example.test",
        "--telemetry-token",
        "mcpht_test-token",
        "--json",
        "--fix",
        "--yes",
    )

    assert result.exit_code == 0, result.output
    migrated = json.loads(source.read_text(encoding="utf-8"))
    env = migrated["mcpServers"]["mcp-hub"]["env"]
    assert env["MCP_HUB_REPORT_URL"] == "https://hub.example.test"
    assert env["MCP_HUB_TELEMETRY_TOKEN"] == "mcpht_test-token"
    assert env["MCP_HUB_AGENT_TYPE"] == "cursor"
    assert env["MCP_HUB_AGENT_STATE_DIR"] == str(state_dir)
    assert env["MCP_HUB_GATEWAY_CONFIG"] == str(state_dir / "gateway.json")


def test_agent_verify_never_repairs_conflicting_duplicate_entries(
    monkeypatch,
    tmp_path,
) -> None:
    state_dir = tmp_path / "state"
    first = _gateway_entry(state_dir, token="mcpht_first-token")
    second = _gateway_entry(state_dir, token="mcpht_second-token")
    source, state_dir = _write_ready_local_config(
        tmp_path,
        servers={
            "mcp-hub": first,
            "mcp-hub-gateway": second,
        },
    )
    original = source.read_bytes()
    _mock_online(monkeypatch)

    result = _invoke_verify(source, state_dir, "--json", "--fix", "--yes")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    duplicate = next(
        check for check in payload["checks"] if check["code"] == "gateway_entry_duplicate"
    )
    assert duplicate["fixable"] is False
    assert payload["planned_fixes"] == []
    assert source.read_bytes() == original
    assert not list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))
