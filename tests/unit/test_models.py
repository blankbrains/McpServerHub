"""单元测试 — 数据模型。"""

from __future__ import annotations

from mcp_hub.models.review import Review
from mcp_hub.models.server import (
    InstallConfig,
    SearchParams,
    SearchResponse,
    SecurityInfo,
    ServerMeta,
)
from mcp_hub.models.user import User


class TestServerMeta:
    def test_basic_creation(self) -> None:
        meta = ServerMeta(name="@org/test", version="1.0.0")
        assert meta.name == "@org/test"
        assert meta.version == "1.0.0"
        assert meta.status == "not_installed"

    def test_display_name(self) -> None:
        meta = ServerMeta(name="@org/my-server", version="1.0.0")
        assert meta.display_name == "my-server"

    def test_is_official_anthropic(self) -> None:
        meta = ServerMeta(name="@anthropic/web-search", version="1.0.0", author="anthropic")
        assert meta.is_official is True

    def test_is_official_google(self) -> None:
        meta = ServerMeta(name="@google/gemini-tools", version="1.0.0", author="google")
        assert meta.is_official is True

    def test_is_official_openai(self) -> None:
        meta = ServerMeta(name="@openai/dalle-tools", version="1.0.0", author="openai")
        assert meta.is_official is True

    def test_is_official_community(self) -> None:
        meta = ServerMeta(name="@community/sql-query", version="1.0.0", author="community")
        assert meta.is_official is False

    def test_default_categories(self) -> None:
        meta = ServerMeta(name="@org/test", version="1.0.0")
        assert meta.categories == []

    def test_default_tags(self) -> None:
        meta = ServerMeta(name="@org/test", version="1.0.0")
        assert meta.tags == []

    def test_default_rating(self) -> None:
        meta = ServerMeta(name="@org/test", version="1.0.0")
        assert meta.rating == 0.0


class TestInstallConfig:
    def test_defaults(self) -> None:
        cfg = InstallConfig(type="pip", package="mcp-test", command="pip install mcp-test")
        assert cfg.type == "pip"
        assert cfg.package == "mcp-test"


class TestSecurityInfo:
    def test_defaults(self) -> None:
        si = SecurityInfo()
        assert si.level == "unreviewed"
        assert si.network_access is False
        assert si.file_access is False


class TestSearchParams:
    def test_defaults(self) -> None:
        sp = SearchParams()
        assert sp.q == ""
        assert sp.page == 1
        assert sp.page_size == 20
        assert sp.sort == "hot"


class TestSearchResponse:
    def test_creation(self) -> None:
        sr = SearchResponse(data=[], meta={"total": 0})
        assert sr.data == []
        assert sr.meta == {"total": 0}


class TestUser:
    def test_creation(self) -> None:
        u = User(id="testuser", role="user")
        assert u.id == "testuser"
        assert u.role == "user"

    def test_defaults(self) -> None:
        u = User(id="testuser")
        assert u.role == "user"


class TestReview:
    def test_creation(self) -> None:
        r = Review(server_id="@org/test", user_id="user1", rating=5)
        assert r.server_id == "@org/test"
        assert r.rating == 5

    def test_rating_range(self) -> None:
        """评分应该在 1-5 之间。"""
        r = Review(server_id="@org/test", user_id="user1", rating=5)
        assert 1 <= r.rating <= 5
