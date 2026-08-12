"""Protocol compatibility matrix presentation contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
LOCAL_DISCOVERY = (
    ROOT / "src" / "mcp_hub" / "web" / "src" / "pages" / "LocalDiscovery.tsx"
)


def test_local_inventory_exposes_protocol_compatibility_matrix() -> None:
    source = LOCAL_DISCOVERY.read_text(encoding="utf-8")

    assert "compatibility:" in source
    assert "协议已验证" in source
    assert "协议部分支持" in source
    assert "协议不支持" in source
    assert "server.compatibility.reason" in source
    assert "工具 {server.compatibility.features.tools" in source
