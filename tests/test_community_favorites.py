from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_hub.api.routes_community import router


def test_favorites_endpoint_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.get("/api/v1/community/favorites")

    assert response.status_code == 401


def test_favorites_endpoint_is_registered() -> None:
    routes = [route.path for route in router.routes]

    assert "/community/favorites" in routes
