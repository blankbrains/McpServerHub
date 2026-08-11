<div align="center">

# <img src="https://raw.githubusercontent.com/blankbrains/McpServerHub/main/logo.svg" width="40" height="40" style="vertical-align:middle" alt="M"> MCP Server Hub

**发现、配置、代理、监控和发布 MCP Server**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)

</div>

MCP Server Hub 将动态市场、个人追踪配置、本地 Gateway 和脱敏遥测放进同一套工作流。推荐架构是：

```text
AI Agent -> 本地 mcp-hub Gateway -> 本地或远程 MCP Server
                         |
                         +-> 中心 Hub：设备、调用、延迟、错误、资源和估算 Token
```

> 浏览器不会扫描用户电脑。只有经过本地 Gateway 的调用才会产生个人监控数据；Agent 直接连接 MCP Server 时，Hub 无法观察该调用。

## 核心能力

- **市场与社区**：搜索、筛选、对比、推荐、收藏、评价和发布 MCP Server。
- **个人配置**：上传 `mcpServers` JSON、确认追踪、配置草稿、方案市场和多 Agent 导出。
- **本地 Gateway**：迁移 stdio、Streamable HTTP 和 SSE Server，保留 `args`、`env`、请求头和工作目录。
- **监控与分析**：设备在线状态、调用量、成功率、平均/P95 延迟、错误分类、资源采样和估算 Token。
- **本地发现**：上报脱敏设备清单和配置指纹，不上传环境变量值、请求头值、完整命令、参数或响应正文。
- **自托管进程管理**：默认关闭，仅管理员设置 `MCP_HUB_ALLOW_SERVER_PROCESS_MANAGEMENT=true` 后可操作 Hub 主机进程。

## 快速开始

当前版本为 `0.2.0`，**尚未发布到 PyPI**。请从 GitHub 安装，不要执行 `pip install mcp-hub-cli==0.2.0`。

### 连接现有 Hub 并监控本地 MCP

1. 安装 CLI：

   ```bash
   uv tool install --force "git+https://github.com/blankbrains/McpServerHub.git@main"
   uv tool update-shell
   mcp-hub --version
   ```

   这条命令只在当前电脑安装 `mcp-hub` CLI 和本地 Gateway，不会修改远程 Hub、GitHub 仓库或项目源码。当前终端位于哪个磁盘不会决定安装位置；Windows 安装到 D 盘以及卸载方法见[安装与部署指南](deploy/install.md#windows-安装到-d-盘)。

2. 确认运行 Agent 的电脑可以访问 Hub：

   ```bash
   curl "http://<Hub地址>:3987/api/v1/health"
   ```

3. 在 Hub 网页登录，进入“监控”页面，为实际使用的 Agent 创建设备。设备令牌只显示一次，不要写入文档或提交到 Git。

4. 确保目标 Agent 已配置至少一个可用 MCP Server，然后执行页面生成的命令：

   ```bash
   mcp-hub agent setup \
     --agent codex \
     --hub-url http://<Hub地址>:3987 \
     --telemetry-token mcpht_<设备令牌>
   ```

5. 完全重启 Agent：退出 Agent 的所有进程后重新打开，确保新进程加载 Gateway 配置。

6. 触发真实调用并验证：让 Agent 实际调用一次已迁移 Server 的 MCP 工具，再回到监控页刷新。普通对话不会产生工具调用数据，未经过本地 Gateway 的直接连接也不会被监控。

诊断命令：

```bash
mcp-hub agent verify --agent codex
mcp-hub agent verify --agent codex --json
mcp-hub agent status --agent codex
mcp-hub agent doctor --agent codex
```

`agent verify` 会同时检查 Agent 入口、Gateway 配置、命令与 cwd、本地遥测队列、Hub 网络、设备令牌、Gateway 心跳和首次真实工具调用。默认只读；只有显式执行 `--fix` 并确认预览后，才会创建缺失的状态目录、备份并规范可安全判定的重复/旧 Gateway 入口，或立即重试遥测队列。它不会生成新令牌，也不会把网络超时误报为令牌无效。

后续在网页调整追踪列表后同步 Gateway：

```bash
mcp-hub config sync --agent codex --server http://<Hub地址>:3987
```

完整的 Agent 配置路径、Windows 命令、故障排查和部署步骤见 [安装与部署指南](https://github.com/blankbrains/McpServerHub/blob/main/deploy/install.md)。

### 在本机运行整个 Hub

从源码构建前端并安装本地包：

```bash
git clone https://github.com/blankbrains/McpServerHub.git
cd McpServerHub
cd src/mcp_hub/web
npm ci
npm run build
cd ../../..
uv tool install --force .
mcp-hub quickstart
# http://localhost:3987
```

Quickstart 会把配置写入 `~/.config/mcp-hub/.env`。默认 OAuth 值只能浏览公开页面；需要登录时必须配置真实 GitHub OAuth App。

仅从 GitHub URL 安装 CLI 时不会携带仓库中未跟踪的前端构建产物，适合连接现有 Hub。Docker 和生产 systemd 部署见 [安装与部署指南](https://github.com/blankbrains/McpServerHub/blob/main/deploy/install.md)。

## 关键边界

| 项目 | 实际行为 |
|------|----------|
| 追踪 Server | 保存当前账户与 Server 的关系，不会远程安装或启动本地进程 |
| 原生配置导出 | Agent 直接连接 Server，不经过 Gateway，因此没有 Hub 调用监控 |
| Gateway 监控 | 记录脱敏指标，不上传原始请求、响应、凭证或完整命令 |
| Token | 根据工具定义或 MCP 调用载荷估算，不等同于模型供应商账单 |
| 网页上传 | 当前仅解析根节点为 `mcpServers` 的 JSON；TOML 和 `servers` JSON 请使用 CLI 迁移 |
| 自托管进程管理 | 默认关闭，只适用于可信 Hub 主机上的管理员 |

## 常用命令

```bash
# 市场
mcp-hub search database
mcp-hub info <server-id>
mcp-hub compare <server-a> <server-b>

# Agent / Gateway
mcp-hub agent setup --agent codex --hub-url <url> --telemetry-token <token>
mcp-hub agent verify --agent codex
mcp-hub agent status --agent codex
mcp-hub agent doctor --agent codex
mcp-hub config sync --agent codex --server <url>

# 本机 Hub
mcp-hub quickstart

# 仅限显式启用的自托管进程管理
mcp-hub install <server-id>
mcp-hub start <server-id>
mcp-hub status
mcp-hub logs <server-id> -f
```

运行 `mcp-hub --help` 或 `mcp-hub <command> --help` 查看完整参数。

## 文档

- [安装与部署指南](https://github.com/blankbrains/McpServerHub/blob/main/deploy/install.md)：CLI 安装、Gateway 接入、排障、Docker 和 systemd。
- [AI Agent 安装说明](https://github.com/blankbrains/McpServerHub/blob/main/deploy/install-skillhub.md)：供自动化代理执行的最小安全流程。
- [贡献指南](https://github.com/blankbrains/McpServerHub/blob/main/CONTRIBUTING.md)：开发环境、检查命令和 Pull Request 要求。

## 技术栈

| 层 | 技术 |
|----|------|
| API | Python 3.10+、FastAPI、Uvicorn |
| 数据库 | PostgreSQL（生产）/ SQLite（Quickstart）、SQLAlchemy async |
| 前端 | React 19、TypeScript、Vite、Tailwind CSS |
| CLI | Click、Rich |
| 认证 | GitHub OAuth、JWT |
| 监控 | 本地 Gateway、可靠遥测队列、聚合分析 |

## 开发状态

当前版本：`0.2.0`

- 中心 Hub + 本地 Gateway 是推荐用户架构。
- 自托管进程管理保留，但默认关闭。
- CI 执行 Ruff、Mypy、Pytest、npm audit、前端构建和 Python 包构建。
- PyPI 发布暂缓；安装命令以本 README 和 `deploy/install.md` 为准。

## 参与贡献

提交代码前请阅读 [贡献指南](https://github.com/blankbrains/McpServerHub/blob/main/CONTRIBUTING.md)。Bug 和功能建议可通过 GitHub Issues 或 Discussions 提交。

## 许可证

MIT © 2026 McpServerHub
