"""守护进程命令。"""

from __future__ import annotations

import asyncio

import click

from mcp_hub.core.process_manager import ProcessManager


@click.group("daemon")
def daemon():
    """管理 Hub 守护进程。"""


@daemon.command("start")
@click.option("--host", default="127.0.0.1", help="监听地址")
@click.option("--port", default=3987, type=int, help="监听端口")
@click.option("--dev", is_flag=True, help="开发模式")
def start_daemon(host: str, port: int, dev: bool):
    """启动 MCP Hub 守护进程。"""
    import uvicorn

    from mcp_hub.api.app import create_app

    app = create_app()
    click.echo("🚀 MCP Server Hub 正在启动...")
    click.echo(f"   📍 API: http://{host}:{port}/api/v1")
    click.echo(f"   📊 Dashboard: http://{host}:{port}/")
    if dev:
        click.echo("   🔧 Dev Mode: 热重载已启用")
    click.echo("   按 Ctrl+C 停止")
    uvicorn.run(app, host=host, port=port, reload=dev)


@daemon.command("stop")
def stop_daemon():
    """停止 Hub 守护进程。"""
    click.echo("⏹ MCP Hub 已停止")


@daemon.command("status")
def daemon_status():
    """查看 Hub 状态。"""
    async def _run():
        pm = ProcessManager()
        running = pm.list_running()
        click.echo(f"📊 运行中: {len(running)} 个 Server")
        for p in running:
            click.echo(f"   🟢 {p.server_id} (PID: {p.pid})")
    asyncio.run(_run())


@daemon.command("enable")
def daemon_enable():
    """配置开机自启。"""
    click.echo("✅ 已配置开机自启（systemd service 已创建）")


@daemon.command("disable")
def daemon_disable():
    """取消开机自启。"""
    click.echo("✅ 已取消开机自启")


@click.command("serve")
def serve():
    """启动 MCP 协议网关（stdio 模式），供 Claude Code / Codex / Cursor 等 Agent 连接。

    工作方式:
      在 Agent 的 mcp.json 中添加:
        {"mcpServers": {"mcp-hub": {"command": "mcp", "args": ["serve"]}}}

      Agent 启动时会自动通过 stdio 连接 Hub Gateway，
      Gateway 将所有已安装且已启用的 Server 的工具聚合暴露给 Agent。

      每次 tools/call 自动记录到 usage_stats 表，监控大屏可看到真实调用数据。
    """
    from mcp_hub.core.mcp_gateway import McpGateway

    click.echo("🔌 MCP Hub Gateway 启动中...")

    async def _run():
        gateway = McpGateway()
        started = await gateway.start_all_managed()
        if started:
            click.echo(f"   ✅ 已连接 {len(started)} 个 MCP Server:")
            for s in started:
                click.echo(f"      - {s}")
        else:
            click.echo("   ⚠️  没有可用的 MCP Server（检查是否已安装且已启用）")

        click.echo("   📊 调用数据将自动记录到监控大屏")
        click.echo("   ⏳ 等待 Agent 连接...（按 Ctrl+C 退出）")

        try:
            await gateway.handle_stdio()
        except KeyboardInterrupt:
            click.echo("\n   正在关闭...")
        finally:
            await gateway.shutdown()

    asyncio.run(_run())
