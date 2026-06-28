"""市场发现 API。"""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from mcp_hub.core.registry import Registry
from mcp_hub.models.server import SearchParams, SearchResponse

router = APIRouter(tags=["market"])


def get_registry():
    return Registry()


@router.get("/market/search")
async def search_servers(
    q: str = Query("", description="搜索关键词"),
    category: str | None = Query(None, description="分类筛选"),
    tag: str | None = Query(None, description="标签筛选"),
    sort: str = Query("hot", description="排序: hot/rating/downloads/new"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    registry: Registry = Depends(get_registry),
):
    """搜索 MCP Server。"""
    results, total = await registry.search(
        q=q, category=category, tag=tag, sort=sort,
        page=page, page_size=page_size,
    )
    return SearchResponse(
        data=results,
        meta={"page": page, "page_size": page_size, "total": total},
    )


@router.get("/market/servers/{server_id:path}")
async def get_server(
    server_id: str,
    registry: Registry = Depends(get_registry),
):
    """获取 Server 详情。"""
    server = await registry.get_by_id(server_id)
    if not server:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' 未找到")
    return {"success": True, "data": server}


@router.get("/market/trending")
async def get_trending(registry: Registry = Depends(get_registry)):
    """热门趋势榜。"""
    results = await registry.get_trending()
    return {"success": True, "data": results}


@router.get("/market/top-rated")
async def get_top_rated(registry: Registry = Depends(get_registry)):
    """评分最高榜。"""
    results = await registry.get_top_rated()
    return {"success": True, "data": results}


@router.get("/market/new-releases")
async def get_new_releases(registry: Registry = Depends(get_registry)):
    """最新发布。"""
    results = await registry.get_new_releases()
    return {"success": True, "data": results}


@router.get("/market/categories")
async def get_categories():
    """获取分类列表。"""
    categories = [
        {"id": "browser", "name": "浏览器 & 搜索"},
        {"id": "database", "name": "数据库"},
        {"id": "developer-tools", "name": "开发者工具"},
        {"id": "ai", "name": "AI & 机器学习"},
        {"id": "communication", "name": "通信 & 协作"},
        {"id": "monitoring", "name": "监控 & 调试"},
        {"id": "cloud", "name": "云服务"},
        {"id": "tools", "name": "工具 & 实用"},
        {"id": "storage", "name": "存储 & 文件"},
        {"id": "language", "name": "语言 & 翻译"},
    ]
    return {"success": True, "data": categories}
