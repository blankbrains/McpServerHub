"""导出/分享 API。"""

from __future__ import annotations

import json
import tempfile

from fastapi import APIRouter
from fastapi.responses import FileResponse

from mcp_hub.core.registry import Registry

router = APIRouter(tags=["export"])


@router.get("/export/config")
async def export_config(share: bool = False):
    """导出配置。share=true 时包含分享信息。"""
    registry = Registry()
    installed = await registry.get_installed()
    config = {"mcpServers": {}}
    for s in installed:
        name = s["id"].split("/")[-1]
        config["mcpServers"][name] = {"command": s.get("install_command", "")}

    if share:
        # Generate a shareable link/description
        config["_meta"] = {
            "exported_by": "mcp-hub",
            "version": "0.1.0",
            "server_count": len(installed),
        }

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(config, tmp, indent=2, ensure_ascii=False)
    tmp.close()

    fn = "mcp-hub-share.json" if share else "mcp-hub-config.json"
    return FileResponse(tmp.name, media_type="application/json", filename=fn)
