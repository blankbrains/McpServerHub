"""API publish 路由模块测试 — 不依赖 LifespanManager。"""
from __future__ import annotations

from mcp_hub.api.routes_publish import router, PublishRequest


def test_router_registered():
    """publish 路由模块应存在且包含端点。"""
    routes = [r.path for r in router.routes]
    assert "/publish" in routes


def test_publish_request_model():
    """PublishRequest 模型应能正确解析。"""
    req = PublishRequest(name="test-server", description="测试")
    assert req.name == "test-server"
    assert req.description == "测试"
    assert req.install_type == "npx"  # default


def test_publish_request_with_all_fields():
    """PublishRequest 应接受所有可选字段。"""
    req = PublishRequest(
        name="full-server",
        description="完整",
        category="database",
        install_type="pip",
        install_command="pip install foo",
        homepage="https://example.com",
        tags=["db", "sql"],
    )
    assert req.category == "database"
    assert req.install_type == "pip"
    assert len(req.tags) == 2
