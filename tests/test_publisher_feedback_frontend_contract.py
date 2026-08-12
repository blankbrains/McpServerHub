"""Publisher feedback UI must preserve consent and k-anonymous boundaries."""

from __future__ import annotations

from pathlib import Path

WEB_SRC = Path(__file__).parents[1] / "src" / "mcp_hub" / "web" / "src"


def test_frontend_exposes_revocable_consent_and_k_anonymous_feedback() -> None:
    telemetry_panel = (WEB_SRC / "components" / "TelemetryPanel.tsx").read_text(
        encoding="utf-8"
    )
    publish = (WEB_SRC / "pages" / "Publish.tsx").read_text(encoding="utf-8")

    assert "/telemetry/contribution-consent" in telemetry_panel
    assert "匿名贡献兼容性数据" in telemetry_panel
    assert "/compatibility-feedback" in publish
    assert "匿名兼容性反馈" in publish
    assert "minimum_contributors" in publish
    assert "success_rate_band" in publish
    assert "avg_duration_ms" not in publish
