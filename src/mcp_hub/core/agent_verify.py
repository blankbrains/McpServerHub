"""Read-only Agent integration verification and explicitly approved safe repairs."""

from __future__ import annotations

import copy
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mcp_hub import __version__
from mcp_hub.core.agent_config import (
    AgentConfigProfile,
    read_agent_document,
    write_agent_document_with_backup,
)
from mcp_hub.core.gateway_config import (
    GATEWAY_CONFIG_ENV,
    GatewayServerSpec,
    get_gateway_config_path,
    load_gateway_config,
)
from mcp_hub.core.telemetry import (
    AGENT_TYPE_ENV,
    REPORT_URL_ENV,
    STATE_DIR_ENV,
    TELEMETRY_TOKEN_ENV,
    TelemetryReporter,
    get_agent_state_dir,
    get_spool_path,
)

CheckStatus = Literal["ok", "warning", "error", "skipped"]
_GATEWAY_NAMES = ("mcp-hub", "mcp-hub-gateway")
_CURRENT_GATEWAY_COMMANDS = {"mcp-hub", "mcp-hub.exe", "mcp-hub.cmd"}
_LEGACY_GATEWAY_COMMANDS = {
    "mcp-hub-gateway",
    "mcp-hub-gateway.exe",
    "mcp-hub-gateway.cmd",
}
_REQUIRED_GATEWAY_ENV = (
    REPORT_URL_ENV,
    TELEMETRY_TOKEN_ENV,
    AGENT_TYPE_ENV,
    STATE_DIR_ENV,
    GATEWAY_CONFIG_ENV,
)


@dataclass(frozen=True)
class VerificationCheck:
    """One stable, machine-readable verification result."""

    check: str
    label: str
    status: CheckStatus
    code: str
    message: str
    fixable: bool = False
    server_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "check": self.check,
            "label": self.label,
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "fixable": self.fixable,
            **({"server_id": self.server_id} if self.server_id else {}),
        }


@dataclass(frozen=True)
class PlannedFix:
    """A repair that can be previewed without retaining sensitive values."""

    code: str
    description: str
    requires_backup: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "description": self.description,
            "requires_backup": self.requires_backup,
        }


@dataclass
class VerificationReport:
    """Complete local and online verification report."""

    agent_type: str
    checks: list[VerificationCheck]
    paths: dict[str, str]
    remote: dict[str, object] = field(default_factory=dict)
    planned_fixes: list[PlannedFix] = field(default_factory=list)
    applied_fixes: list[dict[str, object]] = field(default_factory=list)
    confirmation_required: bool = False

    @property
    def ready(self) -> bool:
        return bool(self.checks) and all(check.status == "ok" for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        errors = sum(1 for check in self.checks if check.status == "error")
        warnings = sum(1 for check in self.checks if check.status == "warning")
        skipped = sum(1 for check in self.checks if check.status == "skipped")
        return {
            "success": True,
            "ready": self.ready,
            "agent_type": self.agent_type,
            "summary": {
                "errors": errors,
                "warnings": warnings,
                "skipped": skipped,
                "checks": len(self.checks),
            },
            "paths": self.paths,
            "remote": self.remote,
            "checks": [check.to_dict() for check in self.checks],
            "planned_fixes": [fix.to_dict() for fix in self.planned_fixes],
            "applied_fixes": self.applied_fixes,
            "confirmation_required": self.confirmation_required,
        }


@dataclass
class _LocalContext:
    agent_type: str
    source_path: Path | None
    state_dir: Path
    gateway_config_path: Path
    hub_url: str
    telemetry_token: str
    checks: list[VerificationCheck]
    profile: AgentConfigProfile | None = None
    document: dict[str, Any] | None = None
    gateway_entry: dict[str, Any] | None = None
    gateway_entries: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    specs: list[GatewayServerSpec] = field(default_factory=list)
    queue_count: int = 0
    oldest_queued_at: str | None = None


class _TokenValidationData(BaseModel):
    """Validated subset of the Hub device-token response."""

    model_config = ConfigDict(extra="ignore", strict=True)

    valid: bool
    revoked: bool
    online: bool = False
    state: str = ""
    label: str = ""
    reason: str = ""
    gateway_version: str = ""
    gateway_last_seen_at: str | None = None
    first_call_at: str | None = None
    queue_depth: int = Field(default=0, ge=0)
    server_count: int = Field(default=0, ge=0)
    configuration_error_count: int = Field(default=0, ge=0)


def _check(
    context: _LocalContext,
    check: str,
    label: str,
    status: CheckStatus,
    code: str,
    message: str,
    *,
    fixable: bool = False,
    server_id: str = "",
) -> None:
    context.checks.append(
        VerificationCheck(
            check=check,
            label=label,
            status=status,
            code=code,
            message=message,
            fixable=fixable,
            server_id=server_id,
        )
    )


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _command_name(value: str) -> str:
    return Path(value.strip()).name.lower()


def _command_available(value: str) -> bool:
    normalized = value.strip()
    return bool(
        normalized
        and (
            shutil.which(normalized)
            or (Path(normalized).is_file() and Path(normalized).exists())
        )
    )


def _gateway_candidates(
    profile: AgentConfigProfile,
    document: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[tuple[str, dict[str, Any]]]]:
    raw_servers = document.get(profile.server_key)
    if not isinstance(raw_servers, dict):
        return None, []
    entries = [
        (name, raw)
        for name, raw in raw_servers.items()
        if str(name) in _GATEWAY_NAMES and isinstance(raw, dict)
    ]
    selected = next((raw for name, raw in entries if name == "mcp-hub"), None)
    if selected is None and entries:
        selected = entries[0][1]
    return selected, entries


def _inspect_spool(path: Path) -> tuple[int, str | None]:
    uri = f"file:{path.resolve().as_posix()}?mode=rw"
    connection = sqlite3.connect(uri, uri=True, timeout=2.0)
    try:
        row = connection.execute(
            "SELECT COUNT(*), MIN(created_at) FROM telemetry_spool"
        ).fetchone()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE telemetry_spool SET created_at = created_at WHERE 0"
        )
        connection.rollback()
    finally:
        connection.close()
    return (int(row[0] or 0), str(row[1]) if row and row[1] else None)


def _resolve_local_context(
    agent_type: str,
    *,
    source_config: Path | None,
    state_dir: Path | None,
    hub_url: str,
    telemetry_token: str,
) -> _LocalContext:
    default_state_dir = state_dir or get_agent_state_dir(agent_type)
    context = _LocalContext(
        agent_type=agent_type,
        source_path=source_config,
        state_dir=default_state_dir,
        gateway_config_path=get_gateway_config_path(
            default_state_dir,
            agent_type=agent_type,
        ),
        hub_url=hub_url.strip().rstrip("/"),
        telemetry_token=telemetry_token.strip(),
        checks=[],
    )

    try:
        profile, resolved_path, document = read_agent_document(
            agent_type,
            source_config,
        )
    except FileNotFoundError as exc:
        _check(
            context,
            "agent_config",
            "Agent 配置",
            "error",
            "agent_config_not_found",
            str(exc),
        )
        return _finish_local_context(context)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        _check(
            context,
            "agent_config",
            "Agent 配置",
            "error",
            "agent_config_invalid",
            f"Agent 配置无法解析: {exc}",
        )
        return _finish_local_context(context)

    context.profile = profile
    context.source_path = resolved_path
    context.document = document
    _check(
        context,
        "agent_config",
        "Agent 配置",
        "ok",
        "ok",
        f"已解析 {profile.name} 配置。",
    )

    raw_servers = document.get(profile.server_key)
    if not isinstance(raw_servers, dict):
        _check(
            context,
            "gateway_entry",
            "Gateway 入口",
            "error",
            "agent_config_invalid",
            f"{profile.server_key} 必须是对象。",
        )
        return _finish_local_context(context)

    entry, entries = _gateway_candidates(profile, document)
    context.gateway_entry = entry
    context.gateway_entries = entries
    if not entries:
        _check(
            context,
            "gateway_entry",
            "Gateway 入口",
            "error",
            "gateway_entry_missing",
            "Agent 配置中没有 mcp-hub Gateway 入口，请重新运行 agent setup。",
        )
        return _finish_local_context(context)
    if len(entries) > 1:
        equivalent = all(raw == entries[0][1] for _name, raw in entries[1:])
        _check(
            context,
            "gateway_entry",
            "Gateway 入口",
            "error",
            "gateway_entry_duplicate",
            (
                "Agent 配置中存在等价的重复 Gateway 入口。"
                if equivalent
                else "Agent 配置中存在相互冲突的 Gateway 入口，不能自动选择。"
            ),
            fixable=equivalent,
        )
    elif entries[0][0] != "mcp-hub":
        _check(
            context,
            "gateway_entry",
            "Gateway 入口",
            "warning",
            "gateway_entry_legacy",
            "检测到旧名称 mcp-hub-gateway，可安全规范为 mcp-hub。",
            fixable=True,
        )
    else:
        _check(
            context,
            "gateway_entry",
            "Gateway 入口",
            "ok",
            "ok",
            "Agent 仅配置了一个 mcp-hub Gateway 入口。",
        )

    if entry is None:
        return _finish_local_context(context)

    raw_command = entry.get("command")
    args = entry.get("args")
    command = raw_command.strip() if isinstance(raw_command, str) else ""
    command_name = _command_name(command)
    args_valid = isinstance(args, list) and bool(args) and args[0] == "serve"
    if command_name in _CURRENT_GATEWAY_COMMANDS and args_valid:
        _check(
            context,
            "gateway_command",
            "Gateway 命令",
            "ok",
            "ok",
            "Gateway 入口指向 mcp-hub serve。",
        )
    elif command_name in _LEGACY_GATEWAY_COMMANDS:
        _check(
            context,
            "gateway_command",
            "Gateway 命令",
            "warning",
            "gateway_command_legacy",
            "Gateway 仍使用旧命令名，可规范为 mcp-hub serve。",
            fixable=True,
        )
    else:
        _check(
            context,
            "gateway_command",
            "Gateway 命令",
            "error",
            "gateway_entry_invalid",
            "Gateway 入口必须使用 mcp-hub serve。",
        )

    if command and _command_available(command):
        _check(
            context,
            "gateway_executable",
            "CLI 可执行文件",
            "ok",
            "ok",
            "当前终端可以解析 Gateway 命令。",
        )
    else:
        _check(
            context,
            "gateway_executable",
            "CLI 可执行文件",
            "error",
            "command_not_found",
            "当前终端找不到 Gateway 命令，请检查 uv tool 安装目录和 PATH。",
        )

    raw_env = entry.get("env")
    env = (
        {str(key): str(value) for key, value in raw_env.items()}
        if isinstance(raw_env, dict)
        else {}
    )
    missing_env = [name for name in _REQUIRED_GATEWAY_ENV if not env.get(name, "").strip()]
    if missing_env:
        can_fix = bool(
            (context.hub_url or env.get(REPORT_URL_ENV, "").strip())
            and (context.telemetry_token or env.get(TELEMETRY_TOKEN_ENV, "").strip())
        )
        _check(
            context,
            "gateway_environment",
            "Gateway 环境",
            "error",
            "gateway_environment_incomplete",
            "Gateway 环境缺少必需字段: " + ", ".join(missing_env),
            fixable=can_fix,
        )
    elif env.get(AGENT_TYPE_ENV) != agent_type:
        _check(
            context,
            "gateway_environment",
            "Gateway 环境",
            "error",
            "gateway_agent_mismatch",
            "Gateway 环境中的 Agent 类型与当前 --agent 不一致。",
            fixable=True,
        )
    else:
        _check(
            context,
            "gateway_environment",
            "Gateway 环境",
            "ok",
            "ok",
            "Gateway 地址、令牌、Agent 类型和本地路径字段完整。",
        )

    if state_dir is None and env.get(STATE_DIR_ENV, "").strip():
        context.state_dir = Path(env[STATE_DIR_ENV]).expanduser()
    if env.get(GATEWAY_CONFIG_ENV, "").strip():
        context.gateway_config_path = Path(env[GATEWAY_CONFIG_ENV]).expanduser()
    else:
        context.gateway_config_path = get_gateway_config_path(
            context.state_dir,
            agent_type=agent_type,
        )
    if not context.hub_url:
        context.hub_url = env.get(REPORT_URL_ENV, "").strip().rstrip("/")
    if not context.telemetry_token:
        context.telemetry_token = env.get(TELEMETRY_TOKEN_ENV, "").strip()

    return _finish_local_context(context)


def _finish_local_context(context: _LocalContext) -> _LocalContext:
    if context.gateway_config_path.exists():
        specs, errors = load_gateway_config(context.gateway_config_path)
        context.specs = specs
        if errors:
            _check(
                context,
                "gateway_config",
                "Gateway 配置",
                "error",
                "gateway_config_invalid",
                f"Gateway 配置包含 {len(errors)} 个无效条目。",
            )
        else:
            _check(
                context,
                "gateway_config",
                "Gateway 配置",
                "ok",
                "ok",
                f"Gateway 配置已解析，共 {len(specs)} 个 Server。",
            )
    else:
        _check(
            context,
            "gateway_config",
            "Gateway 配置",
            "error",
            "gateway_config_not_found",
            f"未找到 {context.gateway_config_path}",
        )

    enabled = [spec for spec in context.specs if spec.enabled]
    if enabled:
        _check(
            context,
            "enabled_servers",
            "启用的 Server",
            "ok",
            "ok",
            f"已启用 {len(enabled)} 个 MCP Server。",
        )
    else:
        _check(
            context,
            "enabled_servers",
            "启用的 Server",
            "error",
            "gateway_no_enabled_servers",
            "Gateway 配置中没有启用的 MCP Server。",
        )

    for spec in enabled:
        if spec.transport == "stdio":
            if _command_available(spec.command):
                _check(
                    context,
                    f"server_executable:{spec.server_id}",
                    "Server 命令",
                    "ok",
                    "ok",
                    f"{spec.server_id} 的命令可执行。",
                    server_id=spec.server_id,
                )
            else:
                _check(
                    context,
                    f"server_executable:{spec.server_id}",
                    "Server 命令",
                    "error",
                    "command_not_found",
                    f"找不到 {spec.server_id} 的命令。",
                    server_id=spec.server_id,
                )
            if spec.cwd:
                if Path(spec.cwd).is_dir():
                    _check(
                        context,
                        f"server_cwd:{spec.server_id}",
                        "工作目录",
                        "ok",
                        "ok",
                        f"{spec.server_id} 的工作目录存在。",
                        server_id=spec.server_id,
                    )
                else:
                    _check(
                        context,
                        f"server_cwd:{spec.server_id}",
                        "工作目录",
                        "error",
                        "cwd_not_found",
                        f"{spec.server_id} 的工作目录不存在。",
                        server_id=spec.server_id,
                    )
        else:
            if _is_http_url(spec.url):
                _check(
                    context,
                    f"remote_url:{spec.server_id}",
                    "远程 Server",
                    "ok",
                    "ok",
                    f"{spec.server_id} 的远程 URL 格式有效。",
                    server_id=spec.server_id,
                )
            else:
                _check(
                    context,
                    f"remote_url:{spec.server_id}",
                    "远程 Server",
                    "error",
                    "remote_url_invalid",
                    f"{spec.server_id} 的远程 URL 无效。",
                    server_id=spec.server_id,
                )
            try:
                spec.resolved_headers(dict(os.environ))
            except ValueError:
                _check(
                    context,
                    f"remote_auth:{spec.server_id}",
                    "远程认证",
                    "error",
                    "remote_auth_missing",
                    f"{spec.server_id} 缺少远程认证所需的环境变量。",
                    server_id=spec.server_id,
                )

    if not context.state_dir.exists():
        _check(
            context,
            "state_dir",
            "状态目录",
            "error",
            "state_dir_missing",
            f"本地状态目录不存在: {context.state_dir}",
            fixable=True,
        )
        return context
    if not context.state_dir.is_dir():
        _check(
            context,
            "state_dir",
            "状态目录",
            "error",
            "state_dir_invalid",
            f"状态目录路径不是目录: {context.state_dir}",
        )
        return context

    spool_path = get_spool_path(context.state_dir)
    if not spool_path.exists():
        writable = os.access(context.state_dir, os.R_OK | os.W_OK)
        _check(
            context,
            "telemetry_queue",
            "遥测队列",
            "ok" if writable else "error",
            "ok" if writable else "queue_unwritable",
            (
                "遥测队列尚未创建，状态目录可读写。"
                if writable
                else "状态目录不可读写。"
            ),
        )
        return context

    try:
        queue_count, oldest = _inspect_spool(spool_path)
    except (OSError, sqlite3.Error) as exc:
        _check(
            context,
            "telemetry_queue",
            "遥测队列",
            "error",
            "queue_unreadable",
            f"遥测队列无法读写: {exc}",
        )
        return context

    context.queue_count = queue_count
    context.oldest_queued_at = oldest
    if queue_count:
        suffix = f"，最早事件 {oldest}" if oldest else ""
        _check(
            context,
            "telemetry_queue",
            "遥测队列",
            "warning",
            "queue_backlog",
            f"待上传事件 {queue_count} 个{suffix}。",
            fixable=bool(context.hub_url and context.telemetry_token),
        )
    else:
        _check(
            context,
            "telemetry_queue",
            "遥测队列",
            "ok",
            "ok",
            "本地遥测队列为空。",
        )
    return context


async def _request_json(
    method: str,
    url: str,
    *,
    token: str = "",
) -> tuple[int, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.request(method, url, headers=headers)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, payload if isinstance(payload, dict) else {}


def _version_family(value: str) -> tuple[int, int] | None:
    try:
        major, minor, *_rest = value.split(".")
        return int(major), int(minor)
    except (TypeError, ValueError):
        return None


async def _verify_online(
    context: _LocalContext,
) -> tuple[list[VerificationCheck], dict[str, object]]:
    checks: list[VerificationCheck] = []
    if not context.hub_url or not _is_http_url(context.hub_url):
        checks.append(
            VerificationCheck(
                "hub_health",
                "Hub 网络",
                "error",
                "hub_url_invalid",
                "没有可用的 Hub HTTP/HTTPS 地址。",
            )
        )
        return checks, {}
    if not context.telemetry_token:
        checks.append(
            VerificationCheck(
                "telemetry_token",
                "设备令牌",
                "error",
                "telemetry_token_missing",
                "未找到设备遥测令牌。",
            )
        )
        return checks, {}

    try:
        health_status, health = await _request_json(
            "GET",
            f"{context.hub_url}/api/v1/health",
        )
    except (httpx.TimeoutException, httpx.RequestError, OSError) as exc:
        checks.append(
            VerificationCheck(
                "hub_health",
                "Hub 网络",
                "error",
                "hub_unreachable",
                f"Hub 无法访问: {exc.__class__.__name__}",
            )
        )
        return checks, {}
    if health_status // 100 != 2:
        checks.append(
            VerificationCheck(
                "hub_health",
                "Hub 网络",
                "error",
                "hub_unreachable",
                f"Hub health 返回 HTTP {health_status}。",
            )
        )
        return checks, {}

    hub_version = str(health.get("version") or "")
    checks.append(
        VerificationCheck(
            "hub_health",
            "Hub 网络",
            "ok",
            "ok",
            f"Hub 可访问，版本 {hub_version or 'unknown'}。",
        )
    )

    try:
        token_status, token_payload = await _request_json(
            "POST",
            f"{context.hub_url}/api/v1/telemetry/token/validate",
            token=context.telemetry_token,
        )
    except (httpx.TimeoutException, httpx.RequestError, OSError) as exc:
        checks.append(
            VerificationCheck(
                "telemetry_token",
                "设备令牌",
                "error",
                "hub_unreachable",
                f"令牌验证请求失败: {exc.__class__.__name__}",
            )
        )
        return checks, {"hub_version": hub_version}
    if token_status == 401:
        checks.append(
            VerificationCheck(
                "telemetry_token",
                "设备令牌",
                "error",
                "telemetry_token_invalid",
                "设备令牌无效，或不属于此 Hub。",
            )
        )
        return checks, {"hub_version": hub_version}
    if token_status // 100 != 2:
        checks.append(
            VerificationCheck(
                "telemetry_token",
                "设备令牌",
                "error",
                "token_validation_failed",
                f"令牌验证返回 HTTP {token_status}。",
            )
        )
        return checks, {"hub_version": hub_version}

    try:
        data = _TokenValidationData.model_validate(token_payload.get("data"))
    except ValidationError:
        checks.append(
            VerificationCheck(
                "telemetry_token",
                "设备令牌",
                "error",
                "token_validation_failed",
                "令牌验证响应格式无效，请确认 Hub 与 CLI 版本兼容。",
            )
        )
        return checks, {"hub_version": hub_version}

    remote: dict[str, object] = {
        "hub_version": hub_version,
        "state": data.state,
        "label": data.label,
        "reason": data.reason,
        "gateway_version": data.gateway_version,
        "gateway_last_seen_at": data.gateway_last_seen_at,
        "first_call_at": data.first_call_at,
        "queue_depth": data.queue_depth,
        "server_count": data.server_count,
        "configuration_error_count": data.configuration_error_count,
    }
    if data.revoked or not data.valid:
        checks.append(
            VerificationCheck(
                "telemetry_token",
                "设备令牌",
                "error",
                "device_revoked",
                "设备令牌已撤销，请创建新设备并重新接入。",
            )
        )
        return checks, remote

    checks.append(
        VerificationCheck(
            "telemetry_token",
            "设备令牌",
            "ok",
            "ok",
            "设备令牌有效。",
        )
    )

    if data.online:
        checks.append(
            VerificationCheck(
                "gateway_online",
                "Gateway 在线",
                "ok",
                "ok",
                "最近 3 分钟内已收到 Gateway 心跳或运行事件。",
            )
        )
    else:
        code = "gateway_not_seen" if data.state in {
            "waiting_configuration",
            "waiting_restart",
        } else "gateway_offline"
        checks.append(
            VerificationCheck(
                "gateway_online",
                "Gateway 在线",
                "error",
                code,
                data.reason or "尚未收到 Gateway 心跳。",
            )
        )

    if data.first_call_at:
        checks.append(
            VerificationCheck(
                "first_tool_call",
                "首次工具调用",
                "ok",
                "ok",
                "已收到真实 MCP 工具调用。",
            )
        )
    else:
        checks.append(
            VerificationCheck(
                "first_tool_call",
                "首次工具调用",
                "warning",
                "first_call_missing",
                "Gateway 尚未上报真实 MCP 工具调用。",
            )
        )

    queue_depth = data.queue_depth
    checks.append(
        VerificationCheck(
            "telemetry_delivery",
            "遥测上传",
            "warning" if queue_depth else "ok",
            "queue_backlog" if queue_depth else "ok",
            (
                f"服务端看到本地待上传队列 {queue_depth} 条。"
                if queue_depth
                else "服务端未检测到待上传积压。"
            ),
            fixable=queue_depth > 0 and context.queue_count > 0,
        )
    )

    configuration_errors = data.configuration_error_count
    if configuration_errors:
        checks.append(
            VerificationCheck(
                "gateway_inventory",
                "Gateway 清单",
                "error",
                "gateway_configuration_error",
                f"{configuration_errors} 个 Server 存在配置或迁移错误。",
            )
        )
    else:
        checks.append(
            VerificationCheck(
                "gateway_inventory",
                "Gateway 清单",
                "ok",
                "ok",
                f"服务端已识别 {data.server_count} 个 Server。",
            )
        )

    versions = [
        ("Hub", hub_version),
        ("Gateway", data.gateway_version),
    ]
    incompatible = [
        name
        for name, version in versions
        if version
        and _version_family(version) is not None
        and _version_family(version) != _version_family(__version__)
    ]
    checks.append(
        VerificationCheck(
            "version_compatibility",
            "版本兼容",
            "error" if incompatible else "ok",
            "version_incompatible" if incompatible else "ok",
            (
                f"{', '.join(incompatible)} 与当前 CLI {__version__} 不兼容。"
                if incompatible
                else f"CLI、Hub 与已知 Gateway 版本兼容（CLI {__version__}）。"
            ),
        )
    )
    return checks, remote


def _build_repaired_document(
    context: _LocalContext,
) -> dict[str, Any] | None:
    if (
        context.profile is None
        or context.document is None
        or context.gateway_entry is None
    ):
        return None
    raw_servers = context.document.get(context.profile.server_key)
    if not isinstance(raw_servers, dict):
        return None
    if len(context.gateway_entries) > 1 and not all(
        raw == context.gateway_entries[0][1]
        for _name, raw in context.gateway_entries[1:]
    ):
        return None

    entry = copy.deepcopy(context.gateway_entry)
    command = str(entry.get("command") or "").strip()
    command_name = _command_name(command)
    args = entry.get("args")
    if command_name in _LEGACY_GATEWAY_COMMANDS:
        entry["command"] = "mcp-hub"
        entry["args"] = ["serve"]
    elif command_name in _CURRENT_GATEWAY_COMMANDS:
        if not isinstance(args, list) or not args or args[0] != "serve":
            if args in (None, []):
                entry["args"] = ["serve"]
            else:
                return None
    else:
        return None

    env = entry.get("env")
    normalized_env = (
        {str(key): str(value) for key, value in env.items()}
        if isinstance(env, dict)
        else {}
    )
    required_values = {
        REPORT_URL_ENV: context.hub_url,
        TELEMETRY_TOKEN_ENV: context.telemetry_token,
        AGENT_TYPE_ENV: context.agent_type,
        STATE_DIR_ENV: str(context.state_dir),
        GATEWAY_CONFIG_ENV: str(context.gateway_config_path),
    }
    for key, value in required_values.items():
        if not normalized_env.get(key, "").strip():
            if not value:
                return None
            normalized_env[key] = value
    normalized_env[AGENT_TYPE_ENV] = context.agent_type
    entry["env"] = normalized_env
    if context.profile.requires_stdio_type:
        entry["type"] = "stdio"

    new_servers = {
        name: value
        for name, value in raw_servers.items()
        if str(name) not in _GATEWAY_NAMES
    }
    new_servers["mcp-hub"] = entry
    repaired = {
        **context.document,
        context.profile.server_key: new_servers,
    }
    return repaired if repaired != context.document else None


def _planned_fixes(context: _LocalContext) -> list[PlannedFix]:
    fixes: list[PlannedFix] = []
    if not context.state_dir.exists():
        fixes.append(
            PlannedFix(
                "create_state_dir",
                f"创建本地状态目录 {context.state_dir}",
                False,
            )
        )
    if _build_repaired_document(context) is not None:
        fixes.append(
            PlannedFix(
                "normalize_gateway_entry",
                "备份 Agent 配置，并规范唯一的 mcp-hub serve 入口和必需环境字段。",
                True,
            )
        )
    if context.queue_count > 0 and context.hub_url and context.telemetry_token:
        fixes.append(
            PlannedFix(
                "retry_telemetry_queue",
                f"立即重试上传本地队列中的 {context.queue_count} 条事件。",
                False,
            )
        )
    return fixes


async def verify_agent(
    agent_type: str,
    *,
    source_config: Path | None = None,
    state_dir: Path | None = None,
    hub_url: str = "",
    telemetry_token: str = "",
) -> VerificationReport:
    """Run local and online checks without modifying local files or remote state."""
    context = _resolve_local_context(
        agent_type,
        source_config=source_config,
        state_dir=state_dir,
        hub_url=hub_url,
        telemetry_token=telemetry_token,
    )
    online_checks, remote = await _verify_online(context)
    checks = [*context.checks, *online_checks]
    return VerificationReport(
        agent_type=agent_type,
        checks=checks,
        paths={
            "agent_config": str(context.source_path or ""),
            "state_dir": str(context.state_dir),
            "gateway_config": str(context.gateway_config_path),
            "telemetry_queue": str(get_spool_path(context.state_dir)),
        },
        remote=remote,
        planned_fixes=_planned_fixes(context),
    )


async def apply_agent_fixes(
    agent_type: str,
    *,
    source_config: Path | None = None,
    state_dir: Path | None = None,
    hub_url: str = "",
    telemetry_token: str = "",
) -> list[dict[str, object]]:
    """Apply only fixes whose safety can be proven from the current local state."""
    context = _resolve_local_context(
        agent_type,
        source_config=source_config,
        state_dir=state_dir,
        hub_url=hub_url,
        telemetry_token=telemetry_token,
    )
    planned = _planned_fixes(context)
    applied: list[dict[str, object]] = []

    for fix in planned:
        if fix.code == "create_state_dir":
            try:
                context.state_dir.mkdir(parents=True, exist_ok=True)
                applied.append(
                    {
                        "code": fix.code,
                        "success": True,
                        "message": f"已创建 {context.state_dir}",
                    }
                )
            except OSError as exc:
                applied.append(
                    {
                        "code": fix.code,
                        "success": False,
                        "message": f"状态目录创建失败: {exc}",
                    }
                )
        elif fix.code == "normalize_gateway_entry":
            repaired = _build_repaired_document(context)
            if (
                repaired is None
                or context.profile is None
                or context.source_path is None
            ):
                applied.append(
                    {
                        "code": fix.code,
                        "success": False,
                        "message": "配置已发生变化，无法安全应用预览修复。",
                    }
                )
                continue
            try:
                backup = write_agent_document_with_backup(
                    context.profile,
                    context.source_path,
                    repaired,
                )
                applied.append(
                    {
                        "code": fix.code,
                        "success": True,
                        "message": "Gateway 入口已规范化。",
                        "backup_path": str(backup),
                    }
                )
            except OSError as exc:
                applied.append(
                    {
                        "code": fix.code,
                        "success": False,
                        "message": f"Agent 配置写入失败: {exc}",
                    }
                )
        elif fix.code == "retry_telemetry_queue":
            try:
                reporter = TelemetryReporter(
                    context.hub_url,
                    context.telemetry_token,
                    context.state_dir,
                    source="verify",
                )
                try:
                    before = reporter.spool.count()
                    await reporter.flush()
                    after = reporter.spool.count()
                finally:
                    reporter.spool.close()
                applied.append(
                    {
                        "code": fix.code,
                        "success": after < before,
                        "message": (
                            f"队列已从 {before} 条降至 {after} 条。"
                            if after < before
                            else f"队列仍有 {after} 条，请检查网络和令牌。"
                        ),
                    }
                )
            except (OSError, sqlite3.Error) as exc:
                applied.append(
                    {
                        "code": fix.code,
                        "success": False,
                        "message": f"队列重试失败: {exc}",
                    }
                )
    return applied
