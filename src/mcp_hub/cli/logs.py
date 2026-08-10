"""日志查看命令。"""

from __future__ import annotations

from pathlib import Path

import click


def safe_log_path(log_dir: str, server_id: str) -> Path:
    """安全构造日志文件路径，防止路径遍历攻击。"""
    safe_name = "".join(c for c in server_id if c.isalnum() or c in "_-")
    if not safe_name:
        raise ValueError(f"无效的 server_id: {server_id}")
    log_file = Path(log_dir).resolve() / f"{safe_name}.log"
    if not str(log_file.resolve()).startswith(str(Path(log_dir).resolve())):
        raise ValueError(f"路径遍历检测: {server_id}")
    return log_file


@click.command("logs")
@click.argument("server_name", required=True)
@click.option("-n", "--lines", default=50, type=int, help="显示行数")
@click.option("-f", "--follow", is_flag=True, help="实时跟踪")
def logs(server_name: str, lines: int, follow: bool) -> None:
    """查看 Server 日志。"""
    import time

    server_id = f"@community/{server_name}" if "/" not in server_name else server_name
    log_dir = str(Path.home() / ".config" / "mcp-hub" / "logs")
    log_file = safe_log_path(log_dir, server_id)

    if not log_file.exists():
        click.echo(f"📭 日志文件不存在: {log_file}")
        click.echo("   提示: Server 可能还未启动过")
        return

    def tail() -> None:
        with open(log_file, encoding="utf-8") as f:
            content = f.read()
            all_lines = content.splitlines()
            for line in all_lines[-lines:]:
                click.echo(line)
            if follow:
                # tail -f
                f.seek(0, 2)  # end of file
                try:
                    while True:
                        line = f.readline()
                        if line:
                            click.echo(line.rstrip())
                        else:
                            time.sleep(0.1)
                except KeyboardInterrupt:
                    pass

    tail()
