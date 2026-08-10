"""Canonical Gateway configuration regression tests."""

from __future__ import annotations

import json

import pytest

from mcp_hub.core.gateway_config import (
    GatewayServerSpec,
    load_gateway_config,
    parse_gateway_config,
    split_legacy_command,
    write_gateway_config,
)


def test_structured_command_preserves_arguments_and_explicit_environment() -> None:
    specs, errors = parse_gateway_config(
        {
            "mcpServers": {
                "weather": {
                    "command": "C:\\Program Files\\nodejs\\npx.cmd",
                    "args": ["-y", "@example/weather", "--label", "New York"],
                    "env": {"WEATHER_API_KEY": "secret", "PORT": 3987},
                    "cwd": "D:\\MCP Servers\\weather",
                }
            }
        }
    )

    assert errors == []
    assert specs == [
        GatewayServerSpec(
            server_id="weather",
            command="C:\\Program Files\\nodejs\\npx.cmd",
            args=("-y", "@example/weather", "--label", "New York"),
            env={"WEATHER_API_KEY": "secret", "PORT": "3987"},
            cwd="D:\\MCP Servers\\weather",
        )
    ]
    assert specs[0].process_env({"PATH": "base", "UNRELATED_SECRET": "not-forwarded"}) == {
        "PATH": "base",
        "UNRELATED_SECRET": "not-forwarded",
        "WEATHER_API_KEY": "secret",
        "PORT": "3987",
    }


def test_inventory_never_contains_argument_or_environment_values() -> None:
    spec = GatewayServerSpec(
        server_id="weather",
        command="npx",
        args=("-y", "@example/weather", "--token", "argument-secret"),
        env={"WEATHER_API_KEY": "environment-secret"},
    )

    inventory = spec.inventory_entry()
    serialized = json.dumps(inventory)

    assert inventory["command_name"] == "npx"
    assert inventory["env_keys"] == ["WEATHER_API_KEY"]
    assert "argument-secret" not in serialized
    assert "environment-secret" not in serialized


def test_remote_servers_are_parsed_without_hiding_valid_stdio_servers() -> None:
    specs, errors = parse_gateway_config(
        {
            "mcpServers": {
                "valid": {"command": "uvx", "args": ["mcp-valid"]},
                "remote": {
                    "type": "http",
                    "url": "https://example.test/mcp",
                    "headers": {
                        "Authorization": "Bearer secret",
                        "X-Tenant": "tenant-a",
                    },
                },
            }
        }
    )

    assert errors == []
    assert [spec.server_id for spec in specs] == ["valid", "remote"]
    remote = specs[1]
    assert remote.transport == "streamable-http"
    assert remote.url == "https://example.test/mcp"
    assert remote.headers["Authorization"] == "Bearer secret"
    inventory = remote.inventory_entry()
    assert inventory["command_name"] == ""
    assert inventory["header_keys"] == ["Authorization", "X-Tenant"]
    serialized = json.dumps(inventory)
    assert "https://example.test/mcp" not in serialized
    assert "Bearer secret" not in serialized


def test_remote_transport_is_inferred_from_url_and_round_trips(tmp_path) -> None:
    specs, errors = parse_gateway_config(
        {
            "mcpServers": {
                "remote": {
                    "url": "https://example.test/mcp",
                    "headers": {"Authorization": "Bearer local-only"},
                },
                "legacy-sse": {
                    "type": "sse",
                    "url": "https://example.test/sse",
                },
            }
        }
    )

    assert errors == []
    assert [spec.transport for spec in specs] == ["streamable-http", "sse"]

    path = tmp_path / "remote-gateway.json"
    write_gateway_config(specs, path)
    loaded, load_errors = load_gateway_config(path)

    assert load_errors == []
    assert loaded == specs


def test_codex_remote_auth_fields_are_preserved_and_resolved() -> None:
    specs, errors = parse_gateway_config(
        {
            "mcpServers": {
                "remote": {
                    "url": "https://example.test/mcp",
                    "http_headers": {"X-Tenant": "tenant-a"},
                    "env_http_headers": {"X-Workspace": "MCP_WORKSPACE"},
                    "bearer_token_env_var": "MCP_ACCESS_TOKEN",
                }
            }
        }
    )

    assert errors == []
    spec = specs[0]
    assert spec.resolved_headers(
        {
            "MCP_WORKSPACE": "workspace-a",
            "MCP_ACCESS_TOKEN": "secret-token",
        }
    ) == {
        "X-Tenant": "tenant-a",
        "X-Workspace": "workspace-a",
        "Authorization": "Bearer secret-token",
    }
    serialized = json.dumps(spec.inventory_entry())
    assert "X-Tenant" in serialized
    assert "X-Workspace" in serialized
    assert "Authorization" in serialized
    assert "workspace-a" not in serialized
    assert "secret-token" not in serialized


def test_codex_oauth_remote_is_retained_as_unsupported() -> None:
    specs, errors = parse_gateway_config(
        {
            "mcpServers": {
                "oauth-server": {
                    "url": "https://example.test/mcp",
                    "auth": "oauth",
                }
            }
        }
    )

    assert specs == []
    assert errors[0]["server_id"] == "oauth-server"
    assert "cannot be migrated" in errors[0]["error"]


def test_gateway_config_round_trip(tmp_path) -> None:
    path = tmp_path / "gateway.json"
    expected = [
        GatewayServerSpec(
            server_id="database",
            command="uvx",
            args=("mcp-database", "--readonly"),
            env={"DATABASE_URL": "sqlite:///data.db"},
            enabled=False,
        )
    ]

    write_gateway_config(expected, path)
    actual, errors = load_gateway_config(path)

    assert errors == []
    assert actual == expected


def test_legacy_command_parser_preserves_quoted_arguments() -> None:
    command, args = split_legacy_command('npx -y @example/server --label "New York"')

    assert command == "npx"
    assert args == ("-y", "@example/server", "--label", "New York")


@pytest.mark.parametrize(
    "raw",
    [
        {"command": "", "args": []},
        {"command": "npx", "args": "--not-a-list"},
        {"command": "npx", "env": {"INVALID-NAME": "value"}},
    ],
)
def test_invalid_server_configuration_is_reported(raw: dict) -> None:
    specs, errors = parse_gateway_config({"mcpServers": {"invalid": raw}})

    assert specs == []
    assert errors and errors[0]["server_id"] == "invalid"
