# MCP Server Hub — 项目概览

## 项目定位

MCP 生态的一站式管理平台。发现 · 安装 · 管理 · 发布 · 社区。

**核心问题**：MCP Server 越来越多但没有统一管理平台，开发者要手动搜索 GitHub、手动配置 mcp.json、手动管理进程。

## 技术栈

- **后端**: Python 3.10+ / FastAPI / SQLAlchemy 2.0 async
- **数据库**: PostgreSQL 16+（asyncpg）或 SQLite（quickstart 模式）
- **CLI**: Click + Rich（彩色表格/面板/进度条）
- **前端**: React 19 + Tailwind CSS + Vite
- **协议**: MCP (JSON-RPC 2.0 over stdio)

## 目录结构

```
src/mcp_hub/
├── api/           # FastAPI 路由（market/manage/community/health/auth/realtime/config/search/export）
├── cli/           # 36 个 CLI 命令（search/install/manage/quickstart/registry-sync/hub-install/prompt-install 等）
├── core/          # 核心服务（registry/installer/process_manager/health_check/event_bus/mcp_gateway/auth/security）
├── db/            # 数据库（SQLAlchemy ORM + repositories + seed + auto_categorize + enrich）
└── web/           # React 前端（Dashboard/Market/ServerDetail/MyServers/ConfigPage）
deploy/            # 部署脚本（install.sh + install.md + systemd + docker + logging）
```

## 核心功能速览

| 功能 | 说明 |
|------|------|
| **MCP 市场** | 971 个 Server，16 分类，20 标签，9 维筛选 |
| **一键安装** | `mcp install @org/server` → 自动配置 |
| **进程管理** | 启动/停止/重启/三级健康检查/自动恢复 |
| **MCP 网关** | `mcp serve` → 单 stdio 入口聚合所有 Server |
| **多 Agent** | 支持 Claude Code / Cursor / Codex / Trae 配置导出 |
| **零配置启动** | `mcp quickstart` → SQLite + 30 秒上线 |
| **AI 安装提示词** | `mcp prompt-install server` → 生成发给 AI 的安装指令 |
| **注册表同步** | `mcp registry-sync` → 从 npm/PyPI/GitHub 拉取 |
| **GitHub OAuth** + JWT | 真实登录 |
| **SSE 实时日志** | Web 界面实时 tail -f |
| **配置绑定** | 上传/下载 mcp.json |
| **Hub 图标** | 971 个 SVG 首字母图标 |

## 部署方式

```bash
# 生产（PostgreSQL）
mcp init → mcp daemon start

# 零配置（SQLite）
mcp quickstart

# Docker
docker-compose up -d
```

## 关键设计决策

1. **Hub 是市场 + 网关，不是运行时**：Server 默认跑在用户本地或自己的服务器上，Hub 负责发现、配置生成、进程管理
2. **SaaS + 自部署双模式**：没服务器的用户用 Web 界面搜索 + 复制配置到本地；有服务器的用户用 `mcp daemon` 集中管理
3. **多 Agent 兼容**：不是只支持 Claude Code，生成的配置适用于任何 MCP 客户端

## 数据库

- PostgreSQL 生产 / SQLite 快速体验
- 7 张表：servers / reviews / users / favorites / health_logs / events / subscriptions
- ServerModel.id 格式：`@org/server-name`

## 开发测试规则

每次新增或修改模块都要写相应测试。

## 计划规划规则

每执行新任务前先梳理逻辑、想出计划再执行。
