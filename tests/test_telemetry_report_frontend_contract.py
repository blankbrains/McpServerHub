"""Monitor report export must stay discoverable and use the authenticated API."""

from __future__ import annotations

from pathlib import Path

WEB_SRC = Path(__file__).parents[1] / "src" / "mcp_hub" / "web" / "src"


def test_monitor_dashboard_exposes_authenticated_telemetry_report_export() -> None:
    dashboard = (WEB_SRC / "pages" / "MonitorDashboard.tsx").read_text(encoding="utf-8")
    client = (WEB_SRC / "api" / "client.ts").read_text(encoding="utf-8")

    assert "exportTelemetryReport" in dashboard
    assert "导出报告" in dashboard
    assert "mcp-hub-telemetry-report-7d.json" in dashboard
    assert "/export/telemetry-report?days=${days}" in client
    assert "headers: getAuthHeaders()" in client
