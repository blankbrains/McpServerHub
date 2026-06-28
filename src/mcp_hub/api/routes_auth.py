"""GitHub OAuth 认证 API。"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from mcp_hub.core.auth import AuthService
from mcp_hub.exceptions import AuthError, TokenInvalidError

router = APIRouter(tags=["auth"])
auth_service = AuthService()


@router.get("/auth/login")
async def login():
    """跳转到 GitHub OAuth 授权页。"""
    url = auth_service.get_github_login_url()
    return RedirectResponse(url=url, status_code=302)


@router.get("/auth/callback")
async def callback(
    code: str = Query(""),
    state: str = Query(""),
    error: str | None = Query(None),
):
    """GitHub OAuth 回调处理。"""
    if error:
        raise AuthError(f"GitHub 授权失败: {error}")
    if not code:
        raise AuthError("缺少授权码")

    result = await auth_service.authenticate_with_github(code)
    if not result["success"]:
        raise AuthError(result.get("error", "认证失败"))

    # 返回 HTML 页面，关闭窗口并将 token 传给前端
    token = result["token"]
    user_id = result["user_id"]
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>登录成功</title></head>
<body style="font-family:sans-serif;text-align:center;padding:60px 20px;">
    <h1 style="color:#22c55e;">✅ 登录成功</h1>
    <p>欢迎, <strong>{user_id}</strong></p>
    <p style="color:#666;">登录窗口即将关闭...</p>
    <script>
        localStorage.setItem("mcp_hub_token", "{token}");
        localStorage.setItem("mcp_hub_user", '{user_id}');
        window.close();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/auth/me")
async def get_current_user(request: Request):
    """获取当前登录用户信息。"""
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif "token" in request.query_params:
        token = request.query_params["token"]

    if not token:
        raise AuthError("未登录")

    user = await auth_service.verify_token(token)
    if not user:
        raise TokenInvalidError()

    return {"success": True, "data": user}


@router.post("/auth/logout")
async def logout():
    """退出登录（客户端清除 token 即可，服务端无状态）。"""
    return {"success": True, "message": "已退出登录"}
