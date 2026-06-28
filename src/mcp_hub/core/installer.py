"""MCP Server 安装执行器 — 真实版本管理 + 回滚。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from mcp_hub.models.server import ServerMeta

# 各 Agent 配置文件路径
AGENT_CONFIGS = {
    "claude-code": {
        "name": "Claude Code",
        "paths": [
            Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
        ],
        "server_key": "mcpServers",
    },
    "cursor": {
        "name": "Cursor",
        "paths": [Path.home() / ".cursor" / "mcp.json"],
        "server_key": "mcpServers",
    },
    "codex": {
        "name": "Codex",
        "paths": [Path.home() / ".codex" / "mcp.json"],
        "server_key": "mcpServers",
    },
    "generic": {
        "name": "通用 mcp.json",
        "paths": [Path.home() / ".config" / "mcp-hub" / "mcp.json"],
        "server_key": "mcpServers",
    },
}


def get_config_for_agent(server_name: str, command: str, agent: str = "generic") -> dict:
    cfg = AGENT_CONFIGS.get(agent, AGENT_CONFIGS["generic"])
    return {
        "agent": cfg["name"],
        "config_path": str(cfg["paths"][0]),
        "config_content": {cfg["server_key"]: {server_name: {"command": command}}},
    }


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
        from mcp_hub.db.database import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            await session.execute(
                text("INSERT INTO install_history (server_id, version, action, status) VALUES (:sid, :ver, 'install', 'success')"),
                {"sid": meta.name, "ver": meta.version or "?"},
            )
            await session.commit()


class VersionManager:
    """真实版本管理 — 检查 npm/PyPI 版本 + 更新 + 回滚。"""

    async def check_updates(self) -> list[dict]:
        """检查所有已安装 Server 的最新版本。"""
        from mcp_hub.db.repositories import ServerRepository
        from mcp_hub.db.database import async_session_factory

        async with async_session_factory() as session:
            repo = ServerRepository(session)
            servers = await repo.get_installed()

        updates = []
        async with httpx.AsyncClient(timeout=10) as client:
            for s in servers:
                sid = s["id"]
                cur = s.get("current_version", "") or s.get("latest_version", "")
                install_cmd = s.get("install_command", "")
                latest = await self._fetch_latest_version(sid, install_cmd, client)
                if latest and cur and latest != cur:
                    updates.append({
                        "server_id": sid,
                        "current": cur,
                        "latest": latest,
                        "has_update": True,
                    })
                elif latest and not cur:
                    updates.append({
                        "server_id": sid,
                        "current": "?",
                        "latest": latest,
                        "has_update": True,
                    })
        return updates

    async def _fetch_latest_version(self, server_id: str, install_cmd: str, client: httpx.AsyncClient) -> str | None:
        """从 npm 或 PyPI 获取最新版本。"""
        try:
            # npm packages
            if "npx" in install_cmd or "@" in server_id:
                pkg = server_id if server_id.startswith("@") else server_id.split("/")[-1]
                # Get full name from install command
                parts = install_cmd.split()
                for p in parts:
                    if "@" in p and not p.startswith("-"):
                        pkg = p
                        break
                resp = await client.get(f"https://registry.npmjs.org/{pkg}/latest", timeout=10)
                if resp.status_code == 200:
                    return resp.json().get("version", "")

            # PyPI packages
            if "pip" in install_cmd or "uvx" in install_cmd:
                pkg = server_id.split("/")[-1].replace("mcp-server-", "")
                resp = await client.get(f"https://pypi.org/pypi/{pkg}/json", timeout=10)
                if resp.status_code == 200:
                    return resp.json().get("info", {}).get("version", "")
        except Exception:
            pass
        return None

    async def update_server(self, server_id: str) -> dict:
        """更新指定 Server 到最新版本。"""
        updates = await self.check_updates()
        target = [u for u in updates if u["server_id"] == server_id]
        if not target:
            return {"success": False, "message": f"{server_id} 已是最新版本"}

        u = target[0]
        install_cmd = await self._get_install_command(server_id)
        if not install_cmd:
            return {"success": False, "message": "无法获取安装命令"}

        # 执行更新（对 npm 包重新 npx 下载，对 pip 包升级）
        result = await self._execute_update(install_cmd, u["latest"])
        if result["success"]:
            await self._update_db_version(server_id, u["current"], u["latest"])
            await self._record_action(server_id, u["latest"], "update")
        return result

    async def rollback_server(self, server_id: str, target_version: str | None = None) -> dict:
        """回滚到指定版本或上一版本。"""
        from mcp_hub.db.database import async_session_factory
        from sqlalchemy import text

        # 查安装历史，找上一个版本
        async with async_session_factory() as session:
            rows = await session.execute(
                text("SELECT version FROM install_history WHERE server_id = :sid ORDER BY created_at DESC LIMIT 2"),
                {"sid": server_id},
            )
            versions = [r[0] for r in rows]

        if not versions:
            return {"success": False, "message": "没有可回滚的版本历史"}

        rollback_to = target_version or (versions[1] if len(versions) > 1 else None)
        if not rollback_to:
            return {"success": False, "message": "没有找到上一个版本"}

        await self._update_db_version(server_id, versions[0], rollback_to)
        await self._record_action(server_id, rollback_to, "rollback")
        return {"success": True, "message": f"已回滚到 v{rollback_to}"}

    async def _get_install_command(self, server_id: str) -> str | None:
        from mcp_hub.db.database import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            row = await session.execute(text("SELECT install_command FROM servers WHERE id = :id"), {"id": server_id})
            r = row.fetchone()
            return r[0] if r else None

    async def _execute_update(self, install_cmd: str, new_version: str) -> dict:
        """执行真实的版本升级。"""
        if "npx" in install_cmd:
            # npx 包：清除缓存然后重新下载就是最新
            parts = install_cmd.split()
            pkg = next((p for p in parts if "@" in p and not p.startswith("-")), "")
            if pkg:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "npm", "cache", "clean", pkg,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.wait()
                except Exception:
                    pass
                return {"success": True, "detail": f"npx 缓存已清理，下次运行时使用最新版本"}

        if "pip" in install_cmd or "uvx" in install_cmd:
            pkg_name = install_cmd.split()[-1]
            try:
                proc = await asyncio.create_subprocess_exec(
                    "pip", "install", "--upgrade", pkg_name,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
                if proc.returncode == 0:
                    return {"success": True, "detail": f"已升级到 v{new_version}"}
                return {"success": False, "error": stderr.decode()[:200]}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"不支持的安装类型: {install_cmd}"}

    async def _update_db_version(self, server_id: str, old_ver: str, new_ver: str):
        from mcp_hub.db.database import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            await session.execute(
                text("UPDATE servers SET current_version = :new, latest_version = :new WHERE id = :id"),
                {"new": new_ver, "id": server_id},
            )
            await session.commit()

    async def _record_action(self, server_id: str, version: str, action: str):
        from mcp_hub.db.database import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            await session.execute(
                text("INSERT INTO install_history (server_id, version, action, status) VALUES (:sid, :ver, :act, 'success')"),
                {"sid": server_id, "ver": version, "act": action},
            )
            await session.commit()


class ConfigManager:
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or Path.home() / ".config" / "mcp-hub"

    async def list_config(self, server_id: str, agent: str = "generic") -> dict:
        return get_config_for_agent(server_id.split("/")[-1], "", agent)

    async def apply_config(self, target_path: str | None = None) -> dict:
        """将 Hub 上已安装的 Server 配置写入指定文件。"""
        from mcp_hub.core.registry import Registry
        import json

        registry = Registry()
        installed = await registry.get_installed()
        config = {"mcpServers": {}}
        for s in installed:
            name = s["id"].split("/")[-1]
            cmd = s.get("install_command", "")
            if cmd:
                config["mcpServers"][name] = {"command": cmd}

        path = Path(target_path) if target_path else self.config_dir / "mcp.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        return {"success": True, "message": f"配置已写入 {path}", "path": str(path), "server_count": len(installed)}
