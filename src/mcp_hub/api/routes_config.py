"""配置绑定 API — 上传/下载/匹配 mcp.json。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any

import httpx
import tomli_w
from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, or_, select, text

from mcp_hub.api.dependencies import get_admin_user, get_current_user
from mcp_hub.core.gateway_config import split_legacy_command
from mcp_hub.core.registry import Registry
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import UserServerModel
from mcp_hub.exceptions import ConfigError
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)

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
    m = re.match(r"^(npx|uvx)\s+(@?[\w][\w.-]*(?:/[\w][\w.-]*)?)", cmd)
    if m:
        return m.group(2)
    # pip install 后面跟的是包名
    m = re.match(r"^pip\s+install\s+(@?[\w][\w.-]*(?:/[\w][\w.-]*)?)", cmd)
    if m:
        return m.group(1)
    return None


async def _resolve_package_online(pkg_name: str) -> dict[str, Any] | None:
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
                    "homepage": data.get("home_page", "")
                    or f"https://pypi.org/project/{pkg_name}/",
                }
    except Exception:
        pass

    return None


@router.get("/config/download")
async def download_config(
    agent: str = "generic",
    user_id: str = Depends(get_current_user),
) -> Response:
    """下载当前用户追踪 Server 的配置 (mcp.json)。"""
    registry = Registry()
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel.server_id)
            .where(
                UserServerModel.user_id == user_id,
                or_(
                    UserServerModel.enabled.is_(True),
                    UserServerModel.enabled.is_(None),
                ),
            )
            .order_by(UserServerModel.created_at)
        )
        server_ids = [row[0] for row in result.fetchall()]

    from mcp_hub.core.config_manager import (
        AGENT_CONFIGS,
        get_config_for_agent,
        server_config_name,
    )

    config_spec = AGENT_CONFIGS.get(agent, AGENT_CONFIGS["generic"])
    server_key = config_spec["server_key"]
    selected_servers: dict[str, Any] = {}
    config: dict[str, Any] = {server_key: selected_servers}
    for server_id in server_ids:
        s = await registry.get_by_id(server_id, include_hidden=True)
        if not s:
            continue
        cmd = s.get("install_command", "")
        name = server_config_name(s["id"], s)
        config_template = s.get("config_template", {})
        if cmd or config_template:
            fragment = get_config_for_agent(
                name,
                cmd,
                agent,
                config_template=config_template if isinstance(config_template, dict) else None,
            )
            selected_servers[name] = fragment["config_content"][server_key][name]

    if config_spec.get("format") == "toml":
        content = tomli_w.dumps(config)
        media_type = "application/toml"
        filename = "mcp-hub-config.toml"
    else:
        content = json.dumps(config, indent=2, ensure_ascii=False)
        media_type = "application/json"
        filename = "mcp-hub-config.json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/config/user-servers")
async def get_user_servers(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """获取当前用户的 Server 配置列表（用户隔离）。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel)
            .where(UserServerModel.user_id == user_id)
            .order_by(UserServerModel.created_at)
        )
        servers: list[dict[str, Any]] = []
        for row in result.scalars().all():
            servers.append(
                {
                    "name": row.server_id,
                    "hub_id": row.server_id,
                    "matched": row.matched,
                    "enabled": row.enabled if row.enabled is not None else True,
                    "agent": row.agent or "",
                    "group_name": row.group_name or "",
                }
            )
    return {"success": True, "data": servers}


@router.post("/config/user-servers/save")
async def save_user_servers(
    data: dict[str, Any],
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """保存当前用户的 Server 配置列表（覆盖式）。"""
    servers = data.get("servers", [])
    if not isinstance(servers, list):
        return {"success": False, "error": "servers 必须是列表"}

    async with async_session_factory() as session:
        # 删除旧记录
        await session.execute(delete(UserServerModel).where(UserServerModel.user_id == user_id))
        # 写入新记录
        for s in servers:
            if not isinstance(s, dict):
                continue
            sid = s.get("hub_id") or s.get("name", "")
            if sid:
                session.add(
                    UserServerModel(
                        user_id=user_id,
                        server_id=sid,
                        matched=s.get("matched", True),
                        enabled=s.get("enabled", True),
                        agent=s.get("agent", ""),
                        group_name=s.get("group_name", ""),
                    )
                )
        await session.commit()

    return {"success": True, "message": f"已保存 {len(servers)} 个 Server"}


@router.post("/config/user-servers/toggle")
async def toggle_server_enabled(
    data: dict[str, Any],
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """直接切换单个 Server 的启用/禁用状态（无需加载全部再保存）。"""
    server_id = data.get("server_id", "")
    enabled = data.get("enabled", True)

    if not server_id:
        return {"success": False, "error": "需要 server_id"}

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE user_servers SET enabled = :en WHERE user_id = :uid AND server_id = :sid"),
            {"en": enabled, "uid": user_id, "sid": server_id},
        )
        await session.commit()

    return {
        "success": True,
        "enabled": enabled,
        "message": f"{'启用' if enabled else '禁用'} {server_id}",
    }


@router.delete("/config/user-servers/{server_id:path}")
async def remove_user_server(
    server_id: str,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """从用户配置中移除单个 Server。"""
    async with async_session_factory() as session:
        await session.execute(
            delete(UserServerModel).where(
                UserServerModel.user_id == user_id, UserServerModel.server_id == server_id
            )
        )
        await session.commit()

    return {"success": True, "message": f"已移除 {server_id}"}


@router.post("/config/upload")
async def upload_config(
    file: Annotated[UploadFile, File(...)],
    user_id: str = Depends(get_current_user),
    x_agent_id: str = Header(""),
    x_track_servers: str = Header("false"),
) -> dict[str, Any]:
    """上传本地的 claude_desktop_config.json，匹配市场中的 Server。

    返回上传配置中每个 Server 在 Hub 市场中的匹配情况，
    并推荐可安装的 Server 列表。
    """
    content = await file.read()
    try:
        config = json.loads(content)
    except json.JSONDecodeError as err:
        raise ConfigError("无效的 JSON 文件") from err
    if not isinstance(config, dict):
        raise ConfigError("配置文件根节点必须是对象")

    servers_map = config.get("mcpServers", {})
    if not isinstance(servers_map, dict):
        raise ConfigError("mcpServers 必须是对象")

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
    from sqlalchemy import delete

    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.models import UserServerModel

    registry = Registry()
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    not_in_hub: list[dict[str, Any]] = []
    all_tracked: list[dict[str, Any]] = []
    track_servers = x_track_servers.lower() == "true"

    for raw_name, cfg in servers_map.items():
        name = str(raw_name)
        if not isinstance(cfg, dict):
            not_in_hub.append(
                {
                    "local_name": name,
                    "local_command": "",
                    "server_count": 1,
                    "matched": False,
                }
            )
            continue
        cmd = cfg.get("command", "") + " " + " ".join(cfg.get("args", []))
        cmd = cmd.strip()

        # 尝试在 Hub 中搜索匹配
        results, _ = await registry.search(q=name, page=1, page_size=10)

        # 精确匹配：名称或命令包含
        found = None
        for s in results:
            sid = s.get("id", "")
            scmd = s.get("install_command", "")
            try:
                executable, _args = split_legacy_command(scmd)
            except ValueError:
                executable = ""
            if name in sid or (executable and cmd and executable in cmd):
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
                    if track_servers:
                        try:
                            await registry.register_server(
                                {
                                    "id": sid,
                                    "name": resolved["name"],
                                    "description": resolved.get(
                                        "description", f"从 {resolved['source']} 发现的 MCP Server"
                                    ),
                                    "install_command": cmd,
                                    "install_type": resolved["source"],
                                    "categories": json.dumps(["tools"]),
                                    "tags": json.dumps([resolved["source"], "discovered"]),
                                    "homepage": resolved.get("homepage", ""),
                                    "author": resolved["source"],
                                    "security_level": "reviewed",
                                }
                            )
                        except Exception:
                            logger.warning(
                                "config.register_discovered_failed",
                                name=name,
                                source=resolved.get("source"),
                            )
                else:
                    # 线上也查不到，才标为自定义
                    unmatched.append(entry)
                    sid = f"@custom/{name}"
                    all_tracked.append({"server_id": sid, "matched": False})
                    if track_servers:
                        try:
                            try:
                                install_type, _args = split_legacy_command(cmd)
                            except ValueError:
                                install_type = "custom"
                            await registry.register_server(
                                {
                                    "id": sid,
                                    "name": name,
                                    "description": f"自定义 Server: {name}",
                                    "install_command": cmd,
                                    "install_type": install_type,
                                    "categories": json.dumps(["custom"]),
                                    "tags": json.dumps(["user-uploaded"]),
                                    "author": "user",
                                }
                            )
                            entry["registered_id"] = sid
                        except Exception:
                            logger.warning("config.register_custom_failed", name=name)
            else:
                entry["matched"] = False
                not_in_hub.append(entry)

    if track_servers:
        async with async_session_factory() as session:
            # 先清理当前用户的旧记录
            await session.execute(delete(UserServerModel).where(UserServerModel.user_id == user_id))
            # 写入新记录
            for ts in all_tracked:
                session.add(
                    UserServerModel(
                        user_id=user_id,
                        server_id=ts["server_id"],
                        matched=ts["matched"],
                        agent=x_agent_id if x_agent_id else "",
                    )
                )
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
            f"配置包含 {len(servers_map)} 个 Server，"
            f"已安装 {len(matched)} 个（市场匹配），"
            f"{len(unmatched)} 个已注册为自定义 Server"
        ),
    }


@router.post("/config/build", response_model=None)
async def build_config(data: dict[str, Any]) -> Response | dict[str, Any]:
    """根据指定的 Server ID 列表生成 mcp.json 配置文件。

    请求体: {"servers": ["@anthropic/web-search", "@github/github-mcp-server"]}
    生成的配置包含这些 Server 的安装命令 + Hub 网关入口。
    """
    server_ids = data.get("servers", [])
    agent = data.get("agent", "generic")
    if not server_ids:
        return {"success": False, "error": "server 列表为空"}

    from mcp_hub.core.config_manager import (
        AGENT_CONFIGS,
        get_config_for_agent,
        server_config_name,
    )

    registry = Registry()
    config_spec = AGENT_CONFIGS.get(agent, AGENT_CONFIGS["generic"])
    server_key = config_spec["server_key"]
    server_configs: dict[str, Any] = {}
    config: dict[str, Any] = {server_key: server_configs}

    for sid in server_ids:
        server = await registry.get_by_id(sid)
        if server:
            cmd = server.get("install_command", "")
            name = server_config_name(sid, server)
            config_template = server.get("config_template", {})
            if cmd or config_template:
                fragment = get_config_for_agent(
                    name,
                    cmd,
                    agent,
                    config_template=(
                        config_template if isinstance(config_template, dict) else None
                    ),
                )
                server_configs[name] = fragment["config_content"][server_key][name]

    if config_spec.get("format") == "toml":
        return Response(
            content=tomli_w.dumps(config),
            media_type="application/toml",
            headers={"Content-Disposition": "attachment; filename=mcp-hub-config.toml"},
        )
    return Response(
        content=json.dumps(config, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=mcp-hub-config.json"},
    )


@router.post("/config/generate")
async def generate_config(_admin_id: str = Depends(get_admin_user)) -> Response:
    """生成完整的 mcp.json 配置文件，包含所有已安装 Server + Hub 网关。"""
    from mcp_hub.core.config_manager import get_config_for_agent, server_config_name

    registry = Registry()
    installed = await registry.get_installed()

    generated_servers: dict[str, Any] = {}
    config: dict[str, Any] = {"mcpServers": generated_servers}

    # 添加所有已安装的 Server
    for s in installed:
        cmd = s.get("install_command", "")
        name = server_config_name(s["id"], s)
        config_template = s.get("config_template", {})
        if cmd or config_template:
            fragment = get_config_for_agent(
                name,
                cmd,
                "generic",
                config_template=config_template if isinstance(config_template, dict) else None,
            )
            generated_servers[name] = fragment["config_content"]["mcpServers"][name]

    return Response(
        content=json.dumps(config, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=mcp-hub-config.json"},
    )


@router.get("/config/from-local")
async def config_from_local(
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """尝试读取本地的 mcp.json 配置文件。

    扫描所有已知 Agent 的标准路径：
    Claude Code, Claude Desktop, Cursor, Codex, Trae,
    以及项目目录下的 mcp.json / .mcp.json。
    """
    from mcp_hub.core.config_manager import AGENT_CONFIGS

    # 从 AGENT_CONFIGS 收集所有已知路径，去重
    seen: set[str] = set()
    paths: list[tuple[str, Path]] = []  # (agent_label, path)
    for _agent_key, cfg in AGENT_CONFIGS.items():
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

    results: list[dict[str, Any]] = []
    for agent_label, p in paths:
        if p.exists():
            try:
                content = json.loads(p.read_text())
                servers = list(content.get("mcpServers", {}).keys())
                results.append(
                    {
                        "path": str(p),
                        "agent": agent_label,
                        "exists": True,
                        "server_count": len(servers),
                        "servers": servers,
                    }
                )
            except Exception:
                results.append(
                    {
                        "path": str(p),
                        "agent": agent_label,
                        "exists": True,
                        "error": "无法解析",
                    }
                )
        else:
            results.append(
                {
                    "path": str(p),
                    "agent": agent_label,
                    "exists": False,
                }
            )

    return {"success": True, "data": results}


# ── 本地 Agent 发现 ─────────────────────────────────────────


@router.get("/local/discover")
async def local_discover(
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """扫描本机所有 AI Agent 的 MCP 配置文件。

    自动发现 Claude Code、Claude Desktop、Cursor、Codex、Trae、
    Windsurf、VS Code Copilot 及项目本地目录下的 MCP 配置。
    """
    from mcp_hub.core.local_discovery import LocalAgentDiscovery

    discovery = LocalAgentDiscovery()
    result = await discovery.get_agent_summary()
    return {"success": True, "data": result}


@router.get("/local/compare")
async def local_compare(
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
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
async def local_conflicts(
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
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
async def config_diff(
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
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
async def config_backup(
    data: dict[str, Any],
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """备份当前配置。可附带 label 标签。"""
    from mcp_hub.core.config_manager import ConfigManager

    label = data.get("label", "")
    cm = ConfigManager()
    result = await cm.backup_config(label)
    return result


@router.get("/config/backups")
async def config_backups_list(
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """列出所有配置备份。"""
    from mcp_hub.core.config_manager import ConfigManager

    cm = ConfigManager()
    backups = await cm.list_backups()
    return {"success": True, "data": backups}


@router.post("/config/restore/{filename:path}")
async def config_restore(
    filename: str,
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """从指定备份恢复配置。"""
    from mcp_hub.core.config_manager import ConfigManager

    cm = ConfigManager()
    result = await cm.restore_backup(filename)
    return result


@router.post("/servers/pre-check")
async def server_pre_check(
    data: dict[str, Any],
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
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
async def server_dependency_analyze(
    data: dict[str, Any],
    _admin_id: str = Depends(get_admin_user),
) -> dict[str, Any]:
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
async def list_groups(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """列出当前用户的所有分组及其包含的 Server。"""
    from sqlalchemy import text

    from mcp_hub.db.database import async_session_factory

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
async def set_server_group(
    data: dict[str, Any],
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """为指定 Server 设置分组。"""
    from sqlalchemy import text

    from mcp_hub.db.database import async_session_factory

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
async def batch_set_group(
    data: dict[str, Any],
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """批量设置多个 Server 的分组（启用/禁用整个分组时用）。"""
    from sqlalchemy import text

    from mcp_hub.db.database import async_session_factory

    group_name = data.get("group_name", "")
    action = data.get("action", "")  # "enable" or "disable"

    if not group_name:
        return {"success": False, "error": "需要 group_name"}
    if action not in {"enable", "disable"}:
        return {"success": False, "error": "action 必须是 enable 或 disable"}
    enabled = action == "enable"

    async with async_session_factory() as session:
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
