"""Distribution contract tests."""

from __future__ import annotations

import json
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from mcp_hub import __version__


def test_distribution_exposes_only_unique_cli_command() -> None:
    root = Path(__file__).parents[1]
    pyproject_path = root / "pyproject.toml"
    with pyproject_path.open("rb") as file:
        pyproject = tomllib.load(file)
    web_package = json.loads(
        (root / "src" / "mcp_hub" / "web" / "package.json").read_text(encoding="utf-8")
    )
    web_lock = json.loads(
        (root / "src" / "mcp_hub" / "web" / "package-lock.json").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["version"] == __version__ == "0.3.1"
    assert web_package["version"] == __version__
    assert web_lock["version"] == __version__
    assert web_lock["packages"][""]["version"] == __version__
    assert pyproject["project"]["scripts"] == {
        "mcp-hub": "mcp_hub.cli.app:cli",
    }
