"""本地 AI Agent MCP 配置发现服务。

扫描用户电脑上所有已知 AI Agent 的 MCP 配置文件，提供：
- discover_all(): 扫描所有 Agent
- compare_agents(): 跨 Agent 对比（谁有谁没有哪些 Server）
- detect_conflicts(): 检测配置冲突（同名 Server 不同命令）

支持的 Agent（自动发现）：
  Claude Code, Claude Desktop, Cursor, Codex, Trae, Windsurf, VS Code Copilot,
  以及项目目录下的 mcp.json / .mcp.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)

# 已知 AI Agent 的 MCP 配置文件路径
KNOWN_AGENT_PATHS: dict[str, dict] = {
    "claude-code": {
        "name": "Claude Code (CLI)",
        "paths": [
            Path.home() / ".config" / "claude-code" / "mcp.json",
            Path.home() / ".claude" / "mcp.json",
        ],
    },
    "claude-desktop": {
        "name": "Claude Desktop",
        "paths": [
            Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
        ],
    },
    "cursor": {
        "name": "Cursor",
        "paths": [
            Path.home() / ".cursor" / "mcp.json",
        ],
    },
    "codex": {
        "name": "Codex",
        "paths": [
            Path.home() / ".codex" / "mcp.json",
        ],
    },
    "trae": {
        "name": "Trae",
        "paths": [
            Path.home() / ".trae" / "mcp.json",
        ],
    },
    "windsurf": {
        "name": "Windsurf",
        "paths": [
            Path.home() / ".windsurf" / "mcp.json",
        ],
    },
    "vscode-copilot": {
        "name": "VS Code Copilot",
        "paths": [
            Path.home() / ".vscode" / "mcp.json",
        ],
    },
    "project-local": {
        "name": "项目本地",
        "paths": [
            Path.cwd() / ".mcp.json",
            Path.cwd() / "mcp.json",
        ],
    },
}


@dataclass
class AgentMCPConfig:
    """单个 Agent 的 MCP 配置快照。"""
    agent_id: str
    agent_name: str
    paths_found: list[str] = field(default_factory=list)
    server_names: list[str] = field(default_factory=list)
    server_details: dict[str, dict] = field(default_factory=dict)
    error: str | None = None


@dataclass
class DiscoverResult:
    """本地发现汇总结果。"""
    agents: list[AgentMCPConfig] = field(default_factory=list)
    all_server_names: set[str] = field(default_factory=set)
    total_agents_found: int = 0


@dataclass
class AgentCompareResult:
    """跨 Agent 比较结果。"""
    server_name: str
    present_in: list[str] = field(default_factory=list)    # 哪些 Agent 有此 Server
    absent_in: list[str] = field(default_factory=list)     # 哪些 Agent 缺少此 Server
    commands: dict[str, str] = field(default_factory=dict)  # agent_id -> command
    has_conflict: bool = False                               # 不同 Agent 的命令是否不一致


@dataclass
class Conflict:
    """配置冲突。"""
    server_name: str
    agent_a: str
    command_a: str
    agent_b: str
    command_b: str
    severity: str = "warning"  # warning / error


class LocalAgentDiscovery:
    """本地 AI Agent MCP 配置发现器。"""

    def __init__(self, agent_paths: dict | None = None) -> None:
        self._agent_paths = agent_paths or KNOWN_AGENT_PATHS

    async def discover_all(self) -> DiscoverResult:
        """扫描所有已知 Agent，返回完整的发现结果。

        对每个 Agent 检查其所有可能路径，读取 mcp.json 内容并提取：
        - 安装了哪些 MCP Server（名称和命令）
        - 配置文件是否可解析
        - 错误信息（文件损坏等）
        """
        result = DiscoverResult()
        all_servers: set[str] = set()

        for agent_id, agent_info in self._agent_paths.items():
            agent_result = await self._discover_agent(agent_id, agent_info)
            result.agents.append(agent_result)
            if agent_result.paths_found:
                result.total_agents_found += 1
                all_servers.update(agent_result.server_names)

        result.all_server_names = all_servers
        return result

    async def compare_agents(self) -> list[AgentCompareResult]:
        """跨 Agent 对比：每个 Server 在各 Agent 中的分布。

        输出可用于回答：
        - "Cursor 缺少哪些 Claude Code 已有的 Server？"
        - "哪些 Server 在所有 Agent 中都装了？"
        - "哪个 Server 在不同 Agent 中配置不一致？"
        """
        discover_result = await self.discover_all()
        # 筛选有配置的 Agent
        active_agents = [a for a in discover_result.agents if a.paths_found]

        # 收集所有 Server → {agent_id: command} 映射
        all_servers: dict[str, dict[str, str]] = {}
        for agent_cfg in active_agents:
            for srv_name, srv_detail in agent_cfg.server_details.items():
                if srv_name not in all_servers:
                    all_servers[srv_name] = {}
                cmd = srv_detail.get("command", "")
                all_servers[srv_name][agent_cfg.agent_id] = cmd

        # 构建比较结果
        agent_ids = [a.agent_id for a in active_agents]
        compare_results: list[AgentCompareResult] = []

        for srv_name, agent_cmds in sorted(all_servers.items()):
            present = list(agent_cmds.keys())
            absent = [aid for aid in agent_ids if aid not in agent_cmds]
            commands = {aid: agent_cmds.get(aid, "") for aid in agent_ids}

            # 检查冲突：同一 Server 在不同 Agent 中命令不同
            unique_cmds = set(c for c in agent_cmds.values() if c)
            has_conflict = len(unique_cmds) > 1

            compare_results.append(AgentCompareResult(
                server_name=srv_name,
                present_in=present,
                absent_in=absent,
                commands=commands,
                has_conflict=has_conflict,
            ))

        return compare_results

    async def detect_conflicts(self) -> list[Conflict]:
        """检测配置冲突 —— 同名 Server 在不同 Agent 中配置不同。"""
        compare_results = await self.compare_agents()
        conflicts: list[Conflict] = []

        for item in compare_results:
            if not item.has_conflict or len(item.present_in) < 2:
                continue
            # 找出命令不同的 Agent 对
            entries = [(aid, cmd) for aid, cmd in item.commands.items() if cmd]
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    aid_i, cmd_i = entries[i]
                    aid_j, cmd_j = entries[j]
                    if cmd_i != cmd_j:
                        conflicts.append(Conflict(
                            server_name=item.server_name,
                            agent_a=aid_i,
                            command_a=cmd_i,
                            agent_b=aid_j,
                            command_b=cmd_j,
                            severity="warning",
                        ))

        return conflicts

    async def get_agent_summary(self) -> dict:
        """获取 Agent 摘要 —— 供 Dashboard 使用。"""
        discover = await self.discover_all()
        return {
            "total_agents_known": len(self._agent_paths),
            "total_agents_found": discover.total_agents_found,
            "total_unique_servers": len(discover.all_server_names),
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "agent_name": a.agent_name,
                    "configured": bool(a.paths_found),
                    "server_count": len(a.server_names),
                    "servers": a.server_names,
                }
                for a in discover.agents
            ],
        }

    # ── 内部方法 ────────────────────────────────────────────

    async def _discover_agent(self, agent_id: str, agent_info: dict) -> AgentMCPConfig:
        """发现单个 Agent 的配置。"""
        result = AgentMCPConfig(
            agent_id=agent_id,
            agent_name=agent_info.get("name", agent_id),
        )

        for path in agent_info.get("paths", []):
            p = Path(path)
            if not p.exists():
                continue
            try:
                content = json.loads(p.read_text(encoding="utf-8"))
                mcp_servers = content.get("mcpServers", {})
                if mcp_servers:
                    result.paths_found.append(str(p))
                    for srv_name, srv_config in mcp_servers.items():
                        result.server_names.append(srv_name)
                        result.server_details[srv_name] = srv_config if isinstance(srv_config, dict) else {}
            except json.JSONDecodeError as e:
                logger.warning(
                    "local_discovery.invalid_json",
                    agent_id=agent_id,
                    path=str(p),
                    error=str(e),
                )
                if str(p) not in result.paths_found:
                    result.paths_found.append(str(p))
                result.error = f"配置文件 JSON 解析失败: {e}"
            except OSError as e:
                logger.warning(
                    "local_discovery.read_error",
                    agent_id=agent_id,
                    path=str(p),
                    error=str(e),
                )

        return result
