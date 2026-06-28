"""API 统一请求/响应 Schema。

所有 API 端点使用统一的响应格式:

成功:
    {"success": true, "data": {...}, "meta": {"page": 1, "total": 100}}

错误:
    {"success": false, "error": {"code": "SERVER_NOT_FOUND", "message": "...", "details": {...}}}
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """错误详情。"""
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiResponse(BaseModel):
    """基础响应。"""
    success: bool = True


class ApiDataResponse(ApiResponse):
    """带数据的成功响应。"""
    data: Any = None
    meta: dict[str, Any] | None = None


class ApiErrorResponse(ApiResponse):
    """错误响应。"""
    success: bool = False
    error: ErrorDetail


class ApiListResponse(ApiResponse):
    """列表响应。"""
    data: list[Any] = []
    meta: dict[str, Any] | None = None


def success_response(data: Any = None, meta: dict[str, Any] | None = None) -> dict:
    """快捷构建成功响应字典。"""
    result: dict = {"success": True}
    if data is not None:
        result["data"] = data
    if meta is not None:
        result["meta"] = meta
    return result


def error_response(code: str, message: str, details: dict | None = None) -> dict:
    """快捷构建错误响应字典。"""
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def list_response(data: list[Any], page: int = 1, page_size: int = 20, total: int = 0) -> dict:
    """快捷构建分页列表响应字典。"""
    return {
        "success": True,
        "data": data,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    }
