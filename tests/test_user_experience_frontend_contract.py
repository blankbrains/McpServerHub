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
