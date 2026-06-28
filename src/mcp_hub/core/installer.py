"""MCP Server 安装执行器。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from mcp_hub.core.config_manager import (  # noqa: F401  # re-export
    AGENT_CONFIGS,
    ConfigManager,  # noqa: F401
    get_config_for_agent,
)

# 向后兼容：从 installer 导入仍然有效
from mcp_hub.core.version_manager import VersionManager  # noqa: F401
from mcp_hub.models.server import ServerMeta


class Installer:
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or Path.home() / ".config" / "mcp-hub"

    async def install(self, meta: ServerMeta) -> dict:
        if not meta.install:
            return {"success": False, "error": "安装配置缺失"}
        result = await self._execute_install(meta.install.command)
        if not result["success"]:
            return result

        configs = []
        for agent_key in AGENT_CONFIGS:
            cfg = get_config_for_agent(meta.display_name, meta.install.command, agent_key)
            configs.append(cfg)

        # 记录安装历史
        await self._record_install(meta)

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
        if parts[0] == "npx":
            return {"success": True, "detail": "已通过 npx 注册"}
        try:
            proc = await asyncio.create_subprocess_exec(
                *parts, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                return {"success": False, "error": f"安装失败 (code={proc.returncode}): {stderr.decode()[:300]}"}
            return {"success": True, "detail": stdout.decode()[:200]}
        except asyncio.TimeoutError:
            return {"success": False, "error": "安装超时"}
        except FileNotFoundError:
            return {"success": False, "error": f"命令未找到: {parts[0]}"}
        except Exception as e:
            return {"success": False, "error": f"安装异常: {str(e)}"}

    async def _record_install(self, meta: ServerMeta):
        """记录安装历史到数据库。"""
        from sqlalchemy import text

        from mcp_hub.db.database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(
                text("INSERT INTO install_history (server_id, version, action, status) VALUES (:sid, :ver, 'install', 'success')"),
                {"sid": meta.name, "ver": meta.version or "?"},
            )
            await session.commit()
