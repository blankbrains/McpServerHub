"""Classify catalog metadata without confusing installation and execution."""

from __future__ import annotations

import shlex
from typing import Any


def _command_parts(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []


def is_install_only_command(command: str) -> bool:
    """Return whether a command prepares software but cannot serve MCP over stdio."""
    parts = [part.lower() for part in _command_parts(command)]
    if not parts:
        return False

    prefixes = (
        ("pip", "install"),
        ("pip3", "install"),
        ("python", "-m", "pip", "install"),
        ("python3", "-m", "pip", "install"),
        ("py", "-m", "pip", "install"),
        ("uv", "pip", "install"),
        ("npm", "install"),
        ("npm", "i"),
        ("pnpm", "add"),
        ("yarn", "add"),
        ("go", "install"),
        ("cargo", "install"),
        ("brew", "install"),
        ("apt", "install"),
        ("apt-get", "install"),
    )
    return any(parts[: len(prefix)] == list(prefix) for prefix in prefixes)


def has_runnable_server_config(
    command: str,
    config_template: dict[str, Any] | None = None,
) -> bool:
    """Return whether metadata contains an executable or structured MCP endpoint."""
    if config_template:
        return True
    normalized = command.strip()
    return bool(normalized) and not is_install_only_command(normalized)


def is_legacy_inferred_github_command(
    server_id: str,
    install_package: str,
    command: str,
) -> bool:
    """Identify commands guessed by the legacy GitHub repository crawler."""
    if not server_id.startswith("@github/") or not install_package:
        return False
    full_name = server_id.removeprefix("@github/")
    if full_name != install_package:
        return False
    name = full_name.rsplit("/", 1)[-1]
    return command.strip() in {
        f"npx -y {full_name}",
        f"uvx {name}",
        f"go install {full_name}@latest",
    }
