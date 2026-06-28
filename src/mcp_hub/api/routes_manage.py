"""安装与管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from mcp_hub.core.registry import Registry
from mcp_hub.core.installer import Installer
from mcp_hub.core.process_manager import get_process_manager
from mcp_hub.models.server import ServerMeta, InstallConfig

router = APIRouter(tags=["manage"])


class InstallRequest(BaseModel):
    server_id: str


@router.post("/servers/install")
async def install_server(req: InstallRequest):
    """安装 Server。"""
    registry = Registry()
    server_data = await registry.get_by_id(req.server_id)
    if not server_data:
        raise HTTPException(status_code=404, detail=f"Server '{req.server_id}' 未找到")

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
        raise HTTPException(status_code=404, detail="Server 未找到")

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
        raise HTTPException(status_code=404, detail="Server 未找到")

    command = server.get("install_command", "")
    if not command:
        raise HTTPException(status_code=400, detail="没有安装命令")

    parts = command.split()
    pm = get_process_manager()
    try:
        await pm.spawn(server_id, parts[0], parts[1:])
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

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

    with open(log_file, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return {"success": True, "data": all_lines[-lines:]}
