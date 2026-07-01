"""安装与管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel

from mcp_hub.core.config_manager import get_config_for_agent
from mcp_hub.core.installer import Installer
from mcp_hub.core.process_manager import get_process_manager
from mcp_hub.core.registry import Registry
from mcp_hub.exceptions import (
    ConfigError,
    InstallError,
    ProcessStartupError,
    ServerAlreadyRunningError,
    ServerNotFoundError,
)
from mcp_hub.models.server import InstallConfig, ServerMeta
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["manage"])


class InstallRequest(BaseModel):
    server_id: str


@router.post("/servers/install")
async def install_server(req: InstallRequest, x_user_id: str = Header("anonymous")):
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
    display_name = server_data.get("display_name", req.server_id.split("/")[-1])

    # 1. 添加到 user_servers（标记为已追踪、已启用）
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import UserServerModel
    from sqlalchemy import delete, select

    async with async_session_factory() as session:
        # 检查是否已存在
        existing = await session.execute(
            select(UserServerModel)
            .where(UserServerModel.user_id == x_user_id, UserServerModel.server_id == req.server_id)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.enabled = True
            row.matched = True
        else:
            session.add(UserServerModel(
                user_id=x_user_id,
                server_id=req.server_id,
                matched=True,
                enabled=True,
            ))
        await session.commit()

    # 2. 更新状态和下载计数
    await registry.update_status(req.server_id, "stopped")
    await registry.increment_download(req.server_id)

    # 3. 生成各 Agent 配置片段
    configs = []
    for agent_key in ["claude-code", "cursor", "codex", "trae", "generic"]:
        cfg = get_config_for_agent(display_name, command, agent_key)
        configs.append(cfg)

    # 4. 记录安装历史
    try:
        async with async_session_factory() as session:
            from sqlalchemy import text
            await session.execute(
                text("INSERT INTO install_history (server_id, version, action, status) "
                     "VALUES (:sid, :ver, 'install', 'success')"),
                {"sid": req.server_id, "ver": server_data.get("version", "?")},
            )
            await session.commit()
    except Exception:
        pass

    return {
        "success": True,
        "data": {
            "server_id": req.server_id,
            "detail": "已添加到配置",
            "install_command": command,
            "configs": configs,
        },
        "message": f"✅ {display_name} 已添加到配置，请在本地终端运行安装命令",
    }


@router.get("/servers/")
async def list_servers():
    """列出已安装的 Server。"""
    registry = Registry()
    servers = await registry.get_installed()
    return {"success": True, "data": servers}


@router.get("/servers/{server_id:path}/status")
async def get_status(server_id: str):
    """获取 Server 运行状态。"""
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
async def start_server(server_id: str, x_user_id: str = Header("anonymous")):
    """启动 Server。"""
    # 检查是否已被当前用户禁用
    try:
        from mcp_hub.db.database import async_session_factory
        from mcp_hub.db.models import UserServerModel
        from sqlalchemy import select
        async with async_session_factory() as session:
            result = await session.execute(
                select(UserServerModel.enabled)
                .where(
                    UserServerModel.server_id == server_id,
                    UserServerModel.user_id == x_user_id,
                )
                .limit(1)
            )
            row = result.fetchone()
            if row is not None and row[0] is False:
                raise ConfigError(f"Server '{server_id}' 已被禁用，请在「我的 Server」中启用后再启动")
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

    parts = command.split()
    pm = get_process_manager()
    try:
        await pm.spawn(server_id, parts[0], parts[1:])
    except ServerAlreadyRunningError as e:
        raise e  # 直接透传，已是 McpHubError
    except ProcessStartupError as e:
        raise e  # 直接透传，已是 McpHubError

    await registry.update_status(server_id, "running")
    return {"success": True, "message": f"{server_id} 已启动"}


@router.post("/servers/{server_id:path}/stop")
async def stop_server(server_id: str):
    """停止 Server。"""
    registry = Registry()
    pm = get_process_manager()
    await pm.kill(server_id)
    await registry.update_status(server_id, "stopped")
    return {"success": True, "message": f"{server_id} 已停止"}


@router.post("/servers/{server_id:path}/uninstall")
async def uninstall_server(server_id: str):
    """卸载 Server。"""
    registry = Registry()
    pm = get_process_manager()

    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    # 停止进程
    await pm.kill(server_id)
    # 重置状态
    await registry.update_status(server_id, "not_installed")

    # 清理残留
    try:
        cmd = server.get("install_command", "")
        if cmd and "pip" in cmd:
            pkg = server.get("install_package", "")
            if pkg:
                import asyncio
                proc = await asyncio.create_subprocess_exec(
                    "pip", "uninstall", "-y", pkg,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.wait()
    except Exception as e:
        logger.warning("manage.uninstall.pip_cleanup_failed", server_id=server_id, error=str(e))

    return {"success": True, "message": f"{server_id} 已卸载"}


@router.get("/servers/{server_id:path}/config")
async def get_server_config(
    server_id: str,
    agent: str = "generic",
):
    """获取 Server 配置（用于复制到本地 Agent）。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    command = server.get("install_command", "")
    from mcp_hub.core.config_manager import get_config_for_agent
    return {
        "success": True,
        "data": get_config_for_agent(
            server_name=server_id.split("/")[-1],
            command=command,
            agent=agent,
        ),
    }


@router.get("/servers/config/download")
async def download_all_config(_agent: str = "generic"):
    """下载所有已安装 Server 的配置（mcp.json 格式），用于导入本地 Agent。"""
    import tempfile

    from fastapi.responses import FileResponse

    registry = Registry()
    installed = await registry.get_installed()
    if not installed:
        raise ServerNotFoundError("（已安装列表）")

    config = {"mcpServers": {}}
    for s in installed:
        cmd = s.get("install_command", "")
        name = s["id"].split("/")[-1]
        config["mcpServers"][name] = {"command": cmd}

    # 写入临时文件并返回
    import json

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2, ensure_ascii=False)

    return FileResponse(
        tmp.name,
        media_type="application/json",
        filename="mcp-hub-config.json",
        headers={"Content-Disposition": "attachment; filename=mcp-hub-config.json"},
    )


@router.get("/servers/{server_id:path}/logs")
async def get_logs(
    server_id: str,
    lines: int = 50,
):
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
):
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

    results: list[dict] = []
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
                results.append({
                    "server": srv_name,
                    "line_number": i + 1,
                    "match": line.rstrip("\n"),
                    "context_before": ctx_before,
                    "context_after": ctx_after,
                })

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
