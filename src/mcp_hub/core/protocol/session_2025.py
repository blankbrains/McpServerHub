"""Compatibility marker for the MCP 2025-06-18 session protocol profile."""

from mcp_hub.core.protocol.base import ProtocolProfile

PROFILE = ProtocolProfile(
    version="2025-06-18",
    supports_cancellation=True,
    supports_list_change_notifications=True,
)
