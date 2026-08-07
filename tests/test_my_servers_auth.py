from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_hub.api.routes_config import router


def test_my_servers_routes_require_authentication() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with TestClient(app) as client:
        list_response = client.get("/api/v1/config/user-servers")
        toggle_response = client.post(
            "/api/v1/config/user-servers/toggle",
            json={"server_id": "anonymous-test", "enabled": True},
        )
        delete_response = client.delete("/api/v1/config/user-servers/anonymous-test")

    assert list_response.status_code == 401
    assert toggle_response.status_code == 401
    assert delete_response.status_code == 401
