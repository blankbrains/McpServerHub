# MCP Server Hub 配置（从环境变量或 .env 文件读取）

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache


def _find_dotenv() -> Path | None:
    """从当前目录或上级目录查找 .env 文件。"""
    paths = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent / ".env",  # 项目根目录
        Path.home() / ".config" / "mcp-hub" / ".env",
    ]
    for p in paths:
        if p.exists():
            return p
    return None


def _load_dotenv() -> None:
    """简易 .env 文件加载（不依赖 python-dotenv 库）。"""
    env_file = _find_dotenv()
    if not env_file:
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key not in os.environ:  # 环境变量优先
                os.environ[key] = value


# 启动时自动加载 .env
_load_dotenv()


class Settings:
    """所有配置项集中管理。"""

    # 数据库
    DATABASE_URL: str = os.getenv(
        "MCP_HUB_DATABASE_URL",
        "postgresql+asyncpg://mcp_hub:mcp_hub_prod_2026@localhost:5432/mcp_hub",
    )

    # JWT
    SECRET_KEY: str = os.getenv("MCP_HUB_SECRET", "mcp-hub-prod-secret-key")

    # GitHub OAuth
    GITHUB_CLIENT_ID: str = os.getenv(
        "MCP_HUB_GITHUB_CLIENT_ID", "Ov23li9rAd3GLySJaUpC"
    )
    GITHUB_CLIENT_SECRET: str = os.getenv(
        "MCP_HUB_GITHUB_CLIENT_SECRET", "f34b991fede4298557345b7ace37c434c0313b33"
    )
    GITHUB_REDIRECT_URI: str = os.getenv(
        "MCP_HUB_GITHUB_REDIRECT_URI",
        "http://172.19.138.78:3987/api/v1/auth/callback",
    )

    # 服务
    HOST: str = os.getenv("MCP_HUB_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("MCP_HUB_PORT", "3987"))
    CORS_ORIGINS: str = os.getenv("MCP_HUB_CORS_ORIGINS", "http://localhost:3987")
    LOG_DIR: str = os.getenv("MCP_HUB_LOG_DIR", "~/.config/mcp-hub/logs")
    WORKERS: int = int(os.getenv("MCP_HUB_WORKERS", "2"))

    @property
    def cors_origins_list(self) -> list[str]:
        origins = self.CORS_ORIGINS
        if origins == "*":
            return ["*"]
        return [o.strip() for o in origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置（带缓存）。"""
    return Settings()
