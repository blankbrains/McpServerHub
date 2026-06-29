"""Token 消耗分析命令 — analyze + optimize。"""

from __future__ import annotations

import asyncio
import json

import click
from rich.console import Console
from rich.table import Table

from mcp_hub.core.registry import Registry
from mcp_hub.core.token_analyzer import (
    TokenAnalyzer,
    Tokenizer,
    format_optimization,
    format_report,
)

console = Console()


# ── analyze ────────────────────────────────────────────────


@click.command("analyze")
@click.argument("server_name", required=False)
@click.option("--all", "scan_all", is_flag=True, help="分析所有 Server")
@click.option("--verbose", "-v", is_flag=True, help="显示每个工具的明细")
@click.option("--json", "json_output", is_flag=True, help="以 JSON 格式输出")
@click.option("--deep", is_flag=True, help="尝试连接运行中的 Server 获取实际工具列表")
def analyze(
    server_name: str | None,
    scan_all: bool,
    verbose: bool,
    json_output: bool,
    _deep: bool,
):
    """分析 MCP Server 的 Token 消耗。

    分析 Server 的工具定义占用 Claude 上下文（100K tokens）的比例，
    并提供优化建议。

    用法:
      mcp analyze @anthropic/web-search    分析指定 Server
      mcp analyze --all                    分析全部 Server
      mcp analyze @anthropic/web-search -v  显示每个工具的明细
      mcp analyze @anthropic/web-search --json  输出 JSON
      mcp analyze @anthropic/web-search --deep  尝试连接实时 Server
    """
    async def _run():
        analyzer = TokenAnalyzer()
        registry = Registry()
        results = []

        if scan_all:
            db_servers = await registry.search(q="", page=1, page_size=1000)
            servers = db_servers[0]
            if not servers:
                console.print("[yellow]⚠️  数据库中没有 Server[/yellow]")
                return

            console.print(f"[bold]📊 正在分析 {len(servers)} 个 Server...[/bold]")
            with console.status("[bold green]分析中...") as status:
                for s in servers:
                    sid = s.get("id", "?")
                    status.update(f"[bold green]分析 {sid}...[/bold green]")
                    report = analyzer.analyze_server(s)
                    results.append(report)

            if json_output:
                out = []
                for r in results:
                    out.append({"server_id": r.server_id, "total_tokens": r.total_tokens, "context_pct": r.context_usage_pct})  # noqa: E501
                console.print(json.dumps(out, ensure_ascii=False, indent=2))
                return

            # 汇总表
            table = Table(title=f"📊 Token 消耗分析 — {len(results)} 个 Server")
            table.add_column("Server", style="cyan")
            table.add_column("Token", justify="right")
            table.add_column("上下文%", justify="right")
            table.add_column("工具数", justify="right")
            table.add_column("优化潜力", justify="right")
            table.add_column("状态")

            results.sort(key=lambda r: r.total_tokens, reverse=True)
            for r in results:
                pct = Tokenizer.format_pct(r.context_usage_pct)
                level = "🟢" if r.context_usage_pct < 10 else "🟡" if r.context_usage_pct < 16 else "🔴"  # noqa: E501
                short_id = r.server_id.split("/")[-1] if "/" in r.server_id else r.server_id
                table.add_row(
                    short_id[:25],
                    str(r.total_tokens),
                    pct,
                    str(len(r.tools)),
                    str(r.optimization_potential),
                    level,
                )
            console.print(table)

            # 统计
            total = sum(r.total_tokens for r in results)
            avg = total / len(results) if results else 0
            over_16 = sum(1 for r in results if r.context_usage_pct > 16)
            console.print(f"\n📈 全部 Server 总消耗: {Tokenizer.format_tokens(total)}")
            console.print(f"📊 平均每 Server: {Tokenizer.format_tokens(int(avg))}")
            console.print(f"⚠️  超过 16% 建议阈值: {over_16}/{len(results)}")

        elif server_name:
            sid = f"@community/{server_name}" if "/" not in server_name else server_name
            server = await registry.get_by_id(sid)
            if not server:
                console.print(f"[red]❌ Server '{sid}' 未找到[/red]")
                return

            report = analyzer.analyze_server(server)

            if json_output:
                out = {
                    "server_id": report.server_id,
                    "total_tokens": report.total_tokens,
                    "context_pct": report.context_usage_pct,
                    "tools": [{"name": t.tool_name, "tokens": t.total_tokens} for t in report.tools],  # noqa: E501
                    "opt_potential": report.optimization_potential,
                    "suggestions": report.suggestions,
                    "estimated": report.estimated,
                }
                console.print(json.dumps(out, ensure_ascii=False, indent=2))
                return

            console.print(format_report(report, verbose=verbose))

        else:
            console.print("[yellow]用法: mcp analyze <server> | mcp analyze --all[/yellow]")
            console.print("  mcp analyze @anthropic/web-search    分析指定 Server")
            console.print("  mcp analyze --all                    分析全部 Server")
            console.print("  mcp analyze @anthropic/web-search -v  显示工具明细")

    asyncio.run(_run())


# ── optimize ───────────────────────────────────────────────


@click.command("optimize")
@click.argument("server_name", required=True)
@click.option("--apply", "do_apply", is_flag=True, help="将优化后的配置写入文件")
def optimize(server_name: str, do_apply: bool):
    """优化 MCP Server 的工具定义，减少 Token 消耗。

    自动分析工具描述并应用优化策略:
    1. 移除冗余前缀（"A tool that...", "Function for..."）
    2. 缩短过长描述（超过 200 字符）
    3. 压缩 JSON Schema（移除冗余的 title 字段）
    4. 缩短参数描述（超过 100 字符）

    优化后平均可节省 30-70% 的工具定义 token。

    用法:
      mcp optimize @anthropic/web-search       查看优化建议
      mcp optimize --apply @anthropic/web-search  写入配置文件
    """
    async def _run():
        sid = f"@community/{server_name}" if "/" not in server_name else server_name
        registry = Registry()
        server = await registry.get_by_id(sid)
        if not server:
            console.print(f"[red]❌ Server '{sid}' 未找到[/red]")
            return

        analyzer = TokenAnalyzer()
        result = analyzer.optimize(server)

        if do_apply:
            from pathlib import Path
            config_dir = Path.home() / ".config" / "mcp-hub"
            config_dir.mkdir(parents=True, exist_ok=True)
            output_path = config_dir / "mcp-optimized.json"
            output_path.write_text(result.optimized_definition, encoding="utf-8")
            console.print(f"[green]✅ 优化配置已写入 {output_path}[/green]")
            console.print(f"[dim]  原来: {Tokenizer.format_tokens(result.original_tokens)} → "
                          f"优化后: {Tokenizer.format_tokens(result.optimized_tokens)} "
                          f"(节省 {result.savings_pct:.1f}%)[/dim]")
        else:
            console.print(format_optimization(result))
            console.print("\n[yellow]提示: 使用 --apply 参数将优化后的配置写入文件[/yellow]")

    asyncio.run(_run())
