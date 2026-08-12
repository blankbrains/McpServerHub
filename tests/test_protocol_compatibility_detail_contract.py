"""Server detail protocol compatibility presentation contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
SERVER_DETAIL = ROOT / "src" / "mcp_hub" / "web" / "src" / "pages" / "ServerDetail.tsx"


def test_server_detail_shows_authenticated_local_protocol_observations() -> None:
    source = SERVER_DETAIL.read_text(encoding="utf-8")

    assert "apiGet<InventoryResponse>('/telemetry/inventory')" in source
    assert "本地 MCP 协议兼容性" in source
    assert "已实际协商的协议和能力" in source
    assert "observed.market_server_id === server.id" in source
    assert "observation.compatibility.features.tools" in source
    assert "环境变量值或请求内容" in source
