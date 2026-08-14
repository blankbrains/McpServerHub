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
    assert 'aria-current={active ? \'page\' : undefined}' in layout
    assert "window.matchMedia('(min-width: 768px)')" in layout
    assert "setMobileOpen(false)" in layout
    assert "inert={!isDesktop && !mobileOpen ? true : undefined}" in layout
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
    assert "requestVersion" in users
    assert 'aria-label="搜索用户"' in users
    assert "dark:text-purple-300" in users

    assert "apiDownload('/admin/export/servers'" in servers
    assert "apiGet<AdminCategory[]>('/admin/categories')" in servers
    assert "window.setTimeout" in servers
    assert "useNavigate" in servers
    assert "onKeyDown" in servers
    assert "requestVersion" in servers
    assert 'aria-label="搜索 Server"' in servers


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


def test_admin_server_detail_metrics_are_responsive() -> None:
    server_detail = (
        WEB_SRC / "pages" / "admin" / "AdminServerDetail.tsx"
    ).read_text(encoding="utf-8")

    assert "grid grid-cols-2 gap-3 sm:grid-cols-4" in server_detail
    assert "const restoring = !server.market_visible" in server_detail
    assert "value={securitySelection}" in server_detail
    assert "setSecuritySelection('')" in server_detail
    assert "min-w-0 flex-1 break-all" in server_detail
    assert 'role={notice.type === \'success\' ? \'status\' : \'alert\'}' in server_detail


def test_admin_rankings_and_details_contain_long_content() -> None:
    overview = (
        WEB_SRC / "pages" / "admin" / "AdminOverview.tsx"
    ).read_text(encoding="utf-8")
    analytics = (
        WEB_SRC / "pages" / "admin" / "AdminAnalytics.tsx"
    ).read_text(encoding="utf-8")
    user_detail = (
        WEB_SRC / "pages" / "admin" / "AdminUserDetail.tsx"
    ).read_text(encoding="utf-8")

    assert "grid min-w-0 gap-4 md:grid-cols-2" in overview
    assert "min-w-0 flex-1 truncate" in overview
    assert "grid min-w-0 gap-4 md:grid-cols-2" in analytics
    assert "min-w-0 flex-1 truncate" in analytics
    assert "min-w-0 flex-1 break-all" in user_detail
    assert "dark:bg-purple-900/40 dark:text-purple-300" in user_detail
    assert "最近 30 天暂无工具调用" in user_detail
    assert "该用户尚未追踪 Server" in user_detail


def test_admin_moderation_supports_complete_safe_review_workflow() -> None:
    reviews = (
        WEB_SRC / "pages" / "admin" / "AdminReviews.tsx"
    ).read_text(encoding="utf-8")

    assert "expandedReviewId" in reviews
    assert "展开全文" in reviews
    assert "aria-expanded" in reviews
    assert "deletingId" in reviews
    assert "deletingReview.current" in reviews
    assert "nextPage !== page" in reviews
    assert "disabled={deletingId !== null}" in reviews
    assert "requestVersion" in reviews
    assert 'className="space-y-3 md:hidden"' in reviews
    assert "md:block" in reviews
    assert "ReviewContent" in reviews


def test_admin_segmented_controls_expose_selected_state() -> None:
    analytics = (
        WEB_SRC / "pages" / "admin" / "AdminAnalytics.tsx"
    ).read_text(encoding="utf-8")
    validation = (
        WEB_SRC / "pages" / "admin" / "AdminValidation.tsx"
    ).read_text(encoding="utf-8")

    assert "aria-pressed={days === value}" in analytics
    assert "aria-pressed={metric === value}" in analytics
    assert "aria-pressed={days === value}" in validation
