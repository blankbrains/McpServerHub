from __future__ import annotations

import re
from pathlib import Path

WEB_SRC = Path(__file__).parents[1] / "src" / "mcp_hub" / "web" / "src"


def test_literal_navigation_targets_are_registered_routes() -> None:
    app_source = (WEB_SRC / "App.tsx").read_text(encoding="utf-8")
    registered_routes = set(re.findall(r'<Route\s+path="([^"]+)"', app_source))

    navigation_targets: set[str] = set()
    for source_path in WEB_SRC.rglob("*.tsx"):
        source = source_path.read_text(encoding="utf-8")
        navigation_targets.update(
            re.findall(r"""navigate\(\s*['"](/[^'"]*)['"]\s*\)""", source)
        )

    missing = sorted(target for target in navigation_targets if target not in registered_routes)
    assert missing == [], f"Literal navigation targets without a registered route: {missing}"
