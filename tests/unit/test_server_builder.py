"""单元测试 — MCP Server 项目生成器。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_hub.core.server_builder import (
    GeneratedProject,
    ServerBuilder,
    ToolTemplate,
    create_mcp_server,
)

# ── ToolTemplate ───────────────────────────────────────────

class TestToolTemplate:
    def test_creation(self) -> None:
        t = ToolTemplate(name="hello", description="Say hello")
        assert t.name == "hello"
        assert t.description == "Say hello"
        assert t.enabled is True

    def test_default_params(self) -> None:
        t = ToolTemplate(name="echo", description="Echo")
        assert len(t.params) == 1
        assert t.params[0]["name"] == "message"

    def test_python_code_default(self) -> None:
        t = ToolTemplate(name="test", description="test")
        code = t.get_python_code()
        assert code is not None
        assert len(code) > 0

    def test_typescript_code_default(self) -> None:
        t = ToolTemplate(name="test", description="test")
        code = t.get_typescript_code()
        assert code is not None
        assert len(code) > 0

    def test_custom_code(self) -> None:
        t = ToolTemplate(name="test", description="test", python_code="print('hello')")
        assert t.get_python_code() == "print('hello')"


# ── ServerBuilder ──────────────────────────────────────────

class TestServerBuilder:
    def test_available_tools(self) -> None:
        tools = ServerBuilder.available_tools()
        assert "hello" in tools
        assert "echo" in tools
        assert "calculator" in tools
        assert len(tools) >= 4

    def test_get_tool(self) -> None:
        t = ServerBuilder.get_tool("hello")
        assert t is not None
        assert t.name == "hello"
        assert ServerBuilder.get_tool("nonexistent") is None

    def test_validate_name_valid(self) -> None:
        result = ServerBuilder._validate_name("my-server")
        assert result == "my-server"
        result = ServerBuilder._validate_name("my_server_123")
        assert result == "my_server_123"

    def test_validate_name_invalid(self) -> None:
        with pytest.raises(ValueError):
            ServerBuilder._validate_name("-bad")
        with pytest.raises(ValueError):
            ServerBuilder._validate_name("bad-")
        with pytest.raises(ValueError):
            ServerBuilder._validate_name("UPPERCASE")

    # ── Python 项目生成 ──────────────────────────────────

    def test_create_python_minimal(self) -> None:
        builder = ServerBuilder()
        project = builder.create_project(
            name="test-server",
            language="python",
            tools=["hello"],
        )
        assert project.language == "python"
        assert project.server_name == "test-server"
        assert len(project.files) >= 4  # pyproject.toml, __init__, server.py, README, .gitignore
        assert "pyproject.toml" in project.files
        assert "README.md" in project.files
        assert ".gitignore" in project.files

    def test_create_python_full(self) -> None:
        builder = ServerBuilder()
        project = builder.create_project(
            name="my-mcp-server",
            language="python",
            description="A test MCP server",
            author="tester",
            tools=["hello", "echo", "calculator"],
        )
        assert project.language == "python"
        # Check that all tool code exists
        server_py = project.files.get("src/my_mcp_server/server.py", "")
        assert "hello" in server_py
        assert "echo" in server_py
        assert "calculate" in server_py
        # Check README content
        readme = project.files.get("README.md", "")
        assert "A test MCP server" in readme
        assert "tester" in readme

    def test_create_python_includes_imports(self) -> None:
        """生成的 Python 项目应包含正确的 MCP SDK 导入。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name="test-imports",
            language="python",
            tools=["hello"],
        )
        server_py = project.files.get("src/test_imports/server.py", "")
        assert "from mcp.server import Server" in server_py
        assert "from mcp.server.stdio import stdio_server" in server_py
        assert "from mcp.types import TextContent" in server_py

    def test_create_python_entry_point(self) -> None:
        """生成的 Python 项目应有 main() 入口点。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name="test-entry",
            language="python",
            tools=["hello"],
        )
        server_py = project.files["src/test_entry/server.py"]
        assert "async def main()" in server_py
        assert "stdio_server" in server_py

    def test_create_python_pyproject(self) -> None:
        """pyproject.toml 应包含正确的元数据。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name="test-pkg",
            language="python",
            description="test description",
            author="author123",
            tools=["hello"],
        )
        pyproject = project.files["pyproject.toml"]
        assert 'name = "test-pkg"' in pyproject
        assert 'description = "test description"' in pyproject
        assert 'authors = [{ name = "author123" }]' in pyproject
        assert '"mcp>=1.0.0"' in pyproject

    def test_create_python_gitignore(self) -> None:
        builder = ServerBuilder()
        project = builder.create_project(name="test-gi", language="python", tools=["hello"])
        gi = project.files[".gitignore"]
        assert "__pycache__" in gi
        assert ".venv" in gi
        assert ".env" in gi

    # ── TypeScript 项目生成 ──────────────────────────────

    def test_create_typescript_minimal(self) -> None:
        builder = ServerBuilder()
        project = builder.create_project(
            name="ts-server",
            language="typescript",
            tools=["hello"],
        )
        assert project.language == "typescript"
        assert "package.json" in project.files
        assert "tsconfig.json" in project.files
        assert "README.md" in project.files
        assert "src/index.ts" in project.files

    def test_create_typescript_content(self) -> None:
        """生成的 TypeScript 项目应包含正确的 SDK 引用。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name="ts-test",
            language="typescript",
            tools=["hello", "echo"],
        )
        index_ts = project.files["src/index.ts"]
        assert "@modelcontextprotocol/sdk" in index_ts
        assert "StdioServerTransport" in index_ts
        assert "CallToolRequestSchema" in index_ts
        assert "ListToolsRequestSchema" in index_ts
        assert "hello" in index_ts
        assert "echo" in index_ts

    def test_create_typescript_package_json(self) -> None:
        builder = ServerBuilder()
        project = builder.create_project(
            name="ts-pkg",
            language="typescript",
            description="ts desc",
            tools=["hello"],
        )
        pkg = json.loads(project.files["package.json"])
        assert pkg["name"] == "ts-pkg"
        assert pkg["description"] == "ts desc"
        assert "@modelcontextprotocol/sdk" in pkg["dependencies"]
        assert "typescript" in pkg["devDependencies"]

    # ── 错误处理 ─────────────────────────────────────────

    def test_invalid_tool_raises(self) -> None:
        builder = ServerBuilder()
        with pytest.raises(ValueError, match="未知的工具模板"):
            builder.create_project(
                name="test",
                language="python",
                tools=["nonexistent_tool"],
            )

    def test_invalid_name_raises(self) -> None:
        builder = ServerBuilder()
        with pytest.raises(ValueError):
            builder.create_project(name="-bad-name", language="python", tools=["hello"])

    def test_partial_invalid_tools(self) -> None:
        """部分工具无效应报错。"""
        builder = ServerBuilder()
        with pytest.raises(ValueError):
            builder.create_project(
                name="test",
                language="python",
                tools=["hello", "fake_tool_123"],
            )

    # ── GeneratedProject ─────────────────────────────────

    def test_project_write(self, tmp_path: Path) -> None:
        """项目写入磁盘应创建所有文件。"""
        project = GeneratedProject(
            root_dir=tmp_path / "test-proj",
            language="python",
            server_name="test-proj",
            files={
                "README.md": "# Test",
                "src/__init__.py": "",
            },
        )
        root = project.write(tmp_path)
        assert (root / "README.md").exists()
        assert (root / "src/__init__.py").exists()
        assert len(project.created_files) == 2

    def test_project_summary(self) -> None:
        project = GeneratedProject(
            root_dir=Path("/tmp/test"),
            language="python",
            server_name="test",
            files={"a.py": "x" * 100},
        )
        summary = project.summary()
        assert "python" in summary
        assert "1 个" in summary

    # ── 生成质量检查 ────────────────────────────────────

    def test_generated_python_syntax_valid(self) -> None:
        """生成的 Python 代码应语法正确。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name="syntax-check",
            language="python",
            tools=["hello", "echo", "calculator", "greet", "weather"],
        )
        for file_name, content in project.files.items():
            if file_name.endswith(".py"):
                # 用 compile 检查语法
                try:
                    compile(content, file_name, "exec")
                except SyntaxError as e:
                    pytest.fail(f"语法错误在 {file_name}: {e}")

    def test_generated_readme_has_all_sections(self) -> None:
        """README 应包含所有必要章节。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name="readme-check",
            language="python",
            description="test",
            author="tester",
            tools=["hello", "echo"],
        )
        readme = project.files["README.md"]
        sections = ["安装", "配置", "开发", "发布", "许可证"]
        for s in sections:
            assert s in readme, f"README 缺少章节: {s}"

    def test_generated_python_has_kebab_package_name(self) -> None:
        """带连字符的名称应转换为下划线。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name="my-awesome-server",
            language="python",
            tools=["hello"],
        )
        # 应生成 src/my_awesome_server/
        has_dir = any("my_awesome_server" in k for k in project.files)
        assert has_dir, "目录名应为 my_awesome_server"
        # 所有 .py 文件应能通过语法检查
        for fn, c in project.files.items():
            if fn.endswith(".py"):
                compile(c, fn, "exec")

    def test_generated_typescript_readme(self) -> None:
        builder = ServerBuilder()
        project = builder.create_project(
            name="ts-readme",
            language="typescript",
            tools=["hello"],
        )
        readme = project.files["README.md"]
        assert "node" in readme or "Node" in readme
        assert "npm" in readme

    # ── create_mcp_server 便捷函数 ──────────────────────

    def test_create_mcp_server_function(self, tmp_path: Path) -> None:
        """create_mcp_server 便捷函数应正常工作。"""
        project = create_mcp_server(
            name="quick-test",
            language="python",
            description="quick test",
            author="tester",
            tools=["hello"],
            output_dir=str(tmp_path),
        )
        # 检查文件生成
        assert len(project.files) >= 4
        # 检查写入磁盘
        project_path = tmp_path / "quick-test"
        assert project_path.exists()
        assert (project_path / "README.md").exists()

    def test_create_mcp_server_typescript(self, tmp_path: Path) -> None:
        project = create_mcp_server(
            name="ts-quick",
            language="typescript",
            tools=["hello", "echo"],
            output_dir=str(tmp_path),
        )
        assert "package.json" in project.files
        assert "src/index.ts" in project.files

    # ── 批量工具测试 ────────────────────────────────────

    @pytest.mark.parametrize("tool_name", ["hello", "echo", "calculator", "greet", "weather"])
    def test_each_tool_generates_correctly(self, tool_name: str) -> None:
        """每个工具模板应能正确生成 Python 代码。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name=f"test-{tool_name}",
            language="python",
            tools=[tool_name],
        )
        server_py = next(v for k, v in project.files.items() if k.endswith("server.py"))
        assert tool_name in server_py

    @pytest.mark.parametrize("tool_name", ["hello", "echo", "calculator"])
    def test_each_tool_ts_generates_correctly(self, tool_name: str) -> None:
        """每个工具模板应能正确生成 TypeScript 代码。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name=f"ts-{tool_name}",
            language="typescript",
            tools=[tool_name],
        )
        index_ts = project.files["src/index.ts"]
        assert tool_name in index_ts

    # ── 边界情况 ─────────────────────────────────────────

    def test_all_tools(self) -> None:
        """使用所有工具不应报错。"""
        builder = ServerBuilder()
        project = builder.create_project(
            name="all-tools",
            language="python",
            tools=["hello", "echo", "calculator", "greet", "weather"],
        )
        assert len(project.files) >= 4
        # 检查 Python 语法
        for fn, c in project.files.items():
            if fn.endswith(".py"):
                compile(c, fn, "exec")

    def test_long_project_name(self) -> None:
        builder = ServerBuilder()
        project = builder.create_project(
            name="a-very-long-project-name-that-should-work-fine",
            language="python",
            tools=["hello"],
        )
        assert project.server_name == "a-very-long-project-name-that-should-work-fine"

    def test_unknown_tool_raises(self) -> None:
        builder = ServerBuilder()
        with pytest.raises(ValueError):
            builder.create_project(name="test", language="python", tools=[""])
