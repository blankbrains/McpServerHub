"""Safe Agent disconnect, backup, and recovery regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import tomli_w
from click.testing import CliRunner

from mcp_hub.cli import agent as agent_cli
from mcp_hub.cli.agent import agent
from mcp_hub.core import agent_recovery
from mcp_hub.core.agent_recovery import (
    MigrationManifest,
    get_migration_manifest_path,
    load_migration_manifest,
)

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib


class _NoopReporter:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    async def report_inventory(
        self,
        _servers: object,
        _errors: object,
        *,
        source: str,
    ) -> None:
        assert source == "setup"

    async def close(self) -> None:
        pass


def _run_setup(
    monkeypatch,
    source: Path,
    state_dir: Path,
    *,
    agent_type: str,
) -> object:
    monkeypatch.setattr(agent_cli, "TelemetryReporter", _NoopReporter)
    return CliRunner().invoke(
        agent,
        [
            "setup",
            "--agent",
            agent_type,
            "--hub-url",
            "https://hub.example.test",
            "--telemetry-token",
            "mcpht_private-device-token",
            "--source-config",
            str(source),
            "--state-dir",
            str(state_dir),
            "--yes",
        ],
    )


def _run_recovery(
    command: str,
    state_dir: Path,
    *,
    agent_type: str,
    yes: bool = True,
    manifest: Path | None = None,
) -> object:
    args = [
        command,
        "--agent",
        agent_type,
        "--state-dir",
        str(state_dir),
        "--json",
    ]
    if manifest is not None:
        args.extend(["--manifest", str(manifest)])
    if yes:
        args.append("--yes")
    return CliRunner().invoke(agent, args)


def _json_source(path: Path) -> dict[str, object]:
    document: dict[str, object] = {
        "theme": "dark",
        "mcpServers": {
            "weather": {
                "command": "uvx",
                "args": ["weather", "--city", "New York"],
                "env": {"WEATHER_API_KEY": "private-weather-key"},
            }
        },
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return document


def test_setup_writes_privacy_preserving_manifest(monkeypatch, tmp_path) -> None:
    source = tmp_path / "mcp.json"
    original = _json_source(source)
    state_dir = tmp_path / "state"

    result = _run_setup(
        monkeypatch,
        source,
        state_dir,
        agent_type="cursor",
    )

    assert result.exit_code == 0, result.output
    manifest_path = get_migration_manifest_path(state_dir)
    manifest = load_migration_manifest(manifest_path)
    assert manifest.status == "active"
    assert manifest.agent_type == "cursor"
    assert manifest.migrated_server_names == ["weather"]
    assert Path(manifest.original_backup_path).is_file()
    assert manifest.pre_migration_hash != manifest.post_migration_hash
    backup = json.loads(
        Path(manifest.original_backup_path).read_text(encoding="utf-8")
    )
    assert backup == original

    serialized = manifest_path.read_text(encoding="utf-8")
    assert "mcpht_private-device-token" not in serialized
    assert "private-weather-key" not in serialized
    assert "New York" not in serialized
    assert "MCP_HUB_TELEMETRY_TOKEN" not in serialized


def test_setup_backs_up_existing_gateway_config(monkeypatch, tmp_path) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    gateway_path = state_dir / "gateway.json"
    previous_gateway = '{"version":1,"mcpServers":{"old":{"command":"uvx"}}}'
    gateway_path.write_text(previous_gateway, encoding="utf-8")

    result = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")

    assert result.exit_code == 0, result.output
    backups = list(state_dir.glob("gateway.json.mcp-hub-backup-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == previous_gateway
    assert "原 Gateway 配置备份" in result.output


def test_setup_rolls_back_agent_and_gateway_when_manifest_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    original = _json_source(source)
    original_bytes = source.read_bytes()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    gateway_path = state_dir / "gateway.json"
    previous_gateway = '{"version":1,"mcpServers":{}}'
    gateway_path.write_text(previous_gateway, encoding="utf-8")
    monkeypatch.setattr(agent_cli, "TelemetryReporter", _NoopReporter)
    monkeypatch.setattr(
        agent_cli,
        "create_migration_manifest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("manifest denied")),
    )

    result = CliRunner().invoke(
        agent,
        [
            "setup",
            "--agent",
            "cursor",
            "--hub-url",
            "https://hub.example.test",
            "--telemetry-token",
            "mcpht_private-device-token",
            "--source-config",
            str(source),
            "--state-dir",
            str(state_dir),
            "--yes",
        ],
    )

    assert result.exit_code == 1
    assert "已恢复迁移前配置" in result.output
    assert source.read_bytes() == original_bytes
    assert json.loads(source.read_text(encoding="utf-8")) == original
    assert gateway_path.read_text(encoding="utf-8") == previous_gateway
    assert not get_migration_manifest_path(state_dir).exists()


def test_setup_refuses_to_replace_an_active_migration_manifest(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "state"
    first = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert first.exit_code == 0, first.output

    current = json.loads(source.read_text(encoding="utf-8"))
    current["mcpServers"]["later"] = {
        "command": "uvx",
        "args": ["later"],
    }
    source.write_text(json.dumps(current), encoding="utf-8")
    current_bytes = source.read_bytes()
    manifest_bytes = get_migration_manifest_path(state_dir).read_bytes()
    backups_before = sorted(tmp_path.rglob("*.mcp-hub-backup-*"))

    second = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")

    assert second.exit_code == 1
    assert "已有未断开的迁移清单" in second.output
    assert source.read_bytes() == current_bytes
    assert get_migration_manifest_path(state_dir).read_bytes() == manifest_bytes
    assert sorted(tmp_path.rglob("*.mcp-hub-backup-*")) == backups_before


def test_disconnect_restores_json_and_preserves_later_changes(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    original = _json_source(source)
    state_dir = tmp_path / "state"
    setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert setup.exit_code == 0, setup.output

    current = json.loads(source.read_text(encoding="utf-8"))
    current["theme"] = "light"
    current["fontSize"] = 15
    current["mcpServers"]["later"] = {
        "command": "uvx",
        "args": ["later"],
    }
    source.write_text(json.dumps(current), encoding="utf-8")
    backups_before = list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))

    result = _run_recovery(
        "disconnect",
        state_dir,
        agent_type="cursor",
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["changed"] is True
    assert payload["restore_server_names"] == ["weather"]
    assert payload["preserved_server_names"] == ["later"]
    assert payload["changed_top_level_keys"] == ["fontSize", "theme"]

    restored = json.loads(source.read_text(encoding="utf-8"))
    assert restored["theme"] == "light"
    assert restored["fontSize"] == 15
    assert set(restored["mcpServers"]) == {"weather", "later"}
    assert restored["mcpServers"]["weather"] == original["mcpServers"]["weather"]
    assert len(list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))) == (
        len(backups_before) + 1
    )
    manifest = load_migration_manifest(get_migration_manifest_path(state_dir))
    assert manifest.status == "disconnected"
    assert manifest.disconnect_backup_path == payload["backup_path"]


def test_disconnect_is_idempotent_and_does_not_create_another_backup(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "state"
    setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert setup.exit_code == 0, setup.output

    first = _run_recovery("disconnect", state_dir, agent_type="cursor")
    assert first.exit_code == 0, first.output
    backups_after_first = list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))
    restored_bytes = source.read_bytes()

    second = _run_recovery("disconnect", state_dir, agent_type="cursor")

    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)
    assert payload["already_disconnected"] is True
    assert source.read_bytes() == restored_bytes
    assert list(tmp_path.glob("mcp.json.mcp-hub-backup-*")) == backups_after_first


def test_disconnect_preview_requires_confirmation_and_is_read_only(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "state"
    setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert setup.exit_code == 0, setup.output
    current_bytes = source.read_bytes()
    backups_before = list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))

    result = _run_recovery(
        "disconnect",
        state_dir,
        agent_type="cursor",
        yes=False,
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["confirmation_required"] is True
    assert payload["success"] is True
    assert source.read_bytes() == current_bytes
    assert list(tmp_path.glob("mcp.json.mcp-hub-backup-*")) == backups_before


def test_disconnect_stops_on_same_name_server_conflict(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "state"
    setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert setup.exit_code == 0, setup.output

    current = json.loads(source.read_text(encoding="utf-8"))
    current["mcpServers"]["weather"] = {
        "command": "uvx",
        "args": ["different-weather"],
    }
    source.write_text(json.dumps(current), encoding="utf-8")
    current_bytes = source.read_bytes()
    backups_before = list(tmp_path.glob("mcp.json.mcp-hub-backup-*"))

    result = _run_recovery("disconnect", state_dir, agent_type="cursor")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["conflicts"] == [
        {
            "code": "server_name_conflict",
            "path": "mcpServers.weather",
            "message": "当前配置存在同名但内容不同的 Server，不能自动覆盖。",
        }
    ]
    assert source.read_bytes() == current_bytes
    assert list(tmp_path.glob("mcp.json.mcp-hub-backup-*")) == backups_before


def test_disconnect_allows_token_rotation_but_rejects_gateway_command_change(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "state"
    setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert setup.exit_code == 0, setup.output

    current = json.loads(source.read_text(encoding="utf-8"))
    gateway = current["mcpServers"]["mcp-hub"]
    gateway["env"]["MCP_HUB_TELEMETRY_TOKEN"] = "mcpht_rotated-token"
    gateway["env"]["MCP_HUB_REPORT_URL"] = "https://new-hub.example.test"
    source.write_text(json.dumps(current), encoding="utf-8")

    rotated = _run_recovery("disconnect", state_dir, agent_type="cursor")
    assert rotated.exit_code == 0, rotated.output

    second_source = tmp_path / "other-mcp.json"
    _json_source(second_source)
    second_state = tmp_path / "other-state"
    second_setup = _run_setup(
        monkeypatch,
        second_source,
        second_state,
        agent_type="cursor",
    )
    assert second_setup.exit_code == 0, second_setup.output
    modified = json.loads(second_source.read_text(encoding="utf-8"))
    modified["mcpServers"]["mcp-hub"]["command"] = "custom-gateway"
    second_source.write_text(json.dumps(modified), encoding="utf-8")

    conflicted = _run_recovery("disconnect", second_state, agent_type="cursor")
    assert conflicted.exit_code == 1
    payload = json.loads(conflicted.output)
    assert payload["conflicts"][0]["code"] == "gateway_entry_modified"


def test_restore_recovers_toml_and_preserves_later_settings(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "config.toml"
    source.write_text(
        """
model = "gpt-5"

[mcp_servers.weather]
command = "uvx"
args = ["weather", "--readonly"]

[mcp_servers.weather.env]
WEATHER_API_KEY = "private-weather-key"
""".strip(),
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"
    setup = _run_setup(monkeypatch, source, state_dir, agent_type="codex")
    assert setup.exit_code == 0, setup.output

    with source.open("rb") as file:
        current = tomllib.load(file)
    current["model"] = "gpt-5.1"
    current["approval_policy"] = "never"
    current["mcp_servers"]["later"] = {
        "command": "uvx",
        "args": ["later"],
    }
    source.write_text(tomli_w.dumps(current), encoding="utf-8")

    result = _run_recovery("restore", state_dir, agent_type="codex")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["operation"] == "restore"
    with source.open("rb") as file:
        restored = tomllib.load(file)
    assert restored["model"] == "gpt-5.1"
    assert restored["approval_policy"] == "never"
    assert set(restored["mcp_servers"]) == {"weather", "later"}
    assert restored["mcp_servers"]["weather"]["env"] == {
        "WEATHER_API_KEY": "private-weather-key"
    }


def test_restore_derives_state_dir_from_explicit_manifest(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "custom-state"
    setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert setup.exit_code == 0, setup.output
    manifest_path = get_migration_manifest_path(state_dir)
    monkeypatch.setattr(
        agent_recovery,
        "get_agent_state_dir",
        lambda _agent_type: pytest.fail("explicit manifest must define its state dir"),
    )

    result = CliRunner().invoke(
        agent,
        [
            "restore",
            "--agent",
            "cursor",
            "--manifest",
            str(manifest_path),
            "--json",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["changed"] is True


def test_restore_rejects_superseded_history_manifest(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "state"
    first_setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert first_setup.exit_code == 0, first_setup.output
    first_manifest = load_migration_manifest(get_migration_manifest_path(state_dir))
    first_history = state_dir / "migration-history" / f"{first_manifest.migration_id}.json"
    disconnected = _run_recovery("disconnect", state_dir, agent_type="cursor")
    assert disconnected.exit_code == 0, disconnected.output

    restored = json.loads(source.read_text(encoding="utf-8"))
    restored["mcpServers"]["weather"]["args"] = ["weather", "--metric"]
    source.write_text(json.dumps(restored), encoding="utf-8")
    second_setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert second_setup.exit_code == 0, second_setup.output
    current_bytes = source.read_bytes()

    result = _run_recovery(
        "restore",
        state_dir,
        agent_type="cursor",
        manifest=first_history,
    )

    assert result.exit_code == 1
    assert "指定清单不是当前迁移记录" in result.output
    assert source.read_bytes() == current_bytes


def test_backups_lists_manifests_without_secrets(monkeypatch, tmp_path) -> None:
    source = tmp_path / "mcp.json"
    _json_source(source)
    state_dir = tmp_path / "state"
    setup = _run_setup(monkeypatch, source, state_dir, agent_type="cursor")
    assert setup.exit_code == 0, setup.output

    result = CliRunner().invoke(
        agent,
        [
            "backups",
            "--agent",
            "cursor",
            "--state-dir",
            str(state_dir),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["backups"]) == 1
    assert payload["backups"][0]["migrated_server_names"] == ["weather"]
    assert "mcpht_private-device-token" not in result.output
    assert "private-weather-key" not in result.output
    assert "New York" not in result.output


@pytest.mark.parametrize(
    ("source_path", "backup_path", "gateway_path"),
    [
        (
            r"C:\Users\Alice\AppData\Roaming\Cursor\mcp.json",
            r"C:\Users\Alice\AppData\Roaming\Cursor\mcp.json.mcp-hub-backup-1",
            r"D:\McpHub\cursor\gateway.json",
        ),
        (
            "/Users/alice/.codex/config.toml",
            "/Users/alice/.codex/config.toml.mcp-hub-backup-1",
            "/Users/alice/.config/mcp-hub/codex/gateway.json",
        ),
        (
            "/home/alice/.config/mcp/mcp.json",
            "/home/alice/.config/mcp/mcp.json.mcp-hub-backup-1",
            "/home/alice/.config/mcp-hub/cursor/gateway.json",
        ),
    ],
)
def test_manifest_preserves_windows_macos_and_linux_paths(
    source_path: str,
    backup_path: str,
    gateway_path: str,
) -> None:
    manifest = MigrationManifest(
        migration_id="a" * 32,
        status="active",
        agent_type="cursor",
        source_config_path=source_path,
        original_backup_path=backup_path,
        migration_time="2026-08-11T10:00:00+00:00",
        pre_migration_hash="b" * 64,
        post_migration_hash="c" * 64,
        gateway_entry_hash="d" * 64,
        migrated_server_names=["weather"],
        retained_server_names=[],
        gateway_config_path=gateway_path,
        cli_version="0.2.0",
    )

    payload = manifest.model_dump(mode="json")
    assert payload["source_config_path"] == source_path
    assert payload["original_backup_path"] == backup_path
    assert payload["gateway_config_path"] == gateway_path
