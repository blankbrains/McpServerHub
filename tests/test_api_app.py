"""Tests for the deployable FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from mcp_hub.api.app import create_app


def test_application_factory_builds_the_api():
    app = create_app()

    assert isinstance(app, FastAPI)
    assert "/api/v1/config/upload" in app.openapi()["paths"]
    assert "/api/v1/telemetry/events" in app.openapi()["paths"]
