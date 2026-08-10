"""导出/分享 API。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from mcp_hub.api.dependencies import get_current_user
from mcp_hub.api.routes_config import download_config

router = APIRouter(tags=["export"])


@router.get("/export/config")
async def export_config(
    share: bool = False,
    user_id: str = Depends(get_current_user),
) -> Response:
    """导出当前用户启用的配置；share=true 时附带非敏感分享元数据。"""
    source = await download_config(agent="generic", user_id=user_id)
    config = json.loads(bytes(source.body))
    server_configs = config.get("mcpServers", {})

    if share:
        config["_meta"] = {
            "exported_by": "mcp-hub",
            "version": "0.2.0",
            "server_count": len(server_configs) if isinstance(server_configs, dict) else 0,
        }

    fn = "mcp-hub-share.json" if share else "mcp-hub-config.json"
    return Response(
        content=json.dumps(config, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )
