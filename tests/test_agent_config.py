"""Agent configuration migration and one-command setup tests."""

from __future__ import annotations

import json

import tomllib
from click.testing import CliRunner

from mcp_hub.cli.agent import agent
from mcp_hub.core.agent_config import apply_agent_migration, prepare_agent_migration
from mcp_hub.core.gateway_config import load_gateway_config, write_gateway_config


def test_json_agent_migration_backs_up_and_retains_unsupported_entries(tmp_path) -> None:
    source = tmp_path / "mcp.json"
    original = {
        "theme": "dark",
        "mcpServers": {
            "weather": {
                "command": "npx",
                "args": ["-y", "@example/weather", "--label", "New York"],
                "env": {"WEATHER_API_KEY": "secret"},
            },
            "remote": {
                "type": "http",
                "url": "https://example.test/mcp",
            },
        },
    }
    source.write_text(json.dumps(original), encoding="utf-8")
    migration = prepare_agent_migration("cursor", source)
    gateway_path = tmp_path / "gateway.json"
    write_gateway_config(list(migration.specs), gateway_path)

    backup = apply_agent_migration(
        migration,
        report_url="https://hub.example.test",
        telemetry_token="mcpht_test",
        state_dir=tmp_path,
        gateway_config_path=gateway_path,
    )

    migrated = json.loads(source.read_text(encoding="utf-8"))
    assert json.loads(backup.read_text(encoding="utf-8")) == original
    assert migrated["theme"] == "dark"
    assert set(migrated["mcpServers"]) == {"remote", "mcp-hub"}
    assert migrated["mcpServers"]["remote"]["url"] == "https://example.test/mcp"
    assert migrated["mcpServers"]["mcp-hub"]["env"]["MCP_HUB_GATEWAY_CONFIG"] == str(
        gateway_path
    )
    specs, errors = load_gateway_config(gateway_path)
    assert errors == []
    assert specs[0].args[-1] == "New York"
    assert specs[0].env == {"WEATHER_API_KEY": "secret"}


def test_codex_toml_migration_preserves_other_settings(tmp_path) -> None:
    source = tmp_path / "config.toml"
    source.write_text(
        """
model = "gpt-5"

[mcp_servers.weather]
command = "uvx"
args = ["weather-server", "--readonly"]

[mcp_servers.weather.env]
WEATHER_API_KEY = "secret"
""".strip(),
        encoding="utf-8",
    )
    migration = prepare_agent_migration("codex", source)
    gateway_path = tmp_path / "gateway.json"
    write_gateway_config(list(migration.specs), gateway_path)

    apply_agent_migration(
        migration,
        report_url="https://hub.example.test",
        telemetry_token="mcpht_test",
        state_dir=tmp_path,
        gateway_config_path=gateway_path,
    )

    with source.open("rb") as file:
        migrated = tomllib.load(file)
    assert migrated["model"] == "gpt-5"
    assert set(migrated["mcp_servers"]) == {"mcp-hub"}
    assert migrated["mcp_servers"]["mcp-hub"]["args"] == ["serve"]


def test_agent_setup_requires_confirmation_and_leaves_source_unchanged(tmp_path) -> None:
    source = tmp_path / "mcp.json"
    original = '{"mcpServers":{"weather":{"command":"uvx","args":["weather"]}}}'
    source.write_text(original, encoding="utf-8")

    result = CliRunner().invoke(
        agent,
        [
            "setup",
            "--agent",
            "cursor",
            "--hub-url",
            "https://hub.example.test",
            "--telemetry-token",
            "mcpht_test",
            "--source-config",
            str(source),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "已取消" in result.output
    assert source.read_text(encoding="utf-8") == original


def test_agent_setup_writes_gateway_and_replaces_direct_entries(tmp_path) -> None:
    source = tmp_path / "mcp.json"
    source.write_text(
        '{"mcpServers":{"weather":{"command":"uvx","args":["weather"]}}}',
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"

    result = CliRunner().invoke(
        agent,
        [
            "setup",
            "--agent",
            "cursor",
            "--hub-url",
            "https://hub.example.test",
            "--telemetry-token",
            "mcpht_test",
            "--source-config",
            str(source),
            "--state-dir",
            str(state_dir),
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    migrated = json.loads(source.read_text(encoding="utf-8"))
    assert set(migrated["mcpServers"]) == {"mcp-hub"}
    specs, errors = load_gateway_config(state_dir / "gateway.json")
    assert errors == []
    assert [spec.server_id for spec in specs] == ["weather"]
