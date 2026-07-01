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
from sqlalchemy import delete, select, text

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
async def get_user_servers(x_user_id: str = Header("anonymous")):
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
                "enabled": row.enabled if row.enabled is not None else True,
                "agent": row.agent or "",
                "group_name": row.group_name or "",
            })
    return {"success": True, "data": servers}


@router.post("/config/user-servers/save")
async def save_user_servers(data: dict, x_user_id: str = Header("anonymous")):
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


@router.post("/config/user-servers/toggle")
async def toggle_server_enabled(data: dict, x_user_id: str = Header("anonymous")):
    """直接切换单个 Server 的启用/禁用状态（无需加载全部再保存）。"""
    server_id = data.get("server_id", "")
    enabled = data.get("enabled", True)

    if not server_id:
        return {"success": False, "error": "需要 server_id"}

    async with async_session_factory() as session:
        await session.execute(
            text(
                "UPDATE user_servers SET enabled = :en "
                "WHERE user_id = :uid AND server_id = :sid"
            ),
            {"en": enabled, "uid": x_user_id, "sid": server_id},
        )
        await session.commit()

    return {
        "success": True,
        "enabled": enabled,
        "message": f"{'启用' if enabled else '禁用'} {server_id}",
    }


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
                        logger.warning("config.register_discovered_failed", name=name, source=resolved.get("source"))
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
                        logger.warning("config.register_custom_failed", name=name)
            else:
                entry["matched"] = False
                not_in_hub.append(entry)

    # 同步所有 server 到 user_servers 表，同时标记为已安装（stopped）
    async with async_session_factory() as session:
        # 先清理当前用户的旧记录
        await session.execute(
            delete(UserServerModel).where(UserServerModel.user_id == x_user_id)
        )
        # 写入新记录
        for ts in all_tracked:
            session.add(UserServerModel(
                user_id=x_user_id,
                server_id=ts["server_id"],
                matched=ts["matched"],
                agent=x_agent_id if x_agent_id else "",
            ))
        await session.commit()

    # 将所有匹配到的 Server 状态改为 stopped（视为已安装）
    for ts in all_tracked:
        try:
            await registry.update_status(ts["server_id"], "stopped")
        except Exception:
            pass

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
            f"配置包含 {len(servers_map)} 个 Server，"
            f"已安装 {len(matched)} 个（市场匹配），"
            f"{len(unmatched)} 个已注册为自定义 Server"
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
    """尝试读取本地的 mcp.json 配置文件。

    扫描所有已知 Agent 的标准路径：
    Claude Code, Claude Desktop, Cursor, Codex, Trae,
    以及项目目录下的 mcp.json / .mcp.json。
    """
    from mcp_hub.core.config_manager import AGENT_CONFIGS

    # 从 AGENT_CONFIGS 收集所有已知路径，去重
    seen = set()
    paths: list[tuple[str, Path]] = []  # (agent_label, path)
    for agent_key, cfg in AGENT_CONFIGS.items():
        for p in cfg["paths"]:
            p_str = str(p)
            if p_str not in seen:
                seen.add(p_str)
                paths.append((cfg["name"], p))

    # 额外扫描项目本地目录
    extra_paths = [
        ("项目本地", Path.cwd() / "mcp.json"),
        ("项目本地", Path.cwd() / ".mcp.json"),
    ]
    for label, ep in extra_paths:
        ep_str = str(ep)
        if ep_str not in seen:
            seen.add(ep_str)
            paths.append((label, ep))

    results = []
    for agent_label, p in paths:
        if p.exists():
            try:
                content = json.loads(p.read_text())
                servers = list(content.get("mcpServers", {}).keys())
                results.append({
                    "path": str(p),
                    "agent": agent_label,
                    "exists": True,
                    "server_count": len(servers),
                    "servers": servers,
                })
            except Exception:
                results.append({
                    "path": str(p),
                    "agent": agent_label,
                    "exists": True,
                    "error": "无法解析",
                })
        else:
            results.append({
                "path": str(p),
                "agent": agent_label,
                "exists": False,
            })

    return {"success": True, "data": results}


# ── 本地 Agent 发现 ─────────────────────────────────────────


@router.get("/local/discover")
async def local_discover():
    """扫描本机所有 AI Agent 的 MCP 配置文件。

    自动发现 Claude Code、Claude Desktop、Cursor、Codex、Trae、
    Windsurf、VS Code Copilot 及项目本地目录下的 MCP 配置。
    """
    from mcp_hub.core.local_discovery import LocalAgentDiscovery

    discovery = LocalAgentDiscovery()
    result = await discovery.get_agent_summary()
    return {"success": True, "data": result}


@router.get("/local/compare")
async def local_compare():
    """跨 Agent 对比 MCP 配置。

    返回每个 MCP Server 在各 Agent 中的分布情况：
    - 哪些 Agent 已安装，哪些缺失
    - 同一 Server 在不同 Agent 中的命令是否一致
    """
    from mcp_hub.core.local_discovery import LocalAgentDiscovery

    discovery = LocalAgentDiscovery()
    compare_results = await discovery.compare_agents()
    return {
        "success": True,
        "data": [
            {
                "server_name": c.server_name,
                "present_in": c.present_in,
                "absent_in": c.absent_in,
                "commands": c.commands,
                "has_conflict": c.has_conflict,
            }
            for c in compare_results
        ],
    }


@router.get("/local/conflicts")
async def local_conflicts():
    """检测本地 MCP 配置冲突。

    发现同名 Server 在不同 Agent 中配置了不同的命令或参数，
    这可能导致行为不一致。
    """
    from mcp_hub.core.local_discovery import LocalAgentDiscovery

    discovery = LocalAgentDiscovery()
    conflicts = await discovery.detect_conflicts()
    return {
        "success": True,
        "data": [
            {
                "server_name": c.server_name,
                "agent_a": c.agent_a,
                "command_a": c.command_a,
                "agent_b": c.agent_b,
                "command_b": c.command_b,
                "severity": c.severity,
            }
            for c in conflicts
        ],
    }


# ── 配置差异、备份、预检 ──────────────────────────────────


@router.get("/config/diff")
async def config_diff():
    """对比本地 mcp.json 与 Hub 上的配置差异。

    返回：
    - only_local: 本地有但 Hub 没有的 Server
    - only_hub: Hub 有但本地没有的 Server
    - different: 两边都有但命令不同的 Server
    - in_sync: 是否完全同步
    """
    from mcp_hub.core.config_manager import ConfigManager

    cm = ConfigManager()
    result = await cm.diff_local_vs_hub()
    return {"success": True, "data": result}


@router.post("/config/backup")
async def config_backup(data: dict):
    """备份当前配置。可附带 label 标签。"""
    from mcp_hub.core.config_manager import ConfigManager

    label = data.get("label", "")
    cm = ConfigManager()
    result = await cm.backup_config(label)
    return result


@router.get("/config/backups")
async def config_backups_list():
    """列出所有配置备份。"""
    from mcp_hub.core.config_manager import ConfigManager

    cm = ConfigManager()
    backups = await cm.list_backups()
    return {"success": True, "data": backups}


@router.post("/config/restore/{filename:path}")
async def config_restore(filename: str):
    """从指定备份恢复配置。"""
    from mcp_hub.core.config_manager import ConfigManager

    cm = ConfigManager()
    result = await cm.restore_backup(filename)
    return result


@router.post("/servers/pre-check")
async def server_pre_check(data: dict):
    """安装前环境预检。

    请求体: {"command": "uvx mcp-server-web-search"}
    返回: overall + 逐项检查结果 + can_install 标志
    """
    from mcp_hub.core.config_manager import ConfigManager

    command = data.get("command", "")
    if not command:
        return {"success": False, "error": "需要提供 command"}

    cm = ConfigManager()
    result = await cm.pre_install_check(command)
    return result


@router.post("/servers/dependency-analyze")
async def server_dependency_analyze(data: dict):
    """分析 MCP Server 的完整依赖链。

    请求体: {"server_id": "@anthropic/web-search", "command": "uvx mcp-server-web-search"}
    返回: 运行时需求 + 环境变量需求 + 缺失清单 + 安装建议
    """
    from mcp_hub.core.dependency_analyzer import DependencyAnalyzer

    server_id = data.get("server_id", "")
    command = data.get("command", "")

    if not command:
        return {"success": False, "error": "需要提供 command"}

    analyzer = DependencyAnalyzer(server_id=server_id, command=command)
    report = await analyzer.analyze()

    return {
        "success": True,
        "data": {
            "server_id": report.server_id,
            "command": report.command,
            "install_tool": report.install_tool,
            "runtime_requirements": [
                {
                    "name": r.name,
                    "min_version": r.min_version,
                    "installed": r.installed,
                    "installed_version": r.installed_version,
                    "message": r.message,
                }
                for r in report.runtime_requirements
            ],
            "env_var_requirements": [
                {
                    "name": e.name,
                    "description": e.description,
                    "required": e.required,
                    "category": e.category,
                    "is_set": e.is_set,
                    "help_url": e.help_url,
                }
                for e in report.env_var_requirements
            ],
            "system_tools": report.system_tools,
            "missing_count": report.missing_count,
            "warning_count": report.warning_count,
            "ready_to_install": report.ready_to_install,
            "suggestions": report.suggestions,
            "notes": report.notes,
        },
    }


# ── Server 分组管理 ────────────────────────────────────────


@router.get("/config/groups")
async def list_groups(request: Request):
    """列出当前用户的所有分组及其包含的 Server。"""
    from sqlalchemy import text
    from mcp_hub.db.database import async_session_factory

    user_id = request.headers.get("x-user-id", "anonymous")
    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT group_name, server_id FROM user_servers "
                "WHERE user_id = :uid AND group_name != '' "
                "ORDER BY group_name, server_id"
            ),
            {"uid": user_id},
        )
        rows = result.fetchall()

    groups: dict[str, list[str]] = {}
    for row in rows:
        gname = row[0]
        sid = row[1]
        if gname not in groups:
            groups[gname] = []
        groups[gname].append(sid)

    return {
        "success": True,
        "data": [
            {"name": name, "servers": servers, "count": len(servers)}
            for name, servers in groups.items()
        ],
    }


@router.post("/config/groups/set")
async def set_server_group(request: Request, data: dict):
    """为指定 Server 设置分组。"""
    from sqlalchemy import text
    from mcp_hub.db.database import async_session_factory

    user_id = request.headers.get("x-user-id", "anonymous")
    server_id = data.get("server_id", "")
    group_name = data.get("group_name", "")

    if not server_id:
        return {"success": False, "error": "需要 server_id"}

    async with async_session_factory() as session:
        await session.execute(
            text(
                "UPDATE user_servers SET group_name = :gname "
                "WHERE user_id = :uid AND server_id = :sid"
            ),
            {"gname": group_name, "uid": user_id, "sid": server_id},
        )
        await session.commit()

    return {"success": True, "message": f"已将 {server_id} 设置为分组 '{group_name}'"}


@router.post("/config/groups/batch")
async def batch_set_group(request: Request, data: dict):
    """批量设置多个 Server 的分组（启用/禁用整个分组时用）。"""
    from sqlalchemy import text
    from mcp_hub.db.database import async_session_factory

    user_id = request.headers.get("x-user-id", "anonymous")
    group_name = data.get("group_name", "")
    action = data.get("action", "")  # "enable" or "disable"
    enabled = True if action == "enable" else (False if action == "disable" else None)

    if not group_name:
        return {"success": False, "error": "需要 group_name"}

    async with async_session_factory() as session:
        if enabled is not None:
            await session.execute(
                text(
                    "UPDATE user_servers SET enabled = :en "
                    "WHERE user_id = :uid AND group_name = :gname"
                ),
                {"en": enabled, "uid": user_id, "gname": group_name},
            )
        await session.commit()

    msg = f"已{'启用' if enabled else '禁用'}分组 '{group_name}' 中的所有 Server"
    return {"success": True, "message": msg}
