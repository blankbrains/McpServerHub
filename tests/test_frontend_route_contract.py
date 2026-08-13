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


def test_primary_navigation_separates_core_product_workflows() -> None:
    layout = (WEB_SRC / "components" / "Layout.tsx").read_text(encoding="utf-8")
    nav_block = re.search(r"const navItems = \[(.*?)\] as const", layout, re.DOTALL)

    assert nav_block is not None
    nav_source = nav_block.group(1)
    for label in (
        "概览",
        "发现 MCP",
        "我的 MCP",
        "配置",
        "设备",
        "监控",
        "告警",
        "报告",
        "发布",
    ):
        assert f"label: '{label}'" in nav_source
    for redundant_label in ("指南", "对比", "方案", "构建", "个人中心"):
        assert f"label: '{redundant_label}'" not in nav_source


def test_workspace_navigation_keeps_related_pages_reachable_without_overloading_my_mcp() -> None:
    workspace = (WEB_SRC / "components" / "McpWorkspaceNav.tsx").read_text(
        encoding="utf-8"
    )
    telemetry_workspace = (
        WEB_SRC / "components" / "TelemetryWorkspaceNav.tsx"
    ).read_text(encoding="utf-8")
    market = (WEB_SRC / "pages" / "Market.tsx").read_text(encoding="utf-8")
    publish = (WEB_SRC / "pages" / "Publish.tsx").read_text(encoding="utf-8")

    assert "状态总览" in workspace
    assert "配置与同步" not in workspace
    assert "本地清单" not in workspace
    for label in ("设备与接入", "本地清单", "运行监控", "调用分析", "用户验证"):
        assert label in telemetry_workspace
    assert "const deviceItems" in telemetry_workspace
    assert "const monitorItems" in telemetry_workspace
    assert "items === deviceItems ? '设备功能' : '监控功能'" in telemetry_workspace
    assert "label: '告警'" not in telemetry_workspace
    assert "label: '报告'" not in telemetry_workspace
    assert "to=\"/compare\"" in market
    assert "to=\"/builder\"" in publish


def test_split_workflow_routes_keep_legacy_urls_available() -> None:
    app_source = (WEB_SRC / "App.tsx").read_text(encoding="utf-8")

    for route in (
        "/devices",
        "/inventory",
        "/analytics",
        "/alerts",
        "/reports",
        "/validation",
        "/config",
        "/local",
        "/notifications",
    ):
        assert f'path="{route}"' in app_source


def test_desktop_sidebar_keeps_auxiliary_actions_at_viewport_bottom() -> None:
    layout = (WEB_SRC / "components" / "Layout.tsx").read_text(encoding="utf-8")
    aside = re.search(r"<aside className=\{`(.*?)`\}>", layout, re.DOTALL)

    assert aside is not None
    aside_classes = aside.group(1)
    for required_class in (
        "overflow-hidden",
        "md:sticky",
        "md:top-0",
        "md:h-screen",
        "md:self-start",
    ):
        assert required_class in aside_classes

    assert 'className="min-h-0 flex-1 overflow-y-auto py-1"' in layout
    assert 'className="flex-shrink-0 border-t border-gray-100 py-1' in layout


def test_notification_actions_publish_unread_count_to_sidebar() -> None:
    layout = (WEB_SRC / "components" / "Layout.tsx").read_text(encoding="utf-8")
    notifications = (WEB_SRC / "pages" / "NotificationsPage.tsx").read_text(
        encoding="utf-8"
    )
    utility = (WEB_SRC / "utils" / "notifications.ts").read_text(encoding="utf-8")

    assert "NOTIFICATION_COUNT_EVENT" in utility
    assert "window.dispatchEvent" in utility
    assert "window.addEventListener(NOTIFICATION_COUNT_EVENT" in layout
    assert '<Link to="/alerts"' in layout
    assert "通知{unreadNotif > 0 ? ` (${unreadNotif})` : ''}" in layout
    assert "publishNotificationCount(response.data.unread_count)" in notifications
    assert "publishNotificationCount(0)" in notifications
