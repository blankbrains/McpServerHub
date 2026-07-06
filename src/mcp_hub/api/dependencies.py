"""FastAPI 认证/鉴权依赖"""
from typing import Optional
from fastapi import Header, HTTPException, Depends
from mcp_hub.core.auth import AuthService
from mcp_hub.config import get_settings


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
) -> str:
    """
    验证用户身份，返回 user_id.
    优先级: Authorization: Bearer <token> > x-user-id header (deprecated)
    """
    auth_service = AuthService()

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = auth_service.verify_token(token)
        if payload:
            return payload["sub"]

    if x_user_id and x_user_id not in ("anonymous", "api-user", ""):
        return x_user_id

    raise HTTPException(status_code=401, detail="需要登录")


async def get_admin_user(
    user_id: str = Depends(get_current_user),
) -> str:
    """要求管理员权限"""
    from mcp_hub.db.repositories import UserRepository
    from mcp_hub.db.database import async_session_factory

    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
    return user_id


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="x-user-id"),
) -> Optional[str]:
    """返回 user_id 或 None（允许匿名访问的市场/搜索端点）"""
    try:
        return await get_current_user(authorization=authorization, x_user_id=x_user_id)
    except HTTPException:
        return None
