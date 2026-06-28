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

    async def list_config(self, server_id: str, agent: str = "generic") -> dict:
        """获取指定 Server 的配置片段。"""
        return get_config_for_agent(server_id.split("/")[-1], "", agent)

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
