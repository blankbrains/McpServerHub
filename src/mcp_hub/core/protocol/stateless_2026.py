"""Compatibility marker for the MCP 2026-07-28 protocol profile."""

from mcp_hub.core.protocol.base import ProtocolProfile

PROFILE = ProtocolProfile(
    version="2026-07-28",
    supports_cancellation=True,
    supports_list_change_notifications=True,
)
