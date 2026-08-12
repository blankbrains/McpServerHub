"""Public CLI and Gateway compatibility policy API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from mcp_hub.core.version_policy import build_compatibility_payload

router = APIRouter(tags=["compatibility"])


@router.get("/client-compatibility")
async def get_client_compatibility(
    cli_version: str = Query("", max_length=50),
    gateway_version: str = Query("", max_length=50),
) -> dict[str, Any]:
    """Return safe, non-sensitive Hub/CLI/Gateway version policy."""
    return {
        "success": True,
        "data": build_compatibility_payload(
            cli_version=cli_version,
            gateway_version=gateway_version,
        ),
    }
