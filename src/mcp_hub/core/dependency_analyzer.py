"""MCP Server 依赖分析器。

分析 Server 的安装命令，自动推断：
- 运行时需求（Python/Node.js 版本）
- 环境变量需求（API Key 等）
- 系统依赖检查
- 建议和相关提示
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# 已知的 MCP Server 常见环境变量需求模式
KNOWN_ENV_PATTERNS: dict[str, dict] = {
    # API Keys
    "OPENAI_API_KEY": {
        "description": "OpenAI API 密钥",
        "required": True,
        "category": "api_key",
        "url": "https://platform.openai.com/api-keys",
    },
    "ANTHROPIC_API_KEY": {
        "description": "Anthropic API 密钥",
        "required": True,
        "category": "api_key",
        "url": "https://console.anthropic.com/",
    },
    "GITHUB_TOKEN": {
        "description": "GitHub Personal Access Token",
        "required": False,
        "category": "api_key",
        "url": "https://github.com/settings/tokens",
    },
    "GITHUB_PERSONAL_ACCESS_TOKEN": {
        "description": "GitHub Personal Access Token",
        "required": False,
        "category": "api_key",
    },
    "GITLAB_TOKEN": {
        "description": "GitLab Access Token",
        "required": False,
        "category": "api_key",
    },
    "GOOGLE_API_KEY": {
        "description": "Google API 密钥",
        "required": True,
        "category": "api_key",
        "url": "https://console.cloud.google.com/apis/credentials",
    },
    "BRAVE_API_KEY": {
        "description": "Brave Search API 密钥",
        "required": True,
        "category": "api_key",
        "url": "https://brave.com/search/api/",
    },
    "SERPAPI_API_KEY": {
        "description": "SerpAPI 密钥",
        "required": True,
        "category": "api_key",
    },
    "NEWSAPI_KEY": {
        "description": "NewsAPI 密钥",
        "required": False,
        "category": "api_key",
        "url": "https://newsapi.org/",
    },
    # Database
    "DATABASE_URL": {
        "description": "数据库连接字符串",
        "required": False,
        "category": "database",
    },
    "POSTGRES_URL": {
        "description": "PostgreSQL 连接字符串",
        "required": False,
        "category": "database",
    },
    "MONGODB_URI": {
        "description": "MongoDB 连接 URI",
        "required": False,
        "category": "database",
    },
    "REDIS_URL": {
        "description": "Redis 连接 URL",
        "required": False,
        "category": "database",
    },
    # Cloud
    "AWS_ACCESS_KEY_ID": {
        "description": "AWS Access Key ID",
        "required": False,
        "category": "cloud",
    },
    "AWS_SECRET_ACCESS_KEY": {
        "description": "AWS Secret Access Key",
        "required": False,
        "category": "cloud",
    },
    "AWS_REGION": {
        "description": "AWS 区域",
        "required": False,
        "category": "cloud",
    },
    "GCP_PROJECT_ID": {
        "description": "GCP 项目 ID",
        "required": False,
        "category": "cloud",
    },
    "AZURE_OPENAI_API_KEY": {
        "description": "Azure OpenAI API 密钥",
        "required": False,
        "category": "api_key",
    },
    # Communication
    "SLACK_BOT_TOKEN": {
        "description": "Slack Bot Token",
        "required": False,
        "category": "communication",
    },
    "DISCORD_BOT_TOKEN": {
        "description": "Discord Bot Token",
        "required": False,
        "category": "communication",
    },
    "TELEGRAM_BOT_TOKEN": {
        "description": "Telegram Bot Token",
        "required": False,
        "category": "communication",
    },
    "NOTION_API_KEY": {
        "description": "Notion API 密钥",
        "required": False,
        "category": "api_key",
    },
    "JIRA_API_TOKEN": {
        "description": "Jira API Token",
        "required": False,
        "category": "api_key",
    },
    "SENTRY_DSN": {
        "description": "Sentry DSN",
        "required": False,
        "category": "monitoring",
    },
}


@dataclass
class EnvVarRequirement:
    """单个环境变量需求。"""
    name: str
    description: str = ""
    required: bool = False
    category: str = ""
    is_set: bool = False
    help_url: str = ""


@dataclass
class RuntimeRequirement:
    """运行时依赖。"""
    name: str               # e.g. "python", "node", "go", "docker"
    min_version: str = ""
    installed: bool = False
    installed_version: str = ""
    message: str = ""


@dataclass
class DependencyReport:
    """完整的依赖分析报告。"""
    server_id: str
    command: str
    install_tool: str = ""           # pip / npx / uvx / go / docker
    runtime_requirements: list[RuntimeRequirement] = field(default_factory=list)
    env_var_requirements: list[EnvVarRequirement] = field(default_factory=list)
    system_tools: list[str] = field(default_factory=list)
    missing_count: int = 0
    warning_count: int = 0
    ready_to_install: bool = False
    suggestions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class DependencyAnalyzer:
    """分析 MCP Server 的完整依赖链。"""

    # 安装工具 → 运行时需求映射
    TOOL_RUNTIME_MAP = {
        "pip": {"name": "python", "min_version": "3.10"},
        "pip3": {"name": "python", "min_version": "3.10"},
        "python": {"name": "python", "min_version": "3.10"},
        "uvx": {"name": "python", "min_version": "3.10"},
        "npx": {"name": "node", "min_version": "18"},
        "npm": {"name": "node", "min_version": "18"},
        "node": {"name": "node", "min_version": "18"},
        "go": {"name": "go", "min_version": "1.21"},
        "docker": {"name": "docker", "min_version": "20"},
    }

    def __init__(self, server_id: str = "", command: str = "") -> None:
        self.server_id = server_id
        self.command = command

    async def analyze(self, server_id: str | None = None, command: str | None = None) -> DependencyReport:
        """运行完整分析。"""
        sid = server_id or self.server_id
        cmd = command or self.command

        report = DependencyReport(server_id=sid, command=cmd)

        if not cmd:
            report.notes.append("未提供安装命令，无法分析")
            return report

        parts = cmd.split()
        tool = parts[0] if parts else "unknown"
        report.install_tool = tool

        # 1. 分析运行时需求
        self._analyze_runtime(tool, report)

        # 2. 扫描环境变量需求
        self._scan_env_vars(report)

        # 3. 从命令参数中分析额外信息
        self._analyze_command(cmd, report)

        # 4. 汇总
        report.missing_count = sum(
            1 for r in report.runtime_requirements if not r.installed
        ) + sum(
            1 for e in report.env_var_requirements if e.required and not e.is_set
        )
        report.warning_count = sum(
            1 for e in report.env_var_requirements if not e.required and not e.is_set
        )
        report.ready_to_install = report.missing_count == 0

        # 5. 生成建议
        self._generate_suggestions(report)

        return report

    async def scan_command_env(self, command: str) -> list[str]:
        """扫描一条命令中引用的环境变量名。"""
        found = set()
        # 匹配 $VAR_NAME 或 ${VAR_NAME} 或 %VAR_NAME%
        for pattern in [r'\$([A-Z_][A-Z0-9_]*)', r'\$\{([A-Z_][A-Z0-9_]*)\}', r'%([A-Z_][A-Z0-9_]*)%']:
            for match in re.finditer(pattern, command):
                found.add(match.group(1))
        return sorted(found)

    # ── 内部分析 ──────────────────────────────────────────

    def _analyze_runtime(self, tool: str, report: DependencyReport) -> None:
        """分析运行时依赖（Python/Node.js/Go 版本检查）。"""
        runtime = self.TOOL_RUNTIME_MAP.get(tool)
        if not runtime:
            return

        name = runtime["name"]
        min_ver = runtime["min_version"]

        installed = False
        installed_ver = ""

        if name == "python":
            import sys
            installed_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
            installed = sys.version_info >= tuple(int(x) for x in min_ver.split("."))
        elif name == "node":
            import subprocess
            try:
                result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
                installed_ver = result.stdout.strip().lstrip("v")
                installed = bool(installed_ver)
            except Exception:
                installed = False
        elif name == "go":
            go_path = shutil.which("go")
            if go_path:
                import subprocess
                try:
                    result = subprocess.run(["go", "version"], capture_output=True, text=True, timeout=10)
                    m = re.search(r'go(\d+\.\d+)', result.stdout)
                    installed_ver = m.group(1) if m else ""
                    installed = bool(installed_ver)
                except Exception:
                    installed = False
        elif name == "docker":
            installed = shutil.which("docker") is not None

        report.runtime_requirements.append(RuntimeRequirement(
            name=name,
            min_version=min_ver,
            installed=installed,
            installed_version=installed_ver,
            message=f"{name} >= {min_ver}" if not installed else f"{name} {installed_ver} (>= {min_ver}) OK",
        ))

    def _scan_env_vars(self, report: DependencyReport) -> None:
        """扫描命令和环境，识别所需的环境变量。"""
        import sys

        # 首先从命令字符串中提取环境变量引用
        cmd_env_vars = set()
        for pattern in [r'\$([A-Z_][A-Z0-9_]*)', r'\$\{([A-Z_][A-Z0-9_]*)\}']:
            for match in re.finditer(pattern, report.command):
                cmd_env_vars.add(match.group(1))

        # 始终检查的常见环境变量（针对不同类型的 Server）
        categories_to_check = ["api_key", "database", "cloud", "communication", "monitoring"]

        # 按 Category 分组，从已知模式中匹配
        for var_name, var_info in KNOWN_ENV_PATTERNS.items():
            # 如果命令中明确引用了这个变量，或属于常见类别
            if var_name in cmd_env_vars or var_info.get("category") in categories_to_check:
                is_set = var_name in os.environ
                report.env_var_requirements.append(EnvVarRequirement(
                    name=var_name,
                    description=var_info.get("description", ""),
                    required=var_info.get("required", False),
                    category=var_info.get("category", ""),
                    is_set=is_set,
                    help_url=var_info.get("url", ""),
                ))

    def _analyze_command(self, command: str, report: DependencyReport) -> None:
        """从命令参数中分析系统工具依赖。"""
        # 检查是否需要 git
        if "github" in command.lower() or "git" in command.lower():
            report.system_tools.append("git")
            if not shutil.which("git"):
                report.notes.append("需要安装 git")

        # 检查是否使用了特定包
        if "playwright" in command.lower() or "browser" in command.lower():
            report.system_tools.append("playwright")
            report.notes.append("Playwright 可能需要安装浏览器: playwright install")

        if "docker" in command.lower():
            report.system_tools.append("docker")
            if not shutil.which("docker"):
                report.notes.append("需要安装 Docker")

        if "puppeteer" in command.lower():
            report.system_tools.append("chromium")
            report.notes.append("Puppeteer 需要 Chromium 浏览器")

        # 检查 API Key 需求（从命令参数推断）
        for part in command.split():
            part_lower = part.lower()
            if "api-key" in part_lower or "apikey" in part_lower:
                report.notes.append("此 Server 需要 API Key，请确保已配置相应的环境变量")

    def _generate_suggestions(self, report: DependencyReport) -> None:
        """生成优化建议。"""
        if report.missing_count > 0:
            report.suggestions.append("请先安装缺失的运行时环境")

        missing_required = [e for e in report.env_var_requirements if e.required and not e.is_set]
        if missing_required:
            names = ", ".join(e.name for e in missing_required)
            report.suggestions.append(f"需要设置以下环境变量: {names}")

        # 工具特定建议
        if report.install_tool == "uvx" and any(r.name == "python" and not r.installed for r in report.runtime_requirements):
            report.suggestions.append("安装 uvx: pip install uv")
        if report.install_tool == "npx" and any(r.name == "node" and not r.installed for r in report.runtime_requirements):
            report.suggestions.append("安装 Node.js: https://nodejs.org/")
