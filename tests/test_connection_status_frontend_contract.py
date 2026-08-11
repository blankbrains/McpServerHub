from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB_SRC = ROOT / "src" / "mcp_hub" / "web" / "src"


def test_monitoring_page_includes_connection_status_panel() -> None:
    telemetry_panel = (WEB_SRC / "components" / "TelemetryPanel.tsx").read_text(
        encoding="utf-8"
    )
    connection_panel = (
        WEB_SRC / "components" / "ConnectionStatusPanel.tsx"
    ).read_text(encoding="utf-8")

    assert "ConnectionStatusPanel" in telemetry_panel
    assert "/telemetry/connection-status" in telemetry_panel
    assert "<ConnectionStatusPanel" in telemetry_panel
    assert "接入状态" in connection_panel
    assert "最近心跳" in connection_panel
    assert "已迁移 Server" in connection_panel
    assert "配置错误" in connection_panel
    assert "首次调用" in connection_panel
    assert "待上传队列" in connection_panel
    assert "mcp-hub agent verify --agent" in connection_panel
