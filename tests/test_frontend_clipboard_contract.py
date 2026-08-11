from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB_SRC = ROOT / "src" / "mcp_hub" / "web" / "src"


def test_clipboard_utility_supports_http_fallback() -> None:
    source = (WEB_SRC / "utils" / "clipboard.ts").read_text(encoding="utf-8")

    assert "window.isSecureContext" in source
    assert "navigator.clipboard?.writeText" in source
    assert "document.createElement('textarea')" in source
    assert "document.execCommand('copy')" in source


def test_pages_use_shared_clipboard_utility() -> None:
    direct_users: list[str] = []
    for source_path in WEB_SRC.rglob("*.tsx"):
        if "navigator.clipboard" in source_path.read_text(encoding="utf-8"):
            direct_users.append(str(source_path.relative_to(WEB_SRC)))

    assert direct_users == []


def test_monitoring_setup_command_remains_visible_and_selectable() -> None:
    source = (WEB_SRC / "components" / "TelemetryPanel.tsx").read_text(
        encoding="utf-8"
    )

    assert "{setupCommand}" in source
    assert "tabIndex={0}" in source
    assert "首次接入：按顺序完成" in source
    assert "mcp-hub agent doctor --agent codex" in source
    assert "mcp-hub agent config" in source
    assert "首次接入仍应优先运行 agent setup" in source


def test_config_sync_command_requires_explicit_agent() -> None:
    source = (WEB_SRC / "pages" / "MyConfig.tsx").read_text(encoding="utf-8")

    assert "mcp-hub config sync --agent ${syncAgent}" in source
    assert "目标 Agent 必须与 agent setup 使用的类型一致" in source
    assert "mcp-hub-gateway" not in source


def test_web_upload_copy_matches_backend_json_contract() -> None:
    config_page = (WEB_SRC / "pages" / "ConfigPage.tsx").read_text(encoding="utf-8")
    guide = (WEB_SRC / "pages" / "Guide.tsx").read_text(encoding="utf-8")

    assert "isRecord(json.mcpServers)" in config_page
    assert "网页检查仅支持根节点包含 mcpServers 对象的 JSON 配置" in config_page
    assert "网页配置上传仅支持根节点为 mcpServers 的 JSON" in guide
    assert "VS Code Copilot mcp.json 使用 servers" in guide


def test_readme_documents_current_github_install_and_first_call() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    github_install = (
        'uv tool install --force '
        '"git+https://github.com/blankbrains/McpServerHub.git@main"'
    )

    assert github_install in readme
    assert 'python -m pip install "mcp-hub-cli==0.2.0"' not in readme
    assert "完全重启 Agent" in readme
    assert "触发真实调用并验证" in readme
    assert "未经过本地 Gateway 的直接连接也不会被监控" in readme
