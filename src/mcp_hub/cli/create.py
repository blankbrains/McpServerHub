"""MCP Server 创建命令 — 交互式项目生成。"""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt

from mcp_hub.core.server_builder import ServerBuilder

console = Console()

# 交互式向导的可用工具列表
AVAILABLE_TOOL_NAMES = ServerBuilder.available_tools()
AVAILABLE_TOOL_DESCRIPTIONS = {
    "hello": "向用户问好",
    "echo": "原样返回输入消息",
    "calculator": "执行数学运算",
    "greet": "生成个性化问候",
    "weather": "获取城市天气信息",
    "memo": "备忘录管理，支持保存和查询笔记",
    "search": "搜索本地文档或记录",
    "translate": "翻译文本到目标语言",
}


def _interactive_wizard(name: str | None) -> tuple[str, str, str, str, list[str]]:
    """交互式向导，收集用户输入。"""
    console.print(Panel.fit(
        "[bold cyan]🛠️  MCP Server Builder[/bold cyan]\n"
        "自动生成生产级 MCP Server 项目骨架",
        border_style="cyan",
    ))

    # 项目名称
    if not name:
        name = Prompt.ask("[bold]项目名称[/bold]", default="my-mcp-server")
    else:
        console.print(f"[dim]项目名称: {name}[/dim]")

    # 语言选择
    console.print("\n[bold]选择语言:[/bold]")
    console.print("  [1] Python 🐍  (推荐，使用官方 mcp SDK)")
    console.print("  [2] TypeScript 📘  (使用 @modelcontextprotocol/sdk)")
    lang_choice = IntPrompt.ask("请输入编号", default=1)
    language = "python" if lang_choice in (1, "1") else "typescript"

    # 描述
    description = Prompt.ask(
        "[bold]项目描述[/bold]",
        default="A MCP Server",
    )

    # 作者
    import os
    default_author = os.environ.get("USER") or os.environ.get("USERNAME") or "developer"
    author = Prompt.ask("[bold]作者[/bold]", default=default_author)

    # 工具选择
    console.print("\n[bold]选择工具模板:[/bold] (默认: hello, echo)")
    console.print(f"  可用工具: {', '.join(AVAILABLE_TOOL_NAMES)}")

    tools_input = Prompt.ask(
        "请输入工具名称（逗号分隔）",
        default="hello, echo",
    )
    tools = [t.strip() for t in tools_input.split(",") if t.strip()]
    # 验证工具名称
    valid_tools = [t for t in tools if t in AVAILABLE_TOOL_NAMES]
    if not valid_tools:
        console.print("[yellow]⚠️  未选择有效工具，使用默认工具[/yellow]")
        valid_tools = ["hello", "echo"]

    # 确认
    console.print("\n[bold]📋 确认信息:[/bold]")
    console.print(f"  名称: {name}")
    console.print(f"  语言: {language}")
    console.print(f"  描述: {description}")
    console.print(f"  作者: {author}")
    console.print(f"  工具: {', '.join(valid_tools)}")

    return name, language, description, author, valid_tools


# ── create ─────────────────────────────────────────────────


@click.command("create")
@click.argument("name", required=False)
@click.option("--language", "-l", type=click.Choice(["python", "typescript"]), help="语言")
@click.option("--description", "-d", help="项目描述")
@click.option("--author", "-a", help="作者")
@click.option("--tools", "-t", help="工具列表（逗号分隔）")
@click.option("--output", "-o", help="输出目录", default=".")
@click.option("--yes", "-y", is_flag=True, help="跳过确认")
def create(
    name: str | None,
    language: str | None,
    description: str | None,
    author: str | None,
    tools: str | None,
    output: str,
    yes: bool,
):
    """交互式创建 MCP Server 项目。

    用法:
      mcp create                         交互式向导
      mcp create my-server               指定名称 + 交互式选择
      mcp create my-server -l python -t hello,echo  完全非交互
      mcp create my-server --language typescript
    """
    async def _run():
        from pathlib import Path

        _proj_name = name
        _proj_lang = language

        # 如果提供了所有参数，跳过交互
        if _proj_name and _proj_lang and tools:
            _tools = [t.strip() for t in tools.split(",")]
            _desc = description or f"MCP Server: {_proj_name}"
            _author = author or "developer"
            _confirm = yes or Confirm.ask(f"\n创建项目 '{_proj_name}'?", default=True)
            if not _confirm:
                console.print("[yellow]已取消[/yellow]")
                return
            _final_name = _proj_name
            _final_lang = _proj_lang
        else:
            _final_name, _final_lang, _desc, _author, _tools = _interactive_wizard(name)

        try:
            builder = ServerBuilder()
            project = builder.create_project(
                name=_final_name,
                language=_final_lang,  # type: ignore
                description=_desc,
                author=_author,
                tools=_tools,
            )

            output_path = Path(output) / _final_name
            if output_path.exists() and not yes and not Confirm.ask(
                f"目录 '{output_path}' 已存在，覆盖?", default=False
            ):
                console.print("[yellow]已取消[/yellow]")
                return

            project.write(Path(output))

            console.print(Panel.fit(
                f"[bold green]✅ MCP Server 项目已创建![/bold green]\n\n"
                f"{project.summary()}\n\n"
                f"[bold]下一步:[/bold]\n"
                f"  cd {output_path}\n"
                f"  {'pip install -e .' if _final_lang == 'python' else 'npm install'}\n"
                f"  {'python -m ' + _final_name.replace('-', '_') if _final_lang == 'python' else 'npm run build'}",  # noqa: E501
                title="🎉 创建成功",
                border_style="green",
            ))

        except ValueError as e:
            console.print(f"[red]❌ 创建失败: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ 创建失败: {type(e).__name__}: {e}[/red]")
            sys.exit(1)

    asyncio.run(_run())
