"""MCP Server Hub 统一异常体系。

所有业务异常继承自 McpHubError，API 层通过 FastAPI exception_handler 统一捕获。
"""

from __future__ import annotations


class McpHubError(Exception):
    """所有 McpHub 异常的基类。

    Attributes:
        message: 面向用户的错误描述
        code: 机器可读的错误码（如 "SERVER_NOT_FOUND"）
        details: 可选的附加信息字典
        http_status: 对应的 HTTP 状态码
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: dict | None = None,
        http_status: int = 400,
    ) -> None:
        self.code = code
        self.details = details or {}
        self.http_status = http_status
        super().__init__(message)


# ── 资源类异常 ────────────────────────────────────────────

class ServerNotFoundError(McpHubError):
    """Server 不存在。"""

    def __init__(self, server_id: str) -> None:
        super().__init__(
            message=f"Server '{server_id}' 未找到",
            code="SERVER_NOT_FOUND",
            details={"server_id": server_id},
            http_status=404,
        )


class ServerAlreadyRunningError(McpHubError):
    """Server 已在运行，不允许重复操作。"""

    def __init__(self, server_id: str, pid: int | None = None) -> None:
        details = {"server_id": server_id}
        if pid is not None:
            details["pid"] = pid
        super().__init__(
            message=f"Server '{server_id}' 已在运行" + (f" (PID: {pid})" if pid else ""),
            code="SERVER_ALREADY_RUNNING",
            details=details,
            http_status=409,
        )


class ServerNotRunningError(McpHubError):
    """Server 未在运行。"""

    def __init__(self, server_id: str) -> None:
        super().__init__(
            message=f"Server '{server_id}' 当前未运行",
            code="SERVER_NOT_RUNNING",
            details={"server_id": server_id},
            http_status=400,
        )


# ── 安装类异常 ────────────────────────────────────────────

class InstallError(McpHubError):
    """安装失败。"""

    def __init__(self, server_id: str, reason: str | None = None) -> None:
        super().__init__(
            message=f"安装 {server_id} 失败" + (f": {reason}" if reason else ""),
            code="INSTALL_FAILED",
            details={"server_id": server_id, "reason": reason},
            http_status=500,
        )


class UnsupportedInstallTypeError(McpHubError):
    """不支持的安装类型。"""

    def __init__(self, install_type: str, supported: list[str] | None = None) -> None:
        detail_msg = f"不支持的安装类型: {install_type}"
        if supported:
            detail_msg += f"，当前仅支持: {', '.join(supported)}"
        super().__init__(
            message=detail_msg,
            code="UNSUPPORTED_INSTALL_TYPE",
            details={"install_type": install_type, "supported": supported},
            http_status=400,
        )


# ── 配置类异常 ────────────────────────────────────────────

class ConfigError(McpHubError):
    """配置相关错误。"""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message=message,
            code="CONFIG_ERROR",
            details=details,
            http_status=400,
        )


# ── 认证类异常 ────────────────────────────────────────────

class AuthError(McpHubError):
    """认证/授权失败。"""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message=message,
            code="AUTH_ERROR",
            details=details,
            http_status=401,
        )


class TokenExpiredError(AuthError):
    """Token 已过期。"""

    def __init__(self) -> None:
        super().__init__(
            message="Token 已过期，请重新登录",
            details={},
        )


class TokenInvalidError(AuthError):
    """Token 无效。"""

    def __init__(self) -> None:
        super().__init__(
            message="Token 无效或已过期",
            details={},
        )


# ── 进程类异常 ────────────────────────────────────────────

class ProcessError(McpHubError):
    """进程管理相关错误。"""

    def __init__(
        self,
        message: str,
        server_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        d = details or {}
        if server_id:
            d["server_id"] = server_id
        super().__init__(
            message=message,
            code="PROCESS_ERROR",
            details=d,
            http_status=500,
        )


class ProcessStartupError(ProcessError):
    """进程启动后立即退出。"""

    def __init__(self, server_id: str, exit_code: int, stderr: str = "") -> None:
        super().__init__(
            message=f"Server '{server_id}' 启动后立即退出 (exit code={exit_code})",
            server_id=server_id,
            details={"exit_code": exit_code, "stderr": stderr[:500]},
        )


# ── 网关类异常 ────────────────────────────────────────────

class GatewayError(McpHubError):
    """MCP 网关相关错误。"""

    def __init__(
        self,
        message: str,
        server_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        d = details or {}
        if server_id:
            d["server_id"] = server_id
        super().__init__(
            message=message,
            code="GATEWAY_ERROR",
            details=d,
            http_status=502,
        )


# ── 验证类异常 ────────────────────────────────────────────

class ValidationError(McpHubError):
    """输入验证失败。"""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            http_status=422,
        )


# ── 版本管理类异常 ────────────────────────────────────────

class VersionError(McpHubError):
    """版本管理相关错误。"""

    def __init__(
        self,
        message: str,
        server_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        d = details or {}
        if server_id:
            d["server_id"] = server_id
        super().__init__(
            message=message,
            code="VERSION_ERROR",
            details=d,
            http_status=400,
        )
