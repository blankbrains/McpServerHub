"""Administrator frontend navigation and workflow contract tests."""

from __future__ import annotations

from pathlib import Path

WEB_SRC = Path(__file__).parents[1] / "src" / "mcp_hub" / "web" / "src"


def test_admin_navigation_exposes_split_operational_workspaces() -> None:
    app = (WEB_SRC / "App.tsx").read_text(encoding="utf-8")
    layout = (WEB_SRC / "pages" / "admin" / "AdminLayout.tsx").read_text(
        encoding="utf-8"
    )

    assert 'path="validation"' in app
    assert "平台概览" in layout
    assert "用户与设备" in layout
    assert "Server 与市场" in layout
    assert "平台分析" in layout
    assert "接入验证" in layout
    assert "内容审核" in layout
    assert "操作审计" in layout
    assert 'aria-label="打开管理员导航"' in layout
    assert "mobileOpen" in layout


def test_admin_lists_support_search_navigation_and_exports() -> None:
    users = (WEB_SRC / "pages" / "admin" / "AdminUsers.tsx").read_text(
        encoding="utf-8"
    )
    servers = (WEB_SRC / "pages" / "admin" / "AdminServers.tsx").read_text(
        encoding="utf-8"
    )

    assert "apiDownload('/admin/export/users'" in users
    assert "window.setTimeout" in users
    assert "useNavigate" in users
    assert "onKeyDown" in users

    assert "apiDownload('/admin/export/servers'" in servers
    assert "apiGet<AdminCategory[]>('/admin/categories')" in servers
    assert "window.setTimeout" in servers
    assert "useNavigate" in servers
    assert "onKeyDown" in servers


def test_admin_audit_and_role_controls_keep_safety_boundaries_visible() -> None:
    audit = (WEB_SRC / "pages" / "admin" / "AdminAuditLog.tsx").read_text(
        encoding="utf-8"
    )
    user_detail = (
        WEB_SRC / "pages" / "admin" / "AdminUserDetail.tsx"
    ).read_text(encoding="utf-8")

    assert "totalPages" in audit
    assert "上一页" in audit
    assert "下一页" in audit
    assert "当前登录账号不可自我降级" in user_detail
