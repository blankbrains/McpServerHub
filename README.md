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
- **上传配置**：网页仅接收根节点为 `mcpServers` 的 JSON，并自动匹配市场 Server
- **确认追踪**：配置检查不会写入账户；用户确认后才更新个人追踪列表
- **Agent 选择**：支持 Claude Code / Codex / Cursor / Windsurf / VS Code Copilot / Trae 和通用 MCP 客户端
- **配置草稿**：保存多套配置方案（工作用/个人用），一键切换
- **配置方案市场**：发布你的配置方案，浏览他人方案，一键导入
- **多格式生成**：导出与 `agent setup` 会按 Agent 生成或迁移 `mcpServers`、`servers` 和 Codex TOML；网页上传不解析 TOML 或根节点为 `servers` 的 JSON
- **安全迁移**：`mcp-hub agent setup` 先预览和确认，再备份原配置并迁移 stdio、Streamable HTTP 与 SSE Server
- **完整进程配置**：保留结构化 `command`、`args`、按 Server 授权的 `env`、`cwd` 和启用状态

### 📦 Server 管理
- **我的 Server**：个人追踪、Gateway 接入状态、同步开关、真实调用与估算 Token 指标
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

下面先介绍最常见的场景：**Hub 已运行在服务器上，你要在自己的电脑上接入 Codex、Claude Code、Cursor 等 Agent，并监控本地 MCP 调用**。

> 当前 `0.2.0` 尚未发布到 PyPI。不要执行 `pip install mcp-hub-cli==0.2.0`，请按下面步骤从 GitHub 安装。

### A. 使用服务器 Hub 监控本地 MCP

#### 1. 安装 uv

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS / Linux：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装后关闭并重新打开终端，确认 `uv --version` 可以执行。

#### 2. 从 GitHub 安装 mcp-hub CLI

```bash
uv tool install --force "git+https://github.com/blankbrains/McpServerHub.git@main"
uv tool update-shell
```

再次关闭并重新打开终端，然后验证：

```bash
mcp-hub --version
```

必须保证 `mcp-hub` 在系统 `PATH` 中，因为接入后 Agent 配置会使用 `mcp-hub serve` 启动本地 Gateway。若命令仍找不到，重新运行 `uv tool update-shell` 并重开终端。

#### 3. 检查本机能访问 Hub

将下面的地址替换成浏览器正在访问的 Hub 地址：

Windows PowerShell：

```powershell
$HubUrl = "http://<Hub地址>:3987"
Invoke-RestMethod "$HubUrl/api/v1/health"
```

macOS / Linux：

```bash
export HUB_URL="http://<Hub地址>:3987"
curl "$HUB_URL/api/v1/health"
```

响应中的 `status` 必须为 `healthy`。如果无法访问，先处理局域网、VPN、防火墙、端口或服务器地址问题；服务器能够打开网页不代表运行 Agent 的电脑一定能访问它。

#### 4. 确认 Agent 已有 MCP Server

`mcp-hub agent setup` 负责迁移现有连接，不负责创建第一个 MCP Server。开始前，目标 Agent 至少要有一个可以正常使用的 stdio、Streamable HTTP 或 SSE Server。

常见配置路径：

| Agent | 默认配置路径 |
|------|-------------|
| Codex | `~/.codex/config.toml` |
| Claude Code | `~/.claude.json`、`~/.claude/mcp.json` 或项目 `.mcp.json` |
| Claude Desktop | `Claude/claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| VS Code Copilot | 项目 `.vscode/mcp.json` |
| Trae | `~/.trae/mcp.json` |

#### 5. 在网页创建设备

1. 在 Hub 网页完成 GitHub 登录。
2. 打开“监控”页面。
3. 选择你实际使用的 Agent，例如 `Codex`。
4. 输入可识别的设备名称并点击“创建”。
5. 保留页面，不要刷新。设备令牌只显示一次。

每个 Agent 使用一个独立设备令牌。令牌不要截图、写入文档、提交到 Git 或发送给他人；一旦泄露，应立即在监控页撤销并重新创建。

#### 6. 运行页面生成的完整接入命令

监控页会显示包含真实 Hub 地址和设备令牌的完整命令。优先复制页面生成的命令，不要照抄下面的示例令牌：

```bash
mcp-hub agent setup --agent codex --hub-url http://<Hub地址>:3987 --telemetry-token mcpht_<设备令牌>
```

CLI 会先展示迁移预览。确认后才会：

1. 为原 Agent 配置创建带时间戳的备份。
2. 把可代理 Server 的完整本地配置写入 Agent 独立的 `gateway.json`。
3. 在 Agent 主配置中用 `mcp-hub serve` 替换受支持的直接连接。
4. 保留无法安全迁移的条目，不会静默删除。
5. 上报脱敏设备清单；不会上传环境变量值、请求头值、完整命令、URL、工具参数或响应正文。

如果提示“没有可迁移到 Gateway 的 MCP Server”，先检查第 4 步中的 Agent 配置路径和 Server 传输格式；必要时使用 `--source-config <配置文件路径>` 明确指定源文件。

#### 7. 完全重启 Agent

关闭目标 Agent 的所有进程后重新打开。仅刷新界面、关闭当前对话或新建会话通常不够。重启后的 Agent 进程必须能从 `PATH` 找到 `mcp-hub`。

#### 8. 触发真实调用并验证

让 Agent 实际调用一次已迁移 MCP Server 的工具，然后回到监控页点击“刷新”。

应至少看到：

- 设备“最后在线”时间更新。
- Server 调用数增加。
- 工具调用、延迟、成功率或错误分类出现数据。
- 估算 Token 随调用变化。

只打开 Agent、查看工具列表或进行未调用 MCP 工具的普通对话，不会产生 `tool_call` 数据。未经过本地 Gateway 的直接连接也不会被监控。

#### 9. 没有数据时排查

```bash
mcp-hub agent status --agent codex
mcp-hub agent doctor --agent codex
```

按顺序检查：

1. `mcp-hub --version` 是否能在新终端执行。
2. Hub 健康接口是否能从运行 Agent 的电脑访问。
3. 设备是否仍有效，Agent 类型是否选对。
4. `agent setup` 是否成功生成 `gateway.json` 和原配置备份。
5. Agent 是否完全重启并读取了新配置。
6. 是否实际调用了 MCP 工具，而不是只打开 Agent。
7. Agent 配置是否仍保留绕过 Gateway 的同名直接连接。
8. 本地队列是否有待上传事件；网络恢复后会自动重试。

当前站点若通过 HTTP 访问，浏览器可能限制标准剪贴板 API。页面会自动尝试兼容复制；若浏览器仍拒绝，完整命令会保持可见并可选中，可手动按 `Ctrl+C`，macOS 使用 `Cmd+C`。

### B. 在本机自托管整个 Hub

仅在你要同时运行 Web、API 和数据库时使用这一方式。它与“连接服务器 Hub 监控本地 MCP”不是同一件事。

SQLite 快速启动：

```bash
mcp-hub quickstart
# 打开 http://localhost:3987
```

Quickstart 配置保存在 `~/.config/mcp-hub/.env`。默认生成的 GitHub OAuth 占位值不能用于真实登录；需要登录时，请在该文件中填写 GitHub OAuth App 的 Client ID、Client Secret 和回调地址后重新启动。

PostgreSQL 初始化：

```bash
mcp-hub init
mcp-hub daemon start
# 打开 http://localhost:3987
```

Docker：

```bash
git clone https://github.com/blankbrains/McpServerHub
cd McpServerHub
cp .env.example .env
# 在 .env 中填写数据库、MCP_HUB_SECRET 和 GitHub OAuth 配置
docker compose up -d
```

GitHub 登录需要正确配置 OAuth Client ID、Client Secret 和回调地址；不登录时只能浏览市场和公开页面。

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

完整首次接入流程见上面的“使用服务器 Hub 监控本地 MCP”。首次接入后，在网页调整个人 Server 清单时，可以同步 Gateway：

```bash
mcp-hub config sync \
  --agent codex \
  --server http://<Hub地址>:3987
```

同步个人配置前需要先完成网页登录与 CLI 登录。同步会备份 `gateway.json`，保留本地环境变量、请求头和工作目录，不覆盖 Agent 主配置；同步完成后需要重启 Agent。

本地诊断：

```bash
mcp-hub agent status --agent codex
mcp-hub agent doctor --agent codex
```

每个 Agent 使用独立令牌和默认状态目录，例如 `~/.config/mcp-hub/codex` 与 `~/.config/mcp-hub/claude-code`。监控大屏会显示已注册 Agent，并可按 Agent 筛选 Server 调用、成功率、延迟和估算 Token。

> 浏览器不能直接扫描用户电脑。只有用户本地 CLI/Gateway 主动发现、代理和上报的数据才会出现在 SaaS Hub 中。Agent 直连 Server 的调用不会经过 Gateway，因此无法监控。

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
| **监控** | 市场健康检查与可靠性评分 + 本地 Gateway 调用、延迟、错误、资源和估算 Token 遥测 |

---

## 📊 项目状态

**当前版本：0.2.0** — 中心 Hub + 本地 Gateway 为推荐架构，同时保留显式启用的自托管进程管理。

| 模块 | 核心功能 |
|------|---------|
| 🏪 市场 | 搜索/浏览/对比/推荐/收藏/评价 |
| 📦 我的 Server | 追踪列表/同步开关/Gateway 状态/调用数据/更新提醒 |
| ⚙️ 配置中心 | 上传匹配/确认追踪/原生配置导出/Gateway 同步/草稿 |
| 📋 方案市场 | 发布方案/浏览/一键导入 |
| 📊 监控大屏 | 调用趋势/P95 延迟/估算 Token/字节/工具/协议/CPU/内存/错误分类 |
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
