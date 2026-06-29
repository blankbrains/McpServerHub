"""质量监控命令 — monitor + reliability。"""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from mcp_hub.core.monitor import Monitor
from mcp_hub.core.registry import Registry

console = Console()


# ── monitor ────────────────────────────────────────────────


@click.command("monitor")
@click.argument("server_name", required=False)
@click.option("--all", "scan_all", is_flag=True, help="监控所有已安装 Server")
@click.option("--watch", is_flag=True, help="持续监控（每 10 秒刷新）")
def monitor(server_name: str | None, scan_all: bool, watch: bool):
    """查看 MCP Server 的健康状态与可靠性。

    显示 Server 的:
    - 当前运行状态
    - 可靠性评分 (0-100)
    - 24小时内 uptime 百分比
    - 平均响应时间
    - 历史 uptime (1h/24h/7d/30d)

    用法:
      mcp monitor @anthropic/web-search    查看指定 Server
      mcp monitor --all                    查看所有 Server
      mcp monitor --watch                  持续刷新
    """
    async def _run():
        if scan_all:
            await _show_all_monitor()
        elif server_name:
            sid = f"@community/{server_name}" if "/" not in server_name else server_name
            while True:
                await _show_server_monitor(sid)
                if not watch:
                    break
                await asyncio.sleep(10)
        else:
            console.print("[yellow]用法: mcp monitor <server> | mcp monitor --all[/yellow]")
            console.print("  mcp monitor @anthropic/web-search    查看 Server 健康")
            console.print("  mcp monitor --all                    查看全部")
            console.print("  mcp monitor @anthropic/web-search --watch  持续刷新")

    asyncio.run(_run())


async def _show_server_monitor(server_id: str):
    """显示单个 Server 的监控数据。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        console.print(f"[red]❌ Server '{server_id}' 未找到[/red]")
        return

    display_name = server_id.split("/")[-1]
    from mcp_hub.core.process_manager import get_process_manager
    pm = get_process_manager()
    running = pm.is_running(server_id)
    status_icon = "🟢" if running else "⏹"

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:  # noqa: E501
        p.add_task(f"🔍 正在获取 {display_name} 监控数据...", total=None)
        report = await Monitor.calculate_reliability(server_id)

    level_icon = "🟢" if report.reliability_score >= 90 else "🟡" if report.reliability_score >= 60 else "🔴"  # noqa: E501
    console.print(Panel.fit(
        f"[bold]{level_icon} 可靠性评分: {report.reliability_score}/100[/bold]  "
        f"{status_icon} {'运行中' if running else '已停止'}",
        title=f"📊 {display_name}",
    ))

    # Uptime 表
    if report.uptime_stats:
        table = Table(title="📈 Uptime 统计")
        table.add_column("时间窗口", style="cyan")
        table.add_column("检查次数", justify="right")
        table.add_column("通过次数", justify="right")
        table.add_column("Uptime", justify="right")
        table.add_column("平均响应", justify="right")
        for u in report.uptime_stats:
            color = "green" if u.uptime_pct >= 99 else "yellow" if u.uptime_pct >= 95 else "red"
            table.add_row(
                u.window,
                str(u.total_checks),
                str(u.passed_checks),
                f"[{color}]{u.uptime_pct}%[/{color}]",
                f"{u.avg_response_time_ms:.0f}ms" if u.avg_response_time_ms > 0 else "-",
            )
        console.print(table)

    # 摘要
    if report.total_checks_recorded > 0:
        status = report.last_check_status or "未知"
        console.print(f"  总检查次数: {report.total_checks_recorded}")
        console.print(f"  最近检查:   {report.last_check_at or '无'}")
        console.print(f"  最近状态:   {status}")

    if report.recent_errors:
        console.print(f"\n[red]⚠️  近期错误 ({len(report.recent_errors)} 条):[/red]")
        for err in report.recent_errors[:3]:
            console.print(f"  [dim]{err[:80]}[/dim]")

    _display_name_short = server_id.split("/")[-1] if "/" in server_id else server_id


async def _show_all_monitor():
    """显示所有 Server 的健康概况。"""
    registry = Registry()
    db_servers = await registry.search(q="", page=1, page_size=1000)
    servers = db_servers[0]
    if not servers:
        console.print("[yellow]⚠️  没有 Server 数据[/yellow]")
        return

    summary = await Monitor.get_summary_stats()

    console.print(Panel.fit(
        f"[bold]📊 监控概览[/bold]\n"
        f"  Server 总数: {summary['total_servers']}\n"
        f"  运行中:      {summary['running']}\n"
        f"  健康检查:    {summary['total_health_checks']} 条记录\n"
        f"  24h 错误:    {summary['errors_last_24h']} 次",
        title="系统状态",
    ))

    console.print(f"\n[bold]🔍 正在获取 {len(servers)} 个 Server 的健康数据...[/bold]")

    table = Table(title="📋 Server 健康状态")
    table.add_column("Server", style="cyan")
    table.add_column("状态")
    table.add_column("可靠性评分", justify="right")
    table.add_column("Uptime 24h", justify="right")
    table.add_column("响应时间", justify="right")
    table.add_column("运行中")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:  # noqa: E501
        for s in servers:
            sid = s["id"]
            p.add_task(f"  检查 {sid}...", total=None)
            health = await Monitor.get_server_health(sid)
            level_icon = "🟢" if health.reliability_score >= 90 else "🟡" if health.reliability_score >= 60 else "🔴"  # noqa: E501
            table.add_row(
                sid[:28],
                f"{level_icon} {health.status}",
                str(health.reliability_score),
                f"{health.uptime_24h:.1f}%" if health.uptime_24h > 0 else "-",
                f"{health.avg_response_ms:.0f}ms" if health.avg_response_ms > 0 else "-",
                "🟢" if health.running else "⏹",
            )

    console.print(table)


# ── reliability ────────────────────────────────────────────


@click.command("reliability")
@click.option("--limit", default=20, help="显示数量")
@click.option("--json", "json_output", is_flag=True, help="JSON 输出")
def reliability(limit: int, json_output: bool):
    """查看最稳定 MCP Server 排行榜。

    基于历史健康检查数据计算可靠性评分 (0-100)，按评分降序排列。
    """
    async def _run():
        console.print("[bold]📊 正在计算 Server 可靠性评分...[/bold]")
        top = await Monitor.get_top_reliable(limit=limit)

        if not top:
            console.print("[yellow]📭 暂无可靠性数据[/yellow]")
            return

        if json_output:
            import json
            out = [
                {
                    "server_id": s.server_id,
                    "reliability_score": s.reliability_score,
                    "uptime_24h": s.uptime_24h,
                    "status": s.status,
                }
                for s in top
            ]
            console.print(json.dumps(out, ensure_ascii=False, indent=2))
            return

        table = Table(title=f"🏆 最稳定 Server Top {len(top)}")
        table.add_column("排名", justify="right", style="dim")
        table.add_column("Server", style="cyan")
        table.add_column("评分", justify="right")
        table.add_column("24h Uptime", justify="right")
        table.add_column("响应时间", justify="right")
        table.add_column("状态")

        for i, s in enumerate(top, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}")
            level_icon = "🟢" if s.reliability_score >= 90 else "🟡" if s.reliability_score >= 60 else "🔴"  # noqa: E501
            table.add_row(
                medal,
                s.server_id[:28],
                f"{s.reliability_score}",
                f"{s.uptime_24h:.1f}%",
                f"{s.avg_response_ms:.0f}ms",
                f"{level_icon} {s.status}",
            )
        console.print(table)

    asyncio.run(_run())
