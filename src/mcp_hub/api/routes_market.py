"""市场发现 API。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from mcp_hub.core.registry import Registry
from mcp_hub.exceptions import ServerNotFoundError
from mcp_hub.models.server import SearchResponse

router = APIRouter(tags=["market"])


@router.get("/market/search")
async def search_servers(
    q: str = Query("", description="搜索关键词"),
    category: str | None = Query(None, description="分类筛选"),
    tag: str | None = Query(None, description="标签筛选"),
    sort: str = Query("hot", description="排序: hot/rating/downloads/new"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    security_level: str | None = Query(None, description="安全等级: verified/reviewed/unreviewed/blocked"),
):
    """搜索 MCP Server。"""
    registry = Registry()
    results, total = await registry.search(
        q=q, category=category, tag=tag, sort=sort,
        page=page, page_size=page_size,
        security_level=security_level,
    )
    return SearchResponse(
        data=results,
        meta={"page": page, "page_size": page_size, "total": total},
    )


@router.get("/market/servers/{server_id:path}")
async def get_server(server_id: str):
    """获取 Server 详情。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)
    return {"success": True, "data": server}


@router.get("/market/trending")
async def get_trending():
    """热门趋势榜。"""
    registry = Registry()
    results = await registry.get_trending()
    return {"success": True, "data": results}


@router.get("/market/top-rated")
async def get_top_rated():
    """评分最高榜。"""
    registry = Registry()
    results = await registry.get_top_rated()
    return {"success": True, "data": results}


@router.get("/market/new-releases")
async def get_new_releases():
    """最新发布。"""
    registry = Registry()
    results = await registry.get_new_releases()
    return {"success": True, "data": results}


@router.get("/market/categories")
async def get_categories():
    """获取分类列表。"""
    from sqlalchemy import func, select

    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import ServerModel

    categories = [
        {"id": "browser", "name": "浏览器 & 搜索", "icon": "🌐"},
        {"id": "database", "name": "数据库", "icon": "🗄️"},
        {"id": "developer-tools", "name": "开发者工具", "icon": "🛠️"},
        {"id": "ai", "name": "AI & 机器学习", "icon": "🤖"},
        {"id": "communication", "name": "通信 & 协作", "icon": "💬"},
        {"id": "cloud", "name": "云服务 & DevOps", "icon": "☁️"},
        {"id": "monitoring", "name": "监控 & 调试", "icon": "📊"},
        {"id": "storage", "name": "存储 & 文件", "icon": "💾"},
        {"id": "security", "name": "安全 & 合规", "icon": "🔒"},
        {"id": "finance", "name": "金融 & 支付", "icon": "💰"},
        {"id": "maps", "name": "地图 & 位置", "icon": "🗺️"},
        {"id": "design", "name": "设计 & 媒体", "icon": "🎨"},
        {"id": "social-media", "name": "社交媒体", "icon": "📱"},
        {"id": "productivity", "name": "效率 & 笔记", "icon": "📝"},
        {"id": "apis", "name": "API & 集成", "icon": "🔌"},
        {"id": "tools", "name": "通用 & 其他", "icon": "🧰"},
    ]

    # 获取每个分类的 Server 数量
    async with async_session_factory() as session:
        for cat in categories:
            result = await session.execute(
                select(func.count(ServerModel.id))
                .where(ServerModel.categories.ilike(f"%{cat['id']}%"))
            )
            cat["count"] = result.scalar() or 0

    # 过滤掉数量为 0 的分类，但保留有数量的
    categories = [c for c in categories if c["count"] > 0]

    # 按数量降序排列
    categories.sort(key=lambda c: c["count"], reverse=True)

    return {"success": True, "data": categories}
