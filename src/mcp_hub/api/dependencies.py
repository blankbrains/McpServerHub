"""FastAPI 认证/鉴权依赖"""

from fastapi import Depends, Header, HTTPException

from mcp_hub.core.auth import AuthService


async def get_current_user(
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="x-user-id"),
) -> str:
    """
    验证用户身份，返回 user_id.
    """
    _ = x_user_id  # Legacy header is accepted by FastAPI but never trusted.
    auth_service = AuthService()

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = await auth_service.verify_token(token)
        if payload:
            return payload["sub"]

    raise HTTPException(status_code=401, detail="需要登录")


async def get_admin_user(
    user_id: str = Depends(get_current_user),
) -> str:
    """要求管理员权限"""
    from mcp_hub.db.database import async_session_factory
    from mcp_hub.db.repositories import UserRepository

    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
    return user_id


async def get_optional_user(
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="x-user-id"),
) -> str | None:
    """返回 user_id 或 None（允许匿名访问的市场/搜索端点）"""
    try:
        return await get_current_user(authorization=authorization, x_user_id=x_user_id)
    except HTTPException:
        return None
