"""MCP Server 数据模型。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SecurityLevel = Literal["verified", "reviewed", "unreviewed", "blocked"]
ServerStatus = Literal["not_installed", "running", "stopped", "error"]
InstallType = Literal["pip", "npm", "uvx", "docker", "npx"]


class InstallConfig(BaseModel):
    type: InstallType
    package: str
    command: str
    auto_config: bool = True


class SecurityInfo(BaseModel):
    level: SecurityLevel = "unreviewed"
    last_audit: str | None = None
    network_access: bool = False
    file_access: bool = False


class ServerMeta(BaseModel):
    """Server 元数据 —— 核心数据结构。"""
    name: str  # @org/server-name
    version: str
    description: str = ""
    author: str = ""
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    install: InstallConfig | None = None
    dependencies: dict[str, str] = Field(default_factory=dict)
    security: SecurityInfo = Field(default_factory=SecurityInfo)
    rating: float = 0.0
    review_count: int = 0
    download_count: int = 0
    homepage: str = ""
    license: str = "MIT"
    status: ServerStatus = "not_installed"
    created_at: str = ""
    updated_at: str = ""

    @property
    def display_name(self) -> str:
        return self.name.split("/")[-1] if "/" in self.name else self.name

    @property
    def is_official(self) -> bool:
        return self.author in {"anthropic", "openai", "google"}


class ServerCreate(BaseModel):
    """创建 Server 请求。"""
    name: str = Field(..., pattern=r"^@[\w-]+/[\w.-]+$")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    description: str = ""
    author: str = ""
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    install: InstallConfig | None = None
    homepage: str = ""
    license: str = "MIT"


class ServerResponse(BaseModel):
    """Server 响应。"""
    id: str
    name: str
    display_name: str
    version: str
    description: str
    author: str
    categories: list[str]
    tags: list[str]
    install: InstallConfig | None = None
    security: SecurityInfo
    rating: float
    review_count: int
    download_count: int
    favorite_count: int = 0
    status: ServerStatus
    homepage: str
    license: str
    created_at: str
    updated_at: str


class SearchParams(BaseModel):
    q: str = ""
    category: str | None = None
    tag: str | None = None
    sort: str = "hot"  # hot / rating / downloads / new
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SearchResponse(BaseModel):
    success: bool = True
    data: list[dict]
    meta: dict
