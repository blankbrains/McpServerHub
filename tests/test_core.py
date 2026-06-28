"""核心模块单元测试。"""

from __future__ import annotations

from mcp_hub.models.server import ServerMeta, InstallConfig, SecurityInfo


def test_server_meta_creation():
    """ServerMeta 应正确创建。"""
    meta = ServerMeta(
        name="@modelcontextprotocol/server-filesystem",
        version="1.0.0",
        description="File system access",
        author="modelcontextprotocol",
        install=InstallConfig(type="npx", package="server-filesystem", command="npx -y @modelcontextprotocol/server-filesystem /tmp"),
    )
    assert meta.name == "@modelcontextprotocol/server-filesystem"
    assert meta.display_name == "server-filesystem"
    assert meta.is_official is False
    assert meta.status == "not_installed"


def test_server_meta_official():
    """官方 Server 应正确标记。"""
    meta = ServerMeta(name="@anthropic/web-search", version="1.0.0", author="anthropic")
    assert meta.is_official is True


def test_security_info_default():
    """安全信息应有合理默认值。"""
    sec = SecurityInfo()
    assert sec.level == "unreviewed"
    assert sec.network_access is False
    assert sec.file_access is False


def test_server_meta_categories():
    """分类和标签应正确设置。"""
    meta = ServerMeta(
        name="@modelcontextprotocol/server-github",
        version="2.0.0",
        categories=["developer-tools", "git"],
        tags=["github", "official"],
    )
    assert "developer-tools" in meta.categories
    assert "github" in meta.tags
