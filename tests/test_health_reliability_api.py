from __future__ import annotations

from mcp_hub.api import routes_health
from mcp_hub.core.monitor import ReliabilityReport, UptimeStats


async def test_reliability_payload_includes_window_check_counts(monkeypatch) -> None:
    async def get_server(_self, server_id: str):
        return {"id": server_id}

    async def calculate_reliability(_server_id: str) -> ReliabilityReport:
        return ReliabilityReport(
            server_id="@test/reliability-payload",
            reliability_score=98,
            total_checks_recorded=12,
            uptime_stats=[
                UptimeStats(
                    window="24h",
                    total_checks=12,
                    passed_checks=11,
                    uptime_pct=91.7,
                    avg_response_time_ms=42.0,
                )
            ],
        )

    monkeypatch.setattr(routes_health.Registry, "get_by_id", get_server)
    monkeypatch.setattr(
        routes_health.Monitor,
        "calculate_reliability",
        calculate_reliability,
    )

    result = await routes_health.get_reliability("@test/reliability-payload")

    assert result["data"]["total_checks"] == 12
    assert result["data"]["uptime_stats"] == [
        {
            "window": "24h",
            "total_checks": 12,
            "passed_checks": 11,
            "uptime_pct": 91.7,
            "avg_response_time_ms": 42.0,
        }
    ]
