"""mcp init — 一键初始化命令。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import click


@click.command("init")
@click.option("--db-url", help="数据库连接字符串（默认从 .env 读取）")
@click.option("--force", is_flag=True, help="强制重新初始化")
@click.option("--no-seed", is_flag=True, help="不导入预置数据")
def init_cmd(db_url: str | None, force: bool, no_seed: bool):
    """一键初始化 MCP Server Hub 环境。"""
    async def _run():
        click.echo("\n🔵 MCP Server Hub 初始化\n")

        # Step 1: 检查环境
        click.echo("📋 环境检查...")
        checks = []
        checks.append(("Python", sys.version.split()[0], True))

        pg_ok = False
        try:
            import subprocess
            result = subprocess.run(
                ["psql", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                pg_ver = result.stdout.strip()
                pg_ok = True
                checks.append(("PostgreSQL", pg_ver, True))
            else:
                checks.append(("PostgreSQL", "未找到", False))
        except Exception:
            checks.append(("PostgreSQL", "未找到", False))

        for name, ver, ok in checks:
            icon = "✅" if ok else "❌"
            click.echo(f"   {icon} {name}: {ver}")

        # Step 2: 创建配置目录
        config_dir = Path.home() / ".config" / "mcp-hub"
        config_dir.mkdir(parents=True, exist_ok=True)
        logs_dir = config_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        click.echo(f"   📁 配置目录: {config_dir}")

        # Step 3: 写入 .env
        env_path = config_dir / ".env"
        if not env_path.exists() or force:
            if db_url:
                db_line = f'MCP_HUB_DATABASE_URL={db_url}'
            elif os.environ.get("MCP_HUB_DATABASE_URL"):
                db_line = f'MCP_HUB_DATABASE_URL={os.environ["MCP_HUB_DATABASE_URL"]}'
            else:
                db_line = "MCP_HUB_DATABASE_URL=postgresql+asyncpg://mcp_hub:mcp_hub_prod_2026@localhost:5432/mcp_hub"

            env_content = f"""# MCP Server Hub 配置（由 mcp init 生成）
{db_line}
MCP_HUB_SECRET={os.urandom(32).hex()}
MCP_HUB_HOST=0.0.0.0
MCP_HUB_PORT=3987
MCP_HUB_CORS_ORIGINS=*
MCP_HUB_WORKERS=2
"""
            env_path.write_text(env_content)
            click.echo(f"   ✅ 配置文件: {env_path}")
        else:
            click.echo(f"   ⏭️  .env 已存在，跳过 (使用 --force 覆盖)")

        # Step 4: 初始化数据库
        click.echo("\n🗄️  数据库初始化...")
        try:
            from mcp_hub.db.database import init_db
            asyncio.run(init_db())
            click.echo("   ✅ 数据库表已创建")
            if not no_seed:
                from mcp_hub.db.seed import seed_database
                n = asyncio.run(seed_database())
                click.echo(f"   ✅ 已导入 {n} 个预置 MCP Server")
        except Exception as e:
            click.echo(f"   ❌ 数据库初始化失败: {e}")
            click.echo("   提示: 确保 PostgreSQL 在运行，或通过 --db-url 指定连接")
            return

        # Step 5: 生成 mcp.json 配置模板
        mcp_config = config_dir / "mcp.json"
        if not mcp_config.exists() or force:
            default_config = {
                "mcpServers": {
                    "mcp-hub": {
                        "command": "mcp",
                        "args": ["serve"],
                        "description": "MCP Server Hub — 聚合所有 MCP Server",
                    }
                }
            }
            mcp_config.write_text(json.dumps(default_config, indent=2, ensure_ascii=False))
            click.echo(f"   ✅ MCP 配置: {mcp_config}")
        else:
            click.echo(f"   ⏭️  mcp.json 已存在，跳过")

        # Step 6: 开机自启
        click.echo("\n🔄 开机自启配置...")
        try:
            cron_job = f"@reboot sleep 5 && cd {os.getcwd()} && {sys.executable} -m uvicorn mcp_hub.api.app:create_app --host 0.0.0.0 --port {os.environ.get('MCP_HUB_PORT', '3987')} --workers 2 --log-level info > /tmp/mcp-hub-prod.log 2>&1"
            result = os.system(f'(crontab -l 2>/dev/null | grep -v "mcp-hub"; echo "{cron_job}") | crontab -')
            if result == 0:
                click.echo("   ✅ crontab 开机自启已配置")
            else:
                click.echo("   ⚠️  crontab 配置失败，可手动添加开机自启")
        except Exception as e:
            click.echo(f"   ⚠️  开机自启配置跳过: {e}")

        click.echo("\n" + "=" * 50)
        click.echo("🎉 MCP Server Hub 初始化完成！")
        click.echo(f"   启动: mcp daemon start")
        click.echo(f"   查看: http://localhost:{os.environ.get('MCP_HUB_PORT', '3987')}")
        click.echo("=" * 50)

    asyncio.run(_run())
