<div align="center">

# <img src="logo.svg" width="40" height="40" style="vertical-align:middle" alt="M"> MCP Server Hub

**MCP 生态的缺失拼图**

发现 · 配置 · 代理 · 监控 · 发布

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-316192?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![React 19](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)

---

<p align="center">
  <b>动态 MCP Server 市场</b> · <b>多 Agent 配置迁移</b> · <b>本地 Gateway</b> · <b>脱敏遥测</b><br>
  搜索 → 配置 → 本地代理 → 运行监控。
</p>

</div>

---

## 🤔 痛点

MCP（Model Context Protocol）生态持续增长，但 Server 的发现、配置、运行状态和调用成本仍分散在不同工具中：

```
👎 找 Server      → GitHub 盲搜，没有评分，没法对比
👎 配置           → 手动看 README → 安装依赖 → 手写 JSON/TOML
👎 管理           → 多个 Agent 各自维护配置，变更难以同步
👎 监控           → 直接连接无法统一统计调用、延迟、错误和估算 Token
👎 发布           → 没有注册中心，没有发现机制，没有社区
```

**MCP Server Hub 将市场、个人配置、本地 Gateway 和脱敏遥测放进同一套工作流。**

---

## ☁️ 双模式：SaaS + 自托管

| 模式 | 适用场景 | 门槛 |
|------|---------|:--:|
| **中心 Hub + 本地 Gateway（推荐）** | 搜索/对比/追踪 Server，本地代理与脱敏监控 | 浏览器 + 本地 CLI |
| **自托管** | 管理员在可信服务器上集中运行 MCP Server 进程 | 需服务器并显式开启进程管理 |

**推荐用户流程**：登录 → 追踪 Server → 创建设备 → 在本地运行 `mcp-hub agent setup` → 重启 Agent → 查看监控

**自托管管理员流程**：部署 Hub → 设置 `MCP_HUB_ALLOW_SERVER_PROCESS_MANAGEMENT=true` → 由管理员集中管理 Hub 主机进程

> Agent 直接连接 MCP Server 时，Hub 无法观察调用。只有经过本地 Gateway 的请求才会产生个人监控数据。

---

## ✨ 功能一览

### 🏪 市场发现
- **搜索 & 浏览**：动态市场目录、16 分类和多维筛选（名称/分类/标签/作者/语言/安装方式/安全等级/追踪状态/排序）
- **Server 对比**：选择 2-4 个 Server 并排对比（评分/安全/下载/可靠性/许可证）
- **智能推荐**：同类推荐（看了还看了）+ 个性化推荐（基于你的偏好）
- **收藏 & 评价**：收藏 Server、评分评价、回复讨论

### ⚡ 配置管理
- **上传配置**：上传本地 `claude_desktop_config.json`，自动匹配市场 Server
- **确认追踪**：配置检查不会写入账户；用户确认后才更新个人追踪列表
- **Agent 选择**：支持 Claude Code / Codex / Cursor / Windsurf / VS Code Copilot / Trae 和通用 MCP 客户端
- **配置草稿**：保存多套配置方案（工作用/个人用），一键切换
- **配置方案市场**：发布你的配置方案，浏览他人方案，一键导入
- **多格式生成**：JSON Agent 使用 `mcpServers`/`servers`，Codex 使用 `~/.codex/config.toml`
- **安全迁移**：`mcp-hub agent setup` 先预览和确认，再备份原配置并迁移 stdio、Streamable HTTP 与 SSE Server
- **完整进程配置**：保留结构化 `command`、`args`、按 Server 授权的 `env`、`cwd` 和启用状态

### 📦 Server 管理
- **我的 Server**：个人追踪、Gateway 接入状态、同步开关、真实调用与 Token 指标
- **配置同步**：首次运行 `agent setup`，后续用 `mcp-hub config sync` 更新 `gateway.json`
- **进程管理**（自托管）：仅管理员且显式启用后可操作 Hub 主机进程
- **版本更新提醒**：自动检查已追踪 Server 是否有新版本，标记 🆕
- **安全指示灯**：绿/黄/红/灰 四色标识安全等级

### 📊 监控 & 分析
- **个人概览**：已追踪/已收藏/有更新/安全风险四维统计
- **监控大屏**：设备在线状态、真实调用次数、估算 Token、延迟、错误和本地资源采样
- **多 Agent 遥测**：为 Claude Code、Claude Desktop、Codex 等客户端创建独立设备令牌，数据按 Agent 隔离
- **调用性能**：调用量、成功率、平均/P95 延迟、输入输出估算 Token 与传输字节
- **工具与协议**：按 Server/工具聚合，并监控 `tools/call`、`resources/read`、`prompts/get`
- **进程资源**：每分钟采样 CPU、内存、进程运行时长，展示平均值与峰值
- **错误分类**：上传稳定错误类别，不上传异常正文、参数或响应
- **离线队列**：本地 SQLite 可靠队列，断网后自动重试
- **本地发现**：设备主动上报 Server 名称、命令文件名、环境变量名称和配置指纹；不上传值或完整命令
- **使用统计**：个人中心展示 30 日调用趋势（柱状图）、成功率、按 Server 分组的详情表
- **Token 分析**：工具定义 Token 估算与优化建议；调用 Token 是载荷估算值，不等同于模型供应商账单
- **安全评分**：四维评分引擎（命令/包/发布者/代码模式），危险 Server 阻止安装

### 🔔 通知 & 体验
- **通知中心**：铃铛角标 + 通知列表（告警/更新/回复/系统），支持单条删除、标为已读和全部标为已读
- **Dark Mode**：深色/亮色主题切换，记住偏好
- **全局搜索**：侧边栏搜索框，实时搜索所有 Server
- **面包屑导航**：自动生成页面层级路径
- **移动端适配**：汉堡菜单 + 响应式侧边栏

### 👤 个人中心
- 用户信息卡片（头像/GitHub ID/角色/注册时间）
- 使用统计（Server 数/调用数/估算 Token/成功率）
- 已追踪 Server 列表 + 快捷入口

---

## 🚀 快速开始

### 1. 安装

```bash
python -m pip install "mcp-hub-cli==0.2.0"
```

<details>
<summary><b>🐳 或用 Docker</b></summary>

```bash
git clone https://github.com/blankbrains/McpServerHub
cd McpServerHub
cp .env.example .env
# 在 .env 中填写 POSTGRES_PASSWORD、MCP_HUB_SECRET 和 GitHub OAuth 配置
docker compose up -d
# 打开 http://localhost:3987
```
</details>

### 2. 本机快速启动

```bash
mcp-hub quickstart
```

该命令使用 SQLite，并在用户配置目录生成本机配置。启动后打开 `http://localhost:3987`。

GitHub 登录仍需要配置 OAuth Client ID、Client Secret 和回调地址；不登录时可以浏览市场和公开页面。

### 3. 完整初始化（PostgreSQL）

```bash
mcp-hub init
mcp-hub daemon start
# 仪表盘: http://localhost:3987
```

---

## 🎮 使用指南

### 🔍 搜索与对比

```bash
# 浏览市场
mcp-hub search

# 按关键词搜索
mcp-hub search database

# 对比两个 Server
mcp-hub compare @modelcontextprotocol/server-postgres @modelcontextprotocol/server-sqlite
```

### 📦 自托管进程管理

```bash
# 仅适用于你自己部署且显式开启进程管理的 Hub
mcp-hub install @modelcontextprotocol/server-filesystem
mcp-hub start server-filesystem
mcp-hub status
mcp-hub logs server-filesystem -f
```

普通中心 Hub 用户不通过网页远程启动自己电脑上的进程，而是在本地使用 Gateway 接入。

### 🔌 一键接入 Agent 与本地监控

在监控页为正在使用的 Agent 创建设备，然后运行页面生成的一次性接入命令：

```bash
mcp-hub agent setup \
  --agent codex \
  --hub-url https://<your-hub-host> \
  --telemetry-token mcpht_<device-token>
```

CLI 会执行以下操作：

1. 自动查找 Agent 配置，或通过 `--source-config` 指定文件。
2. 展示将迁移的 stdio、Streamable HTTP 和 SSE Server。
3. 获得确认后创建带时间戳的原文件备份。
4. 将完整本地连接配置写入 Agent 独立的 `gateway.json`。
5. 用唯一的 `mcp-hub` 入口替换受支持的直接连接。
6. 上报不含 URL、请求头值、参数、响应、环境变量值和完整命令的设备清单。

后续在网页调整个人 Server 后，同步 Gateway：

```bash
mcp-hub config sync \
  --agent codex \
  --server https://<your-hub-host>
```

同步会备份 `gateway.json`，保留本地环境变量、请求头和工作目录，不覆盖 Agent 主配置。

本地诊断：

```bash
mcp-hub agent status --agent codex
mcp-hub agent doctor --agent codex
```

每个 Agent 使用独立令牌和默认状态目录，例如 `~/.config/mcp-hub/codex` 与 `~/.config/mcp-hub/claude-code`。监控大屏会显示已注册 Agent，并可按 Agent 筛选 Server 调用、成功率、延迟和估算 Token。

> 浏览器不能直接扫描用户电脑。只有用户本地 CLI/Gateway 主动发现、代理和上报的数据才会出现在 SaaS Hub 中。

### 🌐 Web 仪表盘

```
http://localhost:3987
```

浏览器负责市场、追踪配置和遥测分析；本地 Server 的启动、代理和配置迁移由 CLI/Gateway 完成。

---

## 🔐 生产部署凭证

真实凭证不得写入仓库、文档或 systemd 单元。生产环境使用服务器本地的 `/etc/mcp-hub/mcp-hub.env`，可从 `deploy/mcp-hub.env.example` 创建后填写实际值，并设置为仅管理员可读。

`deploy/mcp-hub.service` 只引用该本地环境文件；部署前请按实际服务器用户、Python 环境和项目路径调整服务单元。不要提交 `deploy/mcp-hub.env`、`.env`、计划文档或运维说明。

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| **运行时** | Python 3.10+ |
| **API** | FastAPI + uvicorn |
| **数据库** | PostgreSQL 16+（生产）/ SQLite（quickstart） |
| **ORM** | SQLAlchemy 2.0 async |
| **前端** | React 19 + Tailwind CSS + Vite |
| **CLI** | Click + Rich |
| **认证** | GitHub OAuth + JWT |
| **安全** | 四维评分引擎 |
| **监控** | 三级健康检查 + 可靠性评分 |

---

## 📊 项目状态

**当前版本：0.2.0** — 中心 Hub + 本地 Gateway 为推荐架构，同时保留显式启用的自托管进程管理。

| 模块 | 核心功能 |
|------|---------|
| 🏪 市场 | 搜索/浏览/对比/推荐/收藏/评价 |
| 📦 我的 Server | 追踪列表/同步开关/Gateway 状态/调用数据/更新提醒 |
| ⚙️ 配置中心 | 上传匹配/确认追踪/原生配置导出/Gateway 同步/草稿 |
| 📋 方案市场 | 发布方案/浏览/一键导入 |
| 📊 监控大屏 | 调用趋势/P95 延迟/Token/字节/工具/协议/CPU/内存/错误分类 |
| 👤 个人中心 | 资料/统计/趋势图 |
| 🔔 通知中心 | 告警/更新/回复/系统通知/单条删除 |
| 🌙 体验 | Dark Mode/全局搜索/面包屑/移动端 |
| 🛡️ 管理后台 | 用户/Server/分析/审核/审计/导出 |
| 🔑 安全 | JWT 认证 + OAuth CSRF + 路径注入防护 + 环境变量白名单 |

---

## 🗺 路线图

- [x] **管理后台** — 平台运营者管理用户/Server/调用数据的后台
- [ ] **VS Code 插件** — 在编辑器内管理 Server
- [ ] **团队功能** — 多用户、RBAC、审计日志
- [ ] **Docker 沙箱** — 在隔离容器中运行 Server

---

## 🤝 参与贡献

欢迎贡献！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

- 🐛 发现 Bug？[提交 Issue](https://github.com/blankbrains/McpServerHub/issues)
- 💡 有想法？[发起讨论](https://github.com/blankbrains/McpServerHub/discussions)

---

## 📄 许可证

MIT © 2026 McpServerHub

---

<div align="center">
  <sub>为 MCP 社区而生 ❤️</sub>
</div>
