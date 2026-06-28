"""mcp quickstart — 零配置一键启动（适用 SQLite）。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command("quickstart")
@click.option("--port", default=3987, type=int, help="监听端口")
def quickstart(port: int):
    """🚀 零配置启动 MCP Server Hub（30 秒上线）。"""
    async def _run():
        console.print(Panel.fit(
            "[bold blue]🔵 MCP Server Hub Quickstart[/bold blue]\n"
            "零配置模式 · 使用 SQLite · 无需 PostgreSQL",
        ))

        config_dir = Path.home() / ".config" / "mcp-hub"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "logs").mkdir(exist_ok=True)

        # 生成 .env
        env_path = config_dir / ".env"
        secret = os.urandom(32).hex()
        env_content = f"""# MCP Server Hub Quickstart 配置
MCP_HUB_DATABASE_URL=sqlite+aiosqlite:///{config_dir}/mcp-hub.db
MCP_HUB_SECRET={secret}
MCP_HUB_HOST=0.0.0.0
MCP_HUB_PORT={port}
MCP_HUB_CORS_ORIGINS=*
MCP_HUB_WORKERS=1
"""
        env_path.write_text(env_content)
        console.print("  ✅ [green]配置文件已生成[/green]")

        # 初始化数据库
        try:
            from mcp_hub.db.database import init_db
            await init_db()
            console.print("  ✅ [green]数据库已初始化 (SQLite)[/green]")
        except Exception as e:
            console.print(f"  ❌ [red]数据库初始化失败: {e}[/red]")
            return

        # 启动
        import uvicorn

        from mcp_hub.api.app import create_app

        app = create_app(dev=True)
        console.print("\n[bold green]🎉 MCP Server Hub 已启动！[/bold green]")
        console.print(f"  📍 Dashboard: [underline]http://localhost:{port}[/underline]")
        console.print(f"  📚 Market:    [underline]http://localhost:{port}/market[/underline]")
        console.print(f"  📖 API Docs:  [underline]http://localhost:{port}/docs[/underline]")
        console.print("  🔌 MCP Gateway: [bold]mcp serve[/bold]")
        console.print("\n[yellow]按 Ctrl+C 停止[/yellow]\n")

        uvicorn.run(app, host="0.0.0.0", port=port)

    asyncio.run(_run())
