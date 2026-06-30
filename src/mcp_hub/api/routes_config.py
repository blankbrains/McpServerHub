"""配置绑定 API — 上传/下载/匹配 mcp.json。"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, File, Header, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, select

from mcp_hub.core.registry import Registry
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import UserServerModel
from mcp_hub.exceptions import ConfigError

router = APIRouter(tags=["config"])


def _extract_package_name(command: str) -> str | None:
    """从安装命令中提取包名。

    支持的格式：
      npx @org/package         → @org/package
      npx package              → package
      uvx @org/package         → @org/package
      pip install package      → package
      pip install @org/package → @org/package
    """
    cmd = command.strip()
    # npx/uvx 后面跟的就是包名
    m = re.match(r'^(npx|uvx)\s+(@?[\w][\w.-]*(?:/[\w][\w.-]*)?)', cmd)
    if m:
        return m.group(2)
    # pip install 后面跟的是包名
    m = re.match(r'^pip\s+install\s+(@?[\w][\w.-]*(?:/[\w][\w.-]*)?)', cmd)
    if m:
        return m.group(1)
    return None


async def _resolve_package_online(pkg_name: str) -> dict | None:
    """尝试从 npm 和 PyPI 查询包的元信息。"""
    if pkg_name.startswith("@"):
        # npm scoped package: @org/name
        url = f"https://registry.npmjs.org/{pkg_name}/latest"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    desc = data.get("description", "")
                    return {
                        "source": "npm",
                        "id": pkg_name,
                        "name": pkg_name.split("/")[-1] if "/" in pkg_name else pkg_name,
                        "description": desc,
                        "version": data.get("version", ""),
                        "homepage": f"https://www.npmjs.com/package/{pkg_name}",
                    }
        except Exception:
            pass
        return None

    # 先试 npm
    npm_url = f"https://registry.npmjs.org/{pkg_name}/latest"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(npm_url)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "source": "npm",
                    "id": f"@npm/{pkg_name}",
                    "name": pkg_name,
                    "description": data.get("description", ""),
                    "version": data.get("version", ""),
                    "homepage": f"https://www.npmjs.com/package/{pkg_name}",
                }
    except Exception:
        pass

    # 再试 PyPI
    pypi_url = f"https://pypi.org/pypi/{pkg_name}/json"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(pypi_url)
            if resp.status_code == 200:
                data = resp.json().get("info", {})
                return {
                    "source": "pypi",
                    "id": f"@pypi/{pkg_name}",
                    "name": pkg_name,
                    "description": data.get("summary", ""),
                    "version": data.get("version", ""),
                    "homepage": data.get("home_page", "") or f"https://pypi.org/project/{pkg_name}/",
                }
    except Exception:
        pass

    return None


@router.get("/config/download")
async def download_config():
    """下载当前完整配置 (mcp.json)，用于导入本地 Agent。"""
    registry = Registry()
    installed = await registry.get_installed()

    config = {"mcpServers": {}}
    for s in installed:
        cmd = s.get("install_command", "")
        name = s["id"].split("/")[-1]
        if cmd:
            config["mcpServers"][name] = {"command": cmd}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2, ensure_ascii=False)

    return FileResponse(
        tmp.name,
        media_type="application/json",
        filename="mcp-hub-config.json",
    )


@router.get("/config/user-servers")
async def get_user_servers(x_user_id: str = "anonymous"):
    """获取当前用户的 Server 配置列表（用户隔离）。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel)
            .where(UserServerModel.user_id == x_user_id)
            .order_by(UserServerModel.created_at)
        )
        servers = []
        for row in result.scalars().all():
            servers.append({
                "name": row.server_id,
                "hub_id": row.server_id,
                "matched": row.matched,
            })
    return {"success": True, "data": servers}


@router.post("/config/user-servers/save")
async def save_user_servers(data: dict, x_user_id: str = "anonymous"):
    """保存当前用户的 Server 配置列表（覆盖式）。"""
    servers = data.get("servers", [])
    if not isinstance(servers, list):
        return {"success": False, "error": "servers 必须是列表"}

    async with async_session_factory() as session:
        # 删除旧记录
        await session.execute(
            delete(UserServerModel).where(UserServerModel.user_id == x_user_id)
        )
        # 写入新记录
        for s in servers:
            sid = s.get("hub_id") or s.get("name", "")
            if sid:
                session.add(UserServerModel(
                    user_id=x_user_id,
                    server_id=sid,
                    matched=s.get("matched", True),
                    enabled=s.get("enabled", True),
                    agent=s.get("agent", ""),
                ))
        await session.commit()

    return {"success": True, "message": f"已保存 {len(servers)} 个 Server"}


@router.post("/config/upload")
async def upload_config(file: Annotated[UploadFile, File(...)], x_user_id: str = Header("anonymous"), x_agent_id: str = Header("")):
    """上传本地的 claude_desktop_config.json，匹配市场中的 Server。

    返回上传配置中每个 Server 在 Hub 市场中的匹配情况，
    并推荐可安装的 Server 列表。
    """
    content = await file.read()
    try:
        config = json.loads(content)
    except json.JSONDecodeError as err:
        raise ConfigError("无效的 JSON 文件") from err

    servers_map = config.get("mcpServers", {})

    if not servers_map:
        return {
            "success": True,
            "data": {
                "server_count": 0,
                "matched": [],
                "unmatched": [],
                "not_in_hub": [],
                "file_name": file.filename or "unknown",
            },
            "message": "配置中未找到 mcpServers 定义",
        }

    # 在市场中匹配每个 Server
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import UserServerModel
    from sqlalchemy import delete

    registry = Registry()
    matched = []
    unmatched = []
    not_in_hub = []
    all_tracked = []  # 所有需要追踪的 server 列表

    for name, cfg in servers_map.items():
        cmd = cfg.get("command", "") + " " + " ".join(cfg.get("args", []))
        cmd = cmd.strip()

        # 尝试在 Hub 中搜索匹配
        results, _ = await registry.search(q=name, page=1, page_size=10)

        # 精确匹配：名称或命令包含
        found = None
        for s in results:
            sid = s.get("id", "")
            scmd = s.get("install_command", "")
            if name in sid or (scmd and cmd and scmd.split()[0] in cmd):
                found = s
                break

        entry = {
            "local_name": name,
            "local_command": cmd,
            "server_count": 1,
        }

        if found:
            entry["matched"] = True
            entry["hub_id"] = found["id"]
            entry["hub_install_command"] = found.get("install_command", "")
            entry["hub_security_level"] = found.get("security_level", "unreviewed")
            entry["hub_rating"] = found.get("rating", 0)
            matched.append(entry)
            all_tracked.append({"server_id": found["id"], "matched": True})
        else:
            if cmd:
                # 尝试从命令中提取包名并在线查询 npm/PyPI
                pkg_name = _extract_package_name(cmd)
                resolved = None
                if pkg_name:
                    resolved = await _resolve_package_online(pkg_name)

                if resolved:
                    # 从 npm/PyPI 查到真实包信息
                    sid = resolved["id"]
                    entry["matched"] = True
                    entry["hub_id"] = sid
                    entry["hub_install_command"] = cmd
                    entry["hub_security_level"] = "reviewed"
                    entry["resolved_source"] = resolved["source"]
                    matched.append(entry)
                    all_tracked.append({"server_id": sid, "matched": True})
                    try:
                        await registry.register_server({
                            "id": sid,
                            "name": resolved["name"],
                            "description": resolved.get("description",
                                                        f"从 {resolved['source']} 发现的 MCP Server"),
                            "install_command": cmd,
                            "install_type": resolved["source"],
                            "categories": json.dumps(["tools"]),
                            "tags": json.dumps([resolved["source"], "discovered"]),
                            "homepage": resolved.get("homepage", ""),
                            "author": resolved["source"],
                            "security_level": "reviewed",
                        })
                    except Exception:
                        pass
                else:
                    # 线上也查不到，才标为自定义
                    unmatched.append(entry)
                    sid = f"@custom/{name}"
                    all_tracked.append({"server_id": sid, "matched": False})
                    try:
                        await registry.register_server({
                            "id": sid,
                            "name": name,
                            "description": f"自定义 Server: {name}",
                            "install_command": cmd,
                            "install_type": cmd.split()[0] if cmd else "custom",
                            "categories": json.dumps(["custom"]),
                            "tags": json.dumps(["user-uploaded"]),
                            "author": "user",
                        })
                        entry["registered_id"] = sid
                    except Exception:
                        pass
            else:
                entry["matched"] = False
                not_in_hub.append(entry)

    # 同步所有 server 到 user_servers 表（用户追踪列表）
    async with async_session_factory() as session:
        # 先清理当前用户的旧记录
        await session.execute(
            delete(UserServerModel).where(UserServerModel.user_id == x_user_id)
        )
        # 写入新的追踪列表
        for ts in all_tracked:
            session.add(UserServerModel(
                user_id=x_user_id,
                server_id=ts["server_id"],
                matched=ts["matched"],
                agent=x_agent_id if x_agent_id else "",
            ))
        await session.commit()

    return {
        "success": True,
        "data": {
            "server_count": len(servers_map),
            "matched": matched,
            "unmatched": unmatched,
            "not_in_hub": not_in_hub,
            "file_name": file.filename or "unknown",
        },
        "message": (
            f"配置包含 {len(servers_map)} 个 Server 定义，"
            f"其中 {len(matched)} 个可在 Hub 中安装，"
            f"{len(unmatched)} 个未匹配到市场"
        ),
    }


@router.post("/config/build")
async def build_config(data: dict):
    """根据指定的 Server ID 列表生成 mcp.json 配置文件。

    请求体: {"servers": ["@anthropic/web-search", "@github/github-mcp-server"]}
    生成的配置包含这些 Server 的安装命令 + Hub 网关入口。
    """
    server_ids = data.get("servers", [])
    if not server_ids:
        return {"success": False, "error": "server 列表为空"}

    registry = Registry()
    config = {"mcpServers": {}}

    for sid in server_ids:
        server = await registry.get_by_id(sid)
        if server:
            cmd = server.get("install_command", "")
            name = sid.split("/")[-1]
            if cmd:
                config["mcpServers"][name] = {"command": cmd}

    # 添加 Hub 网关
    config["mcpServers"]["mcp-hub-gateway"] = {
        "command": "mcp",
        "args": ["serve"],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2, ensure_ascii=False)

    return FileResponse(
        tmp.name,
        media_type="application/json",
        filename="mcp-hub-config.json",
    )


@router.post("/config/generate")
async def generate_config():
    """生成完整的 mcp.json 配置文件，包含所有已安装 Server + Hub 网关。"""
    registry = Registry()
    installed = await registry.get_installed()

    config = {"mcpServers": {}}

    # 添加所有已安装的 Server
    for s in installed:
        cmd = s.get("install_command", "")
        name = s["id"].split("/")[-1]
        if cmd:
            config["mcpServers"][name] = {"command": cmd}

    # 添加 Hub 网关入口（如果当前是 daemon 模式）
    config["mcpServers"]["mcp-hub"] = {
        "command": "mcp",
        "args": ["serve"],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(config, tmp, indent=2, ensure_ascii=False)

    return FileResponse(
        tmp.name,
        media_type="application/json",
        filename="mcp-hub-config.json",
    )


@router.get("/config/from-local")
async def config_from_local():
    """尝试读取本地的 mcp.json 配置文件。"""
    paths = [
        Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
        Path.home() / ".cursor" / "mcp.json",
        Path.home() / ".config" / "mcp-hub" / "mcp.json",
    ]
    results = []
    for p in paths:
        if p.exists():
            try:
                content = json.loads(p.read_text())
                servers = list(content.get("mcpServers", {}).keys())
                results.append({
                    "path": str(p),
                    "exists": True,
                    "server_count": len(servers),
                    "servers": servers,
                })
            except Exception:
                results.append({"path": str(p), "exists": True, "error": "无法解析"})
        else:
            results.append({"path": str(p), "exists": False})

    return {"success": True, "data": results}
