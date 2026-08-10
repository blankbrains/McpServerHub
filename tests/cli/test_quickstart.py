from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

from click.testing import CliRunner

from mcp_hub.cli import quickstart as quickstart_module
from mcp_hub.cli.quickstart import _prepare_quickstart_environment, quickstart


def test_prepare_quickstart_environment_uses_local_sqlite(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for key in list(os.environ):
        if key.startswith("MCP_HUB_"):
            monkeypatch.delenv(key, raising=False)

    env_path = _prepare_quickstart_environment(tmp_path / "mcp-hub", 3999)

    assert env_path.exists()
    assert os.environ["MCP_HUB_DATABASE_URL"].startswith("sqlite+aiosqlite:///")
    assert os.environ["MCP_HUB_DATABASE_URL"].endswith("/mcp-hub.db")
    assert os.environ["MCP_HUB_HOST"] == "127.0.0.1"
    assert os.environ["MCP_HUB_PORT"] == "3999"
    assert os.environ["MCP_HUB_SKIP_DOTENV"] == "1"
    assert os.environ["MCP_HUB_GITHUB_CLIENT_ID"] == "quickstart-local"

    content = env_path.read_text(encoding="utf-8")
    assert "MCP_HUB_SKIP_DOTENV" not in content
    assert "MCP_HUB_DATABASE_URL=sqlite+aiosqlite:///" in content

    original_secret = os.environ["MCP_HUB_SECRET"]
    monkeypatch.delenv("MCP_HUB_SECRET")
    _prepare_quickstart_environment(tmp_path / "mcp-hub", 3999)
    assert os.environ["MCP_HUB_SECRET"] == original_secret


def test_quickstart_starts_uvicorn_outside_database_event_loop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_module = ModuleType("mcp_hub.db.database")

    async def init_db() -> None:
        return None

    database_module.init_db = init_db  # type: ignore[attr-defined]

    app_module = ModuleType("mcp_hub.api.app")
    app = object()

    def create_app(dev: bool = False) -> object:
        del dev
        return app

    app_module.create_app = create_app  # type: ignore[attr-defined]

    uvicorn_module = ModuleType("uvicorn")
    calls: list[tuple[object, str, int]] = []
    uvicorn_module.run = (  # type: ignore[attr-defined]
        lambda target, host, port: calls.append((target, host, port))
    )

    monkeypatch.setitem(sys.modules, "mcp_hub.db.database", database_module)
    monkeypatch.setitem(sys.modules, "mcp_hub.api.app", app_module)
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn_module)

    def prepare_environment(config_dir: Path, port: int) -> Path:
        del config_dir, port
        return tmp_path / ".env"

    monkeypatch.setattr(
        quickstart_module,
        "_prepare_quickstart_environment",
        prepare_environment,
    )

    result = CliRunner().invoke(quickstart, ["--port", "3999"])

    assert result.exit_code == 0, result.output
    assert calls == [(app, "127.0.0.1", 3999)]
