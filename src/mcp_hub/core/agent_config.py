"""Read, migrate and safely write MCP client configurations."""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import tomli_w

from mcp_hub.agent_types import normalize_agent_type
from mcp_hub.core.gateway_config import GatewayServerSpec, parse_gateway_server

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

ConfigFormat = Literal["json", "toml"]


@dataclass(frozen=True)
class AgentConfigProfile:
    """Known configuration format and paths for one MCP client."""

    agent_type: str
    name: str
    format: ConfigFormat
    server_key: str
    paths: tuple[Path, ...]
    display_path: str
    requires_stdio_type: bool = False


@dataclass(frozen=True)
class AgentMigration:
    """Prepared migration that can be previewed before writing."""

    profile: AgentConfigProfile
    source_path: Path
    document: dict[str, Any]
    specs: tuple[GatewayServerSpec, ...]
    errors: tuple[dict[str, str], ...]
    retained_server_names: tuple[str, ...]


def _home() -> Path:
    return Path.home()


def get_agent_profiles() -> dict[str, AgentConfigProfile]:
    """Return current supported local MCP client configuration profiles."""
    home = _home()
    appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    return {
        "claude-code": AgentConfigProfile(
            agent_type="claude-code",
            name="Claude Code",
            format="json",
            server_key="mcpServers",
            paths=(
                home / ".claude.json",
                home / ".claude" / "mcp.json",
                Path.cwd() / ".mcp.json",
            ),
            display_path="~/.claude.json",
        ),
        "claude-desktop": AgentConfigProfile(
            agent_type="claude-desktop",
            name="Claude Desktop",
            format="json",
            server_key="mcpServers",
            paths=(
                appdata / "Claude" / "claude_desktop_config.json",
                home / ".config" / "Claude" / "claude_desktop_config.json",
            ),
            display_path="Claude/claude_desktop_config.json",
        ),
        "codex": AgentConfigProfile(
            agent_type="codex",
            name="Codex",
            format="toml",
            server_key="mcp_servers",
            paths=(home / ".codex" / "config.toml",),
            display_path="~/.codex/config.toml",
        ),
        "cursor": AgentConfigProfile(
            agent_type="cursor",
            name="Cursor",
            format="json",
            server_key="mcpServers",
            paths=(home / ".cursor" / "mcp.json",),
            display_path="~/.cursor/mcp.json",
        ),
        "windsurf": AgentConfigProfile(
            agent_type="windsurf",
            name="Windsurf",
            format="json",
            server_key="mcpServers",
            paths=(home / ".codeium" / "windsurf" / "mcp_config.json",),
            display_path="~/.codeium/windsurf/mcp_config.json",
        ),
        "vscode-copilot": AgentConfigProfile(
            agent_type="vscode-copilot",
            name="VS Code Copilot",
            format="json",
            server_key="servers",
            paths=(Path.cwd() / ".vscode" / "mcp.json", home / ".vscode" / "mcp.json"),
            display_path=".vscode/mcp.json",
            requires_stdio_type=True,
        ),
        "trae": AgentConfigProfile(
            agent_type="trae",
            name="Trae",
            format="json",
            server_key="mcpServers",
            paths=(home / ".trae" / "mcp.json",),
            display_path="~/.trae/mcp.json",
        ),
        "generic": AgentConfigProfile(
            agent_type="generic",
            name="通用 MCP 客户端",
            format="json",
            server_key="mcpServers",
            paths=(home / ".config" / "mcp-hub" / "mcp.json",),
            display_path="~/.config/mcp-hub/mcp.json",
        ),
    }


def get_agent_profile(agent_type: str) -> AgentConfigProfile:
    normalized = normalize_agent_type(agent_type)
    return get_agent_profiles()[normalized]


def find_agent_config(agent_type: str) -> Path | None:
    """Return the first existing configuration for an Agent."""
    profile = get_agent_profile(agent_type)
    return next((path for path in profile.paths if path.exists()), None)


def _read_document(path: Path, format: ConfigFormat) -> dict[str, Any]:
    if format == "toml":
        with path.open("rb") as file:
            document = tomllib.load(file)
    else:
        document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Agent configuration root must be an object")
    return document


def _gateway_entry(
    profile: AgentConfigProfile,
    *,
    report_url: str,
    telemetry_token: str,
    state_dir: Path,
    gateway_config_path: Path,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "command": "mcp",
        "args": ["serve"],
        "env": {
            "MCP_HUB_REPORT_URL": report_url.rstrip("/"),
            "MCP_HUB_TELEMETRY_TOKEN": telemetry_token,
            "MCP_HUB_AGENT_TYPE": profile.agent_type,
            "MCP_HUB_AGENT_STATE_DIR": str(state_dir),
            "MCP_HUB_GATEWAY_CONFIG": str(gateway_config_path),
        },
    }
    if profile.requires_stdio_type:
        entry = {"type": "stdio", **entry}
    return entry


def prepare_agent_migration(
    agent_type: str,
    source_path: Path | None = None,
) -> AgentMigration:
    """Parse an Agent config and separate migratable stdio Servers."""
    profile = get_agent_profile(agent_type)
    path = source_path or find_agent_config(agent_type)
    if path is None:
        raise FileNotFoundError(f"No {profile.name} MCP configuration was found")
    document = _read_document(path, profile.format)
    raw_servers = document.get(profile.server_key, {})
    if not isinstance(raw_servers, dict):
        raise ValueError(f"{profile.server_key} must be an object")

    specs: list[GatewayServerSpec] = []
    errors: list[dict[str, str]] = []
    retained: list[str] = []
    for server_name, raw_server in raw_servers.items():
        normalized_name = str(server_name)
        if normalized_name in {"mcp-hub", "mcp-hub-gateway"}:
            continue
        try:
            specs.append(parse_gateway_server(normalized_name, raw_server))
        except ValueError as exc:
            retained.append(normalized_name)
            errors.append({"server_id": normalized_name, "error": str(exc)})

    return AgentMigration(
        profile=profile,
        source_path=path,
        document=document,
        specs=tuple(specs),
        errors=tuple(errors),
        retained_server_names=tuple(retained),
    )


def apply_agent_migration(
    migration: AgentMigration,
    *,
    report_url: str,
    telemetry_token: str,
    state_dir: Path,
    gateway_config_path: Path,
) -> Path:
    """Back up and atomically replace direct stdio entries with one Gateway entry."""
    path = migration.source_path
    raw_servers = migration.document.get(migration.profile.server_key, {})
    retained = {
        name: value
        for name, value in raw_servers.items()
        if name in migration.retained_server_names
    }
    retained["mcp-hub"] = _gateway_entry(
        migration.profile,
        report_url=report_url,
        telemetry_token=telemetry_token,
        state_dir=state_dir,
        gateway_config_path=gateway_config_path,
    )
    document = {**migration.document, migration.profile.server_key: retained}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.mcp-hub-backup-{timestamp}")
    backup_path.write_bytes(path.read_bytes())
    source_mode = path.stat().st_mode
    with contextlib.suppress(OSError):
        backup_path.chmod(source_mode)

    if migration.profile.format == "toml":
        serialized = tomli_w.dumps(document)
    else:
        serialized = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    temp_path = path.with_suffix(f"{path.suffix}.mcp-hub.tmp")
    temp_path.write_text(serialized, encoding="utf-8")
    with contextlib.suppress(OSError):
        temp_path.chmod(source_mode)
    temp_path.replace(path)
    return backup_path
