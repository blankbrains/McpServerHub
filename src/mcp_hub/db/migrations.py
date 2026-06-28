"""数据库迁移便捷模块。

直接用 Python 调用 Alembic 命令：
    python -m mcp_hub.db.migrations          # 升级到最新
    python -m mcp_hub.db.migrations -- downgrade -1  # 回滚一步
    python -m mcp_hub.db.migrations -- revision --autogenerate -m "描述"
"""

from __future__ import annotations

import os
import sys


def run_alembic(argv: list[str] | None = None) -> None:
    """运行 Alembic 命令。

    Args:
        argv: Alembic 命令行参数。默认运行 upgrade head。
    """
    from alembic.config import CommandLine

    # 设置 alembic 配置路径
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )))
    alembic_ini = os.path.join(project_root, "alembic.ini")

    if argv is None:
        argv = ["-c", alembic_ini, "upgrade", "head"]
    else:
        argv = ["-c", alembic_ini] + list(argv)

    cli = CommandLine()
    cli.main(argv=argv)


if __name__ == "__main__":
    run_alembic(sys.argv[1:] if len(sys.argv) > 1 else None)
