"""配置绑定 API — 上传/下载/匹配 mcp.json。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, select

from mcp_hub.core.registry import Registry
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import UserServerModel
from mcp_hub.exceptions import ConfigError

router = APIRouter(tags=["config"])


@router.get("/config/download")
async def download_config():
    """下载当前完整配置 (mcp.json)，用于导入本地 Agent。"""
    registry = Registry()
    installed = await registry.get_installed()

    config = {"mcpServers": {}}
    for s in installed:
        cmd = s.get("install_command", "")
        name = s["id"].split("/")[-1]
        if cmd:
            config["mcpServers"][name] = {"command": cmd}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2, ensure_ascii=False)

    return FileResponse(
        tmp.name,
        media_type="application/json",
        filename="mcp-hub-config.json",
    )


@router.get("/config/user-servers")
async def get_user_servers(x_user_id: str = "anonymous"):
    """获取当前用户的 Server 配置列表（用户隔离）。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel)
            .where(UserServerModel.user_id == x_user_id)
            .order_by(UserServerModel.created_at)
        )
        servers = []
        for row in result.scalars().all():
            servers.append({
                "name": row.server_id,
                "hub_id": row.server_id,
                "matched": row.matched,
            })
    return {"success": True, "data": servers}


@router.post("/config/user-servers/save")
async def save_user_servers(data: dict, x_user_id: str = "anonymous"):
    """保存当前用户的 Server 配置列表（覆盖式）。"""
    servers = data.get("servers", [])
    if not isinstance(servers, list):
        return {"success": False, "error": "servers 必须是列表"}

    async with async_session_factory() as session:
        # 删除旧记录
        await session.execute(
            delete(UserServerModel).where(UserServerModel.user_id == x_user_id)
        )
        # 写入新记录
        for s in servers:
            sid = s.get("hub_id") or s.get("name", "")
            if sid:
                session.add(UserServerModel(
                    user_id=x_user_id,
                    server_id=sid,
                    matched=s.get("matched", True),
                ))
        await session.commit()

    return {"success": True, "message": f"已保存 {len(servers)} 个 Server"}


@router.post("/config/upload")
async def upload_config(file: Annotated[UploadFile, File(...)]):
    """上传本地的 claude_desktop_config.json，匹配市场中的 Server。

    返回上传配置中每个 Server 在 Hub 市场中的匹配情况，
    并推荐可安装的 Server 列表。
    """
    content = await file.read()
    try:
        config = json.loads(content)
    except json.JSONDecodeError as err:
        raise ConfigError("无效的 JSON 文件") from err

    servers_map = config.get("mcpServers", {})

    if not servers_map:
        return {
            "success": True,
            "data": {
                "server_count": 0,
                "matched": [],
                "unmatched": [],
                "not_in_hub": [],
                "file_name": file.filename or "unknown",
            },
            "message": "配置中未找到 mcpServers 定义",
        }

    # 在市场中匹配每个 Server
    registry = Registry()
    matched = []
    unmatched = []
    not_in_hub = []

    for name, cfg in servers_map.items():
        cmd = cfg.get("command", "") + " " + " ".join(cfg.get("args", []))
        cmd = cmd.strip()

        # 尝试在 Hub 中搜索匹配
        results, _ = await registry.search(q=name, page=1, page_size=10)

        # 精确匹配：名称或命令包含
        found = None
        for s in results:
            sid = s.get("id", "")
            scmd = s.get("install_command", "")
            if name in sid or (scmd and cmd and scmd.split()[0] in cmd):
                found = s
                break

        entry = {
            "local_name": name,
            "local_command": cmd,
            "server_count": 1,
        }

        if found:
            entry["matched"] = True
            entry["hub_id"] = found["id"]
            entry["hub_install_command"] = found.get("install_command", "")
            entry["hub_security_level"] = found.get("security_level", "unreviewed")
            entry["hub_rating"] = found.get("rating", 0)
            matched.append(entry)
        else:
            # 检查是否只是命名不同但可能是同一个
            if cmd:
                unmatched.append(entry)
            else:
                entry["matched"] = False
                not_in_hub.append(entry)

    return {
        "success": True,
        "data": {
            "server_count": len(servers_map),
            "matched": matched,
            "unmatched": unmatched,
            "not_in_hub": not_in_hub,
            "file_name": file.filename or "unknown",
        },
        "message": (
            f"配置包含 {len(servers_map)} 个 Server 定义，"
            f"其中 {len(matched)} 个可在 Hub 中安装，"
            f"{len(unmatched)} 个未匹配到市场"
        ),
    }


@router.post("/config/build")
async def build_config(data: dict):
    """根据指定的 Server ID 列表生成 mcp.json 配置文件。

    请求体: {"servers": ["@anthropic/web-search", "@github/github-mcp-server"]}
    生成的配置包含这些 Server 的安装命令 + Hub 网关入口。
    """
    server_ids = data.get("servers", [])
    if not server_ids:
        return {"success": False, "error": "server 列表为空"}

    registry = Registry()
    config = {"mcpServers": {}}

    for sid in server_ids:
        server = await registry.get_by_id(sid)
        if server:
            cmd = server.get("install_command", "")
            name = sid.split("/")[-1]
            if cmd:
                config["mcpServers"][name] = {"command": cmd}

    # 添加 Hub 网关
    config["mcpServers"]["mcp-hub-gateway"] = {
        "command": "mcp",
        "args": ["serve"],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2, ensure_ascii=False)

    return FileResponse(
        tmp.name,
        media_type="application/json",
        filename="mcp-hub-config.json",
    )


@router.post("/config/generate")
async def generate_config():
    """生成完整的 mcp.json 配置文件，包含所有已安装 Server + Hub 网关。"""
    registry = Registry()
    installed = await registry.get_installed()

    config = {"mcpServers": {}}

    # 添加所有已安装的 Server
    for s in installed:
        cmd = s.get("install_command", "")
        name = s["id"].split("/")[-1]
        if cmd:
            config["mcpServers"][name] = {"command": cmd}

    # 添加 Hub 网关入口（如果当前是 daemon 模式）
    config["mcpServers"]["mcp-hub"] = {
        "command": "mcp",
        "args": ["serve"],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2, ensure_ascii=False)

    return FileResponse(
        tmp.name,
        media_type="application/json",
        filename="mcp-hub-config.json",
    )


@router.get("/config/from-local")
async def config_from_local():
    """尝试读取本地的 mcp.json 配置文件。"""
    paths = [
        Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
        Path.home() / ".cursor" / "mcp.json",
        Path.home() / ".config" / "mcp-hub" / "mcp.json",
    ]
    results = []
    for p in paths:
        if p.exists():
            try:
                content = json.loads(p.read_text())
                servers = list(content.get("mcpServers", {}).keys())
                results.append({
                    "path": str(p),
                    "exists": True,
                    "server_count": len(servers),
                    "servers": servers,
                })
            except Exception:
                results.append({"path": str(p), "exists": True, "error": "无法解析"})
        else:
            results.append({"path": str(p), "exists": False})

    return {"success": True, "data": results}
