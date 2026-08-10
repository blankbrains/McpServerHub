"""mcp-hub quickstart — 零配置一键启动（适用 SQLite）。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


def _read_existing_environment(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _prepare_quickstart_environment(config_dir: Path, port: int) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "logs").mkdir(exist_ok=True)

    env_path = config_dir / ".env"
    existing_env = _read_existing_environment(env_path)
    database_url = f"sqlite+aiosqlite:///{(config_dir / 'mcp-hub.db').as_posix()}"
    secret = (
        os.getenv("MCP_HUB_SECRET")
        or existing_env.get("MCP_HUB_SECRET")
        or os.urandom(32).hex()
    )
    github_client_id = (
        os.getenv("MCP_HUB_GITHUB_CLIENT_ID")
        or existing_env.get("MCP_HUB_GITHUB_CLIENT_ID")
        or "quickstart-local"
    )
    github_client_secret = (
        os.getenv("MCP_HUB_GITHUB_CLIENT_SECRET")
        or existing_env.get("MCP_HUB_GITHUB_CLIENT_SECRET")
        or os.urandom(24).hex()
    )
    redirect_uri = (
        os.getenv("MCP_HUB_GITHUB_REDIRECT_URI")
        or existing_env.get("MCP_HUB_GITHUB_REDIRECT_URI")
        or f"http://localhost:{port}/api/v1/auth/callback"
    )
    runtime_env = {
        "MCP_HUB_DATABASE_URL": database_url,
        "MCP_HUB_SECRET": secret,
        "MCP_HUB_GITHUB_CLIENT_ID": github_client_id,
        "MCP_HUB_GITHUB_CLIENT_SECRET": github_client_secret,
        "MCP_HUB_GITHUB_REDIRECT_URI": redirect_uri,
        "MCP_HUB_HOST": "127.0.0.1",
        "MCP_HUB_PORT": str(port),
        "MCP_HUB_CORS_ORIGINS": f"http://localhost:{port}",
        "MCP_HUB_WORKERS": "1",
        "MCP_HUB_SKIP_DOTENV": "1",
    }
    os.environ.update(runtime_env)

    env_content = "\n".join(
        [
            "# MCP Server Hub Quickstart 配置",
            *(
                f"{key}={value}"
                for key, value in runtime_env.items()
                if key != "MCP_HUB_SKIP_DOTENV"
            ),
            "",
        ]
    )
    env_path.write_text(env_content, encoding="utf-8")
    return env_path


@click.command("quickstart")
@click.option("--port", default=3987, type=int, help="监听端口")
def quickstart(port: int) -> None:
    """🚀 零配置启动 MCP Server Hub（30 秒上线）。"""
    console.print(
        Panel.fit(
            "[bold blue]🔵 MCP Server Hub Quickstart[/bold blue]\n"
            "零配置模式 · 使用 SQLite · 无需 PostgreSQL",
        )
    )

    config_dir = Path.home() / ".config" / "mcp-hub"
    _prepare_quickstart_environment(config_dir, port)
    console.print("  ✅ [green]配置文件已生成[/green]")

    # 初始化数据库
    try:
        from mcp_hub.db.database import init_db

        asyncio.run(init_db())
        console.print("  ✅ [green]数据库已初始化 (SQLite)[/green]")
    except Exception as e:
        console.print(f"  ❌ [red]数据库初始化失败: {e}[/red]")
        return

    # Uvicorn 管理自己的事件循环，不能在 asyncio.run() 内再次启动。
    import uvicorn

    from mcp_hub.api.app import create_app

    app = create_app(dev=True)
    console.print("\n[bold green]🎉 MCP Server Hub 已启动！[/bold green]")
    console.print(f"  📍 Dashboard: [underline]http://localhost:{port}[/underline]")
    console.print(f"  📚 Market:    [underline]http://localhost:{port}/market[/underline]")
    console.print(f"  📖 API Docs:  [underline]http://localhost:{port}/docs[/underline]")
    console.print("  🔌 MCP Gateway: [bold]mcp-hub serve[/bold]")
    console.print("\n[yellow]按 Ctrl+C 停止[/yellow]\n")

    uvicorn.run(app, host="127.0.0.1", port=port)
