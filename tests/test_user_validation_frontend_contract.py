"""User-validation UI must retain explicit consent and non-leading answers."""

from __future__ import annotations

from pathlib import Path

WEB_SRC = Path(__file__).parents[1] / "src" / "mcp_hub" / "web" / "src"


def test_frontend_exposes_opt_in_progress_and_explicit_assessment_answers() -> None:
    telemetry_panel = (WEB_SRC / "components" / "TelemetryPanel.tsx").read_text(
        encoding="utf-8"
    )
    validation = (WEB_SRC / "pages" / "admin" / "AdminValidation.tsx").read_text(
        encoding="utf-8"
    )

    assert "/telemetry/user-validation" in telemetry_panel
    assert "/telemetry/user-validation/enrollment" in telemetry_panel
    assert "/telemetry/user-validation/assessment" in telemetry_panel
    assert "退出并删除验证数据" in telemetry_panel
    assert "请为每一项验证结果明确选择" in telemetry_panel
    assert "type=\"radio\"" in telemetry_panel
    assert "connection_state_understood: null as boolean | null" in telemetry_panel
    assert "/admin/analytics/user-validation" in validation
    assert "不展示用户身份或本地配置" in validation
