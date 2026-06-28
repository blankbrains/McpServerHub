"""认证命令 —— GitHub OAuth。"""

from __future__ import annotations

import asyncio
import json
import webbrowser
from pathlib import Path

import click

from mcp_hub.core.auth import AuthService


@click.command("login")
def login():
    """使用 GitHub 登录。"""
    async def _run():
        auth = AuthService()
        url = auth.get_github_login_url()

        click.echo("🔑 正在打开 GitHub 登录页面...")
        click.echo("   如果浏览器没有自动打开，请访问:")
        click.echo(f"   {url}")
        click.echo()

        try:
            webbrowser.open(url)
        except Exception:
            pass

        code = click.prompt(
            "   授权完成后，请把浏览器地址栏 ?code= 后面的参数粘贴到此处",
            default="",
        )
        if code:
            result = await auth.authenticate_with_github(code)
            if result.get("success"):
                token_file = Path.home() / ".config" / "mcp-hub" / "token.json"
                token_file.parent.mkdir(parents=True, exist_ok=True)
                token_file.write_text(json.dumps({
                    "token": result["token"],
                    "user_id": result["user_id"],
                }))
                click.echo(f"✅ 登录成功！欢迎 {result['user_id']}")
            else:
                click.echo(f"❌ 登录失败: {result.get('error', '未知错误')}")
        else:
            click.echo("   或者直接复制以下 URL 到浏览器登录:")
            click.echo(f"   {url}")

    asyncio.run(_run())


@click.command("logout")
def logout():
    """退出登录。"""
    token_file = Path.home() / ".config" / "mcp-hub" / "token.json"
    if token_file.exists():
        token_file.unlink()
    click.echo("✅ 已退出登录")


@click.command("whoami")
def whoami():
    """查看当前用户。"""
    token_file = Path.home() / ".config" / "mcp-hub" / "token.json"
    if token_file.exists():
        try:
            data = json.loads(token_file.read_text())
            click.echo(f"👤 当前用户: {data.get('user_id', 'unknown')}")
            return
        except Exception:
            pass
    click.echo("👤 未登录 (使用 mcp login 登录)")
