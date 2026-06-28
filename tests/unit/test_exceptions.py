"""单元测试 — 异常体系。"""

from __future__ import annotations

from mcp_hub.exceptions import (
    AuthError,
    GatewayError,
    InstallError,
    McpHubError,
    ProcessError,
    ProcessStartupError,
    ServerAlreadyRunningError,
    ServerNotFoundError,
    TokenExpiredError,
    TokenInvalidError,
    UnsupportedInstallTypeError,
    ValidationError,
    VersionError,
)


class TestMcpHubError:
    def test_base_error_defaults(self) -> None:
        e = McpHubError("something went wrong")
        assert str(e) == "something went wrong"
        assert e.code == "INTERNAL_ERROR"
        assert e.http_status == 400
        assert e.details == {}

    def test_base_error_custom(self) -> None:
        e = McpHubError("msg", code="CUSTOM", details={"a": 1}, http_status=500)
        assert e.code == "CUSTOM"
        assert e.http_status == 500
        assert e.details == {"a": 1}

    def test_is_exception(self) -> None:
        e = McpHubError("test")
        assert isinstance(e, Exception)


class TestServerNotFoundError:
    def test_code_and_status(self) -> None:
        e = ServerNotFoundError("@test/pkg")
        assert e.code == "SERVER_NOT_FOUND"
        assert e.http_status == 404
        assert e.details["server_id"] == "@test/pkg"
        assert "@test/pkg" in str(e)


class TestServerAlreadyRunningError:
    def test_with_pid(self) -> None:
        e = ServerAlreadyRunningError("test-srv", 12345)
        assert e.http_status == 409
        assert e.details["pid"] == 12345

    def test_without_pid(self) -> None:
        e = ServerAlreadyRunningError("test-srv")
        assert e.http_status == 409
        assert "pid" not in e.details


class TestInstallError:
    def test_with_reason(self) -> None:
        e = InstallError("pkg", reason="pip not found")
        assert e.http_status == 500
        assert e.details["reason"] == "pip not found"

    def test_without_reason(self) -> None:
        e = InstallError("pkg")
        assert e.details["reason"] is None


class TestUnsupportedInstallType:
    def test_formats_message(self) -> None:
        e = UnsupportedInstallTypeError("brew", ["pip", "npm", "uvx"])
        assert "brew" in str(e)
        assert "pip" in str(e)
        assert e.http_status == 400


class TestAuthErrors:
    def test_auth_error(self) -> None:
        e = AuthError("bad token")
        assert e.http_status == 401
        assert e.code == "AUTH_ERROR"

    def test_token_expired_is_auth_error(self) -> None:
        e = TokenExpiredError()
        assert isinstance(e, AuthError)
        assert "过期" in str(e)

    def test_token_invalid_is_auth_error(self) -> None:
        e = TokenInvalidError()
        assert isinstance(e, AuthError)
        assert "无效" in str(e)


class TestProcessErrors:
    def test_process_error(self) -> None:
        e = ProcessError("process died", server_id="srv1")
        assert e.http_status == 500
        assert e.details["server_id"] == "srv1"

    def test_process_startup_error(self) -> None:
        e = ProcessStartupError("srv1", exit_code=1, stderr="fatal error")
        assert isinstance(e, ProcessError)
        assert e.details["exit_code"] == 1
        assert "fatal error" in e.details["stderr"]


class TestGatewayError:
    def test_gateway_error(self) -> None:
        e = GatewayError("connection failed", server_id="@test/x")
        assert e.http_status == 502
        assert e.code == "GATEWAY_ERROR"


class TestValidationError:
    def test_validation_error(self) -> None:
        e = ValidationError("name is required")
        assert e.http_status == 422
        assert e.code == "VALIDATION_ERROR"


class TestVersionError:
    def test_version_error(self) -> None:
        e = VersionError("no rollback target", server_id="srv1")
        assert e.http_status == 400
        assert e.details["server_id"] == "srv1"
