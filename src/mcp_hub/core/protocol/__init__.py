"""MCP version compatibility profiles shared by the Gateway and Hub APIs."""

from mcp_hub.core.protocol.base import (
    SUPPORTED_PROTOCOL_VERSIONS,
    CompatibilityAssessment,
    ProtocolProfile,
    ProtocolState,
    assess_server_compatibility,
    capability_for_method,
    negotiate_protocol,
    supports_server_method,
)

__all__ = [
    "SUPPORTED_PROTOCOL_VERSIONS",
    "CompatibilityAssessment",
    "ProtocolProfile",
    "ProtocolState",
    "assess_server_compatibility",
    "capability_for_method",
    "negotiate_protocol",
    "supports_server_method",
]
