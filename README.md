<div align="center">

# <img src="logo.svg" width="40" height="40" style="vertical-align:middle" alt="M"> MCP Server Hub

**MCP 生态的缺失拼图**

发现 · 安装 · 管理 · 发布 · 社区

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-316192?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![React 19](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/badge/dynamic/json?style=flat-square&label=stars&query=stargazers_count&url=https%3A%2F%2Fapi.github.com%2Frepos%2Fblankbrains%2FMcpServerHub)](https://github.com/blankbrains/McpServerHub)

---

<p align="center">
  <b>970+ 个 MCP Server</b> · <b>36 个 CLI 命令</b> · <b>16 个分类</b> · <b>20 个标签</b><br>
  搜索 → 安装 → 自动配置 → 管理。一个平台搞定。
</p>

</div>

---

## 🤔 痛点

MCP（Model Context Protocol）正在爆发式增长 — 400+ Server、100k+ Stars，被所有主流 AI 平台采用。但用户体验还停留在 2015 年：

```
👎 找 Server      → GitHub 盲搜，没有评分，没法对比
👎 安装           → 手动看 README → pip install → 手写 JSON 配置
👎 管理           → 没有统一进程管理器，没有健康检查
👎 监控           → 挂了不知道，日志散落各处
👎 发布           → 没有注册中心，没有发现机制，没有社区
```

**MCP Server Hub 解决了所有问题。**

---

## ✨ 功能一览

```
🏪 市场              ⚡ 安装                ⚙️ 管理                👥 发布
┌──────────┐         ┌──────────┐           ┌──────────┐          ┌──────────┐
│ 搜索     │  ──→   │ 一行命令  │   ──→    │ 进程管理  │  ──→   │ 一键发布 │
│ 浏览     │         │ 自动配置  │           │ 健康检查  │          │ 注册中心 │
│ 对比     │         │ 版本管理  │           │ 日志查询  │          │ 评分评价 │
│ 评分     │         │ 回滚     │           │ 自动恢复  │          │ 统计     │
└──────────┘         └──────────┘           └──────────┘          └──────────┘
                          │                       │
                          └─────── 🔗 MCP 网关 ────────┘
                        Claude Code/Cursor 的单一 stdio 入口
                        一个配置文件，所有 Server 自动发现。
```

---

## 🚀 快速开始

### 1. 安装

```bash
pip install mcp-hub-cli
```

<details>
<summary><b>🐳 或用 Docker</b></summary>

```bash
git clone https://github.com/blankbrains/McpServerHub
cd McpServerHub
docker-compose up -d
# 打开 http://localhost:3987
```
</details>

### 2. 零配置启动（30 秒上线）

```bash
mcp quickstart
```

自动使用 SQLite，无需安装 PostgreSQL。

### 3. 或完整初始化（PostgreSQL）

```bash
mcp init
mcp daemon start
# 仪表盘: http://localhost:3987
```

---

## 🎮 使用指南

### 🔍 搜索与对比

```bash
# 浏览市场
mcp search

# 按关键词搜索
mcp search database
mcp search web --category browser

# 对比两个 Server
mcp compare @modelcontextprotocol/server-postgres @modelcontextprotocol/server-sqlite

# 查看详情
mcp info @modelcontextprotocol/server-filesystem
```

### 📦 安装与运行

```bash
# 一行命令安装 + 自动配置
mcp install @modelcontextprotocol/server-filesystem

# 管理进程
mcp start server-filesystem
mcp status
mcp logs server-filesystem -f
mcp stop server-filesystem
```

### 🔌 接入 Claude Code

在 `claude_desktop_config.json` 中添加以下配置：

```json
{
  "mcpServers": {
    "mcp-hub": {
      "command": "mcp",
      "args": ["serve"]
    }
  }
}
```

**通过 Hub 安装的任何 Server 都会自动在 Claude Code 中可用，** 无需再手动编辑配置文件。

### 🌐 Web 仪表盘

```
http://localhost:3987
```

实时监控、日志查看、搜索、安装、管理 — 全部在浏览器中完成。

### 📋 本地使用（无需部署 Hub）

不想部署 Hub？每个 Server 详情页都提供配置片段，直接复制到你本地的 Agent 配置文件中即可使用。支持 Claude Code / Cursor / Codex / Trae。

---

## 📋 命令大全

```
用法: mcp [OPTIONS] COMMAND [ARGS]...

🛒  市场
  search [query]       搜索 MCP Server
  info <server>        查看详情
  compare <a> <b>      对比两个 Server

📦  安装
  install <server>     安装 Server（自动配置）
  uninstall <server>    卸载
  list                 列出已安装

⚙️  管理
  start <server>       启动
  stop <server>        停止
  restart <server>     重启
  status [server]      查看状态
  logs <server>        查看日志（-f 实时跟踪）
  update [server]      检查/更新
  rollback <server>    回滚版本
  config               管理配置

🔧  系统
  daemon start        启动 Hub 服务
  daemon stop         停止 Hub 服务
  daemon status       Hub 状态
  serve               启动 MCP 网关（stdio）
  init                一键初始化（PostgreSQL）
  quickstart          零配置启动（SQLite，30 秒）

👤  认证
  login               GitHub 登录
  logout              退出
  whoami              当前用户

📤  发布
  publish <path>      发布你的 Server
  my-servers          已发布列表
  unpublish <server>  下架
  stats <server>      统计

⭐  社区
  rate <srv> <n>      评分 (1-5)
  review <srv>        写/查看评价
  favorite <srv>      收藏
  favorites           收藏列表
  trending            热门趋势
  top-rated           评分最高
  most-downloaded     下载最多
  new-releases        最新发布

🎯  高级
  prompt-install      生成 AI 安装提示词
  hub-install         自动检测/安装 Hub
  registry-sync       从 npm/PyPI/GitHub 同步 Server

📡  事件
  event publish       发布事件
  event subscribe     订阅事件

⚙️  配置
  config download     下载配置
  config upload       上传本地配置
  export config       导出分享
```

---

## 🏗 架构

```
┌──────────────────────────────────────────────────────┐
│                    用户交互层                           │
│    ┌──────────┐        ┌──────────┐    ┌──────────┐  │
│    │   CLI    │        │ Web 仪表盘│    │ MCP stdio│  │
│    │ (Rich)   │        │ (React)  │    │ (网关)   │  │
│    └────┬─────┘        └────┬─────┘    └────┬─────┘  │
├─────────┼───────────────────┼───────────────┼────────┤
│         │                   │               │        │
│         ▼                   ▼               ▼        │
│    ┌────────────────────────────────────────────┐    │
│    │          FastAPI + 核心服务                 │    │
│    │  ┌──────────┐ ┌──────────┐ ┌────────────┐ │    │
│    │  │ 注册中心  │ │ 进程管理  │ │ MCP 网关   │ │    │
│    │  │(Registry)│ │(Manager) │ │(Aggregator)│ │    │
│    │  ├──────────┤ ├──────────┤ ├────────────┤ │    │
│    │  │ 安装器   │ │ 健康检查  │ │ 事件总线   │ │    │
│    │  │(Installer)│ │(Checker) │ │(Pub/Sub)  │ │    │
│    │  └──────────┘ └──────────┘ └────────────┘ │    │
│    └────────────────────┬───────────────────────┘    │
│                         │                           │
│                         ▼                           │
│              ┌─────────────────────┐                │
│              │ PostgreSQL 16+ /    │                │
│              │ SQLite             │                │
│              │ (async ORM)        │                │
│              └─────────────────────┘                │
└──────────────────────────────────────────────────────┘
```

---

## 🛠 技术栈

| 层 | 技术 | 选型理由 |
|----|------|---------|
| **运行时** | Python 3.10+ | 通用、原生异步 |
| **API** | FastAPI + uvicorn | 高性能异步框架 |
| **数据库** | PostgreSQL 16+ | 生产级、asyncpg |
| **ORM** | SQLAlchemy 2.0 | 成熟异步 ORM |
| **迁移** | Alembic | 版本化数据库迁移 |
| **日志** | structlog | 结构化 JSON 日志 |
| **CLI** | Click + Rich | 漂亮的终端输出 |
| **前端** | React 19 + Tailwind | 现代、快速、响应式 |
| **构建** | Vite | 即时 HMR、优化构建 |
| **协议** | MCP (JSON-RPC 2.0) | 行业标准 |
| **认证** | GitHub OAuth + JWT | 零外部依赖 |

---

## 📊 项目状态

**当前: Alpha** — 活跃开发中，API 可能变动。

| 阶段 | 状态 | 内容 |
|------|------|------|
| ✅ P0 | **完成** | MCP 协议网关（聚合所有 Server） |
| ✅ P1 | **完成** | `mcp init`、Docker、PyPI 就绪 |
| ✅ P2 | **完成** | Dashboard：SSE 日志、实时状态 |
| ✅ P3 | **完成** | CLI：Rich 表格、旋转动画、颜色 |
| ✅ P4 | **完成** | 测试、GitHub Actions CI |
| ✅ P5 | **完成** | 英文文档、CONTRIBUTING、PyPI 元数据 |

---

## 🗺 路线图

- [ ] **Hub SDK** — 用于构建 MCP Server 的 Python/JS SDK
- [ ] **VS Code 插件** — 在编辑器内管理 Server
- [ ] **团队功能** — 多用户、RBAC、审计日志
- [ ] **远程注册中心** — 云同步你的 Server 集合
- [ ] **Docker 沙箱** — 在隔离容器中运行 Server
- [ ] **性能仪表盘** — 延迟、错误率、使用分析

---

## 🤝 参与贡献

欢迎贡献！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

- 🐛 发现 Bug？[提交 Issue](https://github.com/blankbrains/McpServerHub/issues)
- 💡 有想法？[发起讨论](https://github.com/blankbrains/McpServerHub/discussions)
- 🔧 想贡献？看看 [good first issues](https://github.com/blankbrains/McpServerHub/contribute)

---

## 📄 许可证

MIT © 2026 McpServerHub

---

<div align="center">
  <sub>为 MCP 社区而生 ❤️</sub>
</div>
