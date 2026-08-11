# Contributing to MCP Server Hub

感谢参与 MCP Server Hub。提交代码前，请先确认改动符合当前的中心 Hub + 本地 Gateway 架构，不要把 SaaS 追踪误写成远程安装或进程管理。

## 开发环境

要求：

- Python 3.10+
- Node.js 22+
- PostgreSQL 16+，或仅测试/Quickstart 时使用 SQLite

```bash
git clone https://github.com/blankbrains/McpServerHub.git
cd McpServerHub

python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

python -m pip install -e ".[dev]"

cd src/mcp_hub/web
npm ci
npm run build
cd ../../..
```

应用运行需要以下环境变量：

```text
MCP_HUB_DATABASE_URL
MCP_HUB_SECRET
MCP_HUB_GITHUB_CLIENT_ID
MCP_HUB_GITHUB_CLIENT_SECRET
```

从 `.env.example` 创建本地配置，但不要提交 `.env`、真实 Token、密码或服务器信息。

## 代码边界

- API 路由位于 `src/mcp_hub/api/`。
- 核心服务位于 `src/mcp_hub/core/`。
- 数据模型和仓储位于 `src/mcp_hub/db/`。
- React 前端位于 `src/mcp_hub/web/`。
- CLI 命令位于 `src/mcp_hub/cli/`。
- 普通用户的运行数据必须来自已授权的本地 Gateway 遥测。
- Hub 主机进程管理默认关闭，不能与个人追踪状态混用。
- Token 指标必须明确标注为估算值。

## 验证

提交前运行完整检查：

```bash
ruff check src tests
mypy src
pytest tests/
```

前端检查：

```bash
cd src/mcp_hub/web
npm audit --audit-level=high --registry=https://registry.npmjs.org
npm run build
```

涉及 Python 分发包时还应构建并检查 wheel/sdist：

```bash
python -m pip install build twine
python -m build
python -m twine check --strict dist/*
```

每个已确认的 Bug 都应包含能够在修复前失败、修复后通过的回归测试。不要通过删除断言、降低检查级别或吞掉异常来让测试通过。

## Pull Request

1. 从最新 `main` 创建功能分支。
2. 保持改动范围聚焦，不混入无关重构。
3. 更新受影响的 README、部署说明或配置示例。
4. 确认 Ruff、Mypy、Pytest、npm audit 和前端构建通过。
5. 检查提交中没有 `.env`、凭证、计划文档或本地运维信息。
6. 提交 Pull Request 到 `main`，说明行为变化、验证结果和剩余风险。

## 文档职责

- `README.md` 只保留产品定位、最短上手路径和关键边界。
- `deploy/install.md` 维护完整安装、Gateway 接入、排障和生产部署说明。
- `deploy/install-skillhub.md` 只供 AI Agent 执行最小安全安装流程。
- 计划、服务器地址和本地 Agent 指令不属于公开文档。
