"""自动对 MCP Server 进行分类 — 基于描述和标签的智能分类。"""

from __future__ import annotations

import json
import re

# 分类关键词映射
CATEGORY_RULES = [
    ("browser", ["web", "browser", "search", "scraping", "crawl", "html", "http", "url", "link", "page"]),
    ("database", ["database", "sql", "postgres", "mysql", "sqlite", "mongodb", "redis", "couch", "dynamo", "db ", "query", "table", "schema"]),
    ("developer-tools", ["git", "github", "code", "developer", "ide", "lint", "build", "deploy", "ci/cd", "devops", "terminal", "cli"]),
    ("ai", ["ai", "llm", "gpt", "chatgpt", "claude", "openai", "anthropic", "machine learning", "nlp", "rag", "embedding", "vector", "language model", "prompt"]),
    ("communication", ["slack", "discord", "teams", "telegram", "email", "messaging", "chat", "notification", "mail", "sms"]),
    ("cloud", ["aws", "azure", "gcp", "cloud", "s3", "lambda", "ec2", "kubernetes", "k8s", "docker", "container"]),
    ("monitoring", ["monitor", "logging", "observability", "sentry", "grafana", "prometheus", "alert", "metric", "trace", "debug"]),
    ("storage", ["file", "filesystem", "storage", "s3", "blob", "object storage", "fs ", "file system"]),
    ("apis", ["api", "rest", "graphql", "integration", "webhook", "oauth", "auth", "authentication"]),
    ("design", ["figma", "design", "ui", "ux", "sketch", "image", "photo", "video", "media"]),
    ("finance", ["finance", "payment", "stripe", "bank", "crypto", "blockchain", "wallet", "invoice"]),
    ("maps", ["map", "maps", "geo", "location", "coordinate", "geocoding", "navigation"]),
    ("security", ["security", "vulnerability", "scan", "audit", "compliance", "encrypt", "certificate"]),
    ("social-media", ["twitter", "reddit", "linkedin", "instagram", "social", "post", "tweet"]),
    ("productivity", ["calendar", "todo", "task", "note", "notion", "obsidian", "productivity", "organize"]),
]

# 代码语言标签
LANG_CATEGORIES = {
    "python": "🐍 Python",
    "javascript": "📜 JavaScript",
    "typescript": "📘 TypeScript",
    "go": "🔵 Go",
    "rust": "🦀 Rust",
    "java": "☕ Java",
    "ruby": "💎 Ruby",
    "c#": "#️⃣ C#",
}


def auto_categorize(name: str, desc: str, tags: list[str] | None = None,
                    existing_cats: list[str] | None = None) -> list[str]:
    """根据名称、描述和标签自动推断分类。"""
    text = f"{name} {desc} {json.dumps(tags or [])}".lower()
    # 清理 GitHub 标签噪声
    noise = ["mcp", "mcp-server", "modelcontextprotocol", "model-context-protocol", "ai", "agentic-ai"]
    for n in noise:
        text = text.replace(n, " ")

    matched = []

    for cat, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in text:
                matched.append(cat)
                break

    # 保留已有的分类
    if existing_cats:
        matched = list(set(matched + [c for c in existing_cats if c != "tools"]))

    # 如果没有任何匹配，归为通用
    if not matched:
        matched = ["tools"]

    return matched[:3]  # 最多 3 个分类


async def recategorize_all():
    """重新分类所有 Server。"""
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import ServerModel
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(ServerModel))
        servers = result.scalars().all()
        updated = 0

        for server in servers:
            old_cats = json.loads(server.categories) if server.categories else []
            good_cats = {"browser", "database", "developer-tools", "ai", "communication",
                        "cloud", "monitoring", "storage", "security", "finance",
                        "maps", "design", "social-media", "productivity", "apis"}
            has_good_cat = any(c in good_cats for c in old_cats)
            should_update = not has_good_cat or len(old_cats) <= 1 or len(old_cats) >= 4
            if should_update:
                new_cats = auto_categorize(
                    name=server.name or "",
                    desc=server.description or "",
                    tags=json.loads(server.tags) if server.tags else [],
                    existing_cats=old_cats,
                )
                if set(new_cats) != set(old_cats):
                    server.categories = json.dumps(new_cats)
                    updated += 1

        await session.commit()
        print(f"✅ 重新分类完成: {updated}/{len(servers)} 个 Server 分类已更新")


if __name__ == "__main__":
    import asyncio
    asyncio.run(recategorize_all())
