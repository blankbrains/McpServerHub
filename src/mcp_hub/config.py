"""MCP Server Hub 配置 — 所有敏感信息仅从 .env 或环境变量读取。"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


def _find_dotenv() -> Path | None:
    paths = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path.home() / ".config" / "mcp-hub" / ".env",
    ]
    for p in paths:
        if p.exists():
            return p
    return None


def _load_dotenv() -> None:
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
            if key not in os.environ:
                os.environ[key] = value


_load_dotenv()


def _require_env(key: str) -> str:
    """获取必需的环境变量，缺失则报错退出。"""
    value = os.getenv(key)
    if not value:
        sys.exit(1)
    return value


class Settings:
    """所有配置项集中管理 — 敏感字段无默认值，仅从 .env 读取。"""

    # === 数据库 ===
    DATABASE_URL: str = _require_env("MCP_HUB_DATABASE_URL")

    # === JWT 密钥 ===
    SECRET_KEY: str = _require_env("MCP_HUB_SECRET")

    # === GitHub OAuth（必须在 .env 中配置）===
    GITHUB_CLIENT_ID: str = _require_env("MCP_HUB_GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: str = _require_env("MCP_HUB_GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: str = os.getenv(
        "MCP_HUB_GITHUB_REDIRECT_URI", "http://localhost:3987/api/v1/auth/callback"
    )

    # === 服务配置（有合理默认值）===
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
