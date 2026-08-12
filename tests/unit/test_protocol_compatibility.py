"""Regression coverage for the explicit Gateway MCP compatibility contract."""

from __future__ import annotations

from types import SimpleNamespace

from mcp_hub.core.protocol import (
    SUPPORTED_PROTOCOL_VERSIONS,
    assess_server_compatibility,
    negotiate_protocol,
    supports_server_method,
)


def test_supported_protocol_profiles_are_exact_and_versioned() -> None:
    assert SUPPORTED_PROTOCOL_VERSIONS == (
        "2024-11-05",
        "2025-06-18",
        "2026-07-28",
    )
    assert negotiate_protocol("2024-11-05") is not None
    assert negotiate_protocol("2026-07-28") is not None
    assert negotiate_protocol("2099-01-01") is None


def test_explicit_child_capabilities_are_enforced_without_breaking_legacy() -> None:
    explicit = SimpleNamespace(capabilities={"resources"})
    legacy = SimpleNamespace(capabilities=set())
    unknown = SimpleNamespace()

    assert supports_server_method(explicit, "resources/read") is True
    assert supports_server_method(explicit, "tools/call") is False
    assert supports_server_method(legacy, "tools/call") is True
    assert supports_server_method(unknown, "prompts/get") is True


def test_inventory_compatibility_assessment_has_safe_reason_codes() -> None:
    verified = assess_server_compatibility(
        "2026-07-28",
        "streamable-http",
        ["tools", "resources"],
    )
    assert verified.status == "verified"
    assert verified.reason_code == "compatible"
    assert verified.features == {
        "tools": True,
        "resources": True,
        "prompts": False,
        "tasks": False,
    }

    partial = assess_server_compatibility("2025-06-18", "stdio", [])
    assert partial.status == "partial"
    assert partial.reason_code == "capabilities_not_reported"

    unsupported_protocol = assess_server_compatibility(
        "2030-01-01",
        "stdio",
        ["tools"],
    )
    assert unsupported_protocol.status == "unsupported"
    assert unsupported_protocol.reason_code == "protocol_unsupported"

    unsupported_transport = assess_server_compatibility(
        "2026-07-28",
        "websocket",
        ["tools"],
    )
    assert unsupported_transport.status == "unsupported"
    assert unsupported_transport.reason_code == "transport_unsupported"
