"""Compatibility marker for the MCP 2024-11-05 protocol profile."""

from mcp_hub.core.protocol.base import ProtocolProfile

PROFILE = ProtocolProfile(
    version="2024-11-05",
    supports_cancellation=False,
    supports_list_change_notifications=False,
)
