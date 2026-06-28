# MCP Server Hub — 项目快照

> 用于新对话快速恢复上下文的完整项目状态。

## 项目定位

MCP 生态的一站式管理平台。发现 · 安装 · 管理 · 发布 · 社区。
971 个 MCP Server · 36 个 CLI 命令 · 16 个分类 · 20 个标签。

## 部署信息

- **服务器**: `gpu-server` (172.19.138.78), 用户 `djl`
- **代码路径**: 服务器 `/home/djl/code/McpServerHub` / 本地 `e:\硕士方向\...\McpServerHub`
- **服务地址**: `http://172.19.138.78:3987/`
- **运行时**: uvicorn + FastAPI, workers=1, systemd/crontab 自启
- **数据库**: PostgreSQL 18.4 (conda), 库 `mcp_hub`, 用户/密码 `mcp_hub`/`mcp_hub_prod_2026`
- **Conda**: 环境名 `McpServerHub`, Python 3.10
- **GitHub**: `https://github.com/blankbrains/McpServerHub`
- **pip 安装**: `pip install git+https://github.com/blankbrains/McpServerHub.git`

## 技术栈

后端 Python 3.10+ / FastAPI / SQLAlchemy 2.0 async / asyncpg
CLI Click + Rich（彩色表格/面板/进度条）
前端 React 19 + Tailwind CSS + Vite
协议 MCP (JSON-RPC 2.0 over stdio)
认证 GitHub OAuth + 纯 HMAC JWT（无外部依赖）
数据库 PostgreSQL 16+（asyncpg）或 SQLite（quickstart 模式）

## 目录结构

```
src/mcp_hub/
├── api/       11 路由 (market/manage/community/health/auth/realtime/config/search/export + app.py)
├── cli/       18 命令模块 (app.py 注册所有 36 个命令)
├── core/      8 模块 (registry/installer/process_manager/health_check/event_bus/mcp_gateway/auth/security)
├── db/        7 模块 (database/models/repositories/seed/auto_categorize/enrich_servers + __init__)
├── config.py  集中配置，敏感字段仅从 .env 读取
└── web/       React (Dashboard/Market/ServerDetail/MyServers/ConfigPage + 5 组件)
deploy/        install.sh / install.md / mcp-hub.service / logging.conf
```

## 核心功能清单

| 功能 | 实现情况 |
|------|----------|
| MCP 市场 971 Server | ✅ 16 分类 20 标签 9 维筛选 |
| 一键安装 | ✅ `mcp install @org/server` |
| 进程管理 | ✅ 启动/停止/重启/三级健康检查/自动恢复 |
| MCP 网关 | ✅ `mcp serve` 聚合 tools+resources+prompts |
| 多 Agent | ✅ Claude Code / Cursor / Codex / Trae |
| 零配置启动 | ✅ `mcp quickstart` SQLite 30 秒 |
| AI 安装提示词 | ✅ `mcp prompt-install` 生成"请先检查是否已安装..." |
| 注册表同步 | ✅ `mcp registry-sync` 从 npm/PyPI/GitHub |
| 版本管理 | ✅ update/upgrade/rollback/version-history |
| 配置 apply | ✅ `mcp config apply` 写入本地文件 |
| GitHub OAuth | ✅ 真实登录 + JWT |
| SSE 实时日志 | ✅ Web 界面实时 tail -f |
| 配置上传/下载 | ✅ Web 绑定本地 mcp.json |
| 图标 | ✅ 971 个 SVG 首字母图标 |
| Docker | ✅ Dockerfile + docker-compose.yml |
| CI | ✅ GitHub Actions |
| Hub favicon | ✅ 32×32 SVG 蓝紫渐变 M |
| 种子数据清空 bug | ✅ 已修复，启动不再删除已有数据 |
| SPA 路由 404 | ✅ 已修复 |
| 重复启动 500 | ✅ 改为 409 Conflict |
| install_history 表 | ✅ 8 张表 |

## 命令速查

```bash
mcp search|info|compare|install|uninstall|list|start|stop|restart|status
mcp logs|update|upgrade|rollback|version-history|config|daemon|serve|init
mcp quickstart|login|logout|whoami|publish|rate|review|favorite|trending
mcp registry-sync|hub-install|prompt-install|event
```

## 关键设计决策

1. **SQLite + PostgreSQL 双模式**：`MCP_HUB_DATABASE_URL` 以 `sqlite` 开头用 SQLite，否则 PostgreSQL
2. **SaaS + 自部署双模式**：Web 复制配置到本地 或 `mcp daemon` 集中管理
3. **Hub = 市场 + 网关**：Server 默认跑在用户本地或自己服务器上
4. **安全**：敏感配置仅从 `.env` 读取，代码中无任何默认值
5. **全局单例 ProcessManager**：API 和 CLI 共享同一个进程管理器

## .env 配置（服务器上）

```
MCP_HUB_DATABASE_URL=postgresql+asyncpg://mcp_hub:mcp_hub_prod_2026@localhost:5432/mcp_hub
MCP_HUB_SECRET=mcp-hub-prod-secret-key
MCP_HUB_GITHUB_CLIENT_ID=Ov23li9rAd3GLySJaUpC
MCP_HUB_GITHUB_CLIENT_SECRET=f34b991fede4298557345b7ace37c434c0313b33（旧的，已被吊销）
MCP_HUB_GITHUB_REDIRECT_URI=http://172.19.138.78:3987/api/v1/auth/callback
MCP_HUB_CORS_ORIGINS=*
MCP_HUB_WORKERS=1
```

## 遗留问题

- 翻译暂停（用户说算了）
- PyPI 未发布
- HTTPS + 域名未配置
- 部分 CLI 命令 `@community/` 前缀硬编码
