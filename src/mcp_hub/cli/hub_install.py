"""mcp hub-install — 自动检测/安装 MCP Hub + 指定 Server。"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


def _find_mcp() -> str | None:
    """查找 mcp 命令路径。"""
    return shutil.which("mcp")


def _install_mcp() -> bool:
    """安装 MCP Hub CLI。"""
    console.print("[yellow]📦 正在安装 MCP Hub CLI...[/yellow]")

    methods = [
        ([sys.executable, "-m", "pip", "install", "-i",
          "https://pypi.tuna.tsinghua.edu.cn/simple", "mcp-hub"], "pip (清华源)"),
        ([sys.executable, "-m", "pip", "install", "mcp-hub"], "pip"),
        (["pipx", "install", "mcp-hub"], "pipx"),
    ]

    for cmd, label in methods:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                console.print(f"  ✅ [green]通过 {label} 安装成功[/green]")
                return True
        except Exception:
            continue

    return False


@click.command("hub-install")
@click.argument("server_id", required=False)
@click.option("--force", is_flag=True, help="强制重新安装 MCP Hub")
def hub_install(server_id: str | None, force: bool):
    """自动检测/安装 MCP Hub，然后安装指定 Server。

    用法:
      mcp hub-install                                  # 只安装 MCP Hub
      mcp hub-install @org/server-name                 # 安装 Hub + 指定 Server
    """
    async def _run():
        console.print(Panel.fit("[bold blue]🔵 MCP Hub Installer[/bold blue]"))

        # Step 1: Check/Install MCP Hub
        mcp_path = _find_mcp()
        if mcp_path and not force:
            console.print(f"  ✅ [green]MCP Hub 已就绪: {mcp_path}[/green]")
        else:
            if force:
                console.print("[yellow]  --force: 重新安装...[/yellow]")
            ok = _install_mcp()
            if not ok:
                console.print("[red]❌ 安装失败，请手动执行: pip install mcp-hub[/red]")
                return
            # Re-check
            mcp_path = _find_mcp()
            if not mcp_path:
                console.print("[red]❌ 安装后未找到 mcp 命令，请重启终端[/red]")
                return

        # Step 2: Install Server (if specified)
        if server_id:
            console.print(f"\n[yellow]📦 正在安装 {server_id}...[/yellow]")

            # Try via Hub CLI
            try:
                result = subprocess.run(
                    [mcp_path, "install", server_id],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    console.print(f"  ✅ [green]{server_id} 安装成功[/green]")
                    # Show config
                    info = subprocess.run(
                        [mcp_path, "info", server_id],
                        capture_output=True, text=True, timeout=10,
                    )
                    if info.stdout:
                        console.print(info.stdout)
                else:
                    raise Exception(result.stderr[:200])
            except Exception as e:
                # Fallback: generate config snippet
                console.print(f"  ⚠️  Hub 安装失败: {e}")
                console.print("\n[bold cyan]📋 请手动添加配置到 claude_desktop_config.json:[/bold cyan]\n")
                display_name = server_id.split("/")[-1] if "/" in server_id else server_id
                config = {
                    "mcpServers": {
                        display_name: {
                            "command": "npx",
                            "args": ["-y", server_id],
                        }
                    }
                }
                import json
                console.print(json.dumps(config, indent=2, ensure_ascii=False))
                console.print(f"\n[yellow]  配置文件路径:[/yellow]")
                console.print(f"  ~/.config/Claude/claude_desktop_config.json")
                console.print(f"  ~/.cursor/mcp.json")

        console.print(f"\n[bold green]✅ 安装完成！[/bold green]")

    asyncio.run(_run())
