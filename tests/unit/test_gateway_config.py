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


def test_invalid_server_does_not_hide_valid_servers() -> None:
    specs, errors = parse_gateway_config(
        {
            "mcpServers": {
                "valid": {"command": "uvx", "args": ["mcp-valid"]},
                "remote": {"type": "http", "url": "https://example.test/mcp"},
            }
        }
    )

    assert [spec.server_id for spec in specs] == ["valid"]
    assert errors[0]["server_id"] == "remote"
    assert "unsupported transport" in errors[0]["error"]


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
