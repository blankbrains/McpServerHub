"""Explicit MCP compatibility contract for the Gateway.

The transport layer remains owned by the official MCP SDK where possible.  This
module only decides which documented protocol versions and capabilities the
Gateway can safely advertise and route.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CompatibilityStatus = Literal["verified", "partial", "unsupported"]


@dataclass(frozen=True)
class ProtocolProfile:
    """One protocol version that the Gateway has regression coverage for."""

    version: str
    supports_cancellation: bool
    supports_list_change_notifications: bool


@dataclass
class ProtocolState:
    """Negotiated state for one stdio client connection."""

    profile: ProtocolProfile | None = None
    initialized: bool = False

    @property
    def version(self) -> str:
        return self.profile.version if self.profile else ""


@dataclass(frozen=True)
class CompatibilityAssessment:
    """Safe, presentation-ready compatibility result for one observed Server."""

    status: CompatibilityStatus
    reason_code: str
    reason: str
    features: dict[str, bool]


_PROFILES = (
    ProtocolProfile(
        version="2024-11-05",
        supports_cancellation=False,
        supports_list_change_notifications=False,
    ),
    ProtocolProfile(
        version="2025-06-18",
        supports_cancellation=True,
        supports_list_change_notifications=True,
    ),
    ProtocolProfile(
        version="2026-07-28",
        supports_cancellation=True,
        supports_list_change_notifications=True,
    ),
)
_PROFILE_BY_VERSION = {profile.version: profile for profile in _PROFILES}
SUPPORTED_PROTOCOL_VERSIONS = tuple(profile.version for profile in _PROFILES)
SUPPORTED_TRANSPORTS = frozenset({"stdio", "streamable-http", "sse"})

_METHOD_CAPABILITIES = {
    "tools/list": "tools",
    "tools/call": "tools",
    "resources/list": "resources",
    "resources/templates/list": "resources",
    "resources/read": "resources",
    "prompts/list": "prompts",
    "prompts/get": "prompts",
}


def negotiate_protocol(requested_version: str) -> ProtocolProfile | None:
    """Return the exact version profile requested by a compatible client."""
    return _PROFILE_BY_VERSION.get(requested_version)


def capability_for_method(method: str) -> str | None:
    """Return the server capability required by an MCP request, if any."""
    return _METHOD_CAPABILITIES.get(method)


def supports_server_method(server: Any, method: str) -> bool:
    """Honor explicit child capabilities without breaking legacy Servers.

    Older stdio Servers may omit capabilities despite accepting a request.  An
    absent or non-set value is therefore treated as unknown and remains
    compatible.  A real non-empty set is an explicit contract and is enforced.
    """
    capability = capability_for_method(method)
    if capability is None:
        return True
    capabilities = getattr(server, "capabilities", None)
    if not isinstance(capabilities, set) or not capabilities:
        return True
    return capability in capabilities


def assess_server_compatibility(
    protocol_version: str,
    transport: str,
    capabilities: list[str],
) -> CompatibilityAssessment:
    """Classify an observed Gateway inventory row without inspecting secrets."""
    normalized_capabilities = set(capabilities)
    features = {
        "tools": "tools" in normalized_capabilities,
        "resources": "resources" in normalized_capabilities,
        "prompts": "prompts" in normalized_capabilities,
        "tasks": False,
    }
    if transport not in SUPPORTED_TRANSPORTS:
        return CompatibilityAssessment(
            status="unsupported",
            reason_code="transport_unsupported",
            reason=f"Gateway does not support {transport or 'unknown'} transport",
            features=features,
        )
    if not protocol_version:
        return CompatibilityAssessment(
            status="partial",
            reason_code="protocol_not_observed",
            reason="The Gateway has not completed protocol negotiation with this Server",
            features=features,
        )
    if protocol_version not in _PROFILE_BY_VERSION:
        return CompatibilityAssessment(
            status="unsupported",
            reason_code="protocol_unsupported",
            reason=f"MCP {protocol_version} is outside the verified compatibility set",
            features=features,
        )
    if not normalized_capabilities:
        return CompatibilityAssessment(
            status="partial",
            reason_code="capabilities_not_reported",
            reason="The Server negotiated MCP but did not report capabilities",
            features=features,
        )
    return CompatibilityAssessment(
        status="verified",
        reason_code="compatible",
        reason="Protocol, transport, and advertised capabilities are supported",
        features=features,
    )
