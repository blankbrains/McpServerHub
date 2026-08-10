"""FastAPI 认证/鉴权依赖"""

from fastapi import Depends, Header, HTTPException, Request

from mcp_hub.config import get_settings
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
            user_id = payload.get("sub")
            if isinstance(user_id, str) and user_id:
                return user_id

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


async def get_process_admin(
    user_id: str = Depends(get_admin_user),
) -> str:
    """Require an administrator and explicit self-hosted process-control opt-in."""
    if not get_settings().ALLOW_SERVER_PROCESS_MANAGEMENT:
        raise HTTPException(
            status_code=403,
            detail=(
                "中央进程管理未启用；SaaS 用户应通过本地 Gateway 管理和监控 MCP Server"
            ),
        )
    return user_id


async def get_process_admin_eventstream(request: Request) -> str:
    """Authenticate an EventSource request before exposing host process data."""
    authorization = request.headers.get("Authorization")
    if not authorization:
        token = request.query_params.get("token", "")
        authorization = f"Bearer {token}" if token else None
    user_id = await get_current_user(authorization=authorization, x_user_id=None)
    admin_id = await get_admin_user(user_id)
    return await get_process_admin(admin_id)


async def get_optional_user(
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="x-user-id"),
) -> str | None:
    """返回 user_id 或 None（允许匿名访问的市场/搜索端点）"""
    try:
        return await get_current_user(authorization=authorization, x_user_id=x_user_id)
    except HTTPException:
        return None
