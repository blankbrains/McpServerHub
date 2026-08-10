"""CLI entry-point encoding regression tests."""

from __future__ import annotations

import os
import subprocess
import sys


def test_help_does_not_crash_in_strict_gbk_console() -> None:
    environment = {
        **os.environ,
        "PYTHONIOENCODING": "gbk:strict",
        "MCP_HUB_DATABASE_URL": "sqlite+aiosqlite:///F:/tmp/mcp-hub-cli-help.db",
        "MCP_HUB_SECRET": "cli-help-test-secret-at-least-32-characters",
        "MCP_HUB_GITHUB_CLIENT_ID": "test-client",
        "MCP_HUB_GITHUB_CLIENT_SECRET": "test-secret",
    }

    result = subprocess.run(
        [sys.executable, "-m", "mcp_hub.cli.app", "--help"],
        check=False,
        capture_output=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr.decode("gbk", errors="replace")
    assert b"Usage:" in result.stdout
