"""日志查看命令。"""

from __future__ import annotations

from pathlib import Path

import click


@click.command("logs")
@click.argument("server_name", required=True)
@click.option("-n", "--lines", default=50, type=int, help="显示行数")
@click.option("-f", "--follow", is_flag=True, help="实时跟踪")
def logs(server_name: str, lines: int, follow: bool):
    """查看 Server 日志。"""
    import time

    server_id = f"@community/{server_name}" if "/" not in server_name else server_name
    safe_name = server_id.replace("/", "_").replace("@", "")
    log_file = Path.home() / ".config" / "mcp-hub" / "logs" / f"{safe_name}.log"

    if not log_file.exists():
        click.echo(f"📭 日志文件不存在: {log_file}")
        click.echo("   提示: Server 可能还未启动过")
        return

    def tail():
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
