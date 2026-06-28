"""MCP Server Hub FastAPI 入口。

用法:
    python -m mcp_hub.main                 # 开发模式（docs 启用）
    uvicorn mcp_hub.main:app --port 3987   # 生产模式
"""

from __future__ import annotations

from mcp_hub.api.app import create_app

app = create_app(dev=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("mcp_hub.main:app", host="0.0.0.0", port=3987, reload=True)
