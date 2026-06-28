"""配置绑定 API — 上传/下载 mcp.json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from mcp_hub.exceptions import ConfigError

router = APIRouter(tags=["config"])


@router.get("/config/download")
async def download_config():
    """下载当前完整配置 (mcp.json)。"""
    from mcp_hub.core.registry import Registry
    registry = Registry()
    installed = await registry.get_installed()

    config = {"mcpServers": {}}
    for s in installed:
        cmd = s.get("install_command", "")
        name = s["id"].split("/")[-1]
        config["mcpServers"][name] = {"command": cmd}

    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2, ensure_ascii=False)

    return FileResponse(
        tmp.name,
        media_type="application/json",
        filename="mcp-hub-config.json",
    )


@router.post("/config/upload")
async def upload_config(file: Annotated[UploadFile, File(...)]):
    """上传本地的 mcp.json 配置文件。"""
    content = await file.read()
    try:
        config = json.loads(content)
    except json.JSONDecodeError as err:
        raise ConfigError("无效的 JSON 文件") from err

    # 分析上传的配置，返回可安装的 Server 列表
    servers = config.get("mcpServers", {})
    return {
        "success": True,
        "data": {
            "server_count": len(servers),
            "servers": list(servers.keys()),
            "file_name": file.filename,
        },
        "message": f"配置包含 {len(servers)} 个 Server 定义",
    }


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
