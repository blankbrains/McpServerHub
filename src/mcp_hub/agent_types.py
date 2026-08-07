"""Supported MCP client identities used for telemetry device isolation."""

from __future__ import annotations

DEFAULT_AGENT_TYPE = "generic"

AGENT_TYPE_LABELS: dict[str, str] = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "cursor": "Cursor",
    "windsurf": "Windsurf",
    "vscode-copilot": "VS Code Copilot",
    "trae": "Trae",
    DEFAULT_AGENT_TYPE: "通用 MCP 客户端",
}

AGENT_TYPES = tuple(AGENT_TYPE_LABELS)


def normalize_agent_type(value: str | None) -> str:
    """Validate and normalize an Agent type received from a trusted user action."""
    normalized = (value or DEFAULT_AGENT_TYPE).strip().lower()
    if normalized not in AGENT_TYPE_LABELS:
        raise ValueError("不支持的 Agent 类型")
    return normalized
