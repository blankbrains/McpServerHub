"""本地 MCP Hub Agent 遥测配置命令。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from mcp_hub.agent_types import AGENT_TYPES, DEFAULT_AGENT_TYPE
from mcp_hub.core.telemetry import (
    AGENT_TYPE_ENV,
    REPORT_URL_ENV,
    STATE_DIR_ENV,
    TELEMETRY_TOKEN_ENV,
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
    config = {
        "mcpServers": {
            "mcp-hub": {
                "command": "mcp",
                "args": ["serve"],
                "env": {
                    REPORT_URL_ENV: hub_url.rstrip("/"),
                    TELEMETRY_TOKEN_ENV: telemetry_token,
                    STATE_DIR_ENV: str(agent_state_dir),
                    AGENT_TYPE_ENV: agent_type,
                },
            }
        }
    }
    click.echo(json.dumps(config, ensure_ascii=False, indent=2))


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
                "queued_events": queued_events,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
