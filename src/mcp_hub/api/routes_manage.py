"""安装与管理 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from mcp_hub.api.dependencies import get_current_user, get_process_admin
from mcp_hub.core.config_manager import AGENT_CONFIGS, get_config_for_agent, server_config_name
from mcp_hub.core.gateway_config import split_legacy_command
from mcp_hub.core.process_manager import get_process_manager
from mcp_hub.core.registry import Registry
from mcp_hub.exceptions import (
    ConfigError,
    ProcessStartupError,
    ServerAlreadyRunningError,
    ServerNotFoundError,
)
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["manage"])


class InstallRequest(BaseModel):
    server_id: str


@router.post("/servers/install")
async def install_server(
    req: InstallRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """将 Server 添加到用户的配置中（非实际安装）。

    在 Web 界面点击「一键安装」时，不尝试在服务器上运行 pip/npm 安装，
    而是:
    1. 将 Server 标记为已启用/已安装到 user_servers
    2. 生成各 Agent 的配置片段
    3. 返回安装命令提示用户本地运行
    """
    registry = Registry()
    server_data = await registry.get_by_id(req.server_id)
    if not server_data:
        raise ServerNotFoundError(req.server_id)

    command = server_data.get("install_command", "")
    config_template = server_data.get("config_template", {})
    display_name = server_data.get("display_name", req.server_id.split("/")[-1])

    # 1. 添加到 user_servers（标记为已追踪、已启用）
    from sqlalchemy import select

    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import UserServerModel

    async with async_session_factory() as session:
        # 检查是否已存在
        existing = await session.execute(
            select(UserServerModel).where(
                UserServerModel.user_id == user_id, UserServerModel.server_id == req.server_id
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.enabled = True
            row.matched = True
        else:
            session.add(
                UserServerModel(
                    user_id=user_id,
                    server_id=req.server_id,
                    matched=True,
                    enabled=True,
                )
            )
        await session.commit()

    # 2. 下载计数是市场级指标；运行状态由每个用户的本地 Gateway 上报。
    await registry.increment_download(req.server_id)

    # 3. 生成各 Agent 配置片段
    configs: list[dict[str, Any]] = []
    for agent_key in AGENT_CONFIGS:
        cfg = get_config_for_agent(
            server_config_name(req.server_id, server_data),
            command,
            agent_key,
            config_template=config_template if isinstance(config_template, dict) else None,
        )
        configs.append(cfg)

    # 4. 记录安装历史
    try:
        async with async_session_factory() as session:
            from sqlalchemy import text

            await session.execute(
                text(
                    "INSERT INTO install_history "
                    "(server_id, user_id, version, action, status) "
                    "VALUES (:sid, :uid, :ver, 'install', 'success')"
                ),
                {
                    "sid": req.server_id,
                    "uid": user_id,
                    "ver": server_data.get("version", "?"),
                },
            )
            await session.commit()
    except Exception:
        logger.warning("记录安装历史失败", exc_info=True)

    return {
        "success": True,
        "data": {
            "server_id": req.server_id,
            "detail": "已添加到配置",
            "install_command": command,
            "config_template": config_template if isinstance(config_template, dict) else {},
            "configs": configs,
        },
        "message": f"✅ {display_name} 已添加到配置，请在本地终端运行安装命令",
    }


@router.get("/servers/")
async def list_servers(
    _admin_id: str = Depends(get_process_admin),
) -> dict[str, Any]:
    """列出 Hub 主机上由管理员集中管理的 Server。"""
    registry = Registry()
    servers = await registry.get_installed()
    return {"success": True, "data": servers}


@router.get("/servers/{server_id:path}/status")
async def get_status(
    server_id: str,
    _admin_id: str = Depends(get_process_admin),
) -> dict[str, Any]:
    """获取 Hub 主机上的 Server 运行状态。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    pm = get_process_manager()
    running = pm.is_running(server_id)

    return {
        "success": True,
        "data": {
            "server_id": server_id,
            "status": server.get("status", "not_installed"),
            "running": running,
            "version": server.get("version", ""),
        },
    }


@router.post("/servers/{server_id:path}/start")
async def start_server(
    server_id: str,
    user_id: str = Depends(get_process_admin),
) -> dict[str, Any]:
    """在显式启用的自托管 Hub 上启动 Server。"""
    # 检查是否已被当前用户禁用
    try:
        from sqlalchemy import select

        from mcp_hub.db.database import async_session_factory
        from mcp_hub.db.models import UserServerModel

        async with async_session_factory() as session:
            result = await session.execute(
                select(UserServerModel.enabled)
                .where(
                    UserServerModel.server_id == server_id,
                    UserServerModel.user_id == user_id,
                )
                .limit(1)
            )
            row = result.fetchone()
            if row is not None and row[0] is False:
                raise ConfigError(
                    f"Server '{server_id}' 已被禁用，请在「我的 Server」中启用后再启动"
                )
    except ConfigError:
        raise
    except Exception as e:
        logger.warning("manage.start.enabled_check_failed", server_id=server_id, error=str(e))

    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    command = server.get("install_command", "")
    if not command:
        raise ConfigError("没有安装命令", {"server_id": server_id})

    try:
        executable, args = split_legacy_command(command)
    except ValueError as exc:
        raise ConfigError(str(exc), {"server_id": server_id}) from exc
    from mcp_hub.core.config_manager import ConfigManager

    env = await ConfigManager().list_all_config(server_id)
    pm = get_process_manager()
    try:
        await pm.spawn(server_id, executable, list(args), env=env)
    except ServerAlreadyRunningError as e:
        raise e  # 直接透传，已是 McpHubError
    except ProcessStartupError as e:
        raise e  # 直接透传，已是 McpHubError

    await registry.update_status(server_id, "running")
    return {"success": True, "message": f"{server_id} 已启动"}


@router.post("/servers/{server_id:path}/stop")
async def stop_server(
    server_id: str,
    _admin_id: str = Depends(get_process_admin),
) -> dict[str, Any]:
    """在显式启用的自托管 Hub 上停止 Server。"""
    registry = Registry()
    pm = get_process_manager()
    await pm.kill(server_id)
    await registry.update_status(server_id, "stopped")
    return {"success": True, "message": f"{server_id} 已停止"}


@router.post("/servers/{server_id:path}/uninstall")
async def uninstall_server(
    server_id: str,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """从当前用户配置中移除 Server，不操作 Hub 主机或用户电脑的软件。"""
    registry = Registry()

    server = await registry.get_by_id(server_id, include_hidden=True)
    if not server:
        raise ServerNotFoundError(server_id)

    from sqlalchemy import delete

    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import InstallHistoryModel, UserServerModel

    async with async_session_factory() as session:
        await session.execute(
            delete(UserServerModel).where(
                UserServerModel.server_id == server_id,
                UserServerModel.user_id == user_id,
            )
        )
        session.add(
            InstallHistoryModel(
                server_id=server_id,
                user_id=user_id,
                version=str(server.get("version", "")),
                action="uninstall",
                status="success",
            )
        )
        await session.commit()

    return {"success": True, "message": f"{server_id} 已从你的配置中移除"}


@router.get("/servers/{server_id:path}/config")
async def get_server_config(
    server_id: str,
    agent: str = "generic",
) -> dict[str, Any]:
    """获取 Server 配置（用于复制到本地 Agent）。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    command = server.get("install_command", "")
    config_template = server.get("config_template", {})

    return {
        "success": True,
        "data": get_config_for_agent(
            server_name=server_config_name(server_id, server),
            command=command,
            agent=agent,
            config_template=config_template if isinstance(config_template, dict) else None,
        ),
    }


@router.get("/servers/config/download")
async def download_all_config(
    _agent: str = "generic",
    _admin_id: str = Depends(get_process_admin),
) -> Response:
    """下载所有已安装 Server 的配置（mcp.json 格式），用于导入本地 Agent。"""
    registry = Registry()
    installed = await registry.get_installed()
    if not installed:
        raise ServerNotFoundError("（已安装列表）")

    from mcp_hub.core.config_manager import command_config

    server_configs: dict[str, dict[str, object]] = {}
    for s in installed:
        cmd = s.get("install_command", "")
        name = server_config_name(s["id"], s)
        config_template = s.get("config_template", {})
        if isinstance(config_template, dict) and config_template:
            server_configs[name] = config_template
        elif cmd:
            server_configs[name] = command_config(cmd)
    config: dict[str, Any] = {"mcpServers": server_configs}

    import json

    return Response(
        content=json.dumps(config, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=mcp-hub-config.json"},
    )


@router.get("/servers/{server_id:path}/logs")
async def get_logs(
    server_id: str,
    lines: int = 50,
    _admin_id: str = Depends(get_process_admin),
) -> dict[str, Any]:
    """获取 Server 日志。"""
    from pathlib import Path

    safe_name = server_id.replace("/", "_").replace("@", "")
    log_file = Path.home() / ".config" / "mcp-hub" / "logs" / f"{safe_name}.log"
    if not log_file.exists():
        return {"success": True, "data": [], "message": "日志文件不存在"}

    with open(log_file, encoding="utf-8") as f:
        all_lines = f.readlines()
    return {"success": True, "data": all_lines[-lines:]}


@router.get("/logs/search")
async def search_logs(
    q: str = "",
    server_id: str | None = None,
    lines: int = 100,
    _admin_id: str = Depends(get_process_admin),
) -> dict[str, Any]:
    """跨 Server 日志关键词搜索。

    支持:
    - 搜索所有 Server 日志或指定某个 Server
    - 返回匹配行及其上下文
    - 默认返回最近 100 条匹配
    """
    import re
    from pathlib import Path

    if not q:
        return {"success": False, "error": "请提供搜索关键词"}

    log_dir = Path.home() / ".config" / "mcp-hub" / "logs"
    if not log_dir.exists():
        return {"success": True, "data": [], "servers_scanned": 0}

    # 确定要搜索的日志文件
    if server_id:
        safe_name = server_id.replace("/", "_").replace("@", "")
        log_files = [log_dir / f"{safe_name}.log"]
    else:
        log_files = sorted(log_dir.glob("*.log"), reverse=True)

    results: list[dict[str, Any]] = []
    servers_scanned = 0

    for log_file in log_files:
        if not log_file.exists():
            continue
        servers_scanned += 1
        srv_name = log_file.stem

        try:
            with open(log_file, encoding="utf-8", errors="replace") as f:
                file_lines = f.readlines()
        except OSError:
            continue

        try:
            pattern = re.compile(re.escape(q), re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(q))

        for i, line in enumerate(file_lines):
            if pattern.search(line):
                # 返回匹配行及前后各 2 行上下文
                ctx_before = [
                    file_lines[j].rstrip("\n")
                    for j in range(max(0, i - 2), i)
                    if j < len(file_lines)
                ]
                ctx_after = [
                    file_lines[j].rstrip("\n")
                    for j in range(i + 1, min(len(file_lines), i + 3))
                    if j < len(file_lines)
                ]
                results.append(
                    {
                        "server": srv_name,
                        "line_number": i + 1,
                        "match": line.rstrip("\n"),
                        "context_before": ctx_before,
                        "context_after": ctx_after,
                    }
                )

        if len(results) >= lines:
            break

    # 限制返回数量
    results = results[:lines]

    return {
        "success": True,
        "data": results,
        "query": q,
        "servers_scanned": servers_scanned,
        "total_matches": len(results),
    }


@router.get("/servers/check-updates")
async def check_updates(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """检查用户已安装的 Server 是否有新版本可用。"""
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import UserServerModel

    registry = Registry()
    updates: list[dict[str, Any]] = []

    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel).where(UserServerModel.user_id == user_id)
        )
        user_servers = result.scalars().all()

    # 批量查询所有 Server（避免 N+1）
    all_servers = await registry.get_all()
    server_map = {s["id"]: s for s in all_servers}

    for us in user_servers:
        server = server_map.get(us.server_id)
        if not server:
            continue
        current = server.get("current_version", "")
        latest = server.get("latest_version", "")
        if latest and current and latest != current:
            updates.append(
                {
                    "server_id": us.server_id,
                    "name": server.get("name", us.server_id),
                    "current_version": current,
                    "latest_version": latest,
                }
            )

    # 自动为有更新的 Server 创建通知
    if updates:
        try:
            from mcp_hub.api.routes_notifications import create_notification

            for u in updates[:3]:  # 最多 3 条通知
                await create_notification(
                    user_id=user_id,
                    notif_type="update",
                    title=f"新版本可用: {u['name']}",
                    message=f"v{u['current_version']} → v{u['latest_version']}",
                    server_id=u["server_id"],
                    link=f"/servers/{u['server_id']}",
                )
        except Exception:
            logger.warning("创建更新通知失败", exc_info=True)

    return {
        "success": True,
        "data": {"updates": updates, "count": len(updates)},
    }
