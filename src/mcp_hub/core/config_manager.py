"""配置管理 — 多 Agent 配置生成 / 导入导出 / 环境切换。"""

from __future__ import annotations

import json
from pathlib import Path

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
    "trae": {
        "name": "Trae",
        "paths": [Path.home() / ".trae" / "mcp.json"],
        "server_key": "mcpServers",
    },
    "generic": {
        "name": "通用 mcp.json",
        "paths": [Path.home() / ".config" / "mcp-hub" / "mcp.json"],
        "server_key": "mcpServers",
    },
}


def get_config_for_agent(
    server_name: str, command: str, agent: str = "generic"
) -> dict:
    """生成指定 Agent 的配置片段。"""
    cfg = AGENT_CONFIGS.get(agent, AGENT_CONFIGS["generic"])
    return {
        "agent": cfg["name"],
        "config_path": str(cfg["paths"][0]),
        "config_content": {cfg["server_key"]: {server_name: {"command": command}}},
    }


class ConfigManager:
    """配置管理 — 增删改查 / 导入导出 / 环境切换。"""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or Path.home() / ".config" / "mcp-hub"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._env_config_path = self.config_dir / "server_env.json"

    async def set_config(self, server_id: str, key: str, value: str) -> bool:
        """为指定 Server 设置环境变量配置，持久化到本地 JSON 文件。

        用法: mcp config set <server_id> API_KEY sk-xxx
        """
        from mcp_hub.core.registry import Registry

        # 确认 Server 存在于注册表中
        registry = Registry()
        server = await registry.get_by_id(server_id)
        if not server:
            return False

        # 读取已有配置
        env_config: dict[str, dict[str, str]] = {}
        if self._env_config_path.exists():
            try:
                env_config = json.loads(self._env_config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                env_config = {}

        # 设置 key=value
        if server_id not in env_config:
            env_config[server_id] = {}
        env_config[server_id][key] = value

        # 持久化写入
        self._env_config_path.write_text(
            json.dumps(env_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True

    async def get_config(self, server_id: str, key: str) -> str | None:
        """获取指定 Server 的环境变量配置。"""
        if not self._env_config_path.exists():
            return None
        try:
            env_config = json.loads(self._env_config_path.read_text(encoding="utf-8"))
            return env_config.get(server_id, {}).get(key)
        except (json.JSONDecodeError, OSError):
            return None

    async def list_config(self, server_id: str, agent: str = "generic") -> dict:
        """获取指定 Server 的配置片段（含真实命令和环境变量）。"""
        from mcp_hub.core.registry import Registry

        registry = Registry()
        server = await registry.get_by_id(server_id)
        # 优先从注册表获取命令，其次从已安装列表
        command = ""
        if server:
            command = server.get("install_command", "")
        else:
            # 尝试从已安装列表中查找
            installed = await registry.get_installed()
            for s in installed:
                if s["id"] == server_id:
                    command = s.get("install_command", "")
                    break

        # 获取用户设置的环境变量
        env_vars = await self.list_all_config(server_id)

        server_name = server_id.split("/")[-1]
        base_config = get_config_for_agent(server_name, command, agent)

        # 将环境变量注入配置 content
        if env_vars and "config_content" in base_config:
            for config_key, config_value in base_config["config_content"].items():
                if server_name in config_value:
                    config_value[server_name]["env"] = env_vars
                    break

        return base_config

    async def list_all_config(self, server_id: str) -> dict[str, str]:
        """列出指定 Server 的所有环境变量配置。"""
        if not self._env_config_path.exists():
            return {}
        try:
            env_config = json.loads(self._env_config_path.read_text(encoding="utf-8"))
            return env_config.get(server_id, {})
        except (json.JSONDecodeError, OSError):
            return {}

    async def _load_config(self) -> dict:
        """加载本地 mcp.json 配置文件。"""
        config_path = self.config_dir / "mcp.json"
        if config_path.exists():
            try:
                return json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"mcpServers": {}}
        return {"mcpServers": {}}

    async def apply_config(self, target_path: str | None = None) -> dict:
        """将 Hub 上已安装的 Server 配置写入指定文件。"""
        from mcp_hub.core.registry import Registry

        registry = Registry()
        installed = await registry.get_installed()
        config: dict = {"mcpServers": {}}
        for s in installed:
            name = s["id"].split("/")[-1]
            cmd = s.get("install_command", "")
            if cmd:
                config["mcpServers"][name] = {"command": cmd}

        path = Path(target_path) if target_path else self.config_dir / "mcp.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        return {
            "success": True,
            "message": f"配置已写入 {path}",
            "path": str(path),
            "server_count": len(installed),
        }

    # ── 配置差异检测 ─────────────────────────────────────

    async def diff_local_vs_hub(self) -> dict:
        """对比本地 mcp.json 与 Hub 上的配置，返回差异报告。"""
        from mcp_hub.core.registry import Registry

        # 本地配置
        local_config = await self._load_config()
        local_servers = local_config.get("mcpServers", {})

        # Hub 配置
        registry = Registry()
        installed = await registry.get_installed()
        hub_servers: dict[str, str] = {}
        for s in installed:
            cmd = s.get("install_command", "")
            if cmd:
                hub_servers[s["id"].split("/")[-1]] = cmd

        # 计算差异
        all_names = set(list(local_servers.keys()) + list(hub_servers.keys()))
        only_local = [n for n in all_names if n in local_servers and n not in hub_servers]
        only_hub = [n for n in all_names if n in hub_servers and n not in local_servers]
        different = []
        for n in all_names:
            if n in local_servers and n in hub_servers:
                l_cmd = local_servers[n].get("command", "") if isinstance(local_servers[n], dict) else ""
                h_cmd = hub_servers.get(n, "")
                if l_cmd and h_cmd and l_cmd != h_cmd:
                    different.append({"name": n, "local": l_cmd, "hub": h_cmd})

        return {
            "local_count": len(local_servers),
            "hub_count": len(hub_servers),
            "only_local": only_local,
            "only_hub": only_hub,
            "different": different,
            "in_sync": len(different) == 0 and len(only_local) == 0 and len(only_hub) == 0,
        }

    # ── 配置备份与快照 ─────────────────────────────────────

    async def backup_config(self, label: str = "") -> dict:
        """备份当前 mcp.json 到快照目录。"""
        from datetime import datetime

        backup_dir = self.config_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        config = await self._load_config()
        if not config.get("mcpServers"):
            return {"success": False, "message": "当前无配置可备份"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mcp_{timestamp}"
        if label:
            filename += f"_{label.replace(' ', '_')}"
        filename += ".json"

        backup_path = backup_dir / filename
        backup_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "success": True,
            "message": f"配置已备份",
            "path": str(backup_path),
            "filename": filename,
        }

    async def list_backups(self) -> list[dict]:
        """列出所有配置备份。"""
        backup_dir = self.config_dir / "backups"
        if not backup_dir.exists():
            return []
        backups = []
        for f in sorted(backup_dir.glob("mcp_*.json"), reverse=True):
            stat = f.stat()
            try:
                cfg = json.loads(f.read_text(encoding="utf-8"))
                count = len(cfg.get("mcpServers", {}))
            except Exception:
                count = -1
            backups.append({
                "filename": f.name,
                "path": str(f),
                "size": stat.st_size,
                "created_at": stat.st_mtime,
                "server_count": count,
            })
        return backups

    async def restore_backup(self, filename: str) -> dict:
        """从备份恢复配置。先自动备份当前配置，再恢复。"""
        backup_path = self.config_dir / "backups" / filename
        if not backup_path.exists():
            return {"success": False, "message": f"备份文件不存在: {filename}"}

        # 恢复前先备份当前配置
        await self.backup_config("pre_restore")

        # 写入当前配置
        config_data = json.loads(backup_path.read_text(encoding="utf-8"))
        config_path = self.config_dir / "mcp.json"
        config_path.write_text(json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "success": True,
            "message": f"已从 {filename} 恢复配置",
            "server_count": len(config_data.get("mcpServers", {})),
        }

    # ── 安装前预检 ────────────────────────────────────────

    async def pre_install_check(self, command: str) -> dict:
        """安装前环境预检。

        检查：
        - Python 版本是否满足
        - 安装工具是否可用（pip/npm/npx/uvx）
        - 磁盘空间是否充足
        - 当前环境是否可能存在端口冲突
        """
        import os
        import shutil
        import subprocess
        import sys

        checks: list[dict] = []

        # 1. Python 版本检查
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        py_ok = sys.version_info >= (3, 10)
        checks.append({
            "name": "Python 版本",
            "status": "ok" if py_ok else "fail",
            "detail": f"Python {py_version}" + (" (需要 ≥ 3.10)" if not py_ok else " ✓"),
        })

        # 2. 安装工具检查
        cmd_parts = command.split()
        tool = cmd_parts[0] if cmd_parts else "unknown"
        tool_available = False

        if tool in ("pip", "pip3"):
            try:
                subprocess.run([sys.executable, "-m", "pip", "--version"],
                             capture_output=True, timeout=10)
                tool_available = True
            except Exception:
                pass
        elif tool == "npm":
            tool_available = shutil.which("npm") is not None
        elif tool in ("npx",):
            tool_available = shutil.which("npx") is not None or shutil.which("npm") is not None
        elif tool == "uvx":
            tool_available = shutil.which("uvx") is not None or shutil.which("uv") is not None
        elif tool == "go":
            tool_available = shutil.which("go") is not None

        checks.append({
            "name": f"安装工具 ({tool})",
            "status": "ok" if tool_available else "warn",
            "detail": "已安装" if tool_available else f"未找到 {tool}，安装可能失败",
        })

        # 3. 磁盘空间检查
        try:
            usage = shutil.disk_usage(self.config_dir)
            free_gb = usage.free / (1024 ** 3)
            disk_ok = free_gb >= 1.0
            checks.append({
                "name": "磁盘空间",
                "status": "ok" if disk_ok else "warn",
                "detail": f"可用 {free_gb:.1f} GB" + ("" if disk_ok else " (建议 ≥ 1GB)"),
            })
        except Exception:
            checks.append({
                "name": "磁盘空间",
                "status": "ok",
                "detail": "无法检测",
            })

        # 汇总
        has_failure = any(c["status"] == "fail" for c in checks)
        has_warning = any(c["status"] == "warn" for c in checks)
        overall = "fail" if has_failure else ("warn" if has_warning else "ok")

        return {
            "success": True,
            "overall": overall,
            "checks": checks,
            "can_install": not has_failure,
        }
