"""搜索 API — 全文检索 + 20+ 筛选维度。"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import ServerModel
from mcp_hub.db.repositories import ServerRepository

router = APIRouter(tags=["search"])

# 扩展标签体系 — 20+ 个实用标签
SEARCH_TAGS = {
    "向量检索": ["vector", "embedding", "semantic", "similarity", "rag", "retrieval"],
    "数据处理": ["data", "pipeline", "etl", "transform", "process", "extract", "csv"],
    "代码生成": ["code", "generate", "coding", "program", "cli", "terminal"],
    "内容创作": ["writing", "content", "blog", "article", "copy", "markdown"],
    "客户服务": ["customer", "support", "ticket", "service", "help", "chatbot"],
    "DevOps": ["deploy", "kubernetes", "docker", "ci/cd", "infra", "ops"],
    "商业智能": ["analytics", "bi", "report", "insight", "dashboard", "metric"],
    "安全合规": ["security", "compliance", "audit", "vuln", "scan", "auth"],
    "LLM 集成": ["llm", "gpt", "chatgpt", "claude", "openai", "anthropic"],
    "知识管理": ["knowledge", "wiki", "note", "obsidian", "notion", "document"],
    "项目管理": ["project", "task", "jira", "linear", "trello", "asana"],
    "自动化测试": ["test", "testing", "qa", "assert", "coverage"],
    "API 集成": ["rest", "graphql", "api", "webhook", "integration"],
    "文件处理": ["file", "pdf", "excel", "csv", "image", "upload"],
    "消息通知": ["notification", "email", "slack", "discord", "push"],
    "地图位置": ["map", "geo", "location", "coordinate", "gis"],
    "金融支付": ["payment", "stripe", "invoice", "finance", "wallet"],
    "设计工具": ["figma", "design", "ui", "ux", "sketch", "image"],
    "云原生": ["cloud", "aws", "gcp", "azure", "serverless"],
    "搜索索引": ["search", "index", "elasticsearch", "meilisearch"],
}

# 常见编程语言
LANGUAGES = {
    "Python": ["python", "pip", "uvx"],
    "TypeScript": ["typescript", "ts", "npx"],
    "JavaScript": ["javascript", "js", "node"],
    "Go": ["go", "golang"],
    "Rust": ["rust", "cargo"],
    "Java": ["java", "maven"],
    "C#": ["c#", "dotnet"],
}


@router.get("/search/tags")
async def get_tags():
    """获取可筛选的标签列表。"""
    return {"success": True, "data": [
        {"id": k, "name": k, "count": 0} for k in SEARCH_TAGS
    ]}


@router.get("/search/languages")
async def get_languages():
    """获取编程语言列表。"""
    return {"success": True, "data": [
        {"id": k.lower(), "name": k} for k in LANGUAGES
    ]}


@router.get("/search/authors")
async def get_authors():
    """获取常见作者/组织。"""
    async with async_session_factory() as session:
        from sqlalchemy import text
        rows = await session.execute(
            text("SELECT author, COUNT(*) as cnt FROM servers WHERE author != '' GROUP BY author ORDER BY cnt DESC LIMIT 30")
        )
        authors = [{"id": r[0], "name": r[0], "count": r[1]} for r in rows]
    return {"success": True, "data": authors}


@router.get("/search/advanced")
async def advanced_search(
    q: str = Query("", description="关键词"),
    category: str | None = Query(None, description="分类"),
    tag: str | None = Query(None, description="功能标签"),
    author: str | None = Query(None, description="作者/组织"),
    language: str | None = Query(None, description="编程语言"),
    install_type: str | None = Query(None, description="安装方式"),
    security_level: str | None = Query(None, description="安全等级"),
    min_stars: int | None = Query(None, description="最低 Star 数"),
    sort: str = Query("hot", description="排序"),
    page: int = Query(1, ge=1),
    page_size: int = Query(9, ge=1, le=100),
):
    """高级搜索 — 9 维筛选。"""
    async with async_session_factory() as session:
        query = select(ServerModel)
        count_query = select(func.count(ServerModel.id))
        conditions = []

        # 1) 关键词全文检索
        if q:
            keyword_cond = or_(
                ServerModel.name.ilike(f"%{q}%"),
                ServerModel.display_name.ilike(f"%{q}%"),
                ServerModel.description.ilike(f"%{q}%"),
                ServerModel.tags.ilike(f"%{q}%"),
                ServerModel.categories.ilike(f"%{q}%"),
            )
            conditions.append(keyword_cond)

        # 2) 分类
        if category:
            conditions.append(ServerModel.categories.ilike(f"%{category}%"))

        # 3) 功能标签
        if tag:
            keywords = SEARCH_TAGS.get(tag, [tag])
            tag_cond = or_(*[ServerModel.tags.ilike(f"%{kw}%") for kw in keywords])
            tag_cond = or_(tag_cond, *[ServerModel.description.ilike(f"%{kw}%") for kw in keywords])
            conditions.append(tag_cond)

        # 4) 作者/组织
        if author:
            conditions.append(ServerModel.author.ilike(f"%{author}%"))

        # 5) 编程语言
        if language:
            lang_keywords = LANGUAGES.get(language.capitalize(), [language])
            lang_cond = or_(
                *[ServerModel.tags.ilike(f"%{kw}%") for kw in lang_keywords],
                *[ServerModel.install_type == kw for kw in lang_keywords],
                *[ServerModel.description.ilike(f"%{kw}%") for kw in lang_keywords],
            )
            conditions.append(lang_cond)

        # 6) 安装方式
        if install_type:
            conditions.append(ServerModel.install_type == install_type)

        # 7) 安全等级
        if security_level:
            conditions.append(ServerModel.security_level == security_level)

        # 8) 最低 Star/下载数
        if min_stars:
            conditions.append(ServerModel.download_count >= min_stars)

        for cond in conditions:
            query = query.where(cond)
            count_query = count_query.where(cond)

        # 排序
        sort_map = {
            "hot": ServerModel.download_count.desc(),
            "rating": ServerModel.rating.desc(),
            "downloads": ServerModel.download_count.desc(),
            "new": ServerModel.created_at.desc(),
            "name": ServerModel.name.asc(),
        }
        order = sort_map.get(sort, ServerModel.download_count.desc())
        query = query.order_by(order)

        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)

        total = (await session.execute(count_query)).scalar() or 0
        rows = (await session.execute(query)).scalars().all()
        repo = ServerRepository(session)
        results = [repo._server_to_dict(r) for r in rows]

    return {
        "success": True,
        "data": results,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "filters": {
                "q": q, "category": category, "tag": tag,
                "author": author, "language": language,
                "install_type": install_type, "security_level": security_level,
                "min_stars": min_stars,
            },
        },
    }
