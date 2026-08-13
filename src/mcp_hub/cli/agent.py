"""本地 MCP Hub Agent 遥测配置命令。"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Literal

import click
import tomli_w

from mcp_hub.agent_types import AGENT_TYPES, DEFAULT_AGENT_TYPE
from mcp_hub.core.agent_config import (
    apply_agent_migration,
    create_timestamped_backup,
    get_agent_profile,
    prepare_agent_migration,
    read_agent_document,
    restore_file_from_backup,
)
from mcp_hub.core.agent_recovery import (
    RecoveryPreview,
    apply_agent_recovery,
    create_migration_manifest,
    ensure_setup_can_create_manifest,
    list_migration_manifests,
    manifest_summary,
    prepare_agent_recovery,
)
from mcp_hub.core.agent_verify import (
    VerificationReport,
    apply_agent_fixes,
    verify_agent,
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
    try:
        ensure_setup_can_create_manifest(
            agent_type,
            source_path=migration.source_path,
            state_dir=agent_state_dir,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

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
        reporter = TelemetryReporter(
            hub_url,
            telemetry_token,
            agent_state_dir,
            source="setup",
        )
        asyncio.run(reporter.report_validation_stage("setup_started", source="setup"))
        reporter.spool.close()
    except Exception:
        pass

    gateway_existed = gateway_config_path.is_file()
    gateway_backup_path: Path | None = None
    backup_path: Path | None = None
    try:
        gateway_backup_path = (
            create_timestamped_backup(gateway_config_path)
            if gateway_existed
            else None
        )
        write_gateway_config(list(migration.specs), gateway_config_path)
        backup_path = apply_agent_migration(
            migration,
            report_url=hub_url,
            telemetry_token=telemetry_token,
            state_dir=agent_state_dir,
            gateway_config_path=gateway_config_path,
        )
        manifest = create_migration_manifest(
            migration,
            backup_path=backup_path,
            gateway_config_path=gateway_config_path,
            state_dir=agent_state_dir,
        )
    except (OSError, TypeError, ValueError) as exc:
        rollback_errors: list[str] = []
        if backup_path is not None:
            try:
                restore_file_from_backup(migration.source_path, backup_path)
            except OSError as rollback_exc:
                rollback_errors.append(f"Agent 配置回滚失败: {rollback_exc}")
        try:
            if gateway_backup_path is not None:
                restore_file_from_backup(gateway_config_path, gateway_backup_path)
            elif not gateway_existed and gateway_config_path.exists():
                gateway_config_path.unlink()
        except OSError as rollback_exc:
            rollback_errors.append(f"Gateway 配置回滚失败: {rollback_exc}")

        detail = (
            "；".join(rollback_errors)
            if rollback_errors
            else "已恢复迁移前配置"
        )
        backup_hint = f"；原配置备份: {backup_path}" if backup_path else ""
        raise click.ClickException(
            f"配置迁移失败: {exc}；{detail}{backup_hint}"
        ) from exc

    assert backup_path is not None
    click.echo(f"配置完成，原文件备份: {backup_path}")
    click.echo(
        "迁移清单: "
        f"{agent_state_dir / 'migration-manifest.json'} ({manifest.migration_id})"
    )
    click.echo(f"Gateway 管理配置: {gateway_config_path}")
    if gateway_backup_path:
        click.echo(f"原 Gateway 配置备份: {gateway_backup_path}")
    try:
        reporter = TelemetryReporter(
            hub_url,
            telemetry_token,
            agent_state_dir,
            source="setup",
        )

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
                source="setup",
            )
            await reporter.close()

        asyncio.run(_report_inventory())
    except Exception:
        click.echo("警告：本地配置已完成，但发现清单暂未上传，将在 Gateway 启动后重试。")
    click.echo("重启 Agent 后，所有已迁移 Server 调用会经过 mcp-hub 并上报监控指标。")


@agent.command("backups")
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
    help="本地 Agent 状态目录；默认使用对应 Agent 的标准目录。",
)
@click.option("--json", "json_output", is_flag=True, help="输出稳定 JSON 结果。")
def agent_backups(
    agent_type: str,
    state_dir: Path | None,
    json_output: bool,
) -> None:
    """列出可用于安全断开和恢复的迁移清单与备份。"""
    try:
        manifests = list_migration_manifests(
            state_dir,
            agent_type=agent_type,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    summaries = [manifest_summary(path, manifest) for path, manifest in manifests]
    if json_output:
        click.echo(
            json.dumps(
                {
                    "success": True,
                    "agent_type": agent_type,
                    "backups": summaries,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if not summaries:
        click.echo("没有找到迁移清单。首次接入请运行 agent setup。")
        return
    for item in summaries:
        migrated_names = item["migrated_server_names"]
        migrated_count = len(migrated_names) if isinstance(migrated_names, list) else 0
        click.echo(
            f"{item['migration_time']}  {item['status']}  "
            f"{migrated_count} 个 Server"
        )
        click.echo(f"  Agent 配置: {item['source_config_path']}")
        backup_state = "存在" if item["original_backup_exists"] else "缺失"
        click.echo(f"  原始备份: {item['original_backup_path']} ({backup_state})")
        if item["disconnect_backup_path"]:
            disconnect_state = (
                "存在" if item["disconnect_backup_exists"] else "缺失"
            )
            click.echo(
                f"  断开前备份: {item['disconnect_backup_path']} "
                f"({disconnect_state})"
            )


def _render_recovery_preview(preview: RecoveryPreview, *, operation: str) -> None:
    title = "断开本地 Gateway" if operation == "disconnect" else "恢复 Agent 配置"
    click.echo(f"{title}: {preview.source_path}")
    if preview.already_disconnected:
        click.echo("此迁移清单已完成断开，当前命令不会再次写入配置。")
        return
    click.echo(
        "当前文件"
        + ("仍等于迁移后版本。" if preview.post_hash_matches else "已有后续修改，将执行安全合并。")
    )
    if preview.restore_server_names:
        click.echo("将恢复直连 Server: " + ", ".join(preview.restore_server_names))
    if preview.already_restored_server_names:
        click.echo(
            "已是原配置的 Server: "
            + ", ".join(preview.already_restored_server_names)
        )
    click.echo(
        "将移除本次 Gateway 入口。"
        if preview.remove_gateway
        else "当前未发现可移除的本次 Gateway 入口。"
    )
    if preview.preserved_server_names:
        click.echo(
            "将保留其他 Server: " + ", ".join(preview.preserved_server_names)
        )
    if preview.changed_top_level_keys:
        click.echo(
            "将保留迁移后的顶层设置改动: "
            + ", ".join(preview.changed_top_level_keys)
        )
    if preview.conflicts:
        click.echo("无法自动合并的冲突：")
        for conflict in preview.conflicts:
            click.echo(
                f"  - [{conflict.code}] {conflict.path}: {conflict.message}"
            )


def _run_agent_recovery(
    context: click.Context,
    *,
    operation: str,
    agent_type: str,
    state_dir: Path | None,
    manifest_path: Path | None,
    json_output: bool,
    yes: bool,
) -> None:
    validation_reporter: TelemetryReporter | None = None

    def prepare_validation_reporter(source_path: Path) -> TelemetryReporter | None:
        try:
            profile, _source_path, document = read_agent_document(agent_type, source_path)
            raw_servers = document.get(profile.server_key)
            if not isinstance(raw_servers, dict):
                return None
            gateway_entry = raw_servers.get("mcp-hub")
            if not isinstance(gateway_entry, dict):
                return None
            env = gateway_entry.get("env")
            if not isinstance(env, dict):
                return None
            hub_url = str(env.get(REPORT_URL_ENV) or "").strip()
            telemetry_token = str(env.get(TELEMETRY_TOKEN_ENV) or "").strip()
            if not hub_url or not telemetry_token:
                return None
            resolved_state_dir = state_dir or get_agent_state_dir(agent_type)
            return TelemetryReporter(
                hub_url,
                telemetry_token,
                resolved_state_dir,
                source="legacy",
            )
        except Exception:
            return None

    def report_stage(
        reporter: TelemetryReporter,
        stage: Literal["disconnect_completed", "restore_completed"],
    ) -> None:
        try:
            asyncio.run(reporter.report_validation_stage(stage, source="recovery"))
        except Exception:
            return
        finally:
            with suppress(Exception):
                reporter.spool.close()

    try:
        preview = prepare_agent_recovery(
            agent_type,
            state_dir=state_dir,
            manifest_path=manifest_path,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if preview.conflicts:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        **preview.to_dict(),
                        "operation": operation,
                        "confirmation_required": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            context.exit(1)
        _render_recovery_preview(preview, operation=operation)
        raise click.ClickException(
            "当前配置无法安全自动合并；请按冲突路径手工处理后重试。"
        )

    if preview.already_disconnected:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        **preview.to_dict(),
                        "operation": operation,
                        "confirmation_required": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            _render_recovery_preview(preview, operation=operation)
        return

    if json_output and not yes:
        click.echo(
            json.dumps(
                {
                    **preview.to_dict(),
                    "operation": operation,
                    "confirmation_required": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        context.exit(1)

    if not json_output:
        _render_recovery_preview(preview, operation=operation)
        if not yes and not click.confirm(
            "继续前会再次校验配置并创建断开前备份，是否继续？",
            default=False,
        ):
            click.echo("已取消，未修改任何配置。")
            return

    validation_reporter = prepare_validation_reporter(preview.source_path)
    try:
        result = apply_agent_recovery(
            agent_type,
            state_dir=state_dir,
            manifest_path=manifest_path,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if result.changed and validation_reporter is not None:
        recovery_stage: Literal["disconnect_completed", "restore_completed"] = (
            "disconnect_completed"
            if operation == "disconnect"
            else "restore_completed"
        )
        report_stage(validation_reporter, recovery_stage)

    if json_output:
        click.echo(
            json.dumps(
                {
                    **result.to_dict(),
                    "operation": operation,
                    "confirmation_required": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if operation == "disconnect":
        if result.changed:
            click.echo(f"已断开 Gateway 并恢复原 Server 直连，备份: {result.backup_path}")
        else:
            click.echo("当前配置已处于断开结果，未重复写入。")
        click.echo("请完全退出并重新打开 Agent，使直连配置生效。")
    else:
        if result.changed:
            click.echo(f"已恢复 Agent 配置，恢复前备份: {result.backup_path}")
        else:
            click.echo("当前配置已是恢复结果，未重复写入。")
        click.echo("请完全退出并重新打开 Agent，使恢复配置生效。")
    click.echo("设备令牌不会自动撤销；如需停止 Hub 上报，请在网页单独撤销设备。")


@agent.command("disconnect")
@click.option(
    "--agent",
    "agent_type",
    type=click.Choice(AGENT_TYPES),
    default=DEFAULT_AGENT_TYPE,
    show_default=True,
)
@click.option("--state-dir", type=click.Path(path_type=Path), default=None)
@click.option("--json", "json_output", is_flag=True, help="输出稳定 JSON 结果。")
@click.option("--yes", is_flag=True, help="确认预览并执行安全断开。")
@click.pass_context
def agent_disconnect(
    context: click.Context,
    agent_type: str,
    state_dir: Path | None,
    json_output: bool,
    yes: bool,
) -> None:
    """恢复原 Server 直连并移除本次 setup 创建的 Gateway 入口。"""
    _run_agent_recovery(
        context,
        operation="disconnect",
        agent_type=agent_type,
        state_dir=state_dir,
        manifest_path=None,
        json_output=json_output,
        yes=yes,
    )


@agent.command("restore")
@click.option(
    "--agent",
    "agent_type",
    type=click.Choice(AGENT_TYPES),
    default=DEFAULT_AGENT_TYPE,
    show_default=True,
)
@click.option("--state-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="指定迁移清单；默认使用状态目录中的 migration-manifest.json。",
)
@click.option("--json", "json_output", is_flag=True, help="输出稳定 JSON 结果。")
@click.option("--yes", is_flag=True, help="确认预览并执行安全恢复。")
@click.pass_context
def agent_restore(
    context: click.Context,
    agent_type: str,
    state_dir: Path | None,
    manifest_path: Path | None,
    json_output: bool,
    yes: bool,
) -> None:
    """从当前或指定迁移清单安全恢复原 Agent Server 条目。"""
    _run_agent_recovery(
        context,
        operation="restore",
        agent_type=agent_type,
        state_dir=state_dir,
        manifest_path=manifest_path,
        json_output=json_output,
        yes=yes,
    )


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
    reporter = TelemetryReporter(
        hub_url,
        telemetry_token,
        agent_state_dir,
        source="discovery",
    )

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
            source="discovery",
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


def _render_verification_report(report: VerificationReport) -> None:
    status_labels = {
        "ok": "正常",
        "warning": "等待",
        "error": "异常",
        "skipped": "跳过",
    }
    for check in report.checks:
        suffix = f" [{check.code}]" if check.code != "ok" else ""
        click.echo(
            f"{check.label:<14} {status_labels[check.status]}{suffix}：{check.message}"
        )
    if report.applied_fixes:
        click.echo("")
        click.echo("已应用修复：")
        for fix in report.applied_fixes:
            status = "完成" if fix.get("success") else "失败"
            click.echo(f"  - {status} {fix.get('message', '')}")
            if fix.get("backup_path"):
                click.echo(f"    备份: {fix['backup_path']}")
    click.echo("")
    click.echo("接入验证完成。" if report.ready else "接入尚未完成，请按异常项处理。")


@agent.command("verify")
@click.option(
    "--agent",
    "agent_type",
    type=click.Choice(AGENT_TYPES),
    default=DEFAULT_AGENT_TYPE,
    show_default=True,
)
@click.option(
    "--source-config",
    type=click.Path(path_type=Path),
    default=None,
    help="Agent 配置路径；未指定时查找该 Agent 的标准路径。",
)
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="本地状态目录；优先于 Agent Gateway 入口中的路径。",
)
@click.option(
    "--hub-url",
    default=lambda: os.environ.get(REPORT_URL_ENV, ""),
    help="Hub 地址；未指定时读取 Agent Gateway 入口。",
)
@click.option(
    "--telemetry-token",
    envvar=TELEMETRY_TOKEN_ENV,
    default="",
    help="设备遥测令牌；未指定时读取 Agent Gateway 入口。",
)
@click.option("--json", "json_output", is_flag=True, help="输出稳定 JSON 结果。")
@click.option("--fix", is_flag=True, help="预览并应用可证明安全的修复。")
@click.option("--yes", is_flag=True, help="确认应用 --fix 预览中的全部安全修复。")
@click.pass_context
def agent_verify_command(
    context: click.Context,
    agent_type: str,
    source_config: Path | None,
    state_dir: Path | None,
    hub_url: str,
    telemetry_token: str,
    json_output: bool,
    fix: bool,
    yes: bool,
) -> None:
    """验证 Agent 配置、Gateway、Hub、设备令牌和首次真实调用。"""

    async def _verify() -> VerificationReport:
        return await verify_agent(
            agent_type,
            source_config=source_config,
            state_dir=state_dir,
            hub_url=hub_url,
            telemetry_token=telemetry_token,
        )

    report = asyncio.run(_verify())
    if fix and report.planned_fixes:
        if json_output and not yes:
            report.confirmation_required = True
            click.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            context.exit(1)

        if not json_output:
            click.echo("计划应用以下安全修复：")
            for planned in report.planned_fixes:
                backup = "（写入前备份）" if planned.requires_backup else ""
                click.echo(f"  - {planned.description}{backup}")
            if not yes and not click.confirm("确认应用以上修复？", default=False):
                click.echo("已取消，未修改任何配置。")
                _render_verification_report(report)
                context.exit(1)

        applied = asyncio.run(
            apply_agent_fixes(
                agent_type,
                source_config=source_config,
                state_dir=state_dir,
                hub_url=hub_url,
                telemetry_token=telemetry_token,
            )
        )
        rerun = asyncio.run(_verify())
        rerun.applied_fixes = applied
        report = rerun

    if json_output:
        click.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        _render_verification_report(report)

    try:
        resolved_hub_url = hub_url
        resolved_token = telemetry_token
        if not resolved_hub_url or not resolved_token:
            profile, _path, document = read_agent_document(agent_type, source_config)
            raw_servers = document.get(profile.server_key)
            gateway_entry = raw_servers.get("mcp-hub") if isinstance(raw_servers, dict) else None
            env = gateway_entry.get("env") if isinstance(gateway_entry, dict) else None
            if not resolved_hub_url and isinstance(env, dict):
                resolved_hub_url = str(env.get(REPORT_URL_ENV) or "").strip()
            if not resolved_token and isinstance(env, dict):
                resolved_token = str(env.get(TELEMETRY_TOKEN_ENV) or "").strip()
        if resolved_hub_url and resolved_token:
            reporter = TelemetryReporter(
                resolved_hub_url,
                resolved_token,
                state_dir or get_agent_state_dir(agent_type),
                source="verify",
            )
            try:
                asyncio.run(
                    reporter.report_validation_stage(
                        "verify_succeeded" if report.ready else "verify_failed",
                        source="verify",
                    )
                )
            finally:
                reporter.spool.close()
    except Exception:
        pass

    if not report.ready:
        context.exit(1)
