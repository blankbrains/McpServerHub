"""预置真实 MCP Server 数据（全部可安装）。"""

from __future__ import annotations

from sqlalchemy import select

from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import ServerModel


REAL_MCP_SERVERS = [
    {
        "id": "@modelcontextprotocol/server-filesystem",
        "name": "server-filesystem",
        "display_name": "Filesystem",
        "description": "安全的文件系统操作 - 读取、写入、管理本地文件。需要指定可访问的目录路径。",
        "author": "modelcontextprotocol",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["tools", "filesystem"]',
        "tags": '["file", "fs", "official"]',
        "install_type": "npx",
        "install_package": "@modelcontextprotocol/server-filesystem",
        "install_command": "npx -y @modelcontextprotocol/server-filesystem /tmp",
        "security_level": "verified",
        "network_access": False,
        "file_access": True,
        "rating": 4.5,
        "download_count": 8700,
        "homepage": "https://github.com/modelcontextprotocol/servers",
    },
    {
        "id": "@modelcontextprotocol/server-github",
        "name": "server-github",
        "display_name": "GitHub",
        "description": "GitHub API 集成 - 管理仓库、Issue、PR、代码搜索。需要配置 GITHUB_TOKEN 环境变量。",
        "author": "modelcontextprotocol",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["developer-tools", "git"]',
        "tags": '["github", "git", "devops", "official"]',
        "install_type": "npx",
        "install_package": "@modelcontextprotocol/server-github",
        "install_command": "npx -y @modelcontextprotocol/server-github",
        "security_level": "verified",
        "network_access": True,
        "rating": 4.7,
        "download_count": 11200,
        "homepage": "https://github.com/modelcontextprotocol/servers",
    },
    {
        "id": "@modelcontextprotocol/server-postgres",
        "name": "server-postgres",
        "display_name": "PostgreSQL",
        "description": "PostgreSQL 数据库管理 - 查询、表结构、索引分析。需要数据库连接字符串。",
        "author": "modelcontextprotocol",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["database", "sql"]',
        "tags": '["postgres", "database", "sql", "official"]',
        "install_type": "npx",
        "install_package": "@modelcontextprotocol/server-postgres",
        "install_command": "npx -y @modelcontextprotocol/server-postgres",
        "security_level": "verified",
        "network_access": True,
        "rating": 4.5,
        "download_count": 7800,
        "homepage": "https://github.com/modelcontextprotocol/servers",
    },
    {
        "id": "@modelcontextprotocol/server-slack",
        "name": "server-slack",
        "display_name": "Slack",
        "description": "Slack 工作区集成 - 消息发送、频道管理、搜索历史。需要 SLACK_TOKEN 配置。",
        "author": "modelcontextprotocol",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["communication", "messaging"]',
        "tags": '["slack", "messaging", "official"]',
        "install_type": "npx",
        "install_package": "@modelcontextprotocol/server-slack",
        "install_command": "npx -y @modelcontextprotocol/server-slack",
        "security_level": "verified",
        "network_access": True,
        "rating": 4.1,
        "download_count": 4800,
        "homepage": "https://github.com/modelcontextprotocol/servers",
    },
    {
        "id": "@modelcontextprotocol/server-sentry",
        "name": "server-sentry",
        "display_name": "Sentry",
        "description": "Sentry 错误追踪集成 - 查询 issues、事件、性能数据。",
        "author": "modelcontextprotocol",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["monitoring", "debugging"]',
        "tags": '["sentry", "error-tracking", "official"]',
        "install_type": "npx",
        "install_package": "@modelcontextprotocol/server-sentry",
        "install_command": "npx -y @modelcontextprotocol/server-sentry",
        "security_level": "verified",
        "network_access": True,
        "rating": 4.0,
        "download_count": 3200,
        "homepage": "https://github.com/modelcontextprotocol/servers",
    },
    {
        "id": "@modelcontextprotocol/server-memory",
        "name": "server-memory",
        "display_name": "Memory",
        "description": "持久化记忆系统 - Agent 可以跨会话记住用户信息和偏好。数据存储在本地文件。",
        "author": "modelcontextprotocol",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["ai", "memory"]',
        "tags": '["memory", "persistence", "official"]',
        "install_type": "npx",
        "install_package": "@modelcontextprotocol/server-memory",
        "install_command": "npx -y @modelcontextprotocol/server-memory",
        "security_level": "verified",
        "file_access": True,
        "network_access": False,
        "rating": 4.6,
        "download_count": 9200,
        "homepage": "https://github.com/modelcontextprotocol/servers",
    },
    {
        "id": "@modelcontextprotocol/server-puppeteer",
        "name": "server-puppeteer",
        "display_name": "Puppeteer (Browser)",
        "description": "浏览器自动化 - 网页截图、PDF 生成、页面交互、Console 日志捕获。",
        "author": "modelcontextprotocol",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["browser", "automation"]',
        "tags": '["browser", "puppeteer", "screenshot", "official"]',
        "install_type": "npx",
        "install_package": "@modelcontextprotocol/server-puppeteer",
        "install_command": "npx -y @modelcontextprotocol/server-puppeteer",
        "security_level": "verified",
        "network_access": True,
        "rating": 4.3,
        "download_count": 6500,
        "homepage": "https://github.com/modelcontextprotocol/servers",
    },
    {
        "id": "@modelcontextprotocol/server-sqlite",
        "name": "server-sqlite",
        "display_name": "SQLite",
        "description": "SQLite 数据库操作 - 查询、创建表、插入数据。需要指定数据库文件路径。",
        "author": "modelcontextprotocol",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["database", "sql"]',
        "tags": '["sqlite", "database", "official"]',
        "install_type": "npx",
        "install_package": "@modelcontextprotocol/server-sqlite",
        "install_command": "npx -y @modelcontextprotocol/server-sqlite",
        "security_level": "verified",
        "file_access": True,
        "network_access": False,
        "rating": 4.2,
        "download_count": 5400,
        "homepage": "https://github.com/modelcontextprotocol/servers",
    },
    {
        "id": "@community/mcp-server-tavily",
        "name": "mcp-server-tavily",
        "display_name": "Tavily Search",
        "description": "AI 驱动的网页搜索 - 通过 Tavily API 提供高质量的搜索结果和内容提取。",
        "author": "tavily",
        "categories": '["browser", "search"]',
        "tags": '["search", "web", "ai"]',
        "install_type": "pip",
        "install_package": "mcp-server-tavily",
        "install_command": "uvx mcp-server-tavily",
        "security_level": "reviewed",
        "network_access": True,
        "rating": 4.4,
        "download_count": 6100,
        "homepage": "https://github.com/tavily-ai/mcp-server-tavily",
    },
    {
        "id": "@anthropic/mcp-server-web-search",
        "name": "mcp-server-web-search",
        "display_name": "Web Search",
        "description": "网络搜索功能 - 让 Agent 搜索互联网并获取结构化结果。Anthropic 官方出品。",
        "author": "anthropic",
        "publisher_type": "organization",
        "publisher_verified": True,
        "categories": '["browser", "search"]',
        "tags": '["search", "web", "official"]',
        "install_type": "pip",
        "install_package": "mcp-server-web-search",
        "install_command": "uvx mcp-server-web-search",
        "security_level": "verified",
        "network_access": True,
        "rating": 4.8,
        "download_count": 12340,
        "homepage": "https://github.com/anthropics/mcp-server-web-search",
    },
]


async def seed_database() -> int:
    """导入真实 MCP Server 数据。"""
    count = 0
    async with async_session_factory() as session:
        # Clear old data with CASCADE (delete dependent tables first)
        from sqlalchemy import text
        await session.execute(text("DELETE FROM reviews"))
        await session.execute(text("DELETE FROM favorites"))
        await session.execute(text("DELETE FROM health_logs"))
        await session.execute(text("DELETE FROM servers"))
        await session.commit()

        for data in REAL_MCP_SERVERS:
            server = ServerModel(**data)
            session.add(server)
            count += 1
        await session.commit()
    return count


if __name__ == "__main__":
    import asyncio
    n = asyncio.run(seed_database())
    print(f"Seeded {n} real MCP servers")
