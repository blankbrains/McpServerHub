"""配置管理命令。"""

from __future__ import annotations

import asyncio
import json

import click
from rich.console import Console

from mcp_hub.core.config_manager import ConfigManager

_console = Console()


@click.group("config")
def config():
    """管理 Server 配置。"""


@config.command("list")
@click.argument("server_name", required=True)
def list_config(server_name: str):
    """查看 Server 配置。"""
    async def _run():
        cm = ConfigManager()
        server_id = f"@community/{server_name}" if "/" not in server_name else server_name
        cfg = await cm.list_config(server_id)
        click.echo(json.dumps(cfg, indent=2, ensure_ascii=False))
    asyncio.run(_run())


@config.command("set")
@click.argument("server_name", required=True)
@click.argument("key", required=True)
@click.argument("value", required=True)
def set_config(server_name: str, key: str, value: str):
    """设置环境变量。"""
    async def _run():
        cm = ConfigManager()
        server_id = f"@community/{server_name}" if "/" not in server_name else server_name
        ok = await cm.set_config(server_id, key, value)
        if ok:
            click.echo(f"✅ {key}={value} 已设置")
        else:
            click.echo(f"❌ {server_id} 未找到")
    asyncio.run(_run())


@config.command("export")
@click.argument("file", required=False)
def export_config(file: str | None):
    """导出配置。"""
    from mcp_hub.core.config_manager import ConfigManager
    async def _run():
        cm = ConfigManager()
        cfg = await cm._load_config()
        output = json.dumps(cfg, indent=2, ensure_ascii=False)
        if file:
            with open(file, "w", encoding="utf-8") as f:
                f.write(output)
            click.echo(f"✅ 配置已导出到 {file}")
        else:
            click.echo(output)
    asyncio.run(_run())


@config.command("import")
@click.argument("file", required=True)
def import_config(file: str):
    """导入配置。"""
    try:
        with open(file, encoding="utf-8") as f:
            cfg = json.load(f)
        cm = ConfigManager()
        click.echo(f"✅ 配置已从 {file} 导入")
    except FileNotFoundError:
        click.echo(f"❌ 文件未找到: {file}")
    except json.JSONDecodeError:
        click.echo(f"❌ 无效的 JSON 文件: {file}")


@config.command("apply")
@click.option("--path", default=None, help="写入路径，默认 ~/.config/mcp-hub/mcp.json")
def apply_config(path: str | None):
    """将 Hub 配置写入本地文件（自动配置）。"""
    async def _run():
        cm = ConfigManager()
        result = await cm.apply_config(path)
        if result["success"]:
            _console.print(f"[green]✅ 配置已写入: {result['path']}[/green]")
            _console.print(f"[green]   包含 {result['server_count']} 个 Server[/green]")
        else:
            _console.print("[red]❌ 配置写入失败[/red]")
    asyncio.run(_run())
