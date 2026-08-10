"""Canonical local configuration used by the MCP stdio gateway."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_hub.core.telemetry import get_agent_state_dir

GATEWAY_CONFIG_ENV = "MCP_HUB_GATEWAY_CONFIG"
GATEWAY_CONFIG_FILENAME = "gateway.json"
GATEWAY_SERVER_KEY = "mcpServers"
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class GatewayServerSpec:
    """Validated stdio process definition for one local MCP Server."""

    server_id: str
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    enabled: bool = True
    transport: str = "stdio"
    version: str = ""

    @property
    def executable(self) -> str:
        return self.command

    def process_env(self, base_env: dict[str, str]) -> dict[str, str]:
        """Merge only this Server's explicitly authorized environment variables."""
        return {**base_env, **self.env}

    def inventory_entry(self) -> dict[str, Any]:
        """Return a privacy-preserving inventory record without values or arguments."""
        fingerprint_payload = {
            "command": self.command,
            "args": list(self.args),
            "env_keys": sorted(self.env),
            "cwd": self.cwd or "",
            "transport": self.transport,
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return {
            "server_name": self.server_id,
            "transport": self.transport,
            "command_name": Path(self.command).name,
            "env_keys": sorted(self.env),
            "config_hash": fingerprint,
            "enabled": self.enabled,
        }


def get_gateway_config_path(
    state_dir: Path | None = None,
    *,
    agent_type: str | None = None,
) -> Path:
    """Return the configured canonical Gateway file path."""
    configured = os.environ.get(GATEWAY_CONFIG_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return (state_dir or get_agent_state_dir(agent_type)) / GATEWAY_CONFIG_FILENAME


def split_legacy_command(command: str) -> tuple[str, tuple[str, ...]]:
    """Parse a legacy command string for compatibility with Registry records."""
    normalized = command.strip()
    if not normalized:
        raise ValueError("MCP Server command cannot be empty")
    try:
        parts = shlex.split(normalized, posix=os.name != "nt")
    except ValueError as exc:
        raise ValueError(f"Invalid MCP Server command: {exc}") from exc
    parts = [
        part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"' else part
        for part in parts
    ]
    if not parts:
        raise ValueError("MCP Server command cannot be empty")
    return parts[0], tuple(parts[1:])


def _normalize_env(raw_env: Any) -> dict[str, str]:
    if raw_env is None:
        return {}
    if not isinstance(raw_env, dict):
        raise ValueError("MCP Server env must be an object")

    env: dict[str, str] = {}
    for raw_key, raw_value in raw_env.items():
        key = str(raw_key)
        if not _ENV_NAME_PATTERN.fullmatch(key):
            raise ValueError(f"Invalid environment variable name: {key}")
        if not isinstance(raw_value, (str, int, float, bool)):
            raise ValueError(f"Environment variable {key} must be a scalar value")
        env[key] = str(raw_value)
    return env


def parse_gateway_server(server_id: str, raw: Any) -> GatewayServerSpec:
    """Validate an MCP client JSON entry and preserve its structured process data."""
    if not isinstance(raw, dict):
        raise ValueError(f"MCP Server {server_id} configuration must be an object")

    transport = str(raw.get("type") or raw.get("transport") or "stdio").strip().lower()
    if transport != "stdio":
        raise ValueError(f"MCP Server {server_id} uses unsupported transport: {transport}")

    raw_command = raw.get("command", "")
    if not isinstance(raw_command, str) or not raw_command.strip():
        raise ValueError(f"MCP Server {server_id} command cannot be empty")

    raw_args = raw.get("args")
    if raw_args is None:
        command, args = split_legacy_command(raw_command)
    else:
        if not isinstance(raw_args, list) or not all(isinstance(arg, str) for arg in raw_args):
            raise ValueError(f"MCP Server {server_id} args must be a string array")
        command = raw_command.strip()
        args = tuple(raw_args)

    cwd = raw.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not cwd.strip()):
        raise ValueError(f"MCP Server {server_id} cwd must be a non-empty string")

    return GatewayServerSpec(
        server_id=server_id,
        command=command,
        args=args,
        env=_normalize_env(raw.get("env")),
        cwd=cwd.strip() if isinstance(cwd, str) else None,
        enabled=bool(raw.get("enabled", True)),
        transport=transport,
        version=str(raw.get("version", "")),
    )


def parse_gateway_config(config: Any) -> tuple[list[GatewayServerSpec], list[dict[str, str]]]:
    """Parse a canonical or standard MCP JSON configuration."""
    if not isinstance(config, dict):
        raise ValueError("Gateway configuration must be a JSON object")

    raw_servers = config.get(GATEWAY_SERVER_KEY)
    if raw_servers is None:
        raw_servers = config.get("servers", {})
    if not isinstance(raw_servers, dict):
        raise ValueError("Gateway configuration must contain an MCP Server object")

    specs: list[GatewayServerSpec] = []
    errors: list[dict[str, str]] = []
    for server_id, raw in raw_servers.items():
        normalized_id = str(server_id).strip()
        if not normalized_id or normalized_id in {"mcp-hub", "mcp-hub-gateway"}:
            continue
        try:
            specs.append(parse_gateway_server(normalized_id, raw))
        except ValueError as exc:
            errors.append({"server_id": normalized_id, "error": str(exc)})
    return specs, errors


def load_gateway_config(
    path: Path | None = None,
    *,
    agent_type: str | None = None,
) -> tuple[list[GatewayServerSpec], list[dict[str, str]]]:
    """Load the local canonical Gateway file. A missing file is not an error."""
    config_path = path or get_gateway_config_path(agent_type=agent_type)
    if not config_path.exists():
        return [], []
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [{"server_id": "", "error": f"Gateway JSON parse failed: {exc}"}]
    except OSError as exc:
        return [], [{"server_id": "", "error": f"Gateway config read failed: {exc}"}]
    try:
        return parse_gateway_config(raw)
    except ValueError as exc:
        return [], [{"server_id": "", "error": str(exc)}]


def write_gateway_config(
    specs: list[GatewayServerSpec],
    path: Path | None = None,
    *,
    agent_type: str | None = None,
) -> Path:
    """Atomically persist the canonical local Gateway configuration."""
    config_path = path or get_gateway_config_path(agent_type=agent_type)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        GATEWAY_SERVER_KEY: {
            spec.server_id: {
                "command": spec.command,
                "args": list(spec.args),
                "env": spec.env,
                **({"cwd": spec.cwd} if spec.cwd else {}),
                "enabled": spec.enabled,
                "transport": spec.transport,
                **({"version": spec.version} if spec.version else {}),
            }
            for spec in specs
        },
    }
    temp_path = config_path.with_suffix(f"{config_path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(config_path)
    if os.name != "nt":
        with contextlib.suppress(OSError):
            config_path.chmod(0o600)
    return config_path
