"""Builder API validation regression tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp_hub.api.app import create_app


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"name": ""}, "项目名称"),
        ({"name": "../escape"}, "不合法"),
        ({"name": "valid-name", "tools": "unknown"}, "未知的工具模板"),
        ({"name": "valid-name", "language": "ruby"}, "language 必须是"),
    ],
)
def test_builder_rejects_invalid_user_input_with_422(
    params: dict[str, str],
    message: str,
) -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/builder/generate", params=params)

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert message in payload["error"]["message"]


def test_builder_still_generates_valid_projects() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/builder/generate",
        params={"name": "valid-name", "language": "python", "tools": "hello"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content.startswith(b"PK")
