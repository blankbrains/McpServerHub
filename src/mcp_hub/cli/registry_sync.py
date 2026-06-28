"""registry-sync — 从 npm/PyPI/GitHub 同步 200+ 热门 MCP Server。"""

from __future__ import annotations

import asyncio
import json
import re

import click
import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# 已知官方 Server（确保优先收录）
CURATED_SERVERS = [
    "@modelcontextprotocol/server-filesystem",
    "@modelcontextprotocol/server-github",
    "@modelcontextprotocol/server-postgres",
    "@modelcontextprotocol/server-slack",
    "@modelcontextprotocol/server-sentry",
    "@modelcontextprotocol/server-memory",
    "@modelcontextprotocol/server-puppeteer",
    "@modelcontextprotocol/server-sqlite",
    "@modelcontextprotocol/server-google-maps",
    "@modelcontextprotocol/server-redis",
    "@anthropic/mcp-server-web-search",
]

# npm 搜索关键词
NPM_SEARCH_KEYWORDS = [
    "mcp-server", "mcp%20server", "modelcontextprotocol",
    "mcp-tool", "mcp-plugin",
]


async def sync_from_npm(client: httpx.AsyncClient, dry_run: bool) -> int:
    """从 npm 同步热门 MCP Server。"""
    count = 0
    seen = set()

    console.print("\n📦 [cyan]npm[/cyan]: 搜索 MCP Server...")

    for keyword in NPM_SEARCH_KEYWORDS:
        try:
            resp = await client.get(
                f"https://registry.npmjs.org/-/v1/search",
                params={
                    "text": keyword,
                    "size": 100,
                    "popularity": 1.0,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            for obj in data.get("objects", []):
                pkg = obj.get("package", {})
                name = pkg.get("name", "")
                if not name or name in seen:
                    continue
                seen.add(name)

                # 过滤：只收录 MCP 相关包
                desc = (pkg.get("description") or "").lower()
                keywords = pkg.get("keywords", [])
                is_mcp = any(k in desc or k in str(keywords).lower()
                             for k in ["mcp", "modelcontextprotocol", "model context protocol"])
                if not is_mcp and "mcp" not in name.lower():
                    continue

                ver = pkg.get("version", "?")
                score = obj.get("score", {}).get("detail", {}).get("popularity", 0)
                if score < 0.01:
                    continue  # 过滤低热度

                console.print(f"  ✅ {name}@[green]{ver}[/green] (pop={score:.3f})")
                if not dry_run:
                    await _register_npm_package(name, ver, pkg.get("description", ""),
                                                pkg.get("homepage", ""), keywords)
                    count += 1

        except Exception as e:
            console.print(f"  ⚠️  搜索 '{keyword}': {e}")

    return count


async def sync_from_pypi(client: httpx.AsyncClient, dry_run: bool) -> int:
    """从 PyPI 同步热门 MCP Server。"""
    count = 0
    console.print("\n📦 [yellow]PyPI[/yellow]: 获取包列表...")

    try:
        resp = await client.get(
            "https://pypi.org/simple/",
            headers={"Accept": "application/vnd.pypi.simple.v1+json"},
            timeout=30,
        )
        if resp.status_code != 200:
            console.print("  ⚠️  PyPI simple API 失败")
            return 0

        all_pkgs = resp.json().get("packages", [])

        # 筛选 MCP 相关包
        mcp_pkgs = [p for p in all_pkgs if (
            p.startswith("mcp-server-") or
            p.startswith("mcp-") and "server" in p or
            "mcp-server" in p
        )]
        mcp_pkgs = sorted(set(mcp_pkgs))[:100]  # 最多 100 个

        console.print(f"  找到 {len(mcp_pkgs)} 个 MCP 相关包")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("正在获取详情...", total=len(mcp_pkgs))

            for pkg_name in mcp_pkgs:
                try:
                    info_resp = await client.get(
                        f"https://pypi.org/pypi/{pkg_name}/json",
                        timeout=10,
                    )
                    if info_resp.status_code == 200:
                        info = info_resp.json().get("info", {})
                        ver = info.get("version", "?")
                        desc = (info.get("summary", "") or "")[:200]
                        home = info.get("home_page", "") or info.get("project_urls", {}).get("Source", "")

                        console.print(f"  ✅ {pkg_name}@[green]{ver}[/green]")
                        if not dry_run:
                            await _register_pypi_package(pkg_name, ver, desc, home)
                            count += 1
                except Exception:
                    pass

                progress.update(task, advance=1)

    except Exception as e:
        console.print(f"  ⚠️  PyPI: {e}")

    return count


async def sync_from_github(client: httpx.AsyncClient, dry_run: bool) -> int:
    """从 GitHub 同步高 Star MCP Server。"""
    count = 0
    console.print("\n📦 [magenta]GitHub[/magenta]: 搜索 MCP Server (star>100)...")

    query = "topic:mcp-server stars:>100"
    page = 1
    seen_topics = set()

    while page <= 5:  # 最多 5 页 = 500 个结果
        try:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 100,
                    "page": page,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=15,
            )

            if resp.status_code != 200:
                console.print(f"  ⚠️  GitHub API 限制 (HTTP {resp.status_code})")
                break

            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for repo in items:
                full_name = repo.get("full_name", "")
                if full_name in seen_topics:
                    continue
                seen_topics.add(full_name)

                stars = repo.get("stargazers_count", 0)
                desc = (repo.get("description") or "")[:200]
                topics = repo.get("topics", [])
                lang = repo.get("language") or "unknown"

                # 过滤：必须有 MCP 相关主题
                mcp_topics = [t for t in topics if "mcp" in t.lower()]
                if not mcp_topics:
                    continue

                console.print(f"  ⭐ {full_name} (⭐{stars}, {lang})")
                if not dry_run:
                    await _register_github_repo(full_name, desc, stars, topics, lang)
                    count += 1

            page += 1

        except Exception as e:
            console.print(f"  ⚠️  GitHub page {page}: {e}")
            break

    return count


async def _register_npm_package(name: str, ver: str, desc: str, homepage: str, keywords: list):
    """注册 npm 包到数据库。"""
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import ServerModel
    from sqlalchemy import select

    parts = name.split("/")
    server_id = name if name.startswith("@") else f"@npm/{name}"
    display = parts[-1].replace("mcp-server-", "").replace("server-", "").replace("-", " ").title()
    cmd = f"npx -y {name}"
    install_type = "npx"

    # 如果是 modelcontextprotocol 官方，用 uvx 也可
    if "/" in name:
        org = name.split("/")[0].strip("@")
        if org == "modelcontextprotocol":
            cmd = f"npx -y {name}"
            install_type = "npx"
        else:
            cmd = f"npx -y {name}"
    else:
        cmd = f"npx -y {name}"

    async with async_session_factory() as session:
        existing = await session.execute(select(ServerModel).where(ServerModel.id == server_id))
        if existing.scalar_one_or_none():
            return

        cats = json.dumps(keywords[:3] if keywords else ["tools"])
        tags = json.dumps(keywords[:5] if keywords else [])
        network = "network" in desc.lower() or "api" in desc.lower() or "web" in desc.lower()

        server = ServerModel(
            id=server_id,
            name=parts[-1],
            display_name=display,
            description=desc[:200],
            categories=cats,
            tags=tags,
            install_type=install_type,
            install_package=name,
            install_command=cmd,
            security_level="reviewed",
            network_access=network,
            latest_version=ver,
            homepage=homepage or f"https://www.npmjs.com/package/{name}",
        )
        session.add(server)
        await session.commit()


async def _register_pypi_package(name: str, ver: str, desc: str, homepage: str):
    """注册 PyPI 包到数据库。"""
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import ServerModel
    from sqlalchemy import select

    server_id = f"@pypi/{name}"
    display = name.replace("mcp-server-", "").replace("mcp-", "").replace("-", " ").title()

    async with async_session_factory() as session:
        existing = await session.execute(select(ServerModel).where(ServerModel.id == server_id))
        if existing.scalar_one_or_none():
            return

        server = ServerModel(
            id=server_id,
            name=name,
            display_name=display,
            description=desc[:200],
            categories='["tools", "python"]',
            tags='["mcp", "python", "pypi"]',
            install_type="pip",
            install_package=name,
            install_command=f"uvx {name}",
            security_level="reviewed",
            network_access=True,
            latest_version=ver,
            homepage=homepage or f"https://pypi.org/project/{name}/",
        )
        session.add(server)
        await session.commit()


async def _register_github_repo(full_name: str, desc: str, stars: int, topics: list, lang: str):
    """注册 GitHub 仓库到数据库。"""
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import ServerModel
    from sqlalchemy import select

    server_id = f"@github/{full_name}"
    name = full_name.split("/")[-1]
    display = name.replace("mcp-server-", "").replace("-", " ").title()

    async with async_session_factory() as session:
        existing = await session.execute(select(ServerModel).where(ServerModel.id == server_id))
        if existing.scalar_one_or_none():
            return

        # 判断安装方式
        install_type = "pip"
        install_cmd = f"uvx {name}"
        if "node" in lang.lower() or "typescript" in lang.lower():
            install_type = "npx"
            install_cmd = f"npx -y {full_name}"
        elif "python" in lang.lower():
            install_type = "pip"
            install_cmd = f"uvx {name}"
        elif "go" in lang.lower():
            install_type = "pip"
            install_cmd = f"go install {full_name}@latest"

        cats = json.dumps(topics[:3] if topics else ["tools"])
        tags = json.dumps(topics[:5] if topics else ["github"])
        rating = min(5.0, 3.0 + (stars / 500))  # star 越多评分越高

        server = ServerModel(
            id=server_id,
            name=name,
            display_name=display,
            description=desc[:200],
            author=full_name.split("/")[0],
            categories=cats,
            tags=tags,
            install_type=install_type,
            install_package=full_name,
            install_command=install_cmd,
            security_level="reviewed",
            network_access=True,
            rating=round(rating, 1),
            download_count=stars,
            homepage=f"https://github.com/{full_name}",
        )
        session.add(server)
        await session.commit()


@click.command("registry-sync")
@click.option("--dry-run", is_flag=True, help="只预览，不写入数据库")
@click.option("--source", type=click.Choice(["npm", "pypi", "github", "all"]), default="all")
def registry_sync(dry_run: bool, source: str):
    """从 npm/PyPI/GitHub 同步热门 MCP Server 到本地市场。"""
    async def _run():
        console.print("[bold]🔄 正在同步 MCP 注册表 (200+ servers)...[/bold]\n")

        total = 0
        async with httpx.AsyncClient(timeout=15) as client:
            if source in ("npm", "all"):
                n = await sync_from_npm(client, dry_run)
                total += n

            if source in ("pypi", "all"):
                n = await sync_from_pypi(client, dry_run)
                total += n

            if source in ("github", "all"):
                n = await sync_from_github(client, dry_run)
                total += n

        console.print(f"\n[green]✅ 同步完成！新增 {total} 个 Server[/green]")
        if dry_run:
            console.print("[yellow]  (dry-run 模式，未写入数据库)[/yellow]")

        # 显示统计
        from mcp_hub.db.database import async_session_factory
        from mcp_hub.db.models import ServerModel
        from sqlalchemy import select, func

        async with async_session_factory() as session:
            cnt = (await session.execute(select(func.count(ServerModel.id)))).scalar()
            console.print(f"\n📊 市场总计: [bold]{cnt}[/bold] 个 MCP Server")

    asyncio.run(_run())
