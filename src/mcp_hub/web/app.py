"""Web Dashboard 静态文件服务（FastAPI 集成）。

Serve built React SPA from web/static/ directory.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_web_dashboard(app: FastAPI, static_dir: Path) -> None:
    """将 React SPA 挂载到 FastAPI 应用。

    - /assets/* → 静态资源
    - /favicon.svg, /logo.svg → 根静态文件
    - 所有非 API GET 路径 → index.html (SPA 回退)

    Args:
        app: FastAPI 应用实例。
        static_dir: 前端构建产物目录 (web/static/)。
    """
    index_html = static_dir / "index.html"
    if not index_html.exists():
        return  # 前端未构建，跳过

    # 静态资源
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="web_assets")

    # 根静态文件索引
    root_files: dict[str, Path] = {}
    for name in ["favicon.svg", "favicon.ico", "logo.svg"]:
        path = static_dir / name
        if path.exists():
            root_files[name] = path

    @app.get("/favicon.svg")
    async def _favicon():
        if "favicon.svg" in root_files:
            return FileResponse(str(root_files["favicon.svg"]))
        return FileResponse(str(index_html))

    @app.get("/logo.svg")
    async def _logo():
        if "logo.svg" in root_files:
            return FileResponse(str(root_files["logo.svg"]))
        return FileResponse(str(index_html))

    @app.api_route("/{path:path}", methods=["GET"])
    async def _spa_fallback(path: str):
        if path in root_files:
            return FileResponse(str(root_files[path]))
        return FileResponse(str(index_html))
