"""Telemetry report export must stay discoverable and use the authenticated API."""

from __future__ import annotations

from pathlib import Path

WEB_SRC = Path(__file__).parents[1] / "src" / "mcp_hub" / "web" / "src"


def test_reports_page_exposes_authenticated_telemetry_report_export() -> None:
    report_page = (WEB_SRC / "pages" / "ReportsPage.tsx").read_text(encoding="utf-8")
    client = (WEB_SRC / "api" / "client.ts").read_text(encoding="utf-8")

    assert "exportTelemetryReport" in report_page
    assert "导出报告" in report_page
    assert "mcp-hub-telemetry-report-7d.json" in report_page
    assert "/export/telemetry-report?days=${days}" in client
    assert "headers: getAuthHeaders()" in client
