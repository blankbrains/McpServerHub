from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
MY_MCP_PAGE = ROOT / "src" / "mcp_hub" / "web" / "src" / "pages" / "MyServers.tsx"


def test_my_mcp_uses_unified_overview_and_required_status_filters() -> None:
    source = MY_MCP_PAGE.read_text(encoding="utf-8")

    assert "/my-mcp/overview?days=7" in source
    assert "apiGet<{ servers:" not in source
    assert "apiGet<UserServerConfig[]>" not in source
    for label in (
        "全部",
        "本地已发现",
        "已追踪",
        "已接入",
        "需要处理",
        "多设备冲突",
    ):
        assert label in source


def test_my_mcp_displays_independent_status_dimensions() -> None:
    source = MY_MCP_PAGE.read_text(encoding="utf-8")

    for field in (
        "market_status",
        "tracking_status",
        "gateway_status",
        "runtime_status",
        "call_status",
        "config_status",
        "security_status",
    ):
        assert field in source
    for label in (
        "市场已收录",
        "本地私有",
        "已接入 Gateway",
        "有真实调用",
        "配置一致",
        "安全已验证",
    ):
        assert label in source


def test_my_mcp_keeps_one_primary_action_and_private_tracking_boundary() -> None:
    source = MY_MCP_PAGE.read_text(encoding="utf-8")

    assert "server.primary_action.code === 'track'" in source
    assert "server.primary_action.target" in source
    assert "/my-mcp/track" in source
    assert "未收录的本地 Server 只在你的账户中可见" in source
    assert "加入追踪不会自动发布到市场" in source
    assert "<summary" in source
    assert "更多" in source
