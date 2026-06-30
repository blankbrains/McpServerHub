"""发布 API — 含安全检查。"""
from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel

from mcp_hub.core.registry import Registry
from mcp_hub.core.security_scanner import SecurityScanner

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
    """发布 MCP Server（含自动安全扫描）。"""
    server_id = f"@{req.name}" if not req.name.startswith("@") else req.name

    # 安全检查
    scanner = SecurityScanner()
    scan_data = {
        "id": server_id,
        "name": req.name,
        "description": req.description,
        "install_command": req.install_command,
        "install_type": req.install_type,
        "author": x_user_id,
    }
    report = await scanner.scan(scan_data)
    if report.score < 50:
        return {
            "success": False,
            "error": f"安全评分 {report.score}/100（{report.level}），发布被阻止。请修复安装命令中的安全问题后再试。",
            "security_report": {
                "score": report.score,
                "level": report.level,
                "findings": [{"title": f.title, "severity": f.severity} for f in report.findings],
            },
        }

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
        "security_level": report.level,
        "author": x_user_id if x_user_id != "api-user" else "",
    })
    return {"success": True, "data": {"id": result_id}, "security": {"score": report.score, "level": report.level}}


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
