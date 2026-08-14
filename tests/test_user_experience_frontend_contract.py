from __future__ import annotations

from pathlib import Path

WEB_SRC = Path(__file__).parents[1] / "src" / "mcp_hub" / "web" / "src"


def _source(relative_path: str) -> str:
    return (WEB_SRC / relative_path).read_text(encoding="utf-8")


def test_auth_state_is_reactive_and_unauthorized_requests_clear_only_the_used_token() -> None:
    client = _source("api/client.ts")
    hook = _source("hooks/useAuthState.ts")
    layout = _source("components/Layout.tsx")

    assert "AUTH_STATE_EVENT" in client
    assert "window.dispatchEvent(new Event(AUTH_STATE_EVENT))" in client
    assert "window.addEventListener(AUTH_STATE_EVENT" in client
    assert "window.addEventListener('storage'" in client
    assert "response.status === 401" in client
    assert "localStorage.getItem(AUTH_TOKEN_KEY) === tokenUsed" in client
    assert "clearAuth()" in client
    assert "useSyncExternalStore" in hook
    assert "subscribeAuthState" in hook
    assert "const auth = useAuthState()" in layout
    assert "const handleLogout = () => clearAuth()" in layout


def test_protected_telemetry_pages_do_not_request_account_data_before_login() -> None:
    telemetry = _source("components/TelemetryPanel.tsx")
    monitor = _source("pages/MonitorDashboard.tsx")

    telemetry_guard = telemetry.index("if (!auth.token)")
    first_telemetry_request = telemetry.index(
        "apiGet<ConnectionStatusData>('/telemetry/connection-status')"
    )
    assert telemetry_guard < first_telemetry_request
    assert "return <AuthRequired" in telemetry

    monitor_guard = monitor.index("if (!auth.token)")
    first_monitor_request = monitor.index(
        "apiGet<DashboardData>('/monitor/dashboard')"
    )
    assert monitor_guard < first_monitor_request
    assert "<AuthRequired" in monitor


def test_personal_pages_share_the_reactive_auth_state() -> None:
    protected_pages = (
        "pages/MyServers.tsx",
        "pages/MyConfig.tsx",
        "pages/LocalDiscovery.tsx",
        "pages/MonitorDashboard.tsx",
        "pages/NotificationsPage.tsx",
        "pages/ProfilePage.tsx",
        "pages/Publish.tsx",
        "pages/ReportsPage.tsx",
    )

    for page in protected_pages:
        source = _source(page)
        assert "useAuthState" in source, page
        assert "AuthRequired" in source, page


def test_unknown_routes_render_a_recovery_page() -> None:
    app = _source("App.tsx")
    not_found = _source("pages/NotFound.tsx")

    assert "import NotFound from './pages/NotFound'" in app
    assert '<Route path="*" element={<NotFound />} />' in app
    assert "页面不存在" in not_found
    assert 'to="/"' in not_found
    assert 'to="/market"' in not_found


def test_mobile_command_and_agent_controls_are_contained() -> None:
    server_detail = _source("pages/ServerDetail.tsx")
    guide = _source("pages/Guide.tsx")

    assert '<div className="flex flex-wrap items-center gap-2 mb-4">' in server_detail
    assert (
        'className="min-w-0 max-w-full overflow-x-auto bg-gray-900 rounded-lg p-4"'
        in guide
    )
    assert 'className="min-w-max text-green-400 text-sm font-mono whitespace-pre"' in guide


def test_protected_fetches_use_the_shared_api_client() -> None:
    config = _source("pages/ConfigPage.tsx")
    logs = _source("components/LogViewer.tsx")
    builder = _source("pages/Builder.tsx")

    assert "apiDelete(`/config/user-servers/" in config
    assert "apiFetch(`/config/download?" in config
    assert "fetch(" not in config
    assert "apiFetch(`/servers/" in logs
    assert "fetch(" not in logs
    assert "apiFetch('/builder/tools')" in builder
    assert "apiFetch(`/builder/generate?" in builder
    assert "readApiErrorMessage" in builder
    assert "await res.text()" not in builder
    assert "fetch(" not in builder


def test_anonymous_market_and_server_actions_offer_login_instead_of_401_errors() -> None:
    market = _source("pages/Market.tsx")
    detail = _source("pages/ServerDetail.tsx")

    assert "navigate('/login')" in market
    assert "登录后加入追踪" in detail
    assert "登录后收藏" in detail
    assert "登录后回复" in detail
    assert "runtime_config_available === false" in detail
    assert "Auto-fetch config for first agent" not in detail


def test_reliability_empty_state_is_not_rendered_as_a_failure_score() -> None:
    server_detail = _source("pages/ServerDetail.tsx")

    assert "reliability.total_checks === 0" in server_detail
    assert "reliability.total_checks > 0 ? reliability.reliability_score : '-'" in server_detail
    assert "uptime && uptime.total_checks > 0" in server_detail
    assert "`${uptime.uptime_pct.toFixed(1)}%`" in server_detail


def test_login_cancel_and_sidebar_responsive_states_are_recoverable() -> None:
    login = _source("pages/Login.tsx")
    layout = _source("components/Layout.tsx")

    assert "const popupRef = useRef<Window | null>(null)" in login
    assert "if (popupRef.current?.closed)" in login
    assert "GitHub 授权窗口已关闭，登录未完成" in login
    assert 'role="alert"' in login

    assert "window.matchMedia('(min-width: 768px)')" in layout
    assert "if (event.matches) setSidebarOpen(false)" in layout
    assert "handleCollapsedSearch" in layout
    assert 'aria-label="展开侧栏并搜索 Server"' in layout
    assert 'aria-label="搜索 Server"' in layout
    assert 'aria-expanded={sidebarOpen}' in layout
    assert 'aria-controls="primary-sidebar"' in layout


def test_market_pagination_scrolls_to_server_results_only_after_page_changes() -> None:
    market = _source("pages/Market.tsx")

    assert "const resultsRef = useRef<HTMLParagraphElement>(null)" in market
    assert "const shouldScrollToResults = useRef(false)" in market
    assert "resultsRef.current?.scrollIntoView" in market
    assert "shouldScrollToResults.current = true" in market
    assert "onClick={() => changePage(page + 1)}" in market
    assert ".filter(s => {" not in market
    assert "登录后筛选追踪状态" in market


def test_server_security_badge_uses_one_icon_and_one_text_label() -> None:
    card = _source("components/ServerCard.tsx")

    assert "verified: '安全认证'" in card
    assert "reviewed: '已审查'" in card
    assert "unreviewed: '未审查'" in card
    assert "blocked: '已阻止'" in card
    assert "verified: '🔒 安全认证'" not in card


def test_legacy_public_pages_receive_dark_theme_without_overriding_explicit_variants() -> None:
    styles = _source("index.css")
    guide = _source("pages/Guide.tsx")

    assert '.text-gray-900:not([class*="dark:text-"])' in styles
    assert '.bg-white:not([class*="dark:bg-"])' in styles
    assert '.border-gray-200:not([class*="dark:border-"])' in styles
    assert '.text-blue-700:not([class*="dark:text-"])' in styles
    assert '.bg-red-50:not([class*="dark:bg-"])' in styles
    assert '.text-gray-400:not([class*="dark:text-"])' in styles
    assert '.bg-green-600:not([class*="dark:bg-"])' in styles
    assert ".dark {" in styles
    assert "color-scheme: dark" in styles
    assert "dark:from-amber-950/40" in guide
    assert "text-gray-400 dark:text-gray-400" in _source("components/Layout.tsx")
    assert _source("pages/ConfigPage.tsx").count("dark:text-gray-300") >= 4


def test_builder_errors_are_readable_and_form_controls_are_labeled() -> None:
    builder = _source("pages/Builder.tsx")
    client = _source("api/client.ts")

    assert "export async function readApiErrorMessage" in client
    assert "payload?.error?.message" in client
    assert "new ApiRequestError(" in builder
    assert 'role="alert"' in builder
    assert 'role="status"' in builder
    assert 'htmlFor="builder-name"' in builder
    assert 'id="builder-name"' in builder
    assert 'aria-pressed={language === \'python\'}' in builder
    assert 'aria-pressed={selectedTools.has(tool.name)}' in builder
