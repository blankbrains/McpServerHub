from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_hub.api.routes_manage import router


def test_stop_server_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.post("/api/v1/servers/anonymous-stop-test/stop")

    assert response.status_code == 401
