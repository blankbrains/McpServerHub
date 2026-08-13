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


def test_readme_documents_stable_github_install_and_first_call() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    github_install = (
        'uv tool install --force '
        '"git+https://github.com/blankbrains/McpServerHub.git@v0.3.2"'
    )

    assert github_install in readme
    assert 'python -m pip install "mcp-hub-cli==0.3.2"' not in readme
    assert "@main" not in github_install
    assert "main` 只作为测试通道" in readme
    assert "完全重启 Agent" in readme
    assert "触发真实调用并验证" in readme
    assert "未经过本地 Gateway 的直接连接也不会被监控" in readme
    assert "mcp-hub agent verify --agent codex" in readme


def test_install_guides_explain_custom_location_and_uninstall() -> None:
    guide = (WEB_SRC / "pages" / "Guide.tsx").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install_guide = (ROOT / "deploy" / "install.md").read_text(encoding="utf-8")
    agent_guide = (ROOT / "deploy" / "install-skillhub.md").read_text(
        encoding="utf-8"
    )

    for source in (guide, install_guide, agent_guide):
        assert "UV_TOOL_DIR" in source
        assert "UV_TOOL_BIN_DIR" in source
        assert "UV_CACHE_DIR" in source
        assert "UV_PYTHON_INSTALL_DIR" in source
        assert "uv tool uninstall mcp-hub-cli" in source

    for source in (guide, readme, install_guide, agent_guide):
        assert "mcp-hub agent verify" in source
        assert "mcp-hub agent backups" in source
        assert "mcp-hub agent disconnect" in source

    assert "当前终端所在目录不会决定 uv 的安装位置" in guide
    assert "不会修改远程 Hub、GitHub 仓库或项目源码" in readme
    assert "不要把“在 D 盘目录执行命令”解释为“安装到 D 盘”" in agent_guide
