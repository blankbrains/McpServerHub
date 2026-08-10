"""Gateway-aware Hub configuration synchronization regression tests."""

from __future__ import annotations

from mcp_hub.cli.config import _decode_hub_config, _merge_private_gateway_fields
from mcp_hub.core.agent_config import get_agent_profile
from mcp_hub.core.gateway_config import GatewayServerSpec


def test_decode_hub_config_supports_json_and_codex_toml() -> None:
    json_specs, json_errors = _decode_hub_config(
        {"mcpServers": {"weather": {"command": "npx", "args": ["weather-mcp"]}}},
        get_agent_profile("cursor"),
    )
    toml_specs, toml_errors = _decode_hub_config(
        '[mcp_servers.weather]\ncommand = "uvx"\nargs = ["weather-mcp"]\n',
        get_agent_profile("codex"),
    )

    assert json_errors == []
    assert toml_errors == []
    assert json_specs[0].command == "npx"
    assert toml_specs[0].command == "uvx"


def test_sync_preserves_local_credentials_and_working_directory() -> None:
    existing = [
        GatewayServerSpec(
            server_id="weather",
            command="npx",
            args=("old-weather",),
            env={"WEATHER_API_KEY": "local-secret"},
            cwd="/srv/weather",
        ),
        GatewayServerSpec(
            server_id="remote",
            transport="streamable-http",
            url="https://old.example.test/mcp",
            headers={"Authorization": "Bearer local-secret"},
        ),
    ]
    desired = [
        GatewayServerSpec(
            server_id="weather",
            command="npx",
            args=("new-weather",),
        ),
        GatewayServerSpec(
            server_id="remote",
            transport="streamable-http",
            url="https://new.example.test/mcp",
        ),
    ]

    merged = _merge_private_gateway_fields(desired, existing)

    assert merged[0].args == ("new-weather",)
    assert merged[0].env == {"WEATHER_API_KEY": "local-secret"}
    assert merged[0].cwd == "/srv/weather"
    assert merged[1].url == "https://new.example.test/mcp"
    assert merged[1].headers == {"Authorization": "Bearer local-secret"}
