"""Auth 模块单元测试。"""

from __future__ import annotations

from mcp_hub.core.auth import simple_jwt_decode, simple_jwt_encode


def test_jwt_encode_decode():
    """JWT 应能正确编码和解码。"""
    payload = {"sub": "test-user", "role": "user"}
    token = simple_jwt_encode(payload)
    assert token is not None
    assert len(token.split(".")) == 3

    decoded = simple_jwt_decode(token)
    assert decoded is not None
    assert decoded["sub"] == "test-user"
    assert decoded["role"] == "user"


def test_jwt_has_valid_structure():
    """JWT token 应有正确的三部分结构。"""
    payload = {"sub": "test", "role": "user"}
    token = simple_jwt_encode(payload)
    parts = token.split(".")
    assert len(parts) == 3
    # header
    import base64
    import json
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    assert header["alg"] == "HS256"
    assert header["typ"] == "JWT"
    # payload has required fields
    payload_decoded = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
    assert payload_decoded["sub"] == "test"
    assert "iat" in payload_decoded
    assert "exp" in payload_decoded
    assert payload_decoded["exp"] > payload_decoded["iat"]


def test_jwt_invalid():
    """无效 JWT 应返回 None。"""
    assert simple_jwt_decode("invalid.token.here") is None
    assert simple_jwt_decode("") is None
    assert simple_jwt_decode("a.b.c.d") is None
