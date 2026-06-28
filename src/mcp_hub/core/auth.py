"""OAuth 认证 + JWT + GitHub 登录。"""

from __future__ import annotations

import json
import time
from urllib.parse import urlencode

import httpx

from mcp_hub.config import get_settings
from mcp_hub.db.repositories import UserRepository
from mcp_hub.db.database import async_session_factory

settings = get_settings()


def simple_jwt_encode(payload: dict) -> str:
    """生产级 JWT 编码（纯 HMAC-SHA256，无外部依赖）。"""
    import hashlib
    import hmac
    import base64

    secret = settings.SECRET_KEY
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload["iat"] = int(time.time())
    payload["exp"] = int(time.time()) + 86400 * 7  # 7 天有效期
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    message = f"{header}.{payload_b64}"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{message}.{sig_b64}"


def simple_jwt_decode(token: str) -> dict | None:
    """验证并解码 JWT。"""
    import hashlib
    import hmac
    import base64

    secret = settings.SECRET_KEY
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, sig_b64 = parts
    message = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).digest()
    actual_sig = base64.urlsafe_b64decode(sig_b64 + "==")
    if not hmac.compare_digest(expected_sig, actual_sig):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    except (json.JSONDecodeError, Exception):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


class AuthService:
    """认证服务：GitHub OAuth + JWT。"""

    @staticmethod
    def get_github_login_url(state: str = "") -> str:
        """生成 GitHub OAuth 授权 URL。"""
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_token(code: str) -> str | None:
        """用授权码换取 access_token。"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_REDIRECT_URI,
                },
                headers={"Accept": "application/json"},
                timeout=30,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data.get("access_token")

    @staticmethod
    async def get_github_user(access_token: str) -> dict | None:
        """通过 access_token 获取 GitHub 用户信息。"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30,
            )
            if resp.status_code != 200:
                return None
            return resp.json()

    async def authenticate_with_github(self, code: str) -> dict:
        """完整的 GitHub OAuth 认证流程。"""
        # Step 1: code → access_token
        access_token = await self.exchange_code_for_token(code)
        if not access_token:
            return {"success": False, "error": "GitHub 授权码无效或已过期"}

        # Step 2: access_token → user info
        github_user = await self.get_github_user(access_token)
        if not github_user:
            return {"success": False, "error": "获取 GitHub 用户信息失败"}

        # Step 3: create/get user in local DB
        async with async_session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_or_create({
                "id": github_user.get("login", ""),
                "name": github_user.get("name", ""),
                "avatar_url": github_user.get("avatar_url", ""),
            })

        # Step 4: generate JWT
        token = simple_jwt_encode({
            "sub": user["id"],
            "role": user.get("role", "user"),
        })

        return {
            "success": True,
            "token": token,
            "user_id": user["id"],
            "display_name": user.get("display_name", user["id"]),
            "avatar_url": user.get("avatar_url", ""),
        }

    async def authenticate(self, user_data: dict) -> dict:
        """直接创建/认证用户（用于 CLI 等场景）。"""
        async with async_session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_or_create(user_data)
        token = simple_jwt_encode({
            "sub": user["id"],
            "role": user.get("role", "user"),
        })
        return {
            "success": True,
            "token": token,
            "user_id": user["id"],
        }

    async def verify_token(self, token: str) -> dict | None:
        """验证 token 并返回用户信息。"""
        payload = simple_jwt_decode(token)
        if not payload:
            return None
        async with async_session_factory() as session:
            repo = UserRepository(session)
            return await repo.get_or_create({"id": payload["sub"]})
