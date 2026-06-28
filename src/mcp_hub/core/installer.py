"""MCP Server 安装执行器 — 多 Agent 配置支持。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp_hub.models.server import ServerMeta

# 各 Agent 配置文件路径
AGENT_CONFIGS = {
    "claude-code": {
        "name": "Claude Code",
        "paths": [
            Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
            Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        ],
        "server_key": "mcpServers",
    },
    "cursor": {
        "name": "Cursor",
        "paths": [
            Path.home() / ".cursor" / "mcp.json",
        ],
        "server_key": "mcpServers",
    },
    "codex": {
        "name": "Codex",
        "paths": [
            Path.home() / ".codex" / "mcp.json",
        ],
        "server_key": "mcpServers",
    },
    "trae": {
        "name": "Trae",
        "paths": [
            Path.home() / ".trae" / "mcp.json",
        ],
        "server_key": "mcpServers",
    },
    "generic": {
        "name": "通用 mcp.json",
        "paths": [
            Path.home() / ".config" / "mcp-hub" / "mcp.json",
        ],
        "server_key": "mcpServers",
    },
}


def get_config_for_agent(server_name: str, command: str, agent: str = "generic") -> dict:
    """生成指定 Agent 的配置片段。"""
    cfg = AGENT_CONFIGS.get(agent, AGENT_CONFIGS["generic"])
    return {
        "agent": cfg["name"],
        "config_path": str(cfg["paths"][0]),
        "config_content": {
            cfg["server_key"]: {
                server_name: {"command": command},
            }
        },
    }


class Installer:
    """安装执行器 — 返回配置信息，不硬写用户本地文件。"""

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or Path.home() / ".config" / "mcp-hub"

    async def install(self, meta: ServerMeta) -> dict:
        if not meta.install:
            return {"success": False, "error": "安装配置缺失"}

        result = await self._execute_install(meta.install.command)
        if not result["success"]:
            return result

        # 生成各 Agent 配置
        configs = []
        for agent_key in AGENT_CONFIGS:
            cfg = get_config_for_agent(meta.display_name, meta.install.command, agent_key)
            configs.append(cfg)

        return {
            "success": True,
            "server_id": meta.name,
            "version": meta.version,
            "detail": "安装成功",
            "configs": configs,
        }

    async def _execute_install(self, command: str) -> dict:
        parts = command.split()
        if not parts:
            return {"success": False, "error": "空命令"}

        cmd = parts[0]
        try:
            if cmd == "npx":
                return {"success": True, "detail": "已通过 npx 注册"}

            proc = await asyncio.create_subprocess_exec(
                *parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                return {"success": False, "error": "安装超时"}

            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": f"安装失败 (code={proc.returncode}): {stderr.decode()[:300]}",
                }
            return {"success": True, "detail": stdout.decode()[:200]}

        except FileNotFoundError:
            return {"success": False, "error": f"命令未找到: {cmd}"}
        except Exception as e:
            return {"success": False, "error": f"安装异常: {str(e)}"}


class VersionManager:
    async def check_updates(self) -> list[dict]:
        from mcp_hub.db.repositories import ServerRepository
        from mcp_hub.db.database import async_session_factory
        async with async_session_factory() as session:
            repo = ServerRepository(session)
            servers = await repo.get_installed()
            updates = []
            for s in servers:
                cur = s.get("current_version", "")
                latest = s.get("latest_version", "")
                if latest and cur and latest != cur:
                    updates.append({
                        "server_id": s["id"],
                        "current": cur,
                        "latest": latest,
                        "has_update": True,
                    })
            return updates


class ConfigManager:
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or Path.home() / ".config" / "mcp-hub"

    async def list_config(self, server_id: str, agent: str = "generic") -> dict:
        return get_config_for_agent(server_id.split("/")[-1], "", agent)

    async def set_config(self, server_id: str, key: str, value: str) -> bool:
        return True
