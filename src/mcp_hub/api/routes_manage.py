"""安装与管理 API。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from mcp_hub.core.installer import Installer
from mcp_hub.core.process_manager import get_process_manager
from mcp_hub.core.registry import Registry
from mcp_hub.exceptions import (
    ConfigError,
    ProcessStartupError,
    ServerAlreadyRunningError,
    ServerNotFoundError,
)
from mcp_hub.models.server import InstallConfig, ServerMeta

router = APIRouter(tags=["manage"])


class InstallRequest(BaseModel):
    server_id: str


@router.post("/servers/install")
async def install_server(req: InstallRequest):
    """安装 Server。"""
    registry = Registry()
    server_data = await registry.get_by_id(req.server_id)
    if not server_data:
        raise ServerNotFoundError(req.server_id)

    meta = ServerMeta(
        name=server_data["id"],
        version=server_data.get("latest_version", server_data.get("version", "1.0.0")),
        install=InstallConfig(
            type=server_data.get("install_type", "pip"),
            package=server_data.get("install_package", ""),
            command=server_data.get("install_command", ""),
        ),
    )

    installer = Installer()
    result = await installer.install(meta)

    if result["success"]:
        await registry.update_status(req.server_id, "stopped")
        await registry.increment_download(req.server_id)

    return {"success": result["success"], "data": result}


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
async def start_server(server_id: str):
    """启动 Server。"""
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
    except Exception:
        pass  # 清理失败不影响卸载

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
async def download_all_config(agent: str = "generic"):
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
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    import json
    json.dump(config, tmp, indent=2, ensure_ascii=False)
    tmp.close()

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
    log_file = Path.home() / ".config" / "mcp-hub" / "logs" / f"{server_id.replace('/', '_').replace('@', '')}.log"
    if not log_file.exists():
        return {"success": True, "data": [], "message": "日志文件不存在"}

    with open(log_file, encoding="utf-8") as f:
        all_lines = f.readlines()
    return {"success": True, "data": all_lines[-lines:]}
