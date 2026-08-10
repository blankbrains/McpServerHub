"""配置管理命令。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console

from mcp_hub.core.agent_config import AgentConfigProfile, get_agent_profile
from mcp_hub.core.config_manager import ConfigManager
from mcp_hub.core.gateway_config import (
    GatewayServerSpec,
    get_gateway_config_path,
    load_gateway_config,
    parse_gateway_config,
    write_gateway_config,
)

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

_console = Console()


def _get_saved_auth_headers() -> dict[str, str]:
    """读取 CLI 登录令牌，用于访问用户隔离的 Hub 配置接口。"""
    token_file = Path.home() / ".config" / "mcp-hub" / "token.json"
    try:
        token = json.loads(token_file.read_text(encoding="utf-8")).get("token", "")
    except (OSError, json.JSONDecodeError):
        token = ""
    return {"Authorization": f"Bearer {token}"} if token else {}


def _decode_hub_config(
    config: str | dict[str, Any],
    profile: AgentConfigProfile,
) -> tuple[list[GatewayServerSpec], list[dict[str, str]]]:
    """Convert a downloaded Agent document into canonical Gateway specs."""
    document = tomllib.loads(config) if isinstance(config, str) else config
    if not isinstance(document, dict):
        raise ValueError("Hub 配置根节点必须是对象")
    raw_servers = document.get(profile.server_key, {})
    if not isinstance(raw_servers, dict):
        raise ValueError(f"Hub 配置中的 {profile.server_key} 必须是对象")
    return parse_gateway_config({"mcpServers": raw_servers})


def _merge_private_gateway_fields(
    desired: list[GatewayServerSpec],
    existing: list[GatewayServerSpec],
) -> list[GatewayServerSpec]:
    """Preserve local-only credentials and working directories during Hub sync."""
    existing_by_id = {spec.server_id: spec for spec in existing}
    merged: list[GatewayServerSpec] = []
    for spec in desired:
        previous = existing_by_id.get(spec.server_id)
        if previous is None or previous.transport != spec.transport:
            merged.append(spec)
            continue
        if spec.transport == "stdio":
            merged.append(
                replace(
                    spec,
                    env=dict(previous.env),
                    cwd=previous.cwd,
                )
            )
        else:
            merged.append(
                replace(
                    spec,
                    headers=dict(previous.headers),
                    header_env=dict(previous.header_env),
                    bearer_token_env_var=previous.bearer_token_env_var,
                )
            )
    return merged


@click.group("config")
def config() -> None:
    """管理 Server 配置。"""


@config.command("list")
@click.argument("server_name", required=True)
def list_config(server_name: str) -> None:
    """查看 Server 配置。"""

    async def _run() -> None:
        cm = ConfigManager()
        server_id = f"@community/{server_name}" if "/" not in server_name else server_name
        cfg = await cm.list_config(server_id)
        click.echo(json.dumps(cfg, indent=2, ensure_ascii=False))

    asyncio.run(_run())


@config.command("set")
@click.argument("server_name", required=True)
@click.argument("key", required=True)
@click.argument("value", required=True)
def set_config(server_name: str, key: str, value: str) -> None:
    """设置环境变量。"""

    async def _run() -> None:
        cm = ConfigManager()
        server_id = f"@community/{server_name}" if "/" not in server_name else server_name
        ok = await cm.set_config(server_id, key, value)
        if ok:
            click.echo(f"✅ {key}={value} 已设置")
        else:
            click.echo(f"❌ {server_id} 未找到")

    asyncio.run(_run())


@config.command("export")
@click.argument("file", required=False)
def export_config(file: str | None) -> None:
    """导出配置。"""
    from mcp_hub.core.config_manager import ConfigManager

    async def _run() -> None:
        cm = ConfigManager()
        cfg = await cm._load_config()
        output = json.dumps(cfg, indent=2, ensure_ascii=False)
        if file:
            with open(file, "w", encoding="utf-8") as f:
                f.write(output)
            click.echo(f"✅ 配置已导出到 {file}")
        else:
            click.echo(output)

    asyncio.run(_run())


@config.command("import")
@click.argument("file", required=True)
def import_config(file: str) -> None:
    """导入配置。"""
    try:
        with open(file, encoding="utf-8") as f:
            data = json.load(f)
        cm = ConfigManager()
        config_path = cm.config_dir / "mcp.json"
        config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        click.echo(f"✅ 配置已从 {file} 导入")
    except FileNotFoundError:
        click.echo(f"❌ 文件未找到: {file}")
    except json.JSONDecodeError:
        click.echo(f"❌ 无效的 JSON 文件: {file}")


@config.command("apply")
@click.option("--path", default=None, help="写入路径，默认 ~/.config/mcp-hub/mcp.json")
def apply_config(path: str | None) -> None:
    """将 Hub 配置写入本地文件（自动配置）。"""

    async def _run() -> None:
        cm = ConfigManager()
        result = await cm.apply_config(path)
        if result["success"]:
            _console.print(f"[green]✅ 配置已写入: {result['path']}[/green]")
            _console.print(f"[green]   包含 {result['server_count']} 个 Server[/green]")
        else:
            _console.print("[red]❌ 配置写入失败[/red]")

    asyncio.run(_run())


@config.command("sync")
@click.option("--server", "hub_url", default="http://localhost:3987", help="Hub 服务器地址")
@click.option(
    "--agent", default="claude-code", help="目标 Agent (claude-code/cursor/codex/generic)"
)  # noqa: E501
@click.option("--server-ids", help="要同步的 Server ID 列表（逗号分隔），默认同步所有已安装")
@click.option("--yes", is_flag=True, help="确认覆盖前已阅读目标路径与备份说明")
def sync_config(hub_url: str, agent: str, server_ids: str | None, yes: bool) -> None:
    """从 Hub 同步当前用户配置到本地 Gateway。

    Agent 配置必须先通过 `mcp-hub agent setup` 接入 Gateway。
    同步只更新 Gateway 管理的 Server 清单，不覆盖 Agent 主配置。

    用法:
      mcp-hub config sync                                    # 同步所有已安装
      mcp-hub config sync --server https://hub.example.com   # 指定 Hub 地址
      mcp-hub config sync --agent cursor                     # 同步到 Cursor
      mcp-hub config sync --server-ids @anth/web,@git/hub    # 只同步指定 Server
    """

    async def _run() -> None:
        import httpx

        api_base = hub_url.rstrip("/") + "/api/v1"
        auth_headers = _get_saved_auth_headers()
        _console.print(f"[dim]🔗 连接 Hub: {api_base}[/dim]")

        try:
            if server_ids:
                ids = [s.strip() for s in server_ids.split(",")]
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        f"{api_base}/config/build",
                        json={"servers": ids, "agent": agent},
                        headers=auth_headers,
                    )
                    if resp.status_code != 200:
                        _console.print(f"[red]❌ Hub 返回错误: {resp.status_code}[/red]")
                        return
                    if "toml" in resp.headers.get("content-type", ""):
                        config = resp.text
                    else:
                        config = resp.json()
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        f"{api_base}/config/download",
                        params={"agent": agent},
                        headers=auth_headers,
                    )
                    if resp.status_code == 401:
                        _console.print(
                            "[red]❌ 请先使用 mcp-hub login 登录后再同步个人配置[/red]"
                        )
                        return
                    if resp.status_code != 200:
                        _console.print(f"[red]❌ Hub 返回错误: {resp.status_code}[/red]")
                        return
                    if "toml" in resp.headers.get("content-type", ""):
                        config = resp.text
                    else:
                        config = resp.json()

        except httpx.ConnectError:
            _console.print(f"[red]❌ 无法连接 Hub: {api_base}[/red]")
            _console.print("[yellow]   请确保 Hub 在运行，或使用 --server 指定地址[/yellow]")
            return
        except Exception as e:
            _console.print(f"[red]❌ 同步失败: {e}[/red]")
            return

        try:
            profile = get_agent_profile(agent)
        except ValueError as exc:
            _console.print(f"[red]❌ {exc}[/red]")
            return
        gateway_path = get_gateway_config_path(agent_type=agent)
        if not gateway_path.exists():
            _console.print(
                "[red]❌ 尚未找到本地 Gateway 配置，请先运行 "
                f"`mcp-hub agent setup --agent {agent}`[/red]"
            )
            return

        try:
            desired, decode_errors = _decode_hub_config(config, profile)
        except (ValueError, TypeError, tomllib.TOMLDecodeError) as exc:
            _console.print(f"[red]❌ Hub 返回的配置无效: {exc}[/red]")
            return
        if decode_errors:
            for error in decode_errors:
                _console.print(
                    "[red]❌ "
                    f"{error.get('server_id') or 'unknown'}: {error.get('error', '配置无效')}[/red]"
                )
            return

        existing, existing_errors = load_gateway_config(gateway_path)
        if existing_errors:
            for error in existing_errors:
                _console.print(
                    "[red]❌ 当前 Gateway 配置损坏: "
                    f"{error.get('server_id') or 'root'}: {error.get('error', '配置无效')}[/red]"
                )
            return
        merged = _merge_private_gateway_fields(desired, existing)
        desired_ids = {spec.server_id for spec in merged}
        removed_ids = [spec.server_id for spec in existing if spec.server_id not in desired_ids]

        _console.print(f"Agent: {profile.name}")
        _console.print(f"Gateway: {gateway_path}")
        _console.print(f"同步后 Server: {len(merged)} 个")
        if removed_ids:
            _console.print("将从 Gateway 移除: " + ", ".join(removed_ids))
        if not yes and not click.confirm(
            "继续会先备份当前 Gateway 配置，再应用 Hub 清单，是否继续？",
            default=False,
        ):
            _console.print("[yellow]已取消，未修改本地配置[/yellow]")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = gateway_path.with_name(
            f"{gateway_path.name}.mcp-hub-backup-{timestamp}"
        )
        backup_path.write_bytes(gateway_path.read_bytes())
        write_gateway_config(merged, gateway_path)

        _console.print("[green]✅ Gateway 配置已同步[/green]")
        _console.print(f"   备份: [bold]{backup_path}[/bold]")
        _console.print(f"   Server: {len(merged)} 个")
        _console.print(f"\n[dim]💡 重启 {profile.name} 后生效[/dim]")

    asyncio.run(_run())
