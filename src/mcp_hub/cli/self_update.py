"""CLI and Gateway self-version checks, upgrades, and rollback history."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import httpx

from mcp_hub import __version__
from mcp_hub.core.version_policy import (
    STABLE_REF,
    TEST_REF,
    build_compatibility_payload,
    install_command,
    is_release_tag,
)


@dataclass(frozen=True)
class UpgradeRecord:
    """One local, credential-free CLI install transition."""

    previous_version: str
    target_ref: str
    created_at: str


def _default_state_dir() -> Path:
    configured = os.environ.get("MCP_HUB_SELF_STATE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / "mcp-hub"


def _history_path(state_dir: Path) -> Path:
    return state_dir / "cli-update-history.json"


def _read_history(state_dir: Path) -> list[UpgradeRecord]:
    path = _history_path(state_dir)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("CLI 升级历史格式无效。")
    records = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("CLI 升级历史格式无效。")
        records.append(
            UpgradeRecord(
                previous_version=str(entry.get("previous_version", "")),
                target_ref=str(entry.get("target_ref", "")),
                created_at=str(entry.get("created_at", "")),
            )
        )
    return records


def _append_history(state_dir: Path, record: UpgradeRecord) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = _history_path(state_dir)
    previous = _read_history(state_dir)
    payload = [asdict(item) for item in [*previous, record]][-20:]
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _compatibility_url(hub_url: str) -> str:
    return f"{hub_url.rstrip('/')}/api/v1/client-compatibility"


def _fetch_compatibility(
    hub_url: str,
    *,
    gateway_version: str,
) -> dict[str, Any]:
    response = httpx.get(
        _compatibility_url(hub_url),
        params={
            "cli_version": __version__,
            "gateway_version": gateway_version,
        },
        timeout=5.0,
    )
    response.raise_for_status()
    body = response.json()
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise ValueError("Hub 兼容策略响应格式无效。")
    return dict(data)


def _run_uv_install(ref: str) -> None:
    uv_path = shutil.which("uv")
    if not uv_path:
        raise click.ClickException(
            "找不到 uv。请先安装 uv 并重新打开终端后再执行升级。"
        )
    command = [
        uv_path,
        "tool",
        "install",
        "--force",
        f"git+https://github.com/blankbrains/McpServerHub.git@{ref}",
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise click.ClickException(f"CLI 安装失败，uv 退出码 {completed.returncode}。")


@click.group("self")
def self_group() -> None:
    """检查、升级或回滚 mcp-hub CLI 与本地 Gateway。"""


@self_group.command("check")
@click.option("--hub-url", default="", help="可选 Hub 地址，用于读取实时兼容策略。")
@click.option(
    "--gateway-version",
    default=__version__,
    show_default=True,
    help="当前本地 Gateway 版本；默认与正在运行的 CLI 相同。",
)
@click.option("--json", "json_output", is_flag=True, help="输出稳定 JSON 结果。")
def self_check(hub_url: str, gateway_version: str, json_output: bool) -> None:
    """检查当前 CLI、Hub 与 Gateway 的版本兼容性。"""
    payload = build_compatibility_payload(
        cli_version=__version__,
        gateway_version=gateway_version,
    )
    source = "bundled_policy"
    if hub_url.strip():
        try:
            payload = _fetch_compatibility(
                hub_url,
                gateway_version=gateway_version,
            )
            source = "hub_policy"
        except (httpx.HTTPError, ValueError) as exc:
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "success": False,
                            "error": "hub_unreachable",
                            "message": type(exc).__name__,
                            "data": payload,
                        },
                        ensure_ascii=False,
                    )
                )
                raise click.exceptions.Exit(1) from exc
            raise click.ClickException(
                f"无法读取 Hub 兼容策略: {type(exc).__name__}"
            ) from exc

    result = {
        "success": True,
        "policy_source": source,
        "installed_cli_version": __version__,
        "gateway_version": gateway_version,
        "data": payload,
    }
    if json_output:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return
    cli = payload.get("cli") or {}
    click.echo(f"当前 CLI: {__version__}")
    click.echo(f"当前 Gateway: {gateway_version}")
    click.echo(f"Hub: {payload.get('hub_version', 'unknown')}")
    click.echo(f"最低 Gateway: {payload.get('minimum_gateway_version', '-')}")
    click.echo(f"推荐 Gateway: {payload.get('recommended_gateway_version', '-')}")
    click.echo(f"状态: {cli.get('status', 'unknown')} - {cli.get('message', '')}")
    click.echo(f"稳定升级: {install_command(str(payload.get('stable_ref', STABLE_REF)))}")


@self_group.command("upgrade")
@click.option(
    "--channel",
    type=click.Choice(["stable", "test"]),
    default="stable",
    show_default=True,
)
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=_default_state_dir,
    show_default="MCP_HUB_SELF_STATE_DIR 或 ~/.config/mcp-hub",
)
@click.option("--dry-run", is_flag=True, help="只显示升级计划，不执行 uv。")
@click.option("--json", "json_output", is_flag=True, help="输出稳定 JSON 结果。")
def self_upgrade(
    channel: str,
    state_dir: Path,
    dry_run: bool,
    json_output: bool,
) -> None:
    """升级当前 CLI 和未来启动的 Gateway，不修改 Agent 配置。"""
    ref = STABLE_REF if channel == "stable" else TEST_REF
    record = UpgradeRecord(
        previous_version=__version__,
        target_ref=ref,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    result = {
        "success": True,
        "channel": channel,
        "previous_version": __version__,
        "target_ref": ref,
        "install_command": install_command(ref),
        "state_dir": str(state_dir),
        "agent_config_changed": False,
        "device_token_changed": False,
        "dry_run": dry_run,
    }
    if dry_run:
        if json_output:
            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            click.echo(f"将执行: {result['install_command']}")
            click.echo("升级前会记录当前版本；不会修改 Agent 配置或设备令牌。")
        return
    try:
        _run_uv_install(ref)
        _append_history(state_dir, record)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"无法记录升级历史: {exc}") from exc
    if json_output:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        click.echo(f"已请求升级到 {ref}。重启 Agent 后新的 Gateway 进程会使用升级后的 CLI。")


@self_group.command("rollback")
@click.option("--to", "target_ref", default="", help="目标 Git Tag，例如 v0.2.0。")
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=_default_state_dir,
    show_default="MCP_HUB_SELF_STATE_DIR 或 ~/.config/mcp-hub",
)
@click.option("--dry-run", is_flag=True, help="只显示回滚计划，不执行 uv。")
@click.option("--json", "json_output", is_flag=True, help="输出稳定 JSON 结果。")
def self_rollback(
    target_ref: str,
    state_dir: Path,
    dry_run: bool,
    json_output: bool,
) -> None:
    """回滚 CLI 到上次升级前版本或指定稳定 Git Tag。"""
    try:
        history = _read_history(state_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"无法读取升级历史: {exc}") from exc
    ref = target_ref.strip()
    if not ref:
        if not history or not history[-1].previous_version:
            raise click.ClickException("没有可回滚记录；请使用 --to v<version> 指定目标。")
        ref = f"v{history[-1].previous_version.lstrip('v')}"
    if not is_release_tag(ref):
        raise click.ClickException(
            "回滚目标必须是已发布的稳定 Git Tag，格式为 v<major>.<minor>.<patch>。"
        )
    result = {
        "success": True,
        "target_ref": ref,
        "install_command": install_command(ref),
        "state_dir": str(state_dir),
        "agent_config_changed": False,
        "device_token_changed": False,
        "dry_run": dry_run,
    }
    if not dry_run:
        _run_uv_install(ref)
    if json_output:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        click.echo(f"{'将执行' if dry_run else '已请求执行'}: {result['install_command']}")
        click.echo("回滚不会修改 Agent 配置或设备令牌；重启 Agent 后新 Gateway 进程生效。")
