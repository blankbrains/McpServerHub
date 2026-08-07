<div align="center">

# <img src="logo.svg" width="40" height="40" style="vertical-align:middle" alt="M"> MCP Server Hub

**MCP 生态的缺失拼图**

发现 · 安装 · 管理 · 发布 · 社区

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-316192?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![React 19](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)

---

<p align="center">
  <b>983+ 个 MCP Server</b> · <b>23 个 Web 页面</b> · <b>16 个分类</b> · <b>315 个测试</b><br>
  搜索 → 安装 → 配置 → 监控。一个平台搞定。
</p>

</div>

---

## 🤔 痛点

MCP（Model Context Protocol）正在爆发式增长 — 983+ Server，被所有主流 AI 平台采用。但用户体验还停留在 2015 年：

```
👎 找 Server      → GitHub 盲搜，没有评分，没法对比
👎 安装           → 手动看 README → pip install → 手写 JSON 配置
👎 管理           → 没有统一进程管理器，没有健康检查
👎 监控           → 挂了不知道，日志散落各处
👎 发布           → 没有注册中心，没有发现机制，没有社区
```

**MCP Server Hub 解决了所有问题。**

---

## ☁️ 双模式：SaaS + 自托管

| 模式 | 适用场景 | 门槛 |
|------|---------|:--:|
| **SaaS（推荐）** | 搜索/对比/追踪 Server，获取安装命令，版本更新提醒 | 打开浏览器即可 |
| **自托管** | 团队/企业集中管理 MCP Server 进程，实时监控 | 需服务器 |

**SaaS 用户流程**：登录 → 搜索 Server → 点"追踪" → 复制安装命令 → 粘贴到 Claude Code / Cursor 的 mcp.json
**自托管用户流程**：部署 Hub → 一键安装 → 集中管理所有 MCP Server 进程 + 实时健康监控

---

## ✨ 功能一览

### 🏪 市场发现
- **搜索 & 浏览**：983+ Server，16 分类，9 维筛选（名称/分类/标签/作者/语言/安装方式/安全等级/追踪状态/排序）
- **Server 对比**：选择 2-4 个 Server 并排对比（评分/安全/下载/可靠性/许可证）
- **智能推荐**：同类推荐（看了还看了）+ 个性化推荐（基于你的偏好）
- **收藏 & 评价**：收藏 Server、评分评价、回复讨论

### ⚡ 配置管理
- **上传配置**：上传本地 `claude_desktop_config.json`，自动匹配市场 Server
- **上传/取消**：明确选择是否将配置上传到 Hub 进行监控追踪
- **Agent 选择**：支持 Claude Code / Codex / Cursor / Windsurf / VS Code Copilot / Trae 和通用 MCP 客户端
- **配置草稿**：保存多套配置方案（工作用/个人用），一键切换
- **配置方案市场**：发布你的配置方案，浏览他人方案，一键导入
- **下载 & 同步**：一键下载配置文件，CLI 同步到本地

### 📦 Server 管理
- **我的 Server**：配置追踪 / 进程管理 双视图切换
- **配置追踪**：追踪 Server → 查看安装命令 → 一键复制 → 粘贴到本地 Agent
- **进程管理**（自托管）：批量操作、启动/停止/重启、调用数据、可靠性评分
- **版本更新提醒**：自动检查已追踪 Server 是否有新版本，标记 🆕
- **安全指示灯**：绿/黄/红/灰 四色标识安全等级

### 📊 监控 & 分析
- **个人概览**：已追踪/已收藏/有更新/安全风险 四维统计
- **监控大屏**：实时运行状态、调用次数、Token 消耗、可靠性排行榜
- **多 Agent 遥测**：为 Claude Code、Codex 等客户端创建独立设备令牌，调用、延迟、错误和 Token 按 Agent 隔离汇总与筛选
- **使用统计**：个人中心展示 30 日调用趋势（柱状图）、成功率、按 Server 分组的详情表
- **Token 分析**：工具定义 Token 消耗分析 + 优化建议
- **安全评分**：四维评分引擎（命令/包/发布者/代码模式），危险 Server 阻止安装

### 🔔 通知 & 体验
- **通知中心**：铃铛角标 + 通知列表（告警/更新/回复/系统），支持单条删除、标为已读和全部标为已读
- **Dark Mode**：深色/亮色主题切换，记住偏好
- **全局搜索**：侧边栏搜索框，实时搜索所有 Server
- **面包屑导航**：自动生成页面层级路径
- **移动端适配**：汉堡菜单 + 响应式侧边栏

### 👤 个人中心
- 用户信息卡片（头像/GitHub ID/角色/注册时间）
- 使用统计（Server 数/调用数/Token/成功率）
- 安装的 Server 列表 + 快捷入口

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
cp .env.example .env
# 在 .env 中填写 POSTGRES_PASSWORD、MCP_HUB_SECRET 和 GitHub OAuth 配置
docker compose up -d
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

# 对比两个 Server
mcp compare @modelcontextprotocol/server-postgres @modelcontextprotocol/server-sqlite
```

### 📦 安装与运行

```bash
mcp install @modelcontextprotocol/server-filesystem
mcp start server-filesystem
mcp status
mcp logs server-filesystem -f
```

### 🔌 接入 Agent 与按 Agent 隔离遥测

将 Hub Gateway 添加到 Claude Code、Codex 或其他 MCP 客户端的配置中：

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

仅添加 Gateway 不会自动上传本地调用数据。请在监控页为每个使用的 Agent 分别创建设备，再复制该设备生成的 Gateway 配置。设备令牌在服务端绑定 Agent 类型，事件体不能自行声明或伪造归属。

也可以通过 CLI 生成对应配置：

```bash
# 在监控页为 Codex 创建设备后，使用该设备的一次性遥测令牌
mcp agent config \
  --agent codex \
  --hub-url https://<your-hub-host> \
  --telemetry-token mcpht_<device-token>

# 查看 Codex 自己的离线队列状态
mcp agent status --agent codex
```

每个 Agent 使用独立令牌和默认状态目录，例如 `~/.config/mcp-hub/codex` 与 `~/.config/mcp-hub/claude-code`。监控大屏会显示已注册 Agent，并可按 Agent 筛选 Server 调用、成功率、延迟和 Token。

### 🌐 Web 仪表盘

```
http://localhost:3987
```

实时监控、日志查看、搜索、安装、管理 — 全部在浏览器中完成。

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

**当前: v2.3** — SaaS + 自托管双模式，管理后台功能完整，生产环境运行中。

| 模块 | 核心功能 |
|------|---------|
| 🏪 市场 | 搜索/浏览/对比/推荐/收藏/评价 |
| 📦 我的 Server | 批量操作/重启/调用数据/更新提醒 |
| ⚙️ 配置中心 | 上传匹配/Agent选择/配置下载/草稿 |
| 📋 方案市场 | 发布方案/浏览/一键导入 |
| 📊 监控大屏 | 实时状态/调用/Token/可靠性/按 Agent 筛选 |
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
