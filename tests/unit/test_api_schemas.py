"""单元测试 — API 统一响应 Schema。"""

from __future__ import annotations

import pytest
from mcp_hub.api.schemas import (
    ErrorDetail,
    ApiResponse,
    ApiDataResponse,
    ApiErrorResponse,
    ApiListResponse,
    success_response,
    error_response,
    list_response,
)


class TestResponseSchemas:
    def test_api_response(self) -> None:
        r = ApiResponse()
        assert r.success is True

    def test_api_data_response(self) -> None:
        r = ApiDataResponse(data={"id": "test"}, meta={"total": 1})
        assert r.success is True
        assert r.data == {"id": "test"}
        assert r.meta == {"total": 1}

    def test_api_error_response(self) -> None:
        detail = ErrorDetail(code="TEST_ERR", message="test error")
        r = ApiErrorResponse(error=detail)
        assert r.success is False
        assert r.error.code == "TEST_ERR"

    def test_api_list_response(self) -> None:
        r = ApiListResponse(data=[1, 2, 3], meta={"total": 3})
        assert r.success is True
        assert len(r.data) == 3


class TestHelperFunctions:
    def test_success_response_basic(self) -> None:
        r = success_response()
        assert r == {"success": True}

    def test_success_response_with_data(self) -> None:
        r = success_response(data={"key": "val"})
        assert r == {"success": True, "data": {"key": "val"}}

    def test_success_response_with_meta(self) -> None:
        r = success_response(meta={"page": 1})
        assert r == {"success": True, "meta": {"page": 1}}

    def test_error_response(self) -> None:
        r = error_response("NOT_FOUND", "not found", {"id": "x"})
        assert r["success"] is False
        assert r["error"]["code"] == "NOT_FOUND"
        assert r["error"]["details"] == {"id": "x"}

    def test_error_response_no_details(self) -> None:
        r = error_response("ERR", "message")
        assert r["error"]["details"] == {}

    def test_list_response(self) -> None:
        r = list_response([{"a": 1}], page=2, page_size=10, total=25)
        assert r["success"] is True
        assert r["data"] == [{"a": 1}]
        assert r["meta"] == {"page": 2, "page_size": 10, "total": 25}

    def test_list_response_defaults(self) -> None:
        r = list_response([], total=0)
        assert r["meta"] == {"page": 1, "page_size": 20, "total": 0}
