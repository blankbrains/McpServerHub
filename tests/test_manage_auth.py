import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from mcp_hub.api.dependencies import get_admin_user, get_current_user
from mcp_hub.api.routes_manage import router


def test_stop_server_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.post("/api/v1/servers/anonymous-stop-test/stop")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/servers/",
        "/api/v1/servers/example/status",
        "/api/v1/servers/config/download",
        "/api/v1/servers/example/logs",
        "/api/v1/logs/search?q=secret",
    ],
)
def test_hub_host_process_and_log_routes_require_authentication(path: str) -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 401


def test_authenticated_non_admin_cannot_start_hub_host_process() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: "ordinary-user"

    def reject_non_admin() -> str:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    app.dependency_overrides[get_admin_user] = reject_non_admin

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/servers/example/start")

    assert response.status_code == 403
