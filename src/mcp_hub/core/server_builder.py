"""MCP Server 项目生成器。

自动生成生产级 MCP Server 项目骨架，支持 Python 和 TypeScript。
生成的 Server 使用官方 MCP SDK，包含 tools/resources/prompts 支持，
可直接发布到 PyPI/npm 和 MCP Hub。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

Language = Literal["python", "typescript"]


# ── 工具模板定义 ───────────────────────────────────────────


@dataclass
class ToolTemplate:
    """单个工具的模板定义。"""
    name: str
    description: str
    enabled: bool = True
    params: list[dict] = field(default_factory=lambda: [
        {"name": "message", "type": "string", "description": "输入消息", "required": True},
    ])
    python_code: str = ""
    typescript_code: str = ""

    def get_python_code(self) -> str:
        """获取工具实现的 Python 代码模板。"""
        if self.python_code:
            return self.python_code
        return f"# {self.name}: {self.description} (使用默认模板)"

    def get_typescript_code(self) -> str:
        """获取工具实现的 TypeScript 代码模板。"""
        if self.typescript_code:
            return self.typescript_code
        return f"// {self.name}: {self.description} (使用默认模板)"


# ── 默认代码生成器 ─────────────────────────────────────────


def _make_python_tool_code(name: str, description: str, params: list[dict]) -> str:
    """生成 Python 工具实现代码。"""
    param_docs = "\n        ".join(
        f"{p['name']} ({p['type']}): {p['description']}"
        for p in params
    )
    return f'''@app.tool()
async def {name}({', '.join(f'{p["name"]}: {p["type"]}' for p in params)}) -> list[types.TextContent]:
    """{description}

    Args:
        {param_docs}
    Returns:
        包含处理结果的 TextContent 列表。
    """
    # TODO: 实现实际的工具逻辑
    result = f"处理完成: {', '.join(str(p['name']) + '=' + str(locals().get(p['name'], '')) for p in params)}"
    return [types.TextContent(type="text", text=result)]'''  # noqa: E501


def _make_ts_tool_code(name: str, _description: str, params: list[dict]) -> str:
    """生成 TypeScript 工具实现代码。"""
    param_interface = "\n  ".join(
        f'{p["name"]}: {p["type"]};'
        for p in params
    )
    param_access = "\n      ".join(
        f'const {p["name"]} = String(args.{p["name"]} || "");'
        for p in params
    )
    return f'''server.setRequestHandler(CallToolRequestSchema, async (request) => {{
  if (request.params.name === "{name}") {{
    const args = request.params.arguments as {{ {param_interface} }};
    {param_access}
    return {{
      content: [{{ type: "text", text: `处理完成: ${{JSON.stringify(args)}}` }}],
    }};
  }}
  throw new Error("Unknown tool: " + request.params.name);
}});'''


# ── 项目结构生成 ───────────────────────────────────────────


@dataclass
class GeneratedProject:
    """生成的完整项目。"""
    root_dir: Path
    language: Language
    server_name: str
    files: dict[str, str] = field(default_factory=dict)  # relative_path -> content
    created_files: list[Path] = field(default_factory=list)

    def write(self, root: Path | None = None) -> Path:
        """将项目写入磁盘。"""
        base = root or self.root_dir
        base.mkdir(parents=True, exist_ok=True)
        for rel_path, content in self.files.items():
            file_path = base / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            self.created_files.append(file_path)
        return base

    def summary(self) -> str:
        """返回生成摘要。"""
        total_size = sum(len(c) for c in self.files.values())
        return (
            f"  语言: {self.language}\n"
            f"  文件: {len(self.files)} 个\n"
            f"  代码: {total_size} 字符\n"
            f"  目录: {self.root_dir}"
        )


# ── 交互式构建器 ───────────────────────────────────────────


class ServerBuilder:
    """MCP Server 项目生成器。

    用法:
        builder = ServerBuilder()
        project = builder.create_project(
            name="my-server",
            language="python",
            description="My MCP Server",
            author="me",
            tools=["hello", "echo"],
        )
        project.write(Path("./my-server"))
    """

    # 预定义的工具模板
    TOOL_TEMPLATES: dict[str, ToolTemplate] = {
        "hello": ToolTemplate(
            name="hello",
            description="向用户问好",
            params=[
                {"name": "name", "type": "string", "description": "用户名称", "required": True},
            ],
        ),
        "echo": ToolTemplate(
            name="echo",
            description="原样返回输入消息",
            params=[
                {"name": "message", "type": "string", "description": "要回显的消息", "required": True},  # noqa: E501
            ],
        ),
        "calculator": ToolTemplate(
            name="calculate",
            description="执行数学运算",
            params=[
                {"name": "a", "type": "number", "description": "第一个数字", "required": True},
                {"name": "b", "type": "number", "description": "第二个数字", "required": True},
                {"name": "operation", "type": "string", "description": "运算: add/sub/mul/div", "required": True},  # noqa: E501
            ],
        ),
        "greet": ToolTemplate(
            name="greet",
            description="生成个性化问候",
            params=[
                {"name": "name", "type": "string", "description": "姓名", "required": True},
                {"name": "language", "type": "string", "description": "语言 (zh/en/ja)", "required": False},  # noqa: E501
                {"name": "style", "type": "string", "description": "风格 (formal/casual)", "required": False},  # noqa: E501
            ],
        ),
        "weather": ToolTemplate(
            name="get_weather",
            description="获取城市天气信息",
            params=[
                {"name": "city", "type": "string", "description": "城市名称", "required": True},
                {"name": "unit", "type": "string", "description": "温度单位 (celsius/fahrenheit)", "required": False},  # noqa: E501
            ],
        ),
    }

    @staticmethod
    def available_tools() -> list[str]:
        """返回可用工具模板名称列表。"""
        return list(ServerBuilder.TOOL_TEMPLATES.keys())

    @staticmethod
    def get_tool(name: str) -> ToolTemplate | None:
        """获取指定名称的工具模板。"""
        return ServerBuilder.TOOL_TEMPLATES.get(name)

    # ── 模板渲染 ──────────────────────────────────────────

    @staticmethod
    def _validate_name(name: str) -> str:
        """验证并规范化项目名称。"""
        if not re.match(r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$", name):
            raise ValueError(
                f"项目名称 '{name}' 不合法。名称必须由小写字母、数字、下划线和连字符组成，"
                f"不能以特殊字符开头或结尾。"
            )
        return name

    def create_project(
        self,
        name: str,
        language: Language = "python",
        description: str = "",
        author: str = "",
        tools: list[str] | None = None,
    ) -> GeneratedProject:
        """创建一个完整的 MCP Server 项目。

        Args:
            name: 项目名称 (如 my-mcp-server)。
            language: 语言 (python/typescript)。
            description: 项目描述。
            author: 作者名称。
            tools: 要包含的工具模板列表。

        Returns:
            包含所有文件内容的 GeneratedProject。

        Raises:
            ValueError: 名称或参数不合法。
        """
        name = self._validate_name(name)
        description = description or f"MCP Server: {name}"
        author = author or os.environ.get("USER", os.environ.get("USERNAME", "developer"))
        tools = tools or ["hello", "echo"]
        year = str(datetime.now().year)

        # 验证工具名称
        invalid = [t for t in tools if t not in self.TOOL_TEMPLATES]
        if invalid:
            raise ValueError(f"未知的工具模板: {', '.join(invalid)}。可用: {', '.join(self.available_tools())}")  # noqa: E501

        selected_tools = [self.TOOL_TEMPLATES[t] for t in tools]

        if language == "python":
            return self._generate_python(name, description, author, year, selected_tools)
        else:
            return self._generate_typescript(name, description, author, year, selected_tools)

    # ── Python 项目生成 ────────────────────────────────────

    def _generate_python(
        self,
        name: str,
        description: str,
        author: str,
        year: str,
        tools: list[ToolTemplate],
    ) -> GeneratedProject:
        """生成 Python MCP Server 项目。"""
        safe_name = name.replace("-", "_")
        display_name = name.replace("-", " ").replace("_", " ").title()

        # 构建工具注册代码
        tool_registrations = []
        for t in tools:
            tool_registrations.append(self._make_python_tool(t))

        "\n\n".join(tool_registrations)

        files: dict[str, str] = {}

        # pyproject.toml
        files["pyproject.toml"] = f"""[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
authors = [{{ name = "{author}" }}]
license = {{ text = "MIT" }}
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
]

[project.urls]
Homepage = "https://github.com/{author}/{name}"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

        # src/{safe_name}/__init__.py
        files[f"src/{safe_name}/__init__.py"] = f"""\"\"\"MCP Server: {description}\"\"\"

from {safe_name}.server import main

__all__ = ["main"]
__version__ = "0.1.0"
"""

        # src/{safe_name}/server.py （主体）
        tool_params_list = []
        for t in tools:
            for _p in t.params:
                tool_params_list.append(t)


        # 构建 tool definitions 列表
        tool_defs_list = []
        for t in tools:
            props = {}
            required = []
            for p in t.params:
                ts_type = {"string": "string", "number": "number", "integer": "integer", "boolean": "boolean"}.get(p["type"], "string")  # noqa: E501
                prop = {"type": ts_type, "description": p["description"]}
                props[p["name"]] = prop
                if p.get("required", True):
                    required.append(p["name"])
            json.dumps({
                "type": "object",
                "properties": props,
                "required": required,
            }, indent=8, ensure_ascii=False)
            tool_defs_list.append(f"""@app.tool()
async def {t.name}({', '.join(f'{p["name"]}: {p["type"]}' for p in t.params)}) -> list[TextContent]:
    \"\"\"{t.description}\"\"\"
    result = f"[{display_name}] {t.description}: " + ", ".join(
        f"{{k}}={{v}}" for k, v in locals().items() if k != "self"
    )
    return [TextContent(type="text", text=result)]""")

        tool_code_combined = "\n\n".join(tool_defs_list)

        files[f"src/{safe_name}/server.py"] = f'''"""MCP Server {display_name} — 由 MCP Server Hub 生成。"""

from __future__ import annotations

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

app = Server("{name}")


{tool_code_combined}


async def main():
    """使用 stdio 传输启动 MCP Server。"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''  # noqa: E501

        # README.md
        tool_table = "\n".join(
            f"| `{t.name}` | {t.description} |"
            for t in tools
        )

        files["README.md"] = f"""# {display_name}

{description}

由 [MCP Server Hub](https://github.com/blankbrains/McpServerHub) 生成。

## 功能

{tool_table}

## 安装

```bash
# 直接安装
pip install {name}

# 或从源码安装
git clone https://github.com/{author}/{name}
cd {name}
pip install -e .
```

## 配置

在 `claude_desktop_config.json` 中添加：

```json
{{
  "mcpServers": {{
    "{name}": {{
      "command": "uvx",
      "args": ["{name}"]
    }}
  }}
}}
```

或从源码运行：

```json
{{
  "mcpServers": {{
    "{name}": {{
      "command": "uv",
      "args": ["run", "--directory", "/path/to/{name}", "{safe_name}"]
    }}
  }}
}}
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行
python -m {safe_name}
```

## 发布

```bash
# 发布到 PyPI
pip install build twine
python -m build
twine upload dist/*
```

## 许可证

MIT © {year} {author}
"""

        # .gitignore
        files[".gitignore"] = """# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
"""

        return GeneratedProject(
            root_dir=Path(name),
            language="python",
            server_name=name,
            files=files,
        )

    # ── TypeScript 项目生成 ────────────────────────────────

    def _generate_typescript(
        self,
        name: str,
        description: str,
        author: str,
        year: str,
        tools: list[ToolTemplate],
    ) -> GeneratedProject:
        """生成 TypeScript MCP Server 项目。"""
        display_name = name.replace("-", " ").replace("_", " ").title()

        # 构建工具代码
        tool_code_parts = []
        for t in tools:
            props_parts = []
            for p in t.params:
                ts_type = {"string": "z.string()", "number": "z.number()", "integer": "z.number().int()", "boolean": "z.boolean()"}.get(p["type"], "z.string()")  # noqa: E501
                props_parts.append(f"      {p['name']}: {ts_type}.describe(\"{p['description']}\")")

            required_schema = {}
            for p in t.params:
                if p.get("required", True):
                    required_schema[p["name"]] = "z.string()"

            tool_code_parts.append(f"""  {{
    name: "{t.name}",
    description: "{t.description}",
    inputSchema: {{
      type: "object",
      properties: {{
{chr(10).join(props_parts)}
      }},
      required: [{', '.join(f'"{p["name"]}"' for p in t.params if p.get("required", True))}],
    }},
  }}""")

        tool_defs = ",\n".join(tool_code_parts)

        tool_handlers = []
        for t in tools:
            param_names = ", ".join(f'"{p["name"]}"' for p in t.params)
            ", ".join(f'{p["name"]}: args.{p["name"]}' for p in t.params)
            tool_handlers.append(f"""    if (request.params.name === "{t.name}") {{
      const args = request.params.arguments as any;
      return {{
        content: [{{ type: "text" as const, text: `[{display_name}] {t.description}: ${{JSON.stringify({{{param_names}}})}}` }}],
      }};
    }}""")  # noqa: E501

        handler_code = "\n".join(tool_handlers)

        files: dict[str, str] = {}

        # package.json
        files["package.json"] = json.dumps({
            "name": name,
            "version": "0.1.0",
            "description": description,
            "type": "module",
            "main": "dist/index.js",
            "scripts": {
                "build": "tsc",
                "start": "node dist/index.js",
                "prepare": "npm run build",
            },
            "dependencies": {
                "@modelcontextprotocol/sdk": "^1.0.0",
                "zod": "^3.22.0",
            },
            "devDependencies": {
                "typescript": "^5.4.0",
                "@types/node": "^20.0.0",
            },
        }, indent=2) + "\n"

        # tsconfig.json
        files["tsconfig.json"] = json.dumps({
            "compilerOptions": {
                "target": "ES2022",
                "module": "NodeNext",
                "moduleResolution": "NodeNext",
                "esModuleInterop": True,
                "strict": True,
                "outDir": "dist",
                "rootDir": "src",
                "declaration": True,
                "sourceMap": True,
                "skipLibCheck": True,
            },
            "include": ["src/**/*"],
        }, indent=2) + "\n"

        # src/index.ts
        files["src/index.ts"] = f"""#!/usr/bin/env node
/**
 * MCP Server: {display_name}
 * {description}
 * 由 MCP Server Hub 生成。
 */

import {{ Server }} from "@modelcontextprotocol/sdk/server/index.js";
import {{ StdioServerTransport }} from "@modelcontextprotocol/sdk/server/stdio.js";
import {{
  CallToolRequestSchema,
  ListToolsRequestSchema,
}} from "@modelcontextprotocol/sdk/types.js";
import {{ z }} from "zod";

const server = new Server(
  {{ name: "{name}", version: "0.1.0" }},
  {{ capabilities: {{ tools: {{}} }} }}
);

// ── 工具定义 ──────────────────────────────────────────────

const TOOLS = [
{tool_defs}
];

// ── 工具处理 ──────────────────────────────────────────────

server.setRequestHandler(ListToolsRequestSchema, async () => ({{
  tools: TOOLS,
}}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {{
{handler_code}
  throw new Error(`未知工具: ${{request.params.name}}`);
}});

// ── 启动 ──────────────────────────────────────────────────

async function main() {{
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`[🚀] {name} MCP Server 已启动`);
}}

main().catch((error) => {{
  console.error("[❌] Server 错误:", error);
  process.exit(1);
}});
"""

        # README.md
        tool_table = "\n".join(
            f"| `{t.name}` | {t.description} |"
            for t in tools
        )
        files["README.md"] = f"""# {display_name}

{description}

由 [MCP Server Hub](https://github.com/blankbrains/McpServerHub) 生成。

## 功能

{tool_table}

## 安装

```bash
# 安装依赖
npm install

# 构建
npm run build
```

## 配置

在 `claude_desktop_config.json` 中添加：

```json
{{
  "mcpServers": {{
    "{name}": {{
      "command": "node",
      "args": ["/path/to/{name}/dist/index.js"]
    }}
  }}
}}
```

## 开发

```bash
# 开发模式（自动重编译）
npm run build -- --watch
```

## 发布

```bash
# 发布到 npm
npm publish
```

## 许可证

MIT © {year} {author}
"""

        # .gitignore
        files[".gitignore"] = """# Node
node_modules/
dist/
*.js.map

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
"""

        return GeneratedProject(
            root_dir=Path(name),
            language="typescript",
            server_name=name,
            files=files,
        )

    # ── 辅助方法 ──────────────────────────────────────────

    @staticmethod
    def _make_python_tool(tool: ToolTemplate) -> str:
        """生成单个 Python 工具定义的代码。"""
        params_list = []
        for p in tool.params:
            ts_type = p["type"]
            params_list.append(f"        {p['name']}: {ts_type}")

        params_str = ",\n".join(params_list)
        if tool.params:
            params_str = f"\n{params_str}\n    "

        return f"""@app.tool()
async def {tool.name}(
    {', '.join(f'{p["name"]}: {p["type"]}' for p in tool.params)}
) -> list[TextContent]:
    \"\"\"{tool.description}\"\"\"
    return [TextContent(
        type="text",
        text=f"[{tool.description}] 参数: {{locals()}}"
    )]"""


# ── 便捷函数 ───────────────────────────────────────────────


def create_mcp_server(
    name: str,
    language: Language = "python",
    description: str = "",
    author: str = "",
    tools: list[str] | None = None,
    output_dir: str | Path | None = None,
) -> GeneratedProject:
    """一键创建 MCP Server 项目。

    Args:
        name: 项目名称。
        language: python 或 typescript。
        description: 项目描述。
        author: 作者。
        tools: 工具列表 (可用: hello, echo, calculator, greet, weather)。
        output_dir: 输出目录，默认当前目录。

    Returns:
        生成的 GeneratedProject 对象。
    """
    builder = ServerBuilder()
    project = builder.create_project(
        name=name,
        language=language,
        description=description,
        author=author,
        tools=tools,
    )
    output_path = Path(output_dir) if output_dir else Path.cwd()
    root = output_path / name
    project.write(root)
    return project
