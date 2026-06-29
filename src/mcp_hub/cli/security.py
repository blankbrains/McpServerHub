"""安全扫描命令 — 评分 + 详情。"""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mcp_hub.core.registry import Registry
from mcp_hub.core.security_scanner import ScanFinding, SecurityScanner

console = Console()


@click.command("security")
@click.argument("server_name", required=False)
@click.option("--all", "scan_all", is_flag=True, help="扫描所有 Server")
@click.option("--verbose", "-v", is_flag=True, help="显示详细发现项")
@click.option("--json", "json_output", is_flag=True, help="以 JSON 格式输出")
def security(server_name: str | None, scan_all: bool, verbose: bool, json_output: bool):
    """扫描 MCP Server 的安全性并给出评分。

    四维评分体系:
    - 命令安全(40分) — 安装命令是否安全
    - 包信誉(25分)   — npm/PyPI 包的可信度
    - 发布者(20分)   — 发布者是否可信
    - 代码模式(15分) — 是否存在危险模式

    等级: 🟢 verified(90+) 🟡 reviewed(70+) 🟠 unreviewed(40+) 🔴 blocked(<40)
    """
    async def _run():
        scanner = SecurityScanner()
        registry = Registry()
        results = []

        if scan_all:
            # 从 DB 获取所有 Server
            db_servers = await registry.search(q="", page=1, page_size=1000)
            servers = db_servers[0]
            if not servers:
                console.print("[yellow]⚠️  数据库中没有 Server[/yellow]")
                return
            console.print(f"[bold]🔍 正在扫描 {len(servers)} 个 Server...[/bold]")
            with console.status("[bold green]扫描中...") as status:
                for s in servers:
                    status.update(f"[bold green]扫描 {s.get('id', '?')}...[/bold green]")
                    report = await scanner.scan(s)
                    results.append(report)

            if json_output:
                import json as j
                out = []
                for r in results:
                    out.append({"server_id": r.server_id, "level": r.level, "score": r.score})
                console.print(j.dumps(out, ensure_ascii=False, indent=2))
                return

            # 显示汇总表
            table = Table(title=f"📊 安全扫描报告 — {len(results)} 个 Server")
            table.add_column("Server", style="cyan")
            table.add_column("评分", justify="right")
            table.add_column("等级")
            table.add_column("网络访问", justify="center")
            table.add_column("文件访问", justify="center")
            table.add_column("发现问题")

            # 按分数排序
            results.sort(key=lambda r: r.score)

            for r in results:
                level_icon = {"verified": "🟢", "reviewed": "🟡", "unreviewed": "🟠", "blocked": "🔴"}  # noqa: E501
                icon = level_icon.get(r.level, "❓")
                critical = sum(1 for f in r.findings if f.severity == "critical")
                high = sum(1 for f in r.findings if f.severity == "high")
                issues = f"{critical}🔴{high}🟠" if (critical + high) > 0 else "✅"
                net = "🌐" if r.network_access else "—"
                file_acc = "📁" if r.file_access else "—"
                table.add_row(
                    r.server_id,
                    str(r.score),
                    f"{icon} {r.level}",
                    net,
                    file_acc,
                    issues,
                )
            console.print(table)

            # 统计
            avg_score = sum(r.score for r in results) / len(results)
            stat_safe = sum(1 for r in results if r.score >= 70)
            stat_warn = sum(1 for r in results if r.score < 70)
            stat_danger = sum(1 for r in results if r.score < 40)
            console.print(f"\n📈 平均评分: {avg_score:.1f}/100")
            console.print(f"✅ 安全(>=70): {stat_safe}/{len(results)}")
            console.print(f"⚠️  需关注(<70): {stat_warn}/{len(results)}")
            console.print(f"🔴 危险(<40): {stat_danger}/{len(results)}")

        elif server_name:
            sid = f"@community/{server_name}" if "/" not in server_name else server_name
            server = await registry.get_by_id(sid)
            if not server:
                console.print(f"[red]❌ Server '{sid}' 未找到[/red]")
                return

            report = await scanner.scan(server)

            if json_output:
                import json as j
                out = {
                    "server_id": report.server_id,
                    "score": report.score,
                    "level": report.level,
                    "findings": [
                        {"severity": f.severity, "title": f.title, "impact": f.score_impact}
                        for f in report.findings
                    ],
                }
                console.print(j.dumps(out, ensure_ascii=False, indent=2))
                return

            # 显示报告
            level_icons = {"verified": "🟢", "reviewed": "🟡", "unreviewed": "🟠", "blocked": "🔴"}  # noqa: E501
            icon = level_icons.get(report.level, "❓")
            color = "green" if report.score >= 70 else "red"
            console.print(Panel.fit(
                f"[bold]{icon} 安全评分: {report.score}/100[/bold] — [{color}]{report.level}[/]",
                title=f"🔒 {sid}",
            ))

            if report.findings:
                # 按严重程度分组
                critical_f = [f for f in report.findings if f.severity == "critical"]
                high_f = [f for f in report.findings if f.severity == "high"]
                suspicious_f = [f for f in report.findings if f.severity == "suspicious"]
                info_f = [f for f in report.findings if f.severity == "info"]

                if critical_f:
                    _print_findings(critical_f, "🔴 严重问题", "red")
                if high_f:
                    _print_findings(high_f, "🟠 高危", "orange3")
                if suspicious_f:
                    _print_findings(suspicious_f, "🟡 可疑", "yellow")
                if info_f:
                    _print_findings(info_f, "ℹ️ 信息", "blue")

            # 评分明细（仅 -v 时显示）
            if verbose:
                breakdown = report.score_breakdown()
                score_table = Table(title="📊 评分明细")
                score_table.add_column("维度", style="cyan")
                score_table.add_column("得分", justify="right")
                score_table.add_column("满分", justify="right")
                dim_names = {
                    "command_safety": "命令安全",
                    "package_reputation": "包信誉",
                    "publisher_trust": "发布者信任",
                    "code_patterns": "代码模式",
                }
                max_scores = {"command_safety": 40, "package_reputation": 25, "publisher_trust": 20, "code_patterns": 15}  # noqa: E501
                for dim, name in dim_names.items():
                    score_table.add_row(name, str(breakdown[dim]), str(max_scores[dim]))
                console.print(score_table)

        else:
            console.print("[yellow]用法: mcp security <server> | mcp security --all[/yellow]")
            console.print("  mcp security @anthropic/web-search    扫描指定 Server")
            console.print("  mcp security --all                   扫描全部 Server")
            console.print("  mcp security @anthropic/web-search -v 显示详情")

    asyncio.run(_run())


def _print_findings(findings: list[ScanFinding], title: str, style: str):
    """打印一组发现项。"""
    console.print(f"\n[bold {style}]{title} ({len(findings)} 项)[/bold {style}]")
    for f in findings:
        impact_str = f" [{f.score_impact:+d}分]" if f.score_impact != 0 else ""
        console.print(f"  • {f.title}{impact_str}")
        console.print(f"    [dim]{f.description}[/dim]")


if __name__ == "__main__":
    security()
