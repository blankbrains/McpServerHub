"""Distribution contract tests."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib


def test_distribution_exposes_only_unique_cli_command() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as file:
        pyproject = tomllib.load(file)

    assert pyproject["project"]["version"] == "0.3.0"
    assert pyproject["project"]["scripts"] == {
        "mcp-hub": "mcp_hub.cli.app:cli",
    }
