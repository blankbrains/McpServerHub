"""守护进程命令。"""

from __future__ import annotations

import asyncio
import os
import subprocess as sp
import sys
import time
from pathlib import Path

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

    # 写入 PID 文件供 stop 命令使用
    pid_file = Path.home() / ".config" / "mcp-hub" / "daemon.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))

    app = create_app()
    click.echo("🚀 MCP Server Hub 正在启动...")
    click.echo(f"   📍 API: http://{host}:{port}/api/v1")
    click.echo(f"   📊 Dashboard: http://{host}:{port}/")
    if dev:
        click.echo("   🔧 Dev Mode: 热重载已启用")
    click.echo("   按 Ctrl+C 停止")
    try:
        uvicorn.run(app, host=host, port=port, reload=dev)
    finally:
        pid_file.unlink(missing_ok=True)


@daemon.command("stop")
def stop_daemon():
    """停止 Hub 守护进程。"""
    pid_file = Path.home() / ".config" / "mcp-hub" / "daemon.pid"

    if not pid_file.exists():
        click.echo("⚠️  守护进程未运行（PID 文件不存在）")
        return

    try:
        pid = int(pid_file.read_text().strip())
        # 尝试优雅终止
        sp.run(["kill", "-TERM", str(pid)], capture_output=True)
        time.sleep(1)
        # 检查进程是否还在运行
        check = sp.run(["kill", "-0", str(pid)], capture_output=True)
        if check.returncode != 0:
            pid_file.unlink(missing_ok=True)
            click.echo("⏹ MCP Hub 已停止")
        else:
            click.echo("⚠️  进程未响应 TERM 信号，使用 KILL 强制终止...")
            sp.run(["kill", "-KILL", str(pid)], capture_output=True)
            pid_file.unlink(missing_ok=True)
            click.echo("⏹ MCP Hub 已强制停止")
    except ValueError:
        pid_file.unlink(missing_ok=True)
        click.echo("⚠️  PID 文件无效，已清理")
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        click.echo("⚠️  进程已不存在，PID 文件已清理")
    except Exception as e:
        click.echo(f"❌ 停止失败: {e}")


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
    username = os.environ.get("USER", os.environ.get("USERNAME", "root"))
    exec_start = (
        f"{sys.executable} -m uvicorn mcp_hub.api.app:create_app "
        "--host 0.0.0.0 --port 3987 --workers 2"
    )
    service_content = f"""[Unit]
Description=MCP Server Hub Daemon
After=network.target

[Service]
Type=simple
User={username}
WorkingDirectory={os.getcwd()}
ExecStart={exec_start}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_path = service_dir / "mcp-hub.service"
    service_path.write_text(service_content)

    # 尝试通过 systemctl 启用
    result = sp.run(
        ["systemctl", "--user", "enable", "mcp-hub.service"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo("✅ 已配置开机自启（systemd user service 已创建并启用）")
    else:
        click.echo(f"✅ 已创建 service 文件: {service_path}")
        click.echo("   手动启用: systemctl --user enable mcp-hub.service")


@daemon.command("disable")
def daemon_disable():
    """取消开机自启。"""
    result = sp.run(
        ["systemctl", "--user", "disable", "mcp-hub.service"],
        capture_output=True,
        text=True,
    )
    service_path = Path.home() / ".config" / "systemd" / "user" / "mcp-hub.service"
    if service_path.exists():
        service_path.unlink()

    if result.returncode == 0:
        click.echo("✅ 已取消开机自启")
    else:
        click.echo("✅ 已取消开机自启（service 文件已移除）")


@click.command("serve")
def serve():
    """启动 MCP 协议网关（stdio 模式），供 Claude Code / Codex / Cursor 等 Agent 连接。

    工作方式:
      在 Agent 的 mcp.json 中添加:
        {"mcpServers": {"mcp-hub": {"command": "mcp", "args": ["serve"]}}}

      Agent 启动时会自动通过 stdio 连接 Hub Gateway，
      Gateway 将所有已安装且已启用的 Server 的工具聚合暴露给 Agent。

      每次 tools/call 自动记录到 usage_stats 表，监控大屏可看到真实调用数据。

      远程上报（可选）：
        设置环境变量后，调用数据自动上报到远程 Hub：
          MCP_HUB_REPORT_URL=http://your-hub:3987
          MCP_HUB_USER_ID=your-github-username
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
