# MCP Server Hub — 项目概览

## 项目定位

MCP 生态的一站式管理平台。发现 · 安装 · 管理 · 发布 · 社区。

**核心问题**：MCP Server 越来越多但没有统一管理平台，开发者要手动搜索 GitHub、手动配置 mcp.json、手动管理进程。

## 部署信息

- **服务器**: `gpu-server` (172.19.138.78), 用户 `djl`
- **代码路径**: 服务器 `/home/djl/code/McpServerHub` / 本地 `e:\硕士方向\...\McpServerHub`
- **服务地址**: `http://172.19.138.78:3987/` → Cloudflare Tunnel
- **运行时**: uvicorn + FastAPI, workers=1, conda env `McpServerHub`
- **数据库**: PostgreSQL 18.4, 库 `mcp_hub`
- **Conda**: 环境名 `McpServerHub`, Python 3.10, 路径 `/home/djl/miniconda3/envs/McpServerHub`
- **GitHub**: `https://github.com/blankbrains/McpServerHub`
- **PyPI**: `pip install mcp-hub-cli`

## 技术栈

- **后端**: Python 3.10+ / FastAPI / SQLAlchemy 2.0 async
- **数据库**: PostgreSQL 16+（asyncpg）或 SQLite（quickstart 模式）
- **CLI**: Click + Rich（彩色表格/面板/进度条）
- **前端**: React 19 + Tailwind CSS + Vite
- **协议**: MCP (JSON-RPC 2.0 over stdio)
- **认证**: GitHub OAuth + 纯 HMAC JWT（无外部依赖）
- **安全**: 四维评分引擎（命令/包/发布者/代码模式）
- **Token 分析**: tiktoken + 优化引擎（分析工具定义上下文占比）
- **监控**: 三级健康检查 + 可靠性评分（uptime/响应时间/排行榜）
- **迁移**: Alembic（本地开发用，已.gitignore）

## 目录结构

```
src/mcp_hub/
├── main.py              # FastAPI 应用入口
├── config.py            # 集中配置，敏感字段仅从 .env 读取
├── exceptions.py        # 统一异常体系 (McpHubError + 12 子类)
├── logging_config.py    # structlog 结构化日志
│
├── api/                 # 15 个路由模块
│   ├── app.py           # FastAPI 实例 + CORS + 中间件 + 路由注册
│   ├── routes_market.py / routes_manage.py / routes_community.py
│   ├── routes_health.py / routes_auth.py / routes_realtime.py
│   ├── routes_config.py / routes_search.py / routes_export.py
│   ├── routes_security.py / routes_token.py / routes_builder.py
│   └── schemas.py       # Pydantic 模型 (ApiResponse/ErrorDetail)
│
├── cli/                 # 24 个命令模块 → 注册 46 个 CLI 命令
│   ├── app.py           # Click 主入口 + 所有命令注册
│   ├── search.py / install.py / manage.py / logs.py
│   ├── update.py / config.py / daemon.py
│   ├── publish.py / community.py / trending.py / event.py / auth.py
│   ├── security.py / token.py / monitor.py / create.py
│   ├── hub_install.py / prompt_install.py / registry_sync.py
│   ├── init_cmd.py / quickstart.py
│   └── ...
│
├── core/                # 12 个核心服务模块
│   ├── registry.py           # Server 注册与索引
│   ├── installer.py          # 安装执行器 (pip/npm/uvx)
│   ├── process_manager.py    # 子进程生命周期管理
│   ├── health_check.py       # 三级健康检查 (L1/L2/L3)
│   ├── event_bus.py          # 事件总线 (Pub/Sub)
│   ├── mcp_gateway.py        # MCP 网关 (单 stdio 聚合)
│   ├── auth.py               # GitHub OAuth + JWT
│   ├── security_scanner.py   # 四维安全评分引擎
│   ├── token_analyzer.py     # Token 消耗分析 + 优化
│   ├── server_builder.py     # MCP Server 构建器 (8 模板)
│   ├── monitor.py            # 质量监控网络 (可靠性评分)
│   ├── config_manager.py     # 配置管理
│   └── version_manager.py    # 版本管理
│
├── db/                  # 7 个数据库模块
│   ├── database.py      # SQLAlchemy async engine + session
│   ├── models.py        # 10 张表的 ORM 模型
│   ├── repositories.py  # 数据访问层
│   ├── migrations.py    # Alembic 异步迁移
│   ├── seed.py          # 18 个高质量种子 Server
│   ├── auto_categorize.py
│   └── enrich_servers.py
│
├── models/              # Pydantic 模型 (server/review/user)
└── web/                 # React 前端
    ├── app.py           # 静态文件服务 + SPA fallback
    └── src/
        ├── pages/       # Dashboard / Market / ServerDetail / MyServers / ConfigPage / Builder / MyConfig
        └── components/  # StatusBadge / StarRating / LogViewer / ServerCard / Layout
```

## 核心功能速览

| 功能 | 说明 |
|------|------|
| **MCP 市场** | 983+ 个 Server，16 分类，20+ 标签，9 维筛选 |
| **一键安装** | `mcp install @org/server` → 自动配置 |
| **进程管理** | 启动/停止/重启/三级健康检查/自动恢复 |
| **MCP 网关** | `mcp serve` → 单 stdio 入口聚合所有 Server |
| **多 Agent** | 支持 Claude Code / Cursor / Codex / Trae 配置导出 |
| **零配置启动** | `mcp quickstart` → SQLite + 30 秒上线 |
| **AI 安装提示词** | `mcp prompt-install server` → 生成发给 AI 的安装指令 |
| **注册表同步** | `mcp registry-sync` → 从 npm/PyPI/GitHub 拉取 |
| **GitHub OAuth** + JWT | 真实登录 + 纯 HMAC JWT |
| **SSE 实时日志** | Web 界面实时 tail -f |
| **配置绑定** | 上传/下载 mcp.json + 用户隔离 |
| **Hub 图标** | 983+ 个 SVG 首字母图标 |
| **🛡️ 安全评分** | 四维评分引擎（命令/包/发布者/代码模式）→ blocked(<50) 阻止安装 |
| **📊 Token 分析** | tiktoken 精确计数 + 优化建议 + 同类对比 |
| **🛠️ Server Builder** | 8 个工具模板 → 交互式 CLI 向导 + Web Builder |
| **📈 质量监控** | 可靠性评分 (uptime×40%+7d×30%+响应×20%+1h×10%) |

## 部署方式

```bash
# 生产（PostgreSQL）
mcp init → mcp daemon start

# 零配置（SQLite）
mcp quickstart

# Docker
docker-compose up -d
```

## 数据库

- PostgreSQL 生产 / SQLite 快速体验
- 10 张表：servers / reviews / users / favorites / health_logs / events / subscriptions / install_history / user_servers / alembic_version
- ServerModel.id 格式：`@org/server-name`

## 关键设计决策

1. **Hub 是市场 + 网关，不是运行时**：Server 默认跑在用户本地或自己的服务器上，Hub 负责发现、配置生成、进程管理
2. **SaaS + 自部署双模式**：没服务器的用户用 Web 界面搜索 + 复制配置到本地；有服务器的用户用 `mcp daemon` 集中管理
3. **多 Agent 兼容**：不是只支持 Claude Code，生成的配置适用于任何 MCP 客户端
4. **SQLite + PostgreSQL 双模式**：`MCP_HUB_DATABASE_URL` 以 `sqlite` 开头用 SQLite，否则 PostgreSQL
5. **全局单例 ProcessManager**：API 和 CLI 共享同一个进程管理器
6. **敏感配置**：仅从 `.env` 读取，代码中无任何默认值
7. **四维安全评分**：命令安全(40)+包信誉(25)+发布者可信度(20)+代码模式(15)
8. **评价系统**：支持叠层回复 (parent_id)，作者/发布者/管理员可删除
9. **配置同步**：`mcp config sync --server <url>` 一键从 Hub 拉取配置写入本地

## 基础设施

- **异常体系**: `exceptions.py` — McpHubError 基类 + 12 个子类，FastAPI 全局 handler
- **结构化日志**: `logging_config.py` — structlog 配置，JSON/console 双模式
- **API Schema**: `api/schemas.py` — ApiResponse/ErrorDetail 统一响应格式
- **数据库迁移**: Alembic + `db/migrations.py` — 版本化异步迁移
- **IDE**: `.vscode/settings.json` + `extensions.json`
- **Git hooks**: `.hooks/pre-commit` — Ruff + mypy + pytest
- **CI/CD**: GitHub Actions (`ci.yml` + `deploy.yml`)

## 命令大全（46 个）

```
🛒 市场: search / info / compare
📦 安装: install / uninstall / list
🔒 安全: security / security --all
📊 Token: analyze / analyze --all / optimize
📈 监控: monitor / monitor --all / monitor --watch / reliability
⚙️ 管理: start / stop / restart / status / logs / update / upgrade / rollback / version-history / config
🛠️ 构建: create
🔧 系统: daemon / serve / init / quickstart
👤 认证: login / logout / whoami
📤 发布: publish / my-servers / unpublish / stats
⭐ 社区: rate / review / favorite / favorites / trending / top-rated / most-downloaded / new-releases
🎯 高级: prompt-install / hub-install / registry-sync
📡 事件: event publish / subscribe / list / history
```

## 开发测试规则

每次新增或修改模块都要写相应测试。当前 206 个测试覆盖 exceptions/logging/health_check/models/api_schemas/security_scanner/token_analyzer/server_builder/monitor。

## 计划规划规则

每执行新任务前先梳理逻辑、想出计划再执行。

## 已知问题

- Cloudflare Tunnel 临时域名，重启后会变
- gpu-server 用 `python3` 而非 `python`，重启命令需注意
- `mcp monitor` 需要 daemon 模式 + 已安装并启动 Server 才有数据
- Token 分析在没有实际工具定义时只能做估算
- 部分 CLI 命令 `@community/` 前缀硬编码
