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


def test_device_management_distinguishes_recovery_from_token_revocation() -> None:
    telemetry_panel = (WEB_SRC / "components" / "TelemetryPanel.tsx").read_text(
        encoding="utf-8"
    )

    assert "mcp-hub agent ${action} --agent ${agentType}" in telemetry_panel
    assert "'backups' | 'disconnect'" in telemetry_panel
    assert "查看最近备份" in telemetry_panel
    assert "恢复 Agent 配置" in telemetry_panel
    assert "撤销令牌不会恢复本地直连配置" in telemetry_panel
    assert "网页只能撤销 Hub 设备令牌，不能读取或修改你电脑上的 Agent 配置" in telemetry_panel
