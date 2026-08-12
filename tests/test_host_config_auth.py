"""Server-host configuration operations must not be public SaaS APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mcp_hub.api.app import create_app


def test_host_filesystem_config_routes_require_authentication() -> None:
    client = TestClient(create_app())
    requests = [
        ("GET", "/api/v1/config/from-local", None),
        ("GET", "/api/v1/local/discover", None),
        ("GET", "/api/v1/local/compare", None),
        ("GET", "/api/v1/local/conflicts", None),
        ("GET", "/api/v1/my-mcp/overview", None),
        ("POST", "/api/v1/my-mcp/track", {"server_id": "private-local"}),
        ("GET", "/api/v1/config/diff", None),
        ("POST", "/api/v1/config/backup", {}),
        ("GET", "/api/v1/config/backups", None),
        ("POST", "/api/v1/config/restore/example.json", None),
        ("POST", "/api/v1/servers/pre-check", {"command": "uvx example"}),
        (
            "POST",
            "/api/v1/servers/dependency-analyze",
            {"server_id": "@example/server", "command": "uvx example"},
        ),
        ("POST", "/api/v1/config/generate", None),
    ]

    for method, path, body in requests:
        response = client.request(method, path, json=body)
        assert response.status_code == 401, (method, path, response.text)
