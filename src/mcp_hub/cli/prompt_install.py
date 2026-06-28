"""mcp prompt-install — 生成安装提示词，用户可直接发给 AI 执行。"""

from __future__ import annotations

import json
import shutil

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# 常用 MCP Server 别名映射
ALIASES = {
    "filesystem": "@modelcontextprotocol/server-filesystem",
    "github": "@modelcontextprotocol/server-github",
    "postgres": "@modelcontextprotocol/server-postgres",
    "slack": "@modelcontextprotocol/server-slack",
    "memory": "@modelcontextprotocol/server-memory",
    "puppeteer": "@modelcontextprotocol/server-puppeteer",
    "sqlite": "@modelcontextprotocol/server-sqlite",
    "maps": "@modelcontextprotocol/server-google-maps",
    "redis": "@modelcontextprotocol/server-redis",
    "web-search": "@anthropic/mcp-server-web-search",
    "search": "@anthropic/mcp-server-web-search",
    "translate": "@community/server-translate",
    "weather": "@community/server-weather",
    "docker": "@community/server-docker",
    "s3": "@community/server-s3",
    "ssh": "@community/server-ssh",
    "mongodb": "@community/server-mongodb",
    "email": "@community/server-email",
}


def _resolve_alias(name: str) -> str:
    """解析别名或直接返回 Server ID。"""
    if name.startswith("@") or "/" in name:
        return name
    return ALIASES.get(name, name)


def _check_hub_installed() -> bool:
    """检查 mcp 命令是否可用。"""
    return shutil.which("mcp") is not None


@click.command("prompt-install")
@click.argument("server_id", required=True)
@click.option("--copy", is_flag=True, help="自动复制到剪贴板")
@click.option("--json-output", "json_out", is_flag=True, help="JSON 格式输出")
def prompt_install(server_id: str, copy: bool, json_out: bool):
    """生成安装提示词 — 发给 AI 即可自动安装。

    用法:
      mcp prompt-install filesystem          # 用别名
      mcp prompt-install @org/server-name    # 用完整 ID
    """
    resolved = _resolve_alias(server_id)
    is_installed = _check_hub_installed()

    if json_out:
        result = {
            "server_id": resolved,
            "hub_installed": is_installed,
            "prompt": _generate_prompt(resolved, is_installed),
        }
        console.print_json(json.dumps(result, ensure_ascii=False))
        return

    # Display
    console.print(Panel.fit(
        "[bold blue]🔵 安装提示词生成器[/bold blue]\n"
        f"Server: {resolved}\n"
        f"MCP Hub: {'✅ 已安装' if is_installed else '❌ 未安装'}",
    ))

    console.print("\n[bold]📋 复制以下提示词发给 AI：[/bold]\n")

    prompt = _generate_prompt(resolved, is_installed)

    console.print(Panel(
        prompt,
        border_style="cyan",
        title="安装提示词",
        title_align="left",
    ))

    if copy:
        try:
            import pyperclip
            pyperclip.copy(prompt)
            console.print("\n[green]✅ 已复制到剪贴板[/green]")
        except ImportError:
            console.print("\n[yellow]⚠️  未安装 pyperclip，请手动复制[/yellow]")

    # Also show the manual equivalent
    console.print("\n[dim]等效命令（手动执行）:[/dim]")
    if not is_installed:
        console.print(f"  pip install mcp-hub")
    console.print(f"  mcp install {resolved}")


def _generate_prompt(server_id: str, hub_installed: bool) -> str:
    """生成安装提示词。"""
    if hub_installed:
        prompt = (
            f"请先检查是否已安装 MCP Hub 商店，"
            f"若未安装，请根据 https://mcphub.cn/install/skillhub.md 安装 MCP Hub 商店，"
            f"但是只安装 CLI，"
            f"然后安装 {server_id}。"
            f"若已安装，则直接安装 {server_id}。"
        )
    else:
        prompt = (
            f"请先检查是否已安装 MCP Hub 商店，"
            f"若未安装，请根据 https://mcphub.cn/install/skillhub.md 安装 MCP Hub 商店，"
            f"但是只安装 CLI，"
            f"然后安装 {server_id}。"
            f"若已安装，则直接安装 {server_id}。"
        )
    return prompt
