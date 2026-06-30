"""发布 API — Publish.tsx 依赖此端点。"""
from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel

from mcp_hub.core.registry import Registry

router = APIRouter(tags=["publish"])


class PublishRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "tools"
    install_type: str = "npx"
    install_command: str = ""
    homepage: str = ""
    tags: list[str] = []


@router.post("/publish")
async def publish_server(req: PublishRequest, x_user_id: str = Header("api-user")):
    """发布 MCP Server。"""
    server_id = f"@{req.name}" if not req.name.startswith("@") else req.name
    registry = Registry()
    result_id = await registry.register_server({
        "id": server_id,
        "name": req.name,
        "description": req.description,
        "categories": [req.category],
        "tags": req.tags,
        "install_type": req.install_type,
        "install_command": req.install_command,
        "homepage": req.homepage,
        "author": x_user_id if x_user_id != "api-user" else "",
    })
    return {"success": True, "data": {"id": result_id}}


@router.get("/publish/mine")
async def my_published_servers(x_user_id: str = Header("api-user")):
    """获取当前用户发布的 Server。"""
    if x_user_id == "api-user":
        return {"success": True, "data": []}
    registry = Registry()
    servers = await registry.get_by_author(x_user_id)
    return {"success": True, "data": servers}


@router.post("/publish/unpublish/{server_id:path}")
async def unpublish_server(server_id: str, x_user_id: str = Header("api-user")):
    """下架自己发布的 Server。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        return {"success": False, "error": "Server 不存在"}
    if server.get("author", "") != x_user_id and x_user_id != "api-user":
        return {"success": False, "error": "只能下架自己发布的 Server"}
    ok = await registry.unpublish_server(server_id)
    return {"success": ok, "message": "已下架" if ok else "下架失败"}
