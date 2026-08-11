"""本地 MCP Hub Agent 遥测配置命令。"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

import click
import tomli_w

from mcp_hub.agent_types import AGENT_TYPES, DEFAULT_AGENT_TYPE
from mcp_hub.core.agent_config import (
    apply_agent_migration,
    get_agent_profile,
    prepare_agent_migration,
)
from mcp_hub.core.gateway_config import (
    GATEWAY_CONFIG_ENV,
    get_gateway_config_path,
    load_gateway_config,
    write_gateway_config,
)
from mcp_hub.core.telemetry import (
    AGENT_TYPE_ENV,
    REPORT_URL_ENV,
    STATE_DIR_ENV,
    TELEMETRY_TOKEN_ENV,
    TelemetryReporter,
    TelemetrySpool,
    get_agent_state_dir,
    get_spool_path,
)


@click.group("agent")
def agent() -> None:
    """配置本地 MCP Gateway 遥测 Agent。"""


@agent.command("config")
@click.option(
    "--agent",
    "agent_type",
    type=click.Choice(AGENT_TYPES),
    default=DEFAULT_AGENT_TYPE,
    show_default=True,
    help="此设备令牌绑定的 MCP 客户端类型。",
)
@click.option(
    "--hub-url",
    default=lambda: os.environ.get(REPORT_URL_ENV, "http://127.0.0.1:3987"),
    show_default="环境变量 MCP_HUB_REPORT_URL 或 http://127.0.0.1:3987",
    help="MCP Hub 服务地址。",
)
@click.option(
    "--telemetry-token",
    envvar=TELEMETRY_TOKEN_ENV,
    required=True,
    help="在监控页创建的设备遥测令牌。",
)
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="本地离线队列目录，默认 ~/.config/mcp-hub。",
)
def agent_config(
    agent_type: str,
    hub_url: str,
    telemetry_token: str,
    state_dir: Path | None,
) -> None:
    """输出可放入 MCP 客户端配置的 Gateway 配置片段。"""
    agent_state_dir = state_dir or get_agent_state_dir(agent_type)
    gateway_config_path = get_gateway_config_path(agent_state_dir)
    profile = get_agent_profile(agent_type)
    entry: dict[str, object] = {
        "command": "mcp-hub",
        "args": ["serve"],
        "env": {
            REPORT_URL_ENV: hub_url.rstrip("/"),
            TELEMETRY_TOKEN_ENV: telemetry_token,
            STATE_DIR_ENV: str(agent_state_dir),
            AGENT_TYPE_ENV: agent_type,
            GATEWAY_CONFIG_ENV: str(gateway_config_path),
        },
    }
    if profile.requires_stdio_type:
        entry = {"type": "stdio", **entry}
    config = {profile.server_key: {"mcp-hub": entry}}
    output = (
        tomli_w.dumps(config)
        if profile.format == "toml"
        else json.dumps(config, ensure_ascii=False, indent=2)
    )
    click.echo(output)


@agent.command("setup")
@click.option(
    "--agent",
    "agent_type",
    type=click.Choice(AGENT_TYPES),
    default=DEFAULT_AGENT_TYPE,
    show_default=True,
)
@click.option(
    "--hub-url",
    default=lambda: os.environ.get(REPORT_URL_ENV, "http://127.0.0.1:3987"),
    show_default="环境变量 MCP_HUB_REPORT_URL 或 http://127.0.0.1:3987",
)
@click.option(
    "--telemetry-token",
    envvar=TELEMETRY_TOKEN_ENV,
    required=True,
    help="在监控页创建的一次性设备遥测令牌。",
)
@click.option(
    "--source-config",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="现有 Agent 配置；未指定时自动查找标准路径。",
)
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=None,
)
@click.option("--yes", is_flag=True, help="确认已阅读变更预览并执行迁移。")
def agent_setup(
    agent_type: str,
    hub_url: str,
    telemetry_token: str,
    source_config: Path | None,
    state_dir: Path | None,
    yes: bool,
) -> None:
    """备份现有 Agent 配置并迁移到可监控的本地 Gateway。"""
    try:
        migration = prepare_agent_migration(agent_type, source_config)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not migration.specs:
        detail = (
            f"；{len(migration.errors)} 个条目因传输方式不支持或配置无效而保留"
            if migration.errors
            else ""
        )
        raise click.ClickException(f"没有可迁移到 Gateway 的 MCP Server{detail}")

    agent_state_dir = state_dir or get_agent_state_dir(agent_type)
    gateway_config_path = get_gateway_config_path(agent_state_dir)
    click.echo(f"Agent: {migration.profile.name}")
    click.echo(f"配置: {migration.source_path}")
    click.echo(f"将迁移 {len(migration.specs)} 个 MCP Server 到: {gateway_config_path}")
    for spec in migration.specs:
        endpoint = spec.command if spec.transport == "stdio" else spec.transport
        click.echo(f"  - {spec.server_id} ({endpoint})")
    if migration.retained_server_names:
        click.echo(
            "以下条目不会删除或代理，将保留在原 Agent 配置中: "
            + ", ".join(migration.retained_server_names)
        )

    if not yes and not click.confirm(
        "继续后会先创建带时间戳备份，再用 mcp-hub Gateway 替换上述直接连接，是否继续？",
        default=False,
    ):
        click.echo("已取消，未修改任何配置。")
        return

    try:
        write_gateway_config(list(migration.specs), gateway_config_path)
        backup_path = apply_agent_migration(
            migration,
            report_url=hub_url,
            telemetry_token=telemetry_token,
            state_dir=agent_state_dir,
            gateway_config_path=gateway_config_path,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise click.ClickException(f"配置迁移失败: {exc}") from exc

    click.echo(f"配置完成，原文件备份: {backup_path}")
    click.echo(f"Gateway 管理配置: {gateway_config_path}")
    try:
        reporter = TelemetryReporter(hub_url, telemetry_token, agent_state_dir)

        async def _report_inventory() -> None:
            await reporter.report_inventory(
                [spec.inventory_entry() for spec in migration.specs],
                [
                    {
                        "server_id": error.get("server_id", ""),
                        "error_code": "unsupported_or_invalid",
                    }
                    for error in migration.errors
                ],
            )
            await reporter.close()

        asyncio.run(_report_inventory())
    except Exception:
        click.echo("警告：本地配置已完成，但发现清单暂未上传，将在 Gateway 启动后重试。")
    click.echo("重启 Agent 后，所有已迁移 Server 调用会经过 mcp-hub 并上报监控指标。")


@agent.command("discover")
@click.option(
    "--agent",
    "agent_type",
    type=click.Choice(AGENT_TYPES),
    default=DEFAULT_AGENT_TYPE,
    show_default=True,
)
@click.option(
    "--hub-url",
    default=lambda: os.environ.get(REPORT_URL_ENV, "http://127.0.0.1:3987"),
    show_default="环境变量 MCP_HUB_REPORT_URL 或 http://127.0.0.1:3987",
)
@click.option(
    "--telemetry-token",
    envvar=TELEMETRY_TOKEN_ENV,
    required=True,
)
@click.option(
    "--source-config",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
)
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=None,
)
def agent_discover(
    agent_type: str,
    hub_url: str,
    telemetry_token: str,
    source_config: Path | None,
    state_dir: Path | None,
) -> None:
    """只读取并上报脱敏的本地 MCP 清单，不修改 Agent 配置。"""
    try:
        migration = prepare_agent_migration(agent_type, source_config)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise click.ClickException(str(exc)) from exc

    agent_state_dir = state_dir or get_agent_state_dir(agent_type)
    reporter = TelemetryReporter(hub_url, telemetry_token, agent_state_dir)

    async def _run() -> None:
        await reporter.report_inventory(
            [spec.inventory_entry() for spec in migration.specs],
            [
                {
                    "server_id": error.get("server_id", ""),
                    "error_code": "unsupported_or_invalid",
                }
                for error in migration.errors
            ],
        )
        await reporter.close()

    asyncio.run(_run())
    click.echo(
        f"已上报 {len(migration.specs)} 个脱敏 Server 清单；"
        f"{len(migration.errors)} 个非 stdio 或无效条目未代理。"
    )


@agent.command("status")
@click.option(
    "--agent",
    "agent_type",
    type=click.Choice(AGENT_TYPES),
    default=DEFAULT_AGENT_TYPE,
    show_default=True,
    help="查看指定 MCP 客户端的本地遥测队列。",
)
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="本地离线队列目录，默认 ~/.config/mcp-hub。",
)
def agent_status(agent_type: str, state_dir: Path | None) -> None:
    """显示本地 Agent 的遥测配置和待上传事件数。"""
    agent_state_dir = state_dir or get_agent_state_dir(agent_type)
    spool_path = get_spool_path(agent_state_dir)
    gateway_config_path = get_gateway_config_path(agent_state_dir)
    specs, configuration_errors = load_gateway_config(gateway_config_path)
    queued_events = 0
    if spool_path.exists():
        spool = TelemetrySpool(agent_state_dir)
        try:
            queued_events = spool.count()
        finally:
            spool.close()

    configured = bool(
        os.environ.get(REPORT_URL_ENV, "").strip()
        and os.environ.get(TELEMETRY_TOKEN_ENV, "").strip()
    )
    click.echo(
        json.dumps(
            {
                "telemetry_configured": configured,
                "agent_type": agent_type,
                "state_dir": str(agent_state_dir),
                "gateway_config_path": str(gateway_config_path),
                "gateway_configured": gateway_config_path.exists(),
                "configured_servers": len(specs),
                "enabled_servers": sum(1 for spec in specs if spec.enabled),
                "configuration_errors": configuration_errors,
                "queued_events": queued_events,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@agent.command("doctor")
@click.option(
    "--agent",
    "agent_type",
    type=click.Choice(AGENT_TYPES),
    default=DEFAULT_AGENT_TYPE,
    show_default=True,
)
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=None,
)
def agent_doctor(agent_type: str, state_dir: Path | None) -> None:
    """检查 Gateway 配置、命令、工作目录和遥测队列。"""
    agent_state_dir = state_dir or get_agent_state_dir(agent_type)
    gateway_config_path = get_gateway_config_path(agent_state_dir)
    specs, configuration_errors = load_gateway_config(gateway_config_path)
    checks: list[dict[str, object]] = []

    if not gateway_config_path.exists():
        checks.append(
            {
                "status": "error",
                "check": "gateway_config",
                "message": f"未找到 {gateway_config_path}",
            }
        )
    for error in configuration_errors:
        checks.append(
            {
                "status": "error",
                "check": "server_config",
                "server_id": error.get("server_id", ""),
                "message": error.get("error", "配置无效"),
            }
        )
    for spec in specs:
        executable_found = bool(
            shutil.which(spec.command)
            or (Path(spec.command).exists() and Path(spec.command).is_file())
        )
        checks.append(
            {
                "status": "ok" if executable_found else "error",
                "check": "executable",
                "server_id": spec.server_id,
                "message": (
                    f"已找到 {spec.command}"
                    if executable_found
                    else f"找不到命令 {spec.command}"
                ),
            }
        )
        if spec.cwd:
            cwd_exists = Path(spec.cwd).is_dir()
            checks.append(
                {
                    "status": "ok" if cwd_exists else "error",
                    "check": "cwd",
                    "server_id": spec.server_id,
                    "message": (
                        f"工作目录存在: {spec.cwd}"
                        if cwd_exists
                        else f"工作目录不存在: {spec.cwd}"
                    ),
                }
            )

    spool_path = get_spool_path(agent_state_dir)
    queued_events = 0
    if spool_path.exists():
        spool = TelemetrySpool(agent_state_dir)
        try:
            queued_events = spool.count()
        finally:
            spool.close()
    checks.append(
        {
            "status": "warning" if queued_events else "ok",
            "check": "telemetry_queue",
            "message": f"待上传事件 {queued_events} 个",
        }
    )
    result = {
        "healthy": bool(checks) and all(check["status"] != "error" for check in checks),
        "agent_type": agent_type,
        "gateway_config_path": str(gateway_config_path),
        "checks": checks,
    }
    click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["healthy"]:
        raise click.ClickException("Gateway 自检发现需要处理的问题")
