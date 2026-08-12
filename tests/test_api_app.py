"""Tests for the deployable FastAPI application factory."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_hub import __version__
from mcp_hub.api.app import create_app
from mcp_hub.core.monitor import Monitor


def test_application_factory_builds_the_api():
    app = create_app()

    assert isinstance(app, FastAPI)
    assert "/api/v1/config/upload" in app.openapi()["paths"]
    assert "/api/v1/telemetry/events" in app.openapi()["paths"]
    assert "/api/v1/telemetry/contribution-consent" in app.openapi()["paths"]
    assert "/api/v1/telemetry/user-validation" in app.openapi()["paths"]
    assert "/api/v1/telemetry/user-validation/enrollment" in app.openapi()["paths"]
    assert "/api/v1/telemetry/user-validation/assessment" in app.openapi()["paths"]
    assert "/api/v1/telemetry/user-validation/stages" in app.openapi()["paths"]
    assert "/api/v1/admin/analytics/user-validation" in app.openapi()["paths"]
    assert "/api/v1/client-compatibility" in app.openapi()["paths"]
    assert (
        "/api/v1/publish/mine/{server_id}/compatibility-feedback"
        in app.openapi()["paths"]
    )


def test_static_top_reliability_route_is_not_shadowed(monkeypatch) -> None:
    monkeypatch.setattr(Monitor, "get_top_reliable", AsyncMock(return_value=[]))
    client = TestClient(create_app())

    response = client.get("/api/v1/health/reliability/top?limit=5")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": []}


def test_health_reports_distribution_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["version"] == __version__


def test_client_compatibility_is_public_and_returns_safe_policy() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/client-compatibility",
        params={"cli_version": "0.2.0", "gateway_version": "0.3.0"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["hub_version"] == __version__
    assert payload["data"]["cli"]["status"] == "upgrade_recommended"
    assert payload["data"]["gateway"]["status"] == "current"
    assert "token" not in str(payload).lower()
