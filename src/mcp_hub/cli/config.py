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
            json.load(f)
        ConfigManager()
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


@config.command("sync")
@click.option("--server", "hub_url", default="http://localhost:3987", help="Hub 服务器地址")
@click.option("--agent", default="claude-code", help="目标 Agent (claude-code/cursor/codex/generic)")  # noqa: E501
@click.option("--server-ids", help="要同步的 Server ID 列表（逗号分隔），默认同步所有已安装")
def sync_config(hub_url: str, agent: str, server_ids: str | None):
    """从 Hub 同步配置到本地。

    从 Hub 服务器获取配置，自动写入本地 Agent 配置文件。

    用法:
      mcp config sync                                    # 同步所有已安装
      mcp config sync --server https://hub.example.com   # 指定 Hub 地址
      mcp config sync --agent cursor                     # 同步到 Cursor
      mcp config sync --server-ids @anth/web,@git/hub    # 只同步指定 Server
    """
    async def _run():
        import httpx

        api_base = hub_url.rstrip("/") + "/api/v1"
        _console.print(f"[dim]🔗 连接 Hub: {api_base}[/dim]")

        try:
            if server_ids:
                ids = [s.strip() for s in server_ids.split(",")]
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(f"{api_base}/config/build", json={"servers": ids})
                    if resp.status_code != 200:
                        _console.print(f"[red]❌ Hub 返回错误: {resp.status_code}[/red]")
                        return
                    config = resp.json()
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"{api_base}/config/download")
                    if resp.status_code != 200:
                        _console.print(f"[red]❌ Hub 返回错误: {resp.status_code}[/red]")
                        return
                    config = resp.json()

        except httpx.ConnectError:
            _console.print(f"[red]❌ 无法连接 Hub: {api_base}[/red]")
            _console.print("[yellow]   请确保 Hub 在运行，或使用 --server 指定地址[/yellow]")
            return
        except Exception as e:
            _console.print(f"[red]❌ 同步失败: {e}[/red]")
            return

        # 确定目标路径
        from pathlib import Path
        agent_paths = {
            "claude-code": Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
            "cursor": Path.home() / ".cursor" / "mcp.json",
            "codex": Path.home() / ".codex" / "mcp.json",
            "generic": Path.home() / ".config" / "mcp-hub" / "mcp.json",
        }
        target = agent_paths.get(agent, agent_paths["claude-code"])

        # 写入本地文件
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

        server_count = len(config.get("mcpServers", {})) if isinstance(config, dict) else 0
        _console.print("[green]✅ 配置已同步[/green]")
        _console.print(f"   写入: [bold]{target}[/bold]")
        _console.print(f"   Server: {server_count} 个")

        if agent == "claude-code":
            _console.print("\n[dim]💡 重启 Claude Code 即可生效[/dim]")
        elif agent == "cursor":
            _console.print("\n[dim]💡 重启 Cursor 即可生效[/dim]")

    asyncio.run(_run())
