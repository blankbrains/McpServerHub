from __future__ import annotations

import re
from pathlib import Path

WEB_SRC = Path(__file__).parents[1] / "src" / "mcp_hub" / "web" / "src"


def test_literal_navigation_targets_are_registered_routes() -> None:
    app_source = (WEB_SRC / "App.tsx").read_text(encoding="utf-8")
    registered_routes = set(re.findall(r'<Route\s+path="([^"]+)"', app_source))

    navigation_targets: set[str] = set()
    for source_path in WEB_SRC.rglob("*.tsx"):
        source = source_path.read_text(encoding="utf-8")
        navigation_targets.update(
            re.findall(r"""navigate\(\s*['"](/[^'"]*)['"]\s*\)""", source)
        )

    missing = sorted(target for target in navigation_targets if target not in registered_routes)
    assert missing == [], f"Literal navigation targets without a registered route: {missing}"


def test_primary_navigation_is_limited_to_core_product_workflows() -> None:
    layout = (WEB_SRC / "components" / "Layout.tsx").read_text(encoding="utf-8")
    nav_block = re.search(r"const navItems = \[(.*?)\] as const", layout, re.DOTALL)

    assert nav_block is not None
    nav_source = nav_block.group(1)
    for label in ("概览", "发现 MCP", "我的 MCP", "监控", "发布"):
        assert f"label: '{label}'" in nav_source
    for redundant_label in ("指南", "配置", "对比", "方案", "构建", "发现", "个人中心"):
        assert f"label: '{redundant_label}'" not in nav_source


def test_my_mcp_workspace_keeps_configuration_and_inventory_reachable() -> None:
    workspace = (WEB_SRC / "components" / "McpWorkspaceNav.tsx").read_text(
        encoding="utf-8"
    )
    market = (WEB_SRC / "pages" / "Market.tsx").read_text(encoding="utf-8")
    publish = (WEB_SRC / "pages" / "Publish.tsx").read_text(encoding="utf-8")

    assert "已追踪" in workspace
    assert "配置与同步" in workspace
    assert "本地清单" in workspace
    assert "to=\"/compare\"" in market
    assert "to=\"/builder\"" in publish
