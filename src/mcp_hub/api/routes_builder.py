"""MCP Server Builder API — 在线生成并下载项目。"""

from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from mcp_hub.core.server_builder import ServerBuilder

router = APIRouter(tags=["builder"])


@router.get("/builder/tools")
async def list_tools():
    """获取可用工具模板列表。"""
    builder = ServerBuilder()
    tools = []
    for name in builder.available_tools():
        t = builder.get_tool(name)
        if t:
            tools.append({
                "name": name,
                "description": t.description,
                "params": [
                    {"name": p["name"], "type": p["type"], "description": p["description"]}
                    for p in t.params
                ],
            })
    return {"success": True, "data": tools}


@router.get("/builder/generate")
async def generate_project(
    name: str = Query(..., description="项目名称"),
    language: str = Query("python", description="python 或 typescript"),
    description: str = Query("", description="项目描述"),
    author: str = Query("", description="作者"),
    tools: str = Query("hello,echo", description="工具列表（逗号分隔）"),
):
    """生成 MCP Server 项目并返回 ZIP 下载。"""
    builder = ServerBuilder()
    tool_list = [t.strip() for t in tools.split(",") if t.strip()]

    project = builder.create_project(
        name=name,
        language=language,  # type: ignore
        description=description or f"MCP Server: {name}",
        author=author or "developer",
        tools=tool_list,
    )

    # 生成 ZIP 内存文件
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in project.files.items():
            zf.writestr(rel_path, content.encode("utf-8"))
    buf.seek(0)

    return FileResponse(
        buf,
        media_type="application/zip",
        filename=f"{name}.zip",
        headers={
            "Content-Disposition": f'attachment; filename="{name}.zip"',
            "Content-Type": "application/zip",
        },
    )
